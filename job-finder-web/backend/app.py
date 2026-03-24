"""
Job Finder Web App - Main Application

Optimized for fast startup - lazy imports for heavy modules
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pathlib import Path
import logging

# Import config first (lightweight)
from backend.config import DEBUG, HOST, PORT

# Setup logging immediately
from backend.logging_config import setup_logging
logger = setup_logging(DEBUG)

# Import database dependency
from backend.database import get_db

logger.info("Starting Job Finder Web App...")

# Create FastAPI app (fast)
app = FastAPI(
    title="Job Finder Web App",
    description="Multi-candidate job search automation",
    version="1.0.0",
    debug=DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent.parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Setup templates - use simple directory path (compatible with latest Starlette)
templates_path = Path(__file__).parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))

logger.info("FastAPI app created")


@app.on_event("startup")
async def startup_event():
    """Run on application startup - lazy initialization"""
    logger.info(f"Initializing database...")
    
    # Import and initialize database (imports all models)
    from backend.database import init_db
    init_db()
    
    logger.info("Database initialized")
    logger.info(f"Job Finder Web App ready on http://{HOST}:{PORT}")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal error: {exc}")
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)


# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    """Home page - Dashboard"""
    from backend.models.candidate import Candidate
    from backend.models.job import Job
    from backend.models.job import JobApplication
    
    # Get counts
    candidate_count = db.query(Candidate).filter(Candidate.is_active == True).count()
    job_count = db.query(Job).count()
    priority_jobs = db.query(Job).filter(Job.ai_remote_score >= 80).count()
    application_count = db.query(JobApplication).count()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "candidate_count": candidate_count,
        "job_count": job_count,
        "priority_jobs": priority_jobs,
        "application_count": application_count
    })


# Import routes on-demand (not at startup)
def get_candidate_router():
    from backend.routes import candidates
    return candidates.router


def get_health_router():
    from backend.routes import health
    return health.router


# LLM router - LAZY LOAD to avoid 45s LiteLLM import on startup
# The llm_test.py file imports litellm INSIDE the endpoint, not at module level
# So just importing the router is fast!
def get_llm_router():
    from backend.routes import llm_test
    return llm_test.router


def get_llm_config_router():
    from backend.routes import llm_config
    return llm_config.router


def get_documents_router():
    from backend.routes import documents
    return documents.router


def get_candidate_parser_router():
    from backend.routes import candidate_parser
    return candidate_parser.router


def get_llm_functions_router():
    from backend.routes import llm_functions
    return llm_functions.router


def get_chat_router():
    from backend.routes import chat
    return chat.router


def get_skills_router():
    from backend.routes import skills
    return skills.router


def get_preferences_router():
    from backend.routes import preferences
    return preferences.router


def get_platform_accounts_router():
    from backend.routes import platform_accounts
    return platform_accounts.router


# Register routes
app.include_router(get_candidate_router(), prefix="/candidates", tags=["Candidates"])
app.include_router(get_health_router(), prefix="/api", tags=["Health"])
app.include_router(get_llm_router(), prefix="/api/llm", tags=["LLM Test"])
app.include_router(get_llm_config_router(), prefix="/settings", tags=["LLM Config"])
app.include_router(get_documents_router(), prefix="/candidates", tags=["Documents"])
app.include_router(get_candidate_parser_router(), prefix="/candidates", tags=["Candidate Parser"])
app.include_router(get_llm_functions_router(), tags=["LLM Functions"])
app.include_router(get_chat_router(), tags=["AI Chat"])
app.include_router(get_skills_router(), tags=["Skills"])
app.include_router(get_preferences_router(), tags=["Preferences"])
app.include_router(get_platform_accounts_router(), tags=["Platform Accounts"])


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on http://{HOST}:{PORT}")
    uvicorn.run(
        "backend.app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )
