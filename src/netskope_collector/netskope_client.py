"""
Netskope API client module for the Event Collector.

This module provides a typed, retry-aware HTTP client for interacting with
the Netskope Data Export Iterator API. It handles pagination, rate limits,
timeouts, and streaming iteration of event data.

Features:
---------
- Retrieves event data from Netskope's iterator-based endpoints
- Supports configurable retry behavior and pagination
- Integrates with the application-wide `Settings` object
- Yields parsed event records as Python dictionaries
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterator

import requests

from .config import Settings
from .logger import get_logger

logger = get_logger(__name__)


class NetskopeClient:
    """
    HTTP client for the Netskope Data Export Iterator API.

    This client supports iterator-based access to security event logs
    (e.g., application, network, alert) and handles:

    - Authorization via Bearer token
    - Rate limit handling (HTTP 429 with retry)
    - Page-based iteration and early termination
    - Streaming of event data as dictionaries

    Attributes:
    -----------
    base_url : str
        Base URL of the Netskope API (without trailing slash).
    index : str
        Iterator index used for client isolation.
    settings : Settings
        Configuration object with API and fetch limits.
    session : requests.Session
        Reusable HTTP session for making requests.
    """

    def __init__(
        self,
        api_endpoint: str,
        token: str,
        index: str,
        session: requests.Session | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize the NetskopeClient instance.

        Parameters:
        -----------
        api_endpoint : str
            Base URL of the Netskope API (e.g., "https://tenant.goskope.com").
        token : str
            Bearer token for API authentication.
        index : str
            Iterator index name for tracking pagination state.
        session : Optional[requests.Session]
            Optional HTTP session for request reuse (injectable for testing).
        settings : Optional[Settings]
            Configuration object (uses default if not provided).
        """
        self.base_url = api_endpoint.rstrip("/")
        self.index = index
        self.settings = settings or Settings()
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    # ------------------------------------------------------------------ #
    def fetch_events(
        self,
        *,
        endpoint: str,
        since: datetime,
    ) -> Iterator[Dict[str, Any]]:
        """
        Fetch events from the Netskope API and stream them as an iterator.

        This method performs paginated retrieval of events starting from the
        given UTC timestamp. It respects maximum page limits, duration limits,
        and server-specified `wait_time` instructions.

        Parameters:
        -----------
        endpoint : str
            One of the supported keys (e.g., "application", "alert", "network").
        since : datetime
            UTC timestamp indicating the start of the collection window.

        Yields:
        -------
        Dict[str, Any]
            Parsed event objects from Netskope API.

        Raises:
        -------
        ValueError:
            If an unsupported endpoint is specified.
        requests.RequestException:
            For any unrecoverable network or HTTP error.
        """

        max_pages = self.settings.max_fetch_pages
        max_duration_seconds = self.settings.max_fetch_duration_seconds

        path = self.settings.endpoint_paths.get(endpoint)
        if path is None:
            raise ValueError(f"Unsupported endpoint: {endpoint!r}")

        url = f"{self.base_url}{path}"
        params: Dict[str, Any] = {
            "operation": int(since.replace(tzinfo=timezone.utc).timestamp()),
            "index": self.index,
        }

        start_time = time.time()
        page_count = 0

        while True:
            logger.info("Fetching '%s' events ...", endpoint)
            logger.debug("GET %s params=%s", url, params)

            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as e:
                logger.warning("Request failed: %s", str(e))
                break

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                logger.warning(
                    "Rate limit hit (429); sleeping for %d seconds", retry_after
                )
                time.sleep(retry_after)
                continue

            resp.raise_for_status()

            body = resp.json()
            events = body.get("result", [])
            wait_time = int(body.get("wait_time", 0))

            logger.debug("Received %d events, wait_time=%s", len(events), wait_time)
            yield from events

            page_count += 1
            elapsed = time.time() - start_time

            if not events and wait_time == 0:
                logger.info("No more events; iterator finished")
                break
            if page_count >= max_pages:
                logger.warning("Max page limit reached (%d)", max_pages)
                break
            if elapsed >= max_duration_seconds:
                logger.warning("Max duration reached (%.1f sec)", elapsed)
                break

            if wait_time > 0:
                logger.debug("Sleeping %s sec (server wait_time)", wait_time)
                time.sleep(wait_time)

            params = {"operation": "next", "index": self.index}
