"""
Runner module for the Netskope Event Collector.

This module acts as the orchestration layer that connects the data fetcher
(`NetskopeClient`) and the output writer (`S3Writer`) through the dependency
injection container.

It supports both direct function invocation (`run`) and CLI-based execution (`cli`),
and can also be run as a script entrypoint.

Features:
---------
- Calculates the fetch window based on current time and configuration
- Invokes the Netskope API client and streams results to S3
- Can be used in Lambda handler or local CLI environments
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .container import AppContainer
from .logger import get_logger


def run(endpoint: str = "application", since_minutes: int | None = None) -> str:
    """
    Fetch events from the specified endpoint and upload them to S3.

    This function is the core logic for the collector. It calculates
    the collection window, fetches events from the Netskope API,
    and streams them into gzip-compressed JSONL files in S3.

    Parameters:
    -----------
    endpoint : str, default = "application"
        The Netskope event endpoint to fetch (e.g., "alert", "network").
    since_minutes : Optional[int]
        Number of minutes in the past to start collecting events.
        If None, falls back to the configured fetch window.

    Returns:
    --------
    str
        The S3 key where the collected data was uploaded.
    """
    log = get_logger(__name__)
    c = AppContainer()
    cfg = c.config()

    since_minutes = since_minutes or cfg.fetch_window_minutes
    since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

    log.info(
        "=== Fetch → Stream Upload ===  endpoint=%s  since=%s",
        endpoint,
        since.isoformat(),
    )

    s3_key = c.s3_writer().write_events(
        events_iter=c.netskope_client().fetch_events(endpoint=endpoint, since=since),
        endpoint=endpoint,
    )
    log.info("Upload done: %s", s3_key)
    return s3_key


def cli() -> None:
    """
    Command-line entrypoint for the Netskope Collector.

    This function uses the configured `target_endpoint` and `target_since_minutes`
    from the environment (via `Settings`) and invokes the `run()` function.

    Can be used with `python -m netskope_collector` or as a Lambda handler delegate.
    """
    c = AppContainer()
    cfg = c.config()
    run(endpoint=cfg.target_endpoint, since_minutes=cfg.target_since_minutes)


if __name__ == "__main__":
    cli()
