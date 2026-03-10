import logging
from json import dumps
from logging.config import dictConfig


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        return dumps(payload)


def configure_logging(level: str, *, log_json: bool = False) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
                "json": {
                    "()": JSONFormatter,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json" if log_json else "default",
                }
            },
            "root": {"handlers": ["console"], "level": level},
        }
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
