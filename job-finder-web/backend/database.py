"""
Database Configuration
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

# Database URL
DATABASE_URL = "sqlite:///./data/jobs.db"

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables - import all models first"""
    # Import all models to register them with Base
    from backend.models.candidate import Candidate
    from backend.models.job import Job, JobApplication
    from backend.models.supporting import CandidateJobTitle, CandidateSkill, CandidatePreferences
    from backend.models.llm_provider import LLMProvider, LLMModel
    from backend.models.document import CandidateDocument, DocumentSection, DocumentParsePrompt, LLMFunctionMapping

    Base.metadata.create_all(bind=engine)

    # Run migrations after tables are created
    migrate_database()


def migrate_database():
    """Run database migrations for schema updates"""
    from backend.models.llm_provider import LLMProvider, LLMModel
    from backend.models.document import CandidateDocument, DocumentSection, DocumentParsePrompt, LLMFunctionMapping

    # Check if llm_models table exists by querying it
    conn = engine.connect()
    try:
        # Try to query the table to see if it exists
        conn.execute(text("SELECT 1 FROM llm_models LIMIT 1"))
        conn.commit()
    except Exception:
        # Table doesn't exist, create it
        LLMModel.__table__.create(bind=engine)

    # Check if we need to migrate old model_name column
    conn = engine.connect()
    try:
        conn.execute(text("SELECT model_name FROM llm_providers LIMIT 1"))
        conn.commit()
        has_old_column = True
    except Exception:
        has_old_column = False
    finally:
        conn.close()

    if has_old_column:
        # Migrate existing model_name from LLMProvider to LLMModel
        db = SessionLocal()
        try:
            providers = db.query(LLMProvider).all()
            for provider in providers:
                if provider.model_name:
                    # Create default model for this provider
                    model = LLMModel(
                        provider_id=provider.id,
                        model_name=provider.model_name,
                        display_name=provider.model_name,
                        is_default_for_provider=True,
                        is_active=True
                    )
                    db.add(model)

            db.commit()

            # Remove the old model_name column (recreate table without it)
            # For SQLite, we need to recreate the table
            conn = engine.connect()
            conn.execute(text("""
                CREATE TABLE llm_providers_new (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    api_key_encrypted TEXT,
                    api_url VARCHAR,
                    is_global_default BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Copy data from old table
            conn.execute(text("""
                INSERT INTO llm_providers_new (id, name, api_key_encrypted, api_url, is_global_default, is_active, created_at)
                SELECT id, name, api_key_encrypted, api_url, is_global_default, is_active, created_at
                FROM llm_providers
            """))

            # Drop old table and rename new one
            conn.execute(text("DROP TABLE llm_providers"))
            conn.execute(text("ALTER TABLE llm_providers_new RENAME TO llm_providers"))
            conn.commit()
            conn.close()

        except Exception as e:
            db.rollback()
            print(f"Migration warning: {e}")
        finally:
            db.close()

    # Populate default models for providers that don't have any
    populate_default_models()

    # Populate default document parse prompts
    populate_default_parse_prompts()

    # Populate default LLM function mappings
    populate_default_function_mappings()


def populate_default_models():
    """Populate default models for providers that don't have any"""
    from backend.models.llm_provider import LLMProvider, LLMModel
    
    db = SessionLocal()
    try:
        from backend.routes.llm_config import DEFAULT_PROVIDERS

        providers = db.query(LLMProvider).all()
        for provider in providers:
            # Check if provider has any models
            existing_models = db.query(LLMModel).filter(LLMModel.provider_id == provider.id).all()

            # If no models exist, add defaults
            if len(existing_models) == 0 and provider.name in DEFAULT_PROVIDERS:
                for model_name in DEFAULT_PROVIDERS[provider.name]["models"]:
                    model = LLMModel(
                        provider_id=provider.id,
                        model_name=model_name,
                        display_name=model_name,
                        is_default_for_provider=(model_name == DEFAULT_PROVIDERS[provider.name]["models"][0]),
                        is_active=True
                    )
                    db.add(model)
                db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: Could not populate default models: {e}")
    finally:
        db.close()


def populate_default_parse_prompts():
    """Populate default system prompts for document parsing"""
    from backend.models.document import DocumentParsePrompt

    db = SessionLocal()
    try:
        default_prompts = [
            {
                "name": "job_titles_parser",
                "description": "Extract job titles from markdown documents",
                "document_type": "job_titles",
                "prompt_template": """You are a data extraction assistant. Extract all job titles from the following markdown content.

Return a JSON array of job titles with their priority (1=highest, 3=lowest):

[
  {"title": "Job Title Here", "priority": 1, "description": "Optional description if available"},
  ...
]

If priority is not explicitly stated, infer it from context:
- "Staff", "Principal", "Lead", "Architect" → priority 1
- "Senior" → priority 2
- Other → priority 3

Markdown content:
{{content}}""",
                "output_schema": '{"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"}, "priority": {"type": "integer"}, "description": {"type": "string"}}}}',
                "is_system": True
            },
            {
                "name": "profile_parser",
                "description": "Extract profile information (summary, skills, experience, certifications)",
                "document_type": "profile",
                "prompt_template": """You are a data extraction assistant. Extract the following from this markdown profile:

1. **Summary**: 2-3 sentence bio
2. **Skills**: List all technical skills
3. **Experience**: For each role extract: title, company, dates, description
4. **Certifications**: Name, issuer, date if available

Return as JSON:
{
  "summary": "...",
  "skills": [{"name": "Python", "level": "required"}, ...],
  "experience": [{"title": "...", "company": "...", "start": "...", "end": "...", "description": "..."}],
  "certifications": [{"name": "...", "issuer": "...", "date": "..."}]
}

Markdown content:
{{content}}""",
                "output_schema": '{"type": "object", "properties": {"summary": {"type": "string"}, "skills": {"type": "array"}, "experience": {"type": "array"}, "certifications": {"type": "array"}}}',
                "is_system": True
            }
        ]

        for prompt_data in default_prompts:
            existing = db.query(DocumentParsePrompt).filter(
                DocumentParsePrompt.name == prompt_data["name"],
                DocumentParsePrompt.candidate_id.is_(None)
            ).first()

            if not existing:
                prompt = DocumentParsePrompt(
                    name=prompt_data["name"],
                    description=prompt_data["description"],
                    document_type=prompt_data["document_type"],
                    prompt_template=prompt_data["prompt_template"],
                    output_schema=prompt_data["output_schema"],
                    is_system=prompt_data["is_system"]
                )
                db.add(prompt)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: Could not populate default parse prompts: {e}")
    finally:
        db.close()


def populate_default_function_mappings():
    """Populate default LLM function mappings"""
    from backend.models.document import LLMFunctionMapping
    from backend.models.llm_provider import LLMProvider, LLMModel

    db = SessionLocal()
    try:
        default_functions = [
            {"function_name": "job_title_parser", "display_name": "Job Title Parser"},
            {"function_name": "job_scorer", "display_name": "Job Scorer (AI)"},
            {"function_name": "resume_matcher", "display_name": "Resume-Job Matcher"},
        ]

        # Get the default Ollama model for all functions
        default_model = None
        ollama_provider = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
        if ollama_provider:
            default_model = db.query(LLMModel).filter(
                LLMModel.provider_id == ollama_provider.id,
                LLMModel.is_default_for_provider == True
            ).first()

        for func_data in default_functions:
            existing = db.query(LLMFunctionMapping).filter(
                LLMFunctionMapping.function_name == func_data["function_name"]
            ).first()

            if not existing:
                mapping = LLMFunctionMapping(
                    function_name=func_data["function_name"],
                    display_name=func_data["display_name"],
                    model_id=default_model.id if default_model else None
                )
                db.add(mapping)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: Could not populate default function mappings: {e}")
    finally:
        db.close()
