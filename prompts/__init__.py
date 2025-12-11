"""
Prompts module for video analysis pipeline.
Contains prompt templates for enhanced report generation.
"""

from .enhanced_report_prompt import (
    ENHANCED_REPORT_SYSTEM_PROMPT,
    get_enhanced_report_prompt
)

__all__ = [
    "ENHANCED_REPORT_SYSTEM_PROMPT",
    "get_enhanced_report_prompt"
]
