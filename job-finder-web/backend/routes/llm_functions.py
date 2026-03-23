"""
LLM Function Mappings Routes - Map functionalities to specific LLM models
"""
from pathlib import Path
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.document import LLMFunctionMapping
from backend.models.llm_provider import LLMProvider, LLMModel


router = APIRouter(tags=["LLM Functions"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


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


@router.post("/settings/functions/save")
async def save_function_mapping(
    request: Request,
    function_name: str = Form(...),
    model_id: int = Form(None),
    db: Session = Depends(get_db)
):
    """Save function-to-model mapping"""
    # Get or create mapping
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name
    ).first()
    
    if mapping:
        mapping.model_id = model_id
    else:
        # Get function display name
        display_names = {
            "job_title_parser": "Job Title Parser",
            "job_scorer": "Job Scorer (AI)",
            "resume_matcher": "Resume-Job Matcher",
        }
        
        mapping = LLMFunctionMapping(
            function_name=function_name,
            display_name=display_names.get(function_name, function_name),
            model_id=model_id
        )
        db.add(mapping)
    
    db.commit()
    
    return {"success": True, "message": "Mapping saved successfully"}


@router.post("/settings/functions/reset")
async def reset_function_mapping(
    request: Request,
    function_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Reset function mapping to default (Ollama)"""
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Function mapping not found")
    
    # Get default Ollama model
    ollama = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
    if ollama:
        default_model = db.query(LLMModel).filter(
            LLMModel.provider_id == ollama.id,
            LLMModel.is_default_for_provider == True
        ).first()
        mapping.model_id = default_model.id if default_model else None
    else:
        mapping.model_id = None
    
    db.commit()
    
    return {"success": True, "message": "Mapping reset to default"}
