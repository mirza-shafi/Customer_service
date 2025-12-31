"""
Customer Service - Business Logic Layer

Handles customer CRUD operations and business logic.
"""

from datetime import datetime
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.models import Customer
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerMetaProfileUpdate,
)


class CustomerService:
    """Service class for customer operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_customer(self, customer_data: CustomerCreate) -> Customer:
        """
        Create a new customer.

        Args:
            customer_data: Customer creation data

        Returns:
            Created customer instance
        """
        customer = Customer(
            app_id=customer_data.app_id,
            platform_id=customer_data.platform_id,
            platform=customer_data.platform,
            first_name=customer_data.first_name,
            last_name=customer_data.last_name,
            profile_pic_url=customer_data.profile_pic_url,
            email=customer_data.email,
            phone=customer_data.phone,
            metadata=customer_data.metadata or {},
            access_token=customer_data.access_token,
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def get_customer_by_id(self, customer_id: UUID) -> Optional[Customer]:
        """Get customer by ID."""
        return self.db.query(Customer).filter(Customer.id == customer_id).first()

    def get_customer_by_platform_id(self, platform_id: str) -> Optional[Customer]:
        """Get customer by Platform ID."""
        return (
            self.db.query(Customer).filter(Customer.platform_id == platform_id).first()
        )

    def get_customer_by_app_and_platform_id(
        self, app_id: UUID, platform_id: str
    ) -> Optional[Customer]:
        """Get customer by app_id and platform_id combination."""
        return (
            self.db.query(Customer)
            .filter(Customer.app_id == app_id, Customer.platform_id == platform_id)
            .first()
        )

    def get_customers_by_app(
        self,
        app_id: UUID,
        skip: int = 0,
        limit: int = 50,
        platform: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Customer], int]:
        """
        Get all customers for an app with pagination and filtering.

        Returns:
            Tuple of (customers list, total count)
        """
        query = self.db.query(Customer).filter(Customer.app_id == app_id)

        if platform:
            query = query.filter(Customer.platform == platform)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Customer.first_name.ilike(search_pattern),
                    Customer.last_name.ilike(search_pattern),
                    Customer.email.ilike(search_pattern),
                    Customer.phone.ilike(search_pattern),
                    Customer.platform_id.ilike(search_pattern),
                )
            )

        total = query.count()
        customers = query.offset(skip).limit(limit).all()
        return customers, total

    def update_customer(
        self, customer_id: UUID, update_data: CustomerUpdate
    ) -> Optional[Customer]:
        """Update customer data."""
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(customer, field, value)

        customer.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def update_customer_from_meta(
        self, customer_id: UUID, meta_data: CustomerMetaProfileUpdate
    ) -> Optional[Customer]:
        """
        Update customer with data fetched from Meta Graph API.

        This is used after successfully calling:
        GET https://graph.facebook.com/v21.0/<PSID>?fields=first_name,last_name,profile_pic
        """
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            return None

        if meta_data.first_name:
            customer.first_name = meta_data.first_name
        if meta_data.last_name:
            customer.last_name = meta_data.last_name
        if meta_data.profile_pic_url:
            customer.profile_pic_url = meta_data.profile_pic_url

        customer.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def update_last_interaction(self, customer_id: UUID) -> Optional[Customer]:
        """Update the last interaction timestamp."""
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            return None

        customer.last_interaction_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def upsert_customer(
        self,
        app_id: UUID,
        platform_id: str,
        platform: str = "instagram",
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        profile_pic_url: Optional[str] = None,
    ) -> Tuple[Customer, bool]:
        """
        Update or Insert a customer.

        Used by webhook service to sync customer data after
        fetching profile from Meta Graph API.

        Returns:
            Tuple of (customer, created) where created is True if new customer
        """
        existing = self.get_customer_by_app_and_platform_id(app_id, platform_id)

        if existing:
            # Update existing customer
            if first_name:
                existing.first_name = first_name
            if last_name:
                existing.last_name = last_name
            if profile_pic_url:
                existing.profile_pic_url = profile_pic_url

            existing.updated_at = datetime.utcnow()
            existing.last_interaction_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing, False
        else:
            # Create new customer
            customer = Customer(
                app_id=app_id,
                platform_id=platform_id,
                platform=platform,
                first_name=first_name,
                last_name=last_name,
                profile_pic_url=profile_pic_url,
                last_interaction_at=datetime.utcnow(),
            )
            self.db.add(customer)
            self.db.commit()
            self.db.refresh(customer)
            return customer, True

    def delete_customer(self, customer_id: UUID) -> bool:
        """Delete a customer."""
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            return False

        self.db.delete(customer)
        self.db.commit()
        return True

    def block_customer(self, customer_id: UUID) -> Optional[Customer]:
        """Block a customer."""
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            return None

        customer.is_blocked = True
        customer.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def unblock_customer(self, customer_id: UUID) -> Optional[Customer]:
        """Unblock a customer."""
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            return None

        customer.is_blocked = False
        customer.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(customer)
        return customer
