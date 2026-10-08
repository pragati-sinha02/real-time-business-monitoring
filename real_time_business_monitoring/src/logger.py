"""Simple logging to console + a file inside the logs/ folder."""
import logging
import sys

from .config import LOG_DIR


def get_logger(name: str = "monitor", logfile: str = "monitor.log") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Windows consoles may not use UTF-8 by default; this lets the rupee sign print.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    LOG_DIR.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(LOG_DIR / logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger