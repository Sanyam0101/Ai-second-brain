from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
import asyncpg
import uuid
from typing import List, Optional
from app.deps.database import get_db_connection
from app.deps.auth import get_current_user
from app.schemas.notes import NoteCreate, NoteUpdate, NoteResponse
from app.schemas.auth import UserResponse
from app.services.notes import NotesService
import io
import csv

router = APIRouter(prefix="/notes", tags=["notes"])

ALLOWED_EXTENSIONS = {'.pdf', '.csv', '.txt', '.md', '.docx'}

def extract_text_from_file(filename: str, content: bytes) -> str:
    """Extract text content from uploaded files"""
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    if ext == '.txt' or ext == '.md':
        return content.decode('utf-8', errors='replace')
    
    elif ext == '.csv':
        text_content = content.decode('utf-8', errors='replace')
        reader = csv.reader(io.StringIO(text_content))
        rows = []
        for row in reader:
            rows.append(' | '.join(row))
        return '\n'.join(rows)
    
    elif ext == '.pdf':
        try:
            import pdfplumber
            pdf = pdfplumber.open(io.BytesIO(content))
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            pdf.close()
            return text.strip() if text.strip() else f"[PDF file: {filename} - no extractable text]"
        except ImportError:
            return f"[PDF file: {filename} - pdfplumber not installed]"
    
    elif ext == '.docx':
        try:
            from docx import Document
            doc = Document(io.BytesIO(content))
            text = '\n'.join([p.text for p in doc.paragraphs])
            return text if text.strip() else f"[DOCX file: {filename} - no text]"
        except ImportError:
            return f"[DOCX file: {filename} - python-docx not installed]"
    
    return f"[Unsupported file: {filename}]"


@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note_data: NoteCreate,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Create a new note"""
    try:
        return await NotesService.create_note(conn, current_user.id, note_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error creating note: {str(e)}"
        )

@router.post("/upload", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def upload_file_as_note(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(""),
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Upload a file (PDF, CSV, TXT, MD, DOCX) and create a note from its content"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    ext = '.' + file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    extracted_text = extract_text_from_file(file.filename, content)

    # Truncate to 4000 chars to keep embedding generation within memory limits
    # on the free Render tier (512MB RAM)
    MAX_CHARS = 4000
    if len(extracted_text) > MAX_CHARS:
        extracted_text = extracted_text[:MAX_CHARS] + "\n\n[... content truncated for embedding ...]"

    # Auto-generate tags from file type
    tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
    tag_list.append(ext.replace('.', ''))  # Add file extension as tag
    tag_list.append('uploaded')
    tag_list = list(set(tag_list))

    # Prefix with filename for context
    full_content = f"📄 {file.filename}\n\n{extracted_text}"
    
    note_data = NoteCreate(content=full_content, tags=tag_list)
    
    try:
        return await NotesService.create_note(conn, current_user.id, note_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating note from file: {str(e)}"
        )

@router.get("/search", response_model=List[NoteResponse])
async def search_notes(
    q: str,
    limit: int = 10,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Semantic search notes"""
    try:
        return await NotesService.search_notes(conn, q, current_user.id, limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching notes: {str(e)}"
        )

@router.get("/", response_model=List[NoteResponse])
async def get_notes(
    limit: int = 50,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Get all notes for the current user"""
    try:
        return await NotesService.get_all_notes(conn, current_user.id, limit, offset)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching notes: {str(e)}"
        )

@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Get a single note by ID"""
    try:
        note = await NotesService.get_note_by_id(conn, note_id, current_user.id)
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found"
            )
        return note
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching note: {str(e)}"
        )

@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: uuid.UUID,
    note_data: NoteUpdate,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Update a note"""
    try:
        note = await NotesService.update_note(conn, note_id, current_user.id, note_data)
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found"
            )
        return note
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating note: {str(e)}"
        )

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Delete a note"""
    try:
        deleted = await NotesService.delete_note(conn, note_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting note: {str(e)}"
        )
