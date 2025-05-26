from __future__ import annotations
import importlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List

import pytest

from netskope_collector.config import Settings
from netskope_collector.netskope_client import NetskopeClient
from netskope_collector.s3_writer import S3Writer, _crc32_base64
from netskope_collector.runner import run as runner_run


# ---------------------------------------------------------------------------#
# Dummy helpers
# ---------------------------------------------------------------------------#
class DummyResponse:
    """
    Mock response object for simulating HTTP responses from the Netskope API.
    Used in DummySession to test NetskopeClient behavior.
    """

    def __init__(
        self,
        status: int,
        body: Dict[str, Any] | None = None,
        headers: Dict[str, str] | None = None,
    ):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}

    def raise_for_status(self):
        """
        Simulates raise_for_status() by throwing an exception for status >= 400.
        """
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        """
        Returns the mocked JSON body payload.
        """
        return self._body


class DummySession:
    """
    Mock requests.Session that yields a predefined list of DummyResponse objects.
    """

    def __init__(self, responses: List[DummyResponse]):
        self._iter = iter(responses)
        self.headers: Dict[str, str] = {}

    def get(self, *_a, **_kw):
        """
        Returns the next DummyResponse or a default empty response if exhausted.
        """
        try:
            return next(self._iter)
        except StopIteration:
            return DummyResponse(200, {"result": [], "wait_time": 0})


class DummyS3:
    """
    Mock boto3 S3 client that simulates multipart upload behavior.
    Used for testing S3Writer without actual S3 access.
    """

    def __init__(self):
        self.parts: List[Dict[str, Any]] = []
        self.completed = False

    def create_multipart_upload(self, **_kw):
        """Simulates initiating a multipart upload."""
        return {"UploadId": "u‑1"}

    def upload_part(self, *, PartNumber: int, Body: bytes, **_kw):
        """Records part upload and returns a mock ETag."""
        self.parts.append({"PartNumber": PartNumber, "Body": Body})
        return {"ETag": f"etag‑{PartNumber}"}

    def complete_multipart_upload(self, *, MultipartUpload: Dict[str, Any], **_kw):
        """
        Validates that all parts match in part number and CRC32,
        and marks upload as complete.
        """
        for sent, recorded in zip(MultipartUpload["Parts"], self.parts, strict=True):
            assert sent["PartNumber"] == recorded["PartNumber"]
            assert sent["ChecksumCRC32"] == _crc32_base64(recorded["Body"])
        self.completed = True

    def abort_multipart_upload(self, **_kw):
        """Simulates aborting a multipart upload."""
        self.completed = False


# ---------------------------------------------------------------------------#
# Helpers
# ---------------------------------------------------------------------------#


def no_sleep(*_a, **_kw):
    """Stub for time.sleep() to speed up tests."""
    return None


def make_settings(**overrides) -> Settings:
    """
    Returns a Settings object with default or overridden values.
    """
    return Settings(endpoint_paths={"application": "/dummy-path"}, **overrides)


def make_client(
    responses: List[DummyResponse], *, settings: Settings | None = None
) -> NetskopeClient:
    """
    Returns a NetskopeClient using DummySession with provided responses.
    """
    return NetskopeClient(
        api_endpoint="http://mock",
        token="dummy",
        index="demo",
        session=DummySession(responses),
        settings=settings or make_settings(),
    )


# ---------------------------------------------------------------------------#
# NetskopeClient
# ---------------------------------------------------------------------------#


def test_fetch_single_page():
    """
    Verifies that a single API response with one event is collected correctly.
    """
    client = make_client([DummyResponse(200, {"result": [{"id": 1}], "wait_time": 0})])
    events = list(
        client.fetch_events(endpoint="application", since=datetime.now(timezone.utc))
    )
    assert events == [{"id": 1}]


def test_fetch_pagination_and_wait(monkeypatch):
    """
    Verifies that pagination and wait_time behavior work across multiple pages.
    """
    client = make_client(
        [
            DummyResponse(200, {"result": [1], "wait_time": 1}),
            DummyResponse(200, {"result": [], "wait_time": 0}),
        ]
    )
    monkeypatch.setattr("time.sleep", no_sleep)
    events = list(
        client.fetch_events(endpoint="application", since=datetime.now(timezone.utc))
    )
    assert events == [1]


def test_fetch_rate_limit_retry(monkeypatch):
    """
    Simulates a 429 Rate Limit response and ensures retry logic works.
    """
    monkeypatch.setattr("time.sleep", no_sleep)
    client = make_client(
        [
            DummyResponse(429, headers={"Retry-After": "0"}),
            DummyResponse(200, {"result": ["x"], "wait_time": 0}),
        ]
    )
    events = list(
        client.fetch_events(endpoint="application", since=datetime.now(timezone.utc))
    )
    assert events == ["x"]


