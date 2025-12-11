"""
OpenAPI 3.0 Specification for Incident Orchestrator Agent.
Complete API documentation for Flutter mobile app and backend integration.
"""

from typing import Dict, Any


def get_openapi_spec() -> Dict[str, Any]:
    """
    Generate complete OpenAPI 3.0 specification.
    
    Returns:
        OpenAPI spec as dictionary (can be converted to YAML/JSON)
    """
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "BI3 Incident Orchestrator API",
            "description": "API for Smart Traffic Safety incident response orchestration. Handles VLM events, action execution, mobile device management, and operator overrides.",
            "version": "1.0.0",
            "contact": {
                "name": "BI3 Smart Traffic Safety",
                "email": "support@bi3.example.com"
            }
        },
        "servers": [
            {
                "url": "https://api.bi3.example.com",
                "description": "Production server"
            },
            {
                "url": "http://localhost:8000",
                "description": "Local development"
            }
        ],
        "security": [{"BearerAuth": []}],
        "tags": [
            {"name": "Incidents", "description": "Incident management endpoints"},
            {"name": "Actions", "description": "Action execution and overrides"},
            {"name": "Devices", "description": "Mobile device management"},
            {"name": "Callbacks", "description": "Webhook callbacks from devices/providers"},
            {"name": "Reports", "description": "Report generation"},
            {"name": "System", "description": "Health and metrics"}
        ],
        "paths": {
            **_get_incident_paths(),
            **_get_action_paths(),
            **_get_device_paths(),
            **_get_callback_paths(),
            **_get_report_paths(),
            **_get_system_paths()
        },
        "components": {
            "securitySchemes": _get_security_schemes(),
            "schemas": _get_schemas(),
            "headers": _get_headers(),
            "responses": _get_common_responses()
        },
        "x-fcm-payloads": _get_fcm_payloads(),
        "x-websocket-messages": _get_websocket_messages(),
        "x-error-codes": _get_error_codes()
    }


