"""
Dependency injection container module for the Netskope Event Collector.

This module provides the `AppContainer` class, which wires together the
application's configuration, Netskope API client, and S3 writer
using the `dependency-injector` framework.
"""

from dependency_injector import containers, providers

from .config import Settings
from .netskope_client import NetskopeClient
from .s3_writer import S3Writer


class AppContainer(containers.DeclarativeContainer):
    """
    Declarative DI container for the Netskope Collector.

    Provides the following providers:
    - config (Singleton[Settings]): Loads and shares configuration
    - netskope_client (Factory[NetskopeClient]): HTTP client for Netskope API
    - s3_writer (Factory[S3Writer]): Gzipped JSONL writer to Amazon S3
    """

    config = providers.Singleton(Settings)

    netskope_client = providers.Factory(
        NetskopeClient,
        api_endpoint=config.provided.netskope_api_endpoint,
        token=config.provided.netskope_token,
        index=config.provided.netskope_iterator_index,
        settings=config,
    )

    s3_writer = providers.Factory(
        S3Writer,
        bucket=config.provided.s3_bucket,
        prefix=config.provided.s3_prefix,
        endpoint_url=config.provided.s3_endpoint_url,
        region=config.provided.aws_region,
    )
