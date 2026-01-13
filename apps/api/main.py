import os
import json
import re
import queue
import threading
import uuid
import shutil
from pathlib import Path
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse, FileResponse
from pydantic import BaseModel, Field, ValidationError
import asyncio

import chromadb
from openai import OpenAI

# Import LLM providers - try relative first, then absolute
try:
    from .llm_providers import get_provider
except ImportError:
    from llm_providers import get_provider

# Load .env from repo root when present (platform deploys typically inject env vars)
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client only if API key is available
# This allows the server to start even if the key is missing (will fail gracefully when used)
if OPENAI_API_KEY:
    oai = OpenAI(api_key=OPENAI_API_KEY)
else:
    # Create a dummy object that will raise a helpful error when used
    class MissingAPIKeyError:
        def __getattr__(self, name):
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please set it in Railway/Render settings (Settings → Variables → Add OPENAI_API_KEY)."
            )
    oai = MissingAPIKeyError()

CHROMA_DIR = os.getenv("CHROMA_DIR", str(ROOT / "storage" / "chroma"))
UPLOAD_DIR = ROOT / "storage" / "uploads"
DOCUMENTS_META_FILE = ROOT / "storage" / "documents_metadata.json"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ch = chromadb.PersistentClient(path=CHROMA_DIR)

# Document metadata storage
def load_documents_metadata() -> Dict:
    """Load document metadata from JSON file."""
    if DOCUMENTS_META_FILE.exists():
        try:
            with open(DOCUMENTS_META_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"documents": [], "active_document_id": None}
    return {"documents": [], "active_document_id": None}

def save_documents_metadata(metadata: Dict):
    """Save document metadata to JSON file."""
    DOCUMENTS_META_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DOCUMENTS_META_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def get_active_collection():
    """Get the ChromaDB collection for the active document."""
    meta = load_documents_metadata()
    active_id = meta.get("active_document_id")
    
    if active_id:
        # Check if document exists
        doc = next((d for d in meta.get("documents", []) if d["id"] == active_id), None)
        if doc and doc.get("status") == "processed":
            collection_name = f"doc_{active_id}"
            try:
                return ch.get_collection(name=collection_name)
            except:
                pass
    
    # Fallback to default collection - check if it exists and has content
    try:
        default_col = ch.get_collection(name="market_outlook")
        if default_col.count() > 0:
            return default_col
    except:
        pass
    
    # If no collection exists, raise an error
    raise HTTPException(status_code=404, detail="No active document available. Please upload a document first.")

# Initialize default collection if available, otherwise will be set on first use
try:
    col = get_active_collection()
except:
    col = None

# Initialize default document if collection exists but not in metadata
def initialize_default_document():
    """Check if default collection exists and create metadata entry if needed."""
    try:
        default_col = ch.get_collection(name="market_outlook")
        count = default_col.count()
        if count > 0:
            meta = load_documents_metadata()
            # Check if default document entry exists
            default_doc = next((d for d in meta.get("documents", []) if d.get("id") == "default"), None)
            if not default_doc:
                # Create default document entry
                default_doc = {
                    "id": "default",
                    "filename": "report.pdf",  # or detect from data folder
                    "uploaded_at": datetime.now().isoformat(),
                    "file_size": 0,  # Unknown for legacy document
                    "status": "processed",
                    "chunks": count,
                    "pages": 0  # Unknown for legacy document
                }
                if not meta.get("documents"):
                    meta["documents"] = []
                meta["documents"].append(default_doc)
                # Set as active if no active document
                if not meta.get("active_document_id"):
                    meta["active_document_id"] = "default"
                save_documents_metadata(meta)
                print(f"[INFO] Initialized default document with {count} chunks")
    except:
        pass  # Default collection doesn't exist, that's fine

# Try to initialize default document on startup
initialize_default_document()

app = FastAPI(title="Market Outlook RAG API")

# CORS: allow the Next.js frontend (localhost + Vercel). Provide a comma-separated
# list via ALLOWED_ORIGINS, e.g. "http://localhost:3000,https://your-app.vercel.app".
_default_origins = ["http://localhost:3000"]
_allowed = os.getenv("ALLOWED_ORIGINS")

if _allowed and _allowed.strip() == "*":
    allowed_origins = ["*"]
else:
    raw_origins = (
        [o.strip() for o in _allowed.split(",") if o.strip()] if _allowed else _default_origins
    )
    # Normalize: browsers send Origin without a trailing slash, and ensure no extra spaces
    allowed_origins = [o.rstrip("/").strip() for o in raw_origins if o.strip()]

# Debug: log allowed origins (remove in production if sensitive)
print(f"[CORS] Allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["*"],
    max_age=3600,
)

class ConversationTurn(BaseModel):
    question: str
    answer: str

class AskRequest(BaseModel):
    question: str
    top_k: int = Field(default=8, ge=1, le=20)
    provider: Optional[str] = Field(default="openai", description="LLM provider: 'openai' or 'together'")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for maintaining context")
    conversation_history: Optional[List[ConversationTurn]] = Field(default=[], description="Previous Q&A pairs for context")

class Citation(BaseModel):
    chunk_id: str
    page: int
    quote: str

class AskResponse(BaseModel):
    answer: str
    key_points: List[str]
    citations: List[Citation]
    not_found: bool
    provider: Optional[str] = None
    visual_data: Optional[Dict] = None  # Tables, charts, images from cited pages

class ComparisonResponse(BaseModel):
    question: str
    responses: List[AskResponse]

class SuggestedQuestionsRequest(BaseModel):
    conversation_history: Optional[List[ConversationTurn]] = Field(default=[], description="Previous Q&A pairs for context")
    last_answer: Optional[str] = Field(default=None, description="The most recent answer to generate follow-ups from")

class SuggestedQuestionsResponse(BaseModel):
    questions: List[str]

# --- Citation enforcement helpers ---
_NUM_TOKEN_RE = re.compile(r"(US\$\s?\d+(?:\.\d+)?\s?(?:billion|trillion)?)|(\$\s?\d+(?:\.\d+)?)|(\b\d+(?:\.\d+)?%\b)|(\b\d{4}\b)|(\b\d+(?:\.\d+)?\b)", re.IGNORECASE)


def _extract_numeric_tokens(text: str) -> List[str]:
    if not text:
        return []
    tokens: List[str] = []
    for m in _NUM_TOKEN_RE.finditer(text):
        tok = next((g for g in m.groups() if g), "")
        tok = tok.strip()
        if not tok:
            continue
        # Normalize whitespace (e.g., "US$ 130" -> "US$ 130")
        tok = re.sub(r"\s+", " ", tok)
        tokens.append(tok)
    # Deduplicate while preserving order
    seen = set()
    out: List[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _snippet_around(text: str, needle: str, window: int = 90) -> str:
    if not text or not needle:
        return ""
    idx = text.lower().find(needle.lower())
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(needle) + window)
    snippet = text[start:end].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    # Keep quotes short-ish
    if len(snippet) > 120:
        snippet = snippet[:117].rstrip() + "…"
    return snippet


