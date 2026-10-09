"""Run a single-worker, loopback-only server: python -m mini_learngraph.api."""

import uvicorn

from mini_learngraph.api.app import create_app
from mini_learngraph.api.settings import ServerSettings


def main() -> None:
    settings = ServerSettings()
    uvicorn.run(
        create_app(),
        host=settings.host,
        port=settings.port,
        workers=1,
        proxy_headers=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
