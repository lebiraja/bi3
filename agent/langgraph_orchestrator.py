"""
LangGraph-based Incident Orchestrator for BI3 Smart Traffic Safety.

This module implements the incident response workflow using LangGraph,
providing stateful, multi-step processing with LLM-enhanced decision making.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Annotated, TypedDict, Literal
from operator import add

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .models import (
    IncidentInput,
    ActionPlanItem,
    ActionType,
    TargetRole,
    ActionStatus,
    FinalStatus,
    AuditEntry,
    DeviceInfo,
    MobileCallback,
    RetryPolicy,  # Added missing import
)
from .actions import ActionExecutor
from .api_spec import get_openapi_spec
from .config import AgentConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


# ============ State Schema ============

class IncidentState(TypedDict):
    """State that flows through the LangGraph workflow."""
    # Input data
    incident_id: str
    vlm_summary: Dict[str, Any]
    enhanced_report: Dict[str, Any]
    location: Dict[str, Any] | None
    history: List[Dict[str, Any]]
    
    # LLM conversation
    messages: Annotated[List[BaseMessage], add]
    
    # Processing state
    policy_decision: str  # "auto_dispatch", "queue_review", "log_only"
    risk_assessment: Dict[str, Any]
    llm_reasoning: str
    
    # Actions
    action_plan: List[Dict[str, Any]]
    executed_actions: List[Dict[str, Any]]
    failed_actions: List[Dict[str, Any]]
    needs_retry: bool
    
    # Output
    final_status: str
    audit_trail: Annotated[List[Dict[str, Any]], add]
    operator_message: str | None


# ============ Helper Functions ============

def extract_severity(text: str) -> str:
    """Extract severity from LLM response."""
    text_lower = text.lower()
    if "critical" in text_lower:
        return "critical"
    elif "high" in text_lower:
        return "high"
    elif "medium" in text_lower:
        return "medium"
    return "low"


def extract_urgency(text: str) -> str:
    """Extract urgency from LLM response."""
    text_lower = text.lower()
    if "immediate" in text_lower:
        return "immediate"
    elif "urgent" in text_lower:
        return "urgent"
    return "standard"


def get_contact_number(service: str) -> str:
    """Get contact number for emergency service."""
    contacts = {
        "ambulance": "+916369445764",
        "police": "+919535879330",
        "traffic_control": "+919535879330",
        "fire_department": "+911234567890",
    }
    return contacts.get(service, "+911234567890")


def generate_message(state: IncidentState, service: str) -> str:
    """Generate spoken message for emergency service."""
    incident_type = state['vlm_summary'].get('incident_type', 'unknown incident')
    risk_score = state['enhanced_report'].get('risk_score', 0)
    location = state.get('location')
    
    message = f"Emergency alert: {incident_type} detected. "
    
    if location:
        message += f"Location: coordinates {location['lat']}, {location['lon']}. "
    
    message += f"Risk level: {'critical' if risk_score >= 8 else 'high' if risk_score >= 6 else 'moderate'}. "
    message += f"Incident ID: {state['incident_id']}. "
    message += "Please respond immediately."
    
    return message


def generate_sms(state: IncidentState, service: str) -> str:
    """Generate SMS content for emergency service."""
    incident_type = state['vlm_summary'].get('incident_type', 'unknown')
    risk_score = state['enhanced_report'].get('risk_score', 0)
    location = state.get('location')
    
    sms = f"🚨 TRAFFIC INCIDENT\n"
    sms += f"Type: {incident_type}\n"
    sms += f"Risk: {risk_score}/10\n"
    
    if location:
        sms += f"Location: {location['lat']}, {location['lon']}\n"
    
    sms += f"ID: {state['incident_id'][:8]}\n"
    sms += "Respond ASAP"
    
    return sms


def create_audit_entry(step: str, outcome: str, action_id: str = None, details: Dict = None) -> Dict[str, Any]:
    """Create an audit entry."""
    return {
        'ts': datetime.utcnow().isoformat() + 'Z',
        'actor': 'langgraph-orchestrator',
        'step': step,
        'outcome': outcome,
        'action_id': action_id,
        'details': details
    }


# ============ Graph Nodes ============

async def analyze_incident(state: IncidentState) -> IncidentState:
    """
    Node 1: Analyze incident with LLM for enhanced risk assessment.
    """
    logger.info(f"Analyzing incident {state['incident_id']} with LLM")
    
    # Initialize LLM
    llm = ChatOllama(
        model="gemma3:1b",
        base_url="http://localhost:11434",
        temperature=0.3
    )
    
    # Build analysis prompt
    prompt = f"""Analyze this traffic incident and provide a risk assessment:

