"""
Entry point for running the netskope_collector package as a script.

This module is executed when running the package via:
    python -m netskope_collector

It delegates execution to the CLI defined in `runner.py` (the `cli()` function).

Usage:
------
$ python -m netskope_collector --help

Notes:
------
- The `__main__.py` file is required for Python to recognize this package as executable via the `-m` flag.
- The actual CLI logic resides in `runner.cli()`, keeping this entrypoint minimal and focused.
"""

from .runner import cli

if __name__ == "__main__":
    cli()
