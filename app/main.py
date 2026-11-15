import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.api.routes import auth, bonbons, images, media

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bonbon-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure volume/storage paths exist
    storage = settings.storage_path
    logger.info(f"Storage volume mounted at: {storage}")

    # Check if target host is localhost
    if settings.is_localhost_db and os.getenv("RAILWAY_ENVIRONMENT"):
        logger.warning(
            "⚠️  WARNING: DATABASE_URL is pointing to localhost inside Railway! "
            "In Railway, PostgreSQL runs as its own service. "
            "Please ensure you added DATABASE_URL to your service variables "
            "(e.g. DATABASE_URL=${{Postgres.DATABASE_URL}} or select from Add Reference Variable)."
        )

    logger.info(f"Connecting to database at {settings.sanitized_database_url}...")

    # Connection retry loop (useful during container startup races in Railway)
    max_retries = 5
    connected = False
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database connected and tables verified.")
            connected = True
            break
        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    f"❌ CRITICAL: Failed to connect to database after {max_retries} attempts: {e}\n"
                    f"Target was: {settings.sanitized_database_url}\n"
                    "If you are running in Railway:\n"
                    "1. Go to your API Service -> Variables.\n"
                    "2. Check if DATABASE_URL is set.\n"
                    "3. Click 'Add Reference Variable' and choose your PostgreSQL service's DATABASE_URL."
                )
                raise
            logger.warning(
                f"Database connection attempt {attempt}/{max_retries} failed ({e}). Retrying in 3s..."
            )
            await asyncio.sleep(3)

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
        "database": settings.sanitized_database_url,
        "storage": str(settings.storage_path),
    }
