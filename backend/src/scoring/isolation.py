"""
Anomaly detection via Isolation Forest.

Trained on a batch of listings, then used to flag statistical outliers.
Falls back to a neutral score before fitting so the pipeline doesn't
crash on fresh data.
"""
from dataclasses import dataclass

import numpy as np
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
        "source": "isolation_forest",
    }


def _extract_features(listing) -> list[float]:
    """Extract numerical features from a Listing for the model.
    
    Every feature must be a number — strings can't go through sklearn.
    Field names match our Listing SQLAlchemy model.
    """
    description = getattr(listing, "description", "") or ""
    heading = getattr(listing, "heading", "") or ""
    price = float(getattr(listing, "price", 0) or 0)
    image_urls = getattr(listing, "image_urls", []) or []
    
    return [
        price,
        float(len(description)),
        float(len(image_urls)),
        float(len(heading)),
        float(1 if getattr(listing, "location", None) else 0),
        float(1 if getattr(listing, "seller_type", None) == "company" else 0),
    ]


class AnomalyDetector:
    """Wrapper around sklearn's Isolation Forest."""
    
    def __init__(self, contamination: float = 0.1):
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100,
        )
        self.is_fitted = False
    
    def fit(self, listings: list) -> None:
        """Train on a list of listings. Call once with 10+ listings."""
        if len(listings) < 10:
            print("Warning: fewer than 10 listings to train on, skipping fit.")
            return
        
        features = [_extract_features(l) for l in listings]
        X = np.array(features)
        self.model.fit(X)
        self.is_fitted = True
        print(f"Isolation Forest fitted on {len(listings)} listings.")
    
    def score_ad(self, listing) -> IsolationResult:
        """Score one listing. Returns neutral 0.5 if not fitted yet."""
        if not self.is_fitted:
            return IsolationResult(
                score=0.5,
                is_anomaly=False,
                reasons=[_make_reason(
                    "Anomalidetektion ej aktiv ännu (för lite data)",
                    "warning",
                )],
            )
        
        features = np.array([_extract_features(listing)])
        raw_score = self.model.score_samples(features)[0]
        prediction = self.model.predict(features)[0]
        
        normalized = float(np.clip((raw_score + 0.5) / 1.0, 0.0, 1.0))
        is_anomaly = prediction == -1
        
        reasons = []
        if is_anomaly:
            reasons.append(_make_reason(
                "Annonsen avviker statistiskt från normala annonser",
                "negative",
            ))
        else:
            reasons.append(_make_reason(
                "Annonsen liknar normala annonser statistiskt",
                "positive",
            ))
        
        return IsolationResult(
            score=normalized,
            is_anomaly=is_anomaly,
            reasons=reasons,
        )


# Singleton — imported across the app
detector = AnomalyDetector(contamination=0.1)