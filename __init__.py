"""
Agent-S3 + Coasty Bridge: Unified GUI Automation Framework
Connects Coasty's beautiful frontend with Agent-S3's powerful backend.
"""

from .llm_router import UnifiedLLMRouter, LLMTier
from .agents3_adapter import AgentS3Adapter, Action, ActionType
from .fastapi_server import app

__version__ = "1.0.0"
__all__ = [
    "UnifiedLLMRouter",
    "LLMTier",
    "AgentS3Adapter",
    "Action",
    "ActionType",
    "app",
]
