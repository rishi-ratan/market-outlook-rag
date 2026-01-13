# Market Outlook RAG

A sophisticated Retrieval-Augmented Generation (RAG) application for querying PDF documents with AI. Built with Next.js, FastAPI, and ChromaDB. Supports multiple LLM providers, real-time streaming, document management, and visual data extraction.

## 🚀 Features

### Core Functionality
- **Document Q&A**: Ask natural language questions about uploaded PDF documents
- **Citation Support**: Every answer includes source citations with page numbers
- **PDF Viewer Integration**: Click citations to view the original document at exact locations
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

### Document Management
- **Upload PDFs**: Upload and manage multiple PDF documents
- **Per-Document Collections**: Each document has its own ChromaDB collection for isolated RAG
- **Active Document System**: Switch between documents seamlessly
- **Document Metadata**: Track document status, pages, chunks, and upload dates
- **Automatic Processing**: Documents are processed asynchronously upon upload
- **Document Deletion**: Remove documents and their associated data
- **PDF Viewer Integration**: PDF viewer automatically displays the active document

### Visual Data Extraction
- **Table Extraction**: Automatically extracts tables from PDFs using `pdfplumber`
- **Chart Analysis**: GPT-4 Vision integration for analyzing charts and graphs (optional)
- **Visual Data Display**: Tables and chart insights displayed in responses
- **Structured Data**: Extracted visual data included in RAG context

### User Experience
- **Conversation Context**: Maintains conversation history for contextual follow-up questions
- **Dynamic Suggested Questions**: AI-generated contextual follow-up questions that adapt to conversation and document content
- **Conversation History**: Full conversation tracking with expandable Q&A pairs
- **Citation Preservation**: All citations are saved with conversation history for easy reference
- **Enhanced PDF Navigation**: Click citations to jump to exact pages with automatic text search
- **Export & Share**: Copy conversation to clipboard (with citations) or export as PDF (with sources)
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
- **Visual Processing**: pdfplumber for tables, GPT-4 Vision for charts (optional)

### Frontend (Next.js)
- **Framework**: Next.js 14+ with React
- **Styling**: Tailwind CSS
- **Type Safety**: TypeScript throughout
- **State Management**: React hooks with localStorage persistence

## 📋 Prerequisites

- Python 3.8+
- Node.js 18+
- OpenAI API key (required)
- Together AI API key (optional, for Qwen model)
- Poppler (for PDF processing) - See installation below

### Installing Poppler (for PDF processing)

**Windows:**
1. Download from: https://github.com/oschwartz10612/poppler-windows/releases/
2. Extract and add `bin` folder to PATH
3. Or use: `choco install poppler`

**Mac:**
```bash
brew install poppler
```

**Linux:**
```bash
sudo apt-get install poppler-utils
```

## 🛠️ Setup

### 1. Clone the Repository

```bash
git clone https://github.com/rishi-ratan/market-outlook-rag.git
cd market-outlook-rag
```

### 2. Environment Variables

Create a `.env` file in the root directory:

