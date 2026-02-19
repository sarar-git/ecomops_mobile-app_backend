#!/bin/bash
# Example curl requests for Logistics Scanning API
# Base URL - change for your environment
BASE_URL="http://localhost:8000"

echo "=== 1. Login ==="
TOKEN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@demo.com", "password": "admin123"}')
echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))"

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens']['access_token'])")
echo "Access Token: ${ACCESS_TOKEN:0:50}..."

echo -e "\n=== 2. Get Current User ==="
curl -s -X GET "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== 3. List Warehouses ==="
WAREHOUSES=$(curl -s -X GET "$BASE_URL/api/v1/warehouses" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
echo "$WAREHOUSES" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

WAREHOUSE_ID=$(echo "$WAREHOUSES" | python3 -c "import sys,json; w=json.load(sys.stdin); print(w[0]['id'] if w else '')")
echo "Using Warehouse ID: $WAREHOUSE_ID"

echo -e "\n=== 4. Start a New Manifest ==="
TODAY=$(date +%Y-%m-%d)
MANIFEST_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/manifests/start" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"warehouse_id\": \"$WAREHOUSE_ID\",
    \"manifest_date\": \"$TODAY\",
    \"shift\": \"MORNING\",
    \"marketplace\": \"AMAZON\",
    \"carrier\": \"DELHIVERY\",
    \"flow_type\": \"DISPATCH\"
  }")
echo "$MANIFEST_RESPONSE" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

MANIFEST_ID=$(echo "$MANIFEST_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id', ''))")
echo "Manifest ID: $MANIFEST_ID"

echo -e "\n=== 5. Bulk Create Scan Events ==="
curl -s -X POST "$BASE_URL/api/v1/scan-events/bulk" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {\"manifest_id\": \"$MANIFEST_ID\", \"barcode_value\": \"PKG-AMZ-001\", \"barcode_type\": \"QR\"},
      {\"manifest_id\": \"$MANIFEST_ID\", \"barcode_value\": \"PKG-AMZ-002\", \"extracted_order_id\": \"ORD123\"},
      {\"manifest_id\": \"$MANIFEST_ID\", \"barcode_value\": \"PKG-AMZ-003\", \"extracted_awb\": \"AWB456\", \"confidence_score\": 0.95}
    ]
  }" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== 6. List Scan Events for Manifest ==="
curl -s -X GET "$BASE_URL/api/v1/scan-events?manifest_id=$MANIFEST_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== 7. Get Manifest Details ==="
curl -s -X GET "$BASE_URL/api/v1/manifests/$MANIFEST_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== 8. Close Manifest ==="
curl -s -X POST "$BASE_URL/api/v1/manifests/$MANIFEST_ID/close" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== 9. Export Manifest CSV ==="
curl -s -X GET "$BASE_URL/api/v1/manifests/$MANIFEST_ID/export.csv" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

echo -e "\n\n=== 10. List All Manifests (with filters) ==="
curl -s -X GET "$BASE_URL/api/v1/manifests?status=CLOSED&marketplace=AMAZON" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== 11. Test Duplicate Scan (Idempotent) ==="
curl -s -X POST "$BASE_URL/api/v1/scan-events/bulk" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {\"manifest_id\": \"$MANIFEST_ID\", \"barcode_value\": \"PKG-AMZ-001\"}
    ]
  }" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== 12. Refresh Token ==="
REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens']['refresh_token'])")
curl -s -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== Done! ==="
