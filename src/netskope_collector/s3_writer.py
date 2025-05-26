"""
S3 upload module for the Netskope Event Collector.

This module provides functionality to write event data to Amazon S3
in gzip-compressed JSON Lines format using multipart upload.
Each file is uploaded with integrity checks via CRC32 checksums,
and the structure is organized by endpoint and timestamp.

Features:
---------
- Multipart uploads with automatic part sizing
- Streamed gzip+JSONL file creation
- CRC32 checksums for data integrity (S3-compatible)
- ISO 8601 timestamp-based directory structure
"""

from __future__ import annotations

import base64
import gzip
import io
import json
import math
import zlib
from datetime import datetime, timezone
from typing import Iterable, List

import boto3
from .logger import get_logger

logger = get_logger(__name__)
PART_SIZE = 8 * 1024 * 1024  # 8 MiB


def _crc32_base64(data: bytes) -> str:
    """
    Calculate a base64-encoded CRC32 checksum for a given byte buffer.

    This format is required by S3 multipart uploads with CRC32 integrity checks.

    Parameters:
    -----------
    data : bytes
        The binary payload to checksum.

    Returns:
    --------
    str
        Base64-encoded CRC32 value in big-endian byte order.
    """
    crc_val = zlib.crc32(data) & 0xFFFFFFFF
    return base64.b64encode(crc_val.to_bytes(4, "big")).decode()


class S3Writer:
    """
    Streamed multipart uploader for gzip-compressed JSON Lines to Amazon S3.

    This class receives an iterator of event dictionaries and writes them to S3
    using multipart upload. Events are compressed using gzip and stored in the
    following path format:

        <prefix>/<endpoint>/YYYY/MM/DD/HHMMSS.jsonl.gz

    Attributes:
    -----------
    bucket : str
        The name of the S3 bucket where files are uploaded.
    prefix : str
        An optional S3 key prefix for logical file organization.
    s3 : boto3.client
        The S3 client instance configured with optional endpoint and region.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str | None = None,
    ) -> None:
        """
        Initialize the S3Writer.

        Parameters:
        -----------
        bucket : str
            The S3 bucket name.
        prefix : str, optional
            Optional S3 key prefix. Will be normalized to end with '/' if provided.
        endpoint_url : Optional[str]
            Custom S3 endpoint (e.g., LocalStack).
        region : Optional[str]
            AWS region name.
        """
        self.bucket = bucket
        self.prefix = (prefix.rstrip("/") + "/") if prefix else ""
        self.s3 = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

    def write_events(self, events_iter: Iterable[dict], *, endpoint: str) -> str:
        """
        Stream event data to S3 using multipart gzip-compressed JSON Lines format.

        Events are written incrementally in parts of size `PART_SIZE`. CRC32
        checksums are computed and included in the final multipart completion request.

        Parameters:
        -----------
        events_iter : Iterable[dict]
            An iterator of event dictionaries to be serialized and uploaded.
        endpoint : str
            The logical endpoint name used for path construction in S3.

        Returns:
        --------
        str
            The S3 object key where the data was uploaded.

        Raises:
        -------
        Exception
            If an upload part or completion fails, the multipart upload is aborted.
        """
        now = datetime.now(timezone.utc)
        date_folder = now.strftime("%Y/%m/%d")  # 2025/05/26
        fname = f"{now.strftime('%H%M%S')}.jsonl.gz"  # 050246.jsonl.gz
        key = f"{self.prefix}{endpoint}/{date_folder}/{fname}"

        logger.info("Start multipart upload: s3://%s/%s", self.bucket, key)
        mp = self.s3.create_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            ChecksumAlgorithm="CRC32",
        )
        upload_id: str = mp["UploadId"]
        parts: List[dict] = []

        try:
            part_no, buf = 1, io.BytesIO()
            gz = gzip.GzipFile(fileobj=buf, mode="wb")

            for ev in events_iter:
                gz.write(json.dumps(ev, separators=(",", ":")).encode() + b"\n")
                if buf.tell() >= PART_SIZE:
                    gz.close()
                    parts.append(self._upload_part(buf, key, upload_id, part_no))
                    part_no, buf = part_no + 1, io.BytesIO()
                    gz = gzip.GzipFile(fileobj=buf, mode="wb")

            gz.close()
            parts.append(self._upload_part(buf, key, upload_id, part_no))

            self.s3.complete_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [
                        {
                            "PartNumber": p["PartNumber"],
                            "ETag": p["ETag"],
                            "ChecksumCRC32": p["ChecksumCRC32"],
                        }
                        for p in parts
                    ]
                },
            )
            size_mb = math.ceil(sum(p["Size"] for p in parts) / 1_048_576)
            logger.info("Upload complete (%d parts, ~%d MiB)", len(parts), size_mb)
            return key

        except Exception:
            logger.exception("Abort multipart upload due to error")
            self.s3.abort_multipart_upload(
                Bucket=self.bucket, Key=key, UploadId=upload_id
            )
            raise

    def _upload_part(
        self, buf: io.BytesIO, key: str, upload_id: str, part_no: int
    ) -> dict:
        """
        Upload a single part to S3 with CRC32 checksum calculation.

        Parameters:
        -----------
        buf : io.BytesIO
            The byte buffer containing the part payload.
        key : str
            The full S3 object key being uploaded.
        upload_id : str
            The multipart upload ID.
        part_no : int
            The 1-based part number.

        Returns:
        --------
        dict
            Metadata for the uploaded part including part number, ETag, size, and checksum.
        """
        buf.seek(0)
        payload = buf.getvalue()
        checksum_b64 = _crc32_base64(payload)

        logger.debug(
            "Uploading part %d (size=%d bytes, crc32=%s)",
            part_no,
            len(payload),
            checksum_b64,
        )
        resp = self.s3.upload_part(
            Bucket=self.bucket,
            Key=key,
            PartNumber=part_no,
            UploadId=upload_id,
            Body=payload,
            ChecksumCRC32=checksum_b64,
        )
        return {
            "PartNumber": part_no,
            "ETag": resp.get("ETag", ""),
            "Size": len(payload),
            "ChecksumCRC32": checksum_b64,
        }
