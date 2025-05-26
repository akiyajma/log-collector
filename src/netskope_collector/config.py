"""
Configuration module for the Netskope Event Collector.

This module handles runtime configuration by reading from environment variables.
It provides default values for all necessary parameters and supports overriding
the Netskope Data Export API endpoint paths via a JSON-formatted environment variable.

Components:
-----------
- _DEFAULT_ENDPOINT_PATHS:
    A dictionary of default API paths for Netskope event types.

- _load_endpoint_paths():
    Helper function to parse and return custom endpoint paths from the
    NETSKOPE_ENDPOINTS environment variable.

- ENDPOINT_PATHS:
    Final dictionary used across the application for endpoint path resolution.

- Settings (dataclass):
    Centralized configuration object used for dependency injection across components.
    It encapsulates all environment-derived runtime settings.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict

# ------------------------------------------------------------------ #
# 1. Default Netskope Data Export API endpoints
#    - Can be overridden via the environment variable NETSKOPE_ENDPOINTS
# ------------------------------------------------------------------ #
_DEFAULT_ENDPOINT_PATHS: Dict[str, str] = {
    "application": "/api/v2/events/dataexport/events/application",
    "network": "/api/v2/events/dataexport/events/network",
    "page": "/api/v2/events/dataexport/events/page",
    "alert": "/api/v2/events/dataexport/events/alert",
    "audit": "/api/v2/events/dataexport/events/audit",
}


def _load_endpoint_paths() -> Dict[str, str]:
    """
    Load Netskope API endpoint paths from the environment.

    If the environment variable `NETSKOPE_ENDPOINTS` is defined,
    this function attempts to parse it as a JSON object.
    If parsing fails or the variable is not set, it falls back
    to a default set of predefined endpoint paths.

    Returns:
        Dict[str, str]: A mapping of event type keys to API paths.
    """
    raw = os.getenv("NETSKOPE_ENDPOINTS")
    if not raw:
        return _DEFAULT_ENDPOINT_PATHS
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except json.JSONDecodeError:
        pass
    return _DEFAULT_ENDPOINT_PATHS


ENDPOINT_PATHS: Dict[str, str] = _load_endpoint_paths()


# ------------------------------------------------------------------ #
# 2. Settings dataclass for application configuration
# ------------------------------------------------------------------ #
@dataclass(frozen=True, slots=True)
class Settings:
    """
    Application configuration based on environment variables.

    This dataclass centralizes all configurable parameters used across
    the collector. It is designed to be injected via dependency injection
    and supports immutability for safe sharing.

    Attributes:
        netskope_api_endpoint (str): Base URL of the Netskope API.
        netskope_token (str): Bearer token for authenticating API requests.
        netskope_iterator_index (str): Iterator index to separate consumers.

        fetch_window_minutes (int): Number of minutes of event data to fetch.
        max_fetch_pages (int): Max number of pages to retrieve per execution.
        max_fetch_duration_seconds (int): Max time allowed for fetching.

        target_endpoint (str): The default endpoint to collect (e.g. "application").
        target_since_minutes (Optional[int]): Override for how far back to fetch.

        aws_region (str): AWS region used for S3 operations.
        s3_bucket (str): Name of the destination S3 bucket.
        s3_prefix (str): Optional prefix to organize files in S3.
        s3_endpoint_url (Optional[str]): Custom endpoint URL (e.g., for LocalStack).

        endpoint_paths (Dict[str, str]): Mapping of event types to API paths.
    """

    # ── Netskope configuration ─────────────────────────────
    netskope_api_endpoint: str = os.getenv(
        "NETSKOPE_API_ENDPOINT", "https://tenant.goskope.com"
    )
    netskope_token: str = os.getenv("NETSKOPE_TOKEN", "")
    netskope_iterator_index: str = os.getenv("NETSKOPE_INDEX", "default")

    # ── Fetch window and limits ───────────────────────────
    fetch_window_minutes: int = int(os.getenv("FETCH_WINDOW_MINUTES", "15"))
    max_fetch_pages: int = int(os.getenv("MAX_FETCH_PAGES", "100"))
    max_fetch_duration_seconds: int = int(
        os.getenv("MAX_FETCH_DURATION_SECONDS", "300")
    )

    # ── Execution target override (CLI alternative) ───────
    target_endpoint: str = os.getenv("ENDPOINT", "application")
    target_since_minutes: int | None = (
        int(os.getenv("SINCE_MINUTES")) if os.getenv("SINCE_MINUTES") else None
    )

    # ── AWS / S3 configuration ────────────────────────────
    aws_region: str = os.getenv("AWS_REGION", "ap-northeast-1")
    s3_bucket: str = os.getenv("S3_BUCKET", "netskope-events")
    s3_prefix: str = os.getenv("S3_PREFIX", "")
    s3_endpoint_url: str | None = os.getenv("S3_ENDPOINT") or None

    # ── Endpoint path map (overridable via env) ───────────
    endpoint_paths: Dict[str, str] = field(default_factory=lambda: ENDPOINT_PATHS)
