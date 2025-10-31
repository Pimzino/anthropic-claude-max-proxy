"""Pydantic models for Anthropic API"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ThinkingParameter(BaseModel):
    """Anthropic thinking/reasoning parameter"""
    type: str = Field(default="enabled")
    budget_tokens: int = Field(default=16000)


class AnthropicMessageRequest(BaseModel):
    """Anthropic Messages API request model"""
    model: str
    messages: List[Dict[str, Any]]
    max_tokens: int
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    system: Optional[List[Dict[str, Any]]] = None
    stream: Optional[bool] = False
    thinking: Optional[ThinkingParameter] = None
    tools: Optional[List[Dict[str, Any]]] = None
