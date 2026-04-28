import asyncpg
import uuid
from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.schemas.analytics import (
    SystemStats, ActivityMetrics, TagAnalytics, 
    DatabaseHealth, AnalyticsResponse, SearchAnalytics
)

class AnalyticsService:
    @staticmethod
    async def get_system_overview(
        pg_conn: asyncpg.Connection,
        user_id: str
    ) -> AnalyticsResponse:
        """Get comprehensive system analytics"""
        
        # Get PostgreSQL stats
        system_stats = await AnalyticsService._get_system_stats(pg_conn, user_id)
        activity_metrics = await AnalyticsService._get_activity_metrics(pg_conn, user_id)
        top_tags = await AnalyticsService._get_tag_analytics(pg_conn, user_id)
        db_health = await AnalyticsService._get_database_health(pg_conn)
        
        return AnalyticsResponse(
            timestamp=datetime.utcnow(),
            system_stats=system_stats,
            activity_metrics=activity_metrics,
            top_tags=top_tags,
            database_health=db_health
        )
    
    @staticmethod
    async def _get_system_stats(
        pg_conn: asyncpg.Connection,
        user_id: str
    ) -> SystemStats:
        """Get basic system statistics"""
        
        user_uuid = uuid.UUID(str(user_id))

        # PostgreSQL queries
        notes_count = await pg_conn.fetchval("SELECT COUNT(*) FROM notes WHERE user_id = $1", user_uuid)
        unique_users = await pg_conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM notes WHERE user_id = $1", user_uuid)

        ideas_count = notes_count
        
        # Tags count
        tags_count = await pg_conn.fetchval(
            "SELECT COUNT(DISTINCT tag) FROM (SELECT unnest(tags) as tag FROM notes WHERE user_id = $1) t", user_uuid
        )
        
        # Connections count (note_links + note tags)
        # Note -> Tag connections
        tag_connections = await pg_conn.fetchval(
            "SELECT COUNT(tag) FROM (SELECT unnest(tags) as tag FROM notes WHERE user_id = $1) t", user_uuid
        )
        # Idea -> Idea connections
        try:
            idea_connections = await pg_conn.fetchval(
                "SELECT COUNT(*) FROM note_links INNER JOIN notes ON notes.id = note_links.src_id WHERE notes.user_id = $1", user_uuid
            )
        except Exception:
            idea_connections = 0
            
        connections_count = (tag_connections or 0) + (idea_connections or 0)
        
        return SystemStats(
            total_notes=notes_count or 0,
            total_ideas=ideas_count,
            total_connections=connections_count,
            total_tags=tags_count,
            unique_users=unique_users or 0
        )
    
    @staticmethod
    async def _get_activity_metrics(pg_conn: asyncpg.Connection, user_id: str) -> ActivityMetrics:
        """Get recent activity metrics"""
        
        user_uuid = uuid.UUID(str(user_id))
        yesterday = datetime.utcnow() - timedelta(days=1)

        recent_notes = await pg_conn.fetchval(
            "SELECT COUNT(*) FROM notes WHERE user_id = $1 AND created_at > $2", user_uuid, yesterday
        )

        last_activity = await pg_conn.fetchval(
            "SELECT MAX(created_at) FROM notes WHERE user_id = $1", user_uuid
        )
        
        return ActivityMetrics(
            recent_notes=recent_notes or 0,
            recent_ideas=0,  # We'll enhance this later
            recent_searches=0,  # We'll track this later
            last_activity=last_activity
        )
    
    @staticmethod
    async def _get_tag_analytics(pg_conn: asyncpg.Connection, user_id: str) -> List[TagAnalytics]:
        """Get tag usage analytics"""
        
        user_uuid = uuid.UUID(str(user_id))
        total_notes = await pg_conn.fetchval("SELECT COUNT(*) FROM notes WHERE user_id = $1", user_uuid)
        if not total_notes:
            return []
            
        # Get tag frequencies (PostgreSQL array unnesting)
        tag_query = '''
            SELECT tag, COUNT(*) as count
            FROM (
                SELECT unnest(tags) as tag 
                FROM notes 
                WHERE user_id = $1 AND array_length(tags, 1) > 0
            ) t
            GROUP BY tag
            ORDER BY count DESC
            LIMIT 10
        '''
        
        rows = await pg_conn.fetch(tag_query, user_uuid)
        
        return [
            TagAnalytics(
                tag=row['tag'],
                count=row['count'],
                percentage=round((row['count'] / total_notes) * 100, 1)
            )
            for row in rows
        ]
    
    @staticmethod
    async def _get_database_health(
        pg_conn: asyncpg.Connection
    ) -> DatabaseHealth:
        """Get database health status"""
        
        # PostgreSQL health
        try:
            pg_size = await pg_conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )
            pg_status = "healthy"
        except Exception:
            pg_size = "unknown"
            pg_status = "error"
            
        neo4j_status = "removed"
        neo4j_size = "0 MB"
            
        return DatabaseHealth(
            postgres_status=pg_status,
            neo4j_status=neo4j_status,
            postgres_size=pg_size,
            neo4j_size=neo4j_size
        )
