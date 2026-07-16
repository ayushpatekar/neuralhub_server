# NeuralHub

A federated learning system that lets multiple people train a shared AI model
without ever sharing their actual data. Only the model weights get sent to the
server — your CSV stays on your machine.

---

## Who is this for?

**User A / B — Trainers (the client app)**
These are the people with training data. They run `run_client.bat`, log in,
upload their CSV to train the model, and can run predictions. Their accounts
and model data all live on the server — nothing sensitive is stored locally.

**User C — End users (the prediction portal)**
People who just want to use the model for predictions. They run `run_portal.bat`,
log in with a separate portal account, and chat with the AI assistant to get
predictions. They don't train anything, and they can't see the model internals.

**The Server — stays on your PC**
Everything lives here: user accounts, model weights, the AI chat backend (Ollama),
model registry. You share access via ngrok so others can connect remotely.

---

## Quick Start

### Step 1 — Set up the server (your PC)

1. Make sure Python is installed (3.9+)
2. Install Ollama from https://ollama.com and run: `ollama pull phi3:mini`
3. Run `run_server.bat`
4. Install ngrok from https://ngrok.com/download
5. In a separate terminal: `ngrok http 8000`
6. Copy the `https://xxxx.ngrok-free.app` URL

### Step 2 — Configure the client

Open `app.py` and update this line near the top:

```python
SERVER_URL = "https://your-ngrok-url-here.ngrok-free.app"
```

Do the same in `predict_portal.py`.

### Step 3 — Run the client

Double-click `run_client.bat`. Browser opens at http://localhost:5000.
Register an account — it gets stored on the server, not locally.

### Step 4 — Share with your friend (User C)

Give them the portal files (see below). They run `run_portal.bat` and
get a prediction assistant — no training required, no technical knowledge needed.

---

## File Structure

```
server.py           — FastAPI server (run on YOUR PC only)
app.py              — Flask client app (trainers run this)
predict_portal.py   — Flask portal (end users run this)
model_manager.py    — Neural network definition (shared)
train_manager.py    — Local training logic (shared)
predict_manager.py  — Local prediction helper (shared)
server_config.json  — Server settings (Ollama/Gemini config)
run_server.bat      — Start server + ngrok
run_client.bat      — Start trainer client app
run_portal.bat      — Start end-user portal
```

**Data files created automatically:**
```
users.json          — Trainer accounts (on server)
portal_users.json   — Portal accounts (on server)
models.json         — Model registry (on server)
server_models/      — Trained model weights (on server)
```

---

## What to send to your friend (User C)

They only need:
- `predict_portal.py`
- `run_portal.bat`
- `templates_portal/` folder
- `model_manager.py`
- `predict_manager.py`
- `server_config.json` (optional — only if you want them to use Gemini too)

**Do not send:** `server.py`, `app.py`, `users.json`, `models.json`, or anything in `server_models/`.

Update `SERVER_URL` in `predict_portal.py` to your ngrok URL before sharing.

---

## AI Assistant Setup

The AI assistant runs on the server using Ollama (phi3:mini by default).
Edit `server_config.json` to change settings:

```json
{
  "use_ollama": true,
  "ollama_url": "http://localhost:11434",
  "ollama_model": "phi3:mini",
  "gemini_api_key": "your-key-here",
  "gemini_model": "gemini-2.0-flash"
}
```

If `use_ollama` is true, it tries Ollama first. If Ollama is not running,
it falls back to Gemini. If both fail, the assistant still works — it just
uses keyword matching to guide users through predictions without the LLM.

Get a free Gemini key at https://aistudio.google.com/apikey

---

## How federated learning works here

1. You create a model (just a name + target column — no data needed)
2. You share the model ID with your friend (User B)
3. Both of you upload your own CSVs locally
4. The training runs on your machine — your data never leaves
5. Only the trained weight values (a list of numbers) get sent to the server
6. The server averages the weights from all clients (FedAvg)
7. Everyone gets the benefit of the combined training

The model gets better with each training round. The version number and
validation accuracy are tracked so you can see improvement over time.

---

## Notes

- The model structure (AdaptiveNN) is a 4-layer neural network that adapts
  to however many features your CSV has — no configuration needed.
- Duplicate CSV detection: if you upload the same file twice, the server
  detects it by MD5 hash and skips the update (version stays the same).
- Validation accuracy is measured on a 20% holdout split — so it reflects
  real performance, not just training fit.