def _get_visual_data_for_citations(citations: List[dict], metas: List[dict]) -> Optional[Dict]:
    """Retrieve visual data (tables, charts) for pages cited in the response."""
    if not citations:
        return None
    
    # Get unique pages from citations
    cited_pages = set()
    for citation in citations:
        if isinstance(citation, dict) and "page" in citation:
            cited_pages.add(citation["page"])
    
    if not cited_pages:
        return None
    
    # Get active document ID
    meta = load_documents_metadata()
    active_doc_id = meta.get("active_document_id")
    
    if not active_doc_id:
        # Try default document
        visual_data_file = ROOT / "storage" / "visual_data" / "default.json"
    else:
        visual_data_file = ROOT / "storage" / "visual_data" / f"{active_doc_id}.json"
    
    if not visual_data_file.exists():
        return None
    
    try:
        with open(visual_data_file, "r") as f:
            all_visual_data = json.load(f)
        
        # Extract visual data for cited pages
        result = {
            "tables": [],
            "charts": [],
            "images": []
        }
        
        for page_num in cited_pages:
            page_visual = all_visual_data.get(str(page_num), {})
            
            # Add tables
            for table in page_visual.get("tables", []):
                # Don't include base64 images in response (too large)
                # Just include table structure
                table_copy = {
                    "table_id": table.get("table_id"),
                    "page": table.get("page"),
                    "rows": table.get("rows", [])[:20],  # Limit rows for response size
                    "row_count": table.get("row_count"),
                    "col_count": table.get("col_count")
                }
                result["tables"].append(table_copy)
            
            # Add chart analyses
            for chart in page_visual.get("chart_analyses", []):
                chart_copy = {
                    "page": chart.get("page"),
                    "analysis": chart.get("analysis", {}),
                    "model": chart.get("model")
                }
                result["charts"].append(chart_copy)
        
        # Only return if we have visual data
        if result["tables"] or result["charts"] or result["images"]:
            return result
    except Exception as e:
        print(f"[WARN] Failed to load visual data: {e}")
    
    return None


def _ensure_numeric_citations(data: dict, docs: List[str], metas: List[dict]) -> dict:
    """Ensure every numeric token in answer/key_points is backed by at least one citation.

    Strategy:
    - If the number appears in any already-cited chunk, it's covered.
    - If it's present in retrieved chunks but not cited, add a citation automatically.
    - If it's not present in retrieved chunks at all, we do NOT fabricate a citation.
    """
    answer_text = (data.get("answer") or "")
    key_points = data.get("key_points") or []
    kp_text = "\n".join([kp for kp in key_points if isinstance(kp, str)])
    all_text = f"{answer_text}\n{kp_text}"

    tokens = _extract_numeric_tokens(all_text)
    if not tokens:
        return data

    citations = data.get("citations") if isinstance(data.get("citations"), list) else []

    # Build lookup: chunk_id -> (page, doc_text)
    chunk_lookup = {m["chunk_id"]: (m["page"], d) for d, m in zip(docs, metas)}

    # Which chunks are already cited?
    cited_chunk_ids = set()
    for c in citations:
        if isinstance(c, dict) and c.get("chunk_id") in chunk_lookup:
            cited_chunk_ids.add(c.get("chunk_id"))

    def token_is_covered(tok: str) -> bool:
        for cid in cited_chunk_ids:
            _, txt = chunk_lookup[cid]
            if tok.lower() in txt.lower():
                return True
        return False

    # Add citations for uncovered tokens that exist in retrieved docs
    for tok in tokens:
        if token_is_covered(tok):
            continue

        # Find a retrieved chunk that contains the token
        found_cid = None
        for cid, (pg, txt) in chunk_lookup.items():
            if tok.lower() in txt.lower():
                found_cid = cid
                break

        if not found_cid:
            # Token not present in retrieved context; leave it (LLM may be wrong).
            # Frontend can surface this via missing-citation behavior, or you can choose to hard-fail.
            continue

        pg, txt = chunk_lookup[found_cid]
        snippet = _snippet_around(txt, tok)
        citations.append({
            "chunk_id": found_cid,
            "page": pg,
            "quote": snippet or f"Contains reference to {tok}",
        })
        cited_chunk_ids.add(found_cid)

    data["citations"] = citations
    return data

@app.get("/health")
def health():
    """Health check with collection stats."""
    try:
        active_col = get_active_collection()
        count = active_col.count()
        
        if count == 0:
            return {
                "status": "ok",
                "chroma_dir": CHROMA_DIR,
                "allowed_origins": allowed_origins,
                "allowed_origins_env": os.getenv("ALLOWED_ORIGINS"),
                "collection_count": 0,
                "pages_in_index": [],
                "page_range": "none",
                "total_pages_indexed": 0,
                "message": "No documents indexed yet. Please upload a document."
            }
        
        # Get all documents to see complete page range (may be slow for large indexes)
        all_results = active_col.get(limit=count)
        pages_in_index = set()
        if all_results.get("metadatas"):
            for meta in all_results["metadatas"]:
                if "page" in meta:
                    pages_in_index.add(meta["page"])
        
        return {
            "status": "ok",
            "chroma_dir": CHROMA_DIR,
            "allowed_origins": allowed_origins,
            "allowed_origins_env": os.getenv("ALLOWED_ORIGINS"),
            "collection_count": count,
            "pages_in_index": sorted(list(pages_in_index)) if pages_in_index else [],
            "page_range": f"{min(pages_in_index)}-{max(pages_in_index)}" if pages_in_index else "none",
            "total_pages_indexed": len(pages_in_index),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "ok",
            "chroma_dir": CHROMA_DIR,
            "allowed_origins": allowed_origins,
            "allowed_origins_env": os.getenv("ALLOWED_ORIGINS"),
            "collection_count": 0,
            "pages_in_index": [],
            "page_range": "none",
            "total_pages_indexed": 0,
            "message": "No active document available. Please upload a document first.",
            "error": str(e)
        }

