import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class BridgeService:
    @staticmethod
    async def sync_batch_to_main_backend(batch_data: dict, tenant_id: str):
        """
        Sends the completed batch data to the Main EcomOps Backend.
        """
        if not settings.MAIN_BACKEND_URL:
            logger.warning("MAIN_BACKEND_URL not set. Skipping sync.")
            return

        url = f"{settings.MAIN_BACKEND_URL}/api/v1/integrations/mobile-sync"
        headers = {
            "Authorization": f"Bearer {settings.BRIDGE_API_KEY}",
            "X-Tenant-ID": tenant_id,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=batch_data, headers=headers, timeout=10.0)
                response.raise_for_status()
                logger.info(f"Successfully synced batch {batch_data.get('batch_id')} to main backend.")
            except Exception as e:
                logger.error(f"Failed to sync batch to main backend: {str(e)}")
                # TODO: Implement retry logic (Celery/Redis)
