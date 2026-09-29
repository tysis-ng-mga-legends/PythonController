import csv
import logging
import os
import signal
import sys
import time
from pathlib import Path

from src.feature_mapper import map_features
from src.predictor import TrafficPredictor
from src.qos_manager import QoSManager
from src.receiver import listen_flows

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

CSV_LOG_PATH = Path("qos_telemetry_benchmarks.csv")


def init_csv_log() -> None:
    if not CSV_LOG_PATH.exists():
        with open(CSV_LOG_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "flow_id",
                    "predicted_class",
                    "t_window_us",
                    "t_extract_us",
                    "t_ipc_us",
                    "t_infer_us",
                    "t_kernel_us",
                    "t_total_us",
                ]
            )


def main() -> None:
    if os.geteuid() != 0:
        logging.error("Controller must be run with sudo.")
        sys.exit(1)

    init_csv_log()

    wan_iface = os.environ.get("GATEWAY_WAN_IFACE", "wlan0")
    model_path = Path(__file__).parent / "models" / "rf_model.joblib"
    predictor = TrafficPredictor(model_path)
    qos = QoSManager(lan_interface="wlan0", wan_interface=wan_iface)

    def shutdown(sig, frame):
        logging.info("Shutting down QoS engine...")
        qos.teardown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logging.info("[READY] Controller listening for flows from Go...")

    try:
        for raw_payload in listen_flows():
            t_py_recv_us = int(time.time() * 1e6)

            features_raw = raw_payload.get("features")
            flow_id = raw_payload.get("flow_id")
            telemetry = raw_payload.get("telemetry", {})

            if not features_raw or not flow_id:
                continue

            try:
                # 1. Feature Vector Extraction
                mapped_features = map_features(features_raw)

                # 2. Measure T_infer
                t_infer_start = time.perf_counter_ns()
                predicted_class = predictor.predict(mapped_features)
                t_infer_us = (time.perf_counter_ns() - t_infer_start) / 1000.0

                # 3. Measure T_kernel
                t_kernel_start = time.perf_counter_ns()
                enforced = qos.apply_policy(flow_id, predicted_class)
                t_kernel_us = (time.perf_counter_ns() - t_kernel_start) / 1000.0

                if not enforced:
                    continue

                # 4. Telemetry Calculation
                t_window_us = telemetry.get("t_window_us", 0)
                t_extract_us = telemetry.get("t_extract_us", 0)
                t_go_send_us = telemetry.get("t_go_send_us", t_py_recv_us)
                t_ipc_us = max(0, t_py_recv_us - t_go_send_us)

                t_total_us = (
                    t_window_us + t_extract_us + t_ipc_us + t_infer_us + t_kernel_us
                )

                flow_str = f"{flow_id.get('SrcIP')}:{flow_id.get('SrcPort')} <-> {flow_id.get('DstIP')}:{flow_id.get('DstPort')}"
                logging.info(
                    f"\n[BENCHMARK] {flow_str} -> {predicted_class}\n"
                    f"  ├─ T_window  : {t_window_us:>8.2f} µs ({t_window_us/1000:.2f} ms)\n"
                    f"  ├─ T_extract : {t_extract_us:>8.2f} µs ({t_extract_us/1000:.2f} ms)\n"
                    f"  ├─ T_ipc     : {t_ipc_us:>8.2f} µs ({t_ipc_us/1000:.2f} ms)\n"
                    f"  ├─ T_infer   : {t_infer_us:>8.2f} µs ({t_infer_us/1000:.2f} ms)\n"
                    f"  ├─ T_kernel  : {t_kernel_us:>8.2f} µs ({t_kernel_us/1000:.2f} ms)\n"
                    f"  └─ T_total   : {t_total_us:>8.2f} µs ({t_total_us/1000:.2f} ms)"
                )

                # Persist metrics for thesis evaluation graphs
                with open(CSV_LOG_PATH, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            flow_str,
                            predicted_class,
                            t_window_us,
                            t_extract_us,
                            t_ipc_us,
                            round(t_infer_us, 2),
                            round(t_kernel_us, 2),
                            round(t_total_us, 2),
                        ]
                    )

            except Exception as err:
                logging.warning(f"Error handling flow: {err}")
                continue

    except Exception as fatal:
        logging.critical(f"Pipeline crashed: {fatal}")
    finally:
        qos.teardown()


if __name__ == "__main__":
    main()