```env
# Required
OPENAI_API_KEY=sk-your-openai-key-here
TOGETHER_API_KEY=your-together-api-key-here

# Optional - Model Selection
TOGETHER_MODEL=Qwen/Qwen2.5-72B-Instruct
OPENAI_MODEL=gpt-4o-mini

# Optional - Vision Analysis (for chart extraction)
ENABLE_VISION_ANALYSIS=false
OPENAI_VISION_MODEL=gpt-4o-mini

# Optional - CORS (for production)
ALLOWED_ORIGINS=http://localhost:3000
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

### 4. Build the Index (Optional - for default document)

```bash
cd ingestion
python build_index.py
```

This processes `data/report.pdf` and creates the vector index in `storage/chroma/`.

**Note**: You can also upload documents directly through the UI. The default document setup is optional.

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

### Document Management
- **Upload Documents**: Click "Documents" button to open the document management panel
- **Drag & Drop**: Drag PDF files into the upload area or click to select
- **Document Status**: See processing status (uploading, processing, processed, error)
- **Switch Documents**: Click "Activate" on any document to make it active
- **Delete Documents**: Remove documents and their associated data with "Delete"
- **Active Document**: The current active document is highlighted and used for all queries

### Conversation Features
- **Follow-up Questions**: Ask contextual questions like "Tell me more about that" - the system remembers previous Q&A
- **Dynamic Suggestions**: Suggested questions update automatically based on your conversation and the active document's content
- **View Full History**: Expand any conversation turn to see the complete answer
- **Citation Buttons**: Each answer shows clickable citation buttons (e.g., "Pg 5", "Pg 12") in conversation history
- **Copy Conversation**: Click "Copy" to copy the entire conversation to clipboard (includes all citations)
- **Export PDF**: Click "PDF" to download a formatted PDF of your conversation (includes all sources)
- **New Conversation**: Click "New Conversation" to start fresh

### Using Citations
- **In Answers**: Click any citation to open the PDF viewer at that page
- **In History**: Click citation buttons (e.g., "Pg 5") in conversation history to jump to sources
- **Smart Search**: PDF viewer automatically attempts to search for the quoted text
- **Manual Search**: Use "Search in PDF" button or Ctrl+F (Cmd+F on Mac) to find exact text
- **Citation Validation**: Citations are automatically validated against the source document
- **Source Preservation**: All citations are saved with conversation history for future reference
- **Every factual claim is backed by at least one citation**

## 🔧 Configuration

### Environment Variables

**Required:**
- `OPENAI_API_KEY`: Required for embeddings and OpenAI provider

**Optional:**
- `TOGETHER_API_KEY`: Required for Together AI/Qwen provider
- `TOGETHER_MODEL`: Optional, defaults to `Qwen/Qwen2.5-72B-Instruct`
- `OPENAI_MODEL`: Optional, defaults to `gpt-4o-mini`
- `ENABLE_VISION_ANALYSIS`: Optional, set to `true` to enable GPT-4 Vision for chart analysis (default: `false`)
- `OPENAI_VISION_MODEL`: Optional, vision model to use: `gpt-4o-mini` (cheapest), `gpt-4o` (best quality), or `gpt-4-turbo` (default: `gpt-4o-mini`)
- `ALLOWED_ORIGINS`: CORS origins (comma-separated, e.g., `https://your-app.vercel.app,http://localhost:3000`)
- `CHROMA_DIR`: Path to ChromaDB storage (defaults to `storage/chroma`)

### Vision Analysis Setup

To enable GPT-4 Vision for chart and graph analysis:

1. **Add to `.env`**:
   ```env
   ENABLE_VISION_ANALYSIS=true
   OPENAI_VISION_MODEL=gpt-4o-mini
   ```

2. **Model Options**:
   - `gpt-4o-mini` (Recommended): ~$0.15 per 1M tokens - Best balance of cost and quality
   - `gpt-4o` (Best quality): ~$2.50 per 1M tokens - Use when you need highest accuracy
   - `gpt-4-turbo` (Alternative): ~$1.00 per 1M tokens - Good middle ground

3. **Cost Estimation**: 50-page document with `gpt-4o-mini` costs ~$0.10-0.30

4. **Note**: Qwen models on TogetherAI do NOT support vision. Vision analysis requires OpenAI models.

### Multi-LLM Setup

To use Qwen model via Together AI:

1. **Get Together AI API Key**: Sign up at https://together.ai
2. **Add to `.env`**:
   ```env
   TOGETHER_API_KEY=your-together-api-key-here
   TOGETHER_MODEL=Qwen/Qwen2.5-72B-Instruct
   ```

3. **Use in UI**: Select "Together AI (Qwen2.5-72B)" from the provider dropdown

### API Endpoints

- `GET /health` - Health check and index statistics
- `POST /ask` - Single provider query (supports conversation history)
- `POST /ask/stream` - Streaming single provider query (supports conversation history)
- `POST /ask/compare` - Comparison query (non-streaming, supports conversation history)
- `POST /ask/compare/stream` - Streaming comparison query (supports conversation history)
- `POST /suggest-questions` - Generate contextual follow-up questions based on conversation history and document content
- `GET /documents` - List all documents and get active document ID
- `POST /documents/upload` - Upload and process a new PDF document
- `POST /documents/{doc_id}/activate` - Set a document as active
- `DELETE /documents/{doc_id}` - Delete a document and its associated data
- `GET /documents/{doc_id}/pdf` - Serve a specific document's PDF file
- `GET /documents/active/pdf` - Serve the active document's PDF file

