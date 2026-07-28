from typing import Any, Dict

MODEL_KEYMAP = {
    "FwdPktLenMax": "fwd_pkt_len_max",
    "BwdPktLenMax": "bwd_pkt_len_max",
    "FwdPktLenMin": "fwd_pkt_len_min",
    "BwdPktLenMin": "bwd_pkt_len_min",
    "FwdPktLenMean": "fwd_pkt_len_mean",
    "BwdPktLenMean": "bwd_pkt_len_mean",
    "FwdPktLenSTD": "fwd_pkt_len_std",
    "BwdPktLenSTD": "bwd_pkt_len_std",
    "PktLenVar": "pkt_len_var",
    "FlowIatMean": "flow_iat_mean",
    "FlowIatSTD": "flow_iat_std",
    "FlowIatMax": "flow_iat_max",
    "FwdIatMean": "fwd_iat_mean",
    "PshFlagCount": "psh_flag_cnt",
    "ProtoUDP": "proto_UDP",
}


def case_translator(raw_features: Dict[str, Any]) -> Dict[str, Any]:
    mapped_features = {
        MODEL_KEYMAP[key]: val
        for key, val in raw_features.items()
        if key in MODEL_KEYMAP
    }

    return mapped_features
