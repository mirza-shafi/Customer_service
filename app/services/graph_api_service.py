import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GraphAPIService:
    BASE_URL = "https://graph.facebook.com/v21.0"

    @classmethod
    async def get_user_profile(
        cls, access_token: str, psid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch user profile information from Meta Graph API using PSID.

        Args:
            access_token: The Page Access Token.
            psid: The Page-Scoped ID of the user.

        Returns:
            Dict containing user profile data (first_name, last_name, profile_pic) or None.
        """
        url = f"{cls.BASE_URL}/{psid}"

        params = {
            "fields": "first_name,last_name,profile_pic",
            "access_token": access_token,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Fetched profile for {psid}")
                    return data
                else:
                    logger.error(
                        f"❌ Failed to fetch profile: {response.status_code} - {response.text}"
                    )
                    return None

        except httpx.RequestError as e:
            logger.error(f"❌ Network error fetching profile: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching profile: {e}")
            return None
