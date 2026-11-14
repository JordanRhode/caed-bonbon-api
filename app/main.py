from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.api.routes import auth, bonbons, images, media


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure storage paths exist
    settings.storage_path

    # In dev or fresh start without migrations, ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Clean up engine pool on shutdown
    await engine.dispose()


app = FastAPI(
    title="Caed Bonbon Management API",
    description="Backend service for bonbon flavor management, activation, and AI background-removal processing.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware (allows Next.js frontend with credentials / cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/api")
app.include_router(bonbons.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(media.router)
app.include_router(media.router, prefix="/api")


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "caed-bonbon-api",
        "storage": str(settings.storage_path),
    }
