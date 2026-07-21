import zmq
import time


def start_receiver():
    context = zmq.Context()
    receiver = context.socket(zmq.PULL)

    receiver.bind("ipc:///tmp/flow_pipeline.ipc")
    print("[Recieving Network Flows")

    while True:
        # Pull the raw message from the queue (blocking call)
        message = receiver.recv_string()
        print(f"Received Feature Vector: {message}")

        # This is where your ML inference model will process the vector!
        time.sleep(0.01)
