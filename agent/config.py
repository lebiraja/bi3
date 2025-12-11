"""
Configuration for Incident Orchestrator Agent.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RegionalContacts:
    """Regional emergency contact configuration."""
    
    # Police contacts - HARDCODED
    police_primary: str = "+919535879330"
    police_alternates: List[str] = field(default_factory=list)  # No alternates
    
    # Ambulance contacts - HARDCODED
    ambulance_primary: str = "+916369445764"
    ambulance_alternates: List[str] = field(default_factory=list)  # No alternates
    
    # Traffic control - uses police number as fallback
    traffic_control_primary: str = "+919535879330"
    traffic_control_alternates: List[str] = field(default_factory=list)


@dataclass
class RetryPolicyConfig:
    """Retry policy configuration."""
    
    max_attempts: int = 3
    backoff_seconds: int = 10
    call_timeout_seconds: int = 30


@dataclass
class VoIPConfig:
    """VoIP provider configuration."""
    
    provider_url: str = "{VOIP_PROVIDER_URL}"
    api_key: str = "{VOIP_API_KEY}"
    tts_voice: str = "en-US-Standard-D"
    callback_url: str = "{VOIP_CALLBACK_URL}"


@dataclass
class FCMConfig:
    """Firebase Cloud Messaging configuration."""
    
    server_key: str = "{FCM_SERVER_KEY}"
    sender_id: str = "{FCM_SENDER_ID}"
    ttl_seconds: int = 300
    priority: str = "high"


@dataclass
class PolicyConfig:
    """Policy thresholds configuration."""
    
    # Risk score thresholds
    auto_action_min_risk_score: int = 7
    queue_for_review_min_risk_score: int = 4
    
    # Confidence thresholds
    auto_action_min_confidence: float = 0.85
    
    # Ambiguity detection
    ambiguous_keywords: List[str] = field(default_factory=lambda: [
        "ambiguous",
        "unclear",
        "uncertain",
        "possible",
        "might be"
    ])


@dataclass
class AgentConfig:
    """Main agent configuration."""
    
    agent_id: str = "incident-orchestrator-v1"
    regional_contacts: RegionalContacts = field(default_factory=RegionalContacts)
    retry_policy: RetryPolicyConfig = field(default_factory=RetryPolicyConfig)
    voip: VoIPConfig = field(default_factory=VoIPConfig)
    fcm: FCMConfig = field(default_factory=FCMConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    
    # Logging
    log_level: str = "INFO"
    audit_retention_days: int = 365
    encrypt_audit_at_rest: bool = True
    
    # Rate limiting
    max_actions_per_minute: int = 60
    max_calls_per_minute: int = 10


# Default configuration instance
DEFAULT_CONFIG = AgentConfig()
