# Deploying to Railway

1. Create a new Railway project.
2. Select "Deploy from GitHub" and connect this folder.
3. Railway will auto-detect:
   - Procfile
   - Python runtime
   - FastAPI server
4. After deploy, copy your Railway domain:
   https://your-app-id.up.railway.app
5. In your frontend `.env`:
   VITE_AUDIT_BACKEND=https://your-app-id.up.railway.app
