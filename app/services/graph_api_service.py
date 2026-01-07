import httpx
import logging
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class GraphAPIService:
    BASE_URL = "https://graph.facebook.com/v21.0"

    # Platform-specific field sets
    FACEBOOK_FIELDS = [
        "first_name",
        "last_name",
        "name",
        "profile_pic",
        "email",
        "locale",
        "timezone",
        "gender",
    ]
    INSTAGRAM_FIELDS = ["name", "username", "profile_pic", "biography", "website"]
    BASE_FIELDS = ["name", "profile_pic", "id"]

    @classmethod
    def _detect_platform_and_fetch_sync(
        cls, access_token: str, psid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user is Instagram or Facebook and fetch appropriate fields.
        Uses a smart detection strategy with minimal API calls.

        Returns:
            Dict with profile data or None
        """
        url = f"{cls.BASE_URL}/{psid}"

        # ========== Call 1: Try Instagram fields first ==========
        logger.info(
            f"📡 Fetching profile for {psid} (sync) - Attempt 1: Instagram fields"
        )
        params = {
            "fields": ",".join(cls.BASE_FIELDS + cls.INSTAGRAM_FIELDS),
            "access_token": access_token,
        }
        response = httpx.get(url, params=params, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            # Check if Instagram-specific field (username) was returned
            if "username" in data:
                logger.info(f"✅ Detected Instagram profile for {psid}")
                logger.info(f"✅ Fetched profile with fields: {list(data.keys())}")
                return data
            else:
                # Has base fields but no username - might be Facebook or partial
                logger.debug(f"Instagram fields returned but no username field")
                return data

        error_response = (
            response.json()
            if response.headers.get("content-type") == "application/json"
            else response.text
        )
        logger.debug(f"Instagram attempt failed: {str(error_response)[:150]}")

        # ========== Call 2: Try Facebook fields ==========
        logger.info(
            f"📡 Fetching profile for {psid} (sync) - Attempt 2: Facebook fields"
        )
        params["fields"] = ",".join(cls.BASE_FIELDS + cls.FACEBOOK_FIELDS)
        response = httpx.get(url, params=params, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Detected Facebook profile for {psid}")
            logger.info(f"✅ Fetched profile with fields: {list(data.keys())}")
            return data

        logger.debug(f"Facebook attempt failed: {response.text[:150]}")

        # ========== Fallback: Base fields only ==========
        logger.warning(
            f"📡 Fetching profile for {psid} (sync) - Fallback: Base fields only"
        )
        params["fields"] = ",".join(cls.BASE_FIELDS)
        response = httpx.get(url, params=params, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Fetched minimal profile for {psid}: {list(data.keys())}")
            return data

        logger.error(f"❌ All attempts failed. Meta API Error: {response.text[:200]}")
        return None

    @classmethod
    def get_user_profile_sync(
        cls, access_token: str, psid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous version of get_user_profile for use in gRPC handlers and other sync contexts.

        Fetch comprehensive user profile information from Meta Graph API using PSID/IGSID.
        Intelligently detects whether the user is from Instagram or Facebook and requests appropriate fields.

        Args:
            access_token: The Page Access Token.
            psid: The Page-Scoped ID or Instagram-Scoped ID of the user.

        Returns:
            Dict containing user profile data or None.

        Available Fields (by platform):
            Facebook Messenger:
            - first_name, last_name, name, profile_pic
            - email (requires email permission)
            - locale, timezone, gender

            Instagram Business:
            - name, username, profile_pic
            - biography, website

        Optimization:
            Makes 2-3 API calls maximum (vs previous 12+ calls)
            Detects platform type to request only available fields
        """
        try:
            return cls._detect_platform_and_fetch_sync(access_token, psid)

        except httpx.RequestError as e:
            logger.error(f"❌ Network error fetching profile (sync): {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching profile (sync): {e}")
            return None

    @classmethod
    async def _detect_platform_and_fetch(
        cls, client: httpx.AsyncClient, access_token: str, psid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user is Instagram or Facebook and fetch appropriate fields (async).
        Uses a smart detection strategy with minimal API calls.

        Returns:
            Dict with profile data or None
        """
        url = f"{cls.BASE_URL}/{psid}"

        # ========== Call 1: Try Instagram fields first ==========
        logger.info(f"📡 Fetching profile for {psid} - Attempt 1: Instagram fields")
        params = {
            "fields": ",".join(cls.BASE_FIELDS + cls.INSTAGRAM_FIELDS),
            "access_token": access_token,
        }
        response = await client.get(url, params=params, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            # Check if Instagram-specific field (username) was returned
            if "username" in data:
                logger.info(f"✅ Detected Instagram profile for {psid}")
                logger.info(f"✅ Fetched profile with fields: {list(data.keys())}")
                return data
            else:
                # Has base fields but no username - might be Facebook or partial
                logger.debug(f"Instagram fields returned but no username field")
                return data

        error_response = (
            response.json()
            if response.headers.get("content-type") == "application/json"
            else response.text
        )
        logger.debug(f"Instagram attempt failed: {str(error_response)[:150]}")

        # ========== Call 2: Try Facebook fields ==========
        logger.info(f"📡 Fetching profile for {psid} - Attempt 2: Facebook fields")
        params["fields"] = ",".join(cls.BASE_FIELDS + cls.FACEBOOK_FIELDS)
        response = await client.get(url, params=params, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Detected Facebook profile for {psid}")
            logger.info(f"✅ Fetched profile with fields: {list(data.keys())}")
            return data

        logger.debug(f"Facebook attempt failed: {response.text[:150]}")

        # ========== Fallback: Base fields only ==========
        logger.warning(f"📡 Fetching profile for {psid} - Fallback: Base fields only")
        params["fields"] = ",".join(cls.BASE_FIELDS)
        response = await client.get(url, params=params, timeout=10.0)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Fetched minimal profile for {psid}: {list(data.keys())}")
            return data

        logger.error(f"❌ All attempts failed. Meta API Error: {response.text[:200]}")
        return None

    @classmethod
    async def get_user_profile(
        cls, access_token: str, psid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive user profile information from Meta Graph API using PSID/IGSID.
        Intelligently detects whether the user is from Instagram or Facebook and requests appropriate fields.

        Args:
            access_token: The Page Access Token.
            psid: The Page-Scoped ID or Instagram-Scoped ID of the user.

        Returns:
            Dict containing user profile data or None.

        Available Fields (by platform):
            Facebook Messenger:
            - first_name, last_name, name, profile_pic
            - email (requires email permission)
            - locale, timezone, gender

            Instagram Business:
            - name, username, profile_pic
            - biography, website

        Optimization:
            Makes 2-3 API calls maximum (vs previous 12+ calls)
            Detects platform type to request only available fields
        """
        try:
            async with httpx.AsyncClient() as client:
                return await cls._detect_platform_and_fetch(client, access_token, psid)

        except httpx.RequestError as e:
            logger.error(f"❌ Network error fetching profile: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching profile: {e}")
            return None
