"""
Customer Service - Main Application Entry Point

Manages external customers (Instagram/Facebook contacts) as the "Source of Truth"
for external identities in your microservices architecture.

Uses clean layered architecture:
- api/          - HTTP layer (controllers/endpoints)
- core/         - Cross-cutting concerns (config, database, security)
- models/       - SQLAlchemy ORM models
- schemas/      - Pydantic schemas for request/response validation
- services/     - Business logic layer

Authentication:
- Uses JWKS-based JWT validation (same pattern as webhook-service and apps_service)
- Validates tokens against Auth Service's public key

Database:
- Separate PostgreSQL database for Customer Service
- Port 5434 (different from other services)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import api_router

# Import models to ensure they're registered with SQLAlchemy
from app.models import Customer

# Create database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Customer Service",
    description="""
    A microservice for managing external customers from Instagram and Facebook.
    
    ## Overview
    
    This service acts as the **Source of Truth** for external identities in your
    microservices architecture. It manages customers who message you via Instagram/Facebook,
    distinct from internal platform users.
    
    ## Key Concepts
    
    * **PSID (Page Scoped ID)** - Unique identifier from Instagram/Facebook webhooks
    * **app_id** - Logical link to App Service (no hard FK across microservices)
    * **access_token** - Meta Graph API token for fetching profile data (manual entry for now)
    
    ## Features
    
    * **Customer CRUD** - Create, read, update, delete customers
    * **Profile Fetching** - Fetch customer profile from Meta Graph API
    * **Upsert Support** - Update or insert customers (for webhook sync)
    * **Search & Filter** - Find customers by name, email, phone, or PSID
    * **Block/Unblock** - Manage customer access
    * **Redis Caching** - Cache Meta profiles to avoid rate limits
    
    ## Integration with Other Services
    
    * **Webhook Service** - Calls `/customers/upsert` to sync customer data
    * **App Service** - Uses `app_id` to link customers to apps
    * **Auth Service** - JWT validation via JWKS
    
    ## Authentication
    
    All endpoints require a valid JWT token from the authentication service.
    Include the token in the Authorization header: `Bearer <token>`
    
    ## Manual Mode (Current)
    
    For now, customer IDs and access tokens are saved manually.
    In the future, this will be automated through the webhook flow.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint

    Returns a welcome message and API information.
    """
    return {
        "message": "Welcome to Customer Service",
        "version": "1.0.0",
        "description": "Manage external customers from Instagram/Facebook",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint

    Returns the API health status.
    """
    return {"status": "healthy", "service": "customer-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8007)
