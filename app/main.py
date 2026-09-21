from fastapi import FastAPI

from app.database import Base, engine
from app.routers import addresses, auth

Base.metadata.create_all(bind=engine)

app = FastAPI(title="QuickBites API")

app.include_router(auth.router)
app.include_router(addresses.router)


@app.get("/health")
def health():
    return {"status": "ok"}
