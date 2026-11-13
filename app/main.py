"""FastAPI application entrypoint for the QuickBite menu service.

Creates the `app` object, mounts the menu router from app.routers_menu and
creates database tables on startup through `init_db` (a lifespan handler).
OpenAPI docs are served by FastAPI at /docs and /openapi.json. Run locally
with `uvicorn app.main:app`. Further routers (customisation groups, versions,
availability) should be included here as those tasks land.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers_menu import router as menu_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="QuickBite Menu API", lifespan=lifespan)
app.include_router(menu_router)
