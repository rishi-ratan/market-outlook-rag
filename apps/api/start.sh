#!/bin/bash
# Don't use set -e - we want to handle errors gracefully and show logs

echo "=========================================="
echo "Starting Market Outlook RAG API..."
echo "=========================================="

# Check if ChromaDB index exists
CHROMA_DIR=${CHROMA_DIR:-/app/storage/chroma}
echo "Creating storage directory: $CHROMA_DIR"
mkdir -p "$CHROMA_DIR" || {
    echo "ERROR: Failed to create storage directory"
    exit 1
}

INDEX_EXISTS=false

if [ -f "$CHROMA_DIR/chroma.sqlite3" ]; then
    echo "Checking ChromaDB index..."
    # Check if collection has data
    if python3 -c "
import chromadb
import sys
try:
    ch = chromadb.PersistentClient(path='$CHROMA_DIR')
    col = ch.get_or_create_collection(name='market_outlook')
    count = col.count()
    print(f'Found {count} chunks in index')
    if count > 100:  # Reasonable threshold - adjust based on your PDF size
        sys.exit(0)  # Index exists and has data
    else:
        print('Index exists but has too few chunks, will rebuild')
        sys.exit(1)  # Index is empty or incomplete
except Exception as e:
    print(f'Error checking index: {e}')
    sys.exit(1)
" 2>&1; then
        INDEX_EXISTS=true
    else
        INDEX_EXISTS=false
    fi
else
    echo "ChromaDB index file not found"
    INDEX_EXISTS=false
fi

# Build index if it doesn't exist or is empty
if [ "$INDEX_EXISTS" = false ]; then
    echo "ChromaDB index not found or incomplete. Building index from PDF..."
    # Check if OPENAI_API_KEY is set before trying to build
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "⚠️  WARNING: OPENAI_API_KEY not set. Skipping index build."
        echo "   You can upload documents through the UI once the server starts."
    else
        echo "Building index with OPENAI_API_KEY..."
        if python3 -m ingestion.build_index 2>&1; then
            echo "✅ Index build complete!"
        else
            echo "⚠️  WARNING: Index build failed. Server will start anyway."
            echo "   You can upload documents through the UI once the server starts."
        fi
    fi
else
    echo "✅ ChromaDB index found. Skipping build."
fi

# Start the API server
# Railway sets PORT automatically - use it or default to 8000
PORT=${PORT:-8000}
echo "=========================================="
echo "Starting API server..."
echo "Host: 0.0.0.0"
echo "Port: ${PORT}"
echo "PYTHONPATH: ${PYTHONPATH:-/app}"
echo "Working directory: $(pwd)"
echo "Python version: $(python3 --version)"
echo "=========================================="

# Use PORT environment variable if set (Railway/Render), otherwise default to 8000
# Railway automatically sets PORT (usually 8080), so we use it directly
# Use exec to replace shell process with uvicorn
exec python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT} --log-level info 2>&1

