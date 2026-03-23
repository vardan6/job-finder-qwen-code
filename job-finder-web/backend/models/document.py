"""
Candidate Document Models - For storing and managing uploaded documents
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
import json

from backend.database import Base


class CandidateDocument(Base):
    """Stores uploaded documents for a candidate"""
    __tablename__ = "candidate_documents"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)

    # File info
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Relative path from data/
    file_hash = Column(String, nullable=True)  # SHA256 hash to detect duplicates
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String, default="text/markdown")

    # Document type: profile, job_titles, resume, cover_letter, custom
    document_type = Column(String, nullable=False, default="custom")

    # Parsing info
    parse_status = Column(String, default="pending")  # pending, processing, completed, failed
    parse_error = Column(Text, nullable=True)
    parsed_at = Column(DateTime, nullable=True)
    parsed_data = Column(Text, nullable=True)  # JSON string of AI extraction result

    # Loading strategy: immediate, on_demand
    load_strategy = Column(String, default="immediate")

    # Relationships
    candidate = relationship("Candidate", back_populates="documents")
    sections = relationship("DocumentSection", back_populates="document", cascade="all, delete-orphan", lazy="select")

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def get_parsed_data_json(self):
        """Return parsed_data as dict"""
        if self.parsed_data:
            return json.loads(self.parsed_data)
        return None

    def set_parsed_data_json(self, data: dict):
        """Store dict as JSON string"""
        self.parsed_data = json.dumps(data)

    def __repr__(self):
        return f"<CandidateDocument(id={self.id}, filename='{self.filename}', type='{self.document_type}')>"


class DocumentSection(Base):
    """Stores parsed sections from a document"""
    __tablename__ = "document_sections"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False)

    # Section info
    section_name = Column(String, nullable=False)  # e.g., "Experience", "Skills"
    section_content = Column(Text, nullable=True)  # Raw markdown content

    # Extracted structured data (JSON string)
    extracted_data = Column(Text, nullable=True)

    # Relationships
    document = relationship("CandidateDocument", back_populates="sections")

    created_at = Column(DateTime, server_default=func.now())

    def get_extracted_data_json(self):
        """Return extracted_data as dict"""
        if self.extracted_data:
            return json.loads(self.extracted_data)
        return None

    def set_extracted_data_json(self, data: dict):
        """Store dict as JSON string"""
        self.extracted_data = json.dumps(data)

    def __repr__(self):
        return f"<DocumentSection(id={self.id}, name='{self.section_name}')>"


class DocumentParsePrompt(Base):
    """Stores AI prompts for parsing different document types"""
    __tablename__ = "document_parse_prompts"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True)  # NULL = system prompt

    # Prompt info
    name = Column(String, nullable=False)  # e.g., "job_titles_parser", "profile_parser"
    description = Column(String, nullable=True)
    document_type = Column(String, nullable=False)  # Which document type this prompt is for

    # The actual prompt template (use {{content}} as placeholder for markdown content)
    prompt_template = Column(Text, nullable=False)

    # Expected output schema (JSON string)
    output_schema = Column(Text, nullable=True)

    # System prompts can't be deleted, only used as templates
    is_system = Column(Boolean, default=False)

    # Relationships
    candidate = relationship("Candidate", back_populates="parse_prompts")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DocumentParsePrompt(name='{self.name}', type='{self.document_type}')>"


class LLMFunctionMapping(Base):
    """Maps application functionalities to specific LLM models"""
    __tablename__ = "llm_function_mappings"

    id = Column(Integer, primary_key=True, index=True)

    # Function identifier (e.g., "job_title_parser", "job_scorer", "resume_matcher")
    function_name = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=True)  # Human-readable name

    # The model to use for this function
    model_id = Column(Integer, ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    model = relationship("LLMModel", backref="function_mappings")

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<LLMFunctionMapping(function='{self.function_name}', model_id={self.model_id})>"
