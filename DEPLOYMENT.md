# Deployment Guide

This guide will help you deploy the Market Outlook RAG application to production using **Vercel** (frontend) and **Render** (recommended) or **Railway** (backend).

> **💡 Recommendation**: Use **Render** instead of Railway - it's much easier to set up! See [RENDER_SETUP.md](./RENDER_SETUP.md) for the simplest deployment path.

## Architecture Overview

- **Frontend (Next.js)**: Deployed on Vercel (free tier)
- **Backend (FastAPI)**: Deployed on Railway or Render (free tier)
- **Vector Database (ChromaDB)**: Stored locally on the backend server
- **File Storage**: PDFs stored on the backend server's filesystem

## Option 1: Render (Recommended - Easiest Setup) ⭐

> **See [RENDER_SETUP.md](./RENDER_SETUP.md) for detailed step-by-step instructions.**

### Quick Steps

1. **Go to [render.com](https://render.com)** and sign up
2. **New +** → **Web Service** → Connect GitHub
3. **Select your repo**
4. **Configure**:
   - Environment: **Docker**
   - Dockerfile Path: `apps/api/Dockerfile`
   - Docker Context: `.`
   - Plan: **Free**
5. **Add environment variables** (OPENAI_API_KEY, etc.)
6. **Deploy!** (~5-10 minutes)

**That's it!** Much simpler than Railway. See [RENDER_SETUP.md](./RENDER_SETUP.md) for full details.

---

## Option 2: Railway (Alternative)

### Prerequisites
- GitHub account
- Railway account (sign up at [railway.app](https://railway.app))
- OpenAI API key
- Together AI API key (optional, for Qwen model)

### Step 1: Deploy Backend to Railway

1. **Push your code to GitHub** (if not already):
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

2. **Create a new Railway project**:
   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Configure the service**:
   - **IMPORTANT**: In Railway, go to your service → Settings → Source
   - **Set Build Command**: Leave empty (Docker will handle it)
   - **Set Start Command**: Leave empty (Dockerfile CMD will handle it)
   - **Set Dockerfile Path**: `apps/api/Dockerfile`
   - **Set Root Directory**: `.` (root of repo)
   - If Railway still tries to use Railpack, you may need to:
     - Go to Settings → Source
     - Toggle "Use Docker" or select "Dockerfile" as the build method
   - Add environment variables:
     - `OPENAI_API_KEY`: Your OpenAI API key (required)
     - `TOGETHER_API_KEY`: Your Together AI API key (optional)
     - `ALLOWED_ORIGINS`: `https://your-frontend.vercel.app,http://localhost:3000` (add your Vercel URL after deployment)
     - `ENABLE_VISION_ANALYSIS`: `false` (or `true` if you want vision)
     - `OPENAI_VISION_MODEL`: `gpt-4o` (if vision enabled)
     - `PORT`: Railway sets this automatically

4. **Deploy**:
   - Railway will automatically build and deploy
   - Wait for deployment to complete
   - Copy the generated URL (e.g., `https://your-app.railway.app`)

5. **Test the backend**:
   - Visit `https://your-app.railway.app/health`
   - Should return `{"status": "ok"}`

### Step 2: Deploy Frontend to Vercel

1. **Install Vercel CLI** (optional, or use web interface):
   ```bash
   npm i -g vercel
   ```

2. **Deploy via Vercel Dashboard**:
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New Project"
   - Import your GitHub repository
   - Configure:
     - **Root Directory**: `apps/web`
     - **Framework Preset**: Next.js
     - **Build Command**: `npm run build`
     - **Output Directory**: `.next`
     - **Install Command**: `npm install`

3. **Add Environment Variables**:
   - In Vercel project settings, add:
     - `NEXT_PUBLIC_API_BASE`: Your Railway backend URL (e.g., `https://your-app.railway.app`)

4. **Deploy**:
   - Click "Deploy"
   - Wait for build to complete
   - Your app will be live at `https://your-app.vercel.app`

### Step 3: Configure CORS

The backend automatically reads allowed origins from the `ALLOWED_ORIGINS` environment variable.

1. **In Railway**, go to your service → Variables tab
2. **Add or update** the `ALLOWED_ORIGINS` variable:
   - Value: `https://your-app.vercel.app,http://localhost:3000`
   - (Separate multiple origins with commas, no spaces)
3. **Redeploy** if needed (Railway auto-redeploys on env var changes)

**Note**: If `ALLOWED_ORIGINS` is not set, it defaults to localhost only (for local development).

---

## Option 3: Other Alternatives

See [DEPLOYMENT_ALTERNATIVES.md](./DEPLOYMENT_ALTERNATIVES.md) for other options like Fly.io, Google Cloud Run, etc.

### Step 1: Deploy Backend to Render

1. **Push code to GitHub** (if not already)

2. **Create a new Web Service on Render**:
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository

3. **Configure the service**:
   - **Name**: `market-outlook-rag-api`
   - **Environment**: Docker
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Dockerfile Path**: `apps/api/Dockerfile`
   - **Docker Context**: `.` (root directory)
   - **Plan**: Free

4. **Add Environment Variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `TOGETHER_API_KEY`: Your Together AI API key (optional)
   - `ENABLE_VISION_ANALYSIS`: `false`
   - `OPENAI_VISION_MODEL`: `gpt-4o`
   - `PORT`: `8000`

5. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment (first deploy takes ~10 minutes)
   - Copy the URL (e.g., `https://your-app.onrender.com`)

### Step 2: Deploy Frontend to Vercel

Same as Step 2 in Railway section above, but use your Render URL for `NEXT_PUBLIC_API_BASE`.

---

## Environment Variables Reference

### Backend (Railway/Render)
- `OPENAI_API_KEY` (required): Your OpenAI API key
- `TOGETHER_API_KEY` (optional): Your Together AI API key for Qwen model
- `ALLOWED_ORIGINS` (required for production): Comma-separated list of allowed origins (e.g., `https://your-app.vercel.app,http://localhost:3000`)
- `ENABLE_VISION_ANALYSIS` (optional): `true` or `false` - Enable GPT-4 Vision
- `OPENAI_VISION_MODEL` (optional): `gpt-4o`, `gpt-4o-mini`, or `gpt-4-turbo`
- `PORT` (auto-set): Port number (Railway/Render sets this automatically)

### Frontend (Vercel)
- `NEXT_PUBLIC_API_BASE` (required): Your backend URL (e.g., `https://your-app.railway.app`)

---

## Important Notes

### Free Tier Limitations

**Railway Free Tier**:
- $5 credit/month (enough for light usage)
- Sleeps after 30 days of inactivity
- Persistent storage included

**Render Free Tier**:
- Sleeps after 15 minutes of inactivity (takes ~30s to wake up)
- 750 hours/month free
- Persistent storage included

**Vercel Free Tier**:
- Unlimited deployments
- 100GB bandwidth/month
- No sleep/wake issues

### Storage Considerations

- **ChromaDB**: Stored in `/app/storage/chroma` on the backend server
- **Uploaded PDFs**: Stored in `/app/storage/uploads` on the backend server
- Both persist across deployments on Railway/Render

### Cost Optimization

1. **Disable Vision Analysis** if not needed (saves OpenAI costs)
2. **Use GPT-4o-mini** for embeddings (cheaper)
3. **Monitor usage** on Railway/Render dashboards
4. **Set up alerts** for usage limits

---

## Troubleshooting

### Backend Issues

1. **Health check fails**:
   - Check logs in Railway/Render dashboard
   - Verify environment variables are set
   - Check if port is correctly configured

2. **ChromaDB errors**:
   - Ensure storage directory exists
   - Check file permissions
   - Verify ChromaDB path in environment

3. **API key errors**:
   - Verify `OPENAI_API_KEY` is set correctly
   - Check for typos in environment variables

### Frontend Issues

1. **CORS errors**:
   - Update CORS settings in backend
   - Verify `NEXT_PUBLIC_API_BASE` is correct
   - Check browser console for errors

2. **API connection fails**:
   - Verify backend URL is correct
   - Check if backend is running (visit `/health` endpoint)
   - Check Railway/Render logs

### Deployment Issues

1. **Build fails**:
   - Check build logs in Vercel/Railway/Render
   - Verify all dependencies are in `requirements.txt` and `package.json`
   - Check for syntax errors

2. **Docker build fails**:
   - Verify Dockerfile is correct
   - Check if all paths are correct
   - Ensure all required files are in the repository

---

## Updating Your Deployment

### Backend Updates
1. Push changes to GitHub
2. Railway/Render will automatically redeploy
3. Check logs to ensure successful deployment

### Frontend Updates
1. Push changes to GitHub
2. Vercel will automatically redeploy
3. Check build logs in Vercel dashboard

---

## Custom Domain (Optional)

### Vercel Custom Domain
1. Go to Vercel project settings
2. Click "Domains"
3. Add your custom domain
4. Follow DNS configuration instructions

### Railway Custom Domain
1. Go to Railway project settings
2. Click "Settings" → "Domains"
3. Add your custom domain
4. Configure DNS records

---

## Monitoring

- **Railway**: Built-in metrics and logs
- **Render**: Built-in metrics and logs
- **Vercel**: Built-in analytics and logs

Check these dashboards regularly to monitor:
- API response times
- Error rates
- Resource usage
- Deployment status

---

## Support

If you encounter issues:
1. Check the logs in your deployment platform
2. Review this guide
3. Check GitHub issues
4. Review platform-specific documentation
