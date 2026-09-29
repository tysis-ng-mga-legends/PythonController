import logging
import os
import signal
import sys
from pathlib import Path

from src import feature_mapper
from src.predictor import TrafficPredictor
from src.qos_manager import QoSManager
from src.receiver import listen_flows

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def check_privileges() -> None:
    """Linux TC requires root / CAP_NET_ADMIN privileges."""
    if os.geteuid() != 0:
        logging.error("Controller must be run with sudo to manipulate TC.")
        sys.exit(1)


def main() -> None:
    check_privileges()

    model_dir = Path(__file__).parent / "models"
    predictor = TrafficPredictor(model_dir)
    qos = QoSManager()

    # Clean up kernel qdiscs on Ctrl+C or termination
    def shutdown(sig, frame):
        logging.info("Shutting down controller and clearing TC qdiscs...")
        qos.teardown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logging.info("[CONTROLLER] Pipeline active. Waiting for Go flow engine...")

    try:
        for raw_payload in listen_flows():
            features_raw = raw_payload.get("features")
            flow_id = raw_payload.get("flow_id")

            if not features_raw or not flow_id:
                continue

            try:
                # 1. Map Go PascalCase keys to model features
                features = feature_mapper.case_translator(features_raw)

                # Fallback: ensure proto_UDP exists if omitted in Go features
                if "proto_UDP" not in features:
                    is_udp = str(flow_id.get("Protocol", "")).upper() == "UDP"
                    features["proto_UDP"] = 1 if is_udp else 0

                # 2. ML Inference
                predicted_class = predictor.predict(features)

                # 3. Kernel QoS enforcement on wlan0
                qos.apply_policy(flow_id, predicted_class)

            except Exception as err:
                logging.warning(
                    f"Skipping malformed flow {flow_id.get('SrcIP')}: {err}"
                )
                continue

    except Exception as fatal_err:
        logging.critical(f"Fatal error in listener: {fatal_err}")
    finally:
        qos.teardown()


if __name__ == "__main__":
    main()
