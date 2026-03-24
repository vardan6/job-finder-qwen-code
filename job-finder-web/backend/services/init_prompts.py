"""
Initialize System Parse Prompts

Run this once to populate default AI prompts for document parsing.
"""
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models.document import DocumentParsePrompt


JOB_TITLES_PARSER_PROMPT = """You are an expert job title extractor. Your task is to analyze a candidate's document (resume, profile, or job preferences) and extract all preferred job titles.

## Input
The candidate has provided the following markdown document:

{{content}}

## Instructions
1. Read the document carefully and identify all job titles the candidate is targeting or has experience with
2. For each job title, determine:
   - **title**: The exact job title (e.g., "Staff SDET", "Principal EDA Engineer")
   - **priority**: Assign priority based on emphasis in document:
     - 1 = High priority (explicitly mentioned as target, emphasized, or current role they want to grow from)
     - 2 = Medium priority (mentioned as related experience or secondary interest)
     - 3 = Low priority (tangentially related or historical role)
   - **description**: Optional brief note about why this title is relevant (1 sentence max)

## Output Format
Return ONLY a valid JSON array (no markdown, no explanations):

[
  {
    "title": "Staff SDET",
    "priority": 1,
    "description": "Candidate's current focus with 18 years QA automation experience"
  },
  {
    "title": "Principal EDA Design Automation Engineer",
    "priority": 1,
    "description": "Strong EDA background at Silvaco and Synopsys"
  }
]

## Rules
- Extract 5-15 job titles maximum
- Prioritize titles that match the candidate's actual experience level (Staff/Principal/Senior)
- Include variations (SDET, Test Infrastructure, QA Automation)
- Focus on remote-friendly roles in US/EU/Canada
- If the document mentions specific preferences (e.g., "fully remote only"), prioritize those titles
- Return ONLY the JSON array, nothing else
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