def _get_incident_paths() -> Dict[str, Any]:
    """Incident management endpoints."""
    return {
        "/v1/incidents": {
            "post": {
                "tags": ["Incidents"],
                "operationId": "createIncident",
                "summary": "Receive VLM event and process incident",
                "description": "Main entry point for VLM events. Creates incident, evaluates policies, builds action plan, and initiates execution.",
                "security": [{"BearerAuth": ["incidents:write"]}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/IncidentCreateRequest"},
                            "example": {
                                "incident_id": "inc-2024-001",
                                "vlm_summary": {
                                    "confidence": 0.92,
                                    "incident_type": "vehicle_collision",
                                    "description": "Two-car collision at intersection",
                                    "vehicles_involved": 2,
                                    "recommended_alerts": ["call", "sms"],
                                    "ambiguous": False
                                },
                                "enhanced_report": {
                                    "report_text": "Detailed collision report...",
                                    "risk_score": 8,
                                    "executive_summary": "High-speed collision detected"
                                },
                                "location": {"lat": 12.9716, "lon": 77.5946},
                                "history": []
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Incident created and processed",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/OrchestratorOutput"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "500": {"$ref": "#/components/responses/InternalError"}
                },
                "x-idempotency": {
                    "header": "Idempotency-Key",
                    "description": "Use incident_id as idempotency key. Duplicate requests within 24h return cached response."
                }
            }
        },
        "/v1/incidents/{incident_id}": {
            "get": {
                "tags": ["Incidents"],
                "operationId": "getIncident",
                "summary": "Fetch incident details",
                "description": "Retrieve incident with enhanced report, action plan, and audit trail.",
                "security": [{"BearerAuth": ["incidents:read"]}],
                "parameters": [
                    {
                        "name": "incident_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "inc-2024-001"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Incident details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/IncidentResponse"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "401": {"$ref": "#/components/responses/Unauthorized"}
                }
            }
        }
    }


def _get_action_paths() -> Dict[str, Any]:
    """Action management endpoints."""
    return {
        "/v1/actions/{incident_id}": {
            "post": {
                "tags": ["Actions"],
                "operationId": "manualOverride",
                "summary": "Manual override or trigger actions",
                "description": "Operator-initiated override for incident actions. Can approve, reject, escalate, or cancel pending actions.",
                "security": [{"BearerAuth": ["actions:write"]}],
                "parameters": [
                    {
                        "name": "incident_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ManualOverrideRequest"},
                            "example": {
                                "action": "approve",
                                "reason": "Verified collision via CCTV",
                                "operator_id": "op-123",
                                "target_actions": None
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Override applied",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "message": {"type": "string"},
                                        "updated_actions": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/ActionPlanItem"}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        "/v1/agent/decision": {
            "post": {
                "tags": ["Actions"],
                "operationId": "agentDecision",
                "summary": "Operator-initiated decision override",
                "description": "Submit operator decision for queued incidents. Can dispatch, escalate, or dismiss.",
                "security": [{"BearerAuth": ["decisions:write"]}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AgentDecisionRequest"},
                            "example": {
                                "incident_id": "inc-2024-001",
                                "decision": "dispatch",
                                "additional_actions": [],
                                "notes": "Confirmed by traffic camera"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Decision processed",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ActionResult"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                }
            }
        }
    }


def _get_device_paths() -> Dict[str, Any]:
    """Device management endpoints."""
    return {
        "/v1/devices/register": {
            "post": {
                "tags": ["Devices"],
                "operationId": "registerDevice",
                "summary": "Register mobile device",
                "description": "Register a mobile device with capabilities and push token for action execution.",
                "security": [{"DeviceAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/DeviceRegisterRequest"},
                            "example": {
                                "device_id": "device-abc123",
                                "push_token": "fcm:token...",
                                "capabilities": {
                                    "calls": True,
                                    "sms": True,
                                    "push": True
                                },
                                "device_api_key": "per-device-key-from-keystore"
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Device registered",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "device_id": {"type": "string"},
                                        "registered_at": {"type": "string", "format": "date-time"},
                                        "status": {"type": "string", "enum": ["active", "pending_verification"]}
                                    }
                                }
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "409": {
                        "description": "Device already registered",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        }
                    }
                }
            }
        },
        "/v1/devices/{device_id}": {
            "get": {
                "tags": ["Devices"],
                "operationId": "getDevice",
                "summary": "Get device status and capabilities",
                "security": [{"BearerAuth": ["devices:read"]}],
                "parameters": [
                    {
                        "name": "device_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Device info",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DeviceInfo"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        }
    }


def _get_callback_paths() -> Dict[str, Any]:
    """Callback endpoints for devices and providers."""
    return {
        "/v1/mobile/callback": {
            "post": {
                "tags": ["Callbacks"],
                "operationId": "mobileCallback",
                "summary": "Mobile app reports action execution results",
                "description": "Called by mobile app after executing an action (call, SMS). Updates action status and triggers next steps.",
                "security": [{"DeviceAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/MobileCallback"},
                            "example": {
                                "action_id": "act-123",
                                "device_id": "device-abc123",
                                "status": "acknowledged",
                                "call_state": "CALL_STATE_OFFHOOK",
                                "duration_seconds": 45,
                                "timestamp": "2024-01-15T10:30:00Z"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Callback processed",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "received": {"type": "boolean"},
                                        "next_action": {
                                            "type": "object",
                                            "nullable": True,
                                            "description": "Next action to execute, if any"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                },
                "x-retry-semantics": {
                    "idempotent": True,
                    "retry_after_header": True,
                    "backoff": "exponential",
                    "max_retries": 3
                }
            }
        },
        "/v1/webhooks/voip": {
            "post": {
                "tags": ["Callbacks"],
                "operationId": "voipCallback",
                "summary": "VoIP provider status callback",
                "description": "Webhook endpoint for VoIP provider to report call status updates.",
                "security": [{"WebhookSignature": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/VoIPCallbackPayload"},
                            "example": {
                                "call_id": "voip-call-456",
                                "action_id": "act-123",
                                "status": "answered",
                                "duration_seconds": 30,
                                "timestamp": "2024-01-15T10:30:00Z",
                                "provider_details": {"codec": "PCMU"}
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Callback acknowledged"},
                    "400": {"$ref": "#/components/responses/BadRequest"}
                },
                "x-mtls-required": True
            }
        }
    }


def _get_report_paths() -> Dict[str, Any]:
    """Report generation endpoints."""
    return {
        "/v1/reports/{incident_id}/generate": {
            "post": {
                "tags": ["Reports"],
                "operationId": "generateReport",
                "summary": "Trigger enhanced report generation",
                "description": "Manually trigger Gemma enhancement for an incident report.",
                "security": [{"BearerAuth": ["reports:write"]}],
                "parameters": [
                    {
                        "name": "incident_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "202": {
                        "description": "Report generation started",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "enum": ["processing"]},
                                        "estimated_completion": {"type": "string", "format": "date-time"}
                                    }
                                }
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        }
    }


def _get_system_paths() -> Dict[str, Any]:
    """System health and metrics endpoints."""
    return {
        "/health": {
            "get": {
                "tags": ["System"],
                "operationId": "healthCheck",
                "summary": "Health check",
                "security": [],
                "responses": {
                    "200": {
                        "description": "Service healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                        "version": {"type": "string"},
                                        "components": {
                                            "type": "object",
                                            "properties": {
                                                "database": {"type": "string"},
                                                "ollama": {"type": "string"},
                                                "voip_provider": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/metrics": {
            "get": {
                "tags": ["System"],
                "operationId": "getMetrics",
                "summary": "Prometheus metrics",
                "security": [{"BearerAuth": ["metrics:read"]}],
                "responses": {
                    "200": {
                        "description": "Prometheus metrics",
                        "content": {
                            "text/plain": {
                                "example": "# HELP incidents_total Total incidents processed\nincidents_total{status=\"dispatched\"} 150\nincidents_total{status=\"escalated\"} 12"
                            }
                        }
                    }
                }
            }
        }
    }


def _get_security_schemes() -> Dict[str, Any]:
    """Security scheme definitions."""
    return {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token with required scopes. Include in Authorization header: `Bearer <token>`"
        },
        "DeviceAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Device-API-Key",
            "description": "Per-device API key stored in Android Keystore"
        },
        "WebhookSignature": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Webhook-Signature",
            "description": "HMAC-SHA256 signature of request body"
        }
    }


def _get_schemas() -> Dict[str, Any]:
    """Component schemas."""
    return {
        "IncidentCreateRequest": {
            "type": "object",
            "required": ["vlm_summary", "enhanced_report"],
            "properties": {
                "incident_id": {"type": "string", "description": "Optional, auto-generated if not provided"},
                "vlm_summary": {"$ref": "#/components/schemas/VLMSummary"},
                "enhanced_report": {"$ref": "#/components/schemas/EnhancedReportData"},
                "location": {"$ref": "#/components/schemas/Location"},
                "history": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/HistoricalIncident"}
                }
            }
        },
        "VLMSummary": {
            "type": "object",
            "required": ["confidence", "incident_type"],
            "properties": {
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "incident_type": {"type": "string"},
                "description": {"type": "string"},
                "vehicles_involved": {"type": "integer"},
                "recommended_alerts": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["call", "sms", "notify"]}
                },
                "ambiguous": {"type": "boolean", "default": False}
            }
        },
        "EnhancedReportData": {
            "type": "object",
            "required": ["report_text", "risk_score"],
            "properties": {
                "report_text": {"type": "string"},
                "risk_score": {"type": "integer", "minimum": 1, "maximum": 10},
                "executive_summary": {"type": "string"},
                "evidence_mapping": {"type": "object"}
            }
        },
        "Location": {
            "type": "object",
            "required": ["lat", "lon"],
            "properties": {
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180}
            }
        },
        "HistoricalIncident": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "incident_type": {"type": "string"},
                "risk_score": {"type": "integer"},
                "summary": {"type": "string"}
            }
        },
        "ActionPlanItem": {
            "type": "object",
            "required": ["action_id", "type", "target_role", "number", "text"],
            "properties": {
                "action_id": {"type": "string", "format": "uuid"},
                "type": {"type": "string", "enum": ["call", "sms", "notify"]},
                "target_role": {"type": "string", "enum": ["ambulance", "police", "traffic_control"]},
                "number": {"type": "string"},
                "text": {"type": "string"},
                "retry_policy": {"$ref": "#/components/schemas/RetryPolicy"},
                "status": {"type": "string", "enum": ["pending", "sent", "acknowledged", "failed", "escalated"]},
                "attempts": {"type": "integer"},
                "last_result": {"type": "object"},
                "created_at": {"type": "string", "format": "date-time"}
            }
        },
        "RetryPolicy": {
            "type": "object",
            "properties": {
                "attempts": {"type": "integer", "default": 3},
                "backoff_seconds": {"type": "integer", "default": 10}
            }
        },
        "AuditEntry": {
            "type": "object",
            "required": ["ts", "actor", "step", "outcome"],
            "properties": {
                "ts": {"type": "string", "format": "date-time"},
                "actor": {"type": "string"},
                "action_id": {"type": "string"},
                "step": {"type": "string"},
                "outcome": {"type": "string"},
                "details": {"type": "object"}
            }
        },
        "ActionResult": {
            "type": "object",
            "required": ["incident_id", "action_plan", "final_status", "audit"],
            "properties": {
                "incident_id": {"type": "string"},
                "action_plan": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ActionPlanItem"}
                },
                "final_status": {
                    "type": "string",
                    "enum": ["dispatched", "escalated", "queued_for_review", "logged_only"]
                },
                "audit": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/AuditEntry"}
                },
                "operator_message": {"type": "string"},
                "device_status": {"type": "object"}
            }
        },
        "OrchestratorOutput": {
            "type": "object",
            "required": ["action_result", "api_spec"],
            "properties": {
                "action_result": {"$ref": "#/components/schemas/ActionResult"},
                "api_spec": {"type": "object", "description": "OpenAPI 3.0 specification"}
            }
        },
        "IncidentResponse": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "status": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "enhanced_report": {"$ref": "#/components/schemas/EnhancedReportData"},
                "action_plan": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ActionPlanItem"}
                },
                "audit": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/AuditEntry"}
                }
            }
        },
        "ManualOverrideRequest": {
            "type": "object",
            "required": ["action", "reason", "operator_id"],
            "properties": {
                "action": {"type": "string", "enum": ["approve", "reject", "escalate", "cancel"]},
                "reason": {"type": "string"},
                "operator_id": {"type": "string"},
                "target_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific action IDs to override (all if null)"
                }
            }
        },
        "AgentDecisionRequest": {
            "type": "object",
            "required": ["incident_id", "decision"],
            "properties": {
                "incident_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["dispatch", "escalate", "dismiss"]},
                "additional_actions": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ActionPlanItem"}
                },
                "notes": {"type": "string"}
            }
        },
        "DeviceRegisterRequest": {
            "type": "object",
            "required": ["device_id", "push_token", "capabilities", "device_api_key"],
            "properties": {
                "device_id": {"type": "string"},
                "push_token": {"type": "string"},
                "capabilities": {"$ref": "#/components/schemas/DeviceCapabilities"},
                "device_api_key": {"type": "string", "description": "Per-device API key from Android Keystore"}
            }
        },
        "DeviceCapabilities": {
            "type": "object",
            "properties": {
                "calls": {"type": "boolean", "default": True},
                "sms": {"type": "boolean", "default": True},
                "push": {"type": "boolean", "default": True}
            }
        },
        "DeviceInfo": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "push_token": {"type": "string"},
                "capabilities": {"$ref": "#/components/schemas/DeviceCapabilities"},
                "is_online": {"type": "boolean"},
                "last_seen": {"type": "string", "format": "date-time"}
            }
        },
        "MobileCallback": {
            "type": "object",
            "required": ["action_id", "device_id", "status", "timestamp"],
            "properties": {
                "action_id": {"type": "string"},
                "device_id": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "sent", "acknowledged", "failed", "escalated"]},
                "call_state": {"type": "string", "enum": ["CALL_STATE_IDLE", "CALL_STATE_RINGING", "CALL_STATE_OFFHOOK"]},
                "duration_seconds": {"type": "integer"},
                "error_message": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "details": {"type": "object"}
            }
        },
        "VoIPCallbackPayload": {
            "type": "object",
            "required": ["call_id", "action_id", "status", "timestamp"],
            "properties": {
                "call_id": {"type": "string"},
                "action_id": {"type": "string"},
                "status": {"type": "string", "enum": ["initiated", "ringing", "answered", "completed", "failed", "busy", "no_answer"]},
                "duration_seconds": {"type": "integer"},
                "timestamp": {"type": "string", "format": "date-time"},
                "provider_details": {"type": "object"}
            }
        },
        "ErrorResponse": {
            "type": "object",
            "required": ["error_code", "message"],
            "properties": {
                "error_code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object"},
                "timestamp": {"type": "string", "format": "date-time"}
            }
        }
    }


