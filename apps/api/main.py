import os
import json
import re
import queue
import threading
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
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
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY. Set it in the environment (or locally in ROOT/.env).")

oai = OpenAI(api_key=OPENAI_API_KEY)

CHROMA_DIR = os.getenv("CHROMA_DIR", str(ROOT / "storage" / "chroma"))
ch = chromadb.PersistentClient(path=CHROMA_DIR)
col = ch.get_or_create_collection(name="market_outlook")

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

class AskRequest(BaseModel):
    question: str
    top_k: int = Field(default=8, ge=1, le=20)
    provider: Optional[str] = Field(default="openai", description="LLM provider: 'openai' or 'together'")

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

class ComparisonResponse(BaseModel):
    question: str
    responses: List[AskResponse]

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
    # Get collection stats
    count = col.count()
    
    # Get all documents to see complete page range (may be slow for large indexes)
    all_results = col.get(limit=count)
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

@app.options("/ask")
@app.options("/api/ask")
async def options_ask():
    """Handle preflight OPTIONS requests - CORS middleware should handle this, but this ensures it works"""
    # Return empty 200 - CORS middleware will add the headers
    return Response(status_code=200)

def _generate_response(question: str, top_k: int, provider_name: str, docs: List[str], metas: List[dict]) -> AskResponse:
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

    user = (
        f"Question: {question}\n\n"
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
    results = col.query(
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
    return _generate_response(req.question, req.top_k, req.provider, docs, metas)


def _stream_generator(question: str, top_k: int, provider_name: str, docs: List[str], metas: List[dict]):
    """Generator function for streaming responses via SSE."""
    try:
        # Build context blocks
        context_blocks = []
        for d, m in zip(docs, metas):
            context_blocks.append(f"[{m['chunk_id']} | page {m['page']}]\n{d}")

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
            f"Question: {question}\n\n"
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
    results = col.query(
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
        _stream_generator(req.question, req.top_k, req.provider, docs, metas),
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

            user = (
                f"Question: {question}\n\n"
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
        results = col.query(
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
    results = col.query(
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
            return _generate_response(req.question, req.top_k, provider_name, docs, metas)
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