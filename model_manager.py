import os
import json
import uuid
import torch
import torch.nn as nn


class AdaptiveNN(nn.Module):
    def __init__(self, input_size):
        super().__init__()
        self.fc1 = nn.Linear(input_size, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 16)
        self.out = nn.Linear(16, 1)

    def forward(self, x):
        return self.out(torch.relu(self.fc3(torch.relu(self.fc2(torch.relu(self.fc1(x)))))))


def create_model(df, target):
    model_id = "model_" + str(uuid.uuid4())[:8]

    path = f"saved_models/{model_id}"
    os.makedirs(path, exist_ok=True)

    features = [col for col in df.columns if col != target]

    config = {
        "model_id": model_id,
        "target": target,
        "features": features,
        "input_size": len(features)
    }

    with open(f"{path}/config.json", "w") as f:
        json.dump(config, f)

    model = AdaptiveNN(len(features))
    torch.save(model.state_dict(), f"{path}/model.pth")

    print("Model created:", model_id)

    return model_id