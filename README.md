# Controller Architecture and File Structure Guide

This guide details the updated directory structure for our Python Controller. Following the Python design principle of keeping module structures flat rather than deeply nested, this layout separates runtime storage, static model artifacts, and core execution logic while avoiding complex import paths.

---

## 1. Directory Tree

```text
PYTHONCONTROLLER/
├── data/                          <-- Persistent local runtime storage
│   ├── gateway_logs.db            <-- Auto-created SQLite database
│   └── dossiers/                  <-- Directory holding JSON Client Dossiers
│
├── models/                        <-- Static Machine Learning artifacts
│   ├── feature_columns_n7.pkl
│   ├── label_encoder_n7.pkl
│   ├── rf_baseline_model_n7.pkl
│   └── scaler_n7.pkl
│
├── src/                           <-- Core source logic
│   ├── __init__.py
│   ├── config.py                  <-- Central configuration, thresholds, and paths
│   ├── receiver.py                <-- ZeroMQ receiver listening to Go engine
│   ├── feature_mapper.py          <-- Maps incoming payload features to ML inputs
│   ├── predictor.py               <-- Random Forest model inference engine
│   ├── qos_manager.py             <-- Linux tc HTB queue manager
│   ├── risk_engine.py             <-- Anomaly rules and rolling risk score tracker
│   ├── mitigator.py               <-- Kernel iptables and blackhole route execution
│   ├── database.py                <-- SQLite connection and query handler
│   └── dossier_manager.py         <-- Hardware MAC-bound JSON dossier writer
│
├── main.py                        <-- Central pipeline orchestrator
├── .gitignore
└── venv/
```
