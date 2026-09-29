from typing import Any, Dict, List

# Explicit mapping from Go struct fields to Scikit-Learn training feature names
GO_TO_MODEL_FEATURE_MAP: Dict[str, str] = {
    "FrameLenMean": "frame_len_mean",
    "FrameLenStd": "frame_len_std",
    "FrameLenMin": "frame_len_min",
    "FrameLenMax": "frame_len_max",
    "FrameLenCV": "frame_len_cv",
    "PayloadLenMean": "payload_len_mean",
    "PayloadLenStd": "payload_len_std",
    "PayloadLenMin": "payload_len_min",
    "PayloadLenMax": "payload_len_max",
    "PayloadLenSum": "payload_len_sum",
    "PayloadLenCV": "payload_len_cv",
    "Duration": "duration",
    "IatMean": "iat_mean",
    "IatStd": "iat_std",
    "IatMin": "iat_min",
    "IatMax": "iat_max",
    "IatCV": "iat_cv",
    "FwdPackets": "fwd_packets",
    "RevPackets": "rev_packets",
    "FwdPayloadBytes": "fwd_payload_bytes",
    "RevPayloadBytes": "rev_payload_bytes",
    "DirNormAsymPackets": "dir_norm_asym_packets",
    "DirNormAsymBytes": "dir_norm_asym_bytes",
}

FEATURE_NAMES: List[str] = list(GO_TO_MODEL_FEATURE_MAP.values())


def map_features(raw_features: Dict[str, Any]) -> Dict[str, float]:
    """Translates Go PascalCase feature dictionary to snake_case float key-value pairs."""
    mapped: Dict[str, float] = {}
    for go_key, model_key in GO_TO_MODEL_FEATURE_MAP.items():
        val = raw_features.get(go_key, 0.0)
        try:
            mapped[model_key] = float(val)
        except (ValueError, TypeError):
            mapped[model_key] = 0.0
    return mapped
