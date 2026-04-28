from fastapi import APIRouter, Depends, HTTPException
import asyncpg
from pydantic import BaseModel
from typing import List, Optional
from app.deps.database import get_db_connection
from app.deps.auth import get_current_user
from app.schemas.auth import UserResponse
from collections import Counter
import time
import re
# Reuse the same HuggingFace API embedding helper from notes service
from app.services.notes import get_embedding
from app.core.config import settings
import openai

router = APIRouter(prefix="/analyst", tags=["analyst"])

class AnalystQuery(BaseModel):
    query: str
    limit: int = 8

class ContextItem(BaseModel):
    content: str
    tags: List[str]
    similarity: Optional[float] = None

class AnalystResponse(BaseModel):
    query: str
    answer: str
    context_items: List[ContextItem]
    graph_connections: List[dict]
    processing_time_ms: float
    total_notes_scanned: int


def _classify_intent(query: str) -> str:
    """Classify the user's question intent"""
    q = query.lower().strip()
    if any(w in q for w in ['how many', 'count', 'total', 'number of']):
        return 'count'
    if any(w in q for w in ['list', 'show me', 'all my', 'what are', 'what do i have']):
        return 'list'
    if any(w in q for w in ['summarize', 'summary', 'overview', 'tell me about', 'explain']):
        return 'summary'
    if any(w in q for w in ['related', 'connected', 'link', 'connection', 'graph']):
        return 'graph'
    if any(w in q for w in ['tag', 'tagged', 'topic', 'category', 'categories']):
        return 'tags'
    if any(w in q for w in ['find', 'search', 'where', 'which', 'name', 'names']):
        return 'search'
    return 'general'


def _strip_markup(text: str) -> str:
    """Strip HTML tags, markdown images, and clean up whitespace"""
    text = re.sub(r'<[^>]+>', '', text)  # HTML tags
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # markdown images
    text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)  # markdown links -> text only
    text = re.sub(r'#{1,6}\s*', '', text)  # markdown headers
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)  # bold/italic
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_note_title(content: str) -> str:
    """Extract a clean title from note content"""
    # Remove emoji prefixes
    content = re.sub(r'^[📄📎🐙📝📁💡🏷]\s*', '', content.strip())
    
    # Common patterns
    patterns = [
        r'^GitHub Repo:\s*(.+?)(?:\n|$)',
        r'^README from\s*(.+?)(?:\n|$)',
        r'^Google (?:Drive|Doc)[:\s]*(.+?)(?:\n|$)',
        r'^Connected to\s*(.+?)(?:\n|$)',
        r'^DOCX file:\s*(.+?)(?:\n|$)',
        r'^PDF file:\s*(.+?)(?:\n|$)',
    ]
    for p in patterns:
        m = re.match(p, content, re.IGNORECASE)
        if m:
            return _strip_markup(m.group(1).strip()[:80])
    
    # First meaningful line  
    lines = [l.strip() for l in content.split('\n') if l.strip() and len(l.strip()) > 5]
    if lines:
        title = _strip_markup(lines[0])[:80]
        if len(title) > 80:
            title = title.rsplit(' ', 1)[0] + '…'
        return title
    return _strip_markup(content[:60])


def _get_note_summary(content: str, max_len: int = 200) -> str:
    """Extract a meaningful snippet/summary from content"""
    content = re.sub(r'^[📄📎🐙📝📁💡🏷]\s*', '', content.strip())
    # Skip title line, get body
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    body_lines = lines[1:] if len(lines) > 1 else lines
    body = ' '.join(body_lines)
    # Clean up - strip HTML and markdown
    body = _strip_markup(body)
    body = re.sub(r'\[.*?not installed\]', '', body)
    body = re.sub(r'URL:\s*https?://\S+', '', body)
    body = re.sub(r'https?://\S+', '', body)  # remove raw URLs
    body = re.sub(r'\s+', ' ', body).strip()
    if len(body) > max_len:
        body = body[:max_len].rsplit(' ', 1)[0] + '…'
    return body if body else '(No preview available)'


