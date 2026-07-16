import torch
import torch.nn as nn
import pandas as pd
import json
import numpy as np
import joblib
import os

from sklearn.preprocessing import StandardScaler
from model_manager import AdaptiveNN


def train_model(model_id, csv_path, epochs=30):

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    path = f"saved_models/{model_id}"

    
    # LOAD CONFIG
    
    with open(f"{path}/config.json") as f:
        config = json.load(f)

    target = config.get("target")
    features = config.get("features", [])


    # LOAD CSV (auto-detect separator)
    
    for sep in [';', ',', '\t', '|']:
        df = pd.read_csv(csv_path, sep=sep)
        df.columns = df.columns.str.strip()
        if len(df.columns) > 1:
            break  # found correct separator

    # Case-insensitive column matching
    col_map = {c.lower().strip(): c for c in df.columns}
    target_lower = target.lower().strip()

    # Check exact match first, then case-insensitive
    if target not in df.columns:
        if target_lower in col_map:
            df = df.rename(columns={col_map[target_lower]: target})
            print(f" Matched target '{col_map[target_lower]}' → '{target}'")
        else:
            available = df.columns.tolist()
            raise Exception(f"Target '{target}' not found in CSV. Available columns: {available}")

    print("CSV Columns:", df.columns.tolist())
    print("Using target:", target)

    
    # AUTO DETECT FEATURES
    
    if not features:
        features = [col for col in df.columns if col not in [target, "id"]]

    if not features:
        raise Exception(" No features detected. Check dataset.")

    
    # SAVE FEATURES BACK
    
    config["features"] = features
    config["input_size"] = len(features)   

    with open(f"{path}/config.json", "w") as f:
        json.dump(config, f, indent=4)

    
    # PREPARE DATA
   
    df = df[features + [target]]

    # Fill missing values
    df = df.fillna(df.mean(numeric_only=True))

    scaler = StandardScaler()
    X = scaler.fit_transform(df[features])

    
    # SAVE MEANS + SCALER
    
    means = df[features].mean().to_dict()
    joblib.dump(means, f"{path}/means.pkl")
    joblib.dump(scaler, f"{path}/scaler.pkl")

    y = df[target].values

    
    X = np.nan_to_num(X)

    X = torch.tensor(X, dtype=torch.float32).to(device)
    y = torch.tensor(y, dtype=torch.float32).view(-1, 1).to(device)

    
    # MODEL INIT
    
    model = AdaptiveNN(len(features)).to(device)

    
    # LOAD EXISTING MODEL
    
    model_path = f"{path}/model.pth"

    if os.path.exists(model_path):
        try:
            model.load_state_dict(torch.load(model_path, map_location=device))
            print(" Loaded existing model")
        except Exception as e:
            print("Model mismatch → using fresh model", e)

    
    # TRAINING SETUP
    
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0003)

    model.train()

    
    # TRAIN LOOP
    
    for epoch in range(epochs):

        outputs = model(X)
        outputs = torch.clamp(outputs, -10, 10)

        loss = criterion(outputs, y)

        if torch.isnan(loss):
            print("⚠️ Skipping NaN loss")
            continue

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 3)
        optimizer.step()

        print(f"Epoch {epoch+1}, Loss: {loss.item():.4f}")

    
    # SAVE MODEL
    
    torch.save(model.state_dict(), model_path)

    print("Training complete!")

    
    # RETURN WEIGHTS 
    
    return {k: v.detach().cpu() for k, v in model.state_dict().items()}