Incident Type: {state['vlm_summary'].get('incident_type', 'unknown')}
VLM Confidence: {state['vlm_summary'].get('confidence', 0):.2f}
Risk Score: {state['enhanced_report'].get('risk_score', 0)}/10
Vehicles Involved: {state['vlm_summary'].get('vehicles_involved', 'unknown')}

Report Summary:
{state['enhanced_report'].get('executive_summary', 'No summary available')}

Assess:
1. Severity (critical/high/medium/low)
2. Urgency (immediate/urgent/standard)
3. Required emergency services (ambulance, police, traffic_control, fire_department)
4. Brief reasoning

Format: Severity: [level] | Urgency: [level] | Services: [list] | Reasoning: [text]"""
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        state['messages'] = [HumanMessage(content=prompt), response]
        state['llm_reasoning'] = response.content
        state['risk_assessment'] = {
            'severity': extract_severity(response.content),
            'urgency': extract_urgency(response.content),
            'llm_analysis': response.content
        }
        
        # Add audit entry
        state['audit_trail'] = [create_audit_entry(
            "LLM Analysis",
            f"Severity: {state['risk_assessment']['severity']}, Urgency: {state['risk_assessment']['urgency']}",
            details={'llm_response': response.content[:200]}
        )]
        
        logger.info(f"LLM assessment: {state['risk_assessment']['severity']} severity, {state['risk_assessment']['urgency']} urgency")
        
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}, using fallback")
        # Fallback to rule-based assessment
        risk_score = state['enhanced_report'].get('risk_score', 0)
        state['risk_assessment'] = {
            'severity': 'critical' if risk_score >= 8 else 'high' if risk_score >= 6 else 'medium',
            'urgency': 'immediate' if risk_score >= 8 else 'urgent',
            'llm_analysis': 'LLM unavailable, using rule-based assessment'
        }
        state['audit_trail'] = [create_audit_entry(
            "Fallback Analysis",
            f"LLM failed, using rules: {state['risk_assessment']['severity']}",
            details={'error': str(e)}
        )]
    
    return state


async def policy_decision(state: IncidentState) -> IncidentState:
    """
    Node 2: Make policy decision based on rules + LLM insights.
    """
    logger.info(f"Making policy decision for incident {state['incident_id']}")
    
    risk_score = state['enhanced_report'].get('risk_score', 0)
    confidence = state['vlm_summary'].get('confidence', 0)
    severity = state['risk_assessment'].get('severity', 'low')
    urgency = state['risk_assessment'].get('urgency', 'standard')
    
    # Hybrid decision: rules + LLM
    if risk_score >= 8 and confidence >= 0.85 and severity == 'critical':
        decision = 'auto_dispatch'
        reason = f"Auto-dispatch: risk {risk_score}, confidence {confidence:.2f}, {severity} severity"
    elif risk_score >= 7 and urgency == 'immediate':
        decision = 'auto_dispatch'
        reason = f"Auto-dispatch: risk {risk_score}, {urgency} urgency"
    elif risk_score >= 6 or severity in ['critical', 'high']:
        decision = 'queue_review'
        reason = f"Queue for review: risk {risk_score}, {severity} severity"
    else:
        decision = 'log_only'
        reason = f"Log only: risk {risk_score}, {severity} severity"
    
    state['policy_decision'] = decision
    state['audit_trail'].append(create_audit_entry(
        "Policy Decision",
        reason,
        details={'decision': decision, 'risk_score': risk_score, 'severity': severity}
    ))
    
    logger.info(f"Policy decision: {decision} - {reason}")
    
    return state


async def build_action_plan(state: IncidentState) -> IncidentState:
    """Build action plan based on policy decision - SMS ONLY."""
    incident_id = state["incident_id"]
    decision = state["policy_decision"]
    
    # Get severity from risk_assessment and risk_score from enhanced_report
    risk_assessment = state.get("risk_assessment", {})
    severity = risk_assessment.get("severity", "medium")
    risk_score = state.get('enhanced_report', {}).get('risk_score', 5)
    
    logger.info(f"Building action plan for incident {incident_id}")
    
    actions = []
    
    # Generate detailed SMS report content
    vlm_summary = state.get("vlm_summary", {})
    incident_type = vlm_summary.get("incident_type", "Unknown Incident")
    description = vlm_summary.get("description", "No description available")
    location = state.get("location", "Unknown location") # Location is directly from state
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    def generate_sms_report(recipient_type: str) -> str:
        """Generate customized SMS report for recipient type."""
        if recipient_type == "police":
            return f"""🚨 POLICE ALERT

