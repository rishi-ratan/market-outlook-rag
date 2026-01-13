# Fix Railway Build Error: "Error creating build plan with Railpack"

## Problem
Railway is trying to use Railpack (buildpacks) instead of Docker, causing the build to fail.

## Solution

### Option 1: Configure in Railway UI (Recommended)

1. **Go to your Railway project**
2. **Click on your service** (market-outlook-rag)
3. **Go to Settings** → **Source**
4. **Configure the following**:
   - **Build Command**: Leave **empty** (Docker handles this)
   - **Start Command**: Leave **empty** (Dockerfile CMD handles this)
   - **Dockerfile Path**: `apps/api/Dockerfile`
   - **Root Directory**: `.` (root of repository)
   - **Build Method**: Select **"Dockerfile"** explicitly (if option available)

5. **Save changes** and redeploy

### Option 2: Delete and Recreate Service

If Option 1 doesn't work:

1. **Delete the current service** in Railway
2. **Create a new service**:
   - Click "New" → "GitHub Repo"
   - Select your repository
   - **Before deploying**, go to Settings → Source
   - Set Dockerfile Path: `apps/api/Dockerfile`
   - Ensure "Use Docker" is enabled

### Option 3: Use Railway CLI

If you have Railway CLI installed:

```bash
railway link
railway variables set RAILWAY_DOCKERFILE_PATH=apps/api/Dockerfile
railway up
```

### Option 4: Move Dockerfile to Root (Alternative)

If the above don't work, you can temporarily move the Dockerfile to the root:

```bash
# In your repo root
cp apps/api/Dockerfile ./Dockerfile
```

Then update the Dockerfile paths:
- Change `COPY apps/api/requirements.txt` to `COPY apps/api/requirements.txt`
- Keep all other paths relative to root

After moving, Railway should auto-detect it.

## Verify Configuration

After applying the fix:

1. **Check the build logs** - Should show "Building Docker image" instead of "Using Railpack"
2. **Build should succeed** - The Docker build process should complete
3. **Deployment should start** - After build completes

## Common Issues

### Still seeing Railpack error?
- Make sure `railway.json` exists in the root
- Check that `nixpacks.toml` exists (prevents Railpack from being used)
- Verify Dockerfile path is correct in Railway settings

### Build succeeds but app doesn't start?
- Check environment variables are set
- Verify `PORT` environment variable (Railway sets this automatically)
- Check deploy logs for startup errors

### Need more help?
- Check Railway logs: Service → Deployments → Click on deployment → View logs
- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app
