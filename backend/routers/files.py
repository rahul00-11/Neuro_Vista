from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional
import os, uuid
from models.database import save_file, get_patient
from config import UPLOAD_FOLDER

router = APIRouter(prefix="/files", tags=["Files"])
ALLOWED = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}

@router.post("/upload/{patient_id}")
async def upload(patient_id: int, file: UploadFile = File(...),
                 file_type: str = Form("general")):
    if not get_patient(patient_id):
        raise HTTPException(404, "Patient not found")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"File type '{ext}' not allowed")
    folder = os.path.join(UPLOAD_FOLDER, str(patient_id), file_type)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        f.write(await file.read())
    save_file(patient_id, file.filename, path, file_type)
    return {"message": "Uploaded", "original_name": file.filename, "file_type": file_type}
