"""Accuracy of the qualification step on a labeled set of posts (precision / recall / F1)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .agent import qualify
from .llm import LLM
from .models import ICP, Signal


@dataclass
class EvalResult:
    total: int
    judged: int
    tp: int
    fp: int
    fn: int
    tn: int
    intent_correct: int
    mistakes: list[dict]

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def load_dataset(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(dataset: list[dict], icp: ICP, llm: LLM) -> EvalResult:
    signals = [
        Signal(id=d["id"], source="eval", url="", title=d.get("title", ""), text=d["text"]) for d in dataset
    ]
    judged = {q.id: q for q in qualify(signals, icp, llm)}
    tp = fp = fn = tn = intent_ok = 0
    mistakes: list[dict] = []
    for d in dataset:
        q = judged.get(d["id"])
        predicted = bool(q and q.intent.value != "not_relevant" and q.fit_score >= icp.min_score)
        expected = bool(d["is_lead"])
        if q and d.get("intent") and q.intent.value == d["intent"]:
            intent_ok += 1
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
        elif expected:
            fn += 1
        else:
            tn += 1
        if predicted != expected:
            mistakes.append(
                {
                    "id": d["id"],
                    "expected": expected,
                    "score": q.fit_score if q else None,
                    "intent": q.intent.value if q else None,
                }
            )
    return EvalResult(len(dataset), len(judged), tp, fp, fn, tn, intent_ok, mistakes)
