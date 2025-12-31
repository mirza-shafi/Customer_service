"""
Meta Graph API Service

Service for fetching user profile data from Meta (Facebook/Instagram) Graph API.

Usage:
    GET https://graph.facebook.com/v21.0/<PSID>?fields=first_name,last_name,profile_pic&access_token=<TOKEN>

Note: This is prepared for future automation. Currently, access tokens are saved manually.
In the future, this will be triggered automatically when a webhook message is received.
"""

from typing import Optional, Dict, Any
import httpx
import redis
import json

from app.core.config import settings
from app.schemas.customer import CustomerMetaProfileUpdate


# Redis client for caching profile data
redis_client = redis.StrictRedis.from_url(settings.REDIS_URL, decode_responses=True)


class MetaApiService:
    """
    Service for interacting with Meta Graph API.

    Pro-Tip: Use Redis for Caching to avoid rate limits:
    1. Check Redis for the PSID
    2. If not found, call Meta API
    3. Save to Postgres (Customer Service) and Redis
    """

    CACHE_TTL = 3600  # Cache profile for 1 hour

    def __init__(self):
        self.base_url = settings.META_GRAPH_API_BASE_URL
        self.api_version = settings.META_GRAPH_API_VERSION

    def _get_cache_key(self, platform_id: str) -> str:
        """Generate Redis cache key for profile."""
        return f"meta_profile:{platform_id}"

    async def fetch_user_profile(
        self, platform_id: str, access_token: str
    ) -> Optional[CustomerMetaProfileUpdate]:
        """
        Fetch user profile from Meta Graph API.

        Args:
            platform_id: Platform ID (sender_id from webhook)
            access_token: The channel's page access token

        Returns:
            CustomerMetaProfileUpdate with first_name, last_name, profile_pic_url
            or None if fetch failed
        """
        # Check cache first
        cached = self._get_from_cache(platform_id)
        if cached:
            return CustomerMetaProfileUpdate(**cached)

        # Fetch from Meta API
        url = f"{self.base_url}/{self.api_version}/{platform_id}"
        params = {
            "fields": "first_name,last_name,profile_pic",
            "access_token": access_token,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code != 200:
                    # Log error but don't raise - profile fetch is non-critical
                    print(
                        f"Meta API error for platform_id {platform_id}: {response.status_code}"
                    )
                    return None

                data = response.json()

                profile_data = {
                    "first_name": data.get("first_name"),
                    "last_name": data.get("last_name"),
                    "profile_pic_url": data.get("profile_pic"),
                }

                # Cache the result
                self._save_to_cache(platform_id, profile_data)

                return CustomerMetaProfileUpdate(**profile_data)

        except httpx.TimeoutException:
            print(f"Meta API timeout for platform_id {platform_id}")
            return None
        except Exception as e:
            print(f"Meta API error for platform_id {platform_id}: {str(e)}")
            return None

    def _get_from_cache(self, psid: str) -> Optional[Dict[str, Any]]:
        """Get profile from Redis cache."""
        try:
            cached = redis_client.get(self._get_cache_key(psid))
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None

    def _save_to_cache(self, psid: str, profile_data: Dict[str, Any]) -> None:
        """Save profile to Redis cache."""
        try:
            redis_client.set(
                self._get_cache_key(psid), json.dumps(profile_data), ex=self.CACHE_TTL
            )
        except Exception as e:
            print(f"Redis cache error: {str(e)}")

    def invalidate_cache(self, psid: str) -> None:
        """Invalidate cached profile for a PSID."""
        try:
            redis_client.delete(self._get_cache_key(psid))
        except Exception:
            pass


# Singleton instance
meta_api_service = MetaApiService()


async def fetch_meta_user_profile(
    psid: str, access_token: str
) -> Optional[CustomerMetaProfileUpdate]:
    """
    Convenience function to fetch Meta user profile.

    This is the function you mentioned you might want.

    Usage in webhook-service after receiving a message:

    ```python
    from customer_service.app.services.meta_api_service import fetch_meta_user_profile

    # After receiving sender_id from webhook
    profile = await fetch_meta_user_profile(
        psid=sender_id,
        access_token=channel.page_access_token
    )

    if profile:
        # Call POST /customers to upsert
        customer_data = {
            "app_id": app_id,
            "psid": sender_id,
            "platform": "instagram",
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "profile_pic_url": profile.profile_pic_url,
        }
        # POST to customer-service...
    ```
    """
    return await meta_api_service.fetch_user_profile(psid, access_token)