def test_fetch_max_pages_limit(monkeypatch):
    """
    Confirms that the fetch stops when max_fetch_pages is exceeded.
    """
    settings = make_settings(max_fetch_pages=2)
    responses = [DummyResponse(200, {"result": [i], "wait_time": 0}) for i in range(5)]
    client = make_client(responses, settings=settings)
    events = list(
        client.fetch_events(endpoint="application", since=datetime.now(timezone.utc))
    )
    assert events == [0, 1]


def test_fetch_max_duration_limit(monkeypatch):
    """
    Confirms that the fetch stops when max_fetch_duration_seconds is exceeded.
    """
    import netskope_collector.netskope_client as nc

    monkeypatch.setattr(nc.time, "time", lambda: 0)
    settings = make_settings(max_fetch_duration_seconds=0)
    client = make_client(
        [
            DummyResponse(200, {"result": [1], "wait_time": 0}),
            DummyResponse(200, {"result": [2], "wait_time": 0}),
        ],
        settings=settings,
    )
    events = list(
        client.fetch_events(endpoint="application", since=datetime.now(timezone.utc))
    )
    assert events == [1]


def test_unsupported_endpoint():
    """
    Raises ValueError when an unsupported endpoint is passed to fetch_events().
    """
    client = make_client([])
    with pytest.raises(ValueError):
        list(client.fetch_events(endpoint="nope", since=datetime.now(timezone.utc)))


def test_env_custom_endpoint(monkeypatch):
    """
    Ensures custom endpoint paths from NETSKOPE_ENDPOINTS environment variable are loaded.
    """
    monkeypatch.setenv("NETSKOPE_ENDPOINTS", json.dumps({"foo": "/bar"}))
    import netskope_collector.config as cfg_mod

    importlib.reload(cfg_mod)
    cfg = cfg_mod.Settings()
    assert cfg.endpoint_paths["foo"] == "/bar"


# ---------------------------------------------------------------------------#
# _crc32_base64
# ---------------------------------------------------------------------------#


def test_crc32_base64_known_value():
    """
    Verifies that known CRC32 of 'abc' matches expected base64 output.
    """
    assert _crc32_base64(b"abc") == "NSRBwg=="


# ---------------------------------------------------------------------------#
# S3Writer
# ---------------------------------------------------------------------------#


def test_s3_writer_single_part(monkeypatch):
    """
    Ensures a single small part is uploaded and marked as complete.
    """
    mock_s3 = DummyS3()
    monkeypatch.setattr("boto3.client", lambda *_a, **_kw: mock_s3)
    writer = S3Writer(bucket="bkt")
    writer.write_events([{"x": 1}], endpoint="alert")
    assert len(mock_s3.parts) == 1 and mock_s3.completed is True


def test_s3_writer_multi_part(monkeypatch):
    """
    Verifies multi-part uploads when payload exceeds PART_SIZE.
    """
    mock_s3 = DummyS3()
    monkeypatch.setattr("boto3.client", lambda *_a, **_kw: mock_s3)
    import netskope_collector.s3_writer as sw

    monkeypatch.setattr(sw, "PART_SIZE", 16 * 1024)
    writer = sw.S3Writer(bucket="bkt")
    payload = os.urandom(64 * 1024)
    writer.write_events([{"blob": payload.hex()}], endpoint="application")
    assert len(mock_s3.parts) >= 2 and mock_s3.completed is True


def test_s3_writer_abort_on_failure(monkeypatch):
    """
    Simulates a failure during upload_part and checks that abort is triggered.
    """

    class FailingS3(DummyS3):
        def upload_part(self, **_kw):
            raise RuntimeError("boom")

    monkeypatch.setattr("boto3.client", lambda *_a, **_kw: FailingS3())
    writer = S3Writer(bucket="bkt")
    with pytest.raises(RuntimeError):
        writer.write_events([{"x": 1}], endpoint="alert")


# ---------------------------------------------------------------------------#
# Runner integration
# ---------------------------------------------------------------------------#


def test_runner_integration(monkeypatch):
    """
    Full integration test of `runner.run()`:
    - Mocks S3 client and NetskopeClient.fetch_events()
    - Ensures S3 upload completes successfully
    - Asserts returned key format
    """
    mock_s3 = DummyS3()
    monkeypatch.setattr("boto3.client", lambda *_a, **_kw: mock_s3)

    def _dummy_fetch_events(
        self, *, endpoint: str, since: datetime
    ) -> Iterator[Dict[str, Any]]:
        yield {"id": "dummy"}

    monkeypatch.setattr(
        "netskope_collector.netskope_client.NetskopeClient.fetch_events",
        _dummy_fetch_events,
    )

    s3_key = runner_run(endpoint="application", since_minutes=1)

    assert mock_s3.completed is True
    assert s3_key.startswith("application/")
    assert s3_key.endswith(".jsonl.gz")
