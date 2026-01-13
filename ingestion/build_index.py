import os
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from openai import OpenAI
import json
import sys
import time
from fastapi.middleware.cors import CORSMiddleware

# #region agent log
# Write logs to a safe location in any environment (override via MOA_LOG_PATH if desired)
_DEFAULT_LOG = Path(os.getenv("TMPDIR", "/tmp")) / "market_outlook_debug.log"
LOG_PATH = os.getenv("MOA_LOG_PATH", str(_DEFAULT_LOG))
try:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "ALL", "location": "build_index.py:import", "message": "Module imported", "data": {}, "timestamp": int(time.time() * 1000)}) + "\n")
except: pass
# #endregion

from ingestion.pdf_parse import extract_pages
from ingestion.chunking import chunk_text
from ingestion.visual_extraction import (
    extract_visual_data_from_pdf,
    format_table_as_text,
    format_chart_analysis_as_text
)

# #region agent log
try:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "ALL", "location": "build_index.py:import_done", "message": "All imports complete", "data": {}, "timestamp": int(time.time() * 1000)}) + "\n")
except: pass
# #endregion

def main():
    # #region agent log
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "ALL", "location": "build_index.py:17", "message": "main entry", "data": {}, "timestamp": int(time.time() * 1000)}) + "\n")
    except: pass
    # #endregion
    ROOT = Path(__file__).resolve().parents[1]
    # #region agent log
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "ALL", "location": "build_index.py:22", "message": "ROOT path resolved", "data": {"root": str(ROOT)}, "timestamp": int(time.time() * 1000)}) + "\n")
    except: pass
    # #endregion
    # In production (e.g., Render), env vars are typically injected by the platform.
    # Locally, you may have a ROOT/.env file.
    load_dotenv(ROOT / ".env", override=False)
    # #region agent log
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "ALL", "location": "build_index.py:25", "message": "dotenv loaded", "data": {}, "timestamp": int(time.time() * 1000)}) + "\n")
    except: pass
    # #endregion

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in .env")

    oai = OpenAI(api_key=api_key)

    # ---- PDF path (adjust if you didn't rename)
    pdf_path = ROOT / "data" / "report.pdf"
    if not pdf_path.exists():
        # fallback to your original filename
        pdf_path = ROOT / "data" / "2026 BlackRock Private Markets Outlook.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"Could not find PDF in data/. Looked for {pdf_path}")

    # #region agent log
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "build_index.py:45", "message": "Before extract_pages", "data": {"pdf_path": str(pdf_path)}, "timestamp": int(time.time() * 1000)}) + "\n")
    except: pass
    # #endregion
    
    try:
        pages = extract_pages(str(pdf_path))
        # #region agent log
        try:
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "build_index.py:50", "message": "Pages extracted", "data": {"num_pages": len(pages)}, "timestamp": int(time.time() * 1000)}) + "\n")
        except: pass 
        # #endregion
    except Exception as e:
        # #region agent log
        try:
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "build_index.py:55", "message": "extract_pages failed", "data": {"error": str(e), "error_type": type(e).__name__}, "timestamp": int(time.time() * 1000)}) + "\n")
        except: pass
        # #endregion
        raise

    # ---- Chroma persistent storage
    # Allow override for production deploys (e.g., CHROMA_DIR=/app/storage/chroma)
    chroma_dir = os.getenv("CHROMA_DIR")
    persist_dir = Path(chroma_dir) if chroma_dir else (ROOT / "storage" / "chroma")
    persist_dir.mkdir(parents=True, exist_ok=True)
    ch = chromadb.PersistentClient(path=str(persist_dir))

    # repeatable builds
    try:
        ch.delete_collection("market_outlook")
    except Exception:
        pass
    col = ch.get_or_create_collection(name="market_outlook")

    # ---- Stream chunks -> embed -> add (no huge RAM)
    BATCH_DOCS = 32  # smaller = safer
    pending_ids, pending_docs, pending_metas = [], [], []

    total_chunks = 0
    page_count = 0
    all_visual_data = {}  # Store visual data by page
    
    for p in pages:
        page_count += 1
        page_num = p["page"]
        # #region agent log
        try:
            if page_count % 5 == 0 or page_count == 1:
                with open(LOG_PATH, "a") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "build_index.py:70", "message": "Processing page in loop", "data": {"page_num": page_num, "page_count": page_count, "pending_docs_len": len(pending_docs), "total_chunks": total_chunks}, "timestamp": int(time.time() * 1000)}) + "\n")
        except: pass
        # #endregion
        
        # Extract visual data for this page
        # Enable vision via environment variable: ENABLE_VISION_ANALYSIS=true
        use_vision = os.getenv("ENABLE_VISION_ANALYSIS", "false").lower() == "true"
        visual_data = extract_visual_data_from_pdf(
            str(pdf_path),
            page_num,
            use_vision=use_vision,
            api_key=api_key
        )
        all_visual_data[page_num] = visual_data
        
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
        
        chunks = chunk_text(page_text, max_chars=1200, overlap=200)  # slightly smaller chunks
        # #region agent log
        try:
            if page_count % 5 == 0 or page_count == 1:
                with open(LOG_PATH, "a") as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "build_index.py:75", "message": "Chunks created for page", "data": {"page_num": page_num, "num_chunks": len(chunks)}, "timestamp": int(time.time() * 1000)}) + "\n")
        except: pass
        # #endregion
        
        for j, chunk in enumerate(chunks):
            cid = f"p{page_num}_c{j:03d}"
            pending_ids.append(cid)
            pending_docs.append(chunk)
            
            # Enhanced metadata with visual data info
            meta = {
                "page": page_num,
                "chunk_id": cid,
                "has_tables": len(visual_data.get("tables", [])) > 0,
                "has_charts": len(visual_data.get("chart_analyses", [])) > 0,
                "table_count": len(visual_data.get("tables", []))
            }
            pending_metas.append(meta)

            if len(pending_docs) >= BATCH_DOCS:
                # #region agent log
                try:
                    batch_size = sum(len(d) for d in pending_docs)
                    with open(LOG_PATH, "a") as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "build_index.py:85", "message": "Before embedding batch", "data": {"batch_size": len(pending_docs), "total_chars": batch_size}, "timestamp": int(time.time() * 1000)}) + "\n")
                except: pass
                # #endregion
                
                resp = oai.embeddings.create(
                    model="text-embedding-3-small",
                    input=pending_docs,
                )
                # #region agent log
                try:
                    with open(LOG_PATH, "a") as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "build_index.py:92", "message": "Embeddings received", "data": {"num_embeddings": len(resp.data)}, "timestamp": int(time.time() * 1000)}) + "\n")
                except: pass
                # #endregion
                
                embeddings = [x.embedding for x in resp.data]

                # #region agent log
                try:
                    with open(LOG_PATH, "a") as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "D", "location": "build_index.py:98", "message": "Before ChromaDB add", "data": {"num_docs": len(pending_docs)}, "timestamp": int(time.time() * 1000)}) + "\n")
                except: pass
                # #endregion
                
                col.add(
                    ids=pending_ids,
                    documents=pending_docs,
                    metadatas=pending_metas,
                    embeddings=embeddings,
                )
                # #region agent log
                try:
                    with open(LOG_PATH, "a") as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "D", "location": "build_index.py:107", "message": "After ChromaDB add", "data": {}, "timestamp": int(time.time() * 1000)}) + "\n")
                except: pass
                # #endregion

                total_chunks += len(pending_docs)
                print(f"Indexed {total_chunks} chunks...")

                pending_ids, pending_docs, pending_metas = [], [], []

    # flush remainder
    if pending_docs:
        # #region agent log
        try:
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "build_index.py:118", "message": "Flushing remainder batch", "data": {"batch_size": len(pending_docs)}, "timestamp": int(time.time() * 1000)}) + "\n")
        except: pass
        # #endregion
        
        resp = oai.embeddings.create(
            model="text-embedding-3-small",
            input=pending_docs,
        )
        embeddings = [x.embedding for x in resp.data]
        col.add(ids=pending_ids, documents=pending_docs, metadatas=pending_metas, embeddings=embeddings)
        total_chunks += len(pending_docs)

    # #region agent log
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "ALL", "location": "build_index.py:130", "message": "main exit success", "data": {"total_chunks": total_chunks}, "timestamp": int(time.time() * 1000)}) + "\n")
    except: pass
    # #endregion
    
    print(f"✅ Done. Indexed {total_chunks} chunks into {persist_dir}")

if __name__ == "__main__":
    main()