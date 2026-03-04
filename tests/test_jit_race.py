import asyncio
import uuid
from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.user import User
from app.core.dependencies import get_current_user
from app.core.security import TokenPayload

async def test_jit_race_simulation():
    # 1. Setup - Create a dummy token for a non-existent user
    user_id = str(uuid.uuid4())
    token = TokenPayload(
        sub=user_id,
        email=f"race_test_{user_id[:8]}@example.com",
        role="MOBILE_USER",
        tenant_id=None, # Will use logic to get default
        type="access"
    )

    print(f"--- Simulating Concurrent JIT Provisioning for User: {user_id} ---")

    async def simulate_request(req_id):
        async with async_session_maker() as db:
            try:
                print(f"Request {req_id}: Starting...")
                user = await get_current_user(token=token, db=db)
                print(f"Request {req_id}: SUCCESS (User ID: {user.id})")
                return True
            except Exception as e:
                print(f"Request {req_id}: FAILED - {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                return False

    # 2. Fire 5 requests simultaneously
    results = await asyncio.gather(*[simulate_request(i) for i in range(5)])

    # 3. Analyze results
    success_count = sum(1 for r in results if r)
    print(f"--- Results Summary ---")
    print(f"Total Requests: 5")
    print(f"Successful: {success_count}")
    
    if success_count == 5:
        print("✅ SUCCESS: Race condition handled. All concurrent requests succeeded.")
    else:
        print("❌ FAILURE: Some requests failed due to race condition.")

if __name__ == "__main__":
    asyncio.run(test_jit_race_simulation())
