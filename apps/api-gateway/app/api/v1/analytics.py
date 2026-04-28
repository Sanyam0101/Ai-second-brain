from fastapi import APIRouter, Depends, HTTPException
from app.deps.database import get_db_connection
from app.deps.auth import get_current_user
from app.schemas.auth import UserResponse
from app.services.analytics import AnalyticsService
from app.schemas.analytics import AnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/overview", response_model=AnalyticsResponse)
async def get_analytics_overview(
    current_user: UserResponse = Depends(get_current_user),
    pg_conn = Depends(get_db_connection)
):
    """Get comprehensive system analytics overview"""
    try:
        return await AnalyticsService.get_system_overview(pg_conn, current_user.id)
    except Exception as e:
        raise HTTPException(500, f"Analytics query failed: {e}")

@router.get("/stats")
async def get_quick_stats(
    current_user: UserResponse = Depends(get_current_user),
    pg_conn = Depends(get_db_connection)
):
    """Quick stats endpoint for lightweight monitoring"""
    try:
        notes_count = await pg_conn.fetchval("SELECT COUNT(*) FROM notes WHERE user_id = $1", current_user.id)
        ideas_count = notes_count

        return {
            "status": "ok",
            "notes": notes_count or 0,
            "ideas": ideas_count or 0,
            "timestamp": "2025-09-11T16:00:00Z"
        }
    except Exception as e:
        raise HTTPException(500, f"Stats query failed: {e}")

@router.post("/sync-neo4j")
async def sync_notes_to_neo4j():
    # Legacy endpoint, Neo4j removed
    return {
        "status": "ok",
        "synced_notes": 0,
        "message": "Neo4j has been removed. PostgreSQL handles the graph now."
    }

@router.get("/health")
async def analytics_health():
    """Analytics service health check"""
    return {
        "status": "ok",
        "service": "Analytics",
        "capabilities": ["system_stats", "activity_metrics", "tag_analytics", "database_health"]
    }
