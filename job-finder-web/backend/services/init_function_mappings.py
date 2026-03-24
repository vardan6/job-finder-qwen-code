#!/usr/bin/env python3
"""
Initialize LLM Function Mappings

Run this to populate default function-to-LLM mappings.
"""
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models.document import LLMFunctionMapping
from backend.models.llm_provider import LLMProvider, LLMModel


FUNCTION_MAPPINGS = [
    {
        "function_name": "job_title_parser",
        "display_name": "Job Title Parser (AI)",
        "description": "Extracts job titles from uploaded documents"
    },
    {
        "function_name": "skill_extractor",
        "display_name": "Skill Extractor (AI)",
        "description": "Extracts technical skills from resumes and profiles"
    },
    {
        "function_name": "job_scorer",
        "display_name": "Job Scorer (AI)",
        "description": "Scores job postings for remote-work compatibility"
    },
    {
        "function_name": "resume_matcher",
        "display_name": "Resume-Job Matcher (AI)",
        "description": "Compares candidate profile against job descriptions"
    },
    {
        "function_name": "ai_chat",
        "display_name": "AI Chat Assistant",
        "description": "General-purpose AI chat interface"
    }
]


def init_function_mappings(db: Session):
    """Initialize default function-to-LLM mappings"""
    
    # Get default Ollama model
    ollama = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
    default_model_id = None
    
    if ollama:
        default_model = db.query(LLMModel).filter(
            LLMModel.provider_id == ollama.id,
            LLMModel.is_default_for_provider == True
        ).first()
        if default_model:
            default_model_id = default_model.id
            print(f"✅ Found default Ollama model: {default_model.model_name}")
    
    for func_data in FUNCTION_MAPPINGS:
        existing = db.query(LLMFunctionMapping).filter(
            LLMFunctionMapping.function_name == func_data["function_name"]
        ).first()
        
        if not existing:
            mapping = LLMFunctionMapping(
                function_name=func_data["function_name"],
                display_name=func_data["display_name"],
                model_id=default_model_id  # Set to default Ollama model
            )
            db.add(mapping)
            print(f"✅ Created mapping: {func_data['display_name']}")
        else:
            print(f"ℹ️  Mapping already exists: {func_data['display_name']}")
    
    db.commit()
    print("\n✅ LLM function mappings initialized successfully!")
    if default_model_id:
        print(f"   All functions will use Ollama by default")
    else:
        print(f"   No Ollama model found - functions will need manual configuration")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        init_function_mappings(db)
    finally:
        db.close()
