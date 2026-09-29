import ipaddress
import logging
import shutil
import subprocess
from typing import Any, Dict, Set, Tuple

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

CLASS_MAPPING = {
    "real-time-interactive": "1:10",
    "multimedia-streaming": "1:20",
    "bulk-transfer": "1:30",
}


class QoSManager:

    def __init__(
        self,
        lan_interface: str = "wlan0",
        wan_interface: str = "wg0",
        # wan_interface: str = "eth0" // placeholder if there's no wireguard
        down_total: str = "45mbit",
        down_rt: str = "10mbit",
        down_mm: str = "25mbit",
        down_bulk: str = "10mbit",
        up_total: str = "40mbit",
        up_rt: str = "10mbit",
        up_mm: str = "20mbit",
        up_bulk: str = "10mbit",
    ) -> None:
        self.lan_interface = lan_interface
        self.wan_interface = wan_interface
        self.applied_flows: Set[str] = set()

        if not shutil.which("tc"):
            raise EnvironmentError("'tc' binary not found. Install iproute2.")

        # Initialize Download hierarchy on LAN
        self.init_qdisc_tree(lan_interface, down_total, down_rt, down_mm, down_bulk)
        # Initialize Upload hierarchy on WAN
        self.init_qdisc_tree(wan_interface, up_total, up_rt, up_mm, up_bulk)

    def _run_cmd(self, cmd: list[str], check: bool = True) -> bool:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if check and res.returncode != 0:
            logging.error(
                f"tc command failed: {' '.join(cmd)}\nError: {res.stderr.strip()}"
            )
            return False
        return True

    def init_qdisc_tree(
        self,
        iface: str,
        total_rate: str,
        rt_rate: str,
        mm_rate: str,
        bulk_rate: str,
    ) -> None:
        """Sets up the HTB root, classes, and SFQ leaves on an interface."""
        logging.info(f"Configuring HTB QoS tree on {iface} (Ceiling: {total_rate})...")

        self._run_cmd(["tc", "qdisc", "del", "dev", iface, "root"], check=False)

        # 1. Root HTB qdisc
        self._run_cmd(
            [
                "tc",
                "qdisc",
                "add",
                "dev",
                iface,
                "root",
                "handle",
                "1:",
                "htb",
                "default",
                "30",
            ]
        )

        # 2. Parent class (1:1)
        self._run_cmd(
            [
                "tc",
                "class",
                "add",
                "dev",
                iface,
                "parent",
                "1:",
                "classid",
                "1:1",
                "htb",
                "rate",
                total_rate,
                "ceil",
                total_rate,
            ]
        )

        # 3. Class 1:10 -> Real-Time (Priority 1)
        self._run_cmd(
            [
                "tc",
                "class",
                "add",
                "dev",
                iface,
                "parent",
                "1:1",
                "classid",
                "1:10",
                "htb",
                "rate",
                rt_rate,
                "ceil",
                total_rate,
                "prio",
                "1",
            ]
        )
        self._run_cmd(
            [
                "tc",
                "qdisc",
                "add",
                "dev",
                iface,
                "parent",
                "1:10",
                "handle",
                "10:",
                "sfq",
                "perturb",
                "10",
            ]
        )

        # 4. Class 1:20 -> Multimedia (Priority 2)
        self._run_cmd(
            [
                "tc",
                "class",
                "add",
                "dev",
                iface,
                "parent",
                "1:1",
                "classid",
                "1:20",
                "htb",
                "rate",
                mm_rate,
                "ceil",
                total_rate,
                "prio",
                "2",
            ]
        )
        self._run_cmd(
            [
                "tc",
                "qdisc",
                "add",
                "dev",
                iface,
                "parent",
                "1:20",
                "handle",
                "20:",
                "sfq",
                "perturb",
                "10",
            ]
        )

        # 5. Class 1:30 -> Bulk (Priority 3)
        self._run_cmd(
            [
                "tc",
                "class",
                "add",
                "dev",
                iface,
                "parent",
                "1:1",
                "classid",
                "1:30",
                "htb",
                "rate",
                bulk_rate,
                "ceil",
                total_rate,
                "prio",
                "3",
            ]
        )
        self._run_cmd(
            [
                "tc",
                "qdisc",
                "add",
                "dev",
                iface,
                "parent",
                "1:30",
                "handle",
                "30:",
                "sfq",
                "perturb",
                "10",
            ]
        )

        logging.info(f"[✓] Interface {iface} initialized successfully.")

    def _resolve_classid(self, predicted_class: str) -> str:
        key = predicted_class.strip().lower()
        for pattern, class_id in CLASS_MAPPING.items():
            if pattern in key:
                return class_id
        return "1:30"

    def _separate_endpoints(
        self, src_str: str, dst_str: str, src_port: int, dst_port: int
    ) -> Tuple[Tuple[Any, int], Tuple[Any, int]]:
        """Identifies which endpoint is the local client vs remote server."""
        src_ip = ipaddress.ip_address(src_str)
        dst_ip = ipaddress.ip_address(dst_str)

        local_v4_net = ipaddress.ip_network("10.42.0.0/24")

        is_src_client = (
            src_ip.is_private
            or src_ip.is_link_local
            or (src_ip.version == 4 and src_ip in local_v4_net)
        )

        if is_src_client:
            return (src_ip, src_port), (dst_ip, dst_port)
        return (dst_ip, dst_port), (src_ip, src_port)

    def _build_5tuple_filter(
        self,
        iface: str,
        src_ip: Any,
        src_port: int,
        dst_ip: Any,
        dst_port: int,
        target_class: str,
        proto_num: str,
    ) -> list[str]:
        """Constructs a strict 5-tuple u32 filter matching both endpoints and layer-4 ports."""
        is_v4 = src_ip.version == 4
        proto_flag = "ip" if is_v4 else "ipv6"
        match_proto = "ip" if is_v4 else "ip6"
        mask = "32" if is_v4 else "128"

        cmd = [
            "tc",
            "filter",
            "add",
            "dev",
            iface,
            "protocol",
            proto_flag,
            "parent",
            "1:0",
            "prio",
            "1",
            "u32",
        ]

        if proto_num:
            cmd.extend(["match", match_proto, "protocol", proto_num, "0xff"])

        # Strict 5-tuple matches
        cmd.extend(
            [
                "match",
                match_proto,
                "src",
                f"{src_ip}/{mask}",
                "match",
                match_proto,
                "sport",
                str(src_port),
                "0xffff",
                "match",
                match_proto,
                "dst",
                f"{dst_ip}/{mask}",
                "match",
                match_proto,
                "dport",
                str(dst_port),
                "0xffff",
                "flowid",
                target_class,
            ]
        )
        return cmd

    def apply_policy(self, metadata: Dict[str, Any], predicted_class: str) -> None:
        src_str = metadata.get("SrcIP", "")
        dst_str = metadata.get("DstIP", "")
        src_port = int(metadata.get("SrcPort", 0))
        dst_port = int(metadata.get("DstPort", 0))
        proto = str(metadata.get("Protocol", "")).upper()

        try:
            (client_ip, client_port), (server_ip, server_port) = (
                self._separate_endpoints(src_str, dst_str, src_port, dst_port)
            )
        except ValueError:
            logging.error(f"[QoS] Invalid IP address in flow: {src_str} or {dst_str}")
            return

        # Canonical flow key prevents duplicate rules
        flow_key = f"{client_ip}:{client_port}<->{server_ip}:{server_port}-{proto}"
        if flow_key in self.applied_flows:
            return

        target_class = self._resolve_classid(predicted_class)
        proto_num = (
            "6" if proto in ("TCP", "TLS") else "17" if proto in ("UDP", "QUIC") else ""
        )

        logging.info(
            f"[QoS 5-TUPLE] Enforcing {predicted_class} -> Class {target_class}\n"
            f"   Client: {client_ip}:{client_port} | Server: {server_ip}:{server_port} ({proto})"
        )

        # 1. Download filter on wlan0 (Packets moving Server -> Client)
        lan_cmd = self._build_5tuple_filter(
            iface=self.lan_interface,
            src_ip=server_ip,
            src_port=server_port,
            dst_ip=client_ip,
            dst_port=client_port,
            target_class=target_class,
            proto_num=proto_num,
        )
        lan_ok = self._run_cmd(lan_cmd, check=False)

        # 2. Upload filter on WAN/wg0 (Packets moving Client -> Server)
        wan_cmd = self._build_5tuple_filter(
            iface=self.wan_interface,
            src_ip=client_ip,
            src_port=client_port,
            dst_ip=server_ip,
            dst_port=server_port,
            target_class=target_class,
            proto_num=proto_num,
        )
        wan_ok = self._run_cmd(wan_cmd, check=False)

        if lan_ok or wan_ok:
            self.applied_flows.add(flow_key)

    def teardown(self) -> None:
        """Removes root qdiscs on both interfaces."""
        logging.info("Cleaning up QoS hierarchies across both interfaces...")
        self._run_cmd(
            ["tc", "qdisc", "del", "dev", self.lan_interface, "root"],
            check=False,
        )
        self._run_cmd(
            ["tc", "qdisc", "del", "dev", self.wan_interface, "root"],
            check=False,
        )
