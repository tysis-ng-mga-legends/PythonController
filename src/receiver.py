import zmq
import time
import json
from typing import Dict, Any, Generator


def listen_flows(
    ipc_path: str = "ipc:///tmp/flow_pipeline.ipc",
) -> Generator[Dict[str, Any], None, None]:
    context = zmq.Context()
    receiver = context.socket(zmq.PULL)

    receiver.bind(ipc_path)
    print("[Recieving Network Flows]")

    while True:

        message = receiver.recv_string()
        try:
            feature_dict = json.loads(message)
            yield feature_dict
        except json.JSONDecodeError as err:
            print(f"[RECEIVER ERROR] Invalid JSON payload: {err}")
