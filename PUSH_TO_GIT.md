# How to Push Changes to GitHub

## ⚠️ Important: I Don't Push to Git

I can only **create and modify files** on your computer. **You need to push them to GitHub yourself.**

## Step-by-Step: Push Your Changes

### 1. Open Terminal/PowerShell

Navigate to your project directory:

```powershell
cd C:\Users\rishi\OneDrive\Learning\CodingPrep\market-outlook-rag
```

### 2. Check What Needs to Be Pushed

```powershell
git status
```

This will show you:
- Files that are **modified** (red)
- Files that are **new** (untracked)
- Files that are **staged** (green)

### 3. Add All Changes

```powershell
git add .
```

This stages all modified and new files.

### 4. Commit Changes

```powershell
git commit -m "Add deployment configs, fix errors, and update Vercel setup"
```

### 5. Push to GitHub

```powershell
git push origin main
```

Or if you're on a different branch (like `rag-docs`):

```powershell
git push origin rag-docs
```

## Files That Should Be Pushed

Make sure these files are included:

### New Files Created:
- ✅ `apps/web/vercel.json`
- ✅ `railway.json`
- ✅ `nixpacks.toml`
- ✅ `render.yaml`
- ✅ `DEPLOYMENT.md`
- ✅ `DEPLOYMENT_ALTERNATIVES.md`
- ✅ `RENDER_SETUP.md`
- ✅ `VERCEL_FIX.md`
- ✅ `QUICK_DEPLOY.md`
- ✅ `RAILWAY_FIX.md`
- ✅ `.vercelignore`
- ✅ `.gitignore` (updated)

### Modified Files:
- ✅ `apps/web/app/page.tsx` (fixed errors)
- ✅ `apps/api/Dockerfile` (updated)
- ✅ `apps/api/main.py` (CORS fixes)
- ✅ `README.md` (deployment section)

## After Pushing

### Frontend (Vercel):
1. **Vercel will auto-deploy** when you push (if auto-deploy is enabled)
2. **Or manually redeploy**: Vercel Dashboard → Deployments → Redeploy
3. **Check**: Make sure Root Directory is set to `apps/web`

### Backend (Railway/Render):
**You DON'T need to redeploy backend** unless:
- You changed backend code (`apps/api/main.py`)
- You changed `Dockerfile`
- You changed `requirements.txt`

**If you only changed frontend files**, backend stays the same.

## Verify Push Was Successful

1. **Check GitHub**: Go to your repo on GitHub.com
2. **Verify files**: Make sure all the new files appear
3. **Check Vercel**: Go to Vercel Dashboard → Your Project → Deployments
4. **Look for new deployment**: Should show "Deployed from GitHub" with your commit message

## Troubleshooting

### "Nothing to commit"
- All changes are already committed
- Check if you're in the right directory
- Run `git status` to see current state

### "Branch is ahead"
- You have local commits that aren't pushed
- Run `git push origin main` (or your branch name)

### "Permission denied"
- Check your GitHub credentials
- May need to authenticate: `gh auth login` (if using GitHub CLI)
- Or use HTTPS with personal access token

### Vercel Still Shows 404 After Push
1. **Check Root Directory**: Must be `apps/web`
2. **Check Environment Variables**: `NEXT_PUBLIC_API_BASE` must be set
3. **Check Build Logs**: Vercel Dashboard → Deployment → Build Logs
4. **Redeploy manually**: Sometimes auto-deploy doesn't trigger

## Quick Command Reference

```powershell
# Check status
git status

# Add all changes
git add .

# Commit
git commit -m "Your commit message"

# Push to GitHub
git push origin main

# Or if on different branch
git push origin rag-docs
```

## Need Help?

If you're still getting 404:
1. Check Vercel build logs for errors
2. Verify Root Directory is `apps/web`
3. Make sure `NEXT_PUBLIC_API_BASE` is set
4. Check browser console (F12) for errors
