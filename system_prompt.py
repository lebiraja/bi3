"""
System prompt for behavioral analysis using VLM.
Optimized for speed with gemma3:4b model.
"""

# Compact system prompt for faster inference
SYSTEM_PROMPT = """You are a traffic safety AI. Analyze the image and YOLO data to detect risky driving.

Behaviors to detect: speeding, erratic_movement, sudden_stop, violation, collision

Output ONLY this JSON format:
{
    "observations": [
        {
            "behavior_type": "speeding|erratic_movement|sudden_stop|violation",
            "vehicle_id": "ID or description",
            "confidence": "high|medium|low",
            "evidence": "what you see",
            "risk_level": "critical|warning|low",
            "description": "brief description"
        }
    ],
    "overall_assessment": {
        "risk_score": 1-10,
        "summary": "one sentence summary",
        "recommended_alerts": []
    }
}

Rules:
- Be conservative, avoid false positives
- Consider traffic context (urban=crowded is normal)
- Only report genuine risks with evidence
- If traffic is normal, use risk_score 1-3
"""


def get_analysis_prompt(yolo_data: dict, frame_count: int = 1) -> str:
    """
    Generate compact user prompt with YOLO detection context.

    Args:
        yolo_data: Dictionary containing YOLO detection results
        frame_count: Number of frames being analyzed

    Returns:
        Formatted user prompt string
    """
    prompt = "Analyze this traffic scene.\n\nYOLO Detections:\n"

    if yolo_data.get("detections"):
        for frame_idx, detections in enumerate(yolo_data["detections"]):
            if detections:
                for det in detections:
                    track_id = det.get('track_id', 'N/A')
                    class_name = det.get('class_name', 'vehicle')
                    prompt += f"- {class_name} (ID:{track_id})\n"
            else:
                prompt += "- No vehicles\n"
    else:
        prompt += "- No data\n"

    prompt += "\nProvide JSON analysis."

    return prompt
