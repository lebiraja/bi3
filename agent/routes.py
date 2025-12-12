"""
FastAPI Routes for Incident Orchestrator Agent.
Provides REST API endpoints for incident management.

Supports both LangGraph and legacy orchestrator implementations.
"""

import os
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# Feature flag for LangGraph
USE_LANGGRAPH = os.getenv('USE_LANGGRAPH', 'true').lower() == 'true'

if USE_LANGGRAPH:
    from .langgraph_orchestrator import LangGraphOrchestrator as Orchestrator
    logger = logging.getLogger(__name__)
    logger.info("🚀 Using LangGraph orchestrator")
else:
    from .orchestrator import IncidentOrchestrator as Orchestrator
    logger = logging.getLogger(__name__)
    logger.info("📦 Using legacy orchestrator")

from .models import (
    IncidentCreateRequest,
    IncidentResponse,
    ManualOverrideRequest,
    AgentDecisionRequest,
    DeviceRegisterRequest,
    DeviceInfo,
    MobileCallback,
    VoIPCallbackPayload,
    ErrorResponse,
    ActionResult,
    FinalStatus,
)
from .api_spec import get_openapi_spec

# Create router
router = APIRouter(prefix="/v1", tags=["Incident Orchestrator"])

# Global orchestrator instance (should be initialized on startup)
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Dependency to get orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def init_orchestrator(orchestrator: Orchestrator = None, device_manager=None):
    """Initialize the orchestrator instance."""
    global _orchestrator
    if orchestrator:
        _orchestrator = orchestrator
    else:
        _orchestrator = Orchestrator(device_manager=device_manager)
    return _orchestrator



# ============ Incident Endpoints ============

@router.post(
    "/incidents",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Receive VLM event and process incident",
    description="Main entry point for VLM events. Creates incident, evaluates policies, builds action plan."
)
async def create_incident(
    request: IncidentCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Process incoming VLM incident."""
    try:
        # Convert to dict for orchestrator
        incident_data = request.dict()
        
        # Process incident
        result = await orchestrator.process_incident_async(incident_data)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=result
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_REQUEST", "message": str(e)}
        )
    except Exception as e:
        logger.exception("Error processing incident")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INTERNAL_ERROR", "message": str(e)}
        )


@router.get(
    "/incidents/{incident_id}",
    response_model=Dict[str, Any],
    summary="Fetch incident details"
)
async def get_incident(
    incident_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Get incident with enhanced report and audit trail."""
    incident = orchestrator.get_incident(incident_id)
    
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": f"Incident {incident_id} not found"}
        )
    
    return incident


# ============ Action Endpoints ============

@router.post(
    "/actions/{incident_id}",
    response_model=Dict[str, Any],
    summary="Manual override or trigger actions"
)
async def manual_override(
    incident_id: str,
    request: ManualOverrideRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Apply manual override to incident actions."""
    result = orchestrator.handle_manual_override(
        incident_id=incident_id,
        action=request.action,
        operator_id=request.operator_id,
        reason=request.reason,
        target_actions=request.target_actions
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in result["error"].lower() 
            else status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_REQUEST", "message": result["error"]}
        )
    
    return result


@router.post(
    "/agent/decision",
    response_model=Dict[str, Any],
    summary="Operator-initiated decision override"
)
async def agent_decision(
    request: AgentDecisionRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Submit operator decision for queued incidents."""
    incident = orchestrator.get_incident(request.incident_id)
    
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": f"Incident {request.incident_id} not found"}
        )
    
    # Map decision to override action
    action_map = {
        "dispatch": "approve",
        "escalate": "escalate",
        "dismiss": "reject"
    }
    
    result = orchestrator.handle_manual_override(
        incident_id=request.incident_id,
        action=action_map.get(request.decision, "approve"),
        operator_id="operator",
        reason=request.notes or f"Operator decision: {request.decision}"
    )
    
    return result


# ============ Device Endpoints ============

@router.post(
    "/devices/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register mobile device"
)
async def register_device(
    request: DeviceRegisterRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Register a mobile device for action execution."""
    from datetime import datetime
    
    device = DeviceInfo(
        device_id=request.device_id,
        push_token=request.push_token,
        capabilities=request.capabilities,
        is_online=True,
        last_seen=datetime.utcnow().isoformat() + "Z"
    )
    
    orchestrator.register_device(device)
    
    return {
        "device_id": device.device_id,
        "registered_at": device.last_seen,
        "status": "active"
    }


@router.get(
    "/devices/{device_id}",
    response_model=Dict[str, Any],
    summary="Get device status and capabilities"
)
async def get_device(
    device_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Get device info."""
    device = orchestrator.action_executor.registered_devices.get(device_id)
    
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": f"Device {device_id} not found"}
        )
    
    return device.dict()


# ============ Callback Endpoints ============

@router.post(
    "/mobile/callback",
    summary="Mobile app reports action execution results"
)
async def mobile_callback(
    request: MobileCallback,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Handle callback from mobile device after action execution."""
    success = orchestrator.handle_mobile_callback(request)
    
    return {
        "received": success,
        "next_action": None  # Would be populated if chained actions exist
    }


@router.post(
    "/webhooks/voip",
    summary="VoIP provider status callback"
)
async def voip_callback(
    request: VoIPCallbackPayload,
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature")
):
    """Handle VoIP provider callback."""
    # In production, verify webhook signature
    orchestrator = get_orchestrator()
    result = orchestrator.action_executor.handle_voip_callback(request)
    
    return {"received": True, "processed": result}


# ============ Report Endpoints ============

@router.post(
    "/reports/{incident_id}/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger enhanced report generation"
)
async def generate_report(
    incident_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Trigger Gemma enhancement for incident report."""
    incident = orchestrator.get_incident(incident_id)
    
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "message": f"Incident {incident_id} not found"}
        )
    
    from datetime import datetime, timedelta
    estimated = datetime.utcnow() + timedelta(seconds=30)
    
    return {
        "status": "processing",
        "estimated_completion": estimated.isoformat() + "Z"
    }


# ============ System Endpoints ============

@router.get(
    "/health",
    summary="Health check",
    tags=["System"]
)
async def health_check():
    """Check service health."""
    from datetime import datetime
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "components": {
            "database": "healthy",
            "ollama": "unknown",  # Would check actual status
            "voip_provider": "unknown"
        }
    }


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    tags=["System"]
)
async def get_metrics():
    """Get Prometheus-format metrics."""
    from fastapi.responses import PlainTextResponse
    
    metrics = """# HELP incidents_total Total incidents processed
# TYPE incidents_total counter
incidents_total{status="dispatched"} 0
incidents_total{status="escalated"} 0
incidents_total{status="queued_for_review"} 0
incidents_total{status="logged_only"} 0

# HELP actions_total Total actions executed
# TYPE actions_total counter
actions_total{type="call",status="acknowledged"} 0
actions_total{type="sms",status="sent"} 0
actions_total{type="notify",status="sent"} 0
"""
    return PlainTextResponse(content=metrics, media_type="text/plain")


@router.get(
    "/openapi-spec",
    summary="Get OpenAPI specification",
    tags=["System"]
)
async def get_api_spec():
    """Return the complete OpenAPI specification."""
    return get_openapi_spec()


# ============ Include router in main app ============

def include_in_app(app):
    """Include the agent router in a FastAPI app."""
    app.include_router(router)
    return app
