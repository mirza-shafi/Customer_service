"""
Customer Service - API V1 Package
"""

from fastapi import APIRouter
from app.api.v1.endpoints import customers

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
