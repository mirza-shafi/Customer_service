# Customer Service

A microservice for managing external customers from Instagram and Facebook as the **Source of Truth** for external identities in your microservices architecture.

## Overview

This service manages customers who message you via Instagram/Facebook, distinct from internal platform users (managed by Auth Service).

### Key Concepts

| Term | Description |
|------|-------------|
| **PSID** | Page Scoped ID - Unique identifier from Instagram/Facebook webhooks |
| **IGSID** | Instagram Scoped ID - Instagram-specific identifier |
| **app_id** | Logical link to App Service (no hard FK across microservices) |
| **access_token** | Meta Graph API token for fetching profile data |

```mermaid
graph TD
    Auth[Auth Service<br/>Port 8000]
    Web[Webhook Service<br/>Port 8006]
    Cust[Customer Service<br/>Port 8007 / gRPC 50052]
    Apps[Apps Service<br/>Port 8500 / gRPC 50051]
    Meta[Meta Graph API]

    Web -->|gRPC| Apps
    Web -->|gRPC| Cust
    Apps -->|gRPC| Cust
    Cust -->|REST| Meta
    Web -->|REST| Meta
```

## Features

- **Customer CRUD** - Create, read, update, delete customers
- **Profile Fetching** - Fetch customer profile from Meta Graph API
- **Upsert Support** - Update or insert customers (for webhook sync)
- **Search & Filter** - Find customers by name, email, phone, or PSID
- **Block/Unblock** - Manage customer access
- **Redis Caching** - Cache Meta profiles to avoid rate limits

## Database

Uses a **separate PostgreSQL database** for isolation:

| Service | Port | Database |
|---------|------|----------|
| Customer Service | 5434 | customer_db |
| Webhook Service | 5433 | webhook_db |
| Auth/App Service | 5432 | (shared/main) |

## Quick Start

### 1. Start Docker Services

```bash
cd customer-service
docker-compose up -d
```

This starts:
- PostgreSQL (port 5434)
- pgAdmin (port 5051) - Access at http://localhost:5051
- Redis (port 6380)
- FastAPI App (port 8007)

### 2. Access pgAdmin

- URL: http://localhost:5051
- Email: `admin@customer.com`
- Password: `adminpass`

To connect to PostgreSQL in pgAdmin:
- Host: `postgres` (or `host.docker.internal` from host)
- Port: `5432` (internal) or `5434` (external)
- Database: `customer_db`
- Username: `customer_user`
- Password: `customer_password`

### 3. API Documentation

- Swagger UI: http://localhost:8007/docs
- ReDoc: http://localhost:8007/redoc

## Development Setup (Without Docker)

### 1. Create Virtual Environment

```bash
cd customer-service
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Environment

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 4. Start Database Only

```bash
docker-compose up -d postgres pgadmin redis
```

### 5. Run Application

**FastAPI Server**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8007 --reload
```

**gRPC Server**:
```bash
python app/grpc_main.py
```
Starts on port `50052`.

## API Endpoints

### Customer Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/customers` | Create a new customer |
| GET | `/api/v1/customers` | List customers (paginated) |
| GET | `/api/v1/customers/{id}` | Get customer by ID |
| GET | `/api/v1/customers/psid/{psid}` | Get customer by PSID |
| PUT | `/api/v1/customers/{id}` | Update customer |
| DELETE | `/api/v1/customers/{id}` | Delete customer |
| POST | `/api/v1/customers/upsert` | Upsert customer (for webhook) |

### Profile & Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/customers/{id}/fetch-profile` | Fetch profile from Meta API |
| POST | `/api/v1/customers/{id}/block` | Block customer |
| POST | `/api/v1/customers/{id}/unblock` | Unblock customer |
| PATCH | `/api/v1/customers/{id}/interaction` | Update last interaction |

## Integration with Webhook Service

### Workflow for Processing Messages

```python
# In webhook-service/app/services/instagram_service.py

async def process_message(sender_id: str, message: str):
    # 1. Receive message with sender_id (PSID)
    
    # 2. Fetch profile from Meta Graph API
    profile = await fetch_meta_user_profile(
        psid=sender_id,
        access_token=channel.page_access_token
    )
    
    # 3. Sync customer to Customer Service
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8007/api/v1/customers/upsert",
            params={
                "app_id": str(app_id),
                "psid": sender_id,
                "platform": "instagram",
                "first_name": profile.first_name,
                "last_name": profile.last_name,
                "profile_pic_url": profile.profile_pic_url,
            },
            headers={"Authorization": f"Bearer {token}"}
        )
    
    # 4. Continue with conversation/message handling
```

## Manual Mode (Current State)

For now, customer IDs and access tokens are saved manually:

1. **Create Customer** with `psid`, `app_id`, and `access_token`
2. **Fetch Profile** using `POST /customers/{id}/fetch-profile`
3. Customer profile is updated with Meta data

### Example: Creating a Customer

```bash
curl -X POST "http://localhost:8007/api/v1/customers" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "YOUR_APP_UUID",
    "psid": "INSTAGRAM_USER_PSID",
    "platform": "instagram",
    "access_token": "YOUR_META_ACCESS_TOKEN"
  }'
```

### Example: Fetching Profile

```bash
curl -X POST "http://localhost:8007/api/v1/customers/{customer_id}/fetch-profile" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Authentication

All endpoints require a valid JWT token from the Auth Service:

```bash
# Include in Authorization header
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

The service validates tokens using JWKS from:
- `JWKS_URL=http://localhost:8000/.well-known/jwks.json`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | Required |
| REDIS_URL | Redis connection string | Required |
| SECRET_KEY | Application secret key | Required |
| JWKS_URL | Auth service JWKS endpoint | Required |
| JWT_ISSUER | JWT issuer claim | https://auth.brainchat.cloud |
| JWT_AUDIENCE | JWT audience claim | mission-auth |
| META_GRAPH_API_VERSION | Meta API version | v21.0 |

## Future Improvements

1. **Automated Token Handling** - OAuth flow for access tokens
2. **Webhook Integration** - Direct sync from webhook service
3. **Customer Segmentation** - Tags and custom attributes
4. **Analytics** - Customer engagement metrics
5. **Real-time Updates** - WebSocket for live customer data

## License

Private - Internal use only.
