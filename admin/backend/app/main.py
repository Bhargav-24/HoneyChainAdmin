from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.router import router

app = FastAPI(title='HoneyChain Admin Backend')

BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_DIR = BASE_DIR.parent

app.include_router(router)
app.mount('/assets', StaticFiles(directory=ADMIN_DIR), name='assets')
