from __future__ import annotations

import logging
import sys
from functools import lru_cache


def _configure_root_logger() -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        root.addHandler(handler)


@lru_cache(maxsize=None)
def get_logger(name: str) -> logging.Logger:
    _configure_root_logger()
    return logging.getLogger(name)
