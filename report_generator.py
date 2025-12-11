"""
Report Generator Module.
Orchestrates the multi-model pipeline for classical and enhanced report generation.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ollama_client import OllamaClient, OllamaResponse
from prompts import ENHANCED_REPORT_SYSTEM_PROMPT, get_enhanced_report_prompt
from prompts.enhanced_report_prompt import format_classical_report

logger = logging.getLogger(__name__)


@dataclass
class EnhancedReport:
    """Enhanced documentation-style report."""
    report_type: str = "enhanced"
    video_id: str = ""
    generated_at: str = ""
    content: str = ""
    
    # Structured sections (parsed from content if available)
    executive_summary: str = ""
    narrative_summary: str = ""
    incident_breakdown: str = ""
    evidence_mapping: str = ""
    classification: str = ""
    legal_notes: str = ""
    
    # Metadata
    vlm_risk_score: float = 0.0
    observation_count: int = 0
    generation_time_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "report_type": self.report_type,
            "video_id": self.video_id,
            "generated_at": self.generated_at,
            "content": self.content,
            "sections": {
                "executive_summary": self.executive_summary,
                "narrative_summary": self.narrative_summary,
                "incident_breakdown": self.incident_breakdown,
                "evidence_mapping": self.evidence_mapping,
                "classification": self.classification,
                "legal_notes": self.legal_notes
            },
            "metadata": {
                "vlm_risk_score": self.vlm_risk_score,
                "observation_count": self.observation_count,
                "generation_time_ms": self.generation_time_ms
            },
            "success": self.success,
            "error": self.error
        }


@dataclass 
class ClassicalReport:
    """Classical report (existing format)."""
    report_type: str = "classical"
    video_id: str = ""
    total_seconds: int = 0
    analyzed_seconds: int = 0
    avg_risk_score: float = 0.0
    max_risk_score: int = 0
    critical_observations: List[Dict[str, Any]] = field(default_factory=list)
    analysis_timestamp: str = ""
    
    def to_dict(self) -> dict:
        return {
            "report_type": self.report_type,
            "video_id": self.video_id,
            "total_seconds": self.total_seconds,
            "analyzed_seconds": self.analyzed_seconds,
            "avg_risk_score": self.avg_risk_score,
            "max_risk_score": self.max_risk_score,
            "critical_observations": self.critical_observations,
            "analysis_timestamp": self.analysis_timestamp
        }


class ReportGenerator:
    """
    Orchestrates report generation pipeline.
    
    Generates both classical reports (from VLM data) and enhanced
    documentation-style reports (via Gemma3-1B).
    """
    
    def __init__(
        self,
        ollama_client: OllamaClient = None,
        mongodb_handler = None
    ):
        """
        Initialize report generator.
        
        Args:
            ollama_client: Ollama client instance (creates new if not provided)
            mongodb_handler: MongoDB handler for historical context
        """
        self.ollama_client = ollama_client or OllamaClient()
        self.mongodb_handler = mongodb_handler
    
    async def check_ollama_availability(self) -> bool:
        """Check if Ollama is available for enhanced report generation."""
        return await self.ollama_client.check_health()
    
    def generate_classical_report(
        self,
        vlm_analysis: Dict[str, Any]
    ) -> ClassicalReport:
        """
        Generate classical report from VLM analysis data.
        
        This maintains the existing report format for backward compatibility.
        
        Args:
            vlm_analysis: VLM analysis summary dictionary
        
        Returns:
            ClassicalReport object
        """
        return ClassicalReport(
            video_id=vlm_analysis.get("video_id", ""),
            total_seconds=vlm_analysis.get("total_seconds", 0),
            analyzed_seconds=vlm_analysis.get("analyzed_seconds", 0),
            avg_risk_score=vlm_analysis.get("avg_risk_score", 0.0),
            max_risk_score=vlm_analysis.get("max_risk_score", 0),
            critical_observations=vlm_analysis.get("critical_observations", []),
            analysis_timestamp=vlm_analysis.get("analysis_timestamp", "")
        )
    
    async def fetch_historical_reports(
        self,
        video_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical VLM reports for context.
        
        Args:
            video_id: Current video ID (used to exclude from results)
            limit: Maximum number of historical reports
        
        Returns:
            List of historical report summaries
        """
        if not self.mongodb_handler:
            logger.debug("No MongoDB handler, skipping historical reports")
            return []
        
        try:
            return self.mongodb_handler.get_historical_reports(
                exclude_video_id=video_id,
                limit=limit
            )
        except Exception as e:
            logger.warning(f"Failed to fetch historical reports: {e}")
            return []
    
    def _parse_enhanced_report_sections(
        self,
        content: str
    ) -> Dict[str, str]:
        """
        Parse enhanced report content into sections.
        
        Args:
            content: Raw report content from Gemma
        
        Returns:
            Dictionary of section name to content
        """
        sections = {
            "executive_summary": "",
            "narrative_summary": "",
            "incident_breakdown": "",
            "evidence_mapping": "",
            "classification": "",
            "legal_notes": ""
        }
        
        # Simple section parsing based on headers
        section_markers = {
            "EXECUTIVE SUMMARY": "executive_summary",
            "DETAILED NARRATIVE": "narrative_summary",
            "NARRATIVE SUMMARY": "narrative_summary",
            "CHRONOLOGICAL": "incident_breakdown",
            "INCIDENT BREAKDOWN": "incident_breakdown",
            "STEP-BY-STEP": "incident_breakdown",
            "EVIDENCE MAPPING": "evidence_mapping",
            "EVIDENCE": "evidence_mapping",
            "CLASSIFICATION": "classification",
            "SEVERITY": "classification",
            "LEGAL": "legal_notes",
            "PROCEDURAL": "legal_notes"
        }
        
        current_section = None
        current_content = []
        
        for line in content.split("\n"):
            # Check if this line is a section header
            upper_line = line.upper().strip()
            new_section = None
            
            for marker, section_key in section_markers.items():
                if marker in upper_line and (upper_line.startswith("#") or upper_line.startswith("**")):
                    new_section = section_key
                    break
            
            if new_section:
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = new_section
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()
        
        return sections
    
    async def generate_enhanced_report(
        self,
        vlm_analysis: Dict[str, Any],
        video_metadata: Optional[Dict[str, Any]] = None,
        include_historical: bool = True
    ) -> EnhancedReport:
        """
        Generate enhanced documentation-style report.
        
        Pipeline:
        1. Fetch historical reports from DB
        2. Build prompt with VLM data + historical context
        3. Send to Gemma3-1B via Ollama
        4. Parse and structure response
        
        Args:
            vlm_analysis: Current VLM analysis results
            video_metadata: Optional video metadata
            include_historical: Whether to include historical context
        
        Returns:
            EnhancedReport object
        """
        start_time = datetime.utcnow()
        video_id = vlm_analysis.get("video_id", "")
        
        # Step 1: Check Ollama availability
        if not await self.check_ollama_availability():
            logger.error("Ollama not available for enhanced report generation")
            return EnhancedReport(
                video_id=video_id,
                generated_at=datetime.utcnow().isoformat(),
                success=False,
                error="Ollama service not available. Please ensure Ollama is running with gemma3:1b model."
            )
        
        # Step 2: Fetch historical reports
        historical_reports = []
        if include_historical:
            historical_reports = await self.fetch_historical_reports(video_id)
            logger.info(f"Fetched {len(historical_reports)} historical reports for context")
        
        # Step 3: Build prompt
        prompt = get_enhanced_report_prompt(
            vlm_analysis=vlm_analysis,
            historical_reports=historical_reports,
            video_metadata=video_metadata
        )
        
        logger.info(f"Generating enhanced report for video {video_id}")
        
        # Step 4: Generate via Ollama
        response = await self.ollama_client.generate_enhanced_report(
            prompt=prompt,
            system_prompt=ENHANCED_REPORT_SYSTEM_PROMPT
        )
        
        end_time = datetime.utcnow()
        generation_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        if not response.success:
            logger.error(f"Enhanced report generation failed: {response.error}")
            return EnhancedReport(
                video_id=video_id,
                generated_at=end_time.isoformat(),
                generation_time_ms=generation_time_ms,
                success=False,
                error=response.error
            )
        
        # Step 5: Parse sections
        sections = self._parse_enhanced_report_sections(response.content)
        
        return EnhancedReport(
            video_id=video_id,
            generated_at=end_time.isoformat(),
            content=response.content,
            executive_summary=sections.get("executive_summary", ""),
            narrative_summary=sections.get("narrative_summary", ""),
            incident_breakdown=sections.get("incident_breakdown", ""),
            evidence_mapping=sections.get("evidence_mapping", ""),
            classification=sections.get("classification", ""),
            legal_notes=sections.get("legal_notes", ""),
            vlm_risk_score=vlm_analysis.get("avg_risk_score", 0.0),
            observation_count=len(vlm_analysis.get("critical_observations", [])),
            generation_time_ms=generation_time_ms,
            success=True
        )
    
    async def generate_both_reports(
        self,
        vlm_analysis: Dict[str, Any],
        video_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate both classical and enhanced reports.
        
        Args:
            vlm_analysis: VLM analysis results
            video_metadata: Optional video metadata
        
        Returns:
            Dictionary with both reports
        """
        # Generate classical report (synchronous, fast)
        classical = self.generate_classical_report(vlm_analysis)
        
        # Generate enhanced report (async, may take time)
        enhanced = await self.generate_enhanced_report(
            vlm_analysis,
            video_metadata
        )
        
        return {
            "classical_report": classical.to_dict(),
            "enhanced_report": enhanced.to_dict()
        }
    
    async def close(self):
        """Cleanup resources."""
        await self.ollama_client.close()


async def test_report_generator():
    """Test report generator with sample data."""
    # Sample VLM analysis data
    sample_analysis = {
        "video_id": "vid_test123",
        "total_seconds": 10,
        "analyzed_seconds": 10,
        "avg_risk_score": 6.5,
        "max_risk_score": 8,
        "critical_observations": [
            {
                "behavior_type": "speeding",
                "risk_level": "high",
                "vehicle_id": "car_001",
                "confidence": "high",
                "description": "Vehicle traveling at high speed through intersection",
                "evidence": "Significant displacement between frames 1-3"
            }
        ],
        "analysis_timestamp": datetime.utcnow().isoformat()
    }
    
    generator = ReportGenerator()
    
    # Check Ollama
    available = await generator.check_ollama_availability()
    print(f"Ollama available: {available}")
    
    if available:
        # Generate enhanced report
        print("\nGenerating enhanced report...")
        enhanced = await generator.generate_enhanced_report(
            sample_analysis,
            include_historical=False  # No DB for test
        )
        
        print(f"Success: {enhanced.success}")
        if enhanced.success:
            print(f"Generation time: {enhanced.generation_time_ms}ms")
            print(f"\n--- Report Preview (first 500 chars) ---")
            print(enhanced.content[:500])
        else:
            print(f"Error: {enhanced.error}")
    
    await generator.close()


if __name__ == "__main__":
    asyncio.run(test_report_generator())
