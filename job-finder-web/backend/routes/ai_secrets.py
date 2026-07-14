from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.ai_secret_store import SecretStore

router = APIRouter()


@router.get("/api/llm-secrets/{secret_ref}")
async def get_secret_status(secret_ref: str) -> dict[str, object]:
    store = SecretStore()
    clean_ref = secret_ref.strip()
    if not clean_ref:
        raise HTTPException(status_code=400, detail="secret_ref is required")
    return {"secret_ref": clean_ref, "has_secret": store.has_secret(clean_ref)}


@router.put("/api/llm-secrets/{secret_ref}")
async def put_secret(secret_ref: str, payload: dict[str, str]) -> JSONResponse:
    clean_ref = secret_ref.strip()
    if not clean_ref:
        raise HTTPException(status_code=400, detail="secret_ref is required")
    secret_value = str(payload.get("secret_value", "")).strip()
    if not secret_value:
        raise HTTPException(status_code=400, detail="secret_value is required")
    store = SecretStore()
    store.set_secret(clean_ref, secret_value)
    return JSONResponse({"ok": True, "secret_ref": clean_ref, "has_secret": True})


@router.delete("/api/llm-secrets/{secret_ref}")
async def delete_secret(secret_ref: str) -> JSONResponse:
    clean_ref = secret_ref.strip()
    if not clean_ref:
        raise HTTPException(status_code=400, detail="secret_ref is required")
    store = SecretStore()
    store.delete_secret(clean_ref)
    return JSONResponse({"ok": True, "secret_ref": clean_ref, "has_secret": False})