def _generate_smart_answer(query: str, contexts: list, graph_data: list, total_notes: int) -> str:
    """Generate well-structured markdown answers from semantic search + knowledge graph"""
    intent = _classify_intent(query)
    
    if not contexts and not graph_data:
        return (
            f"I searched your knowledge base ({total_notes} notes) for **\"{query}\"** "
            f"but couldn't find relevant content.\n\n"
            "**Suggestions:**\n"
            "- Add notes about this topic\n"
            "- Try different keywords\n"
            "- Upload related documents"
        )
    
    # Collect tag statistics
    all_tags = []
    for ctx in contexts:
        all_tags.extend(ctx.get('tags', []))
    tag_counts = Counter(all_tags)
    top_tags = tag_counts.most_common(8)
    
    # Relevance tiers
    high = [c for c in contexts if c.get('similarity', 0) > 0.5]
    medium = [c for c in contexts if 0.25 < c.get('similarity', 0) <= 0.5]
    low = [c for c in contexts if c.get('similarity', 0) <= 0.25]
    
    idea_nodes = [n for n in graph_data if n.get('label') == 'Idea']
    tag_nodes = [n for n in graph_data if n.get('label') == 'Tag']
    
    lines = []
    
    # === COUNT ===
    if intent == 'count':
        lines.append(f"📊 **Knowledge Base Stats**\n")
        lines.append(f"- **Total Notes:** {total_notes}")
        lines.append(f"- **Ideas in Graph:** {len(idea_nodes)}")
        lines.append(f"- **Tags:** {len(tag_nodes)}")
        if high:
            lines.append(f"- **Relevant to \"{query}\":** {len(high)}")
        lines.append("")
        if top_tags:
            lines.append("**Top topics:** " + ', '.join([f'`#{t}`' for t, _ in top_tags[:5]]))
    
    # === LIST ===
    elif intent == 'list':
        lines.append(f"📋 **Notes matching \"{query}\"**\n")
        for i, ctx in enumerate(contexts[:6], 1):
            title = _get_note_title(ctx['content'])
            score = ctx.get('similarity', 0)
            tags_str = ' '.join([f'`#{t}`' for t in ctx['tags'][:3]])
            badge = '🟢' if score > 0.5 else '🟡' if score > 0.25 else '🔵'
            lines.append(f"{badge} **{i}. {title}**")
            lines.append(f"   {tags_str} — {score:.0%} match\n")
    
    # === SEARCH / FIND ===
    elif intent == 'search':
        lines.append(f"🔍 **Search results for \"{query}\"**\n")
        
        if contexts:
            for i, ctx in enumerate(contexts[:5], 1):
                title = _get_note_title(ctx['content'])
                score = ctx.get('similarity', 0)
                summary = _get_note_summary(ctx['content'], 150)
                tags_str = ' '.join([f'`#{t}`' for t in ctx['tags'][:3]])
                
                lines.append(f"**{i}. {title}**")
                lines.append(f"> {summary}")
                lines.append(f"")
                lines.append(f"Tags: {tags_str} · Relevance: **{score:.0%}**\n")
        
        # Also show idea nodes from graph that might match
        if idea_nodes:
            matching_ideas = []
            q_words = set(query.lower().split())
            for node in idea_nodes:
                name = (node.get('title') or node.get('name') or '').lower()
                if any(w in name for w in q_words) or any(w in query.lower() for w in name.split() if len(w) > 3):
                    matching_ideas.append(node.get('title') or node.get('name'))
            
            if matching_ideas:
                lines.append("**Also found in Knowledge Graph:**")
                for idea in matching_ideas[:5]:
                    lines.append(f"- 💡 {idea}")
                lines.append("")
    
    # === TAGS ===
    elif intent == 'tags':
        lines.append(f"🏷️ **Topic Analysis**\n")
        if top_tags:
            for tag, count in top_tags:
                bar = '█' * min(count, 10)
                lines.append(f"- `#{tag}` — {count} note(s) {bar}")
        else:
            lines.append("No tags found.")
    
    # === GRAPH ===
    elif intent == 'graph':
        lines.append(f"🔗 **Knowledge Graph Overview**\n")
        lines.append(f"Your graph has **{len(idea_nodes)} ideas** connected via **{len(tag_nodes)} tags**.\n")
        
        if idea_nodes:
            lines.append("**Ideas:**")
            for idea in idea_nodes[:8]:
                name = idea.get('title') or idea.get('name', 'Untitled')
                lines.append(f"- 💡 {name}")
            lines.append("")
        
        if tag_nodes:
            tag_names = [t.get('title') or t.get('name', '') for t in tag_nodes[:10]]
            lines.append("**Tag cloud:** " + ' · '.join([f'`#{t}`' for t in tag_names if t]))
    
    # === SUMMARY ===
    elif intent == 'summary':
        lines.append(f"📖 **Summary: \"{query}\"**\n")
        relevant = high or medium or contexts[:3]
        
        for i, ctx in enumerate(relevant[:4], 1):
            title = _get_note_title(ctx['content'])
            summary = _get_note_summary(ctx['content'], 250)
            score = ctx.get('similarity', 0)
            tags_str = ' '.join([f'`#{t}`' for t in ctx['tags'][:3]])
            
            lines.append(f"**{i}. {title}** ({score:.0%} relevance)")
            lines.append(f"> {summary}\n")
            if tags_str:
                lines.append(f"Tags: {tags_str}\n")
        
        if top_tags:
            lines.append("**Key themes:** " + ', '.join([f'`#{t}`' for t, _ in top_tags[:5]]))
    
    # === GENERAL ===
    else:
        lines.append(f"🧠 **Results for \"{query}\"**\n")
        
        relevant = high or medium or contexts
        for i, ctx in enumerate(relevant[:4], 1):
            title = _get_note_title(ctx['content'])
            summary = _get_note_summary(ctx['content'], 180)
            score = ctx.get('similarity', 0)
            tags_str = ' '.join([f'`#{t}`' for t in ctx['tags'][:3]])
            
            lines.append(f"**{i}. {title}** — {score:.0%} match")
            lines.append(f"> {summary}")
            if tags_str:
                lines.append(f"> {tags_str}\n")
            else:
                lines.append("")
        
        if tag_nodes:
            tag_names = [t.get('title') or t.get('name', '') for t in tag_nodes if t.get('title') or t.get('name')]
            if tag_names:
                lines.append(f"**Connected topics:** {', '.join([f'`#{t}`' for t in tag_names[:6]])}")
    
    # Footer
    lines.append(f"\n---\n_Scanned {total_notes} notes · {len(contexts)} matches · {len(graph_data)} graph nodes_")
    
    return '\n'.join(lines)