## 🚀 Deployment

Deploy your RAG application to production for free using Vercel (frontend) and Render (recommended) or Railway (backend).

### Quick Deployment (5 minutes)

#### 1. Backend (Render - Recommended)

1. Go to [render.com](https://render.com) and sign up with GitHub
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. **Configure**:
   - **Name**: `market-outlook-rag-api`
   - **Environment**: **Docker** (important!)
   - **Dockerfile Path**: `apps/api/Dockerfile`
   - **Docker Context**: `.`
   - **Plan**: Free
5. **Add Environment Variables**:
   - `OPENAI_API_KEY` = your key
   - `TOGETHER_API_KEY` = your key (optional)
   - `ALLOWED_ORIGINS` = `http://localhost:3000` (update after frontend deploy)
6. Click **"Create Web Service"**
7. Wait ~5-10 minutes for deployment
8. Copy your Render URL (e.g., `https://market-outlook-rag-api.onrender.com`)

#### 2. Frontend (Vercel)

1. **Push your code to GitHub first!**
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main  # or your branch name
   ```

2. Go to [vercel.com](https://vercel.com) and sign up
3. Click **"Add New Project"** → Import your GitHub repo
4. **Configure**:
   - **Root Directory**: `apps/web` ⚠️ **IMPORTANT!**
   - **Framework**: Next.js (auto-detected)
   - **Build Command**: `npm run build` (default)
   - **Output Directory**: `.next` (default)
5. **Add Environment Variable**:
   - Go to Settings → Environment Variables
   - Add: `NEXT_PUBLIC_API_BASE`
   - Value: Your Render backend URL (e.g., `https://market-outlook-rag-api.onrender.com`)
   - Select: Production, Preview, Development
6. Click **"Deploy"**
7. Wait for build to complete
8. Copy your Vercel URL (e.g., `https://your-app.vercel.app`)

#### 3. Update CORS

1. Go back to Render → Your service → Environment
2. Update `ALLOWED_ORIGINS`:
   ```
   ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000
   ```
3. Save (Render will auto-redeploy)

### Alternative: Railway (Backend)

If you prefer Railway:

1. Go to [railway.app](https://railway.app) and sign up
2. Create new project → Deploy from GitHub
3. **Configure** (Settings → Source):
   - **Dockerfile Path**: `apps/api/Dockerfile`
   - **Root Directory**: `.`
   - **Build Method**: Docker (not Railpack)
4. Add environment variables (same as Render)
5. Deploy

**Note**: Railway may try to use Railpack instead of Docker. If you see "Error creating build plan with Railpack", ensure Docker is selected in Settings → Source.

### Deployment Architecture

- **Frontend**: Vercel (free tier, unlimited deployments)
- **Backend**: Render (free tier, 750 hours/month) or Railway (free tier, $5 credit/month)
- **Storage**: ChromaDB and PDFs stored on backend server (persistent)

### Environment Variables for Production

**Backend (Render/Railway):**
- `OPENAI_API_KEY` (required)
- `TOGETHER_API_KEY` (optional)
- `ALLOWED_ORIGINS` (required): Comma-separated list (e.g., `https://your-app.vercel.app,http://localhost:3000`)
- `ENABLE_VISION_ANALYSIS` (optional): `true` or `false`
- `OPENAI_VISION_MODEL` (optional): `gpt-4o-mini`, `gpt-4o`, or `gpt-4-turbo`
- `PORT` (auto-set by platform)

**Import .env to Railway - Easiest Method (RAW Editor):**
1. Go to Railway → Your Service → **Variables** tab
2. Click **"RAW Editor"** button
3. Copy entire content of your `.env` file
4. Paste into the RAW Editor
5. Click **Save**
6. All variables are now imported! ✅

**Alternative: Railway CLI:**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Import .env file
railway env import .env

# Verify
railway env list
```

**Manual Method (if above don't work):**
Go to Railway → Your Service → Variables → Add each variable manually

**Frontend (Vercel):**
- `NEXT_PUBLIC_API_BASE` (required): Your backend URL

### Cost Estimate

- **Vercel**: Free (unlimited deployments)
- **Render Free Tier**: 750 hours/month, sleeps after 15 min inactivity
- **Railway Free Tier**: $5 credit/month
- **Total**: $0/month for light usage

### Troubleshooting Deployment

**404 Error on Vercel:**
- Verify Root Directory is set to `apps/web`
- Check that code is pushed to GitHub
- Verify `NEXT_PUBLIC_API_BASE` environment variable is set
- Check build logs for errors

**Backend Not Responding:**
- Check Render/Railway logs
- Verify environment variables are set
- Test `/health` endpoint directly
- Ensure backend is not sleeping (Render free tier)

**CORS Errors:**
- Add your Vercel URL to `ALLOWED_ORIGINS` in backend
- No spaces in comma-separated list
- Format: `https://app.vercel.app,http://localhost:3000`
- Redeploy backend after updating

**Railway Railpack Error:**
- Go to Settings → Source
- Ensure Dockerfile Path is set: `apps/api/Dockerfile`
- Select "Docker" as build method (not Railpack)
- Redeploy

## 📁 Project Structure

```
market-outlook-rag/
├── apps/
│   ├── api/              # FastAPI backend
│   │   ├── main.py       # Main API endpoints
│   │   ├── llm_providers.py  # LLM provider abstraction
│   │   ├── Dockerfile    # Docker configuration for deployment
│   │   └── requirements.txt
│   └── web/              # Next.js frontend
│       ├── app/
│       │   └── page.tsx  # Main UI component
│       ├── vercel.json   # Vercel configuration
│       └── package.json
├── ingestion/            # Document processing
│   ├── build_index.py    # Index builder
│   ├── pdf_parse.py      # PDF parser
│   ├── chunking.py       # Text chunking
│   └── visual_extraction.py  # Visual data extraction
├── data/                 # Source documents
│   └── report.pdf
├── storage/              # Application storage
│   ├── chroma/           # ChromaDB storage (per-document collections)
│   ├── uploads/          # Uploaded PDF files
│   ├── visual_data/      # Extracted visual data
│   └── documents_metadata.json  # Document metadata
├── railway.json          # Railway configuration
├── render.yaml           # Render configuration
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
- **SSE Format**: Uses Server-Sent Events for efficient streaming

### Multi-Provider Support
- **Abstraction Layer**: Easy to add new LLM providers
- **Unified Interface**: Same API for all providers
- **Provider Caching**: Efficient provider instance management
- **Error Handling**: Graceful fallbacks if a provider fails

### Document Management System
- **Per-Document Collections**: Each uploaded document gets its own ChromaDB collection
- **Isolated RAG**: Queries only search within the active document's collection
- **Metadata Tracking**: Documents store filename, size, page count, chunk count, status, and timestamps
- **Asynchronous Processing**: Documents are processed in the background after upload
- **Active Document**: Only one document is active at a time, used for all queries
- **PDF Serving**: Active document's PDF is automatically served to the PDF viewer
- **Default Document**: Falls back to default `report.pdf` if no document is active

### Conversation Context
- **History Tracking**: Automatically tracks all Q&A pairs in the session
- **Citation Preservation**: All citations (page numbers and quotes) are saved with each Q&A pair
- **Context Window**: Includes last 3 Q&A pairs in prompts for follow-up questions
- **Smart Suggestions**: AI generates contextual follow-up questions based on conversation and active document content
- **Export Options**: Copy to clipboard (with citations) or export as formatted PDF (with sources)
- **Expandable Display**: View full answers with expand/collapse functionality
- **Quick Navigation**: Click citation buttons in history to jump directly to PDF pages

### Enhanced PDF Navigation
- **Automatic Text Search**: When opening a citation, the system extracts searchable text from the quote
- **PDF.js Integration**: Attempts to use PDF.js search functionality when available
- **Browser Find Fallback**: Falls back to native browser find (Ctrl+F / Cmd+F) if PDF.js isn't available
- **Search Tips**: Shows the search text and keyboard shortcuts in the PDF viewer
- **Exact Text Location**: Helps users find the exact sentence or paragraph referenced in citations

### Visual Data Extraction
- **Table Extraction**: Uses `pdfplumber` to extract tables from PDFs automatically
- **Chart Analysis**: Optional GPT-4 Vision integration for analyzing charts and graphs
- **Structured Data**: Extracted visual data is included in RAG context for better answers
- **UI Display**: Tables and chart insights are displayed in responses

## 🐛 Troubleshooting

### Port Already in Use
- **Backend (8000)**: Kill process or use `--port 8001`
- **Frontend (3000)**: Kill process or use `npm run dev -- -p 3001`

### Missing API Keys
- Ensure `.env` file exists with required keys
- Check that keys are valid and have sufficient credits
- Verify keys are set in production environment (Render/Railway/Vercel)

### Index Not Found
- Run `python ingestion/build_index.py` to create the index
- Ensure `data/report.pdf` exists
- Or upload a document through the UI

### Streaming Not Working
- Check browser console (F12) for errors
- Verify backend is running and accessible
- Check network tab for SSE connection
- Ensure streaming is enabled in the UI checkbox

### Document Upload Fails
- Check file size limits (backend may have limits)
- Verify PDF is not corrupted
- Check backend logs for processing errors
- Ensure Poppler is installed for PDF processing

### Vision Analysis Not Working
- Verify `ENABLE_VISION_ANALYSIS=true` in `.env`
- Check OpenAI API key has access to vision models
- Verify model name is correct (`gpt-4o-mini`, `gpt-4o`, or `gpt-4-turbo`)
- Check backend logs for vision processing errors

### Suggested Questions Not Updating
- Check browser console for errors
- Verify backend `/suggest-questions` endpoint is accessible
- Ensure conversation history is being sent correctly
- Check if document is fully processed (status should be "processed")

### CORS Errors
- Verify `ALLOWED_ORIGINS` includes your frontend URL
- No spaces in comma-separated list
- Format: `https://app.vercel.app,http://localhost:3000`
- Redeploy backend after updating CORS settings

### Vercel Deployment Issues

**404 Error or Build Fails:**
1. **Check Root Directory**: Go to Vercel Dashboard → Settings → General
   - **Root Directory**: Must be set to `apps/web` ⚠️ **MOST IMPORTANT**
   - If set to `.` (root), change it to `apps/web` and redeploy
2. **Verify Project Structure**: Vercel should see `package.json`, `app/` directory, and `next.config.ts` in `apps/web/`
3. **Check Build Logs**: Go to Deployments → Click failed deployment → View Build Logs for specific errors

**Environment Variables Not Set:**
1. Go to Vercel Dashboard → Settings → Environment Variables
2. Add: `NEXT_PUBLIC_API_BASE` with your backend URL
3. **Important**: Select all environments (Production, Preview, Development)
4. Save and redeploy

**Build Command Fails:**
1. **Test Build Locally**:
   ```bash
   cd apps/web
   npm install
   npm run build
   ```
2. Fix any TypeScript errors or missing dependencies locally first
3. Common issues:
   - TypeScript errors → Fix in code
   - Missing dependencies → Check `package.json`
   - "Cannot find module" → Install missing package

**Wrong Branch Connected:**
1. Go to Settings → Git
2. Verify correct repository: `rishi-ratan/market-outlook-rag`
3. Verify correct branch: `rag-docs` (or your active branch)
4. Auto-deploy should be enabled

**Quick Vercel Fix Checklist:**
- ✅ Root Directory = `apps/web` (not `.`)
- ✅ `NEXT_PUBLIC_API_BASE` environment variable set
- ✅ Correct branch connected
- ✅ Build succeeds locally (`npm run build` in `apps/web`)
- ✅ Check build logs for specific errors

## 📚 Additional Resources

- [IMPROVEMENTS_ROADMAP.md](IMPROVEMENTS_ROADMAP.md) - Future enhancements and roadmap

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📄 License

See the original repository for license information.

## 🙏 Acknowledgments

- Built on top of the original Market Outlook RAG project
- Uses OpenAI for embeddings and GPT models
- Uses Together AI for Qwen model access
- ChromaDB for vector storage
- pdfplumber for table extraction
- GPT-4 Vision for chart analysis

---

**Note**: This project is designed for querying PDF documents. Upload any PDF through the UI to start querying it with AI-powered RAG.
