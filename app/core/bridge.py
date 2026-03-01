import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class BridgeService:
    @staticmethod
    async def sync_batch_to_main_backend(batch_data: dict, tenant_id: str, scan_event_ids: list[str]):
        """
        Sends the completed batch data to the Main EcomOps Backend and updates DB sync status.
        """
        if not settings.MAIN_BACKEND_URL:
            logger.warning("MAIN_BACKEND_URL not set. Skipping sync.")
            return

        from app.core.database import async_session_maker
        from app.models.scan_event import ScanEvent
        from app.core.enums import SyncStatus
        from sqlalchemy import update

        url = f"{settings.MAIN_BACKEND_URL}/api/v1/integrations/mobile-sync"
        headers = {
            "Authorization": f"Bearer {settings.BRIDGE_API_KEY}",
            "X-Tenant-ID": tenant_id,
            "Content-Type": "application/json"
        }

        final_status = SyncStatus.FAILED
        async with httpx.AsyncClient() as client:
            for attempt in range(2):  # Simple retry for transient timeouts
                try:
                    # Render cold starts or heavy main backend loads can take >30s
                    response = await client.post(url, json=batch_data, headers=headers, timeout=90.0)
                    if response.is_error:
                        logger.error(f"Sync failed for batch {batch_data.get('batch_id')} (Attempt {attempt+1}) with status {response.status_code}. Response: {response.text}")
                        response.raise_for_status()
                    
                    logger.info(f"Successfully synced batch {batch_data.get('batch_id')} to main backend (Attempt {attempt+1}).")
                    final_status = SyncStatus.SYNCED
                    break  # Success
                except httpx.ReadTimeout:
                    if attempt == 0:
                        logger.warning(f"ReadTimeout during bridge sync (Attempt 1). Retrying...")
                        continue
                    logger.error("ReadTimeout during bridge sync (Attempt 2). Giving up.")
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTPStatusError during bridge sync: {e.response.status_code} - {e.response.text}")
                    break # Don't retry auth/config errors
                except Exception:
                    logger.exception("Unexpected error during bridge sync to main backend")
                    break
        
        # Update database with final status
        if scan_event_ids:
            try:
                async with async_session_maker() as db:
                    await db.execute(
                        update(ScanEvent)
                        .where(ScanEvent.id.in_(scan_event_ids))
                        .values(sync_status=final_status)
                    )
                    await db.commit()
                    logger.info(f"Updated {len(scan_event_ids)} scans to {final_status} for batch {batch_data.get('batch_id')}")
            except Exception as e:
                logger.exception(f"Failed to update sync status for batch {batch_data.get('batch_id')}: {e}")
