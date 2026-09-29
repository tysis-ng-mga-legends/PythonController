import logging
from pathlib import Path
from typing import Any, Dict
import joblib
import pandas as pd
from src.feature_mapper import FEATURE_NAMES


class TrafficPredictor:

    def __init__(self, model_file: Path) -> None:
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found at: {model_file}")

        self.model = joblib.load(model_file)

        # Read feature names saved inside the model, with a fallback to mapper names
        if hasattr(self.model, "feature_names_in_"):
            self.feature_names = list(self.model.feature_names_in_)
        else:
            self.feature_names = FEATURE_NAMES

        logging.info(
            f"[PREDICTOR] Loaded model from {model_file.name} with {len(self.feature_names)} named features."
        )

    def predict(self, mapped_features: Dict[str, float]) -> str:
        # Create a single-row DataFrame using the model's exact column headers
        df = pd.DataFrame([mapped_features])[self.feature_names]

        # Directly outputs class string ('Bulk-Transfer', 'Multimedia-Streaming', etc.)
        predicted_label = self.model.predict(df)[0]
        return str(predicted_label)
