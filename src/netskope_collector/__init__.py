"""
netskope_collector: Top-level package for the Netskope Event Collector.

This module serves as the entry point for the `netskope_collector` package.
It is designed for flexible execution in both CLI and module contexts,
specifically targeting containerized environments such as AWS Lambda or ECS.

Modules:
--------
This package exposes the following submodules:

- config: Handles environment-based configuration management.
- netskope_client: Provides a robust HTTP client for communicating with Netskope's Data Export API.
- s3_writer: Streams events to Amazon S3 using gzip-compressed JSON Lines format.
- container: Sets up the dependency injection container using `dependency-injector`.
- runner: Orchestrates data fetching and upload operations; used as both CLI and Lambda entrypoint.

Lazy CLI Import:
----------------
To avoid circular imports during normal use (e.g., unit testing or library use),
the `cli` object is imported lazily using the `__getattr__` protocol.
This ensures that the CLI (click-based interface) is only imported
when `netskope_collector.cli` is explicitly accessed.

Command-line Execution:
-----------------------
When run as a script using `python -m netskope_collector`,
the CLI defined in `runner.cli()` will be invoked.

Example:
--------
$ python -m netskope_collector

Raises:
-------
AttributeError:
    If an undefined attribute is accessed via `__getattr__`.

Notes:
------
- This module should remain lightweight and avoid eager imports of heavy dependencies.
- All core logic is delegated to submodules to keep the top-level interface clean.
"""

__all__ = [
    "config",
    "netskope_client",
    "s3_writer",
    "container",
    "runner",
]


def __getattr__(name):
    """
    Lazily imports `cli` when accessed as `netskope_collector.cli`.

    This prevents circular imports during module loading.
    """
    if name == "cli":
        from .runner import cli

        return cli
    raise AttributeError(name)


def __main__():
    """
    Entrypoint for CLI execution when the module is invoked directly.

    Equivalent to running:
        python -m netskope_collector

    This will delegate to the `cli()` function defined in `runner.py`.
    """
    from .runner import cli

    cli()
