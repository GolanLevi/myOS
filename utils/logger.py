import logging
import sys
import io
from typing import Optional

class ColorFormatter(logging.Formatter):
    """Custom logging formatter with colors for terminal output."""
    
    # ANSI Color Codes
    GREY = "\x1b[38;20m"
    BLUE = "\x1b[34;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    GREEN = "\x1b[32;20m"
    CYAN = "\x1b[36;20m"

    FORMAT = "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: GREY + FORMAT + RESET,
        logging.INFO: CYAN + FORMAT + RESET,
        logging.WARNING: YELLOW + FORMAT + RESET,
        logging.ERROR: RED + FORMAT + RESET,
        logging.CRITICAL: BOLD_RED + FORMAT + RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

def get_logger(name: str, level: int = logging.INFO):
    """Get a configured logger by name."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Only add handler if it doesn't exist to prevent duplicate logs
    if not logger.handlers:
        stream = sys.stdout
        if hasattr(sys.stdout, "buffer"):
            stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        handler = logging.StreamHandler(stream)
        handler.setFormatter(ColorFormatter())
        logger.addHandler(handler)
        
    logger.propagate = False
    return logger

# Create global loggers for main components
server_logger = get_logger("SERVER")
agent_logger = get_logger("AGENT")
tool_logger = get_logger("TOOL")
memory_logger = get_logger("STATE")
