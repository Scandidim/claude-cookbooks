"""
Market Bot Agent
────────────────
Autonomous agent for market-facing tasks:
  • Competitor analysis
  • Ad copy generation (Facebook, Google, Telegram)
  • SEO content briefs
  • Lead magnet ideas
  • Price monitoring reports
  • Market opportunity research

Supports both Claude (primary) and Gemini (secondary/parallel) for cost optimisation.
"""

from __future__ import annotations

import anthropic

from portal import config
from portal.storage import log, save_artifact

SYSTEM_PROMPT = """You are the Market Bot — an expert digital marketer and business analyst.

Your tasks include:
- Writing high-converting ad copy (Facebook, Google Ads, Telegram)
- Analysing competitor positioning and pricing
- Finding market opportunities and underserved niches
- Creating SEO content briefs and keyword strategies
- Building lead magnet ideas and sales funnels
- Writing product descriptions and landing page copy

Always:
- Be specific with numbers, examples, and actionable recommendations
- Tailor content to the target audience and platform
- Match the user's language (Ukrainian / English / other)
- Structure output clearly with sections
"""

GEMINI_SYSTEM = """You are an expert market researcher and digital marketing specialist.
Provide concise, data-driven analysis and actionable recommendations."""


class MarketBotAgent:
    def __init__(self) -> None:
        self._claude = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._gemini = None
        if config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai  # type: ignore[import]

                genai.configure(api_key=config.GEMINI_API_KEY)
                self._gemini = genai.GenerativeModel(
                    model_name="gemini-2.0-flash",
                    system_instruction=GEMINI_SYSTEM,
                )
            except ImportError:
                pass  # google-generativeai not installed — use Claude only

    def run(self, task_id: str, intent: str, user_input: str, extracted: dict) -> str:
        """Run market analysis/content generation. Returns result text."""
        log(task_id, "market_bot", f"Starting market task: {intent}")

        # Use Gemini for quick research if available, Claude for final output
        research_context = ""
        if self._gemini:
            try:
                research_prompt = (
                    f"Quick market context for: {user_input[:500]}\nBe brief, 3-5 bullet points."
                )
                gem_resp = self._gemini.generate_content(research_prompt)
                research_context = f"\n\nMarket context (Gemini research):\n{gem_resp.text}"
                log(task_id, "market_bot", "Gemini research completed")
            except Exception as e:
                log(task_id, "market_bot", f"Gemini failed, using Claude only: {e}", "warning")

        full_prompt = user_input + research_context
        if extracted:
            full_prompt += f"\n\nAdditional context: {extracted}"

        response = self._claude.messages.create(
            model=config.MODEL_MARKET_BOT,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.4,
        )
        result = response.content[0].text

        save_artifact(
            task_id=task_id,
            artifact_type="report",
            title=intent[:200],
            content=result,
            metadata={"source_model": "claude+gemini" if research_context else "claude"},
        )
        log(task_id, "market_bot", f"Market artifact saved ({len(result)} chars)")
        return result
