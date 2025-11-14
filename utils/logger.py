import logging
import sys
from typing import Optional

LOGGER_NAME = "microcap_scout_bot"


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure an application-wide logger.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False

    # Also configure the FastAPI/Uvicorn loggers to use same format.
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = logger.handlers
    uvicorn_logger.setLevel(level)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    if not name:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
