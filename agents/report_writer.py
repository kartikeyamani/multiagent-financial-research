"""
agents/report_writer.py
-----------------------
Report Writer Agent
Takes the analyst's structured JSON output plus the original retrieved chunks
and writes a clean ~300-word financial research report with inline citations.
"""

import logging
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

# ── System prompt for the Report Writer ───────────────────────────────────────
REPORT_WRITER_SYSTEM_PROMPT = """You are a professional financial report writer for an institutional equity research team.

Your task is to write a clear, authoritative financial research report of approximately 300 words.

Formatting rules:
- Use professional financial prose (no bullet points, no markdown headers with #)
- Cite sources inline as [Source N] where N corresponds to the source number provided
- Structure: 1 paragraph executive summary, 2 paragraphs of analysis (insights + financials), 1 paragraph on risks, 1 paragraph on opportunities/outlook
- End with a "Sources" section listing each cited filing
- Do NOT fabricate any numbers — use only what is in the analysis and retrieved chunks
- Write in third-person, present tense for current analysis"""


class ReportWriterAgent:
    """Synthesises the analyst's findings into a polished research report."""

    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-4.1"

    def run(self, analysis: dict, chunks: list[dict], query: str) -> dict:
        """
        Parameters
        ----------
        analysis : Structured analysis dict from the Analyst agent.
        chunks   : Retrieved chunk list (used for citation metadata).
        query    : Original research question.

        Returns
        -------
        dict with keys:
            report      : final report string
            citations   : list of citation dicts (source_n, company, filing, section)
            token_count : total tokens used
            latency_s   : wall-clock time
        """
        logger.info(f"[ReportWriter] Writing report for query: '{query}'")
        t0 = time.time()

        # ── Build citations list ────────────────────────────────────────────────
        citations = []
        source_lines = []
        for i, chunk in enumerate(chunks, 1):
            citations.append(
                {
                    "source_n": i,
                    "company": chunk["company"],
                    "ticker": chunk["ticker"],
                    "filing": chunk["filing"],
                    "section": chunk["section"],
                }
            )
            source_lines.append(
                f"Source {i}: {chunk['company']} ({chunk['ticker']}) — "
                f"{chunk['filing']}, Section: {chunk['section']}"
            )

        sources_block = "\n".join(source_lines)

        # ── Build user message ──────────────────────────────────────────────────
        import json
        user_message = (
            f"Research Question: {query}\n\n"
            f"Analyst's Structured Analysis:\n{json.dumps(analysis, indent=2)}\n\n"
            f"Available Sources for Citation:\n{sources_block}\n\n"
            f"Write the financial research report now (≈300 words, cite sources inline as [Source N])."
        )

        # ── Call GPT-4 ──────────────────────────────────────────────────────────
        logger.info(f"[ReportWriter] Calling {self.model} …")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": REPORT_WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.4,
        )

        report = response.choices[0].message.content.strip()
        token_count = response.usage.total_tokens
        latency = time.time() - t0

        logger.info(
            f"[ReportWriter] Report complete in {latency:.2f}s | tokens={token_count} | "
            f"words≈{len(report.split())}"
        )

        return {
            "report": report,
            "citations": citations,
            "token_count": token_count,
            "latency_s": latency,
        }
