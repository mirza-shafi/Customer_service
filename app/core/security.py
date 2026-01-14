"""
Security utilities for Customer Service

Contains JWT token validation using JWKS from Auth Service.
Same authentication pattern as apps_service and webhook-service.
"""

from jose import jwt, JWTError, jwk
from fastapi import HTTPException, Request, status, Depends
from app.core.config import settings
from typing import Optional, Dict, Any
import httpx
import redis
import json
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Redis connection for JWKS caching
redis_client = redis.StrictRedis.from_url(settings.REDIS_URL, decode_responses=True)
security_scheme = HTTPBearer(auto_error=False)
JWKS_URL = settings.JWKS_URL
ALGORITHM = settings.ALGORITHM


def extract_token_from_request(request: Request) -> Optional[str]:
    """
    Extract token from cookies or Authorization header.
    """
    # Check for token in cookies
    token = request.cookies.get("access_token")
    if token:
        return token

    # Fallback to Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]

    return None


async def fetch_jwks():
    """
    Fetch JWKS from the auth microservice.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(JWKS_URL)
        response.raise_for_status()
        return response.json()


def get_public_key_from_jwks(jwks, kid):
    """
    Extract the public key from JWKS using the key ID (kid).
    """
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return jwk.construct(key)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token: key not found",
    )


def cache_jwks(jwks):
    """
    Cache the JWKS in Redis for 30 minutes.
    """
    jwks_json = json.dumps(jwks)
    redis_client.set("customer_service_jwks", jwks_json, ex=1800)


def get_cached_jwks():
    """
    Retrieve JWKS from Redis cache.
    """
    cached_jwks = redis_client.get("customer_service_jwks")
    if cached_jwks:
        return json.loads(cached_jwks)
    return None


async def validate_token_with_jwks(token: str) -> Dict[str, Any]:
    """
    Validate the JWT using JWKS, with caching.
    """
    try:
        # Decode the token header to get the key ID (kid)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key ID",
            )

        # Check Redis cache for JWKS
        jwks = get_cached_jwks()
        if not jwks:
            # Fetch JWKS from the auth microservice if not in cache
            jwks = await fetch_jwks()
            cache_jwks(jwks)

        # Get the public key from JWKS
        public_key = get_public_key_from_jwks(jwks, kid)

        # Validate the token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Dict[str, Any]:
    """
    Dependency to get the current user from the request.
    Supports both Authorization header and cookies.
    """
    token = None

    # Check Authorization header first
    if credentials:
        token = credentials.credentials

    # Fallback to cookies if no token in header
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = await validate_token_with_jwks(token)

    # The authentications service uses 'user_id' in the payload
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user information",
        )

    return payload
