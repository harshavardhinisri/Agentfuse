"""FastAPI application entry point."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.database import get_db_manager
from src.classifier import load_classifier
from src.api import health, actions


# Startup/shutdown lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    print("🚀 Starting AgentFuse...")

    # Initialize database
    db_manager = get_db_manager()
    db_manager.init_db()
    print("✓ Database initialized")

    # Load classifier
    classifier = load_classifier()
    if classifier.health_check():
        print("✓ DeBERTa classifier loaded")
    else:
        print("⚠ Using baseline classifier (fine-tuned model not available)")

    # Verify database connection
    if db_manager.health_check():
        print("✓ Database connected")
    else:
        print("✗ Database connection failed!")

    yield

    # Shutdown
    print("\n🛑 Shutting down AgentFuse...")
    db_manager.close()
    print("✓ Resources cleaned up")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application.
    """
    settings = get_settings()

    app = FastAPI(
        title="AgentFuse",
        description="Safety layer for AI agents - intercept, classify, and control destructive actions",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    from src.api.snapshots import router as snapshots_router, rollback_router
    from src.api.kill_switch import router as kill_switch_router, slack_router
    from src.api.websocket import router as websocket_router

    app.include_router(health.router)
    app.include_router(actions.router)
    app.include_router(snapshots_router)
    app.include_router(rollback_router)
    app.include_router(kill_switch_router)
    app.include_router(slack_router)
    app.include_router(websocket_router)

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "AgentFuse",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
