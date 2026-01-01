"""
Customer Service - Pydantic Schemas

Request/Response schemas for customer CRUD operations.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID


class CustomerBase(BaseModel):
    """Base schema with common customer fields."""

    platform_id: str = Field(
        ..., description="Platform Scoped ID from Instagram/Facebook"
    )
    platform: str = Field(
        default="instagram", description="Platform: 'instagram' or 'facebook'"
    )
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    profile_pic_url: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    custom_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CustomerCreate(CustomerBase):
    """
    Schema for creating a new customer.

    For now, app_id and access_token are manually provided.
    In the future, access_token will be fetched automatically.
    """

    app_id: UUID = Field(..., description="App ID from App Service")
    access_token: Optional[str] = Field(
        None, description="Meta Graph API access token (manual entry for now)"
    )


class CustomerUpdate(BaseModel):
    """Schema for updating an existing customer."""

    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    profile_pic_url: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_blocked: Optional[bool] = None
    access_token: Optional[str] = Field(
        None, description="Update Meta Graph API access token"
    )

    class Config:
        from_attributes = True


class CustomerMetaProfileUpdate(BaseModel):
    """
    Schema for updating customer with data fetched from Meta Graph API.
    Used internally after calling Meta's profile endpoint.
    """

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_pic_url: Optional[str] = None


class CustomerResponse(BaseModel):
    """Schema for customer response."""

    id: UUID
    app_id: UUID
    platform_id: str
    platform: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str = Field(default="Unknown")
    profile_pic_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: bool
    is_blocked: bool
    created_at: datetime
    updated_at: datetime
    last_interaction_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """Schema for paginated customer list response."""

    customers: List[CustomerResponse]
    total: int
    page: int
    size: int
    total_pages: int


class CustomerUpsertRequest(BaseModel):
    """
    Schema for upserting a customer (Update or Insert).
    Used by webhook service to sync customer data.
    """

    app_id: UUID = Field(..., description="App ID from App Service")
    platform_id: str = Field(
        ..., description="Platform Scoped ID from Instagram/Facebook"
    )
    platform: str = Field(default="instagram")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_pic_url: Optional[str] = None


class CustomerUpsertResponse(BaseModel):
    """Response for upsert operation."""

    customer: CustomerResponse
    created: bool = Field(description="True if customer was created, False if updated")
