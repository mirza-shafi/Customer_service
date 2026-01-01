import httpx
import logging
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class GraphAPIService:
    BASE_URL = "https://graph.facebook.com/v21.0"

    @classmethod
    async def get_user_profile(
        cls, access_token: str, psid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive user profile information from Meta Graph API using PSID/IGSID.

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
            - biography, website, ig_id
            - followers_count, follows_count

        Note:
            Implements intelligent field selection based on what's actually available.
            Tries to request fields individually to isolate permission/availability issues.
        """
        url = f"{cls.BASE_URL}/{psid}"

        try:
            async with httpx.AsyncClient() as client:
                # ========== Attempt 1: Full comprehensive fields ==========
                logger.info(
                    f"📡 Fetching profile for {psid} - Attempt 1: Comprehensive fields"
                )
                params = {
                    "fields": "first_name,last_name,name,profile_pic,username,email,locale,timezone,gender,biography,website",
                    "access_token": access_token,
                }
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Fetched comprehensive profile for {psid}")
                    logger.debug(f"Returned fields: {list(data.keys())}")
                    return data

                # Log what fields failed
                error_msg = response.text
                logger.warning(
                    f"⚠️ Attempt 1 failed (400): {error_msg[:200]}... Trying individual fields for {psid}"
                )

                # ========== Attempt 2: Try fields individually ==========
                # Start with a base set and add fields one by one
                base_fields = ["name", "profile_pic"]
                optional_fields = [
                    "first_name",
                    "last_name",
                    "username",
                    "email",
                    "locale",
                    "timezone",
                    "gender",
                    "biography",
                    "website",
                ]

                successful_response = None
                collected_fields = {}

                # First try base fields
                logger.info(f"📡 Fetching profile for {psid} - Attempt 2: Base fields")
                params["fields"] = ",".join(base_fields)
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    collected_fields = response.json()
                    logger.info(
                        f"✅ Base fields retrieved: {list(collected_fields.keys())}"
                    )
                else:
                    logger.error(f"❌ Even base fields failed: {response.text[:200]}")
                    return None

                # Try adding optional fields one by one
                for field in optional_fields:
                    test_fields = base_fields + [field]
                    params["fields"] = ",".join(test_fields)
                    response = await client.get(url, params=params, timeout=10.0)

                    if response.status_code == 200:
                        data = response.json()
                        # Check if the new field was actually returned
                        if field in data and field not in collected_fields:
                            collected_fields[field] = data[field]
                            logger.debug(f"✅ Added field: {field} = {data[field]}")
                    else:
                        logger.debug(
                            f"⚠️ Field '{field}' not available or permission denied"
                        )

                if collected_fields:
                    logger.info(
                        f"✅ Fetched profile (composite) for {psid} with fields: {list(collected_fields.keys())}"
                    )
                    return collected_fields

                # ========== Fallback: Minimal fields ==========
                logger.warning(
                    f"📡 Fetching profile for {psid} - Attempt 3: Minimal fields"
                )
                params["fields"] = "name,profile_pic,id"
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"✅ Fetched minimal profile for {psid}: {list(data.keys())}"
                    )
                    return data

                logger.error(f"❌ All attempts failed. Meta API Error: {response.text}")
                return None

        except httpx.RequestError as e:
            logger.error(f"❌ Network error fetching profile: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching profile: {e}")
            return None

        except httpx.RequestError as e:
            logger.error(f"❌ Network error fetching profile: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching profile: {e}")
            return None
