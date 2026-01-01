"""
Customer Service - Database Models

This module defines the Customer entity which serves as the "Source of Truth"
for external identities from Instagram and Facebook.

Key Concepts:
- PSID (Page Scoped ID): Unique identifier from Instagram/Facebook webhooks
- app_id: Logical link to App Service (no hard FK across microservices)
- Fetched data: Name, profile picture from Meta Graph API
- Manual mode: Customer ID and access token are saved manually for now
"""

from datetime import datetime
import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from app.core.database import Base


class Customer(Base):
    """
    Customer model representing external contacts messaging via Instagram/Facebook.

    This is NOT a platform user, but an external contact whose messages come
    through webhooks. The PSID is used to link with Conversation in webhook-service.
    """

    __tablename__ = "customers"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ============= Logical Links to Other Services =============
    # Links to App Service (no hard FK across microservices)
    app_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # ============= Meta Platform Identifiers =============
    # Page Scoped ID - Unique identifier received from Instagram/Facebook webhook
    # This matches sender_id/customer_platform_id in webhook-service
    platform_id = Column(String(255), nullable=False, index=True)

    # Platform identifier: 'instagram' or 'facebook'
    platform = Column(String(50), nullable=False, default="instagram")

    # ============= Data Fetched from Meta Graph API =============
    # GET https://graph.facebook.com/v21.0/<PSID>?fields=first_name,last_name,profile_pic&access_token=<TOKEN>
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    profile_pic_url = Column(Text, nullable=True)

    # ============= Enriched Contact Data (Optional) =============
    # These can be added later through various channels
    email = Column(String(255), index=True, nullable=True)
    phone = Column(String(50), index=True, nullable=True)

    # ============= Custom Metadata =============
    # Store arbitrary custom attributes as JSON
    # Examples: tags, custom_fields, preferences, etc.
    custom_metadata = Column(JSON, nullable=True, default=dict)

    # ============= Status Flags =============
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)

    # ============= Timestamps =============
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_interaction_at = Column(DateTime, nullable=True)

    # ============= Indexes for Performance =============
    __table_args__ = (
        Index(
            "ix_unique_customer_per_app",
            "app_id",
            "platform",
            "platform_id",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<Customer(id={self.id}, platform_id={self.platform_id}, platform={self.platform})>"

    @property
    def full_name(self) -> str:
        """Return full name combining first and last name."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else "Unknown"

    @property
    def display_name(self) -> str:
        """Return display name with fallback to platform_id."""
        name = self.full_name
        return name if name != "Unknown" else f"User ({self.platform_id[:8]}...)"
