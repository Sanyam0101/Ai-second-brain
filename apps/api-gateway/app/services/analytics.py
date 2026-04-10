import asyncpg
import uuid
from neo4j import AsyncSession
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
        neo4j_session: AsyncSession,
        user_id: str
    ) -> AnalyticsResponse:
        """Get comprehensive system analytics"""
        
        # Get PostgreSQL stats
        system_stats = await AnalyticsService._get_system_stats(pg_conn, neo4j_session, user_id)
        activity_metrics = await AnalyticsService._get_activity_metrics(pg_conn, user_id)
        top_tags = await AnalyticsService._get_tag_analytics(pg_conn, user_id)
        db_health = await AnalyticsService._get_database_health(pg_conn, neo4j_session)
        
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
        neo4j_session: AsyncSession,
        user_id: str
    ) -> SystemStats:
        """Get basic system statistics"""
        
        user_uuid = uuid.UUID(str(user_id))

        # PostgreSQL queries
        notes_count = await pg_conn.fetchval("SELECT COUNT(*) FROM notes WHERE user_id = $1", user_uuid)
        unique_users = await pg_conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM notes WHERE user_id = $1", user_uuid)

        # Neo4j queries — wrapped in try/except so a slow Neo4j doesn't crash analytics
        ideas_count = 0
        connections_count = 0
        tags_count = 0
        try:
            ideas_result = await neo4j_session.run("MATCH (i:Idea {user_id: $uid}) RETURN count(i) as count", uid=str(user_id))
            ideas_record = await ideas_result.single()
            ideas_count = ideas_record['count'] if ideas_record else 0

            connections_result = await neo4j_session.run("MATCH (a:Idea {user_id: $uid})-[r]->() RETURN count(r) as count", uid=str(user_id))
            connections_record = await connections_result.single()
            connections_count = connections_record['count'] if connections_record else 0

            tags_result = await neo4j_session.run("MATCH (i:Idea {user_id: $uid})-[:TAGGED_WITH]->(t:Tag) RETURN count(DISTINCT t) as count", uid=str(user_id))
            tags_record = await tags_result.single()
            tags_count = tags_record['count'] if tags_record else 0
        except Exception:
            pass
        
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
        pg_conn: asyncpg.Connection,
        neo4j_session: AsyncSession
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
            
        # Neo4j health
        try:
            neo4j_result = await neo4j_session.run("CALL dbms.components() YIELD name")
            await neo4j_result.consume()
            neo4j_status = "healthy"
            neo4j_size = "unknown"  # Neo4j size query is more complex
        except Exception:
            neo4j_status = "error" 
            neo4j_size = "unknown"
            
        return DatabaseHealth(
            postgres_status=pg_status,
            neo4j_status=neo4j_status,
            postgres_size=pg_size,
            neo4j_size=neo4j_size
        )
