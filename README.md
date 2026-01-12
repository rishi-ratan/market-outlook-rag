# Market Outlook RAG

A sophisticated Retrieval-Augmented Generation (RAG) application for querying BlackRock's 2026 Private Markets Outlook report. Built with Next.js, FastAPI, and ChromaDB.

## 🚀 Features

### Core Functionality
- **Document Q&A**: Ask natural language questions about the report
- **Citation Support**: Every answer includes source citations with page numbers
- **PDF Viewer Integration**: Click citations to view the original document
- **Smart Retrieval**: Semantic search using OpenAI embeddings
- **Citation Enforcement**: Automatic validation ensures factual claims are backed by sources

### Multi-LLM Support
- **OpenAI Integration**: Uses GPT-4o-mini for fast, cost-effective responses
- **Together AI Integration**: Supports Qwen2.5-72B-Instruct via Together AI API
- **Provider Comparison**: Side-by-side comparison of responses from different models
- **Provider Selection**: Choose your preferred LLM provider

### Streaming Responses (SSE)
- **Real-time Streaming**: See responses appear word-by-word as they're generated
- **Comparison Streaming**: Stream both providers simultaneously in comparison mode
- **Visual Indicators**: Green borders, pulsing dots, and progress indicators
- **Toggle Control**: Enable/disable streaming with a checkbox

### User Experience
- **Conversation Context**: Maintains conversation history for contextual follow-up questions
- **Dynamic Suggested Questions**: AI-generated contextual follow-up questions that adapt to conversation
- **Conversation History**: Full conversation tracking with expandable Q&A pairs
- **Export & Share**: Copy conversation to clipboard or export as PDF
- **Question History**: Session history with quick re-ask functionality
- **Dark Theme**: Modern, investor-ready UI
- **Responsive Design**: Works on desktop and mobile

## 🏗️ Architecture

### Backend (FastAPI)
- **Framework**: FastAPI with async support
- **Vector Database**: ChromaDB for persistent document storage
- **Embeddings**: OpenAI `text-embedding-3-small`
- **LLM Providers**: Abstracted provider system supporting multiple backends
- **Streaming**: Server-Sent Events (SSE) for real-time responses

### Frontend (Next.js)
- **Framework**: Next.js 14+ with React
- **Styling**: Tailwind CSS
- **Type Safety**: TypeScript throughout
- **State Management**: React hooks with localStorage persistence

## 📋 Prerequisites

- Python 3.8+
- Node.js 18+
- OpenAI API key
- Together AI API key (optional, for Qwen model)

## 🛠️ Setup

