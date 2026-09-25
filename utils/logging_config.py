"""
utils/logging_config.py
Centralized logging configuration.
"""

import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application-wide logging."""
    from config.settings import get_settings
    settings = get_settings()

    numeric_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(formatter)

    # File handler
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "qp_agent.log", encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    if not root.handlers:
        root.addHandler(console)
        root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy in ["httpx", "httpcore", "urllib3", "openai", "sentence_transformers"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