@router.post("/ask", response_model=AnalystResponse)
async def ask_analyst(
    request: AnalystQuery,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Local AI Data Analyst — semantic vector search + knowledge graph + smart RAG"""
    start = time.time()
    
    # 1. Semantic vector search via HuggingFace API
    query_embedding = get_embedding(request.query)
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
    
    search_query = '''
        SELECT id, user_id, content, tags, created_at,
               1 - (embedding <=> $1) as similarity_score
        FROM notes 
        WHERE user_id = $2 AND embedding IS NOT NULL
        ORDER BY embedding <=> $1
        LIMIT $3
    '''
    rows = await conn.fetch(search_query, embedding_str, current_user.id, request.limit)
    
    contexts = []
    for row in rows:
        contexts.append({
            'content': row['content'],
            'tags': list(row['tags']) if row['tags'] else [],
            'similarity': float(row['similarity_score']) if row['similarity_score'] else 0.0
        })
    
    # 2. Knowledge graph traversal (using PostgreSQL tags)
    graph_nodes = []
    try:
        # Notes
        nodes_records = await conn.fetch("SELECT id, content, tags FROM notes WHERE user_id = $1 LIMIT 50", current_user.id)
        tags_set = set()
        for r in nodes_records:
            nid = str(r['id'])
            content = r['content'] or ''
            title = content[:50] + "..." if len(content) > 50 else content
            title = title or "Untitled Idea"
            graph_nodes.append({
                'internal_id': nid, 'label': 'Idea', 'id': nid, 'title': title
            })
            if r['tags']:
                for tag in r['tags']:
                    if not tag: continue
                    if tag not in tags_set:
                        tags_set.add(tag)
                        graph_nodes.append({
                            'internal_id': tag, 'label': 'Tag', 'id': tag, 'title': tag
                        })
    except Exception:
        pass

    # 3. Total notes count
    count_row = await conn.fetchrow(
        'SELECT count(*) as cnt FROM notes WHERE user_id = $1', current_user.id
    )
    total_notes = count_row['cnt'] if count_row else 0
    
    # 4. Generate smart local answer
    if settings.openai_api_key:
        try:
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            # Prepare context for LLM
            context_text = "\n".join([f"Note (Tags: {', '.join(c['tags'])}):\n{c['content']}" for c in contexts[:5]])
            graph_text = "\n".join([f"Related Node: {n['label']} - {n['title']}" for n in graph_nodes[:10]])
            
            prompt = f"""You are the user's AI Second Brain Data Analyst. Answer their query based primarily on the provided context notes and knowledge graph connections from their personal knowledge base.

User Query: "{request.query}"

Relevant Notes Context:
{context_text}

Related Knowledge Graph Nodes:
{graph_text}

Generate a concise, insightful markdown-formatted answer. If the context doesn't have the exact answer, summarize what is available and state what is missing."""
            
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": prompt}]
            )
            answer = response.choices[0].message.content
        except Exception as e:
            # Fallback to local heuristic generation if OpenAI fails
            answer = f"*Note: OpenAI integration failed ({str(e)}), using local analyzer fallback.*\n\n" + _generate_smart_answer(request.query, contexts, graph_nodes, total_notes)
    else:
        answer = _generate_smart_answer(request.query, contexts, graph_nodes, total_notes)
    
    processing_time = (time.time() - start) * 1000
    
    context_items = [
        ContextItem(
            content=c['content'][:400],
            tags=c['tags'],
            similarity=c.get('similarity')
        )
        for c in contexts
    ]
    
    return AnalystResponse(
        query=request.query,
        answer=answer,
        context_items=context_items,
        graph_connections=graph_nodes[:20],
        processing_time_ms=round(processing_time, 2),
        total_notes_scanned=total_notes
    )


@router.get("/stats")
async def analyst_stats(
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Get knowledge base statistics"""
    notes_count = await conn.fetchrow(
        'SELECT count(*) as cnt FROM notes WHERE user_id = $1', current_user.id
    )
    
    tags_row = await conn.fetchrow(
        "SELECT array_agg(DISTINCT tag) as all_tags FROM (SELECT unnest(tags) as tag FROM notes WHERE user_id = $1) sub",
        current_user.id
    )
    
    graph_stats = {'ideas': 0, 'tags': 0, 'connections': 0}
    try:
        ideas_count = notes_count['cnt'] if notes_count else 0
        tags_count = await conn.fetchval(
            "SELECT COUNT(DISTINCT tag) FROM (SELECT unnest(tags) as tag FROM notes WHERE user_id = $1) t", current_user.id
        )
        graph_stats['ideas'] = ideas_count
        graph_stats['tags'] = tags_count or 0
        graph_stats['connections'] = (tags_count or 0)
    except Exception:
        pass
    
    return {
        'total_notes': notes_count['cnt'] if notes_count else 0,
        'unique_tags': list(tags_row['all_tags']) if tags_row and tags_row['all_tags'] else [],
        'graph': graph_stats
    }
