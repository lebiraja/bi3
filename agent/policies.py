"""
Policy Engine for Incident Orchestrator Agent.
Enforces action gating, target selection, and safety rules.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass

from .config import AgentConfig, DEFAULT_CONFIG
from .models import (
    IncidentInput,
    ActionType,
    TargetRole,
    ActionPlanItem,
    AuditEntry,
    RetryPolicy,
    FinalStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    should_auto_action: bool
    should_queue_for_review: bool
    should_log_only: bool
    is_ambiguous: bool
    reason: str
    final_status: FinalStatus


class PolicyEngine:
    """
    Enforces all policies for incident response actions.
    
    Policies:
    1. Action Gating - Based on risk score and confidence
    2. Target Selection - Emergency contact routing
    3. Ambiguity Detection - Escalate unclear incidents
    4. Retry Policy - Attempt limits and backoff
    """
    
    def __init__(self, config: AgentConfig = None):
        self.config = config or DEFAULT_CONFIG
        self.policy = self.config.policy
    
    def evaluate_action_gating(self, incident: IncidentInput) -> PolicyDecision:
        """
        Evaluate action gating policy based on risk score and confidence.
        
        Rules:
        - Risk >= 7 OR (confidence >= 0.85 AND recommended_alerts include call/sms): Auto-action
        - Risk 4-6: Queue for operator review
        - Risk < 4: Log only, low-priority notification
        - Ambiguous detection: Never auto-call, escalate
        """
        risk_score = incident.enhanced_report.risk_score
        confidence = incident.vlm_summary.confidence
        recommended_alerts = incident.vlm_summary.recommended_alerts or []
        is_ambiguous = self._detect_ambiguity(incident)
        
        # Check for ambiguity first
        if is_ambiguous:
            logger.warning(f"Ambiguous incident detected: {incident.incident_id}")
            return PolicyDecision(
                should_auto_action=False,
                should_queue_for_review=True,
                should_log_only=False,
                is_ambiguous=True,
                reason="Ambiguous collision detected - escalating to operator",
                final_status=FinalStatus.QUEUED_FOR_REVIEW
            )
        
        # Check auto-action criteria
        has_call_sms_recommendation = any(
            alert in recommended_alerts for alert in ["call", "sms"]
        )
        
        auto_action_by_risk = risk_score >= self.policy.auto_action_min_risk_score
        auto_action_by_confidence = (
            confidence >= self.policy.auto_action_min_confidence and
            has_call_sms_recommendation
        )
        
        if auto_action_by_risk or auto_action_by_confidence:
            reason = (
                f"Auto-action triggered: risk_score={risk_score}, "
                f"confidence={confidence:.2f}"
            )
            if auto_action_by_risk:
                reason += f" (risk >= {self.policy.auto_action_min_risk_score})"
            if auto_action_by_confidence:
                reason += f" (confidence >= {self.policy.auto_action_min_confidence} with call/sms recommendation)"
            
            return PolicyDecision(
                should_auto_action=True,
                should_queue_for_review=False,
                should_log_only=False,
                is_ambiguous=False,
                reason=reason,
                final_status=FinalStatus.DISPATCHED
            )
        
        # Check queue for review criteria
        if risk_score >= self.policy.queue_for_review_min_risk_score:
            return PolicyDecision(
                should_auto_action=False,
                should_queue_for_review=True,
                should_log_only=False,
                is_ambiguous=False,
                reason=f"Risk score {risk_score} in review range (4-6) - queuing for operator",
                final_status=FinalStatus.QUEUED_FOR_REVIEW
            )
        
        # Low risk - log only
        return PolicyDecision(
            should_auto_action=False,
            should_queue_for_review=False,
            should_log_only=True,
            is_ambiguous=False,
            reason=f"Low risk score {risk_score} - logging only with low-priority notification",
            final_status=FinalStatus.LOGGED_ONLY
        )
    
    def _detect_ambiguity(self, incident: IncidentInput) -> bool:
        """Detect if the incident is ambiguous based on VLM output."""
        # Check explicit ambiguous flag
        if incident.vlm_summary.ambiguous:
            return True
        
        # Check for ambiguous keywords in description
        description = incident.vlm_summary.description or ""
        report_text = incident.enhanced_report.report_text or ""
        combined_text = f"{description} {report_text}".lower()
        
        for keyword in self.policy.ambiguous_keywords:
            if keyword.lower() in combined_text:
                return True
        
        return False
    
    def select_targets(
        self,
        incident: IncidentInput,
        required_roles: List[TargetRole]
    ) -> Dict[TargetRole, List[str]]:
        """
        Select target phone numbers for each role.
        
        Uses location to find nearest contacts (placeholder logic),
        falls back to regional defaults.
        """
        contacts = self.config.regional_contacts
        targets = {}
        
        for role in required_roles:
            if role == TargetRole.AMBULANCE:
                targets[role] = [contacts.ambulance_primary] + contacts.ambulance_alternates
            elif role == TargetRole.POLICE:
                targets[role] = [contacts.police_primary] + contacts.police_alternates
            elif role == TargetRole.TRAFFIC_CONTROL:
                targets[role] = [contacts.traffic_control_primary] + contacts.traffic_control_alternates
        
        # If location is provided, could use geolocation to find nearest contacts
        # This is a placeholder for actual geolocation logic
        if incident.location:
            logger.info(
                f"Using location ({incident.location.lat}, {incident.location.lon}) "
                f"for contact selection - falling back to regional defaults"
            )
        
        return targets
    
    def determine_required_roles(
        self,
        incident: IncidentInput
    ) -> List[TargetRole]:
        """
        Determine which emergency roles need to be contacted based on incident type.
        """
        incident_type = incident.vlm_summary.incident_type.lower()
        risk_score = incident.enhanced_report.risk_score
        
        roles = []
        
        # High severity incidents need all services
        if risk_score >= 8:
            return [TargetRole.AMBULANCE, TargetRole.POLICE, TargetRole.TRAFFIC_CONTROL]
        
        # Collision-related incidents
        if any(word in incident_type for word in ["collision", "crash", "accident"]):
            roles.append(TargetRole.AMBULANCE)
            roles.append(TargetRole.POLICE)
        
        # Traffic violations
        if any(word in incident_type for word in ["violation", "reckless", "speeding"]):
            roles.append(TargetRole.POLICE)
            roles.append(TargetRole.TRAFFIC_CONTROL)
        
        # Road hazards
        if any(word in incident_type for word in ["hazard", "obstruction", "debris"]):
            roles.append(TargetRole.TRAFFIC_CONTROL)
        
        # Default to police if no specific match
        if not roles:
            roles.append(TargetRole.POLICE)
        
        return list(set(roles))  # Remove duplicates
    
    def get_retry_policy(self) -> RetryPolicy:
        """Get the configured retry policy."""
        return RetryPolicy(
            attempts=self.config.retry_policy.max_attempts,
            backoff_seconds=self.config.retry_policy.backoff_seconds
        )
    
    def generate_spoken_message(self, incident: IncidentInput) -> str:
        """Generate concise spoken message for calls (TTS)."""
        location_str = "unknown location"
        if incident.location:
            location_str = f"coordinates {incident.location.lat:.4f}, {incident.location.lon:.4f}"
        
        incident_type = incident.vlm_summary.incident_type
        risk_level = "critical" if incident.enhanced_report.risk_score >= 8 else "high"
        
        return (
            f"Emergency alert: {incident_type} detected at {location_str}. "
            f"Risk level: {risk_level}. "
            f"A detailed report has been sent via SMS. "
            f"Incident ID: {incident.incident_id[:8]}."
        )
    
    def generate_sms_message(
        self,
        incident: IncidentInput,
        report_link: Optional[str] = None
    ) -> str:
        """Generate detailed SMS message."""
        timestamp = incident.timestamp or "unknown"
        incident_type = incident.vlm_summary.incident_type
        risk_score = incident.enhanced_report.risk_score
        
        location_str = "Unknown"
        if incident.location:
            location_str = f"({incident.location.lat:.6f}, {incident.location.lon:.6f})"
        
        # Get executive summary if available
        evidence = incident.enhanced_report.executive_summary or ""
        if len(evidence) > 100:
            evidence = evidence[:100] + "..."
        
        message = (
            f"🚨 TRAFFIC INCIDENT ALERT\n"
            f"ID: {incident.incident_id[:8]}\n"
            f"Time: {timestamp[:19]}\n"
            f"Type: {incident_type}\n"
            f"Severity: {risk_score}/10\n"
            f"Location: {location_str}\n"
        )
        
        if evidence:
            message += f"Summary: {evidence}\n"
        
        if report_link:
            message += f"Full Report: {report_link}"
        
        return message
    
    def create_audit_entry(
        self,
        actor: str,
        step: str,
        outcome: str,
        action_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Create an audit entry with current timestamp."""
        return AuditEntry(
            actor=actor,
            step=step,
            outcome=outcome,
            action_id=action_id,
            details=details
        )
