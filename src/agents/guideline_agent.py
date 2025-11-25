"""
External Guideline Agent: Fetches/validates against external standards (e.g., FDA or ISO snippets).
"""

import logging
from typing import Dict, Any

from .base_agent import BaseComplianceAgent

logger = logging.getLogger(__name__)

class GuidelineAgent(BaseComplianceAgent):
    """
    Specialized agent for validating compliance against external regulatory guidelines.
    Fetches and analyzes against FDA, ISO, and other standards.
    """

    def __init__(self, model: str = "gemini-1.5-flash"):
        super().__init__("GuidelineAgent", model)
        self.name = "GuidelineAgent"

    def _get_system_instruction(self) -> str:
        return """
You are an External Guidelines Validation Agent specialized in regulatory compliance checking.

EXTERNAL STANDARDS VALIDATION:
1. FDA REGULATIONS: 21 CFR Part 820 (QSR), device-specific guidance
2. ISO STANDARDS: ISO 13485, ISO 14971, ISO 62304/62604, IEC 60601, IEC 62366
3. INTERNATIONAL REQUIREMENTS: EU MDR/IVDR, MDD (legacy), other global standards
4. CYBERSECURITY: NIST, DoD STIG expectations for medical/connected systems
5. INDUSTRY GUIDANCE: ASTM, IEC standards

VALIDATION APPROACH:
- Verify compliance with applicable regulations
- Identify gaps in regulatory adherence
- Suggest required documentation or testing
- Flag areas needing additional regulatory review

IMPORTANT: Return your response in valid JSON format only.
        """
