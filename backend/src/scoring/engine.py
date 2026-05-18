from src.scoring.rules import score_rules, RuleResult
from src.scoring.isolation import detector, IsolationResult
from dataclasses import dataclass


@dataclass
class ScoreOutput:
    score: int
    is_suspicious: bool
    rule_score: float
    isolation_score: float
    llm_score: float
    reasons: list[dict]


WEIGHTS = {
    "rules":     1.0,   # 100% until isolation forest is trained
    "isolation": 0.0,   # inactive until detector.fit() is called
    "llm":       0.0,   # inactive until Claude is integrated
}

SUSPICIOUS_THRESHOLD = 4


def _normalize_to_scale(score: float) -> int:
    return max(1, min(10, round(score * 9) + 1))


def score_ad(ad) -> ScoreOutput:
    # ── Layer 1: Rules ────────────────────────────────────────
    rule_result: RuleResult = score_rules(ad)
    rule_score = rule_result.score
    all_reasons = list(rule_result.reasons)

    # ── Layer 2: Isolation Forest ─────────────────────────────
    isolation_result: IsolationResult = detector.score_ad(ad)
    isolation_score = isolation_result.score
    all_reasons += isolation_result.reasons

    # ── Layer 3: LLM (placeholder) ────────────────────────────
    llm_score = 0.0

    # ── Combine ───────────────────────────────────────────────
    combined = (
        rule_score      * WEIGHTS["rules"] +
        isolation_score * WEIGHTS["isolation"] +
        llm_score       * WEIGHTS["llm"]
    )

    final_score = _normalize_to_scale(combined)
    is_suspicious = final_score <= SUSPICIOUS_THRESHOLD

    return ScoreOutput(
        score=final_score,
        is_suspicious=is_suspicious,
        rule_score=rule_score,
        isolation_score=isolation_score,
        llm_score=llm_score,
        reasons=all_reasons
    )