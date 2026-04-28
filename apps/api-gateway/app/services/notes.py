import asyncpg
import uuid
import hashlib
import math
from typing import List, Optional
from app.schemas.notes import NoteCreate, NoteUpdate, NoteResponse

# Pure-Python hashing embedding — zero external dependencies, always works.
# Uses character n-gram + word-level hashing to produce a stable 384-dim vector.
_DIM = 384

def get_embedding(text: str) -> list:
    """Generate a stable 384-dim l2-normalized n-gram hashing embedding."""
    text = text.lower()[:1000]
    vec = [0.0] * _DIM
    tokens = text.split()
    # word unigrams + character trigrams for good coverage
    features = tokens + [text[i:i+3] for i in range(len(text) - 2)]
    for feat in features:
        digest = hashlib.md5(feat.encode()).digest()
        # use all 16 bytes to spread signal across dimensions
        for i in range(0, 16, 2):
            idx = ((digest[i] << 8) | digest[i + 1]) % _DIM
            sign = 1 if digest[i] & 1 else -1
            vec[idx] += sign
    # L2-normalize so cosine similarity works correctly
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

class NotesService:
    @staticmethod
    async def create_note(conn: asyncpg.Connection, user_id: uuid.UUID, note_data: NoteCreate) -> NoteResponse:
        # Generate embedding via HuggingFace API
        embedding = get_embedding(note_data.content)
        # HF API returns a plain list, no .tolist() needed
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # Simpler query without type casting
        query = '''
            INSERT INTO notes (user_id, content, tags, embedding)
            VALUES ($1, $2, $3, $4::vector)
            RETURNING id, user_id, content, tags, created_at
        '''
        row = await conn.fetchrow(
            query, 
            user_id, 
            note_data.content, 
            note_data.tags,
            embedding_str
        )
        
        # Note: Neo4j integration removed to reduce memory footprint
            
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
                   1 - (embedding <=> $1::vector) as similarity_score
            FROM notes 
            WHERE user_id = $2
            ORDER BY embedding <=> $1::vector
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
            updates.append(f"embedding = ${param_count}::vector")
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
        
        # Note: Neo4j integration removed

        return NoteResponse(
            id=row['id'],
            user_id=row['user_id'],
            content=row['content'],
            tags=row['tags'],
            created_at=row['created_at']
        )
    
    @staticmethod
    async def delete_note(conn: asyncpg.Connection, note_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a note"""
        query = '''
            DELETE FROM notes 
            WHERE id = $1 AND user_id = $2
            RETURNING id
        '''
        result = await conn.fetchrow(query, note_id, user_id)
        if result is not None:
            # Note: Neo4j integration removed
            return True
        return False