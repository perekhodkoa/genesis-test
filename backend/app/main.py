import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.postgres import init_postgres, close_postgres
from app.db.mongodb import init_mongodb, close_mongodb
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.routes import auth, upload, collections, chat, models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_postgres()
    await init_mongodb()
    logging.getLogger(__name__).info("Database connections established")
    yield
    await close_postgres()
    await close_mongodb()
    logging.getLogger(__name__).info("Database connections closed")


app = FastAPI(title="Data Lens", version="0.1.0", lifespan=lifespan)

# Middleware (order matters: outermost first)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(collections.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(models.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
