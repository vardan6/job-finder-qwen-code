"""
Document Parsing Service - AI-powered document parsing using LLM
"""
import json
import re
from typing import Optional, Dict, Any, List
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.document import CandidateDocument, DocumentParsePrompt, LLMFunctionMapping, DocumentSection
from backend.models.llm_provider import LLMProvider, LLMModel
from backend.models.supporting import CandidateJobTitle


def get_llm_for_function(db: Session, function_name: str) -> Optional[LLMModel]:
    """Get the LLM model configured for a specific function"""
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name,
        LLMFunctionMapping.is_active == True
    ).first()
    
    if not mapping or not mapping.model_id:
        return None
    
    return mapping.model


def call_llm(db: Session, model: LLMModel, prompt: str) -> Optional[str]:
    """Call LLM API using the specified model"""
    try:
        # Import litellm lazily
        from litellm import completion
        
        provider = model.provider
        if not provider:
            return None
        
        # Build the model identifier
        if provider.name == "ollama":
            # For Ollama, use host + model
            model_name = f"ollama/{model.model_name}"
            api_base = provider.api_url or "http://localhost:11434"
        else:
            # For other providers, add proper prefix for LiteLLM
            provider_prefixes = {
                "nvidia": "nvidia/",
                "openrouter": "openrouter/",
                "anthropic": "anthropic/",
                "openai": "openai/",
            }
            prefix = provider_prefixes.get(provider.name, "")
            if prefix and not model.model_name.startswith(prefix):
                model_name = prefix + model.model_name
            else:
                model_name = model.model_name
            # Use provider API URL, but strip trailing /v1 if present (LiteLLM adds it)
            api_base = provider.api_url
            if api_base and api_base.endswith('/v1'):
                api_base = api_base[:-3]  # Remove /v1, LiteLLM will add it
        
        # Prepare completion kwargs
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if api_base:
            kwargs["api_base"] = api_base
        
        # Add API key if present (for non-Ollama providers)
        if provider.api_key_encrypted and provider.name != "ollama":
            from backend.security import decrypt_data
            api_key = decrypt_data(provider.api_key_encrypted)
            if api_key:
                kwargs["api_key"] = api_key
        
        # Call the LLM
        response = completion(**kwargs)
        
        if response and response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
        
        return None
        
    except Exception as e:
        print(f"LLM call error: {e}")
        return None


def parse_document_content(db: Session, document: CandidateDocument) -> bool:
    """
    Parse a document using AI and extract structured data.
    Returns True if successful, False otherwise.
    """
    try:
        # Update status to processing
        document.parse_status = "processing"
        db.commit()
        
        # Get the appropriate prompt for this document type
        candidate_id = document.candidate_id
        document_type = document.document_type
        
        # First try to get candidate-specific prompt
        prompt = db.query(DocumentParsePrompt).filter(
            DocumentParsePrompt.document_type == document_type,
            DocumentParsePrompt.candidate_id == candidate_id
        ).first()
        
        # Fall back to system prompt
        if not prompt:
            prompt = db.query(DocumentParsePrompt).filter(
                DocumentParsePrompt.document_type == document_type,
                DocumentParsePrompt.candidate_id.is_(None)
            ).first()
        
        if not prompt:
            raise ValueError(f"No parse prompt found for document type: {document_type}")
        
        # Read the document content
        file_path = Path("data") / document.file_path
        if not file_path.exists():
            raise ValueError(f"Document file not found: {file_path}")
        
        content = file_path.read_text(encoding="utf-8")
        
        # Replace {{content}} placeholder with actual content
        full_prompt = prompt.prompt_template.replace("{{content}}", content)
        
        # Get the LLM model for this function
        function_name = f"{document_type}_parser"
        model = get_llm_for_function(db, function_name)
        
        if not model:
            # Fall back to default Ollama model
            ollama = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
            if ollama:
                model = db.query(LLMModel).filter(
                    LLMModel.provider_id == ollama.id,
                    LLMModel.is_default_for_provider == True
                ).first()
        
        if not model:
            raise ValueError("No LLM model configured for parsing")
        
        # Call the LLM
        result = call_llm(db, model, full_prompt)
        
        if not result:
            raise ValueError("LLM returned empty response")
        
        # Try to parse the result as JSON
        parsed_data = extract_json_from_response(result)
        
        if not parsed_data:
            # Store raw response if JSON extraction fails
            document.parsed_data = json.dumps({"raw_response": result})
            document.parse_status = "completed"
            document.parse_error = "JSON extraction failed, raw response stored"
            document.parsed_at = func.now()
            db.commit()
            return False
        
        # Store parsed data
        document.set_parsed_data_json(parsed_data)
        document.parse_status = "completed"
        document.parsed_at = func.now()
        document.parse_error = None
        
        # Process extracted data based on document type
        if document_type == "job_titles" and isinstance(parsed_data, list):
            # Extract job titles to CandidateJobTitle table
            process_job_titles(db, document, parsed_data)
        elif document_type == "profile" and isinstance(parsed_data, dict):
            # Process profile data (skills, experience, etc.)
            process_profile_data(db, document, parsed_data)
        
        db.commit()
        return True
        
    except Exception as e:
        document.parse_status = "failed"
        document.parse_error = str(e)
        db.commit()
        print(f"Document parsing error: {e}")
        return False