def process_document(pdf_path: str, doc_id: str, use_vision: bool = False) -> dict:
    """Process a PDF document and create a ChromaDB collection for it.
    
    Args:
        pdf_path: Path to the PDF file
        doc_id: Document ID
        use_vision: Whether to use GPT-4 Vision for chart analysis (slower, more expensive)
    """
    try:
        # Import ingestion modules
        try:
            from ingestion.pdf_parse import extract_pages
            from ingestion.chunking import chunk_text
            from ingestion.visual_extraction import (
                extract_visual_data_from_pdf,
                format_table_as_text,
                format_chart_analysis_as_text
            )
        except ImportError:
            import sys
            sys.path.insert(0, str(ROOT))
            from ingestion.pdf_parse import extract_pages
            from ingestion.chunking import chunk_text
            from ingestion.visual_extraction import (
                extract_visual_data_from_pdf,
                format_table_as_text,
                format_chart_analysis_as_text
            )
        
        # Extract pages
        pages = extract_pages(pdf_path)
        
        # Create collection for this document
        collection_name = f"doc_{doc_id}"
        try:
            ch.delete_collection(collection_name)
        except:
            pass
        col = ch.get_or_create_collection(name=collection_name)
        
        # Process and embed chunks with visual data
        BATCH_DOCS = 32
        pending_ids, pending_docs, pending_metas = [], [], []
        total_chunks = 0
        total_tables = 0
        total_charts = 0
        
        for p in pages:
            page_num = p["page"]
            
            # Extract visual data for this page
            visual_data = extract_visual_data_from_pdf(
                pdf_path, 
                page_num, 
                use_vision=use_vision,
                api_key=OPENAI_API_KEY if use_vision else None
            )
            
            # Count visual elements
            total_tables += len(visual_data.get("tables", []))
            total_charts += len(visual_data.get("chart_analyses", []))
            
            # Enhance text with visual data
            page_text = p["text"]
            
            # Add table text to page content
            for table in visual_data.get("tables", []):
                table_text = format_table_as_text(table)
                if table_text:
                    page_text += "\n\n" + table_text
            
            # Add chart analysis text to page content
            for chart in visual_data.get("chart_analyses", []):
                chart_text = format_chart_analysis_as_text(chart)
                if chart_text:
                    page_text += "\n\n" + chart_text
            
            # Chunk the enhanced text
            chunks = chunk_text(page_text, max_chars=1200, overlap=200)
            
            for j, chunk in enumerate(chunks):
                cid = f"p{page_num}_c{j:03d}"
                pending_ids.append(cid)
                pending_docs.append(chunk)
                
                # Enhanced metadata with visual data info
                # Note: ChromaDB metadata only supports primitive types (str, int, float, bool, None)
                # Lists must be converted to strings or removed
                meta = {
                    "page": page_num,
                    "chunk_id": cid,
                    "has_tables": len(visual_data.get("tables", [])) > 0,
                    "has_charts": len(visual_data.get("chart_analyses", [])) > 0,
                    "table_count": len(visual_data.get("tables", []))
                }
                
                # Store visual data references as comma-separated strings (ChromaDB doesn't support lists)
                if visual_data.get("tables"):
                    table_ids = [t["table_id"] for t in visual_data["tables"]]
                    meta["table_ids"] = ",".join(table_ids)  # Convert list to comma-separated string
                if visual_data.get("chart_analyses"):
                    chart_ids = [f"p{page_num}_chart{i}" for i in range(len(visual_data["chart_analyses"]))]
                    meta["chart_ids"] = ",".join(chart_ids)  # Convert list to comma-separated string
                
                pending_metas.append(meta)
                
                if len(pending_docs) >= BATCH_DOCS:
                    resp = oai.embeddings.create(
                        model="text-embedding-3-small",
                        input=pending_docs,
                    )
                    embeddings = [x.embedding for x in resp.data]
                    col.add(
                        ids=pending_ids,
                        documents=pending_docs,
                        metadatas=pending_metas,
                        embeddings=embeddings,
                    )
                    total_chunks += len(pending_docs)
                    pending_ids, pending_docs, pending_metas = [], [], []
        
        # Flush remainder
        if pending_docs:
            resp = oai.embeddings.create(
                model="text-embedding-3-small",
                input=pending_docs,
            )
            embeddings = [x.embedding for x in resp.data]
            col.add(ids=pending_ids, documents=pending_docs, metadatas=pending_metas, embeddings=embeddings)
            total_chunks += len(pending_docs)
        
        # Store visual data separately for retrieval
        visual_data_file = ROOT / "storage" / "visual_data" / f"{doc_id}.json"
        visual_data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Collect all visual data by page
        all_visual_data = {}
        for p in pages:
            page_num = p["page"]
            visual_data = extract_visual_data_from_pdf(
                pdf_path,
                page_num,
                use_vision=use_vision,
                api_key=OPENAI_API_KEY if use_vision else None
            )
            all_visual_data[page_num] = visual_data
        
        with open(visual_data_file, "w") as f:
            json.dump(all_visual_data, f, indent=2)
        
        return {
            "success": True,
            "total_chunks": total_chunks,
            "total_pages": len(pages),
            "total_tables": total_tables,
            "total_charts": total_charts
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/documents")
def list_documents():
    """List all uploaded documents."""
    meta = load_documents_metadata()
    return {
        "documents": meta.get("documents", []),
        "active_document_id": meta.get("active_document_id")
    }

@app.get("/documents/{doc_id}/pdf")
def get_document_pdf(doc_id: str):
    """Serve a document's PDF file."""
    # Check if it's the default document first
    if doc_id == "default":
        default_pdf = ROOT / "data" / "report.pdf"
        if default_pdf.exists():
            meta = load_documents_metadata()
            documents = meta.get("documents", [])
            doc = next((d for d in documents if d.get("id") == doc_id), None)
            return FileResponse(
                path=str(default_pdf),
                media_type="application/pdf",
                filename=doc.get("filename", "report.pdf") if doc else "report.pdf"
            )
        raise HTTPException(status_code=404, detail="Default PDF not found")
    
    # Check if uploaded PDF exists first (more reliable than metadata check)
    pdf_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if pdf_path.exists():
        meta = load_documents_metadata()
        documents = meta.get("documents", [])
        doc = next((d for d in documents if d.get("id") == doc_id), None)
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=doc.get("filename", "document.pdf") if doc else "document.pdf"
        )
    
    # If PDF file doesn't exist, check metadata
    meta = load_documents_metadata()
    documents = meta.get("documents", [])
    doc = next((d for d in documents if d.get("id") == doc_id), None)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    raise HTTPException(status_code=404, detail="PDF file not found")

@app.get("/documents/active/pdf")
def get_active_document_pdf():
    """Serve the active document's PDF file."""
    meta = load_documents_metadata()
    active_id = meta.get("active_document_id")
    
    if not active_id:
        # Fallback to default PDF if no active document
        default_pdf = ROOT / "data" / "report.pdf"
        if default_pdf.exists():
            return FileResponse(
                path=str(default_pdf),
                media_type="application/pdf",
                filename="report.pdf"
            )
        raise HTTPException(status_code=404, detail="No active document and no default PDF found")
    
    # Handle default document
    if active_id == "default":
        default_pdf = ROOT / "data" / "report.pdf"
        if default_pdf.exists():
            return FileResponse(
                path=str(default_pdf),
                media_type="application/pdf",
                filename="report.pdf"
            )
        raise HTTPException(status_code=404, detail="Default PDF not found")
    
    # Check if uploaded PDF exists
    pdf_path = UPLOAD_DIR / f"{active_id}.pdf"
    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        documents = meta.get("documents", [])
        doc = next((d for d in documents if d.get("id") == active_id), None)
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=doc.get("filename", "document.pdf") if doc else "document.pdf"
        )
    
    # If PDF doesn't exist, log and try to serve default as fallback
    print(f"[WARN] Uploaded PDF not found at {pdf_path} for active_id {active_id}, falling back to default PDF")
    default_pdf = ROOT / "data" / "report.pdf"
    if default_pdf.exists():
        return FileResponse(
            path=str(default_pdf),
            media_type="application/pdf",
            filename="report.pdf"
        )
    
    raise HTTPException(status_code=404, detail=f"PDF file not found for active document {active_id}")

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a PDF document."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Generate document ID
    doc_id = str(uuid.uuid4())
    filename = file.filename
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    
    # Save uploaded file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Get file size
    file_size = file_path.stat().st_size
    
    # Load metadata
    meta = load_documents_metadata()
    documents = meta.get("documents", [])
    
    # Add document entry
    doc_entry = {
        "id": doc_id,
        "filename": filename,
        "uploaded_at": datetime.now().isoformat(),
        "file_size": file_size,
        "status": "processing",
        "chunks": 0,
        "pages": 0
    }
    documents.append(doc_entry)
    
    # Always make newly uploaded document active (overrides default if it exists)
    meta["active_document_id"] = doc_id
    
    meta["documents"] = documents
    save_documents_metadata(meta)
    
    # Process document asynchronously
    def process_async():
        # Enable vision analysis (set to False to disable and save costs)
        # Vision analysis uses GPT-4 Vision API which is more expensive
        use_vision = os.getenv("ENABLE_VISION_ANALYSIS", "false").lower() == "true"
        result = process_document(str(file_path), doc_id, use_vision=use_vision)
        meta = load_documents_metadata()
        documents = meta.get("documents", [])
        doc = next((d for d in documents if d["id"] == doc_id), None)
        if doc:
            if result["success"]:
                doc["status"] = "processed"
                doc["chunks"] = result["total_chunks"]
                doc["pages"] = result["total_pages"]
            else:
                doc["status"] = "error"
                doc["error"] = result.get("error", "Unknown error")
        meta["documents"] = documents
        save_documents_metadata(meta)
    
    # Start processing in background thread
    thread = threading.Thread(target=process_async)
    thread.daemon = True
    thread.start()
    
    return {
        "id": doc_id,
        "filename": filename,
        "status": "processing",
        "message": "Document uploaded. Processing in background."
    }

