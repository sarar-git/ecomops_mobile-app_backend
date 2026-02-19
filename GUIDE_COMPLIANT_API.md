# Guide-Compliant Batch Scanning API

## Overview
This implementation provides a guide-compliant `/api/v1/scans/batch` endpoint that matches the Mobile App API Integration Guide exactly.

## Changes Made

### New Files Created
1. **app/schemas/scan.py** - New Pydantic schemas for guide-compliant batch scanning
   - `BatchScanRequest` - Request body matching guide specification
   - `BatchScanResponse` - Response body with batch_id and matched_orders
   - `BatchScanStatusResponse` - Status check response
   
2. **app/api/v1/scans.py** - New router with guide-compliant endpoints
   - `POST /api/v1/scans/batch` - Submit batch of scans
   - `GET /api/v1/scans/batch/{batch_id}` - Check batch status

### Modified Files
- **app/api/v1/__init__.py** - Added scans router to v1 API
- **app/schemas/__init__.py** - Exported new scan schemas

## Endpoint Specification

### POST /api/v1/scans/batch

Submit a batch of scanned barcodes (AWB or Order IDs) for processing.

**Authentication:** Required (JWT Bearer Token)

**Request Body:**
```json
{
  "batch_name": "Morning Dispatch - Feb 18",
  "scan_type": "DISPATCH",
  "scans": [
    {
      "scan_code": "1234567890",
      "timestamp": "2026-02-18T10:30:00Z",
      "meta_data": {
        "device": "Samsung S21",
        "packer": "John Doe"
      }
    },
    {
      "scan_code": "0987654321",
      "timestamp": "2026-02-18T10:30:05Z"
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "message": "Batch processed successfully",
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_scans": 2,
  "matched_orders": 2,
  "results": [
    {
      "scan_code": "1234567890",
      "success": true,
      "is_duplicate": false
    },
    {
      "scan_code": "0987654321",
      "success": true,
      "is_duplicate": false
    }
  ]
}
```

**Response (401 Unauthorized):**
Token is missing or expired. Refresh the token and retry.

### GET /api/v1/scans/batch/{batch_id}

Check the status of a previously submitted batch.

**Response:**
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "batch_name": "Morning Dispatch - Feb 18",
  "scan_type": "DISPATCH",
  "total_scans": 2,
  "processed_scans": 2,
  "matched_orders": 2,
  "created_at": "2026-02-18T10:30:00Z",
  "status": "completed"
}
```

## Key Features

### ✅ Guide Compliance
- Matches exact request/response format from guide
- Uses `scan_code` instead of `barcode_value`
- Returns `batch_id` and `matched_orders`
- Supports optional `batch_name` and `meta_data`

### ✅ Business Logic
- Automatic manifest creation/reuse based on flow_type
- Idempotent processing (duplicate detection)
- Server-controlled timestamps (UTC)
- Device/packer tracking via metadata

### ✅ Error Handling
- Detailed per-scan results array
- Error messages for failed scans
- Duplicate detection (not counted as errors)
- User warehouse assignment validation

## Implementation Details

### Manifest Management
- Automatically creates OPEN manifest per tenant/warehouse/flow_type/date
- Reuses existing manifests if available
- Sets default values: shift=MORNING, marketplace=AMAZON, carrier=DELHIVERY
- Updates total_packets count

### Scan Processing
- Each scan stored as ScanEvent in database
- Duplicates detected on (manifest_id, barcode_value) combination
- Operator and device metadata captured
- Sync status set to SYNCED immediately

### Batch Tracking
- In-memory batch registry (can be upgraded to Redis/DB in production)
- batch_id returned for optional status polling
- Batch status persists for session lifetime

## Integration with Existing System

This endpoint **complements** the existing `/api/v1/scan-events/bulk` endpoint:

| Feature | /scans/batch | /scan-events/bulk |
|---------|--------------|-------------------|
| Target Audience | Mobile app clients | Backend integrations |
| Request Format | batches with flow_type | individual events with manifest_id |
| Auto-Manifest | Yes | No (manifest_id required) |
| Response Format | Guide-compliant | Detailed technical response |
| Use Case | Field scanning | System integrations |

## Testing

Example cURL command:
```bash
curl -X POST http://localhost:8000/api/v1/scans/batch \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "Test Batch",
    "scan_type": "DISPATCH",
    "scans": [
      {
        "scan_code": "AWB123456",
        "timestamp": "2026-02-18T10:30:00Z",
        "meta_data": {
          "device": "iPhone 14",
          "packer": "Alice"
        }
      }
    ]
  }'
```

## Future Enhancements

1. **Order Matching Logic**: Implement actual order matching to populate `matched_orders` with real count
2. **Persistent Batch Storage**: Store batch metadata in database instead of memory
3. **Batch Retry**: Support retry logic for failed scans
4. **Webhook Notifications**: Real-time batch status updates
5. **Configurable Defaults**: Allow per-tenant default marketplace/carrier/shift
6. **Batch Analytics**: Aggregated reporting for batch operations
