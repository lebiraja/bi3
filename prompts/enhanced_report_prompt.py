"""
Enhanced Report Prompt Templates.
Used with Gemma3-1B via Ollama for generating police-ready documentation.
"""

from typing import Dict, List, Any, Optional


ENHANCED_REPORT_SYSTEM_PROMPT = """You are a professional incident documentation specialist creating formal police-ready traffic violation reports. Your reports must be:

1. **Highly Detailed**: Every incident must be fully explained with context
2. **Narrative-Oriented**: Written as a professional documentation, not bullet points
3. **Evidence-Based**: Reference specific frames, timestamps, and detection data
4. **Legally Informative**: Include relevant procedural notes

## Report Structure Requirements

### 1. EXECUTIVE SUMMARY
Provide a comprehensive overview of the incident in 3-4 paragraphs covering:
- What happened and when
- Who/what was involved (vehicles, pedestrians)
- Overall severity assessment

### 2. DETAILED NARRATIVE SUMMARY
A fully elaborated explanation including:
- Complete description of the incident
- How the violation occurred step-by-step
- Why it is considered a violation
- Contributing factors (weather, visibility, road conditions if visible)
- Object interactions (vehicles, pedestrians, infrastructure)

### 3. CHRONOLOGICAL INCIDENT BREAKDOWN
Sequential reconstruction of the event:
- Timeline-based explanation using exact timestamps
- Frame-by-frame progression of the incident
- Key moments identified with evidence

### 4. EVIDENCE MAPPING
Comprehensive evidence documentation:
- Frame references with timestamps
- YOLO detection data summary
- Behavioral signals from VLM analysis
- Visual evidence descriptions

### 5. CLASSIFICATION & SEVERITY
- Incident category/type
- Severity level with justification
- Risk assessment

### 6. LEGAL/PROCEDURAL NOTES
Informational guidance:
- Why the incident may be relevant for authorities
- Nature of the violation under traffic law
- Potential risk to public safety
- Recommended follow-up actions

## Writing Guidelines
- Use formal, professional language
- Write in complete paragraphs, not short bullet points
- Be specific with times, positions, and evidence
- Avoid speculation - only state what is evidenced
- This is NOT a summary - it is comprehensive documentation
"""


