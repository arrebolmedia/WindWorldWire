"""Structured logging configuration using dictConfig."""
import logging
import logging.config
import sys
from typing import Dict, Any

from .settings import get_settings

settings = get_settings()


def get_logging_config(service_name: str = None) -> Dict[str, Any]:
    """Get logging configuration dictionary."""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter"
            },
            "console": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "json" if settings.environment == "production" else "console",
                "stream": sys.stdout
            }
        },
        "loggers": {
            "newsbot": {
                "level": settings.log_level,
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": settings.log_level,
            "handlers": ["console"]
        }
    }
    
    # Add service name to formatter if provided
    if service_name:
        if settings.environment == "production":
            config["formatters"]["json"]["format"] = f"%(asctime)s %(levelname)s {service_name} %(name)s %(message)s"
        else:
            config["formatters"]["console"]["format"] = f"%(asctime)s [{service_name}] [%(levelname)s] %(name)s: %(message)s"
    
    return config


def setup_logging(service_name: str = None) -> None:
    """Configure structured logging using dictConfig."""
    config = get_logging_config(service_name)
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)