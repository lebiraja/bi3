"""
Main Incident Orchestrator for BI3 Smart Traffic Safety.
Coordinates policy enforcement, action planning, and execution.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

from .config import AgentConfig, DEFAULT_CONFIG
from .models import (
    IncidentInput,
    ActionPlanItem,
    ActionType,
    TargetRole,
    ActionStatus,
    ActionResult,
    FinalStatus,
    AuditEntry,
    OrchestratorOutput,
    DeviceInfo,
    MobileCallback,
)
from .policies import PolicyEngine, PolicyDecision
from .actions import ActionExecutor
from .api_spec import get_openapi_spec

logger = logging.getLogger(__name__)


class IncidentOrchestrator:
    """
    Main orchestrator for incident response.
    
    Responsibilities:
    1. Receive VLM events and enhanced reports
    2. Apply policy-based action gating
    3. Build action plans with proper targeting
    4. Execute actions via mobile devices or VoIP
    5. Log all decisions and actions for audit
    6. Provide rollback/cancel capabilities
    """
    
    def __init__(self, config: AgentConfig = None, device_manager=None):
        self.config = config or DEFAULT_CONFIG
        self.agent_id = self.config.agent_id
        self.policy_engine = PolicyEngine(self.config)
        self.action_executor = ActionExecutor(self.config, device_manager=device_manager)
        
        # In-memory incident store (in production, use database)
        self.incidents: Dict[str, Dict[str, Any]] = {}
    
    def process_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incident synchronously (wrapper for async method).
        
        Args:
            incident_data: Raw incident JSON
            
        Returns:
            Complete output with action_result and api_spec
        """
        return asyncio.run(self.process_incident_async(incident_data))
    
    async def process_incident_async(
        self,
        incident_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process an incident and generate response actions.
        
        This is the main entry point for incident processing.
        
        Args:
            incident_data: Raw incident JSON matching IncidentInput schema
            
        Returns:
            Complete output with action_result and api_spec
        """
        audit = []
        
        # Parse and validate input
        try:
            incident = IncidentInput(**incident_data)
        except Exception as e:
            logger.error(f"Failed to parse incident data: {e}")
            return self._create_error_output(
                incident_id=incident_data.get("incident_id", "unknown"),
                error=str(e),
                audit=audit
            )
        
        audit.append(self._create_audit(
            "Incident received",
            f"Processing incident {incident.incident_id}",
            details={
                "risk_score": incident.enhanced_report.risk_score,
                "confidence": incident.vlm_summary.confidence,
                "incident_type": incident.vlm_summary.incident_type
            }
        ))
        
        # Step 1: Apply policy evaluation
        policy_decision = self.policy_engine.evaluate_action_gating(incident)
        
        audit.append(self._create_audit(
            "Policy evaluation",
            policy_decision.reason,
            details={"final_status": policy_decision.final_status.value}
        ))
        
        # Step 2: Build action plan based on policy decision
        action_plan = await self._build_action_plan(incident, policy_decision, audit)
        
        # Step 3: Execute actions if auto-action is approved
        if policy_decision.should_auto_action and action_plan:
            action_plan, execution_audit = await self.action_executor.execute_action_plan(
                action_plan, self.agent_id
            )
            audit.extend(execution_audit)
        
        # Step 4: Build result
        action_result = ActionResult(
            incident_id=incident.incident_id,
            action_plan=action_plan,
            final_status=policy_decision.final_status,
            audit=audit,
            operator_message=self._generate_operator_message(incident, policy_decision)
            if policy_decision.should_queue_for_review else None
        )
        
        # Store incident state
        self.incidents[incident.incident_id] = {
            "incident": incident.dict(),
            "action_result": action_result.dict(),
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        
        audit.append(self._create_audit(
            "Processing complete",
            f"Final status: {policy_decision.final_status.value}"
        ))
        
        # Step 5: Build complete output with API spec
        output = OrchestratorOutput(
            action_result=action_result,
            api_spec=get_openapi_spec()
        )
        
        return output.dict()
    
    async def _build_action_plan(
        self,
        incident: IncidentInput,
        policy_decision: PolicyDecision,
        audit: List[AuditEntry]
    ) -> List[ActionPlanItem]:
        """Build the action plan based on policy decision and incident details."""
        action_plan = []
        
        if policy_decision.should_log_only:
            # Create low-priority notification only
            action_plan.append(ActionPlanItem(
                type=ActionType.NOTIFY,
                target_role=TargetRole.TRAFFIC_CONTROL,
                number="operator_dashboard",
                text=f"Low-risk incident logged: {incident.incident_id}",
                status=ActionStatus.PENDING
            ))
            audit.append(self._create_audit(
                "Action plan created",
                "Low-risk: notification only"
            ))
            return action_plan
        
        if policy_decision.should_queue_for_review:
            # Notification for operator review
            action_plan.append(ActionPlanItem(
                type=ActionType.NOTIFY,
                target_role=TargetRole.TRAFFIC_CONTROL,
                number="operator_dashboard",
                text=self._generate_operator_message(incident, policy_decision),
                status=ActionStatus.PENDING
            ))
            audit.append(self._create_audit(
                "Action plan created",
                "Queued for review: operator notification created"
            ))
            return action_plan
        
        # Auto-action: Build full action plan
        required_roles = self.policy_engine.determine_required_roles(incident)
        targets = self.policy_engine.select_targets(incident, required_roles)
        retry_policy = self.policy_engine.get_retry_policy()
        
        # Generate messages
        spoken_message = self.policy_engine.generate_spoken_message(incident)
        sms_message = self.policy_engine.generate_sms_message(
            incident,
            report_link=f"https://bi3.example.com/reports/{incident.incident_id}"
        )
        
        # Create call and SMS actions for each role
        for role in required_roles:
            role_contacts = targets.get(role, [])
            if not role_contacts:
                continue
            
            primary_number = role_contacts[0]
            
            # Call action
            action_plan.append(ActionPlanItem(
                type=ActionType.CALL,
                target_role=role,
                number=primary_number,
                text=spoken_message,
                retry_policy=retry_policy,
                status=ActionStatus.PENDING
            ))
            
            # SMS action (always send)
            action_plan.append(ActionPlanItem(
                type=ActionType.SMS,
                target_role=role,
                number=primary_number,
                text=sms_message,
                retry_policy=retry_policy,
                status=ActionStatus.PENDING
            ))
        
        audit.append(self._create_audit(
            "Action plan created",
            f"Auto-action: {len(action_plan)} actions for roles {[r.value for r in required_roles]}",
            details={"action_count": len(action_plan)}
        ))
        
        return action_plan
    
    def _generate_operator_message(
        self,
        incident: IncidentInput,
        policy_decision: PolicyDecision
    ) -> str:
        """Generate message for operator review."""
        message = (
            f"INCIDENT REQUIRES REVIEW\n"
            f"ID: {incident.incident_id}\n"
            f"Type: {incident.vlm_summary.incident_type}\n"
            f"Risk Score: {incident.enhanced_report.risk_score}/10\n"
            f"Confidence: {incident.vlm_summary.confidence:.2f}\n"
            f"\nReason: {policy_decision.reason}\n"
        )
        
        if policy_decision.is_ambiguous:
            message += "\n⚠️ AMBIGUOUS DETECTION - Manual verification required"
        
        if incident.location:
            message += f"\nLocation: ({incident.location.lat:.6f}, {incident.location.lon:.6f})"
        
        return message
    
    def handle_manual_override(
        self,
        incident_id: str,
        action: str,
        operator_id: str,
        reason: str,
        target_actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Handle manual override from operator.
        
        Args:
            incident_id: Incident to override
            action: One of 'approve', 'reject', 'escalate', 'cancel'
            operator_id: Operator making the override
            reason: Reason for override
            target_actions: Specific action IDs to override (optional)
        """
        if incident_id not in self.incidents:
            return {"error": f"Incident {incident_id} not found"}
        
        incident_state = self.incidents[incident_id]
        action_result = ActionResult(**incident_state["action_result"])
        
        audit_entry = self._create_audit(
            f"Manual override: {action}",
            f"By operator {operator_id}: {reason}",
            details={"target_actions": target_actions}
        )
        action_result.audit.append(audit_entry)
        
        if action == "approve":
            # Execute pending actions
            return {"status": "approved", "message": "Actions will be executed"}
        elif action == "reject":
            # Cancel all pending actions
            for action_item in action_result.action_plan:
                if target_actions is None or action_item.action_id in target_actions:
                    action_item.status = ActionStatus.FAILED
            action_result.final_status = FinalStatus.LOGGED_ONLY
            return {"status": "rejected", "message": "Actions cancelled"}
        elif action == "escalate":
            action_result.final_status = FinalStatus.ESCALATED
            return {"status": "escalated", "message": "Incident escalated"}
        elif action == "cancel":
            for action_item in action_result.action_plan:
                if action_item.status == ActionStatus.PENDING:
                    action_item.status = ActionStatus.FAILED
            return {"status": "cancelled", "message": "Pending actions cancelled"}
        
        return {"error": f"Unknown action: {action}"}
    
    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get incident details by ID."""
        return self.incidents.get(incident_id)
    
    def register_device(self, device: DeviceInfo) -> None:
        """Register a mobile device for action execution."""
        self.action_executor.register_device(device)
    
    def handle_mobile_callback(self, callback: MobileCallback) -> bool:
        """Handle callback from mobile device."""
        return self.action_executor.handle_mobile_callback(callback)
    
    def _create_audit(
        self,
        step: str,
        outcome: str,
        action_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Create an audit entry."""
        return AuditEntry(
            actor=self.agent_id,
            step=step,
            outcome=outcome,
            action_id=action_id,
            details=details
        )
    
    def _create_error_output(
        self,
        incident_id: str,
        error: str,
        audit: List[AuditEntry]
    ) -> Dict[str, Any]:
        """Create error output."""
        audit.append(self._create_audit(
            "Processing failed",
            error
        ))
        
        return {
            "action_result": {
                "incident_id": incident_id,
                "action_plan": [],
                "final_status": FinalStatus.ESCALATED.value,
                "audit": [a.dict() for a in audit],
                "operator_message": f"Processing failed: {error}"
            },
            "api_spec": get_openapi_spec()
        }
