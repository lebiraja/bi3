"""
Pydantic models for Incident Orchestrator Agent.
Defines input/output schemas for all agent operations.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum
import uuid


# ============ Enums ============

class ActionType(str, Enum):
    """Types of actions the orchestrator can execute."""
    CALL = "call"
    SMS = "sms"
    NOTIFY = "notify"


class TargetRole(str, Enum):
    """Target roles for emergency response."""
    AMBULANCE = "ambulance"
    POLICE = "police"
    TRAFFIC_CONTROL = "traffic_control"


class ActionStatus(str, Enum):
    """Status of an action in the plan."""
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    ESCALATED = "escalated"


class FinalStatus(str, Enum):
    """Final status of incident processing."""
    DISPATCHED = "dispatched"
    ESCALATED = "escalated"
    QUEUED_FOR_REVIEW = "queued_for_review"
    LOGGED_ONLY = "logged_only"


class DeviceCapability(str, Enum):
    """Device capabilities for action execution."""
    CALLS = "calls"
    SMS = "sms"
    PUSH = "push"


# ============ Input Models ============

class Location(BaseModel):
    """Geographic location."""
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    
    @validator('lat')
    def validate_lat(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v
    
    @validator('lon')
    def validate_lon(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v


class VLMSummary(BaseModel):
    """VLM analysis summary."""
    confidence: float = Field(..., ge=0, le=1, description="VLM confidence score 0-1")
    incident_type: str = Field(..., description="Type of incident detected")
    description: Optional[str] = Field(None, description="Detailed description")
    vehicles_involved: Optional[int] = Field(None, description="Number of vehicles")
    recommended_alerts: Optional[List[str]] = Field(
        default_factory=list,
        description="Recommended alert types (call, sms, notify)"
    )
    ambiguous: Optional[bool] = Field(False, description="Whether the detection is ambiguous")
    raw_analysis: Optional[Dict[str, Any]] = Field(None, description="Raw VLM output")


class EnhancedReportData(BaseModel):
    """Enhanced report from Gemma."""
    report_text: str = Field(..., description="Full enhanced report text")
    risk_score: int = Field(..., ge=1, le=10, description="Risk score 1-10")
    executive_summary: Optional[str] = Field(None, description="Executive summary")
    evidence_mapping: Optional[Dict[str, Any]] = Field(None, description="Evidence details")


class HistoricalIncident(BaseModel):
    """Historical incident for context."""
    incident_id: str
    timestamp: str
    incident_type: str
    risk_score: int
    summary: Optional[str] = None


class IncidentInput(BaseModel):
    """Input payload for incident processing."""
    incident_id: str = Field(..., description="Unique incident identifier")
    vlm_summary: VLMSummary = Field(..., description="VLM analysis summary")
    enhanced_report: EnhancedReportData = Field(..., description="Enhanced report")
    location: Optional[Location] = Field(None, description="Incident location")
    history: List[HistoricalIncident] = Field(
        default_factory=list,
        description="Relevant prior incidents"
    )
    timestamp: Optional[str] = Field(None, description="Incident timestamp")
    
    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.utcnow().isoformat() + "Z"


# ============ Action Models ============

class RetryPolicy(BaseModel):
    """Retry policy for actions."""
    attempts: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    backoff_seconds: int = Field(10, ge=1, le=300, description="Backoff between retries")


class ActionPlanItem(BaseModel):
    """Individual action in the action plan."""
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ActionType = Field(..., description="Action type")
    target_role: TargetRole = Field(..., description="Target role")
    number: str = Field(..., description="Target phone number")
    text: str = Field(..., description="Message text or link")
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    status: ActionStatus = Field(ActionStatus.PENDING, description="Current status")
    attempts: int = Field(0, description="Number of attempts made")
    last_result: Optional[Dict[str, Any]] = Field(None, description="Last execution result")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    
    class Config:
        use_enum_values = True


class AuditEntry(BaseModel):
    """Audit log entry."""
    ts: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="Timestamp"
    )
    actor: str = Field(..., description="Agent or actor ID")
    action_id: Optional[str] = Field(None, description="Related action ID")
    step: str = Field(..., description="Step description")
    outcome: str = Field(..., description="Outcome description")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class AuditMetadata(BaseModel):
    """Audit metadata for actions."""
    reason: str = Field(..., description="Reason for action")
    trigger: str = Field(..., description="What triggered this action")
    confidence: float = Field(..., description="Confidence score")
    risk_score: int = Field(..., description="Risk score")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )


# ============ Output Models ============

class ActionResult(BaseModel):
    """Orchestrator output for action results."""
    incident_id: str = Field(..., description="Incident ID")
    action_plan: List[ActionPlanItem] = Field(
        default_factory=list,
        description="List of actions in the plan"
    )
    final_status: FinalStatus = Field(..., description="Final processing status")
    audit: List[AuditEntry] = Field(
        default_factory=list,
        description="Audit trail"
    )
    operator_message: Optional[str] = Field(
        None,
        description="Message for operator (if queued for review)"
    )
    device_status: Optional[Dict[str, Any]] = Field(
        None,
        description="Mobile device status if relevant"
    )
    
    class Config:
        use_enum_values = True


class OrchestratorOutput(BaseModel):
    """Complete orchestrator output with action result and API spec."""
    action_result: ActionResult = Field(..., description="Action execution results")
    api_spec: Dict[str, Any] = Field(..., description="OpenAPI 3.0 specification")


# ============ Device Models ============

class DeviceCapabilities(BaseModel):
    """Device capabilities."""
    calls: bool = Field(True, description="Can make calls")
    sms: bool = Field(True, description="Can send SMS")
    push: bool = Field(True, description="Can receive push notifications")


class DeviceInfo(BaseModel):
    """Mobile device registration."""
    device_id: str = Field(..., description="Unique device ID")
    push_token: str = Field(..., description="FCM push token")
    capabilities: DeviceCapabilities = Field(
        default_factory=DeviceCapabilities
    )
    is_online: bool = Field(True, description="Device online status")
    last_seen: Optional[str] = Field(None, description="Last seen timestamp")
    api_key_hash: Optional[str] = Field(None, description="Hashed device API key")


class MobileCallback(BaseModel):
    """Callback from mobile device after action execution."""
    action_id: str = Field(..., description="Action ID that was executed")
    device_id: str = Field(..., description="Device ID that executed")
    status: ActionStatus = Field(..., description="Execution status")
    call_state: Optional[str] = Field(
        None,
        description="Call state (e.g., CALL_STATE_OFFHOOK, CALL_STATE_IDLE)"
    )
    duration_seconds: Optional[int] = Field(None, description="Call duration")
    error_message: Optional[str] = Field(None, description="Error if failed")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    
    class Config:
        use_enum_values = True


# ============ API Request/Response Models ============

class IncidentCreateRequest(BaseModel):
    """Request to create/process an incident."""
    incident_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Optional incident ID"
    )
    vlm_summary: VLMSummary
    enhanced_report: EnhancedReportData
    location: Optional[Location] = None
    history: List[HistoricalIncident] = Field(default_factory=list)


class IncidentResponse(BaseModel):
    """Response for incident queries."""
    incident_id: str
    status: FinalStatus
    created_at: str
    enhanced_report: EnhancedReportData
    action_plan: List[ActionPlanItem]
    audit: List[AuditEntry]
    
    class Config:
        use_enum_values = True


class ManualOverrideRequest(BaseModel):
    """Manual override request from operator."""
    action: Literal["approve", "reject", "escalate", "cancel"] = Field(
        ..., description="Override action"
    )
    reason: str = Field(..., description="Reason for override")
    operator_id: str = Field(..., description="Operator ID")
    target_actions: Optional[List[str]] = Field(
        None, description="Specific action IDs to override"
    )


class DeviceRegisterRequest(BaseModel):
    """Device registration request."""
    device_id: str
    push_token: str
    capabilities: DeviceCapabilities
    device_api_key: str = Field(..., description="Per-device API key")


class AgentDecisionRequest(BaseModel):
    """Operator-initiated decision override."""
    incident_id: str
    decision: Literal["dispatch", "escalate", "dismiss"] = Field(
        ..., description="Decision type"
    )
    additional_actions: Optional[List[ActionPlanItem]] = Field(
        None, description="Additional actions to execute"
    )
    notes: Optional[str] = Field(None, description="Operator notes")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )


# ============ Webhook Models ============

class VoIPCallbackPayload(BaseModel):
    """VoIP provider callback payload."""
    call_id: str
    action_id: str
    status: Literal[
        "initiated", "ringing", "answered", "completed", "failed", "busy", "no_answer"
    ]
    duration_seconds: Optional[int] = None
    timestamp: str
    provider_details: Optional[Dict[str, Any]] = None


class FCMPushPayload(BaseModel):
    """FCM push notification payload."""
    to: str = Field(..., description="Device token or topic")
    priority: str = Field("high", description="Message priority")
    ttl: str = Field("300s", description="Time to live")
    data: Dict[str, Any] = Field(..., description="Data payload")
    notification: Optional[Dict[str, str]] = Field(
        None, description="Optional notification payload"
    )


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: Literal[
        "connect", "action_plan", "ack", "heartbeat", "status_update", "error"
    ]
    payload: Dict[str, Any]
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
