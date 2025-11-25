"""
Base agent class for compliance review agents using Google Gemini API.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import os

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from src.utils.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseComplianceAgent:
    """
    Base agent class for specialized compliance review agents.
    Uses Google Gemini API for analysis.
    """

    def __init__(self, name: str, model: str = "gemini-1.5-flash"):
        """
        Initialize the compliance agent.

        Args:
            name: Agent name
            model: Gemini model to use
        """
        self._agent_name = name
        self.model_name = model
        self._configure_gemini()

    def _configure_gemini(self) -> None:
        """Configure Gemini API with API key from config."""
        try:
            gemini_config = config.get_gemini_config()
            api_key = gemini_config.get("api_key")
            
            if not api_key:
                logger.warning(f"No Gemini API key configured for {self._agent_name}")
                # Try environment variable
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("Gemini API key not found in config or environment")
            
            genai.configure(api_key=api_key)
            logger.info(f"{self._agent_name} configured with Gemini API")
            
        except Exception as e:
            logger.error(f"Failed to configure Gemini API for {self._agent_name}: {e}")
            raise

    def _get_system_instruction(self) -> str:
        """Return the system instruction for this agent. Override in subclasses."""
        return f"""You are a specialized compliance review agent named {self._agent_name}.
        
You analyze medical device documentation for regulatory compliance.
Always provide detailed, accurate analysis with specific recommendations.
Respond in structured JSON format with clear findings and action items.
        """

    async def analyze(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze the provided content using Gemini API.

        Args:
            content: Document content to analyze
            context: Additional context information

        Returns:
            Analysis results
        """
        if context is None:
            context = {}

        if not content or not isinstance(content, str):
            logger.warning(f"Invalid content provided to {self._agent_name}")
            return self._error_response("Invalid content provided")

        try:
            # Create the model
            model = genai.GenerativeModel(self.model_name)
            
            # Build the prompt
            system_instruction = self._get_system_instruction()
            prompt = f"""{system_instruction}

Additional Context: {json.dumps(context, indent=2)}

Document Content:
{content[:4000]}  # Truncate if too long
{content[4000:] if len(content) > 4000 else ''}

Please analyze this content and provide your assessment.
Return only a JSON response with the following structure:

{{
    "agent": "{self._agent_name}",
    "findings": "Summary of your key findings",
    "issues": ["List", "of", "specific", "issues", "identified"],
    "recommendations": ["List", "of", "specific", "recommendations"],
    "confidence": "high/medium/low",
    "needs_human_review": true/false,
    "additional_data": {{
        // Agent-specific additional data
    }}
}}"""

            # Configure generation
            gemini_config = config.get_gemini_config()
            generation_config = GenerationConfig(
                temperature=gemini_config.get("temperature", 0.2),
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
            logger.info(f"{self._agent_name} analysis completed successfully")
            
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
                logger.warning(f"Failed to parse JSON response from {self._agent_name}")
                # Fallback response with raw text
                return {
                    "agent": self._agent_name,
                    "findings": f"Analysis completed: {response_text[:200]}...",
                    "issues": ["Unable to parse structured response"],
                    "recommendations": ["Review raw analysis text"],
                    "confidence": "low",
                    "needs_human_review": True,
                    "raw_response": response_text
                }

        except Exception as e:
            logger.error(f"Error in {self._agent_name}: {e}")
            return self._error_response(str(e))

    def _error_response(self, error_msg: str) -> Dict[str, Any]:
        """Return standardized error response."""
        return {
            "agent": self._agent_name,
            "findings": "Error occurred during analysis",
            "issues": [f"Analysis failed: {error_msg}"],
            "recommendations": ["Manual review required due to analysis error"],
            "confidence": "low",
            "needs_human_review": True,
            "error": error_msg
        }
