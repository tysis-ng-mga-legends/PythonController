from pathlib import Path
from typing import Dict, Any
import joblib
import pandas as pd


class TrafficPredictor:

    def __init__(self, model_dir: Path) -> None:
        self.model = joblib.load(model_dir / "rf_baseline_model_n7.pkl")
        self.scaler = joblib.load(model_dir / "scaler_n7.pkl")
        self.label_encoder = joblib.load(model_dir / "label_encoder_n7.pkl")
        self.feature_columns = joblib.load(model_dir / "feature_columns_n7.pkl")

    def predict(self, mapped_features: Dict[str, Any]) -> str:
        df = pd.DataFrame([mapped_features])[self.feature_columns]

        # Scale and predict
        scaled = self.scaler.transform(df)
        numeric_pred = self.model.predict(scaled)

        # Map integer prediction back to class string
        label = self.label_encoder.inverse_transform(numeric_pred)[0]
        return str(label)
