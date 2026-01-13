# Fix Vercel 404 Error

## Problem
You're getting a 404 error on Vercel, likely because:
1. Latest code changes weren't pushed to GitHub
2. Vercel is deploying from wrong directory
3. Environment variables aren't set
4. Build is failing

## Solution

### Step 1: Push Latest Changes to GitHub

**IMPORTANT**: Vercel deploys from your GitHub repo, so you need to push all the latest files:

```bash
# Make sure you're in the repo root
cd market-outlook-rag

# Check what files need to be committed
git status

# Add all new/modified files
git add .

# Commit
git commit -m "Add deployment configurations and fix errors"

# Push to GitHub
git push origin main
# (or git push origin rag-docs if that's your branch)
```

### Step 2: Configure Vercel Project Settings

1. **Go to Vercel Dashboard** → Your Project → **Settings**

2. **General Settings**:
   - **Root Directory**: Set to `apps/web`
   - **Framework Preset**: Next.js
   - **Build Command**: `npm run build` (or leave default)
   - **Output Directory**: `.next` (or leave default)
   - **Install Command**: `npm install` (or leave default)

3. **Environment Variables**:
   - Go to **Settings** → **Environment Variables**
   - Add: `NEXT_PUBLIC_API_BASE`
   - Value: Your backend URL (e.g., `https://your-backend.onrender.com` or `https://your-backend.railway.app`)
   - **Important**: Make sure to select **Production**, **Preview**, and **Development** environments

### Step 3: Redeploy

1. **Go to Deployments tab**
2. Click **"..."** (three dots) on the latest deployment
3. Click **"Redeploy"**
4. Or push a new commit to trigger auto-deploy

### Step 4: Check Build Logs

1. Click on the deployment
2. Check **Build Logs** for errors
3. Common issues:
   - Build fails → Check logs for missing dependencies
   - 404 on all routes → Root directory might be wrong
   - API calls fail → Environment variable not set

## Common Issues

### Issue 1: Wrong Root Directory

**Symptom**: 404 on all pages, build succeeds but nothing works

**Fix**:
- Go to Settings → General
- Set **Root Directory** to `apps/web`
- Save and redeploy

### Issue 2: Environment Variable Not Set

**Symptom**: API calls fail, console shows "Failed to fetch"

**Fix**:
- Go to Settings → Environment Variables
- Add `NEXT_PUBLIC_API_BASE` with your backend URL
- **Important**: Variables starting with `NEXT_PUBLIC_` must be set in Vercel
- Redeploy after adding

### Issue 3: Build Fails

**Symptom**: Deployment shows "Build Failed"

**Fix**:
- Check build logs
- Common causes:
  - Missing dependencies in `package.json`
  - TypeScript errors
  - Missing files
- Fix errors and push again

### Issue 4: 404 on Specific Routes

**Symptom**: Homepage works but other routes 404

**Fix**:
- This is normal for Next.js App Router
- Make sure you're using the correct routes
- Check `app/` directory structure

## Quick Checklist

- [ ] Pushed latest code to GitHub
- [ ] Root Directory set to `apps/web` in Vercel
- [ ] `NEXT_PUBLIC_API_BASE` environment variable set
- [ ] Backend is deployed and accessible
- [ ] Redeployed after configuration changes
- [ ] Checked build logs for errors

## Verify It's Working

1. **Visit your Vercel URL** (e.g., `https://your-app.vercel.app`)
2. **Open browser console** (F12)
3. **Check for errors**:
   - No CORS errors
   - API calls succeed
   - No 404s in network tab
4. **Test the app**:
   - Upload a document
   - Ask a question
   - Check if backend responds

## Still Not Working?

1. **Check Vercel logs**: Deployments → Click deployment → View logs
2. **Check browser console**: F12 → Console tab
3. **Check network tab**: F12 → Network tab → Look for failed requests
4. **Verify backend**: Visit `https://your-backend-url/health` directly

## Need Help?

- Vercel logs will show the exact error
- Check the browser console for client-side errors
- Verify your backend is running and accessible
