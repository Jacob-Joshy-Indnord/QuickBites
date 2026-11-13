"""FastAPI application factory.

create_app(catalogue, adjustments) wires a CartService into the cart router and
returns the FastAPI app (OpenAPI docs served at /docs). Both arguments are
optional so tests can inject an InMemoryCatalogue and fake bill adjustments;
module-level `app` uses defaults. A /health endpoint is exposed for probes.
Persistence is currently in-memory behind CartService; a PostgreSQL repository
will replace it when the catalogue and database foundation tasks land.
"""
from fastapi import FastAPI

from app.billing import zero_adjustments
from app.cart import CartService, build_router
from app.catalogue import InMemoryCatalogue


def create_app(catalogue=None, adjustments=zero_adjustments) -> FastAPI:
    app = FastAPI(title="QuickBites API")
    service = CartService(catalogue or InMemoryCatalogue(), adjustments)
    app.state.cart_service = service
    app.include_router(build_router(service))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
