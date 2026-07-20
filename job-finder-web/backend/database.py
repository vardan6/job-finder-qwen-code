"""
Database Configuration
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

# Database URL - use absolute path relative to this file to avoid cwd issues
_DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"
DATABASE_URL = f"sqlite:///{_DB_PATH}"

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
    from backend.models.user import User
    from backend.models.job import Job, JobApplication, SearchRun, SearchRunJob
    from backend.models.supporting import CandidateJobTitle, CandidateSkill, CandidatePreferences, ExtractionOccurrence
    from backend.models.llm_provider import LLMProvider, LLMModel
    from backend.models.document import CandidateDocument, DocumentSection, DocumentParsePrompt, LLMFunctionMapping

    Base.metadata.create_all(bind=engine)

    # Run migrations after tables are created
    migrate_database()


def migrate_database():
    """Run database migrations for schema updates"""
    from backend.models.llm_provider import LLMProvider, LLMModel
    from backend.models.document import CandidateDocument, DocumentSection, DocumentParsePrompt, LLMFunctionMapping

    migrate_ownership_groundwork()
    migrate_deterministic_score()
    migrate_extraction_provenance()
    migrate_llm_job_refinement()
    migrate_remote_verification()
    migrate_job_salary()
    migrate_job_curation()
    migrate_profile_visibility()
    migrate_search_runs()
    migrate_platform_account_rate_limits()

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
        db = SessionLocal()
        conn = engine.connect()
        try:
            # Read legacy provider model names with raw SQL to avoid ORM shape mismatches.
            legacy_rows = conn.execute(text("SELECT id, model_name FROM llm_providers")).fetchall()
            for row in legacy_rows:
                legacy_model_name = row[1]
                if not legacy_model_name:
                    continue
                existing = db.query(LLMModel).filter(
                    LLMModel.provider_id == row[0],
                    LLMModel.model_name == legacy_model_name,
                ).first()
                if existing:
                    continue
                db.add(LLMModel(
                    provider_id=row[0],
                    model_name=legacy_model_name,
                    display_name=legacy_model_name,
                    is_default_for_provider=True,
                    is_active=True,
                ))
            db.commit()

            # Remove the old model_name column (SQLite table rebuild).
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
            conn.execute(text("""
                INSERT INTO llm_providers_new (id, name, api_key_encrypted, api_url, is_global_default, is_active, created_at)
                SELECT id, name, api_key_encrypted, api_url, is_global_default, is_active, created_at
                FROM llm_providers
            """))
            conn.execute(text("DROP TABLE llm_providers"))
            conn.execute(text("ALTER TABLE llm_providers_new RENAME TO llm_providers"))
            conn.commit()
        except Exception as e:
            db.rollback()
            print(f"Migration warning: {e}")
        finally:
            conn.close()
            db.close()

    ensure_llm_provider_auth_columns()

    # Populate default models for providers that don't have any
    populate_default_models()

    # Populate default document parse prompts
    populate_default_parse_prompts()

    # Populate default LLM function mappings
    populate_default_function_mappings()


def migrate_ownership_groundwork(bind=None, session_factory=None):
    """Add candidate ownership without losing existing SQLite data.

    Existing databases receive a nullable column, are backfilled to the seeded
    development user, and rely on the ORM/creation paths for non-null
    enforcement. Fresh databases get the non-null foreign key from metadata.
    """
    from backend.models.user import User
    from backend.ownership import ensure_development_user

    bind = bind or engine
    session_factory = session_factory or SessionLocal
    User.__table__.create(bind=bind, checkfirst=True)

    table_names = inspect(bind).get_table_names()
    if "candidates" not in table_names:
        return

    candidate_columns = {
        column["name"] for column in inspect(bind).get_columns("candidates")
    }
    if "user_id" not in candidate_columns:
        with bind.begin() as conn:
            # SQLite cannot add a NOT NULL FK column to populated tables. The
            # model is NOT NULL for new databases; this compatibility column is
            # immediately backfilled below.
            conn.execute(text("ALTER TABLE candidates ADD COLUMN user_id INTEGER"))

    db = session_factory()
    try:
        user = ensure_development_user(db)
        db.execute(
            text("UPDATE candidates SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": user.id},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def migrate_deterministic_score(bind=None):
    """Add persisted R5 deterministic-score fields to existing SQLite databases."""
    bind = bind or engine
    if "jobs" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    missing_columns = {
        "deterministic_score": "INTEGER",
        "score_breakdown": "TEXT",
        "scoring_version": "VARCHAR",
    }
    pending_columns = [
        (name, definition) for name, definition in missing_columns.items()
        if name not in columns
    ]
    if pending_columns:
        with bind.begin() as conn:
            for name, definition in pending_columns:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {definition}"))


def migrate_platform_account_rate_limits(bind=None):
    """Add per-account rate-limit settings without changing existing sessions."""
    bind = bind or engine
    if "platform_accounts" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("platform_accounts")}
    if "rate_limit_settings" not in columns:
        with bind.begin() as conn:
            conn.execute(text("ALTER TABLE platform_accounts ADD COLUMN rate_limit_settings TEXT"))


def migrate_extraction_provenance(bind=None):
    """Migrate legacy single-document provenance into per-file occurrences."""
    bind = bind or engine
    tables = set(inspect(bind).get_table_names())
    if not {"candidate_job_titles", "candidate_skills"}.issubset(tables):
        return

    from backend.models.supporting import ExtractionOccurrence
    ExtractionOccurrence.__table__.create(bind=bind, checkfirst=True)
    with bind.begin() as conn:
        for table in ("candidate_job_titles", "candidate_skills"):
            columns = {column["name"] for column in inspect(bind).get_columns(table)}
            for name, definition in (
                ("source", "VARCHAR NOT NULL DEFAULT 'edited'"),
                ("original_extracted_value", "VARCHAR"),
            ):
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))

            # Old databases retain the legacy column for SQLite compatibility;
            # application code no longer reads it after this one-time copy.
            if "source_document_id" not in columns:
                continue
            value_column = "title" if table == "candidate_job_titles" else "skill_name"
            fk_column = "job_title_id" if table == "candidate_job_titles" else "skill_id"
            legacy = conn.execute(text(
                f"SELECT id, source_document_id, {value_column} FROM {table} "
                "WHERE source_document_id IS NOT NULL"
            )).mappings()
            for row in legacy:
                exists = conn.execute(text(
                    f"SELECT 1 FROM extraction_occurrences WHERE document_id = :document_id "
                    f"AND {fk_column} = :value_id LIMIT 1"
                ), {"document_id": row["source_document_id"], "value_id": row["id"]}).first()
                if not exists:
                    conn.execute(text(
                        f"INSERT INTO extraction_occurrences (document_id, {fk_column}, raw_extracted_value) "
                        "VALUES (:document_id, :value_id, :value)"
                    ), {"document_id": row["source_document_id"], "value_id": row["id"], "value": row[value_column]})
                conn.execute(text(
                    f"UPDATE {table} SET source = 'extracted', "
                    "original_extracted_value = COALESCE(original_extracted_value, " + value_column + ") "
                    "WHERE id = :value_id"
                ), {"value_id": row["id"]})


def migrate_llm_job_refinement(bind=None):
    """Add optional, separately stored R5 LLM-refinement fields."""
    bind = bind or engine
    if "jobs" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    missing_columns = {
        "llm_score": "INTEGER",
        "llm_rationale": "TEXT",
        "llm_prompt_version": "VARCHAR",
        "llm_profile_fingerprint": "VARCHAR",
    }
    pending_columns = [
        (name, definition) for name, definition in missing_columns.items()
        if name not in columns
    ]
    if pending_columns:
        with bind.begin() as conn:
            for name, definition in pending_columns:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {definition}"))


def migrate_profile_visibility(bind=None):
    """Add the R10 visibility field to legacy candidate databases."""
    bind = bind or engine
    if "candidates" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("candidates")}
    if "visibility_status" not in columns:
        with bind.begin() as conn:
            conn.execute(text(
                "ALTER TABLE candidates ADD COLUMN visibility_status "
                "VARCHAR NOT NULL DEFAULT 'draft'"
            ))


def migrate_remote_verification(bind=None):
    """Add the persisted R6 remote-verification contract to existing jobs."""
    bind = bind or engine
    if "jobs" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    missing_columns = {
        "verified_remote_status": "VARCHAR",
        "remote_restrictions": "TEXT",
        "remote_evidence": "TEXT",
        "remote_verified_version": "VARCHAR",
    }
    with bind.begin() as conn:
        for name, definition in missing_columns.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {definition}"))


def migrate_job_salary(bind=None):
    """Add the source-provided salary display field to existing jobs."""
    bind = bind or engine
    if "jobs" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    if "salary" not in columns:
        with bind.begin() as conn:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN salary VARCHAR"))


def migrate_job_curation(bind=None):
    """Add the non-destructive R7 dismissal flag to legacy job tables."""
    bind = bind or engine
    if "jobs" not in inspect(bind).get_table_names():
        return
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    if "is_dismissed" not in columns:
        with bind.begin() as conn:
            conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN is_dismissed BOOLEAN NOT NULL DEFAULT 0"
            ))


def migrate_search_runs(bind=None):
    """Create R7's run headers and immutable result-membership snapshots."""
    from backend.models.job import SearchRun, SearchRunJob

    bind = bind or engine
    SearchRun.__table__.create(bind=bind, checkfirst=True)
    SearchRunJob.__table__.create(bind=bind, checkfirst=True)