def get_enhanced_report_prompt(
    vlm_analysis: Dict[str, Any],
    historical_reports: Optional[List[Dict[str, Any]]] = None,
    video_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate the prompt for enhanced report generation.
    
    Args:
        vlm_analysis: Current VLM analysis results including observations
        historical_reports: Past VLM summaries for context
        video_metadata: Video information (duration, fps, etc.)
    
    Returns:
        Formatted prompt for Gemma3-1B
    """
    prompt_parts = []
    
    # Video context
    prompt_parts.append("# INCIDENT ANALYSIS DATA\n")
    
    if video_metadata:
        prompt_parts.append("## Video Information")
        prompt_parts.append(f"- Video ID: {video_metadata.get('video_id', 'Unknown')}")
        prompt_parts.append(f"- Duration: {video_metadata.get('total_seconds', 'Unknown')} seconds")
        prompt_parts.append(f"- Analyzed Seconds: {video_metadata.get('analyzed_seconds', 'Unknown')}")
        prompt_parts.append(f"- Analysis Timestamp: {video_metadata.get('analysis_timestamp', 'Unknown')}")
        prompt_parts.append("")
    
    # Current VLM Analysis
    prompt_parts.append("## Current VLM Analysis Results\n")
    
    # Risk scores
    avg_risk = vlm_analysis.get("avg_risk_score", 0)
    max_risk = vlm_analysis.get("max_risk_score", 0)
    prompt_parts.append(f"### Risk Assessment")
    prompt_parts.append(f"- Average Risk Score: {avg_risk}/10")
    prompt_parts.append(f"- Maximum Risk Score: {max_risk}/10")
    prompt_parts.append("")
    
    # Critical observations
    observations = vlm_analysis.get("critical_observations", [])
    if observations:
        prompt_parts.append("### Critical Observations Detected")
        for i, obs in enumerate(observations, 1):
            prompt_parts.append(f"\n#### Observation {i}")
            prompt_parts.append(f"- **Behavior Type**: {obs.get('behavior_type', 'Unknown')}")
            prompt_parts.append(f"- **Risk Level**: {obs.get('risk_level', 'Unknown')}")
            prompt_parts.append(f"- **Vehicle ID**: {obs.get('vehicle_id', 'Unknown')}")
            prompt_parts.append(f"- **Confidence**: {obs.get('confidence', 'Unknown')}")
            prompt_parts.append(f"- **Description**: {obs.get('description', 'No description')}")
            prompt_parts.append(f"- **Evidence**: {obs.get('evidence', 'No evidence provided')}")
    else:
        prompt_parts.append("### No Critical Observations Detected")
        prompt_parts.append("The VLM analysis did not identify any critical violations.")
    
    prompt_parts.append("")
    
    # Per-second analysis data if available
    all_analyses = vlm_analysis.get("all_analyses", [])
    if all_analyses:
        prompt_parts.append("### Per-Second Analysis Data")
        for analysis in all_analyses[:20]:  # Limit to avoid token overflow
            second_idx = analysis.get("second_index", "?")
            timestamp_start = analysis.get("timestamp_start_ms", 0)
            timestamp_end = analysis.get("timestamp_end_ms", 0)
            risk_score = analysis.get("risk_score", 0)
            summary = analysis.get("summary", "")
            frame_nums = analysis.get("frame_numbers", [])
            
            prompt_parts.append(f"\n**Second {second_idx}** ({timestamp_start}ms - {timestamp_end}ms)")
            prompt_parts.append(f"- Frames: {frame_nums}")
            prompt_parts.append(f"- Risk Score: {risk_score}/10")
            if summary:
                prompt_parts.append(f"- Summary: {summary}")
            
            # Include observations for this second
            second_obs = analysis.get("observations", [])
            if second_obs:
                for obs in second_obs:
                    prompt_parts.append(f"  - {obs.get('behavior_type', 'Unknown')}: {obs.get('description', '')}")
        
        prompt_parts.append("")
    
    # Historical context
    if historical_reports:
        prompt_parts.append("## Historical Context (Previous Analyses)")
        prompt_parts.append("The following are summaries from previous video analyses that may provide behavioral patterns and trends:\n")
        
        for i, report in enumerate(historical_reports[-5:], 1):  # Last 5 reports
            prompt_parts.append(f"### Previous Report {i}")
            prompt_parts.append(f"- Video ID: {report.get('video_id', 'Unknown')}")
            prompt_parts.append(f"- Analyzed At: {report.get('analyzed_at', 'Unknown')}")
            prompt_parts.append(f"- Risk Score: {report.get('avg_risk_score', 'N/A')}")
            
            prev_obs = report.get("critical_observations", [])
            if prev_obs:
                prompt_parts.append("- Key Findings:")
                for obs in prev_obs[:3]:
                    prompt_parts.append(f"  - {obs.get('behavior_type', 'Unknown')}: {obs.get('description', '')}")
            prompt_parts.append("")
    
    # Task instruction
    prompt_parts.append("---\n")
    prompt_parts.append("# YOUR TASK")
    prompt_parts.append("""
Based on ALL the data provided above, generate a comprehensive, police-ready ENHANCED INCIDENT REPORT.

This report must be:
1. **Significantly more detailed** than the raw VLM output
2. **Narrative in style** - written as formal documentation, not lists
3. **Evidence-based** - reference specific frames, timestamps, and detections
4. **Structured** - follow the report structure defined in your system prompt

If no critical incidents were detected, still provide a formal documentation noting the analysis was conducted and no violations were found.

Generate the Enhanced Incident Report now:
""")
    
    return "\n".join(prompt_parts)


def format_classical_report(vlm_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format VLM analysis into the classical report structure.
    This maintains backward compatibility with existing report format.
    
    Args:
        vlm_analysis: VLM analysis results
    
    Returns:
        Formatted classical report dictionary
    """
    return {
        "report_type": "classical",
        "video_id": vlm_analysis.get("video_id", "Unknown"),
        "total_seconds": vlm_analysis.get("total_seconds", 0),
        "analyzed_seconds": vlm_analysis.get("analyzed_seconds", 0),
        "avg_risk_score": vlm_analysis.get("avg_risk_score", 0),
        "max_risk_score": vlm_analysis.get("max_risk_score", 0),
        "critical_observations": vlm_analysis.get("critical_observations", []),
        "analysis_timestamp": vlm_analysis.get("analysis_timestamp", "")
    }
