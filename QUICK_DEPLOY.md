# Quick Deployment Guide

## 🚀 Fastest Path to Production

### 1. Backend (Railway) - 5 minutes

1. Go to [railway.app](https://railway.app) and sign up
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Add these environment variables:
   ```
   OPENAI_API_KEY=your_key_here
   TOGETHER_API_KEY=your_key_here (optional)
   ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
   ```
5. Wait for deployment (~5 minutes)
6. Copy your Railway URL (e.g., `https://your-app.railway.app`)

### 2. Frontend (Vercel) - 3 minutes

1. **Push your code to GitHub first!** (Vercel deploys from GitHub)
   ```bash
   git add .
   git commit -m "Prepare for Vercel deployment"
   git push origin main
   ```

2. Go to [vercel.com](https://vercel.com) and sign up
3. Click "Add New Project" → Import your GitHub repo
4. **Configure**:
   - **Root Directory**: `apps/web` ⚠️ **IMPORTANT!**
   - **Framework**: Next.js (auto-detected)
   - **Build Command**: `npm run build` (default)
   - **Output Directory**: `.next` (default)
5. **Add environment variable**:
   - Go to project → Settings → Environment Variables
   - Add: `NEXT_PUBLIC_API_BASE`
   - Value: `https://your-backend.onrender.com` (or Railway URL)
   - Select: Production, Preview, Development
6. Click "Deploy"
7. Wait for build to complete
8. Done! Your app is live 🎉

**⚠️ If you get 404 errors**: See [VERCEL_FIX.md](./VERCEL_FIX.md)

## 📝 Environment Variables Checklist

### Backend (Railway)
- ✅ `OPENAI_API_KEY` (required)
- ✅ `TOGETHER_API_KEY` (optional)
- ✅ `ALLOWED_ORIGINS` (your Vercel URL + localhost)

### Frontend (Vercel)
- ✅ `NEXT_PUBLIC_API_BASE` (your Railway URL)

## 🔍 Test Your Deployment

1. Visit your Vercel URL
2. Check browser console (F12) for errors
3. Try uploading a PDF
4. Ask a question

## 💰 Cost Estimate

- **Vercel**: Free (unlimited deployments)
- **Railway**: Free tier ($5 credit/month)
- **Total**: $0/month for light usage

## 🆘 Troubleshooting

**Backend not responding?**
- Check Railway logs
- Verify environment variables
- Test `/health` endpoint

**CORS errors?**
- Add your Vercel URL to `ALLOWED_ORIGINS` in Railway
- Redeploy backend

**Frontend can't connect?**
- Verify `NEXT_PUBLIC_API_BASE` in Vercel
- Check if backend is running

For detailed instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md)
