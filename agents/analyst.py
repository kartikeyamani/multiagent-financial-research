"""
agents/analyst.py
-----------------
Analyst Agent
Takes the retrieved SEC filing chunks and the original query,
calls GPT-4 with structured output, and returns a JSON analysis
containing key insights, identified risks, and opportunities.
"""

import json
import logging
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

# ── System prompt for the Analyst ─────────────────────────────────────────────
ANALYST_SYSTEM_PROMPT = """You are a senior financial analyst specializing in equity research.
You will be given excerpts from SEC 10-K filings and a research question.

Your task is to produce a structured JSON analysis with the following exact schema:

{
  "summary": "<2-3 sentence executive summary directly answering the research question>",
  "key_insights": [
    "<specific, data-backed insight 1>",
    "<specific, data-backed insight 2>",
    "<specific, data-backed insight 3>"
  ],
  "risks": [
    {
      "risk": "<risk title>",
      "description": "<1-2 sentence explanation with evidence from the filings>",
      "severity": "High | Medium | Low"
    }
  ],
  "opportunities": [
    {
      "opportunity": "<opportunity title>",
      "description": "<1-2 sentence explanation with evidence from the filings>",
      "potential_impact": "High | Medium | Low"
    }
  ],
  "financial_metrics": {
    "<metric_name>": "<value with units>"
  },
  "companies_covered": ["<ticker1>", "<ticker2>"],
  "data_quality_note": "<any caveats about the data or analysis>"
}

Be precise, cite specific numbers from the provided context, and be objective.
Return ONLY valid JSON — no markdown fences, no extra text."""


class AnalystAgent:
    """Analyses retrieved chunks and produces structured financial insights."""

    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-4.1"

    def run(self, chunks: list[dict], query: str) -> dict:
        """
        Parameters
        ----------
        chunks : List of retrieved chunk dicts from the Researcher agent.
        query  : The original research question.

        Returns
        -------
        dict with keys:
            analysis    : structured analysis dict
            token_count : total tokens used (prompt + completion)
            latency_s   : wall-clock time
        """
        logger.info(f"[Analyst] Analysing {len(chunks)} chunks for query: '{query}'")
        t0 = time.time()

        # ── Build context from retrieved chunks ─────────────────────────────────
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Source {i}: {chunk['company']} | {chunk['filing']} | {chunk['section']}]\n"
                f"{chunk['text']}"
            )
        context = "\n\n---\n\n".join(context_parts)

        user_message = (
            f"Research Question: {query}\n\n"
            f"SEC Filing Excerpts:\n\n{context}\n\n"
            f"Please provide your structured JSON analysis."
        )

        # ── Call GPT-4 ──────────────────────────────────────────────────────────
        logger.info(f"[Analyst] Calling {self.model} …")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,  # low temperature for factual analysis
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content
        token_count = response.usage.total_tokens
        latency = time.time() - t0

        # ── Parse JSON output ───────────────────────────────────────────────────
        try:
            analysis = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"[Analyst] JSON parse error: {e}")
            # Attempt to salvage partial JSON or return a fallback
            analysis = {
                "summary": raw_content[:500],
                "key_insights": [],
                "risks": [],
                "opportunities": [],
                "financial_metrics": {},
                "companies_covered": [],
                "data_quality_note": "JSON parse error – raw output stored in summary.",
            }

        logger.info(
            f"[Analyst] Analysis complete in {latency:.2f}s | tokens={token_count}"
        )
        return {
            "analysis": analysis,
            "token_count": token_count,
            "latency_s": latency,
        }
