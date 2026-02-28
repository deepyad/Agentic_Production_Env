#!/usr/bin/env python3
"""
RAGAS evaluation script for the agentic RAG pipeline.

Runs offline / in CI: loads (question, contexts, answer) samples, computes
faithfulness, answer relevancy, and optional context recall. Not used on the
request path. Requires OPENAI_API_KEY for the evaluator LLM.

Usage:
  python scripts/eval_ragas.py
  python scripts/eval_ragas.py --data path/to/samples.json
  python scripts/eval_ragas.py --output results.json

See Documentation/RAGAS_AND_FAITHFULNESS.md for where RAGAS sits in the project.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root for imports if running from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _get_sample_dataset() -> list[dict]:
    """Minimal in-repo sample dataset (support/billing style) for a quick run."""
    return [
        {
            "user_input": "What is the refund policy?",
            "retrieved_contexts": [
                "Refunds are allowed within 30 days of purchase. No exceptions after 30 days."
            ],
            "response": "Refunds are allowed within 30 days of purchase.",
            "reference": "Refunds are allowed within 30 days of purchase.",
        },
        {
            "user_input": "What was my last invoice total?",
            "retrieved_contexts": [
                "Invoice #1001 dated 2024-01-15. Total: $250.00. Due in 30 days."
            ],
            "response": "Your last invoice total was $250.00.",
            "reference": "The last invoice total is $250.00.",
        },
        {
            "user_input": "Can I get a refund after 60 days?",
            "retrieved_contexts": [
                "Refunds are allowed within 30 days of purchase. No exceptions after 30 days."
            ],
            "response": "Refunds are only allowed within 30 days. After 60 days we cannot process a refund.",
            "reference": "No. Refunds are only within 30 days.",
        },
    ]


def load_dataset_from_json(path: str) -> list[dict]:
    """Load evaluation samples from a JSON file.

    Expected format: list of objects with keys user_input, retrieved_contexts (list of str),
    response, and optionally reference.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    for i, row in enumerate(data):
        if "user_input" not in row or "retrieved_contexts" not in row or "response" not in row:
            raise ValueError(
                f"Row {i}: each sample must have user_input, retrieved_contexts, response."
            )
        if isinstance(row["retrieved_contexts"], str):
            row["retrieved_contexts"] = [row["retrieved_contexts"]]
    return data


def run_evaluation(
    dataset_list: list[dict],
    evaluator_model: str = "gpt-4o-mini",
    metrics_only: tuple[str, ...] = ("faithfulness", "answer_relevancy"),
) -> dict:
    """Run RAGAS evaluate() on the dataset. Returns dict of metric name -> score."""
    try:
        from ragas import EvaluationDataset, evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas import metrics as ragas_metrics
    except ImportError as e:
        print("RAGAS is not installed. Run: pip install ragas", file=sys.stderr)
        raise SystemExit(1) from e

    # Metric class names can differ by ragas version (Faithfulness, AnswerRelevancy or ResponseRelevancy)
    FaithfulnessCls = getattr(ragas_metrics, "Faithfulness", None)
    AnswerRelevancyCls = getattr(ragas_metrics, "AnswerRelevancy", None) or getattr(
        ragas_metrics, "ResponseRelevancy", None
    )
    if not FaithfulnessCls:
        raise SystemExit(1)  # ragas should provide Faithfulness

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required for RAGAS evaluator LLM.", file=sys.stderr)
        raise SystemExit(1)

    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    llm = ChatOpenAI(model=evaluator_model, temperature=0)
    evaluator_llm = LangchainLLMWrapper(llm)
    embeddings = OpenAIEmbeddings()

    evaluation_dataset = EvaluationDataset.from_list(dataset_list)

    metrics = []
    if "faithfulness" in metrics_only:
        metrics.append(FaithfulnessCls())
    if "answer_relevancy" in metrics_only and AnswerRelevancyCls:
        metrics.append(AnswerRelevancyCls())

    if not metrics:
        metrics = [FaithfulnessCls()]
        if AnswerRelevancyCls:
            metrics.append(AnswerRelevancyCls())

    eval_kw: dict = {
        "dataset": evaluation_dataset,
        "metrics": metrics,
        "llm": evaluator_llm,
    }
    if embeddings is not None:
        eval_kw["embeddings"] = embeddings

    result = evaluate(**eval_kw)

    # Result is EvaluationResult; extract scores (structure may vary by ragas version)
    out = {}
    if hasattr(result, "scores") and result.scores is not None:
        if hasattr(result.scores, "to_dict"):
            out = result.scores.to_dict()
        elif isinstance(result.scores, dict):
            out = result.scores
        else:
            out = {"result": str(result.scores)}
    if hasattr(result, "to_pandas") and result.to_pandas() is not None:
        df = result.to_pandas()
        if not df.empty and "faithfulness" in df.columns:
            out["faithfulness"] = float(df["faithfulness"].mean())
        if not df.empty and "answer_relevancy" in df.columns:
            out["answer_relevancy"] = float(df["answer_relevancy"].mean())
    return out if out else {"raw": str(result)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAGAS evaluation on RAG samples (offline/CI)."
    )
    parser.add_argument(
        "--data",
        type=str,
        default="",
        help="Path to JSON file with samples (user_input, retrieved_contexts, response, reference). Default: use built-in sample.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Write results to this JSON file. Default: print to stdout.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="Evaluator LLM model (default: gpt-4o-mini).",
    )
    args = parser.parse_args()

    if args.data:
        dataset_list = load_dataset_from_json(args.data)
        print(f"Loaded {len(dataset_list)} samples from {args.data}", file=sys.stderr)
    else:
        dataset_list = _get_sample_dataset()
        print("Using built-in sample dataset (3 samples).", file=sys.stderr)

    scores = run_evaluation(dataset_list, evaluator_model=args.model)
    out_text = json.dumps(scores, indent=2)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"Wrote results to {args.output}", file=sys.stderr)
    else:
        print(out_text)


if __name__ == "__main__":
    main()
