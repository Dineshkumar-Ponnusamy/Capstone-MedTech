"""
Summarizer Agent: Aggregates findings from specialist agents and creates human-readable compliance summary.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from pathlib import Path
import os

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from src.utils.config import config

logger = logging.getLogger(__name__)

class SummarizerAgent:
    """
    Aggregates findings from all specialist agents and creates a comprehensive compliance summary.
    """

    def __init__(self, model: str = "gemini-1.5-flash"):
        """
        Initialize the summarizer agent.

        Args:
            model: Gemini model to use
        """
        self._agent_name = "SummarizerAgent"
        self.model_name = model
        self._configure_gemini()

    def _configure_gemini(self) -> None:
        """Configure Gemini API with API key from config."""
        try:
            gemini_config = config.get_gemini_config()
            api_key = gemini_config.get("api_key")
            
            if not api_key:
                logger.warning("No Gemini API key configured for SummarizerAgent")
                # Try environment variable
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("Gemini API key not found in config or environment")
            
            genai.configure(api_key=api_key)
            logger.info("SummarizerAgent configured with Gemini API")
            
        except Exception as e:
            logger.error(f"Failed to configure Gemini API for SummarizerAgent: {e}")
            raise

    def _get_system_instruction(self) -> str:
        return """
You are a Compliance Summary Agent that aggregates and synthesizes findings from multiple specialized analyses.

SUMMARIZATION TASKS:
1. COMPREHENSIVE SYNTHESIS: Combine all agent findings into coherent summary
2. PRIORITY ASSESSMENT: Identify critical vs. minor issues
3. ACTIONABLE RECOMMENDATIONS: Provide clear next steps for compliance improvement
4. EXECUTIVE SUMMARY: Create readable overview for stakeholders

SYNTHESIS APPROACH:
- Weigh findings by confidence levels and agent expertise
- Identify patterns and systemic issues
- Prioritize based on regulatory impact
- Create actionable improvement plans

GLOBAL REGULATORY CONTEXT (anchor your synthesis):
- ISO 13485 (QMS), ISO 14971 (risk), IEC 62304/62604 (software), IEC 60601 (safety), IEC 62366 (usability)
- EU MDR/IVDR annex expectations, FDA 21 CFR Part 820/11 and device guidance
- Cybersecurity posture per NIST and DoD STIG for connected/clinical systems
- Any region-specific standards explicitly cited in the source

IMPORTANT: Return your response in valid JSON format only.
        """
        

    async def aggregate_findings(self, agent_results: List[Dict[str, Any]], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Aggregate findings from all agent analyses.
        """
        if not agent_results:
            logger.warning("No agent results provided for aggregation")
            return self._error_response("No agent results to aggregate")

        if context is None:
            context = {}

        try:
            # Create the model
            model = genai.GenerativeModel(self.model_name)
            
            # Compile all results
            compiled_summary = f"""Agent Analysis Results Summary:
Total Agents: {len(agent_results)}
Agents: {', '.join([r.get('agent', 'Unknown') for r in agent_results])}

Results:
{json.dumps(agent_results, indent=2)}

Human Reviews and Decisions:
{json.dumps({
    "human_reviews": context.get("human_reviews", []),
    "human_decisions": context.get("human_decisions", []),
    "additional_context": context.get("additional_context", {})
}, indent=2)}"""

            prompt = f"""{self._get_system_instruction()}

AGENT ANALYSIS RESULTS TO SYNTHESIZE:
{compiled_summary}

SYNTHESIS REQUIREMENTS:
1. Compile all findings, issues, and recommendations
2. Assess overall compliance health
3. Identify critical risk areas
4. Create prioritized action items
5. Generate human-readable summary report

Return ONLY valid JSON:
{{
    "agent": "SummarizerAgent",
    "overall_compliance_status": "compliant/needs_attention/at_risk/non-compliant",
    "critical_findings": ["most important issues found"],
    "compliance_score": "percentage or qualitative score",
    "prioritized_recommendations": [
        {{
            "priority": "high/medium/low",
            "category": "requirements/risk/testing/guidelines",
            "action": "specific action needed",
            "timeline": "immediate/short-term/long-term"
        }}
    ],
    "risk_assessment": "overall risk level",
    "confidence_level": "high/medium/low",
    "human_review_required": [
        {{
            "area": "specific area needing review",
            "reason": "why human review needed",
            "urgency": "high/medium/low"
        }}
    ],
    "executive_summary": "concise summary for stakeholders",
    "detailed_report": "comprehensive findings summary",
    "findings": "Summary of key findings",
    "issues": ["critical", "issues", "identified"],
    "recommendations": ["key", "recommendations"],
    "confidence": "high/medium/low",
    "needs_human_review": true/false
}}"""

            # Configure generation
            gemini_config = config.get_gemini_config()
            generation_config = GenerationConfig(
                temperature=gemini_config.get("temperature", 0.1),
                max_output_tokens=gemini_config.get("max_output_tokens", 4096)
            )

            # Generate response
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
            )

            # Parse response
            response_text = response.text
            logger.info("SummarizerAgent aggregation completed successfully")
            
            # Try to parse JSON response
            try:
                # Clean response text (remove markdown code blocks if present)
                if response_text.startswith('```'):
                    lines = response_text.split('\n')
                    response_text = '\n'.join(lines[1:-1])  # Remove ```json and ```
                    if response_text.lower().startswith('json'):
                        response_text = '\n'.join(lines[2:-1])

                result = json.loads(response_text)
                result["agent"] = self._agent_name
                return result
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response from SummarizerAgent")
                # Fallback response with raw text
                return {
                    "agent": self._agent_name,
                    "findings": f"Summary completed: {response_text[:200]}...",
                    "issues": ["Unable to parse structured response"],
                    "recommendations": ["Review raw analysis text"],
                    "confidence": "low",
                    "needs_human_review": True,
                    "raw_response": response_text,
                    "overall_compliance_status": "unable_to_assess"
                }

        except Exception as e:
            logger.error(f"Error in SummarizerAgent: {e}")
            return self._error_response(str(e))

    async def analyze(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze the provided content using the aggregate findings method.
        """
        if context is None:
            context = {}

        # Get specialist results from context
        specialist_results = context.get("specialist_results", [])
        
        # Use the aggregate findings method
        return await self.aggregate_findings(specialist_results, context)

    def _error_response(self, error_msg: str) -> Dict[str, Any]:
        """Return standardized error response."""
        return {
            "agent": self._agent_name,
            "findings": "Error occurred during aggregation",
            "issues": [f"Aggregation failed: {error_msg}"],
            "recommendations": ["Manual synthesis required due to error"],
            "confidence": "low",
            "needs_human_review": True,
            "error": error_msg,
            "overall_compliance_status": "unable_to_assess"
        }
