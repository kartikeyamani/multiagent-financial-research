"""
evaluation/ragas_eval.py
------------------------
RAGAS evaluation module.
Computes Faithfulness and Context Recall after each completed run.
Handles both ragas >=0.2.x (new API) and <0.2.x (legacy API) gracefully.
"""

import logging
import math
import time

logger = logging.getLogger(__name__)


def _sanitize(value):
    """Convert NaN / Inf floats → None so they serialize as JSON null."""
    if value is None:
        return None
    try:
        if math.isnan(value) or math.isinf(value):
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def evaluate_run(query: str, report: str, chunks: list[dict]) -> dict:
    """
    Run RAGAS evaluation on a completed pipeline run.

    Parameters
    ----------
    query   : The original research question (used as 'question').
    report  : The final generated report (used as 'answer').
    chunks  : Retrieved chunks whose text fields are the 'contexts'.

    Returns
    -------
    dict with keys:
        faithfulness     : float [0, 1] or None
        context_recall   : float [0, 1] or None
        latency_s        : evaluation wall-clock time
        error            : error message string if evaluation failed
    """
    contexts = [c["text"] for c in chunks]
    t0 = time.time()

    logger.info("[RAGAS] Starting evaluation …")

    try:
        # ── Try ragas >= 0.2.x API ─────────────────────────────────────────────
        scores = _evaluate_new_api(query, report, contexts)
    except Exception as e_new:
        logger.warning(f"[RAGAS] New API failed ({e_new}), trying legacy API …")
        try:
            scores = _evaluate_legacy_api(query, report, contexts)
        except Exception as e_old:
            logger.error(f"[RAGAS] Both APIs failed: {e_old}")
            return {
                "faithfulness": None,
                "context_recall": None,
                "latency_s": time.time() - t0,
                "error": str(e_old),
            }

    scores["latency_s"] = time.time() - t0
    logger.info(
        f"[RAGAS] Evaluation complete in {scores['latency_s']:.1f}s | "
        f"faithfulness={scores.get('faithfulness')} | "
        f"context_recall={scores.get('context_recall')}"
    )
    return scores


# ── ragas >= 0.2 ───────────────────────────────────────────────────────────────
def _evaluate_new_api(query: str, answer: str, contexts: list[str]) -> dict:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import Faithfulness, ContextRecall
    from ragas.dataset_schema import SingleTurnSample, EvaluationDataset

    sample = SingleTurnSample(
        user_input=query,
        response=answer,
        retrieved_contexts=contexts,
        reference=query,          # placeholder ground truth
    )
    dataset = EvaluationDataset(samples=[sample])
    result = ragas_evaluate(
        dataset,
        metrics=[Faithfulness(), ContextRecall()],
    )
    scores_df = result.to_pandas()
    return {
        "faithfulness": _sanitize(scores_df["faithfulness"].iloc[0]),
        "context_recall": _sanitize(scores_df["context_recall"].iloc[0]),
        "error": None,
    }


# ── ragas < 0.2 (legacy) ───────────────────────────────────────────────────────
def _evaluate_legacy_api(query: str, answer: str, contexts: list[str]) -> dict:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import faithfulness, context_recall  # type: ignore
    from datasets import Dataset

    data = {
        "question": [query],
        "answer": [answer],
        "contexts": [contexts],
        "ground_truths": [[query]],   # placeholder
    }
    dataset = Dataset.from_dict(data)
    result = ragas_evaluate(dataset, metrics=[faithfulness, context_recall])
    scores_df = result.to_pandas()
    return {
        "faithfulness": _sanitize(scores_df["faithfulness"].iloc[0]),
        "context_recall": _sanitize(scores_df["context_recall"].iloc[0]),
        "error": None,
    }