@app.post("/documents/{doc_id}/activate")
def activate_document(doc_id: str):
    """Set a document as the active document for queries."""
    meta = load_documents_metadata()
    documents = meta.get("documents", [])
    doc = next((d for d in documents if d["id"] == doc_id), None)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.get("status") != "processed":
        raise HTTPException(status_code=400, detail="Document is not yet processed")
    
    meta["active_document_id"] = doc_id
    save_documents_metadata(meta)
    
    # Reload collection
    global col
    col = get_active_collection()
    
    return {
        "message": f"Document '{doc['filename']}' is now active",
        "active_document_id": doc_id
    }

@app.get("/documents/{doc_id}/visual/{page_num}")
def get_document_visual_data(doc_id: str, page_num: int):
    """Get visual data (tables, charts) for a specific page of a document."""
    visual_data_file = ROOT / "storage" / "visual_data" / f"{doc_id}.json"
    
    if not visual_data_file.exists():
        raise HTTPException(status_code=404, detail="Visual data not found for this document")
    
    try:
        with open(visual_data_file, "r") as f:
            all_visual_data = json.load(f)
        
        page_visual = all_visual_data.get(str(page_num), {})
        
        if not page_visual:
            return {
                "page": page_num,
                "tables": [],
                "charts": [],
                "images": []
            }
        
        # Return visual data (limit table rows for response size)
        result = {
            "page": page_num,
            "tables": [],
            "charts": page_visual.get("chart_analyses", []),
            "images": []
        }
        
        # Limit table rows to prevent huge responses
        for table in page_visual.get("tables", []):
            table_copy = {
                "table_id": table.get("table_id"),
                "page": table.get("page"),
                "rows": table.get("rows", [])[:50],  # Limit to 50 rows
                "row_count": table.get("row_count"),
                "col_count": table.get("col_count")
            }
            result["tables"].append(table_copy)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading visual data: {str(e)}")

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete a document and its collection."""
    meta = load_documents_metadata()
    documents = meta.get("documents", [])
    doc = next((d for d in documents if d["id"] == doc_id), None)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove from list
    documents = [d for d in documents if d["id"] != doc_id]
    meta["documents"] = documents
    
    # If it was active, set another document as active (or None)
    if meta.get("active_document_id") == doc_id:
        if documents:
            # Find first processed document
            processed = next((d for d in documents if d.get("status") == "processed"), None)
            meta["active_document_id"] = processed["id"] if processed else None
        else:
            meta["active_document_id"] = None
    
    save_documents_metadata(meta)
    
    # Delete collection
    try:
        collection_name = f"doc_{doc_id}"
        ch.delete_collection(collection_name)
    except:
        pass
    
    # Delete file
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if file_path.exists():
        file_path.unlink()
    
    # Reload collection if needed
    global col
    col = get_active_collection()
    
    return {"message": f"Document '{doc['filename']}' deleted"}

@app.options("/ask")
@app.options("/api/ask")
async def options_ask():
    """Handle preflight OPTIONS requests - CORS middleware should handle this, but this ensures it works"""
    # Return empty 200 - CORS middleware will add the headers
    return Response(status_code=200)

def _generate_response(question: str, top_k: int, provider_name: str, docs: List[str], metas: List[dict], conversation_history: Optional[List[ConversationTurn]] = None) -> AskResponse:
    """Generate a response using the specified provider."""
    context_blocks = []
    for d, m in zip(docs, metas):
        context_blocks.append(f"[{m['chunk_id']} | page {m['page']}]\n{d}")

    # System prompt (strict grounding + JSON output)
    system = (
        "You are a senior investment analyst at a venture capital firm. "
        "Answer questions using ONLY the provided report excerpts. "

        "IMPORTANT: Your answer can paraphrase and synthesize information naturally. "
        "The 'answer' field can paraphrase or synthesize for readability, but every factual claim must be grounded in citations. "
        "Citations are required to show sources - the 'quote' field can be a brief summary or reference to the relevant content, not necessarily an exact quote. "

        "Write in a crisp, investor-ready style with analytical depth. "
        "Imagine the reader is an experienced investor who is familiar with the report and the industry. "
        "The 'answer' should be structured to: lead with the main finding, provide reasoning and causal drivers, "
        "include concrete specifics (numbers, trends, mechanisms), and synthesize across excerpts when relevant. "
        "Aim for 3–6 sentences that balance conciseness with depth. "
        "Avoid vague filler (e.g., 'significantly', 'rapidly') unless the context uses it. "

        "The 'key_points' should complement the answer with discrete, actionable insights. "

        "CRITICAL CITATION REQUIREMENTS: "
        "You MUST provide citations ONLY in the 'citations' field — never inside the prose of the 'answer' or 'key_points'. "
        "The 'answer' and 'key_points' must read cleanly with NO inline citations, page references, or chunk IDs. "

        "Every factual claim, statistic, or specific detail in the answer MUST still be backed by a citation, "
        "but those citations must appear exclusively in the 'citations' array. "

        "If multiple facts are used, include multiple citation objects — one per fact — in the 'citations' array. "
        "Do NOT include citations in parentheses or inline text. "

        "The 'citations' field must still include: chunk_id, page, and a short quote or summary. "
        "You MUST ground every factual claim in the provided context. "
        "If synthesizing across multiple excerpts, do so explicitly (e.g., 'Across excerpts A and B...'). "
        "If the report does NOT clearly contain the answer, set not_found=true and say you cannot find it in the report. "
        "Do NOT infer, estimate, or use outside knowledge. "
        "Return ONLY valid JSON matching the provided schema, and ALWAYS include all four top-level keys: "
        "answer, key_points, citations, not_found. "
    )

    # Build conversation context if available
    conversation_context = ""
    if conversation_history and len(conversation_history) > 0:
        conversation_context = "\n\nPrevious conversation:\n"
        for i, turn in enumerate(conversation_history[-3:], 1):  # Include last 3 turns
            conversation_context += f"Q{i}: {turn.question}\n"
            conversation_context += f"A{i}: {turn.answer}\n\n"
        conversation_context += "---\n\n"
        conversation_context += "Current question (you may reference previous answers if relevant):\n"

    user = (
        f"{conversation_context}Question: {question}\n\n"
        "Context:\n" + "\n\n".join(context_blocks) + "\n\n"
        "Schema:\n"
        "{"
        "\"answer\": string, "
        "\"key_points\": array of strings, "
        "\"citations\": array of {\"chunk_id\": string, \"page\": number, \"quote\": string}, "
        "\"not_found\": boolean"
        "}\n\n"
        "Constraints:\n"
        "- quote can be a brief summary or reference (<= 25 words) - does NOT need to be exact quote\n"
        "- chunk_id must match EXACTLY a chunk_id shown in the Context blocks above\n"
        "- page number must match EXACTLY the page number shown for that chunk_id in Context\n"
        "- citations must reference only chunk_ids and pages shown in Context\n"
        "- CRITICAL: Every number, statistic, specific fact, or claim in your answer MUST have a citation\n"
        "- If your answer mentions multiple facts from different chunks, include multiple citations (one per fact)\n"
        "- If not_found=true, citations should be an empty array\n"
        "- answer must be 3-6 sentences with structure: main finding → reasoning → specifics\n"
        "- answer should synthesize key_points with analytical depth, not just list facts\n"
    )

    # Get LLM provider
    try:
        provider = get_provider(provider_name)
    except Exception as e:
        print(f"[ERROR] Failed to get provider {provider_name}: {e}")
        return AskResponse(
            answer=f"Error: Could not initialize {provider_name} provider. {str(e)}",
            key_points=["Please check your API keys in .env file."],
            citations=[],
            not_found=True,
            provider=provider_name,
            visual_data=None,
        )

    # Generate response
    try:
        raw = provider.generate(
            system_prompt=system,
            user_prompt=user,
            temperature=0.0,
            max_tokens=2048,
        )
    except Exception as e:
        print(f"[ERROR] Provider {provider_name} generation failed: {e}")
        return AskResponse(
            answer=f"Error generating response from {provider_name}: {str(e)}",
            key_points=["Please check your API keys and try again."],
            citations=[],
            not_found=True,
            provider=provider_name,
            visual_data=None,
        )

    # Parse + validate JSON
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"[ERROR] Failed to parse JSON from {provider_name}: {e}")
        return AskResponse(
            answer="I could not format a valid JSON response.",
            key_points=["Try re-asking the question."],
            citations=[],
            not_found=True,
            provider=provider_name,
            visual_data=None,
        )

    # Validate citations
    if "citations" in data and isinstance(data["citations"], list):
        chunk_lookup = {}
        for d, m in zip(docs, metas):
            chunk_lookup[m["chunk_id"]] = (m["page"], d)
        
        validated_citations = []
        for cit in data["citations"]:
            if not isinstance(cit, dict):
                continue
            chunk_id = cit.get("chunk_id")
            page = cit.get("page")
            
            if chunk_id in chunk_lookup:
                expected_page, _ = chunk_lookup[chunk_id]
                if page == expected_page:
                    validated_citations.append(cit)
                else:
                    print(f"[WARN] Page mismatch for chunk_id {chunk_id}: expected {expected_page}, got {page}")
            else:
                print(f"[WARN] Invalid chunk_id in citation: {chunk_id}")
        
        data["citations"] = validated_citations

    # Ensure numeric citations
    try:
        data = _ensure_numeric_citations(data, docs, metas)
    except Exception as e:
        print(f"[WARN] Numeric citation enforcement failed: {e}")

    data["provider"] = provider.get_provider_name()
    
    # Retrieve visual data for cited pages
    visual_data = _get_visual_data_for_citations(data.get("citations", []), metas)
    if visual_data:
        data["visual_data"] = visual_data

    try:
        return AskResponse(**data)
    except ValidationError as e:
        print(f"[ERROR] Response validation failed: {e}")
        return AskResponse(
            answer="I could not produce a valid structured response for this question.",
            key_points=["Try re-asking the question with a narrower scope."],
            citations=[],
            not_found=True,
            provider=provider_name,
            visual_data=None,
        )


@app.post("/ask", response_model=AskResponse)
@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    # 1) Embed query
    q_emb = oai.embeddings.create(
        model="text-embedding-3-small",
        input=req.question
    ).data[0].embedding

    # 2) Retrieve chunks
    active_col = get_active_collection()
    results = active_col.query(
        query_embeddings=[q_emb],
        n_results=req.top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    # Debug: log retrieved pages
    retrieved_pages = [m["page"] for m in metas]
    unique_pages = sorted(set(retrieved_pages))
    print(f"[DEBUG] Retrieved {len(docs)} chunks from pages: {unique_pages}")
    if retrieved_pages:
        print(f"[DEBUG] Retrieved page range: {min(retrieved_pages)} - {max(retrieved_pages)}")

    # 3) Generate response using specified provider
    return _generate_response(req.question, req.top_k, req.provider, docs, metas, req.conversation_history)


def _stream_generator(question: str, top_k: int, provider_name: str, docs: List[str], metas: List[dict], conversation_history: Optional[List[ConversationTurn]] = None):
    """Generator function for streaming responses via SSE."""
    try:
        # Build context blocks
        context_blocks = []
        for d, m in zip(docs, metas):
            context_blocks.append(f"[{m['chunk_id']} | page {m['page']}]\n{d}")

        # Build conversation context if available
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_context = "\n\nPrevious conversation:\n"
            for i, turn in enumerate(conversation_history[-3:], 1):  # Include last 3 turns
                conversation_context += f"Q{i}: {turn.question}\n"
                conversation_context += f"A{i}: {turn.answer}\n\n"
            conversation_context += "---\n\n"
            conversation_context += "Current question (you may reference previous answers if relevant):\n"

        # System and user prompts (same as _generate_response)
        system = (
            "You are a senior investment analyst at a venture capital firm. "
            "Answer questions using ONLY the provided report excerpts. "

            "IMPORTANT: Your answer can paraphrase and synthesize information naturally. "
            "The 'answer' field can paraphrase or synthesize for readability, but every factual claim must be grounded in citations. "
            "Citations are required to show sources - the 'quote' field can be a brief summary or reference to the relevant content, not necessarily an exact quote. "

            "Write in a crisp, investor-ready style with analytical depth. "
            "Imagine the reader is an experienced investor who is familiar with the report and the industry. "
            "The 'answer' should be structured to: lead with the main finding, provide reasoning and causal drivers, "
            "include concrete specifics (numbers, trends, mechanisms), and synthesize across excerpts when relevant. "
            "Aim for 3–6 sentences that balance conciseness with depth. "
            "Avoid vague filler (e.g., 'significantly', 'rapidly') unless the context uses it. "

            "The 'key_points' should complement the answer with discrete, actionable insights. "

            "CRITICAL CITATION REQUIREMENTS: "
            "You MUST provide citations ONLY in the 'citations' field — never inside the prose of the 'answer' or 'key_points'. "
            "The 'answer' and 'key_points' must read cleanly with NO inline citations, page references, or chunk IDs. "

            "Every factual claim, statistic, or specific detail in the answer MUST still be backed by a citation, "
            "but those citations must appear exclusively in the 'citations' array. "

            "If multiple facts are used, include multiple citation objects — one per fact — in the 'citations' array. "
            "Do NOT include citations in parentheses or inline text. "

            "The 'citations' field must still include: chunk_id, page, and a short quote or summary. "
            "You MUST ground every factual claim in the provided context. "
            "If synthesizing across multiple excerpts, do so explicitly (e.g., 'Across excerpts A and B...'). "
            "If the report does NOT clearly contain the answer, set not_found=true and say you cannot find it in the report. "
            "Do NOT infer, estimate, or use outside knowledge. "
            "Return ONLY valid JSON matching the provided schema, and ALWAYS include all four top-level keys: "
            "answer, key_points, citations, not_found. "
        )

        user = (
            f"{conversation_context}Question: {question}\n\n"
            "Context:\n" + "\n\n".join(context_blocks) + "\n\n"
            "Schema:\n"
            "{"
            "\"answer\": string, "
            "\"key_points\": array of strings, "
            "\"citations\": array of {\"chunk_id\": string, \"page\": number, \"quote\": string}, "
            "\"not_found\": boolean"
            "}\n\n"
            "Constraints:\n"
            "- quote can be a brief summary or reference (<= 25 words) - does NOT need to be exact quote\n"
            "- chunk_id must match EXACTLY a chunk_id shown in the Context blocks above\n"
            "- page number must match EXACTLY the page number shown for that chunk_id in Context\n"
            "- citations must reference only chunk_ids and pages shown in Context\n"
            "- CRITICAL: Every number, statistic, specific fact, or claim in your answer MUST have a citation\n"
            "- If your answer mentions multiple facts from different chunks, include multiple citations (one per fact)\n"
            "- If not_found=true, citations should be an empty array\n"
            "- answer must be 3-6 sentences with structure: main finding → reasoning → specifics\n"
            "- answer should synthesize key_points with analytical depth, not just list facts\n"
        )

        # Get provider
        provider = get_provider(provider_name)
        
        # Stream response
        accumulated_text = ""
        for chunk in provider.generate_stream(system, user, temperature=0.0, max_tokens=2048):
            accumulated_text += chunk
            # Send chunk as SSE event (escape newlines in JSON)
            chunk_data = json.dumps({'type': 'chunk', 'content': chunk})
            yield f"data: {chunk_data}\n\n"

        # Parse complete JSON
        try:
            data = json.loads(accumulated_text)
        except json.JSONDecodeError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to parse JSON response'})}\n\n"
            return

        # Validate citations
        if "citations" in data and isinstance(data["citations"], list):
            chunk_lookup = {}
            for d, m in zip(docs, metas):
                chunk_lookup[m["chunk_id"]] = (m["page"], d)
            
            validated_citations = []
            for cit in data["citations"]:
                if not isinstance(cit, dict):
                    continue
                chunk_id = cit.get("chunk_id")
                page = cit.get("page")
                
                if chunk_id in chunk_lookup:
                    expected_page, _ = chunk_lookup[chunk_id]
                    if page == expected_page:
                        validated_citations.append(cit)
            
            data["citations"] = validated_citations

        # Ensure numeric citations
        try:
            data = _ensure_numeric_citations(data, docs, metas)
        except Exception as e:
            print(f"[WARN] Numeric citation enforcement failed: {e}")

        data["provider"] = provider.get_provider_name()

        # Send final structured response
        try:
            response = AskResponse(**data)
            yield f"data: {json.dumps({'type': 'complete', 'response': response.model_dump()})}\n\n"
        except ValidationError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Response validation failed'})}\n\n"

    except Exception as e:
        print(f"[ERROR] Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.post("/ask/stream")
@app.post("/api/ask/stream")
def ask_stream(req: AskRequest):
    """Stream response using Server-Sent Events (SSE)."""
    # 1) Embed query
    q_emb = oai.embeddings.create(
        model="text-embedding-3-small",
        input=req.question
    ).data[0].embedding

    # 2) Retrieve chunks
    active_col = get_active_collection()
    results = active_col.query(
        query_embeddings=[q_emb],
        n_results=req.top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    # Debug: log retrieved pages
    retrieved_pages = [m["page"] for m in metas]
    unique_pages = sorted(set(retrieved_pages))
    print(f"[DEBUG] Retrieved {len(docs)} chunks from pages: {unique_pages}")

    return StreamingResponse(
        _stream_generator(req.question, req.top_k, req.provider, docs, metas, req.conversation_history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


def _stream_compare_generator(question: str, top_k: int, docs: List[str], metas: List[dict]):
    """Generator function for streaming comparison responses via SSE."""
    providers = ["openai", "together"]
    provider_responses = {p: {"accumulated": "", "complete": False, "response": None} for p in providers}
    
    def stream_provider_sync(provider_name: str, event_queue: queue.Queue):
        """Stream a single provider's response synchronously, putting events in queue."""
        try:
            context_blocks = []
            for d, m in zip(docs, metas):
                context_blocks.append(f"[{m['chunk_id']} | page {m['page']}]\n{d}")

            system = (
                "You are a senior investment analyst at a venture capital firm. "
                "Answer questions using ONLY the provided report excerpts. "

                "IMPORTANT: Your answer can paraphrase and synthesize information naturally. "
                "The 'answer' field can paraphrase or synthesize for readability, but every factual claim must be grounded in citations. "
                "Citations are required to show sources - the 'quote' field can be a brief summary or reference to the relevant content, not necessarily an exact quote. "

                "Write in a crisp, investor-ready style with analytical depth. "
                "Imagine the reader is an experienced investor who is familiar with the report and the industry. "
                "The 'answer' should be structured to: lead with the main finding, provide reasoning and causal drivers, "
                "include concrete specifics (numbers, trends, mechanisms), and synthesize across excerpts when relevant. "
                "Aim for 3–6 sentences that balance conciseness with depth. "
                "Avoid vague filler (e.g., 'significantly', 'rapidly') unless the context uses it. "

                "The 'key_points' should complement the answer with discrete, actionable insights. "

                "CRITICAL CITATION REQUIREMENTS: "
                "You MUST provide citations ONLY in the 'citations' field — never inside the prose of the 'answer' or 'key_points'. "
                "The 'answer' and 'key_points' must read cleanly with NO inline citations, page references, or chunk IDs. "

                "Every factual claim, statistic, or specific detail in the answer MUST still be backed by a citation, "
                "but those citations must appear exclusively in the 'citations' array. "

                "If multiple facts are used, include multiple citation objects — one per fact — in the 'citations' array. "
                "Do NOT include citations in parentheses or inline text. "

                "The 'citations' field must still include: chunk_id, page, and a short quote or summary. "
                "You MUST ground every factual claim in the provided context. "
                "If synthesizing across multiple excerpts, do so explicitly (e.g., 'Across excerpts A and B...'). "
                "If the report does NOT clearly contain the answer, set not_found=true and say you cannot find it in the report. "
                "Do NOT infer, estimate, or use outside knowledge. "
                "Return ONLY valid JSON matching the provided schema, and ALWAYS include all four top-level keys: "
                "answer, key_points, citations, not_found. "
            )

            # Build conversation context if available (for comparison, we'll use empty history for now)
            # Could be enhanced to support conversation history in comparison mode
            conversation_context = ""
            
            user = (
                f"{conversation_context}Question: {question}\n\n"
                "Context:\n" + "\n\n".join(context_blocks) + "\n\n"
                "Schema:\n"
                "{"
                "\"answer\": string, "
                "\"key_points\": array of strings, "
                "\"citations\": array of {\"chunk_id\": string, \"page\": number, \"quote\": string}, "
                "\"not_found\": boolean"
                "}\n\n"
                "Constraints:\n"
                "- quote can be a brief summary or reference (<= 25 words) - does NOT need to be exact quote\n"
                "- chunk_id must match EXACTLY a chunk_id shown in the Context blocks above\n"
                "- page number must match EXACTLY the page number shown for that chunk_id in Context\n"
                "- citations must reference only chunk_ids and pages shown in Context\n"
                "- CRITICAL: Every number, statistic, specific fact, or claim in your answer MUST have a citation\n"
                "- If your answer mentions multiple facts from different chunks, include multiple citations (one per fact)\n"
                "- If not_found=true, citations should be an empty array\n"
                "- answer must be 3-6 sentences with structure: main finding → reasoning → specifics\n"
                "- answer should synthesize key_points with analytical depth, not just list facts\n"
            )

            provider = get_provider(provider_name)
            accumulated_text = ""
            
            for chunk in provider.generate_stream(system, user, temperature=0.0, max_tokens=2048):
                accumulated_text += chunk
                provider_responses[provider_name]["accumulated"] = accumulated_text
                # Put chunk in queue with provider identifier
                event_queue.put(f"data: {json.dumps({'type': 'chunk', 'provider': provider_name, 'content': chunk})}\n\n")

            # Parse and validate
            try:
                data = json.loads(accumulated_text)
                
                # Validate citations
                if "citations" in data and isinstance(data["citations"], list):
                    chunk_lookup = {}
                    for d, m in zip(docs, metas):
                        chunk_lookup[m["chunk_id"]] = (m["page"], d)
                    
                    validated_citations = []
                    for cit in data["citations"]:
                        if isinstance(cit, dict) and cit.get("chunk_id") in chunk_lookup:
                            expected_page, _ = chunk_lookup[cit.get("chunk_id")]
                            if cit.get("page") == expected_page:
                                validated_citations.append(cit)
                    data["citations"] = validated_citations

                # Ensure numeric citations
                try:
                    data = _ensure_numeric_citations(data, docs, metas)
                except Exception:
                    pass

                data["provider"] = provider.get_provider_name()
                response = AskResponse(**data)
                provider_responses[provider_name]["response"] = response
                provider_responses[provider_name]["complete"] = True
                
                # Put completion event in queue
                event_queue.put(f"data: {json.dumps({'type': 'provider_complete', 'provider': provider_name, 'response': response.model_dump()})}\n\n")
                
            except Exception as e:
                print(f"[ERROR] Failed to process {provider_name} response: {e}")
                import traceback
                traceback.print_exc()
                error_response = AskResponse(
                    answer=f"Error: {str(e)}",
                    key_points=["Provider error"],
                    citations=[],
                    not_found=True,
                    provider=provider_name,
                )
                provider_responses[provider_name]["response"] = error_response
                provider_responses[provider_name]["complete"] = True
                event_queue.put(f"data: {json.dumps({'type': 'provider_complete', 'provider': provider_name, 'response': error_response.model_dump()})}\n\n")
        
        except Exception as e:
            print(f"[ERROR] Streaming error for {provider_name}: {e}")
            import traceback
            traceback.print_exc()
            error_response = AskResponse(
                answer=f"Error: {str(e)}",
                key_points=["Streaming error"],
                citations=[],
                not_found=True,
                provider=provider_name,
            )
            provider_responses[provider_name]["response"] = error_response
            provider_responses[provider_name]["complete"] = True
            event_queue.put(f"data: {json.dumps({'type': 'provider_complete', 'provider': provider_name, 'response': error_response.model_dump()})}\n\n")

    # Stream both providers in parallel using threads
    q = queue.Queue()
    stop_event = threading.Event()
    
    def run_stream(provider_name):
        try:
            stream_provider_sync(provider_name, q)
        except Exception as e:
            print(f"[ERROR] Stream error for {provider_name}: {e}")
            import traceback
            traceback.print_exc()
            error_response = AskResponse(
                answer=f"Error: {str(e)}",
                key_points=["Streaming error"],
                citations=[],
                not_found=True,
                provider=provider_name,
            )
            q.put(f"data: {json.dumps({'type': 'provider_complete', 'provider': provider_name, 'response': error_response.model_dump()})}\n\n")
    
    # Start streaming both providers in separate threads
    threads = []
    for provider in providers:
        t = threading.Thread(target=run_stream, args=(provider,), daemon=True)
        t.start()
        threads.append(t)
    
    # Yield events as they come in
    completed = 0
    try:
        while completed < len(providers):
            try:
                event = q.get(timeout=2.0)
                yield event
                # Check if it's a completion event
                if event.startswith("data: "):
                    try:
                        data = json.loads(event[6:])
                        if data.get("type") == "provider_complete":
                            completed += 1
                    except Exception as e:
                        print(f"[WARN] Failed to parse event: {e}")
            except queue.Empty:
                # Check if threads are still alive
                if all(not t.is_alive() for t in threads):
                    # All threads finished, break
                    break
                continue
    finally:
        stop_event.set()
        # Wait for threads to finish
        for t in threads:
            t.join(timeout=1.0)
    
    # Send final comparison response
    responses = [provider_responses[p]["response"] for p in providers if provider_responses[p]["response"]]
    if responses:
        yield f"data: {json.dumps({'type': 'complete', 'question': question, 'responses': [r.model_dump() for r in responses]})}\n\n"


