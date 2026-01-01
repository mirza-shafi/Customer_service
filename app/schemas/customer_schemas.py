from typing import Optional, Dict, Any
from pydantic import BaseModel, UUID4, Field
from datetime import datetime


class CustomerBase(BaseModel):
    app_id: UUID4
    platform_id: str
    platform: str = "instagram"
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True
    is_blocked: bool = False


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_blocked: Optional[bool] = None


class CustomerResponse(CustomerBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    last_interaction_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IdentifyCustomerRequest(BaseModel):
    access_token: str
    platform_id: str
    platform: str = "instagram"
    app_id: UUID4
