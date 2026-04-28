from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any
import asyncpg
from app.deps.database import get_db_connection
from app.deps.auth import get_current_user
from app.schemas.auth import UserResponse
from app.schemas.graph import IdeaCreate, TagAdd, LinkIdeas

router = APIRouter(prefix="/graph", tags=["graph"])

@router.post("/idea")
async def create_idea(data: IdeaCreate, current_user: UserResponse = Depends(get_current_user), conn: asyncpg.Connection = Depends(get_db_connection)):
    # Handled by notes creation
    return {"id": data.id}

@router.post("/tag")
async def add_tag(data: TagAdd, current_user: UserResponse = Depends(get_current_user), conn: asyncpg.Connection = Depends(get_db_connection)):
    # Handled by notes creation
    return {"id": data.idea_id, "tag": data.tag}

@router.post("/link")
async def link_ideas(data: LinkIdeas, current_user: UserResponse = Depends(get_current_user), conn: asyncpg.Connection = Depends(get_db_connection)):
    try:
        query = '''
            INSERT INTO note_links (src_id, dst_id) 
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        '''
        await conn.execute(query, data.src_id, data.dst_id)
        return {"src": data.src_id, "dst": data.dst_id}
    except Exception as e:
        raise HTTPException(500, f"Error linking ideas: {e}")

@router.get("/neighbors")
async def neighbors(idea_id: str, depth: int = Query(2, ge=1, le=4), current_user: UserResponse = Depends(get_current_user), conn: asyncpg.Connection = Depends(get_db_connection)):
    # Placeholder for PostgreSQL graph traversal if needed by UI
    return {"count": 0, "nodes": []}

@router.get("/shortest_path")
async def shortest_path(src_id: str, dst_id: str, current_user: UserResponse = Depends(get_current_user), conn: asyncpg.Connection = Depends(get_db_connection)):
    # Placeholder for PostgreSQL graph traversal if needed by UI
    return {"path": []}

@router.get("/all")
async def get_all_graph(
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Fetch nodes and edges for frontend graph visualization"""
    try:
        nodes = []
        edges = []
        
        # Fetch all notes
        notes_records = await conn.fetch("SELECT id, content, tags, created_at FROM notes WHERE user_id = $1 LIMIT 500", current_user.id)
        
        tags_set = set()
        for r in notes_records:
            nid = str(r['id'])
            content = r['content'] or ''
            title = content[:50] + "..." if len(content) > 50 else content
            title = title or "Untitled Idea"
            
            nodes.append({
                "internal_id": nid,
                "label": "Idea",
                "id": nid,
                "title": title,
                "content": content,
                "created_at": r['created_at'].isoformat() if r['created_at'] else None
            })
            
            if r['tags']:
                for tag in r['tags']:
                    if not tag: continue
                    if tag not in tags_set:
                        tags_set.add(tag)
                        nodes.append({
                            "internal_id": tag,
                            "label": "Tag",
                            "id": tag,
                            "title": tag
                        })
                    
                    edges.append({
                        "source": nid,
                        "target": tag,
                        "type": "TAGGED_WITH"
                    })

        # Fetch explicit links
        links_records = await conn.fetch("SELECT src_id, dst_id FROM note_links INNER JOIN notes ON notes.id = note_links.src_id WHERE notes.user_id = $1 LIMIT 500", current_user.id)
        for r in links_records:
            edges.append({
                "source": str(r['src_id']),
                "target": str(r['dst_id']),
                "type": "LINKED_TO"
            })

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error fetching graph data: {e}")
