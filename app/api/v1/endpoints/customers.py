from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Customer
from app.schemas.customer_schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    IdentifyCustomerRequest,
)
from app.services.graph_api_service import GraphAPIService
import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()


# Identify a customer
# route: /api/v1/customers/identify
@router.post("/identify", response_model=CustomerResponse)
async def identify_customer(
    request: IdentifyCustomerRequest, db: Session = Depends(get_db)
):
    """
    Identify a customer by their Platform ID (PSID).
    If not found, fetch details from Meta Graph API and create a new customer.
    If found but data is older than 24 hours, refresh from Meta Graph API.
    """
    # Check if customer already exists
    customer = (
        db.query(Customer)
        .filter(
            Customer.platform_id == request.platform_id,
            Customer.app_id == request.app_id,
        )
        .first()
    )

    # ============= Check if refresh needed =============
    should_refresh = False
    if customer:
        # Check if data is older than 24 hours
        time_since_update = datetime.utcnow() - customer.updated_at
        if time_since_update > timedelta(hours=24):
            logger.info(
                f"⏰ Customer {customer.platform_id} data is stale, refreshing from Meta API"
            )
            should_refresh = True
        else:
            return customer

    # ============= Fetch from Graph API (new customer or refresh needed) =============
    profile_data = await GraphAPIService.get_user_profile(
        access_token=request.access_token, psid=request.platform_id
    )
    print(profile_data)

    if not profile_data:
        # If Graph API fails, still create/return customer but with limited info
        if customer and not should_refresh:
            return customer
        profile_data = {}

    # ============= Extract Primary Fields =============
    # Robust field mapping to handle both Messenger and Instagram responses
    full_name = profile_data.get("name") or ""
    first_name = profile_data.get("first_name")
    last_name = profile_data.get("last_name")

    # Fallback: If Meta only gives 'name', split it manually
    if not first_name and full_name:
        parts = full_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    # Use 'profile_pic' (works for both Messenger and Instagram)
    profile_pic_url = profile_data.get("profile_pic")

    # ============= Store Full Meta API Response =============
    # Save entire payload in custom_metadata for audit trail and future use
    # Include all fields returned by Meta API
    custom_metadata = profile_data.copy()  # Store full payload

    if customer and should_refresh:
        # ============= Update Existing Customer =============
        customer.first_name = first_name
        customer.last_name = last_name
        customer.profile_pic_url = profile_pic_url
        customer.custom_metadata = custom_metadata
        customer.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(customer)
        logger.info(f"✅ Refreshed customer {customer.platform_id} data from Meta API")
        return customer
    else:
        # ============= Create New Customer =============
        new_customer = Customer(
            app_id=request.app_id,
            platform_id=request.platform_id,
            platform=request.platform,
            first_name=first_name,
            last_name=last_name,
            profile_pic_url=profile_pic_url,
            custom_metadata=custom_metadata if custom_metadata else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)
        logger.info(f"✅ Created new customer {new_customer.platform_id}")
        return new_customer

    return new_customer


@router.get("/", response_model=List[CustomerResponse])
def read_customers(
    skip: int = 0,
    limit: int = 100,
    app_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve customers.
    """
    query = db.query(Customer)
    if app_id:
        query = query.filter(Customer.app_id == app_id)
    return query.offset(skip).limit(limit).all()


@router.get("/{customer_id}", response_model=CustomerResponse)
def read_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Get a specific customer by ID.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    customer_update: CustomerUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a customer's details.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = customer_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    customer.updated_at = datetime.utcnow()

    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", response_model=CustomerResponse)
def delete_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Delete a customer.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.delete(customer)
    db.commit()
    return customer
