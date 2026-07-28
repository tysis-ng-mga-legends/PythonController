class QoSManager:

    def apply_policy(self, metadata: dict, predicted_class: str):
        src_ip = metadata.get("SrcIP")
        dst_ip = metadata.get("DstIP")
        src_port = metadata.get("SrcPort")
        dst_port = metadata.get("DstPort")
        proto = metadata.get("Protocol")

        flow_tuple = f"{src_ip}:{src_port} -> {dst_ip}:{dst_port} ({proto})"
        print(f"[PREDICTION] Flow {flow_tuple} | Category: {predicted_class}")
