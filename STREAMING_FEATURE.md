# 🚀 Streaming Responses (SSE) Feature

## Overview

The application now supports **Server-Sent Events (SSE)** for streaming responses in real-time. Users can see tokens appear as they're generated, providing a more responsive and engaging experience.

## What Was Added

### Backend Changes

1. **LLM Provider Streaming Support** (`apps/api/llm_providers.py`)
   - Added `generate_stream()` method to `LLMProvider` abstract class
   - Implemented streaming for `OpenAIProvider` using OpenAI's streaming API
   - Implemented streaming for `TogetherAIProvider` using Together AI's streaming API
   - Both providers now support real-time token streaming

2. **New Streaming Endpoint** (`apps/api/main.py`)
   - Added `/ask/stream` endpoint that returns SSE events
   - Streams JSON chunks as they're generated
   - Parses and validates complete response
   - Sends final structured response when complete

### Frontend Changes

1. **Streaming UI** (`apps/web/app/page.tsx`)
   - Added "Stream response" checkbox (enabled by default)
   - Real-time display of streaming tokens
   - Extracts and displays answer field from partial JSON
   - Shows typing indicator (blinking cursor) while streaming
   - Automatically switches to structured view when complete

## How It Works

1. **User enables streaming** (checkbox is checked by default)
2. **Frontend sends request** to `/ask/stream` endpoint
3. **Backend streams tokens** as they're generated from the LLM
4. **Frontend displays tokens** in real-time as they arrive
5. **Backend parses complete JSON** and validates citations
6. **Frontend shows final structured response** with citations and key points

## Usage

### Enable Streaming
- Check the "Stream response" checkbox (enabled by default)
- Streaming only works in single-provider mode (not in comparison mode)

### Disable Streaming
- Uncheck the "Stream response" checkbox
- Falls back to traditional request/response pattern

## Technical Details

### SSE Format
```
data: {"type": "chunk", "content": "token"}
data: {"type": "chunk", "content": " token"}
data: {"type": "complete", "response": {...}}
```

### Frontend Parsing
- Uses `fetch()` with `ReadableStream` (EventSource doesn't support POST)
- Parses SSE events line by line
- Extracts answer field from partial JSON using regex
- Falls back to showing raw text if extraction fails

### Backend Streaming
- Uses FastAPI's `StreamingResponse`
- Generator function yields SSE-formatted events
- Maintains same validation and citation logic as non-streaming endpoint

## Benefits

✅ **Better UX**: Users see responses immediately instead of waiting
✅ **Perceived Performance**: Feels faster even if total time is similar
✅ **Engagement**: More interactive and engaging experience
✅ **Transparency**: Users can see the model "thinking" in real-time

## Limitations

- Streaming only works with single provider (not comparison mode)
- JSON parsing happens incrementally (may show raw JSON briefly)
- Requires modern browser with ReadableStream support

## Future Improvements

- Stream key_points and citations separately
- Better partial JSON parsing
- Streaming support for comparison mode
- Progress indicators
- Cancel streaming requests
