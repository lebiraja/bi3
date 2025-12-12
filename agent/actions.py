"""
Action Execution for Incident Orchestrator Agent.
Handles call, SMS, and notification execution with retry logic.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from .config import AgentConfig, DEFAULT_CONFIG
from .models import (
    ActionPlanItem,
    ActionType,
    ActionStatus,
    TargetRole,
    DeviceInfo,
    MobileCallback,
    AuditEntry,
    VoIPCallbackPayload,
    FCMPushPayload,
)

logger = logging.getLogger(__name__)


class CallState(str, Enum):
    """GSM call states from mobile device."""
    IDLE = "CALL_STATE_IDLE"
    RINGING = "CALL_STATE_RINGING"
    OFFHOOK = "CALL_STATE_OFFHOOK"  # Answered


class ActionExecutor:
    """
    Executes actions from the action plan.
    
    Supports:
    - GSM calls via mobile device
    - VoIP calls as fallback
    - SMS delivery
    - Push notifications
    """
    
    def __init__(self, config: AgentConfig = None, device_manager=None):
        self.config = config or DEFAULT_CONFIG
        self.registered_devices: Dict[str, DeviceInfo] = {}
        self.pending_callbacks: Dict[str, asyncio.Future] = {}
        self.device_manager = device_manager  # WebSocket manager from server
    
    def _create_audit(
        self,
        agent_id: str,
        step: str,
        outcome: str,
        action_id: str = None,
        details: dict = None
    ) -> AuditEntry:
        """Create an audit entry."""
        return AuditEntry(
            ts=datetime.utcnow().isoformat() + 'Z',
            actor=agent_id,
            step=step,
            outcome=outcome,
            action_id=action_id,
            details=details
        )
    
    async def execute_action_plan(
        self,
        action_plan: List[ActionPlanItem],
        agent_id: str
    ) -> tuple[List[ActionPlanItem], List[AuditEntry]]:
        """
        Execute all actions in the plan with proper sequencing and retry logic.
        
        Returns:
            Updated action plan with statuses and audit entries
        """
        audit = []
        updated_plan = []
        
        for action in action_plan:
            audit.append(self._create_audit(
                agent_id,
                f"Starting action execution",
                f"Action {action.action_id} type={action.type}",
                action.action_id
            ))
            
            # Execute SMS actions only
            if action.type == ActionType.SMS:
                executed_action, action_audit = await self._execute_sms(action, agent_id)
            else:
                logger.warning(f"Unsupported action type: {action.type} - skipping")
                action.status = ActionStatus.FAILED
                action.last_result = {"error": f"Unsupported action type: {action.type}"}
                executed_action = action
                action_audit = [self._create_audit(
                    agent_id, f"Unsupported action type: {action.type}", "Skipped", action.action_id
                )]
            
            updated_plan.append(executed_action)
            audit.extend(action_audit)
        
        return updated_plan, audit
    
    async def _execute_call(
        self,
        action: ActionPlanItem,
        agent_id: str
    ) -> tuple[ActionPlanItem, List[AuditEntry]]:
        """Execute a call action with retry logic."""
        audit = []
        max_attempts = action.retry_policy.attempts
        backoff = action.retry_policy.backoff_seconds
        
        # Check for online device with call capability
        device = self._get_available_device(calls_required=True)
        
        for attempt in range(1, max_attempts + 1):
            action.attempts = attempt
            
            audit.append(self._create_audit(
                agent_id,
                f"Call attempt {attempt}/{max_attempts}",
                f"Calling {action.number} for {action.target_role}",
                action.action_id,
                {"device_id": device.device_id if device else "voip_fallback"}
            ))
            
            if device and device.is_online:
                # Execute via mobile device
                result = await self._execute_gsm_call(action, device)
            else:
                # Fallback to VoIP
                audit.append(self._create_audit(
                    agent_id,
                    "Device unavailable",
                    "Falling back to VoIP provider",
                    action.action_id
                ))
                result = await self._execute_voip_call(action)
            
            action.last_result = result
            
            if result.get("answered"):
                action.status = ActionStatus.ACKNOWLEDGED
                audit.append(self._create_audit(
                    agent_id,
                    f"Call acknowledged",
                    f"Call answered after {attempt} attempt(s)",
                    action.action_id,
                    result
                ))
                break
            elif attempt < max_attempts:
                audit.append(self._create_audit(
                    agent_id,
                    f"Call attempt failed",
                    f"Retrying in {backoff}s",
                    action.action_id,
                    result
                ))
                await asyncio.sleep(backoff)
            else:
                action.status = ActionStatus.ESCALATED
                audit.append(self._create_audit(
                    agent_id,
                    f"Call failed after max attempts",
                    "Escalating to alternate contacts",
                    action.action_id,
                    result
                ))
        
        return action, audit
    
    async def _execute_gsm_call(
        self,
        action: ActionPlanItem,
        device: DeviceInfo
    ) -> Dict[str, Any]:
        """
        Execute GSM call via mobile device.
        
        Sends command to device and waits for callback.
        """
        timeout = self.config.retry_policy.call_timeout_seconds
        
        # Create callback future
        callback_future = asyncio.Future()
        self.pending_callbacks[action.action_id] = callback_future
        
        # Send call command to device
        command_payload = {
            "action_id": action.action_id,
            "command": "INITIATE_CALL",
            "number": action.number,
            "timeout_seconds": timeout,
            "spoken_message": action.text or f"Calling {action.target_role}"
        }
        
        # Send via WebSocket if device_manager has send_command method
        if self.device_manager and hasattr(self.device_manager, 'send_command'):
            success = await self.device_manager.send_command(device.device_id, command_payload)
            if not success:
                logger.error(f"Failed to send call command to device {device.device_id}")
                return {
                    "answered": False,
                    "error": "Failed to send command to device",
                    "device_id": device.device_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "method": "gsm"
                }
        else:
            # Simulated for testing
            logger.info(f"Simulated: Sending call command to {device.device_id}")
        
        # Wait for callback with timeout
        try:
            result = await asyncio.wait_for(callback_future, timeout=timeout)
            logger.info(f"Call callback received: {result.status}")
            
            # Check if call was answered
            answered = result.status == ActionStatus.ACKNOWLEDGED
            
            return {
                "answered": answered,
                "call_state": result.call_state,
                "duration": result.duration_seconds,
                "device_id": device.device_id,
                "timestamp": result.timestamp,
                "method": "gsm"
            }
        except asyncio.TimeoutError:
            logger.warning(f"Call timeout after {timeout}s for action {action.action_id}")
            return {
                "answered": False,
                "error": f"Timeout after {timeout}s",
                "device_id": device.device_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "method": "gsm"
            }
        finally:
            # Clean up pending callback
            self.pending_callbacks.pop(action.action_id, None)
    
    async def _execute_voip_call(self, action: ActionPlanItem) -> Dict[str, Any]:
        """Execute call via VoIP provider with TTS."""
        # Simulated VoIP call - in production would call provider API
        voip_config = self.config.voip
        
        logger.info(f"Initiating VoIP call to {action.number} via {voip_config.provider_url}")
        
        # Simulate VoIP API call
        # In production: POST to voip_config.provider_url with TTS message
        
        return {
            "answered": False,  # Would be updated via webhook callback
            "call_id": f"voip-{action.action_id[:8]}",
            "provider": "simulated_voip",
            "tts_voice": voip_config.tts_voice,
            "message": action.text,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "method": "voip",
            "status": "initiated"
        }
    
    async def _execute_sms(
        self,
        action: ActionPlanItem,
        agent_id: str
    ) -> tuple[ActionPlanItem, List[AuditEntry]]:
        """Execute SMS action."""
        audit = []
        
        # SMS should always be sent regardless of call success
        audit.append(self._create_audit(
            agent_id,
            "Sending SMS",
            f"To {action.number}",
            action.action_id
        ))
        
        # Simulated SMS sending
        result = await self._send_sms(action.number, action.text)
        
        action.last_result = result
        action.attempts = 1
        
        if result.get("sent"):
            action.status = ActionStatus.SENT
            audit.append(self._create_audit(
                agent_id,
                "SMS sent successfully",
                f"Message ID: {result.get('message_id')}",
                action.action_id,
                result
            ))
        else:
            action.status = ActionStatus.FAILED
            audit.append(self._create_audit(
                agent_id,
                "SMS failed",
                result.get("error", "Unknown error"),
                action.action_id,
                result
            ))
        
        return action, audit
    
    async def _send_sms(self, number: str, text: str) -> Dict[str, Any]:
        """Send SMS message via mobile device or simulated."""
        import uuid
        
        # Check for available device with SMS capability
        device = self._get_available_device(sms_required=True)
        
        if device and self.device_manager:
            # Send SMS via mobile device
            logger.info(f"Sending SMS via device {device.device_id} to {number}")
            
            # Create SMS command payload
            sms_payload = {
                "type": "sms_action",
                "number": number,
                "text": text,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            # Send via WebSocket if device_manager has broadcast method
            if hasattr(self.device_manager, 'broadcast'):
                try:
                    await self.device_manager.broadcast(device.device_id, sms_payload)
                    logger.info(f"✅ SMS command sent to device {device.device_id}")
                    
                    return {
                        "sent": True,
                        "message_id": str(uuid.uuid4())[:8],
                        "number": number,
                        "text_length": len(text),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "provider": f"mobile_device_{device.device_id}",
                        "device_id": device.device_id
                    }
                except Exception as e:
                    logger.error(f"Failed to send SMS via device: {e}")
                    # Fall through to simulation
        
        # Fallback to simulated SMS
        logger.warning("No device available, using simulated SMS")
        return {
            "sent": True,
            "message_id": str(uuid.uuid4())[:8],
            "number": number,
            "text_length": len(text),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider": "simulated_sms"
        }
    
    async def _execute_notify(
        self,
        action: ActionPlanItem,
        agent_id: str
    ) -> tuple[ActionPlanItem, List[AuditEntry]]:
        """Execute push notification action."""
        audit = []
        
        audit.append(self._create_audit(
            agent_id,
            "Sending notification",
            f"To operator dashboard",
            action.action_id
        ))
        
        # Send notification
        result = await self._send_notification(action)
        
        action.last_result = result
        action.attempts = 1
        action.status = ActionStatus.SENT if result.get("sent") else ActionStatus.FAILED
        
        audit.append(self._create_audit(
            agent_id,
            "Notification sent" if result.get("sent") else "Notification failed",
            result.get("message_id", result.get("error", "Unknown")),
            action.action_id,
            result
        ))
        
        return action, audit
    
    async def _send_notification(self, action: ActionPlanItem) -> Dict[str, Any]:
        """Send push notification."""
        import uuid
        
        # Simulated - in production would use FCM
        return {
            "sent": True,
            "message_id": str(uuid.uuid4())[:8],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider": "fcm_simulated"
        }
    
    def _get_available_device(
        self,
        calls_required: bool = False,
        sms_required: bool = False
    ) -> Optional[DeviceInfo]:
        """Get an available device with required capabilities."""
        # Use device_manager if available
        if self.device_manager:
            # Check if it's the DeviceManager class (from actions.py) with .devices attribute
            if hasattr(self.device_manager, 'devices'):
                for device_id, device in self.device_manager.devices.items():
                    if not device.is_online:
                        continue
                    
                    if calls_required and not device.capabilities.calls:
                        continue
                    
                    if sms_required and not device.capabilities.sms:
                        continue
                    
                    return device
            # Otherwise it's DeviceConnectionManager (from server.py) with .device_connections
            # In this case, we need to check registered_devices or create a dummy device
            elif hasattr(self.device_manager, 'device_connections'):
                # Check if any device is connected
                if self.device_manager.device_connections:
                    # Get first connected device ID
                    device_id = next(iter(self.device_manager.device_connections.keys()))
                    # Create a DeviceInfo for this connected device
                    from .models import DeviceCapabilities
                    return DeviceInfo(
                        device_id=device_id,
                        push_token=f"token-{device_id}",
                        capabilities=DeviceCapabilities(calls=True, sms=True, push=True),
                        is_online=True
                    )
        
        # Fallback to registered_devices (legacy)
        for device in self.registered_devices.values():
            if not device.is_online:
                continue
            
            if calls_required and not device.capabilities.calls:
                continue
            
            if sms_required and not device.capabilities.sms:
                continue
            
            return device
        
        return None
    
    def register_device(self, device: DeviceInfo) -> None:
        """Register a mobile device."""
        self.registered_devices[device.device_id] = device
        logger.info(f"Registered device: {device.device_id}")
    
class DeviceManager:
    """Manages registered mobile devices and their phone numbers."""
    
    def __init__(self):
        self.devices: Dict[str, DeviceInfo] = {}  # device_id -> DeviceInfo
        self.phone_to_device: Dict[str, str] = {}  # phone_number -> device_id
        self.websocket_connections: Dict[str, Any] = {}  # device_id -> websocket
    
    def register_device(self, device: DeviceInfo):
        """Register a mobile device with optional phone number."""
        self.devices[device.device_id] = device
        
        # Map phone number to device ID if provided
        if device.phone_number:
            self.phone_to_device[device.phone_number] = device.device_id
            logger.info(
                f"Registered device {device.device_id} with phone {device.phone_number}"
            )
        else:
            logger.warning(
                f"Device {device.device_id} registered without phone number"
            )
    
    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """Get device by ID."""
        return self.devices.get(device_id)
    
    def get_device_by_phone(self, phone_number: str) -> Optional[DeviceInfo]:
        """Get device by phone number."""
        device_id = self.phone_to_device.get(phone_number)
        if device_id:
            return self.devices.get(device_id)
        return None
    
    def verify_phone_number(self, device_id: str, phone_number: str) -> bool:
        """Verify that phone number matches registered device."""
        device = self.devices.get(device_id)
        if not device:
            logger.warning(f"Device {device_id} not found for phone verification")
            return False
        
        if not device.phone_number:
            # Device has no phone number registered, skip verification
            return True
        
        matches = device.phone_number == phone_number
        if not matches:
            logger.warning(
                f"Phone number mismatch for device {device_id}: "
                f"expected {device.phone_number}, got {phone_number}"
            )
        return matches
    
    def handle_mobile_callback(self, callback: MobileCallback) -> bool:
        """
        Handle callback from mobile device after action execution.
        
        Returns:
            True if callback was processed, False if no pending action
        """
        action_id = callback.action_id
        
        if action_id in self.pending_callbacks:
            future = self.pending_callbacks[action_id]
            if not future.done():
                future.set_result(callback)
            return True
        
        logger.warning(f"Received callback for unknown action: {action_id}")
        return False
    
    def handle_voip_callback(self, callback: VoIPCallbackPayload) -> Dict[str, Any]:
        """Handle callback from VoIP provider."""
        action_id = callback.action_id
        
        logger.info(f"VoIP callback for action {action_id}: status={callback.status}")
        
        # Map VoIP status to action status
        status_map = {
            "answered": ActionStatus.ACKNOWLEDGED,
            "completed": ActionStatus.ACKNOWLEDGED,
            "failed": ActionStatus.FAILED,
            "busy": ActionStatus.FAILED,
            "no_answer": ActionStatus.FAILED,
        }
        
        action_status = status_map.get(callback.status, ActionStatus.PENDING)
        
        return {
            "action_id": action_id,
            "status": action_status,
            "voip_status": callback.status,
            "duration": callback.duration_seconds,
            "timestamp": callback.timestamp
        }
    
    def _create_audit(
        self,
        actor: str,
        step: str,
        outcome: str,
        action_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Create an audit entry."""
        return AuditEntry(
            actor=actor,
            step=step,
            outcome=outcome,
            action_id=action_id,
            details=details
        )
    
    def create_fcm_payload(
        self,
        device_token: str,
        action_plan: List[ActionPlanItem],
        incident_id: str
    ) -> FCMPushPayload:
        """Create FCM push payload for delivering action plan to device."""
        return FCMPushPayload(
            to=device_token,
            priority=self.config.fcm.priority,
            ttl=f"{self.config.fcm.ttl_seconds}s",
            data={
                "type": "action_plan",
                "incident_id": incident_id,
                "actions": [action.dict() for action in action_plan],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            notification={
                "title": "Emergency Action Required",
                "body": f"Incident {incident_id[:8]} requires action"
            }
        )
