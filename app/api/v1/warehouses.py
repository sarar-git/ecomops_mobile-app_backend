"""Warehouse API endpoints."""
from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import TenantCtx, DbSession
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseResponse


router = APIRouter()


@router.get("", response_model=List[WarehouseResponse])
async def list_warehouses(
    ctx: TenantCtx,
    db: DbSession,
):
    """List all warehouses for the current tenant."""
    result = await db.execute(
        select(Warehouse)
        .where(Warehouse.tenant_id == ctx.tenant_id)
        .order_by(Warehouse.name)
    )
    warehouses = result.scalars().all()
    
    return [WarehouseResponse.model_validate(w) for w in warehouses]


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: str,
    ctx: TenantCtx,
    db: DbSession,
):
    """Get a specific warehouse by ID."""
    result = await db.execute(
        select(Warehouse)
        .where(
            Warehouse.id == warehouse_id,
            Warehouse.tenant_id == ctx.tenant_id
        )
    )
    warehouse = result.scalar_one_or_none()
    
    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found",
        )
    
    return WarehouseResponse.model_validate(warehouse)
