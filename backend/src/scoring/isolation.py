import numpy as np
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest


@dataclass
class IsolationResult:
    score: float        # 0.0-1.0
    is_anomaly: bool
    reasons: list[dict]


def _make_reason(reason: str, flag_type: str) -> dict:
    return {
        "reason": reason,
        "flag_type": flag_type,
        "source": "isolation_forest"
    }


def _extract_features(ad) -> list[float]:
    """
    Extract numerical features from an ad for the Isolation Forest.
    Every feature must be a number — no strings.
    """
    body = getattr(ad, "body", "") or ""
    price = getattr(ad, "price", 0) or 0
    image_count = len(getattr(ad, "images", []) or [])

    return [
        float(price),
        float(len(body)),
        float(image_count),
        float(len(getattr(ad, "subject", "") or "")),
        float(1 if getattr(ad, "location", None) else 0),
        float(1 if getattr(ad, "store", None) else 0),
    ]


class AnomalyDetector:
    """
    Wrapper around sklearn's Isolation Forest.
    Must be fitted on a batch of ads before scoring individual ones.
    """

    def __init__(self, contamination: float = 0.1):
        """
        contamination = expected proportion of anomalies in the data.
        0.1 means we expect ~10% of ads to be suspicious.
        """
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.is_fitted = False

    def fit(self, ads: list) -> None:
        """
        Train the model on a list of ads.
        Call this once you have enough ads in the DB (50+ recommended).
        """
        if len(ads) < 10:
            print("Warning: fewer than 10 ads to train on, skipping fit.")
            return

        features = [_extract_features(ad) for ad in ads]
        X = np.array(features)
        self.model.fit(X)
        self.is_fitted = True
        print(f"Isolation Forest fitted on {len(ads)} ads.")

    def score_ad(self, ad) -> IsolationResult:
        """
        Score a single ad. Returns IsolationResult with 0.0-1.0 score.
        Falls back to neutral 0.5 if model hasn't been fitted yet.
        """
        if not self.is_fitted:
            return IsolationResult(
                score=0.5,
                is_anomaly=False,
                reasons=[_make_reason(
                    "Anomalidetektion ej aktiv ännu (för lite data)",
                    "warning"
                )]
            )

        features = np.array([_extract_features(ad)])

        # Raw score: negative = more anomalous, positive = more normal
        raw_score = self.model.score_samples(features)[0]
        prediction = self.model.predict(features)[0]  # -1 = anomaly, 1 = normal

        # Convert raw score to 0.0-1.0
        # Typical range is roughly -0.5 to 0.5
        normalized = float(np.clip((raw_score + 0.5) / 1.0, 0.0, 1.0))
        is_anomaly = prediction == -1

        reasons = []
        if is_anomaly:
            reasons.append(_make_reason(
                "Annonsen avviker statistiskt från normala annonser",
                "negative"
            ))
        else:
            reasons.append(_make_reason(
                "Annonsen liknar normala annonser statistiskt",
                "positive"
            ))

        return IsolationResult(
            score=normalized,
            is_anomaly=is_anomaly,
            reasons=reasons
        )


# Singleton instance — imported and used across the app
detector = AnomalyDetector(contamination=0.1)