def _get_headers() -> Dict[str, Any]:
    """Common headers."""
    return {
        "X-Request-ID": {
            "description": "Unique request ID for tracing",
            "schema": {"type": "string", "format": "uuid"}
        },
        "X-Idempotency-Key": {
            "description": "Idempotency key for safe retries",
            "schema": {"type": "string"}
        },
        "Retry-After": {
            "description": "Seconds to wait before retrying",
            "schema": {"type": "integer"}
        }
    }


def _get_common_responses() -> Dict[str, Any]:
    """Common response definitions."""
    return {
        "BadRequest": {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error_code": "INVALID_REQUEST",
                        "message": "Risk score must be between 1 and 10",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        "Unauthorized": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error_code": "UNAUTHORIZED",
                        "message": "Invalid or expired token",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        "NotFound": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error_code": "NOT_FOUND",
                        "message": "Incident not found",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        "InternalError": {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {
                        "error_code": "INTERNAL_ERROR",
                        "message": "An unexpected error occurred",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }


def _get_fcm_payloads() -> Dict[str, Any]:
    """FCM push notification payload examples."""
    return {
        "action_plan_delivery": {
            "description": "Deliver action plan to mobile device",
            "example": {
                "to": "device_fcm_token",
                "priority": "high",
                "ttl": "300s",
                "data": {
                    "type": "action_plan",
                    "incident_id": "inc-2024-001",
                    "actions": [
                        {
                            "action_id": "act-123",
                            "type": "call",
                            "target_role": "ambulance",
                            "number": "{REGIONAL_AMBULANCE_NUMBER}",
                            "text": "Emergency alert: vehicle collision detected...",
                            "timeout_seconds": 30
                        }
                    ],
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                "notification": {
                    "title": "Emergency Action Required",
                    "body": "Incident inc-2024-001 requires immediate action"
                }
            }
        },
        "status_update": {
            "description": "Update device on action status",
            "example": {
                "to": "device_fcm_token",
                "priority": "high",
                "data": {
                    "type": "status_update",
                    "action_id": "act-123",
                    "status": "acknowledged",
                    "timestamp": "2024-01-15T10:31:00Z"
                }
            }
        }
    }


def _get_websocket_messages() -> Dict[str, Any]:
    """WebSocket message format examples."""
    return {
        "connect": {
            "description": "Initial connection with authentication",
            "example": {
                "type": "connect",
                "payload": {
                    "device_id": "device-abc123",
                    "api_key": "per-device-key"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "message_id": "msg-001"
            }
        },
        "action_plan": {
            "description": "Server sends action plan to device",
            "example": {
                "type": "action_plan",
                "payload": {
                    "incident_id": "inc-2024-001",
                    "actions": [
                        {
                            "action_id": "act-123",
                            "type": "call",
                            "number": "{REGIONAL_AMBULANCE_NUMBER}",
                            "text": "Emergency alert..."
                        }
                    ]
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "message_id": "msg-002"
            }
        },
        "ack": {
            "description": "Device acknowledges message receipt",
            "example": {
                "type": "ack",
                "payload": {
                    "message_id": "msg-002",
                    "status": "received"
                },
                "timestamp": "2024-01-15T10:30:01Z",
                "message_id": "msg-003"
            }
        },
        "heartbeat": {
            "description": "Keep-alive heartbeat",
            "example": {
                "type": "heartbeat",
                "payload": {
                    "device_id": "device-abc123",
                    "battery_level": 85,
                    "network_type": "lte"
                },
                "timestamp": "2024-01-15T10:30:30Z",
                "message_id": "msg-004"
            }
        }
    }


def _get_error_codes() -> Dict[str, Any]:
    """Error code definitions."""
    return {
        "INVALID_REQUEST": {
            "http_status": 400,
            "description": "Request validation failed",
            "retryable": False
        },
        "UNAUTHORIZED": {
            "http_status": 401,
            "description": "Authentication required or failed",
            "retryable": False
        },
        "FORBIDDEN": {
            "http_status": 403,
            "description": "Insufficient permissions",
            "retryable": False
        },
        "NOT_FOUND": {
            "http_status": 404,
            "description": "Resource not found",
            "retryable": False
        },
        "CONFLICT": {
            "http_status": 409,
            "description": "Resource conflict (e.g., duplicate device)",
            "retryable": False
        },
        "RATE_LIMITED": {
            "http_status": 429,
            "description": "Too many requests",
            "retryable": True,
            "retry_after_header": True
        },
        "INTERNAL_ERROR": {
            "http_status": 500,
            "description": "Unexpected server error",
            "retryable": True
        },
        "DEVICE_OFFLINE": {
            "http_status": 503,
            "description": "Target device is offline",
            "retryable": True
        },
        "VOIP_UNAVAILABLE": {
            "http_status": 503,
            "description": "VoIP provider unavailable",
            "retryable": True
        }
    }
