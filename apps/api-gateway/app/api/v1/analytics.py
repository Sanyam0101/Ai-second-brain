from fastapi import APIRouter, Depends, HTTPException
from app.deps.database import get_db_connection, get_neo4j_session
from app.deps.auth import get_current_user
from app.schemas.auth import UserResponse
from app.services.analytics import AnalyticsService
from app.schemas.analytics import AnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/overview", response_model=AnalyticsResponse)
async def get_analytics_overview(
    current_user: UserResponse = Depends(get_current_user),
    pg_conn = Depends(get_db_connection),
    neo4j_session = Depends(get_neo4j_session)
):
    """Get comprehensive system analytics overview"""
    try:
        return await AnalyticsService.get_system_overview(pg_conn, neo4j_session, current_user.id)
    except Exception as e:
        raise HTTPException(500, f"Analytics query failed: {e}")

@router.get("/stats")
async def get_quick_stats(
    current_user: UserResponse = Depends(get_current_user),
    pg_conn = Depends(get_db_connection),
    neo4j_session = Depends(get_neo4j_session)
):
    """Quick stats endpoint for lightweight monitoring"""
    try:
        notes_count = await pg_conn.fetchval("SELECT COUNT(*) FROM notes WHERE user_id = $1", current_user.id)

        ideas_result = await neo4j_session.run("MATCH (i:Idea {user_id: $uid}) RETURN count(i) as count", uid=str(current_user.id))
        ideas_record = await ideas_result.single()
        ideas_count = ideas_record['count'] if ideas_record else 0

        return {
            "status": "ok",
            "notes": notes_count or 0,
            "ideas": ideas_count,
            "timestamp": "2025-09-11T16:00:00Z"
        }
    except Exception as e:
        raise HTTPException(500, f"Stats query failed: {e}")

@router.post("/sync-neo4j")
async def sync_notes_to_neo4j(
    current_user: UserResponse = Depends(get_current_user),
    pg_conn = Depends(get_db_connection),
    neo4j_session = Depends(get_neo4j_session)
):
    """
    One-time sync: reads all notes from PostgreSQL and creates/updates
    corresponding Idea + Tag nodes in Neo4j for the current user.
    Call this once if graph is empty despite having notes.
    """
    try:
        notes = await pg_conn.fetch(
            "SELECT id, user_id, content, tags FROM notes WHERE user_id = $1",
            current_user.id
        )
        synced = 0
        for note in notes:
            note_id = str(note['id'])
            user_id = str(note['user_id'])
            title = note['content'][:50] + "..." if len(note['content']) > 50 else note['content']
            tags = note['tags'] or []

            # Create/update the Idea node
            r = await neo4j_session.run(
                "MERGE (i:Idea {id: $id}) SET i.title = $title, i.user_id = $uid RETURN i.id",
                id=note_id, title=title, uid=user_id
            )
            await r.consume()

            # Create tags and connect them
            for tag in tags:
                tr = await neo4j_session.run(
                    """
                    MATCH (i:Idea {id: $id})
                    MERGE (t:Tag {name: $tag})
                    MERGE (i)-[:TAGGED_WITH]->(t)
                    """,
                    id=note_id, tag=tag
                )
                await tr.consume()

            synced += 1

        return {
            "status": "ok",
            "synced_notes": synced,
            "message": f"Synced {synced} notes to Neo4j! Refresh the dashboard and graph."
        }
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {e}")

@router.get("/health")
async def analytics_health():
    """Analytics service health check"""
    return {
        "status": "ok",
        "service": "Analytics",
        "capabilities": ["system_stats", "activity_metrics", "tag_analytics", "database_health"]
    }
