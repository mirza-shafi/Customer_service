"""
gRPC Service Handler for Customer Service

This module implements the gRPC Servicer that handles customer identification requests.
It bridges gRPC calls with the SQLAlchemy database and Meta Graph API.
"""

import logging
from datetime import datetime, timedelta
import uuid

from app.grpc_gen import customer_service_pb2, customer_service_pb2_grpc
from app.core.database import SessionLocal
from app.models.models import Customer
from app.services.graph_api_service import GraphAPIService

logger = logging.getLogger(__name__)


class CustomerServicer(customer_service_pb2_grpc.CustomerServiceServicer):
    """
    gRPC Servicer for Customer identification and management.

    This service handles incoming gRPC requests from webhook services
    and manages customer identity resolution via Meta Graph API.
    """

    def IdentifyCustomer(self, request, context):
        """
        Identify a customer by their Platform ID (PSID).

        If not found, fetch details from Meta Graph API and create a new customer.
        If found but data is older than 24 hours, refresh from Meta Graph API.

        Args:
            request: IdentifyRequest containing platform_id, app_id, access_token, platform
            context: gRPC context

        Returns:
            CustomerResponse with customer_id, is_new, and full_name
        """
        db = SessionLocal()
        try:
            logger.info(
                f"🔍 gRPC: Identifying customer {request.platform_id} for app {request.app_id}"
            )

            # ============= Check if customer already exists =============
            customer = (
                db.query(Customer)
                .filter(
                    Customer.platform_id == request.platform_id,
                    Customer.app_id == uuid.UUID(request.app_id),
                )
                .first()
            )

            is_new = False
            should_refresh = False

            # ============= Check if refresh needed =============
            if customer:
                # Check if data is older than 24 hours
                time_since_update = datetime.utcnow() - customer.updated_at
                if time_since_update > timedelta(hours=24):
                    logger.info(
                        f"⏰ gRPC: Customer {customer.platform_id} data is stale, refreshing from Meta API"
                    )
                    should_refresh = True
                else:
                    logger.info(f"✅ gRPC: Found existing customer {customer.id}")
                    return customer_service_pb2.CustomerResponse(
                        customer_id=str(customer.id),
                        is_new=False,
                        full_name=f"{customer.first_name or ''} {customer.last_name or ''}".strip(),
                    )

            # ============= Fetch from Graph API (new customer or refresh needed) =============
            logger.info(
                f"📡 gRPC: Fetching profile from Meta Graph API for {request.platform_id}"
            )
            profile_data = GraphAPIService.get_user_profile_sync(
                access_token=request.access_token, psid=request.platform_id
            )

            if not profile_data:
                # If Graph API fails, still create/return customer but with limited info
                if customer and not should_refresh:
                    logger.warning(
                        f"⚠️ gRPC: Meta API failed but returning existing customer {customer.id}"
                    )
                    return customer_service_pb2.CustomerResponse(
                        customer_id=str(customer.id),
                        is_new=False,
                        full_name=f"{customer.first_name or ''} {customer.last_name or ''}".strip(),
                    )
                profile_data = {}
                logger.warning(
                    f"⚠️ gRPC: Meta API failed for new customer {request.platform_id}"
                )

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
            custom_metadata = profile_data.copy()

            if customer and should_refresh:
                # ============= Update Existing Customer =============
                customer.first_name = first_name
                customer.last_name = last_name
                customer.profile_pic_url = profile_pic_url
                customer.custom_metadata = custom_metadata
                customer.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(customer)
                logger.info(
                    f"✅ gRPC: Refreshed customer {customer.platform_id} data from Meta API"
                )
                return customer_service_pb2.CustomerResponse(
                    customer_id=str(customer.id),
                    is_new=False,
                    full_name=f"{customer.first_name or ''} {customer.last_name or ''}".strip(),
                )
            else:
                # ============= Create New Customer =============
                new_customer = Customer(
                    app_id=uuid.UUID(request.app_id),
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
                logger.info(
                    f"✅ gRPC: Created new customer {new_customer.platform_id} with ID {new_customer.id}"
                )
                return customer_service_pb2.CustomerResponse(
                    customer_id=str(new_customer.id),
                    is_new=True,
                    full_name=f"{new_customer.first_name or ''} {new_customer.last_name or ''}".strip(),
                )

        except Exception as e:
            logger.error(
                f"❌ gRPC: Error identifying customer: {str(e)}", exc_info=True
            )
            context.set_code(11)  # UNAVAILABLE
            context.set_details(f"Failed to identify customer: {str(e)}")
            return customer_service_pb2.CustomerResponse(
                customer_id="",
                is_new=False,
                full_name="",
            )

        finally:
            db.close()
