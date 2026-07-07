from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from models.database import init_db
from routers import patients, files
from config import UPLOAD_FOLDER, PORT

app = FastAPI(
    title="NeuroVista AI",
    description="Pediatric Neuro-Ophthalmology AI Platform — Dr. Trupti Kadam Lambat, Little Angels Eye Clinic",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print("🧠 NeuroVista AI v2.0 started")

app.include_router(patients.router, prefix="/api")
app.include_router(files.router,    prefix="/api")

@app.get("/api/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "NeuroVista AI", "version": "2.0.0",
            "clinic": "Little Angels Superspecialty Eye Clinic, Nagpur"}

@app.exception_handler(Exception)
async def global_error(req: Request, exc: Exception):
    print(f"❌ {req.url}: {exc}")
    return JSONResponse(500, {"detail": str(exc)})

# Serve frontend from FastAPI (single deployment on Render)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
