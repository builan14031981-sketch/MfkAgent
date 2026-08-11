from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, Boolean
from datetime import datetime
from app.core.database import Base


class PersonaTemplate(Base):
    __tablename__ = "persona_templates"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(50), unique=True, nullable=False, index=True)

    personality_traits = Column(JSON, default=dict)
    communication_style = Column(JSON, default=dict)
    behavior_rules = Column(JSON, default=dict)
    expression_preferences = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExpressionKnowledge(Base):
    __tablename__ = "expression_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")

    emoji_usage = Column(Float, default=0.5)
    kaomoji_usage = Column(Float, default=0.3)
    markdown_usage = Column(Float, default=0.7)
    colloquial_level = Column(Float, default=0.5)
    internet_slang = Column(Float, default=0.3)
    pause_frequency = Column(Float, default=0.3)
    response_length = Column(Float, default=0.5)
    humor_level = Column(Float, default=0.3)
    proactive_level = Column(Float, default=0.5)
    emotional_expression = Column(Float, default=0.5)

    custom_prompt_fragment = Column(Text, nullable=True)
    is_builtin = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
