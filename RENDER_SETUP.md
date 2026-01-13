# Render Deployment Guide (Easiest Option)

## Why Render?

- ✅ **Easiest setup** - Just connect GitHub and deploy
- ✅ **Free tier** - 750 hours/month
- ✅ **Auto-detects Dockerfile** - No complex config needed
- ✅ **Persistent storage** - Your data stays between deployments
- ⚠️ **Sleeps after 15 min** - Takes ~30 seconds to wake up (free tier only)

---

## Step-by-Step Setup

### 1. Sign Up for Render

1. Go to [render.com](https://render.com)
2. Click **"Get Started for Free"**
3. Sign up with **GitHub** (easiest option)

### 2. Create Web Service

1. Click **"New +"** button (top right)
2. Select **"Web Service"**
3. Click **"Connect account"** next to GitHub (if not already connected)
4. Authorize Render to access your repositories
5. **Select your repository**: `market-outlook-rag`
6. Click **"Connect"**

### 3. Configure the Service

Fill in these settings:

**Basic Settings:**
- **Name**: `market-outlook-rag-api` (or any name you like)
- **Region**: Choose closest to you (e.g., `Oregon (US West)`)
- **Branch**: `main` (or your default branch)
- **Root Directory**: Leave **empty** (or `.`)

**Build & Deploy:**
- **Environment**: Select **"Docker"** (important!)
- **Dockerfile Path**: `apps/api/Dockerfile`
- **Docker Context**: `.` (root directory)

**Plan:**
- **Plan**: Select **"Free"** (or upgrade if you want)

### 4. Add Environment Variables

Click **"Advanced"** → **"Add Environment Variable"** and add:

```
OPENAI_API_KEY = your-openai-api-key-here
TOGETHER_API_KEY = your-together-api-key-here (optional)
ALLOWED_ORIGINS = http://localhost:3000
```

**Note**: You'll update `ALLOWED_ORIGINS` later with your Vercel URL.

### 5. Deploy

1. Click **"Create Web Service"** (bottom)
2. Wait for deployment (~5-10 minutes for first build)
3. Watch the build logs - you should see Docker building
4. When done, you'll see: **"Your service is live at https://..."**

### 6. Get Your Backend URL

1. Copy the URL (e.g., `https://market-outlook-rag-api.onrender.com`)
2. Test it: Visit `https://your-url.onrender.com/health`
3. Should return: `{"status": "ok"}`

### 7. Update CORS (After Frontend is Deployed)

Once your frontend is on Vercel:

1. Go back to Render → Your service → **Environment**
2. Click **"Add Environment Variable"**
3. Update `ALLOWED_ORIGINS`:
   ```
   ALLOWED_ORIGINS = https://your-app.vercel.app,http://localhost:3000
   ```
4. **Save Changes** (Render will auto-redeploy)

---

## Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com)
2. **Add New Project** → Import your GitHub repo
3. Configure:
   - **Root Directory**: `apps/web`
   - **Framework**: Next.js (auto-detected)
4. Add environment variable:
   - `NEXT_PUBLIC_API_BASE` = `https://your-render-url.onrender.com`
5. **Deploy**

---

## Troubleshooting

### Build Fails?

- Check build logs in Render dashboard
- Verify Dockerfile path is correct: `apps/api/Dockerfile`
- Make sure Docker Context is `.` (root)

### Service Sleeps?

- Free tier sleeps after 15 minutes of inactivity
- First request takes ~30 seconds to wake up
- Upgrade to paid plan for always-on (starts at $7/month)

### CORS Errors?

- Make sure `ALLOWED_ORIGINS` includes your Vercel URL
- No spaces in the comma-separated list
- Format: `https://app.vercel.app,http://localhost:3000`

### Health Check Fails?

- Check service logs in Render
- Verify environment variables are set
- Check if port is correctly configured (Render sets `PORT` automatically)

---

## Cost Estimate

**Free Tier:**
- 750 hours/month
- Sleeps after 15 min inactivity
- **Total: $0/month**

**Starter Plan ($7/month):**
- Always on
- No sleep
- Better performance

---

## Next Steps

1. ✅ Deploy backend to Render
2. ✅ Deploy frontend to Vercel
3. ✅ Update `ALLOWED_ORIGINS` with Vercel URL
4. ✅ Test your app!

**That's it!** Much simpler than Railway. 🎉