Type: {incident_type}
Severity: {severity.upper()} (Risk: {risk_score}/10)
Location: {location}
Time: {timestamp}

Details: {description}

Immediate response required.
- BI3 Traffic Safety System"""
        
        elif recipient_type == "ambulance":
            return f"""🚑 MEDICAL EMERGENCY

Incident: {incident_type}
Severity: {severity.upper()}
Location: {location}
Time: {timestamp}

{description}

Dispatch ambulance immediately.
- BI3 Traffic Safety System"""
        
        elif recipient_type == "traffic":
            return f"""⚠️ TRAFFIC INCIDENT

Type: {incident_type}
Risk Level: {risk_score}/10
Location: {location}
Time: {timestamp}

{description}

Traffic control needed.
- BI3 Traffic Safety System"""
        
        else:
            return f"""🚨 INCIDENT ALERT

{incident_type}
Severity: {severity.upper()}
Location: {location}

{description}

- BI3 System"""
    
    # Build SMS-only action plan based on severity
    if decision == "auto_dispatch":
        # High severity - send to police
        if risk_score >= 7:
            actions.append(ActionPlanItem(
                action_id=f"sms-police-{incident_id[:8]}",
                type=ActionType.SMS,
                target_role="police",
                number="+919535879330",  # Police number
                text=generate_sms_report("police"),
                retry_policy=RetryPolicy(attempts=3, backoff_seconds=5)
            ))
        
        # If injuries suspected - send to ambulance
        if "injury" in description.lower() or "accident" in incident_type.lower():
            actions.append(ActionPlanItem(
                action_id=f"sms-ambulance-{incident_id[:8]}",
                type=ActionType.SMS,
                target_role="ambulance",
                number="+916369445764",  # Ambulance number
                text=generate_sms_report("ambulance"),
                retry_policy=RetryPolicy(attempts=3, backoff_seconds=5)
            ))
        
        # Always send to traffic control
        actions.append(ActionPlanItem(
            action_id=f"sms-traffic-{incident_id[:8]}",
            type=ActionType.SMS,
            target_role="traffic_control",
            number="+919535879330",  # Traffic control (using police number for now)
            text=generate_sms_report("traffic"),
            retry_policy=RetryPolicy(attempts=2, backoff_seconds=10)
        ))
    
    elif decision == "manual_review":
        # Medium severity - notify traffic control only
        actions.append(ActionPlanItem(
            action_id=f"sms-notify-{incident_id[:8]}",
            type=ActionType.SMS,
            target_role="traffic_control",
            number="+919535879330",
            text=generate_sms_report("traffic"),
            retry_policy=RetryPolicy(attempts=2, backoff_seconds=10)
        ))
    
    logger.info(f"Created action plan with {len(actions)} SMS actions")
    
    # Convert ActionPlanItem objects to dicts for state storage
    action_dicts = [action.dict() for action in actions]
    
    return {
        **state,
        "action_plan": action_dicts,
        "status": "action_plan_created"
    }


async def execute_actions(state: IncidentState, device_manager=None) -> IncidentState:
    """
    Node 4: Execute all actions in the plan.
    """
    logger.info(f"Executing actions for incident {state['incident_id']}")
    
    from .actions import ActionExecutor
    from .config import DEFAULT_CONFIG
    
    executor = ActionExecutor(config=DEFAULT_CONFIG, device_manager=device_manager)
    
    # Convert dict actions to ActionPlanItem objects
    action_items = [ActionPlanItem(**action) for action in state['action_plan']]
    
    # Execute actions
    updated_plan, audit = await executor.execute_action_plan(
        action_items,
        agent_id='langgraph-orchestrator'
    )
    
    # Convert back to dicts
    state['action_plan'] = [action.dict() for action in updated_plan]
    state['audit_trail'].extend([entry.dict() for entry in audit])
    
    # Track results
    state['executed_actions'] = [
        a for a in state['action_plan'] 
        if a['status'] in ['acknowledged', 'sent']
    ]
    state['failed_actions'] = [
        a for a in state['action_plan'] 
        if a['status'] == 'failed'
    ]
    
    logger.info(f"Executed {len(state['executed_actions'])} actions, {len(state['failed_actions'])} failed")
    
    return state


async def monitor_callbacks(state: IncidentState) -> IncidentState:
    """
    Node 5: Monitor action results and determine if retry needed.
    """
    logger.info(f"Monitoring callbacks for incident {state['incident_id']}")
    
    # Check if any actions need retry
    needs_retry = any(
        action['status'] == 'failed' and action['attempts'] < action['retry_policy']['attempts']
        for action in state['action_plan']
    )
    
    state['needs_retry'] = needs_retry
    
    if needs_retry:
        logger.info("Some actions need retry")
    else:
        logger.info("All actions completed or max retries reached")
    
    return state


async def queue_for_review(state: IncidentState) -> IncidentState:
    """
    Node 6: Queue incident for operator review.
    """
    logger.info(f"Queuing incident {state['incident_id']} for operator review")
    
    state['final_status'] = 'queued_for_review'
    state['operator_message'] = (
        f"Incident {state['incident_id']} requires review. "
        f"Type: {state['vlm_summary'].get('incident_type')}, "
        f"Risk: {state['enhanced_report'].get('risk_score')}/10, "
        f"Severity: {state['risk_assessment'].get('severity')}"
    )
    
    state['audit_trail'].append(create_audit_entry(
        "Queued for Review",
        state['operator_message']
    ))
    
    return state


async def finalize_incident(state: IncidentState) -> IncidentState:
    """
    Node 7: Finalize incident and determine final status.
    """
    logger.info(f"Finalizing incident {state['incident_id']}")
    
    if state['failed_actions']:
        state['final_status'] = 'escalated'
        reason = f"{len(state['failed_actions'])} actions failed"
    elif state['executed_actions']:
        state['final_status'] = 'dispatched'
        reason = f"{len(state['executed_actions'])} actions executed successfully"
    else:
        state['final_status'] = 'logged_only'
        reason = "No actions executed"
    
    state['audit_trail'].append(create_audit_entry(
        "Incident Finalized",
        reason,
        details={'final_status': state['final_status']}
    ))
    
    logger.info(f"Incident finalized with status: {state['final_status']}")
    
    return state


# ============ LangGraph Orchestrator ============

class LangGraphOrchestrator:
    """
    LangGraph-based incident orchestrator.
    
    Provides stateful, multi-step incident processing with LLM-enhanced
    decision making and built-in checkpointing.
    """
    
    def __init__(self, config: AgentConfig = None, device_manager=None):
        self.config = config or DEFAULT_CONFIG
        self.device_manager = device_manager
        self.app = self._build_graph()
        logger.info("LangGraph orchestrator initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create wrapper for execute node with device_manager
        async def execute_with_device_manager(state: IncidentState) -> IncidentState:
            return await execute_actions(state, self.device_manager)
        
        # Create graph
        workflow = StateGraph(IncidentState)
        
        # Add nodes
        workflow.add_node("analyze", analyze_incident)
        workflow.add_node("policy", policy_decision)
        workflow.add_node("build_plan", build_action_plan)
        workflow.add_node("execute", execute_with_device_manager)
        workflow.add_node("monitor", monitor_callbacks)
        workflow.add_node("queue", queue_for_review)
        workflow.add_node("finalize", finalize_incident)
        
        # Define edges
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "policy")
        
        # Conditional routing from policy
        workflow.add_conditional_edges(
            "policy",
            lambda state: state['policy_decision'],
            {
                "auto_dispatch": "build_plan",
                "queue_review": "queue",
                "log_only": "finalize"
            }
        )
        
        workflow.add_edge("build_plan", "execute")
        workflow.add_edge("execute", "monitor")
        
        # Conditional retry logic
        workflow.add_conditional_edges(
            "monitor",
            lambda state: "retry" if state.get('needs_retry', False) else "complete",
            {
                "retry": "execute",
                "complete": "finalize"
            }
        )
        
        workflow.add_edge("queue", END)
        workflow.add_edge("finalize", END)
        
        # Add checkpointing for persistence
        memory = MemorySaver()
        app = workflow.compile(checkpointer=memory)
        
        logger.info("LangGraph workflow compiled successfully")
        return app
    
    async def process_incident_async(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incident through LangGraph workflow.
        
        Args:
            incident_data: Raw incident JSON matching IncidentInput schema
            
        Returns:
            Complete output with action_result and api_spec
        """
        logger.info(f"Processing incident {incident_data.get('incident_id')} via LangGraph")
        
        # Initialize state
        initial_state: IncidentState = {
            'incident_id': incident_data['incident_id'],
            'vlm_summary': incident_data['vlm_summary'],
            'enhanced_report': incident_data['enhanced_report'],
            'location': incident_data.get('location'),
            'history': incident_data.get('history', []),
            'messages': [],
            'policy_decision': '',
            'risk_assessment': {},
            'llm_reasoning': '',
            'action_plan': [],
            'executed_actions': [],
            'failed_actions': [],
            'needs_retry': False,
            'final_status': '',
            'audit_trail': [],
            'operator_message': None,
        }
        
        # Run graph
        config = {"configurable": {"thread_id": incident_data['incident_id']}}
        
        try:
            result = await self.app.ainvoke(initial_state, config)
            
            # Format response
            return {
                'action_result': {
                    'incident_id': result['incident_id'],
                    'action_plan': result['action_plan'],
                    'final_status': result['final_status'],
                    'audit': result['audit_trail'],
                    'operator_message': result.get('operator_message'),
                    'device_status': None
                },
                'api_spec': get_openapi_spec()
            }
        except Exception as e:
            logger.exception(f"LangGraph processing failed for incident {incident_data['incident_id']}")
            raise
    
    def process_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for process_incident_async."""
        return asyncio.run(self.process_incident_async(incident_data))
    
    def get_incident(self, incident_id: str) -> Dict[str, Any] | None:
        """Get incident state from checkpoint."""
        config = {"configurable": {"thread_id": incident_id}}
        
        try:
            state = self.app.get_state(config)
            if state and state.values:
                return {
                    'incident_id': state.values.get('incident_id'),
                    'status': state.values.get('final_status', 'processing'),
                    'action_plan': state.values.get('action_plan', []),
                    'audit': state.values.get('audit_trail', []),
                    'vlm_summary': state.values.get('vlm_summary'),
                    'enhanced_report': state.values.get('enhanced_report'),
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get incident {incident_id}: {e}")
            return None
    
    def register_device(self, device: DeviceInfo) -> None:
        """Register a mobile device (delegated to action executor)."""
        # This is handled by the action executor
        pass
    
    def handle_mobile_callback(self, callback: MobileCallback) -> bool:
        """Handle callback from mobile device (delegated to action executor)."""
        # This is handled by the action executor
        return True
