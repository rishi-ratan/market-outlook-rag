#!/bin/bash
set -e

# Check if ChromaDB index exists
CHROMA_DIR=${CHROMA_DIR:-/app/storage/chroma}
mkdir -p "$CHROMA_DIR"

INDEX_EXISTS=false

if [ -f "$CHROMA_DIR/chroma.sqlite3" ]; then
    # Check if collection has data
    python3 -c "
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
" && INDEX_EXISTS=true || INDEX_EXISTS=false
fi

# Build index if it doesn't exist or is empty
if [ "$INDEX_EXISTS" = false ]; then
    echo "ChromaDB index not found or incomplete. Building index from PDF..."
    # Check if OPENAI_API_KEY is set before trying to build
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "⚠️  WARNING: OPENAI_API_KEY not set. Skipping index build."
        echo "   You can upload documents through the UI once the server starts."
    else
        python3 -m ingestion.build_index || {
            echo "⚠️  WARNING: Index build failed. Server will start anyway."
            echo "   You can upload documents through the UI once the server starts."
        }
        echo "✅ Index build complete!"
    fi
else
    echo "✅ ChromaDB index found. Skipping build."
fi

# Start the API server
echo "Starting API server on port ${PORT:-8000}..."
# Use PORT environment variable if set (Railway/Render), otherwise default to 8000
exec python -m uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}

