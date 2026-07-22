"""
Initialize System Parse Prompts

Run this once to populate default AI prompts for document parsing.
"""
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models.document import DocumentParsePrompt


JOB_TITLES_PARSER_PROMPT = """You curate a candidate's preferred target job titles from their resume, profile, and job-preferences documents. This is not a work-history extraction task.

## Input
{{content}}

## Output
Return ONLY a valid JSON object (no markdown or explanation):
{
  "job_titles": [
    {"title": "Staff SDET", "priority": 1, "description": "Explicit primary target role"}
  ]
}

## Rules
- Return 1-5 concise, canonical market titles. Prefer fewer; never pad the list.
- Include an explicit target role, or at most 1-3 strong target inferences from the candidate's most recent and repeated career direction.
- Do not list every historical role, title variants, generic labels (such as "Engineer" or "Team Lead"), bare seniority words, employer-specific labels, or slash/parenthetical compound titles.
- Merge near-duplicates into one clearest title. Do not emit variants of the same role unless the document clearly treats them as separate target tracks.
- Do not invent a target role. Return {"job_titles": []} if no suitable target is supported by the document.
- Priority 1 is a primary explicit target; priority 2 is a closely related alternative; use priority 3 only for a clearly stated secondary track.
- Each description is a brief factual rationale, at most one sentence.
"""

PROFILE_PARSER_PROMPT = """You are an expert profile analyzer. Extract structured data from a candidate's profile/resume document.

## Input
{{content}}

## Instructions
Extract the following information:
1. **skills**: List of technical skills (programming languages, tools, frameworks)
2. **experience_years**: Total years of experience
3. **current_role**: Current job title
4. **key_achievements**: 3-5 major accomplishments
5. **certifications**: Any certifications mentioned
6. **preferred_work_style**: Remote, hybrid, onsite preferences if mentioned

## Output Format
Return ONLY valid JSON:

{
  "skills": ["Python", "Bash", "FastAPI", "Playwright"],
  "experience_years": 18,
  "current_role": "Software Engineer",
  "key_achievements": [
    "Built CI/CD pipeline reducing deployment time by 80%",
    "Led QA architecture redesign"
  ],
  "certifications": ["Kaggle ML Certifications"],
  "preferred_work_style": "Fully Remote"
}

## Rules
- Be specific with skills (e.g., "Python" not "Programming")
- Extract exact years if mentioned, otherwise estimate from dates
- Only include information explicitly stated in the document
- Return ONLY the JSON object, nothing else
"""


def init_parse_prompts(db: Session):
    """Initialize system parse prompts"""
    
    # Job Titles Parser
    existing_job_titles = db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.document_type == "job_titles",
        DocumentParsePrompt.candidate_id.is_(None)
    ).first()
    
    if not existing_job_titles:
        job_titles_prompt = DocumentParsePrompt(
            name="job_titles_parser",
            description="Extract preferred job titles from candidate documents",
            document_type="job_titles",
            prompt_template=JOB_TITLES_PARSER_PROMPT,
            output_schema='[{"title": "string", "priority": "number", "description": "string"}]',
            is_system=True
        )
        db.add(job_titles_prompt)
        print("✅ Created job_titles_parser system prompt")
    else:
        print("ℹ️  job_titles_parser system prompt already exists")
    
    # Profile Parser
    existing_profile = db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.document_type == "profile",
        DocumentParsePrompt.candidate_id.is_(None)
    ).first()
    
    if not existing_profile:
        profile_prompt = DocumentParsePrompt(
            name="profile_parser",
            description="Extract structured profile data (skills, experience, etc.)",
            document_type="profile",
            prompt_template=PROFILE_PARSER_PROMPT,
            output_schema='{"skills": [], "experience_years": 0, "current_role": ""}',
            is_system=True
        )
        db.add(profile_prompt)
        print("✅ Created profile_parser system prompt")
    else:
        print("ℹ️  profile_parser system prompt already exists")
    
    db.commit()
    print("✅ System parse prompts initialized successfully")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        init_parse_prompts(db)
    finally:
        db.close()