### 1. Clone the Repository
```bash
git clone https://github.com/rishi-ratan/market-outlook-rag.git
cd market-outlook-rag
```

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=sk-your-openai-key-here
TOGETHER_API_KEY=your-together-api-key-here
TOGETHER_MODEL=Qwen/Qwen2.5-72B-Instruct
```

### 3. Install Dependencies

**Backend:**
```bash
cd apps/api
pip install -r requirements.txt
```

**Frontend:**
```bash
cd apps/web
npm install
```

### 4. Build the Index (First Time)
```bash
cd ingestion
python build_index.py
```

This processes `data/report.pdf` and creates the vector index in `storage/chroma/`.

## 🚀 Running the Application

### Option 1: Using Batch Files (Windows)
- **Backend**: Double-click `START_BACKEND.bat`
- **Frontend**: Double-click `START_FRONTEND.bat`

### Option 2: Manual Commands

**Terminal 1 - Backend:**
```bash
cd market-outlook-rag
uvicorn apps.api.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd market-outlook-rag/apps/web
npm run dev
```

### Access the Application
Open your browser to: **http://localhost:3000**

## 📖 Usage

### Single Provider Mode
1. Select a provider from the dropdown (OpenAI or Together AI)
2. Optionally enable "Stream response" for real-time streaming
3. Type your question and click "Ask"
4. View the answer with citations and key points

### Comparison Mode
1. Check "Compare providers"
2. Optionally enable "Stream response" to see both stream simultaneously
3. Type your question and click "Compare"
4. View side-by-side responses from both providers

### Conversation Features
- **Follow-up Questions**: Ask contextual questions like "Tell me more about that" - the system remembers previous Q&A
- **Dynamic Suggestions**: Suggested questions update automatically based on your conversation
- **View Full History**: Expand any conversation turn to see the complete answer
- **Copy Conversation**: Click "Copy" to copy the entire conversation to clipboard
- **Export PDF**: Click "PDF" to download a formatted PDF of your conversation
- **New Conversation**: Click "New Conversation" to start fresh

### Using Citations
- Click any citation to open the PDF viewer at that page
- Citations are automatically validated against the source document
- Every factual claim is backed by at least one citation

## 🔧 Configuration

### Environment Variables
- `OPENAI_API_KEY`: Required for embeddings and OpenAI provider
- `TOGETHER_API_KEY`: Required for Together AI/Qwen provider
- `TOGETHER_MODEL`: Optional, defaults to `Qwen/Qwen2.5-72B-Instruct`
- `OPENAI_MODEL`: Optional, defaults to `gpt-4o-mini`
- `ALLOWED_ORIGINS`: CORS origins (comma-separated)
- `CHROMA_DIR`: Path to ChromaDB storage (defaults to `storage/chroma`)

### API Endpoints
- `GET /health` - Health check and index statistics
- `POST /ask` - Single provider query (supports conversation history)
- `POST /ask/stream` - Streaming single provider query (supports conversation history)
- `POST /ask/compare` - Comparison query (non-streaming, supports conversation history)
- `POST /ask/compare/stream` - Streaming comparison query (supports conversation history)
- `POST /suggest-questions` - Generate contextual follow-up questions based on conversation history

## 📁 Project Structure

```
market-outlook-rag/
├── apps/
│   ├── api/              # FastAPI backend
│   │   ├── main.py       # Main API endpoints
│   │   ├── llm_providers.py  # LLM provider abstraction
│   │   └── requirements.txt
│   └── web/              # Next.js frontend
│       ├── app/
│       │   └── page.tsx  # Main UI component
│       └── package.json
├── ingestion/            # Document processing
│   ├── build_index.py    # Index builder
│   ├── pdf_parse.py      # PDF parser
│   └── chunking.py       # Text chunking
├── data/                 # Source documents
│   └── report.pdf
├── storage/              # ChromaDB storage
│   └── chroma/
└── .env                  # Environment variables
```

## 🎯 Key Features Explained

### Citation Enforcement
The system automatically:
- Validates that citations reference actual document chunks
- Ensures page numbers match the source
- Adds citations for numeric/statistical claims
- Prevents hallucination by grounding all facts

### Streaming Responses
- **Single Mode**: Stream one provider's response in real-time
- **Comparison Mode**: Stream both providers simultaneously
- **Visual Feedback**: See tokens appear as they're generated
- **Fallback**: Automatically falls back to structured response when complete

### Multi-Provider Support
- **Abstraction Layer**: Easy to add new LLM providers
- **Unified Interface**: Same API for all providers
- **Provider Caching**: Efficient provider instance management
- **Error Handling**: Graceful fallbacks if a provider fails

### Conversation Context
- **History Tracking**: Automatically tracks all Q&A pairs in the session
- **Context Window**: Includes last 3 Q&A pairs in prompts for follow-up questions
- **Smart Suggestions**: AI generates contextual follow-up questions based on conversation
- **Export Options**: Copy to clipboard or export as formatted PDF
- **Expandable Display**: View full answers with expand/collapse functionality

## 🐛 Troubleshooting

### Port Already in Use
- Backend (8000): Kill process or use `--port 8001`
- Frontend (3000): Kill process or use `npm run dev -- -p 3001`

### Missing API Keys
- Ensure `.env` file exists with required keys
- Check that keys are valid and have sufficient credits

### Index Not Found
- Run `python ingestion/build_index.py` to create the index
- Ensure `data/report.pdf` exists

### Streaming Not Working
- Check browser console (F12) for errors
- Verify backend is running and accessible
- Check network tab for SSE connection

## 📚 Documentation

- [HOW_TO_RUN.md](HOW_TO_RUN.md) - Detailed setup instructions
- [QWEN_COMPARISON.md](QWEN_COMPARISON.md) - Multi-LLM setup guide
- [STREAMING_FEATURE.md](STREAMING_FEATURE.md) - Streaming documentation
- [IMPROVEMENTS_ROADMAP.md](IMPROVEMENTS_ROADMAP.md) - Future enhancements

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📄 License

See the original repository for license information.

## 🙏 Acknowledgments

- Built on top of the original Market Outlook RAG project
- Uses OpenAI for embeddings and GPT models
- Uses Together AI for Qwen model access
- ChromaDB for vector storage

---

**Note**: This project is designed for querying a specific PDF document (BlackRock's 2026 Private Markets Outlook). To use with other documents, modify the ingestion pipeline and update the document path.