@app.post("/ask/compare/stream")
@app.post("/api/ask/compare/stream")
def ask_compare_stream(req: AskRequest):
    """Stream comparison responses from multiple providers via SSE."""
    try:
        # 1) Embed query
        q_emb = oai.embeddings.create(
            model="text-embedding-3-small",
            input=req.question
        ).data[0].embedding

        # 2) Retrieve chunks
        active_col = get_active_collection()
        results = active_col.query(
            query_embeddings=[q_emb],
            n_results=req.top_k,
            include=["documents", "metadatas", "distances"]
        )

        docs = results["documents"][0]
        metas = results["metadatas"][0]

        # Debug: log retrieved pages
        retrieved_pages = [m["page"] for m in metas]
        unique_pages = sorted(set(retrieved_pages))
        print(f"[DEBUG] Retrieved {len(docs)} chunks from pages: {unique_pages}")

        return StreamingResponse(
            _stream_compare_generator(req.question, req.top_k, docs, metas),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    except Exception as e:
        print(f"[ERROR] ask_compare_stream error: {e}")
        import traceback
        traceback.print_exc()
        # Return error as SSE
        def error_generator():
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )


@app.post("/ask/compare", response_model=ComparisonResponse)
@app.post("/api/ask/compare", response_model=ComparisonResponse)
def ask_compare(req: AskRequest):
    """Compare responses from multiple providers."""
    # 1) Embed query
    q_emb = oai.embeddings.create(
        model="text-embedding-3-small",
        input=req.question
    ).data[0].embedding

    # 2) Retrieve chunks
    active_col = get_active_collection()
    results = active_col.query(
        query_embeddings=[q_emb],
        n_results=req.top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    # Debug: log retrieved pages
    retrieved_pages = [m["page"] for m in metas]
    unique_pages = sorted(set(retrieved_pages))
    print(f"[DEBUG] Retrieved {len(docs)} chunks from pages: {unique_pages}")

    # 3) Generate responses from both providers in parallel
    providers = ["openai", "together"]
    
    def generate_for_provider(provider_name: str) -> AskResponse:
        try:
            return _generate_response(req.question, req.top_k, provider_name, docs, metas, req.conversation_history)
        except Exception as e:
            print(f"[ERROR] Failed to generate response for {provider_name}: {e}")
            return AskResponse(
                answer=f"Error: {str(e)}",
                key_points=["Provider error"],
                citations=[],
                not_found=True,
                provider=provider_name,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(generate_for_provider, providers))

    return ComparisonResponse(question=req.question, responses=responses)


@app.post("/suggest-questions", response_model=SuggestedQuestionsResponse)
@app.post("/api/suggest-questions", response_model=SuggestedQuestionsResponse)
def suggest_questions(req: SuggestedQuestionsRequest):
    """Generate contextual follow-up questions based on conversation history or document content."""
    
    # If no conversation history, generate questions based on document content
    if not req.conversation_history or len(req.conversation_history) == 0:
        try:
            # Get active collection
            active_col = get_active_collection()
            
            if active_col.count() == 0:
                # Return generic questions if collection is empty
                return SuggestedQuestionsResponse(questions=[
                    "What are the main topics covered in this document?",
                    "What are the key findings or conclusions?",
                    "What are the important statistics or data points mentioned?",
                    "What recommendations or insights are provided?",
                ])
            
            # Retrieve diverse chunks from the document to understand its content
            # Use a general query to get representative content
            try:
                # Get random chunks from different parts of the document
                all_results = active_col.get(limit=min(20, active_col.count()))
                docs = all_results.get("documents", [])
                metas = all_results.get("metadatas", [])
                
                if not docs:
                    raise ValueError("No documents in collection")
                
                # Sample diverse chunks
                sample_size = min(10, len(docs))
                step = max(1, len(docs) // sample_size)
                sampled_docs = docs[::step][:sample_size]
                sampled_text = "\n\n".join([f"[Page {metas[i*step]['page']}] {doc[:300]}" for i, doc in enumerate(sampled_docs) if i*step < len(metas)])
                
                # Generate questions based on document content using LLM
                provider = get_provider("openai")
                
                system_prompt = (
                    "You are a helpful assistant that generates relevant questions for a document Q&A system. "
                    "Based on the provided document excerpts, generate 4 concise, specific questions that would help users "
                    "understand and explore the document's content. "
                    "Questions should: "
                    "- Be specific and answerable from the document "
                    "- Cover different important topics in the document "
                    "- Be natural and conversational "
                    "- Help users get started exploring the document "
                    "\n\nReturn ONLY a JSON array of exactly 4 question strings, no other text."
                )
                
                user_prompt = f"Document excerpts:\n\n{sampled_text}\n\nGenerate 4 questions:"
                
                try:
                    response_text = provider.generate(system_prompt, user_prompt)
                    # Extract JSON array from response
                    import re
                    json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                    if json_match:
                        questions_json = json.loads(json_match.group())
                        if isinstance(questions_json, list) and len(questions_json) >= 4:
                            return SuggestedQuestionsResponse(questions=questions_json[:4])
                except Exception as e:
                    print(f"[WARN] Failed to generate questions from document: {e}")
                
                # Fallback: generate questions from key topics
                # Use a summary query to identify topics
                topics_query = "What are the main topics, themes, and key subjects discussed in this document?"
                topics_emb = oai.embeddings.create(
                    model="text-embedding-3-small",
                    input=topics_query
                ).data[0].embedding
                
                topics_results = active_col.query(
                    query_embeddings=[topics_emb],
                    n_results=8,
                    include=["documents", "metadatas"]
                )
                
                topics_docs = topics_results["documents"][0]
                topics_text = "\n\n".join([doc[:200] for doc in topics_docs[:5]])
                
                user_prompt = f"Based on these document excerpts:\n\n{topics_text}\n\nGenerate 4 specific questions users might ask:"
                
                response_text = provider.generate(system_prompt, user_prompt)
                json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                if json_match:
                    questions_json = json.loads(json_match.group())
                    if isinstance(questions_json, list) and len(questions_json) >= 4:
                        return SuggestedQuestionsResponse(questions=questions_json[:4])
                
                # Final fallback
                return SuggestedQuestionsResponse(questions=[
                    "What are the main topics covered in this document?",
                    "What are the key findings or conclusions?",
                    "What important data or statistics are mentioned?",
                    "What recommendations or next steps are provided?",
                ])
                
            except Exception as e:
                print(f"[WARN] Error generating document-based questions: {e}")
                # Fallback to generic questions
                return SuggestedQuestionsResponse(questions=[
                    "What are the main topics covered in this document?",
                    "What are the key findings or conclusions?",
                    "What are the important statistics or data points mentioned?",
                    "What recommendations or insights are provided?",
                ])
        except HTTPException:
            raise
        except Exception as e:
            print(f"[WARN] Error in suggest_questions: {e}")
            # Return generic questions on error
            return SuggestedQuestionsResponse(questions=[
                "What are the main topics covered in this document?",
                "What are the key findings or conclusions?",
                "What are the important statistics or data points mentioned?",
                "What recommendations or insights are provided?",
            ])
    
    # Generate contextual follow-up questions using LLM
    try:
        # Get the last Q&A pair for context
        last_turn = req.conversation_history[-1]
        context = f"Previous question: {last_turn.question}\nPrevious answer: {last_turn.answer[:500]}"  # Limit answer length
        
        # If there are more turns, include them
        if len(req.conversation_history) > 1:
            context += "\n\nEarlier conversation:\n"
            for turn in req.conversation_history[-3:-1]:  # Last 2 before the most recent
                context += f"Q: {turn.question}\nA: {turn.answer[:200]}\n\n"
        
        system_prompt = (
            "You are a helpful assistant that generates relevant follow-up questions for a document Q&A system. "
            "Based on the conversation history, generate 4 concise, specific follow-up questions that would help the user "
            "dive deeper into the topics discussed. "
            "Questions should be: "
            "- Specific and actionable (not vague like 'tell me more') "
            "- Grounded in the previous answers (reference specific topics mentioned) "
            "- Varied (cover different aspects: details, risks, comparisons, implications) "
            "- Investor-focused and analytical "
            "Return ONLY a JSON array of exactly 4 question strings, no other text."
        )
        
        user_prompt = (
            f"{context}\n\n"
            "Generate 4 follow-up questions that would help explore this topic further. "
            "Return as JSON array: [\"question1\", \"question2\", \"question3\", \"question4\"]"
        )
        
        # Use OpenAI for question generation (fast and reliable)
        provider = get_provider("openai")
        response_text = provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,  # Slightly more creative for question generation
            max_tokens=300
        )
        
        # Try to extract JSON array
        try:
            # Look for JSON array in response
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            if json_match:
                questions = json.loads(json_match.group())
                if isinstance(questions, list) and len(questions) >= 4:
                    return SuggestedQuestionsResponse(questions=questions[:4])
        except:
            pass
        
        # Fallback: try to extract questions from text
        questions = []
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and ('?' in line or line.startswith('"') or line.startswith("'")):
                # Clean up the line
                line = line.strip('"\'[]').strip()
                if line and len(line) > 10 and '?' in line:
                    questions.append(line)
                    if len(questions) >= 4:
                        break
        
        if len(questions) >= 4:
            return SuggestedQuestionsResponse(questions=questions[:4])
        else:
            # Fallback to default if generation fails
            return SuggestedQuestionsResponse(questions=default_questions)
            
    except Exception as e:
        print(f"[ERROR] Failed to generate suggested questions: {e}")
        # Fallback to default questions on error
        return SuggestedQuestionsResponse(questions=default_questions)