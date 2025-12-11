"""
Incident Orchestrator Agent for BI3 Smart Traffic Safety.

Provides automated incident response orchestration with:
- Policy-based action gating
- Mobile/VoIP call execution
- SMS and notification dispatch
- Complete audit logging
- OpenAPI 3.0 specification
- Ollama gemma3:1b LLM integration
"""

from .orchestrator import IncidentOrchestrator
from .models import (
    IncidentInput,
    VLMSummary,
    EnhancedReportData,
    ActionPlanItem,
    AuditEntry,
    ActionResult,
    DeviceInfo,
    MobileCallback,
)
from .policies import PolicyEngine
from .actions import ActionExecutor
from .api_spec import get_openapi_spec
from .llm_helper import LLMDecisionHelper
from .routes import router, include_in_app

__all__ = [
    "IncidentOrchestrator",
    "IncidentInput",
    "VLMSummary",
    "EnhancedReportData",
    "ActionPlanItem",
    "AuditEntry",
    "ActionResult",
    "DeviceInfo",
    "MobileCallback",
    "PolicyEngine",
    "ActionExecutor",
    "get_openapi_spec",
    "LLMDecisionHelper",
    "router",
    "include_in_app",
]

__version__ = "1.0.0"
