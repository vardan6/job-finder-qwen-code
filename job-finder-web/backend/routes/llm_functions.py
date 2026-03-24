"""
LLM Function Mappings Routes - Map functionalities to specific LLM models
"""
from pathlib import Path
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.models.document import LLMFunctionMapping
from backend.models.llm_provider import LLMProvider, LLMModel


router = APIRouter(tags=["LLM Functions"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


# ============ HTML Pages ============

@router.get("/settings/functions", response_class=HTMLResponse)
async def get_llm_functions(request: Request, db: Session = Depends(get_db)):
    """LLM Functions configuration page"""
    # Get all function mappings with their models
    mappings = db.query(LLMFunctionMapping).order_by(LLMFunctionMapping.function_name).all()

    # Get all providers with their models
    providers = db.query(LLMProvider).filter(LLMProvider.is_active == True).all()

    return templates.TemplateResponse(
        "settings/functions.html",
        {
            "request": request,
            "mappings": mappings,
            "providers": providers,
        }
    )


# ============ API Endpoints for Inline Model Selectors ============

@router.get("/api/llm/models")
async def get_available_models(db: Session = Depends(get_db)):
    """
    Get all available LLM models grouped by provider.
    Used by inline model selectors throughout the app.
    """
    providers = db.query(LLMProvider).filter(LLMProvider.is_active == True).all()
    
    result = []
    for provider in providers:
        provider_data = {
            "name": provider.name,
            "models": []
        }
        for model in provider.models:
            if model.is_active:
                provider_data["models"].append({
                    "id": model.id,
                    "name": model.model_name,
                    "display_name": model.display_name or model.model_name,
                    "is_default": model.is_default_for_provider
                })
        result.append(provider_data)
    
    return {"providers": result}


@router.get("/api/llm/function/{function_name}/model")
async def get_function_model(
    function_name: str,
    db: Session = Depends(get_db)
):
    """Get the currently configured model for a specific function"""
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name,
        LLMFunctionMapping.is_active == True
    ).first()
    
    if not mapping or not mapping.model_id:
        return {
            "function_name": function_name,
            "model_id": None,
            "model": None
        }
    
    model = mapping.model
    return {
        "function_name": function_name,
        "model_id": mapping.model_id,
        "model": {
            "id": model.id,
            "name": model.model_name,
            "provider_name": model.provider.name if model.provider else None
        }
    }


@router.post("/api/llm/function/{function_name}/model")
async def set_function_model(
    function_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Set the model for a specific function (updates LLMFunctionMapping)"""
    try:
        body = await request.json()
        model_id = body.get("model_id")
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    # Get or create mapping
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name
    ).first()
    
    if mapping:
        mapping.model_id = model_id
    else:
        # Create new mapping
        display_names = {
            "job_title_parser": "Job Title Parser",
            "skill_extractor": "Skill Extractor",
            "job_scorer": "Job Scorer",
            "resume_matcher": "Resume Matcher",
            "ai_chat": "AI Chat",
        }
        mapping = LLMFunctionMapping(
            function_name=function_name,
            display_name=display_names.get(function_name, function_name),
            model_id=model_id
        )
        db.add(mapping)
    
    db.commit()
    
    return {
        "success": True,
        "function_name": function_name,
        "model_id": model_id
    }
