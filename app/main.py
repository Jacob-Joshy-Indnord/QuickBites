"""FastAPI application factory.

create_app(address_repo=None) builds the FastAPI app, mounts the address book
router from app/addresses.py and exposes GET /health for probes. The optional
repository argument lets tests inject their own storage or cipher; the
module-level `app` uses defaults. OpenAPI documentation is served at /docs.
Further routers (cart, orders, payments) are to be included here as they are
built.
"""
from fastapi import FastAPI

from app.addresses import AddressRepository, build_router


def create_app(address_repo: AddressRepository | None = None) -> FastAPI:
    app = FastAPI(title="QuickBites API")
    app.include_router(build_router(address_repo or AddressRepository()))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
