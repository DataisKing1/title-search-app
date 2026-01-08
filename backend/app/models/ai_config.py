"""AI provider configuration model"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Text
from datetime import datetime
from app.database import Base


class AIProviderConfig(Base):
    """AI provider configuration for flexible provider support"""
    __tablename__ = "ai_provider_configs"

    id = Column(Integer, primary_key=True, index=True)

    # Provider identification
    provider_name = Column(String(100), unique=True, nullable=False)  # openai, anthropic, ollama
    display_name = Column(String(100), nullable=False)

    # Configuration
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    priority = Column(Integer, default=10)  # Lower = higher priority for fallback

    # API settings
    api_endpoint = Column(String(500), nullable=True)  # For Ollama or custom endpoints
    model_name = Column(String(100), nullable=True)  # gpt-4, claude-3-opus, etc.

    # Capabilities
    supports_vision = Column(Boolean, default=False)  # Can process images
    supports_json_mode = Column(Boolean, default=True)
    max_tokens = Column(Integer, default=4096)
    context_window = Column(Integer, default=128000)

    # Rate limiting
    requests_per_minute = Column(Integer, default=60)
    tokens_per_minute = Column(Integer, nullable=True)

    # Cost tracking
    cost_per_1k_input_tokens = Column(String(20), nullable=True)
    cost_per_1k_output_tokens = Column(String(20), nullable=True)

    # Prompts configuration
    system_prompt_template = Column(Text, nullable=True)

    # Health
    is_healthy = Column(Boolean, default=True)
    last_health_check = Column(DateTime, nullable=True)
    error_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
