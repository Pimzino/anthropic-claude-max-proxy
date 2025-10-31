"""
Pydantic models for OpenAI API compatibility.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class OpenAIFunction(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class OpenAITool(BaseModel):
    type: str = "function"
    function: OpenAIFunction


class OpenAIToolChoice(BaseModel):
    type: str
    function: Optional[Dict[str, str]] = None


class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    max_tokens: Optional[int] = 4096
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop: Optional[Any] = None  # Can be string or list
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None  # Can be string or dict
    functions: Optional[List[Dict[str, Any]]] = None  # Legacy
    function_call: Optional[Any] = None  # Legacy
    reasoning_effort: Optional[str] = None  # "low", "medium", "high" - maps to Anthropic thinking budget


