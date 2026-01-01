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
from datetime import datetime

router = APIRouter()


@router.post("/identify", response_model=CustomerResponse)
async def identify_customer(
    request: IdentifyCustomerRequest, db: Session = Depends(get_db)
):
    """
    Identify a customer by their Platform ID (PSID).
    If not found, fetch details from Meta Graph API and create a new customer.
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

    if customer:
        # Update access token if changed
        if request.access_token and customer.access_token != request.access_token:
            customer.access_token = request.access_token
            customer.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(customer)
        return customer

    # Customer not found, fetch from Graph API
    profile_data = await GraphAPIService.get_user_profile(
        access_token=request.access_token, psid=request.platform_id
    )

    if not profile_data:
        # If Graph API fails, still create customer but with limited info
        profile_data = {}

    new_customer = Customer(
        app_id=request.app_id,
        platform_id=request.platform_id,
        platform=request.platform,
        access_token=request.access_token,
        first_name=profile_data.get("first_name"),
        last_name=profile_data.get("last_name"),
        profile_pic_url=profile_data.get("profile_pic"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

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
