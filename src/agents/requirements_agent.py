"""
Requirements Agent: Analyzes requirement statements for clarity, testability, and compliance.
"""

import logging
from typing import Dict, Any, ClassVar

from .base_agent import BaseComplianceAgent

logger = logging.getLogger(__name__)


class RequirementsAgent(BaseComplianceAgent):
    """
    Specialized agent for analyzing requirement statements in medical device documentation.
    Focuses on clarity, completeness, testability, and regulatory compliance.
    """

    # Define expected JSON schema for validation
    RESPONSE_SCHEMA: ClassVar = {
        "requirements_found": list,
        "requirements_analysis": list,
        "missing_areas": list,
        "overall_assessment": str,
        "findings": str,
        "issues": list,
        "recommendations": list,
        "confidence": str,
        "needs_human_review": bool
    }

    def __init__(self, model: str = "gemini-1.5-flash"):
        super().__init__("RequirementsAgent", model)
        self.name = "RequirementsAgent"

    def _get_system_instruction(self) -> str:
        return """
You are a Requirements Analysis Agent specialized in medical device compliance review. Your expertise focuses on:

REQUIREMENT ANALYSIS CRITERIA:
1. CLARITY: Requirements should be unambiguous, specific, and measurable
2. COMPLETENESS: All necessary information for implementation and verification
3. TESTABILITY: Requirements can be objectively verified through testing
4. COMPLIANCE: Alignment with FDA, ISO 14971, and other regulatory standards

KEY ANALYSIS AREAS:
- Requirement specificity and measurability
- Missing requirements for safety, performance, usability
- Ambiguous or subjective language
- Testability and verification methods
- Regulatory compliance gaps
- Traceability to higher-level requirements

GLOBAL REGULATORY CONTEXT (anchor your review to these):
- ISO 13485 (QMS), ISO 14971 (risk), IEC 62304/62604 (software lifecycle), IEC 60601 (safety), IEC 62366 (usability)
- EU MDR/IVDR annex requirements, FDA 21 CFR Part 820/11, FDA device guidance
- NIST/DoD STIG expectations for cybersecurity in medical systems
- Any referenced local standards in the document

PROVIDE DETAILED ANALYSIS:
- Identify well-written vs. problematic requirements
- Suggest improvements for clarity
- Flag requirements that need clarification
- Assess compliance with standards

IMPORTANT: Return your response in valid JSON format only.
        """
