from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any
from app.deps.database import get_neo4j_session
from app.deps.auth import get_current_user
from app.schemas.auth import UserResponse
from app.schemas.graph import IdeaCreate, TagAdd, LinkIdeas

router = APIRouter(prefix="/graph", tags=["graph"])

@router.post("/idea")
async def create_idea(data: IdeaCreate, current_user: UserResponse = Depends(get_current_user), session = Depends(get_neo4j_session)):
    q = '''
    MERGE (i:Idea {id:$id})
    SET i.title = $title, i.user_id = $uid
    RETURN i.id AS id
    '''
    try:
        result = await session.run(q, id=data.id, title=data.title, uid=str(current_user.id))
        rec = await result.single()
        return {"id": rec["id"]}
    except Exception as e:
        raise HTTPException(500, f"Error creating idea: {e}")

@router.post("/tag")
async def add_tag(data: TagAdd, current_user: UserResponse = Depends(get_current_user), session = Depends(get_neo4j_session)):
    q = '''
    MATCH (i:Idea {id:$id, user_id:$uid})
    MERGE (t:Tag {name:$tag})
    MERGE (i)-[:TAGGED_WITH]->(t)
    RETURN i.id AS id, t.name AS tag
    '''
    try:
        result = await session.run(q, id=data.idea_id, tag=data.tag, uid=str(current_user.id))
        rec = await result.single()
        return {"id": rec["id"] if rec else None, "tag": rec["tag"] if rec else None}
    except Exception as e:
        raise HTTPException(500, f"Error tagging idea: {e}")

@router.post("/link")
async def link_ideas(data: LinkIdeas, current_user: UserResponse = Depends(get_current_user), session = Depends(get_neo4j_session)):
    q = '''
    MATCH (a:Idea {id:$src, user_id:$uid}), (b:Idea {id:$dst, user_id:$uid})
    MERGE (a)-[:LINKED_TO]->(b)
    RETURN a.id AS src, b.id AS dst
    '''
    try:
        result = await session.run(q, src=data.src_id, dst=data.dst_id, uid=str(current_user.id))
        rec = await result.single()
        return {"src": rec["src"] if rec else None, "dst": rec["dst"] if rec else None}
    except Exception as e:
        raise HTTPException(500, f"Error linking ideas: {e}")

@router.get("/neighbors")
async def neighbors(idea_id: str, depth: int = Query(2, ge=1, le=4), current_user: UserResponse = Depends(get_current_user), session = Depends(get_neo4j_session)):
    q = f"""
    MATCH (i:Idea {{id:$id, user_id:$uid}})-[:LINKED_TO|TAGGED_WITH*1..{depth}]-(n)
    WITH DISTINCT n
    RETURN labels(n) AS labels, n.id AS id LIMIT 100
    """
    try:
        result = await session.run(q, id=idea_id, uid=str(current_user.id))
        # Correct async consumption
        records = []
        async for record in result:
            records.append(dict(record))
        return {"count": len(records), "nodes": records}
    except Exception as e:
        raise HTTPException(500, f"Error reading neighbors: {e}")

@router.get("/shortest_path")
async def shortest_path(src_id: str, dst_id: str, current_user: UserResponse = Depends(get_current_user), session = Depends(get_neo4j_session)):
    q = '''
    MATCH (a:Idea {id:$src, user_id:$uid}), (b:Idea {id:$dst, user_id:$uid}),
          p = shortestPath((a)-[:LINKED_TO*..5]-(b))
    RETURN [n IN nodes(p) | n.id] AS path
    '''
    try:
        result = await session.run(q, src=src_id, dst=dst_id, uid=str(current_user.id))
        rec = await result.single()
        return {"path": rec["path"] if rec and rec["path"] is not None else []}
    except Exception as e:
        raise HTTPException(500, f"Error computing shortest path: {e}")

@router.get("/all")
async def get_all_graph(
    current_user: UserResponse = Depends(get_current_user),
    session = Depends(get_neo4j_session)
):
    """Fetch nodes and edges for frontend graph visualization"""
    try:
        # Fetch nodes
        nodes_result = await session.run(
            """
            MATCH (i:Idea {user_id: $uid})
            OPTIONAL MATCH (i)-[r]-(t:Tag)
            WITH collect(i) + collect(t) as raw_nodes
            UNWIND raw_nodes as n
            WITH DISTINCT n WHERE n IS NOT NULL
            RETURN id(n) as internal_id, labels(n)[0] as label,
                   n.id as id, n.title as title, n.name as name
            LIMIT 300
            """,
            uid=str(current_user.id)
        )
        nodes = []
        async for rec in nodes_result:
            nodes.append({
                "internal_id": rec["internal_id"],
                "label": rec["label"],
                "id": rec["id"],
                "title": rec["title"] or rec["name"]
            })

        # Fetch edges in a separate sequential call (not concurrent)
        edges_result = await session.run(
            """
            MATCH (a:Idea {user_id: $uid})-[r]-(b)
            RETURN id(a) as source, id(b) as target, type(r) as type
            LIMIT 500
            """,
            uid=str(current_user.id)
        )
        edges = []
        async for rec in edges_result:
            edges.append({
                "source": rec["source"],
                "target": rec["target"],
                "type": rec["type"]
            })

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        raise HTTPException(500, f"Error fetching graph data: {e}")
