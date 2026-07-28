from pathlib import Path
from src import feature_mapper
from src.predictor import TrafficPredictor
from src.receiver import listen_flows
from src.qos_manager import QoSManager


def process_flow():
    model_dir = Path(__file__).parent / "models"
    predictor = TrafficPredictor(model_dir)

    qos = QoSManager()

    # Iterating over the generator keeps the receiver loop alive continuously
    for raw_payload in listen_flows():
        # Separate features from metadata if bundled together or handle dict
        features = feature_mapper.case_translator(raw_payload["features"])
        predicted_class = predictor.predict(features)

        qos.apply_policy(raw_payload["flow_id"], predicted_class)


if __name__ == "__main__":
    process_flow()
