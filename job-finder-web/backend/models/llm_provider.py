"""
LLM Provider Model - Stores AI provider configurations
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)  # ollama, openrouter, anthropic, openai
    api_key_encrypted = Column(Text, nullable=True)  # Encrypted API key
    api_url = Column(String, nullable=True)  # For local providers like Ollama
    is_global_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationship to models
    models = relationship("LLMModel", back_populates="provider", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LLMProvider(name='{self.name}')>"


class LLMModel(Base):
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String, nullable=False)  # e.g., "llama3", "gpt-4", "claude-3-opus"
    display_name = Column(String, nullable=True)  # e.g., "Llama 3 8B"
    is_default_for_provider = Column(Boolean, default=False)  # One default per provider
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationship back to provider
    provider = relationship("LLMProvider", back_populates="models")

    def __repr__(self):
        return f"<LLMModel(model_name='{self.model_name}', provider='{self.provider.name if self.provider else None}')>"
