# Logistics Scanning API

Production-ready FastAPI backend for a mobile-only SaaS logistics scanning application.

## Features

- **Multi-Tenant Architecture**: Complete data isolation per tenant
- **JWT Authentication**: Access + refresh token flow
- **PostgreSQL**: Async SQLAlchemy 2.0 with proper indexing
- **Alembic Migrations**: Database versioning
- **Business Rules Enforcement**: 
  - One OPEN manifest per unique combination
  - Server-generated timestamps
  - Idempotent bulk scan ingestion
- **Performance Optimized**: Async queries, proper indexes, batch operations

## Quick Start with Docker

```bash
cd /app/backend
docker-compose up --build
```

The API will be available at `http://localhost:8000`

## API Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## Test Credentials

After seeding:
- Admin: `admin@demo.com` / `admin123`
- Manager: `manager@demo.com` / `manager123`
- Operator: `operator@demo.com` / `operator123`

## API Endpoints

### Authentication
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@demo.com", "password": "admin123"}'

# Get current user
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

### Warehouses
```bash
# List warehouses
curl -X GET http://localhost:8000/api/v1/warehouses \
  -H "Authorization: Bearer <access_token>"
```

### Manifests
```bash
# Start a new manifest
curl -X POST http://localhost:8000/api/v1/manifests/start \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "warehouse_id": "<warehouse_id>",
    "manifest_date": "2024-01-15",
    "shift": "MORNING",
    "marketplace": "AMAZON",
    "carrier": "DELHIVERY",
    "flow_type": "DISPATCH"
  }'

# Close manifest
curl -X POST http://localhost:8000/api/v1/manifests/<manifest_id>/close \
  -H "Authorization: Bearer <access_token>"

# List manifests
curl -X GET http://localhost:8000/api/v1/manifests \
  -H "Authorization: Bearer <access_token>"

# Export manifest to CSV
curl -X GET http://localhost:8000/api/v1/manifests/<manifest_id>/export.csv \
  -H "Authorization: Bearer <access_token>" \
  -o manifest.csv
```

### Scan Events
```bash
# Bulk create scan events
curl -X POST http://localhost:8000/api/v1/scan-events/bulk \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"manifest_id": "<manifest_id>", "barcode_value": "BARCODE001"},
      {"manifest_id": "<manifest_id>", "barcode_value": "BARCODE002", "barcode_type": "QR"}
    ]
  }'

# List scan events for manifest
curl -X GET "http://localhost:8000/api/v1/scan-events?manifest_id=<manifest_id>" \
  -H "Authorization: Bearer <access_token>"
```

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── manifests.py
│   │       ├── scan_events.py
│   │       └── warehouses.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── enums.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── models/
│   │   ├── manifest.py
│   │   ├── scan_event.py
│   │   ├── tenant.py
│   │   ├── user.py
│   │   └── warehouse.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── manifest.py
│   │   ├── scan_event.py
│   │   ├── tenant.py
│   │   └── warehouse.py
│   ├── tasks/
│   │   └── __init__.py (Celery stubs)
│   ├── main.py
│   └── seed_data.py
├── alembic/
│   ├── versions/
│   │   └── 001_initial_schema.py
│   └── env.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_manifests.py
│   └── test_scan_events.py
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Enums Reference

### Marketplaces
- AMAZON, FLIPKART, MYNTRA, JIOMART, MEESHO, AJIO

### Carriers
- DELHIVERY, EKART, SHADOWFAX, BLUEDART, AMAZON_SHIPPING

### Flow Types
- DISPATCH, RETURN

### Shifts
- MORNING, EVENING, NIGHT

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx aiosqlite

# Run tests
pytest tests/ -v
```

## Environment Variables

See `.env.example` for all configuration options.

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```
