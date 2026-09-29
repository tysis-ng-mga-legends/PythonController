import ipaddress
import logging
import shutil
import subprocess
from typing import Any, Dict, Set, Tuple

CLASS_MAPPING = {
    "real-time-interactive": "1:10",
    "multimedia-streaming": "1:20",
    "bulk-transfer": "1:30",
}


class QoSManager:

    def __init__(
        self,
        lan_interface: str = "wlan0",
        # wan_interface: str = "wg0",
        wan_interface: str = "wlan0",
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

        self.init_qdisc_tree(lan_interface, down_total, down_rt, down_mm, down_bulk)
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
        self._run_cmd(["tc", "qdisc", "del", "dev", iface, "root"], check=False)
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

    def _resolve_classid(self, predicted_class: str) -> str:
        key = predicted_class.strip().lower()
        for pattern, class_id in CLASS_MAPPING.items():
            if pattern in key:
                return class_id
        return "1:30"

    def _separate_endpoints(
        self, src_str: str, dst_str: str, src_port: int, dst_port: int
    ) -> Tuple[Tuple[Any, int], Tuple[Any, int]]:
        src_ip = ipaddress.ip_address(src_str)
        dst_ip = ipaddress.ip_address(dst_str)

        # Standard Wi-Fi hotspot subnet
        local_v4 = ipaddress.ip_network("10.42.0.0/24")

        # Any IPv4 private range, link-local, or 10.42.0.x is a local client
        is_src_client = (
            src_ip.is_private
            or src_ip.is_link_local
            or (src_ip.version == 4 and src_ip in local_v4)
        )

        # For IPv6, if neither or both are private, client ports are typically ephemeral (>1024)
        if src_ip.version == 6 and not (src_ip.is_private ^ dst_ip.is_private):
            is_src_client = src_port > dst_port

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
        if src_ip.version == 4:
            cmd = [
                "tc",
                "filter",
                "add",
                "dev",
                iface,
                "protocol",
                "ip",
                "parent",
                "1:0",
                "prio",
                "1",
                "u32",
            ]
            if proto_num:
                cmd.extend(["match", "ip", "protocol", proto_num, "0xff"])
            cmd.extend(
                [
                    "match",
                    "ip",
                    "src",
                    f"{src_ip}/32",
                    "match",
                    "ip",
                    "sport",
                    str(src_port),
                    "0xffff",
                    "match",
                    "ip",
                    "dst",
                    f"{dst_ip}/32",
                    "match",
                    "ip",
                    "dport",
                    str(dst_port),
                    "0xffff",
                    "flowid",
                    target_class,
                ]
            )
        else:
            # IPv6: Offset 40 = L4 Sport, Offset 42 = L4 Dport
            cmd = [
                "tc",
                "filter",
                "add",
                "dev",
                iface,
                "protocol",
                "ipv6",
                "parent",
                "1:0",
                "prio",
                "1",
                "u32",
            ]
            if proto_num:
                cmd.extend(["match", "ip6", "protocol", proto_num, "0xff"])
            cmd.extend(
                [
                    "match",
                    "ip6",
                    "src",
                    f"{src_ip}/128",
                    "match",
                    "u16",
                    str(src_port),
                    "0xffff",
                    "at",
                    "40",
                    "match",
                    "ip6",
                    "dst",
                    f"{dst_ip}/128",
                    "match",
                    "u16",
                    str(dst_port),
                    "0xffff",
                    "at",
                    "42",
                    "flowid",
                    target_class,
                ]
            )
        return cmd

    def apply_policy(self, metadata: Dict[str, Any], predicted_class: str) -> bool:
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
            return False

        flow_key = f"{client_ip}:{client_port}<->{server_ip}:{server_port}-{proto}"
        if flow_key in self.applied_flows:
            return False

        target_class = self._resolve_classid(predicted_class)
        proto_num = (
            "6" if proto in ("TCP", "TLS") else "17" if proto in ("UDP", "QUIC") else ""
        )

        lan_cmd = self._build_5tuple_filter(
            self.lan_interface,
            server_ip,
            server_port,
            client_ip,
            client_port,
            target_class,
            proto_num,
        )
        wan_cmd = self._build_5tuple_filter(
            self.wan_interface,
            client_ip,
            client_port,
            server_ip,
            server_port,
            target_class,
            proto_num,
        )

        lan_ok = self._run_cmd(lan_cmd, check=False)
        wan_ok = self._run_cmd(wan_cmd, check=False)

        if lan_ok or wan_ok:
            self.applied_flows.add(flow_key)
            return True
        return False

    def teardown(self) -> None:
        self._run_cmd(
            ["tc", "qdisc", "del", "dev", self.lan_interface, "root"],
            check=False,
        )
        self._run_cmd(
            ["tc", "qdisc", "del", "dev", self.wan_interface, "root"],
            check=False,
        )
