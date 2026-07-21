"""
Routes Package
"""
from backend.routes.candidates import router as get_candidates_router
from backend.routes.health import router as get_health_router
from backend.routes.llm_test import router as get_llm_router
from backend.routes.llm_config import router as get_llm_config_router
from backend.routes.documents import router as get_documents_router
from backend.routes.candidate_parser import router as get_candidate_parser_router
from backend.routes.chat import router as get_chat_router
from backend.routes.skills import router as get_skills_router
from backend.routes.skills_manager import router as get_skills_manager_router
from backend.routes.preferences import router as get_preferences_router
from backend.routes.platform_accounts import router as get_platform_accounts_router
from backend.routes.jobs import router as get_jobs_router
from backend.routes.ai_settings import router as get_ai_settings_router
from backend.routes.ai_secrets import router as get_ai_secrets_router
from backend.routes.ai_sessions import router as get_ai_sessions_router
from backend.routes.ai_tools import router as get_ai_tools_router

__all__ = [
    'get_candidates_router',
    'get_health_router',
    'get_llm_router',
    'get_llm_config_router',
    'get_documents_router',
    'get_candidate_parser_router',
    'get_chat_router',
    'get_skills_router',
    'get_skills_manager_router',
    'get_preferences_router',
    'get_platform_accounts_router',
    'get_jobs_router',
    'get_ai_settings_router',
    'get_ai_secrets_router',
    'get_ai_sessions_router',
    'get_ai_tools_router',
]
