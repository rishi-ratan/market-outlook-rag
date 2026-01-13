# Vercel Deployment Fix Guide

## Common Issues and Solutions

### Issue 1: 404 Error or Build Fails

**Symptoms:**
- Getting 404 on all routes
- Build fails in Vercel dashboard
- "Page not found" errors

**Solution:**

1. **Check Root Directory in Vercel:**
   - Go to Vercel Dashboard → Your Project → **Settings** → **General**
   - **Root Directory**: Must be set to `apps/web` ⚠️
   - If it's set to `.` (root), change it to `apps/web`
   - Save and redeploy

2. **Verify Project Structure:**
   - Vercel should see `package.json` in the root directory (`apps/web/package.json`)
   - Vercel should see `app/` directory (`apps/web/app/`)
   - Vercel should see `next.config.ts` (`apps/web/next.config.ts`)

3. **Check Build Logs:**
   - Go to Deployments → Click on failed deployment → View Build Logs
   - Look for specific errors (TypeScript errors, missing dependencies, etc.)

### Issue 2: Environment Variables Not Set

**Symptoms:**
- App loads but API calls fail
- Console shows "Failed to fetch"
- Network errors in browser

**Solution:**

1. **Set Environment Variable:**
   - Go to Vercel Dashboard → Your Project → **Settings** → **Environment Variables**
   - Add: `NEXT_PUBLIC_API_BASE`
   - Value: Your backend URL (e.g., `https://your-backend.railway.app` or `https://your-backend.onrender.com`)
   - **Important**: Select all environments (Production, Preview, Development)
   - Save

2. **Redeploy:**
   - Go to Deployments → Click "..." → Redeploy
   - Or push a new commit to trigger auto-deploy

### Issue 3: Build Command Fails

**Symptoms:**
- Build fails with TypeScript errors
- Build fails with missing dependencies
- Build times out

**Solution:**

1. **Check Build Logs:**
   - Look for specific error messages
   - Common issues:
     - TypeScript errors → Fix in code
     - Missing dependencies → Check `package.json`
     - Build timeout → Optimize build or upgrade plan

2. **Test Build Locally:**
   ```bash
   cd apps/web
   npm install
   npm run build
   ```
   - If local build fails, fix those errors first
   - Then push and redeploy

### Issue 4: Wrong Branch Connected

**Symptoms:**
- Changes not deploying
- Old version still showing

**Solution:**

1. **Check Git Connection:**
   - Go to Settings → Git
   - Verify correct repository is connected
   - Verify correct branch is set (should be `rag-docs` or `main`)
   - If wrong, disconnect and reconnect

### Issue 5: Vercel.json Conflicts

**Symptoms:**
- Build succeeds but app doesn't work
- Configuration conflicts

**Solution:**

1. **Simplify vercel.json:**
   - Vercel auto-detects Next.js, so minimal config is needed
   - Current `vercel.json` should be fine, but if issues persist, try removing it

2. **Or Remove vercel.json:**
   - Vercel can auto-detect Next.js without it
   - Delete `apps/web/vercel.json` if it's causing issues
   - Make sure Root Directory is set to `apps/web` in dashboard

## Step-by-Step Fix

### 1. Verify Vercel Project Settings

1. Go to [vercel.com](https://vercel.com) → Your Project
2. Click **Settings** → **General**
3. Verify:
   - **Root Directory**: `apps/web` ⚠️ **MOST IMPORTANT**
   - **Framework Preset**: Next.js
   - **Build Command**: `npm run build` (or leave default)
   - **Output Directory**: `.next` (or leave default)
   - **Install Command**: `npm install` (or leave default)

### 2. Set Environment Variables

1. Go to **Settings** → **Environment Variables**
2. Add:
   - **Key**: `NEXT_PUBLIC_API_BASE`
   - **Value**: Your backend URL
   - **Environments**: Select all (Production, Preview, Development)
3. Save

### 3. Check Git Connection

1. Go to **Settings** → **Git**
2. Verify:
   - Correct repository: `rishi-ratan/market-outlook-rag`
   - Correct branch: `rag-docs` (or your branch)
   - Auto-deploy is enabled

### 4. Redeploy

1. Go to **Deployments** tab
2. Click **"..."** (three dots) on latest deployment
3. Click **Redeploy**
4. Or push a new commit to trigger auto-deploy

### 5. Check Build Logs

1. Click on the deployment
2. Check **Build Logs** for errors
3. Common errors:
   - **"Cannot find module"** → Missing dependency in `package.json`
   - **TypeScript errors** → Fix in code
   - **"Command failed"** → Check build command

## Quick Test

After fixing, test your deployment:

1. Visit your Vercel URL
2. Open browser console (F12)
3. Check for errors:
   - No 404s
   - No "Failed to fetch" errors
   - API calls should work
4. Test the app:
   - Upload a document
   - Ask a question
   - Check if backend responds

## Still Not Working?

1. **Check Vercel Logs**: Deployments → Click deployment → View logs
2. **Check Browser Console**: F12 → Console tab → Look for errors
3. **Verify Backend**: Make sure backend is running and accessible
4. **Test Locally**: Run `npm run build` in `apps/web` to catch errors early

## Common Configuration Mistakes

❌ **Wrong**: Root Directory = `.` (root of repo)
✅ **Correct**: Root Directory = `apps/web`

❌ **Wrong**: Environment variable not set
✅ **Correct**: `NEXT_PUBLIC_API_BASE` set with backend URL

❌ **Wrong**: Wrong branch connected
✅ **Correct**: Branch matches your active branch (`rag-docs`)

❌ **Wrong**: vercel.json in wrong location
✅ **Correct**: vercel.json in `apps/web/` directory
