"""
LLM Integration for Incident Orchestrator Agent.
Uses Ollama with gemma3:1b for intelligent decision support.
"""

import asyncio
import logging
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Add parent directory to path to import from main project
sys.path.insert(0, '/home/lebi/hack')

from ollama_client import OllamaClient, OllamaResponse

logger = logging.getLogger(__name__)


# System prompt for agent decision support
AGENT_DECISION_SYSTEM_PROMPT = """You are an AI assistant supporting the BI3 Smart Traffic Safety Incident Orchestrator.

Your role is to:
1. Analyze incident reports and provide recommendations
2. Help prioritize emergency responses
3. Suggest appropriate escalation paths
4. Generate concise emergency messages

IMPORTANT RULES:
- Be conservative and safety-first
- Never hallucinate or make up information
- If uncertain, recommend human operator review
- Keep all messages concise and actionable
- Do not include sensitive PII

Respond in JSON format when asked for structured output."""


@dataclass
class LLMDecision:
    """Container for LLM decision output."""
    success: bool
    recommendation: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "error": self.error
        }


class LLMDecisionHelper:
    """
    LLM-powered decision support for the orchestrator.
    
    Uses Ollama with gemma3:1b for:
    - Emergency message generation
    - Incident prioritization
    - Ambiguity resolution suggestions
    """
    
    def __init__(self, ollama_client: OllamaClient = None):
        """
        Initialize LLM helper.
        
        Args:
            ollama_client: Existing Ollama client (creates new if not provided)
        """
        self.client = ollama_client or OllamaClient()
        self._available: Optional[bool] = None
    
    async def check_availability(self) -> bool:
        """Check if Ollama is available."""
        if self._available is None:
            self._available = await self.client.check_health()
        return self._available
    
    async def generate_emergency_message(
        self,
        incident_type: str,
        risk_score: int,
        location: Optional[Dict[str, float]] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Generate a concise emergency message using LLM.
        
        Falls back to template if LLM unavailable.
        """
        if not await self.check_availability():
            return self._fallback_emergency_message(
                incident_type, risk_score, location
            )
        
        location_str = "unknown location"
        if location:
            location_str = f"coordinates {location['lat']:.4f}, {location['lon']:.4f}"
        
        prompt = f"""Generate a concise emergency alert message (max 30 words) for:
- Incident Type: {incident_type}
- Risk Level: {risk_score}/10
- Location: {location_str}
{f'- Context: {additional_context}' if additional_context else ''}

The message should be suitable for emergency services. Be direct and actionable.
Output ONLY the message text, nothing else."""
        
        response = await self.client.generate(
            prompt=prompt,
            system_prompt=AGENT_DECISION_SYSTEM_PROMPT,
            temperature=0.2,  # Low temperature for consistent output
            max_tokens=100
        )
        
        if response.success and response.content:
            return response.content.strip()
        
        return self._fallback_emergency_message(incident_type, risk_score, location)
    
    def _fallback_emergency_message(
        self,
        incident_type: str,
        risk_score: int,
        location: Optional[Dict[str, float]] = None
    ) -> str:
        """Fallback template-based message."""
        location_str = "unknown location"
        if location:
            location_str = f"({location['lat']:.4f}, {location['lon']:.4f})"
        
        severity = "critical" if risk_score >= 8 else "high" if risk_score >= 6 else "moderate"
        
        return (
            f"Emergency alert: {incident_type} detected at {location_str}. "
            f"Severity: {severity}. Immediate response required."
        )
    
    async def analyze_ambiguity(
        self,
        vlm_description: str,
        confidence: float
    ) -> LLMDecision:
        """
        Analyze if an incident report is ambiguous.
        
        Returns recommendation for whether to auto-action or escalate.
        """
        if not await self.check_availability():
            return LLMDecision(
                success=False,
                error="LLM unavailable",
                recommendation="escalate",
                reasoning="LLM unavailable, defaulting to human review"
            )
        
        prompt = f"""Analyze this traffic incident report for ambiguity:

VLM Description: {vlm_description}
Confidence Score: {confidence:.2f}

Determine if this incident is clear enough for automated emergency response.

Respond in JSON format:
{{
    "is_ambiguous": true/false,
    "recommendation": "auto_action" or "escalate",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""
        
        response = await self.client.generate(
            prompt=prompt,
            system_prompt=AGENT_DECISION_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=200
        )
        
        if response.success and response.content:
            try:
                import json
                # Try to parse JSON from response
                content = response.content.strip()
                # Handle potential markdown code blocks
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                
                result = json.loads(content)
                return LLMDecision(
                    success=True,
                    recommendation=result.get("recommendation", "escalate"),
                    confidence=result.get("confidence", 0.5),
                    reasoning=result.get("reasoning", "")
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse LLM response: {e}")
        
        return LLMDecision(
            success=False,
            error="Failed to analyze",
            recommendation="escalate",
            reasoning="Analysis failed, defaulting to human review"
        )
    
    async def summarize_for_operator(
        self,
        incident_data: Dict[str, Any]
    ) -> str:
        """Generate a concise summary for operator dashboard."""
        if not await self.check_availability():
            return self._fallback_operator_summary(incident_data)
        
        prompt = f"""Summarize this traffic incident for an emergency operator (max 50 words):

Incident Type: {incident_data.get('incident_type', 'Unknown')}
Risk Score: {incident_data.get('risk_score', 'Unknown')}/10
VLM Confidence: {incident_data.get('confidence', 'Unknown')}
Description: {incident_data.get('description', 'No description')}

Be concise and actionable. Highlight key facts for decision-making."""

        response = await self.client.generate(
            prompt=prompt,
            system_prompt=AGENT_DECISION_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=150
        )
        
        if response.success and response.content:
            return response.content.strip()
        
        return self._fallback_operator_summary(incident_data)
    
    def _fallback_operator_summary(self, incident_data: Dict[str, Any]) -> str:
        """Fallback template-based summary."""
        return (
            f"Incident: {incident_data.get('incident_type', 'Unknown')} | "
            f"Risk: {incident_data.get('risk_score', '?')}/10 | "
            f"Confidence: {incident_data.get('confidence', '?'):.0%}"
        )
    
    async def close(self):
        """Close the Ollama client."""
        await self.client.close()


async def test_llm_helper():
    """Test LLM helper functionality."""
    helper = LLMDecisionHelper()
    
    print("Testing LLM Decision Helper")
    print("=" * 40)
    
    # Check availability
    available = await helper.check_availability()
    print(f"Ollama available: {available}")
    
    if available:
        # Test emergency message
        message = await helper.generate_emergency_message(
            incident_type="vehicle collision",
            risk_score=8,
            location={"lat": 12.9716, "lon": 77.5946}
        )
        print(f"\nEmergency message:\n{message}")
        
        # Test ambiguity analysis
        decision = await helper.analyze_ambiguity(
            vlm_description="Possible collision between two vehicles at intersection",
            confidence=0.75
        )
        print(f"\nAmbiguity analysis:\n{decision.to_dict()}")
    
    await helper.close()


if __name__ == "__main__":
    asyncio.run(test_llm_helper())
