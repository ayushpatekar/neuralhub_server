"""
predict_manager.py
Loads a trained model and runs inference on a sample dict.
"""

import os, json
import torch
import joblib
import numpy as np
from model_manager import AdaptiveNN


def predict(model_id: str, sample: dict) -> dict:
    path = f"saved_models/{model_id}"

    if not os.path.exists(path):
        raise FileNotFoundError(f"Model {model_id} not found")

    # ── load config ──────────────────────────────
    with open(f"{path}/config.json") as f:
        config = json.load(f)

    features   = config.get("features", [])
    input_size = config.get("input_size", len(features))

    if not features:
        raise ValueError("No features defined in config")

    # ── build feature vector ──────────────────────
    # fill missing with 0
    x = [float(sample.get(f, 0)) for f in features]

    # ── scale if scaler saved ────────────────────
    scaler_path = f"{path}/scaler.pkl"
    if os.path.exists(scaler_path):
        scaler = joblib.load(scaler_path)
        x = scaler.transform([x])[0].tolist()

    x_tensor = torch.tensor([x], dtype=torch.float32)

    # ── load model ───────────────────────────────
    model = AdaptiveNN(input_size)
    model_file = f"{path}/model.pth"
    if not os.path.exists(model_file):
        raise FileNotFoundError("model.pth not found — please train first")

    model.load_state_dict(torch.load(model_file, map_location="cpu"))
    model.eval()

    # ── inference ────────────────────────────────
    with torch.no_grad():
        logit = model(x_tensor)
        prob  = torch.sigmoid(logit).item()

    prediction = 1 if prob >= 0.5 else 0

    return {
        "prediction":  prediction,
        "probability": round(prob, 4),
        "label":       "Positive" if prediction == 1 else "Negative"
    }
