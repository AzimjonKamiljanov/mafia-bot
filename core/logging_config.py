import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(default_level: str = "INFO"):
    """Configure structured logging with console output and rotating file handler."""
    level_name = os.getenv("LOG_LEVEL", default_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console Handler
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)

    # Rotating File Handler (save to data/bot.log)
    try:
        log_dir = Path("./data").resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "bot.log"

        if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
            file_handler = RotatingFileHandler(
                str(log_file),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            root_logger.addHandler(file_handler)
    except Exception as e:
        # If filesystem permissions prevent file logging, continue with console
        logging.getLogger("detektiv.logging").warning("Could not setup RotatingFileHandler: %s", e)
