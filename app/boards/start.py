"""Container entry point: verify additive migrations before accepting traffic."""

import os
from boards.infrastructure.migrate import migrate
from boards.infrastructure.logging import configure

if __name__ == "__main__":
    configure()
    migrate()
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "boards.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--no-access-log",
        ],
    )
