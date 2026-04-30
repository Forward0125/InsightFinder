"""LLM-as-judge evaluation for streamed RAG answers.

A single ``gpt-4o-mini`` call scores the answer on three dimensions
using OpenAI's strict JSON-schema response format -- so we get
guaranteed-typed numbers without any post-hoc parsing of free-form
text.

Dimensions (each 0.0 ... 1.0):

  faithfulness        higher = better. Are the answer's claims
                      grounded in the supplied sources?
  answer_relevance    higher = better. Does the answer actually
                      address the user's question?
  hallucination_risk  LOWER  = better. Estimated probability that the
                      answer contains claims not supported by sources.

A run "passes the gates" when all three thresholds are met. Defaults
match what the dashboard surfaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from app import db
from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)


# ─── Thresholds for the "gates_passed" column ─────────────────────

THRESHOLDS = {
    "faithfulness":       0.70,    # min
    "answer_relevance":   0.70,    # min
    "hallucination_risk": 0.30,    # max
}


@dataclass
class EvalResult:
    faithfulness:       float
    answer_relevance:   float
    hallucination_risk: float
    reasoning:          str
    gates_passed:       bool
    evaluator_model:    str
    tokens_in:          int = 0
    tokens_out:         int = 0


def _passed(scores: dict[str, float]) -> bool:
    return (
        scores["faithfulness"]       >= THRESHOLDS["faithfulness"]
        and scores["answer_relevance"]   >= THRESHOLDS["answer_relevance"]
        and scores["hallucination_risk"] <= THRESHOLDS["hallucination_risk"]
    )


# ─── Prompts ──────────────────────────────────────────────────────


EVAL_SYSTEM = """You are an evaluator for a RAG system that answers \
questions about SEC filings (10-K and 10-Q reports).

You score the system's answer on three dimensions. Be honest -- the \
goal is to catch hallucinations and irrelevant answers, not to flatter \
the system.

Rules:
- Compare the ANSWER strictly against the SOURCES. Treat sources as \
ground truth.
- Citations like [1] / [2] in the answer refer to the numbered SOURCES.
- If the answer says "the source doesn't disclose X" and that's actually \
true (no source contains X), that's a HIGH-faithfulness, LOW-hallucination \
answer -- not a failure.
- Penalize fabricated numbers, dates, or facts that don't appear in the \
cited sources.
- Reasoning should be 1-3 sentences citing specific evidence.

Output JSON only -- no prose."""


_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "eval_scores",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "faithfulness": {
                    "type": "number",
                    "description": "0.0 (worst) to 1.0 (best). How grounded is the answer in the sources?",
                },
                "answer_relevance": {
                    "type": "number",
                    "description": "0.0 to 1.0. How directly does the answer address the question?",
                },
                "hallucination_risk": {
                    "type": "number",
                    "description": "0.0 (no risk) to 1.0 (high risk). Probability that the answer contains unsupported claims.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "1-3 sentences citing specific evidence.",
                },
            },
            "required": [
                "faithfulness",
                "answer_relevance",
                "hallucination_risk",
                "reasoning",
            ],
            "additionalProperties": False,
        },
    },
}


def _build_eval_user_prompt(
    query: str, hits: list[Any], answer: str
) -> str:
    parts: list[str] = ["SOURCES", ""]
    for i, h in enumerate(hits, start=1):
        header = (
            f"[{i}] {h.ticker} {h.filing_type} "
            f"(period {h.period_of_report}, chunk #{h.chunk_index})"
        )
        parts.append(header)
        text = h.text.strip()
        if len(text) > 1800:
            text = text[:1800] + "..."
        parts.append(text)
        parts.append("")
    parts.append(f"USER QUESTION: {query.strip()}")
    parts.append("")
    parts.append(f"ANSWER PRODUCED BY THE SYSTEM:\n{answer.strip()}")
    return "\n".join(parts)


# ─── Evaluation ───────────────────────────────────────────────────

# Reuse one async OpenAI client across requests.
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def evaluate(
    query: str,
    hits: list[Any],
    answer: str,
    *,
    model: str | None = None,
) -> EvalResult:
    """Score an answer with LLM-as-judge. Returns an EvalResult."""
    if not hits or not answer.strip():
        # Nothing to evaluate -- gates fail trivially.
        return EvalResult(
            faithfulness=0.0,
            answer_relevance=0.0,
            hallucination_risk=1.0,
            reasoning="No sources or empty answer.",
            gates_passed=False,
            evaluator_model=model or settings.generator_model,
        )

    model = model or settings.generator_model
    user_prompt = _build_eval_user_prompt(query, hits, answer)

    client = _get_client()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EVAL_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        response_format=_RESPONSE_SCHEMA,
        temperature=0.0,
        max_tokens=400,
    )

    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        log.error("eval.bad_json", content=content, error=str(exc))
        # Defensive default if the model somehow ignored the schema.
        data = {
            "faithfulness": 0.0,
            "answer_relevance": 0.0,
            "hallucination_risk": 1.0,
            "reasoning": f"evaluator output was unparseable: {exc}",
        }

    # Clamp to [0, 1] in case the model returns an out-of-range value.
    scores = {
        k: max(0.0, min(1.0, float(data.get(k, 0.0))))
        for k in ("faithfulness", "answer_relevance", "hallucination_risk")
    }

    return EvalResult(
        faithfulness=scores["faithfulness"],
        answer_relevance=scores["answer_relevance"],
        hallucination_risk=scores["hallucination_risk"],
        reasoning=str(data.get("reasoning", ""))[:1000],
        gates_passed=_passed(scores),
        evaluator_model=model,
        tokens_in=(resp.usage.prompt_tokens if resp.usage else 0) or 0,
        tokens_out=(resp.usage.completion_tokens if resp.usage else 0) or 0,
    )


# ─── Persistence ──────────────────────────────────────────────────


async def persist_eval(query_id: int, result: EvalResult) -> None:
    pool = await db.init_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO eval_scores (
                query_id, faithfulness, answer_relevance,
                hallucination_risk, gates_passed,
                evaluator_model, evaluated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (query_id) DO UPDATE SET
                faithfulness       = EXCLUDED.faithfulness,
                answer_relevance   = EXCLUDED.answer_relevance,
                hallucination_risk = EXCLUDED.hallucination_risk,
                gates_passed       = EXCLUDED.gates_passed,
                evaluator_model    = EXCLUDED.evaluator_model,
                evaluated_at       = NOW()
            """,
            query_id,
            result.faithfulness,
            result.answer_relevance,
            result.hallucination_risk,
            result.gates_passed,
            result.evaluator_model,
        )
