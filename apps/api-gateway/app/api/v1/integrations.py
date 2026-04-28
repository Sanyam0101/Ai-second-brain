from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg
import uuid
from typing import List
from app.deps.database import get_db_connection
from app.deps.auth import get_current_user
from app.schemas.auth import UserResponse
from app.schemas.integrations import IntegrationConnect, IntegrationResponse
from app.services.integrations import IntegrationsService
from pydantic import BaseModel

router = APIRouter(prefix="/integrations", tags=["integrations"])

class SyncResponse(BaseModel):
    message: str
    synced_notes: int

@router.get("/", response_model=List[IntegrationResponse])
async def get_integrations(
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    try:
        return await IntegrationsService.get_user_integrations(conn, current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching integrations: {str(e)}"
        )

@router.post("/connect", status_code=status.HTTP_200_OK)
async def connect_integration(
    data: IntegrationConnect,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    try:
        await IntegrationsService.connect_integration(conn, current_user.id, data.platform, data.access_token)
        # Auto-sync immediately after connecting
        try:
            synced = await IntegrationsService.trigger_sync(conn, current_user.id, data.platform)
            return {"status": "success", "platform": data.platform, "synced_notes": synced}
        except Exception:
            return {"status": "success", "platform": data.platform, "synced_notes": 0}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting integration: {str(e)}"
        )

@router.delete("/{platform}", status_code=status.HTTP_200_OK)
async def disconnect_integration(
    platform: str,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    try:
        await IntegrationsService.disconnect_integration(conn, current_user.id, platform)
        return {"status": "success", "platform": platform}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error disconnecting integration: {str(e)}"
        )

@router.post("/{platform}/sync", response_model=SyncResponse)
async def sync_integration(
    platform: str,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    try:
        synced_count = await IntegrationsService.trigger_sync(conn, current_user.id, platform)
        return SyncResponse(message=f"Successfully synced {synced_count} items from {platform}", synced_notes=synced_count)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing integration: {str(e)}"
        )
