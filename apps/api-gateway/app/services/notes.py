import asyncpg
import uuid
import os
import requests
from typing import List, Optional
from app.schemas.notes import NoteCreate, NoteUpdate, NoteResponse

# Embedding via HuggingFace Inference API — zero local memory, same 384-dim model.
# Optionally set HF_API_TOKEN env var for higher rate limits.
_HF_API_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

def get_embedding(text: str) -> list:
    """Call HuggingFace Inference API to get a 384-dim embedding vector."""
    headers = {}
    token = os.environ.get("HF_API_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.post(
        _HF_API_URL,
        headers=headers,
        json={"inputs": text[:512], "options": {"wait_for_model": True}},
        timeout=30
    )
    resp.raise_for_status()
    result = resp.json()
    # HF returns [[...]] for batch or [...] for single
    if isinstance(result[0], list):
        return result[0]
    return result

class NotesService:
    @staticmethod
    async def create_note(conn: asyncpg.Connection, neo4j_session, user_id: uuid.UUID, note_data: NoteCreate) -> NoteResponse:
        # Generate embedding via HuggingFace API
        embedding = get_embedding(note_data.content)
        # HF API returns a plain list, no .tolist() needed
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # Simpler query without type casting
        query = '''
            INSERT INTO notes (user_id, content, tags, embedding)
            VALUES ($1, $2, $3, $4)
            RETURNING id, user_id, content, tags, created_at
        '''
        row = await conn.fetchrow(
            query, 
            user_id, 
            note_data.content, 
            note_data.tags,
            embedding_str
        )
        
        # Sync to Neo4j
        note_id_str = str(row['id'])
        title = note_data.content[:40] + "..." if len(note_data.content) > 40 else note_data.content
        await neo4j_session.run('MERGE (i:Idea {id: $id}) SET i.title = $title, i.user_id = $uid', id=note_id_str, title=title, uid=str(user_id))
        
        for tag in note_data.tags:
            q_tag = '''
            MATCH (i:Idea {id:$id})
            MERGE (t:Tag {name:$tag})
            MERGE (i)-[:TAGGED_WITH]->(t)
            '''
            await neo4j_session.run(q_tag, id=note_id_str, tag=tag)
            
        return NoteResponse(
            id=row['id'],
            user_id=row['user_id'],
            content=row['content'],
            tags=row['tags'],
            created_at=row['created_at']
        )
    
    @staticmethod
    async def search_notes(conn: asyncpg.Connection, query_text: str, user_id: uuid.UUID, limit: int = 10) -> List[NoteResponse]:
        # Generate query embedding via HuggingFace API
        query_embedding = get_embedding(query_text)
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        # Search with cosine distance
        search_query = '''
            SELECT id, user_id, content, tags, created_at,
                   1 - (embedding <=> $1) as similarity_score
            FROM notes 
            WHERE user_id = $2
            ORDER BY embedding <=> $1
            LIMIT $3
        '''
        rows = await conn.fetch(search_query, embedding_str, user_id, limit)
        
        return [
            NoteResponse(
                id=row['id'],
                user_id=row['user_id'],
                content=row['content'],
                tags=row['tags'],
                created_at=row['created_at'],
                similarity_score=float(row['similarity_score']) if row['similarity_score'] else None
            )
            for row in rows
        ]
    
    @staticmethod
    async def get_all_notes(conn: asyncpg.Connection, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> List[NoteResponse]:
        query = '''
            SELECT id, user_id, content, tags, created_at
            FROM notes 
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        '''
        rows = await conn.fetch(query, user_id, limit, offset)
        
        return [
            NoteResponse(
                id=row['id'],
                user_id=row['user_id'],
                content=row['content'],
                tags=row['tags'],
                created_at=row['created_at']
            )
            for row in rows
        ]

    @staticmethod
    async def get_note_by_id(conn: asyncpg.Connection, note_id: uuid.UUID, user_id: uuid.UUID) -> Optional[NoteResponse]:
        """Get a single note by ID"""
        query = '''
            SELECT id, user_id, content, tags, created_at
            FROM notes 
            WHERE id = $1 AND user_id = $2
        '''
        row = await conn.fetchrow(query, note_id, user_id)
        
        if not row:
            return None
        
        return NoteResponse(
            id=row['id'],
            user_id=row['user_id'],
            content=row['content'],
            tags=row['tags'],
            created_at=row['created_at']
        )
    
    @staticmethod
    async def update_note(
        conn: asyncpg.Connection, 
        neo4j_session,
        note_id: uuid.UUID, 
        user_id: uuid.UUID, 
        note_data: NoteUpdate
    ) -> Optional[NoteResponse]:
        """Update a note"""
        # First check if note exists and belongs to user
        existing = await NotesService.get_note_by_id(conn, note_id, user_id)
        if not existing:
            return None
        
        # Build update query dynamically based on what's provided
        updates = []
        params = []
        param_count = 1
        
        if note_data.content is not None:
            # Generate new embedding via HuggingFace API
            embedding = get_embedding(note_data.content)
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            updates.append(f"content = ${param_count}")
            params.append(note_data.content)
            param_count += 1
            updates.append(f"embedding = ${param_count}")
            params.append(embedding_str)
            param_count += 1
        
        if note_data.tags is not None:
            updates.append(f"tags = ${param_count}")
            params.append(note_data.tags)
            param_count += 1
        
        if not updates:
            # Nothing to update
            return existing
        
        # Add note_id and user_id to params
        params.extend([note_id, user_id])
        
        query = f'''
            UPDATE notes 
            SET {', '.join(updates)}, updated_at = now()
            WHERE id = ${param_count} AND user_id = ${param_count + 1}
            RETURNING id, user_id, content, tags, created_at
        '''
        
        row = await conn.fetchrow(query, *params)
        
        if not row:
            return None
        
        if note_data.content is not None:
            # Update title in neo4j
            title = note_data.content[:40] + "..." if len(note_data.content) > 40 else note_data.content
            await neo4j_session.run('MATCH (i:Idea {id: $id}) SET i.title = $title', id=str(note_id), title=title)

        if note_data.tags is not None:
            # Rebuild tags
            q_clear_tags = 'MATCH (i:Idea {id:$id})-[r:TAGGED_WITH]->() DELETE r'
            await neo4j_session.run(q_clear_tags, id=str(note_id))
            for tag in note_data.tags:
                q_tag = '''
                MATCH (i:Idea {id:$id})
                MERGE (t:Tag {name:$tag})
                MERGE (i)-[:TAGGED_WITH]->(t)
                '''
                await neo4j_session.run(q_tag, id=str(note_id), tag=tag)

        return NoteResponse(
            id=row['id'],
            user_id=row['user_id'],
            content=row['content'],
            tags=row['tags'],
            created_at=row['created_at']
        )
    
    @staticmethod
    async def delete_note(conn: asyncpg.Connection, neo4j_session, note_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a note"""
        query = '''
            DELETE FROM notes 
            WHERE id = $1 AND user_id = $2
            RETURNING id
        '''
        result = await conn.fetchrow(query, note_id, user_id)
        if result is not None:
            # Delete from Neo4j
            await neo4j_session.run('MATCH (i:Idea {id:$id}) DETACH DELETE i', id=str(note_id))
            return True
        return False