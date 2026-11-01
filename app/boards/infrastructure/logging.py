"""Operational metadata only: never serialize request headers, bodies or exceptions."""

import json, logging


class OperationalFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                **getattr(record, "metrics", {}),
            },
            separators=(",", ":"),
        )


def configure():
    logger = logging.getLogger("avenboard")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(OperationalFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
