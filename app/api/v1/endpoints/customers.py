"""
Customer Service - Customer Endpoints

CRUD operations for managing external customers (Instagram/Facebook contacts).
All endpoints require authentication via JWT from Auth Service.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.customer_service import CustomerService
from app.services.meta_api_service import meta_api_service
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
)

router = APIRouter()


def _customer_to_response(customer) -> CustomerResponse:
    """Convert Customer model to response schema."""
    return CustomerResponse(
        id=customer.id,
        app_id=customer.app_id,
        platform_id=customer.platform_id,
        platform=customer.platform,
        first_name=customer.first_name,
        last_name=customer.last_name,
        full_name=customer.full_name,
        profile_pic_url=customer.profile_pic_url,
        email=customer.email,
        phone=customer.phone,
        metadata=customer.metadata,
        is_active=customer.is_active,
        is_blocked=customer.is_blocked,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        last_interaction_at=customer.last_interaction_at,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    # current_user: dict = Depends(get_current_user),
):
    """
    Create a new customer.

    For now, app_id, psid, and access_token are manually provided.
    The access_token is used to fetch profile data from Meta Graph API.

    In the future, this will be automated through the webhook service flow.
    """
    service = CustomerService(db)

    # Check if customer with same platform_id already exists for this app
    existing = service.get_customer_by_app_and_platform_id(
        customer_data.app_id, customer_data.platform_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer with platform_id {customer_data.platform_id} already exists for this app",
        )

    customer = service.create_customer(customer_data)
    return _customer_to_response(customer)


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    app_id: UUID = Query(..., description="App ID to filter customers"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    platform: Optional[str] = Query(
        None, description="Filter by platform (instagram/facebook)"
    ),
    search: Optional[str] = Query(
        None, description="Search by name, email, phone, or platform_id"
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all customers for an app with pagination and filtering.
    """
    service = CustomerService(db)
    skip = (page - 1) * size

    customers, total = service.get_customers_by_app(
        app_id=app_id,
        skip=skip,
        limit=size,
        platform=platform,
        search=search,
    )

    total_pages = (total + size - 1) // size

    return CustomerListResponse(
        customers=[_customer_to_response(c) for c in customers],
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a customer by ID.
    """
    service = CustomerService(db)
    customer = service.get_customer_by_id(customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    return _customer_to_response(customer)


@router.get("/platform-id/{platform_id}", response_model=CustomerResponse)
async def get_customer_by_platform_id(
    platform_id: str,
    app_id: UUID = Query(..., description="App ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get a customer by platform_id and App ID.

    This is useful for webhook service to lookup customer by sender_id.
    """
    service = CustomerService(db)
    customer = service.get_customer_by_app_and_platform_id(app_id, platform_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    return _customer_to_response(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    update_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update a customer.
    """
    service = CustomerService(db)
    customer = service.update_customer(customer_id, update_data)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    return _customer_to_response(customer)


@router.post("/{customer_id}/fetch-profile", response_model=CustomerResponse)
async def fetch_and_update_profile(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Fetch customer profile from Meta Graph API and update the customer.

    Requires the customer to have an access_token saved.

    Uses: GET https://graph.facebook.com/v21.0/<platform_id>?fields=first_name,last_name,profile_pic
    """
    service = CustomerService(db)
    customer = service.get_customer_by_id(customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    if not customer.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer does not have an access token. Please add one first.",
        )

    # Fetch profile from Meta API
    profile = await meta_api_service.fetch_user_profile(
        platform_id=customer.platform_id, access_token=customer.access_token
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch profile from Meta Graph API",
        )

    # Update customer with fetched data
    updated_customer = service.update_customer_from_meta(customer_id, profile)
    return _customer_to_response(updated_customer)


@router.post("/upsert", response_model=CustomerResponse)
async def upsert_customer(
    app_id: UUID = Query(..., description="App ID"),
    platform_id: str = Query(..., description="Platform ID"),
    platform: str = Query("instagram", description="Platform"),
    first_name: Optional[str] = Query(None),
    last_name: Optional[str] = Query(None),
    profile_pic_url: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Upsert (Update or Insert) a customer.

    This endpoint is designed for webhook service to sync customer data
    after fetching profile from Meta Graph API.

    Workflow:
    1. Webhook receives message with sender_id
    2. Webhook fetches profile from Meta API
    3. Webhook calls this endpoint to sync customer
    4. Returns the customer (created or updated)
    """
    service = CustomerService(db)
    customer, created = service.upsert_customer(
        app_id=app_id,
        platform_id=platform_id,
        platform=platform,
        first_name=first_name,
        last_name=last_name,
        profile_pic_url=profile_pic_url,
    )

    return _customer_to_response(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a customer.
    """
    service = CustomerService(db)
    deleted = service.delete_customer(customer_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )


@router.post("/{customer_id}/block", response_model=CustomerResponse)
async def block_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Block a customer.
    """
    service = CustomerService(db)
    customer = service.block_customer(customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    return _customer_to_response(customer)


@router.post("/{customer_id}/unblock", response_model=CustomerResponse)
async def unblock_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Unblock a customer.
    """
    service = CustomerService(db)
    customer = service.unblock_customer(customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    return _customer_to_response(customer)


@router.patch("/{customer_id}/interaction")
async def update_interaction(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update the last interaction timestamp for a customer.

    Called by webhook service when a new message is received.
    """
    service = CustomerService(db)
    customer = service.update_last_interaction(customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    return {
        "message": "Interaction updated",
        "last_interaction_at": customer.last_interaction_at,
    }
