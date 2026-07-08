"""Console entrypoint: ``python -m microsandbox_service`` / ``microsandbox-service``."""

from __future__ import annotations

import logging

import uvicorn

from microsandbox_service.app import create_app
from microsandbox_service.config import get_settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    app = create_app(settings)
    # Single worker only: the sandbox registry lives in-process, so multiple
    # workers would each hold a disjoint set of sandboxes.
    uvicorn.run(app, host=settings.host, port=settings.port, workers=1)


if __name__ == "__main__":
    main()