def ensure_llm_provider_auth_columns():
    """Ensure llm_providers has OAuth/auth columns expected by the ORM model."""
    conn = engine.connect()
    try:
        columns = [row[1] for row in conn.execute(text("PRAGMA table_info(llm_providers)")).fetchall()]
        column_updates = [
            ("auth_method", "ALTER TABLE llm_providers ADD COLUMN auth_method VARCHAR(50) DEFAULT 'api_key'"),
            ("oauth_token_encrypted", "ALTER TABLE llm_providers ADD COLUMN oauth_token_encrypted TEXT"),
            ("oauth_refresh_token_encrypted", "ALTER TABLE llm_providers ADD COLUMN oauth_refresh_token_encrypted TEXT"),
            ("oauth_expires_at", "ALTER TABLE llm_providers ADD COLUMN oauth_expires_at DATETIME"),
            ("oauth_subscription_type", "ALTER TABLE llm_providers ADD COLUMN oauth_subscription_type VARCHAR(50)"),
        ]
        changed = False
        for column_name, ddl in column_updates:
            if column_name in columns:
                continue
            conn.execute(text(ddl))
            changed = True

        if changed:
            conn.commit()
    finally:
        conn.close()


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
            {"function_name": "ai_chat", "display_name": "AI Chat Assistant"},
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