def extract_json_from_response(response: str) -> Optional[Any]:
    """Extract JSON from LLM response (handles markdown code blocks)"""
    # Try to find JSON in markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', response, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object/array directly
        json_match = re.search(r'(\{.*?\}|\[.*?\])', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try parsing the whole response as JSON
            json_str = response
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def process_job_titles(db: Session, document: CandidateDocument, job_titles: List[Dict]) -> None:
    """Process extracted job titles and add to candidate's job titles"""
    candidate_id = document.candidate_id
    
    # Clear existing job titles from this document (optional - could also merge)
    # For now, we'll just add new ones without removing old ones
    
    for title_data in job_titles:
        if isinstance(title_data, dict) and "title" in title_data:
            # Check if this job title already exists for this candidate
            existing = db.query(CandidateJobTitle).filter(
                CandidateJobTitle.candidate_id == candidate_id,
                CandidateJobTitle.title == title_data["title"]
            ).first()
            
            if not existing:
                job_title = CandidateJobTitle(
                    candidate_id=candidate_id,
                    title=title_data["title"],
                    priority=title_data.get("priority", 3),
                    description=title_data.get("description"),
                    source_document_id=document.id
                )
                db.add(job_title)


def process_profile_data(db: Session, document: CandidateDocument, profile_data: Dict) -> None:
    """Process extracted profile data (skills, experience, certifications)"""
    # This is a placeholder for future implementation
    # For now, we just store the parsed data in the document
    pass


def get_candidate_prompt(db: Session, candidate_id: int, document_type: str) -> Optional[DocumentParsePrompt]:
    """Get the parse prompt for a candidate and document type"""
    # Try candidate-specific first
    prompt = db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.candidate_id == candidate_id,
        DocumentParsePrompt.document_type == document_type
    ).first()
    
    # Fall back to system prompt
    if not prompt:
        prompt = db.query(DocumentParsePrompt).filter(
            DocumentParsePrompt.candidate_id.is_(None),
            DocumentParsePrompt.document_type == document_type
        ).first()
    
    return prompt


def reset_candidate_prompt_to_system(db: Session, candidate_id: int, document_type: str) -> Optional[DocumentParsePrompt]:
    """Delete candidate-specific prompt and return system prompt"""
    # Delete candidate-specific prompt
    prompt = db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.candidate_id == candidate_id,
        DocumentParsePrompt.document_type == document_type
    ).first()
    
    if prompt:
        db.delete(prompt)
        db.commit()
    
    # Return system prompt
    return db.query(DocumentParsePrompt).filter(
        DocumentParsePrompt.candidate_id.is_(None),
        DocumentParsePrompt.document_type == document_type
    ).first()
