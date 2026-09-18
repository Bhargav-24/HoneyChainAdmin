# HoneyChain Admin

The admin project contains the private operations desk used to review beekeeper applications and update batch statuses.

## Structure

- `requests/` - admin operations desk HTML, JavaScript, and CSS
- `.venv/` - admin-local Python environment
- `requirements.txt` - reserved for admin-only Python dependencies

The FastAPI backend serves the desk at `/requests` and serves its assets from `/assets/requests/`.

## Setup

From the repository root:

```powershell
cd admin
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start the main application from `backend/` as documented in [backend/README.md](../backend/README.md).

## Dynamic hosting

This project includes a Render blueprint at [`render.yaml`](render.yaml). In Render, create a new Blueprint Instance from the repository and enter the Supabase values when prompted. The service runs with Render's injected `PORT` and binds to `0.0.0.0`.

For another host, use the same commands from the `admin/backend` directory:

```powershell
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $env:PORT
```

Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` as server-side environment variables. Do not commit `.env` or expose the service role key in frontend code.
