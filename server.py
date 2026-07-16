import os, json, shutil, datetime, hashlib, re, random
import torch, requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from model_manager import AdaptiveNN

app = FastAPI(title="NeuralHub")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODEL_DIR    = "server_models"
MODEL_DB     = "models.json"
CONFIG_F     = "server_config.json"
CLIENT_USERS = "users.json"        # main app users (User A / B — trainers)
PORTAL_USERS = "portal_users.json" # portal users (User C — prediction only)

os.makedirs(MODEL_DIR, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_F):
        return json.load(open(CONFIG_F))
    cfg = {
        "ollama_url": "http://localhost:11434",
        "ollama_model": "phi3:mini",
        "use_ollama": True,
        "gemini_api_key": "YOUR_GEMINI_KEY_HERE",
        "gemini_model": "gemini-2.0-flash"
    }
    json.dump(cfg, open(CONFIG_F, "w"), indent=2)
    return cfg

def load_db():
    return json.load(open(MODEL_DB)) if os.path.exists(MODEL_DB) else {}

def save_db(d):
    json.dump(d, open(MODEL_DB, "w"), indent=2)

def load_model_cfg(mid):
    p = f"{MODEL_DIR}/{mid}/config.json"
    return json.load(open(p)) if os.path.exists(p) else None

def save_model_cfg(mid, cfg):
    os.makedirs(f"{MODEL_DIR}/{mid}", exist_ok=True)
    json.dump(cfg, open(f"{MODEL_DIR}/{mid}/config.json", "w"), indent=2)

def ts():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def load_users():
    """Main app users (User A/B - trainers). Stored in users.json"""
    return json.load(open(CLIENT_USERS)) if os.path.exists(CLIENT_USERS) else {}

def save_users(u):
    json.dump(u, open(CLIENT_USERS, "w"), indent=2)

def load_pusers():
    """Portal users (User C - prediction only). Stored in portal_users.json"""
    return json.load(open(PORTAL_USERS)) if os.path.exists(PORTAL_USERS) else {}

def save_pusers(u):
    json.dump(u, open(PORTAL_USERS, "w"), indent=2)

def phash(p):
    return hashlib.sha256(p.encode()).hexdigest()


@app.get("/status")
def status():
    return {"status": "online", "models": len(load_db()), "time": ts()}


@app.post("/auth/register")
def register(data: dict):
    u, p = data.get("username", "").strip(), data.get("password", "").strip()
    if not u or not p:
        return {"ok": False, "error": "Fill all fields"}
    users = load_users()
    if u in users:
        return {"ok": False, "error": "Username taken"}
    users[u] = {"password": phash(p)}
    save_users(users)
    return {"ok": True}


@app.post("/auth/login")
def login(data: dict):
    u, p = data.get("username", "").strip(), data.get("password", "").strip()
    users = load_users()
    if u in users and users[u]["password"] == phash(p):
        return {"ok": True}
    return {"ok": False, "error": "Invalid credentials"}


@app.post("/auth/delete")
def delete_user(data: dict):
    u = data.get("username", "").strip()
    users = load_users()
    if u in users:
        del users[u]
        save_users(users)
    return {"ok": True}


# ── PORTAL AUTH (separate DB from client users) ──────────────────────────────
@app.post("/portal/auth/login")
def portal_login(data: dict):
    u, p = data.get("username","").strip(), data.get("password","").strip()
    users = load_pusers()
    if u in users and users[u]["password"] == phash(p):
        return {"ok": True}
    return {"ok": False, "error": "Invalid credentials"}

@app.post("/portal/auth/register")
def portal_register(data: dict):
    u, p = data.get("username","").strip(), data.get("password","").strip()
    if not u or not p: return {"ok": False, "error": "Fill all fields"}
    users = load_pusers()
    if u in users: return {"ok": False, "error": "Username taken"}
    users[u] = {"password": phash(p)}
    save_pusers(users)
    return {"ok": True}

@app.post("/portal/auth/delete")
def portal_delete(data: dict):
    u = data.get("username","")
    users = load_pusers()
    if u in users: del users[u]
    save_pusers(users)
    return {"ok": True}

@app.get("/models")
def get_models():
    return load_db()


@app.post("/models/create")
def create_model(data: dict):
    mid    = data.get("model_id")
    target = data.get("target", "")
    if not mid or not target:
        raise HTTPException(400, "model_id and target required")
    db = load_db()
    db[mid] = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "features_info": data.get("features_info", ""),
        "target": target,
        "creator": data.get("creator", ""),
        "users": [data.get("creator", "")],
        "version": 0,
        "performance": None,
        "prev_performance": None,
        "improvement": None,
        "last_updated": ts(),
        "features": [],
        "input_size": 0,
        "last_csv_hash": ""
    }
    save_db(db)
    save_model_cfg(mid, {"model_id": mid, "target": target, "features": [], "input_size": 0, "version": 0})
    return {"ok": True, "model_id": mid}


@app.post("/models/{mid}/delete")
def delete_model(mid: str, data: dict):
    db = load_db()
    if mid not in db:
        raise HTTPException(404, "Not found")
    if db[mid]["creator"] != data.get("username", ""):
        raise HTTPException(403, "Only creator can delete")
    del db[mid]
    save_db(db)
    mp = f"{MODEL_DIR}/{mid}"
    if os.path.exists(mp):
        shutil.rmtree(mp)
    return {"ok": True}


@app.post("/models/{mid}/join")
def join_model(mid: str, data: dict):
    u = data.get("username", "")
    db = load_db()
    if mid not in db:
        raise HTTPException(404, "Not found")
    if u not in db[mid]["users"]:
        db[mid]["users"].append(u)
    save_db(db)
    return {"ok": True}


@app.post("/models/{mid}/leave")
def leave_model(mid: str, data: dict):
    u = data.get("username", "")
    db = load_db()
    if mid in db and u in db[mid]["users"]:
        db[mid]["users"].remove(u)
        save_db(db)
    return {"ok": True}


@app.get("/get_global/{mid}")
def get_global(mid: str):
    cfg = load_model_cfg(mid)
    if not cfg:
        raise HTTPException(404, "Model not found")
    size = cfg.get("input_size", 0)
    if size == 0:
        return {"message": "Not trained yet", "version": 0}
    model = AdaptiveNN(size)
    mp = f"{MODEL_DIR}/{mid}/model.pth"
    if os.path.exists(mp):
        model.load_state_dict(torch.load(mp, map_location="cpu"))
    db = load_db()
    meta = db.get(mid, {})
    return {
        "global_weights": {k: v.tolist() for k, v in model.state_dict().items()},
        "model_id": mid,
        "features": cfg.get("features", []),
        "version": meta.get("version", 0),
        "performance": meta.get("performance"),
        "last_updated": meta.get("last_updated", "")
    }


@app.post("/send_weights")
def receive_weights(data: dict):
    mid         = data.get("model_id")
    client_id   = data.get("client_id", "unknown")
    client_wts  = data.get("weights", {})
    features    = data.get("features", [])
    input_size  = data.get("input_size", 0)
    performance = data.get("performance", 0.0)
    csv_hash    = data.get("csv_hash", "")

    if not mid:
        raise HTTPException(400, "model_id required")
    cfg = load_model_cfg(mid)
    if not cfg:
        raise HTTPException(404, "Model not on server")

    if cfg.get("input_size", 0) == 0 and input_size > 0:
        cfg["features"]   = features
        cfg["input_size"] = input_size
        save_model_cfg(mid, cfg)

    cur_size = cfg.get("input_size", input_size)
    mp       = f"{MODEL_DIR}/{mid}/model.pth"
    model    = AdaptiveNN(cur_size)
    if os.path.exists(mp):
        try:
            model.load_state_dict(torch.load(mp, map_location="cpu"))
        except Exception:
            pass

    db             = load_db()
    last_hash      = db.get(mid, {}).get("last_csv_hash", "")
    is_duplicate   = bool(csv_hash and csv_hash == last_hash)

    if not is_duplicate:
        gs = model.state_dict()
        cs = {k: torch.tensor(v) for k, v in client_wts.items()}
        for k in gs:
            if k in cs and gs[k].shape == cs[k].shape:
                gs[k] = (gs[k] + cs[k]) / 2.0
        model.load_state_dict(gs)
        os.makedirs(f"{MODEL_DIR}/{mid}", exist_ok=True)
        torch.save(model.state_dict(), mp)

        # Save scaler sent from client so server-side predictions are correctly scaled
        scaler_b64 = data.get("scaler_b64")
        if scaler_b64:
            import base64 as _b64
            with open(f"{MODEL_DIR}/{mid}/scaler.pkl", "wb") as fh:
                fh.write(_b64.b64decode(scaler_b64.encode("utf-8")))

    if mid in db:
        old_perf    = db[mid].get("performance")
        new_version = db[mid].get("version", 0) + (0 if is_duplicate else 1)

        if not is_duplicate and performance > 0:
            new_perf = round(performance, 4)
            db[mid]["prev_performance"] = old_perf
            db[mid]["performance"]      = new_perf
            db[mid]["improvement"]      = None if old_perf is None else round((new_perf - old_perf) * 100, 2)

        db[mid]["version"]       = new_version
        db[mid]["last_csv_hash"] = csv_hash or last_hash
        db[mid]["last_updated"]  = ts()
        db[mid]["features"]      = cfg.get("features", features)
        db[mid]["input_size"]    = cur_size
        save_db(db)

    cfg["version"] = db.get(mid, {}).get("version", 0)
    save_model_cfg(mid, cfg)

    label = "DUPLICATE" if is_duplicate else f"v{cfg['version']} acc={performance*100:.1f}%"
    print(f"[FL] {mid} from {client_id} → {label}")

    return {"ok": True, "version": cfg["version"], "duplicate": is_duplicate}


@app.post("/predict/{mid}")
def predict(mid: str, data: dict):
    import joblib
    cfg = load_model_cfg(mid)
    if not cfg or cfg.get("input_size", 0) == 0:
        raise HTTPException(400, "Model not trained yet")
    x = [float(data.get(f, 0)) for f in cfg["features"]]
    sp = f"{MODEL_DIR}/{mid}/scaler.pkl"
    if os.path.exists(sp):
        x = joblib.load(sp).transform([x])[0].tolist()
    model = AdaptiveNN(cfg["input_size"])
    mp    = f"{MODEL_DIR}/{mid}/model.pth"
    if not os.path.exists(mp):
        raise HTTPException(400, "Train the model first")
    model.load_state_dict(torch.load(mp, map_location="cpu"))
    model.eval()
    with torch.no_grad():
        prob = torch.sigmoid(model(torch.tensor([x], dtype=torch.float32))).item()
    return {"prediction": int(prob >= 0.5), "probability": round(prob, 4),
            "label": "Positive" if prob >= 0.5 else "Negative"}


def call_ollama(prompt, cfg):
    url = cfg.get("ollama_url", "http://localhost:11434").rstrip("/") + "/api/generate"
    r   = requests.post(url, json={
        "model": cfg.get("ollama_model", "phi3:mini"),
        "prompt": prompt, "stream": False,
        "options": {"temperature": 0.3, "num_predict": 500}
    }, timeout=90)
    r.raise_for_status()
    text = r.json().get("response", "")
    if not text:
        raise RuntimeError("empty Ollama response")
    return text


def call_gemini(prompt, cfg):
    key = cfg.get("gemini_api_key", "")
    if not key or key == "YOUR_GEMINI_KEY_HERE":
        raise RuntimeError("no key")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.get('gemini_model','gemini-2.0-flash')}:generateContent?key={key}"
    r   = requests.post(url, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 500, "temperature": 0.3}
    }, timeout=25)
    if r.status_code != 200:
        raise RuntimeError(f"gemini {r.status_code}")
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


_states = {}

def get_state(token):
    return _states.setdefault(token, {"model_id": None, "data": {}, "features": []})

def clear_state(token):
    _states[token] = {"model_id": None, "data": {}, "features": []}

def missing(state):
    return [f for f in state.get("features", []) if f not in state.get("data", {}) or state["data"][f] in [None, ""]]

def friendly_q(feat, info):
    fi = info.get("features_info", "").lower()
    fl = feat.lower()
    mapping = {
        "age":        "How old are you?",
        "smoke":      "Do you smoke? (yes / no)",
        "smoking":    "Do you smoke? (yes / no)",
        "alco":       "Do you drink alcohol regularly? (yes / no)",
        "alcohol":    "Do you drink alcohol regularly? (yes / no)",
        "active":     "Are you physically active? (yes / no)",
        "activity":   "Are you physically active? (yes / no)",
        "gender":     "What is your gender? (male / female)",
        "sex":        "What is your sex? (male / female)",
        "cholesterol":"How is your cholesterol? (normal / high / very high)",
        "chol":       "How is your cholesterol? (normal / high / very high)",
        "glucose":    "How is your blood glucose? (normal / high / very high)",
        "gluc":       "How is your blood glucose? (normal / high / very high)",
        "ap_hi":      "What is your systolic (upper) blood pressure?",
        "ap_lo":      "What is your diastolic (lower) blood pressure?",
    }
    if fl in mapping:
        return mapping[fl]
    if "cm" in fi and fl in ["height"]:
        return "What is your height in cm?"
    if "kg" in fi and fl in ["weight"]:
        return "What is your weight in kg?"
    return f"Could you tell me your {feat.replace('_', ' ').title()}?"


def parse_answer(feat, val, info):
    v  = val.strip().lower()
    fl = feat.lower()
    yes_words = ["yes","y","true","yeah","yep","1"]
    no_words  = ["no","n","false","nope","nah","0"]
    if v in yes_words: return 1
    if v in no_words:  return 0
    if fl in ["gender","sex"]:
        if v in ["male","m","man","boy"]:     return 0
        if v in ["female","f","woman","girl"]: return 1
    if fl in ["cholesterol","chol","glucose","gluc"]:
        if v in ["normal","1"]:            return 1
        if v in ["high","2"]:              return 2
        if v in ["very high","3"]:         return 3
    try:
        return float(val.strip())
    except ValueError:
        return None


def run_prediction(state, token):
    import joblib
    mid = state["model_id"]
    cfg = load_model_cfg(mid)
    if not cfg or cfg.get("input_size", 0) == 0:
        clear_state(token)
        return {"reply": "This model hasn't been trained yet. Please check back later."}
    x  = [float(state["data"].get(f, 0)) for f in cfg["features"]]
    sp = f"{MODEL_DIR}/{mid}/scaler.pkl"
    if os.path.exists(sp):
        x = joblib.load(sp).transform([x])[0].tolist()
    model = AdaptiveNN(cfg["input_size"])
    mp    = f"{MODEL_DIR}/{mid}/model.pth"
    if not os.path.exists(mp):
        clear_state(token)
        return {"reply": "The model needs to be trained before predictions can be made."}
    model.load_state_dict(torch.load(mp, map_location="cpu"))
    model.eval()
    with torch.no_grad():
        prob = torch.sigmoid(model(torch.tensor([x], dtype=torch.float32))).item()
    name = load_db().get(mid, {}).get("name", "the model")
    clear_state(token)
    pol  = "positive" if prob >= 0.5 else "negative"
    return {"reply": f"RESULT:{pol}:{int(prob>=0.5)}:{prob*100:.1f}%", "model_name": name}


def match_model(msg, models):
    ml = msg.lower()
    best, score = None, 0
    for mid, m in models.items():
        blob = (m.get("name","") + " " + m.get("description","") + " " + m.get("target","")).lower()
        s    = sum(1 for w in blob.split() if len(w) > 3 and w in ml)
        if s > score:
            score, best = s, mid
    return best if score >= 1 else None


GREETINGS = [
    "Hey there! How can I help you today? I can chat normally or guide you through a health assessment.",
    "Hello! Feel free to ask me anything — or if you'd like to run a health check, just tell me what you want to assess.",
    "Hi! Great to hear from you. What can I do for you today?",
]
HOW_ARE_YOU = [
    "I'm doing well, thanks for asking! How about you? Let me know if there's anything I can help with.",
    "All good on my end! Ready to chat or help with a health assessment whenever you are.",
]
THANKS = [
    "You're welcome! Let me know if there's anything else.",
    "Happy to help! Feel free to ask anything else.",
    "Of course! Anything else I can do for you?",
]
BYES = [
    "Take care! Come back anytime. 👋",
    "Goodbye! Stay well.",
    "See you! Have a great day.",
]


def smalltalk(msg, models):
    m = msg.lower().strip().rstrip("!?.")
    greets  = ["hi","hello","hey","hiya","howdy","sup","yo"]
    howru   = ["how are you","how r u","how do you do","hows it going","how's it going","you doing","how you doing"]
    thanks  = ["thanks","thank you","thx","ty","cheers"]
    byes    = ["bye","goodbye","cya","see you","see ya","later","take care","farewell"]
    whatcan = ["what can you do","what do you do","how can you help","what are you","who are you","tell me about yourself"]

    if m in greets or any(m.startswith(g) for g in greets):
        return random.choice(GREETINGS)
    if any(p in m for p in howru):
        return random.choice(HOW_ARE_YOU)
    if any(w in m for w in thanks):
        return random.choice(THANKS)
    if any(w in m for w in byes):
        return random.choice(BYES)
    if any(p in m for p in whatcan):
        if models:
            names = ", ".join(f"**{v.get('name','')}**" for v in models.values())
            return f"I can chat normally about anything and also run AI assessments! Right now I have: {names}.\n\nJust tell me what you'd like to check — for example, 'I want to check my heart health'."
        return "I can have a normal conversation and guide you through health assessments. Just tell me what you need!"
    return None


@app.post("/chat")
def chat(data: dict):
    username = data.get("username", "").strip()
    app_id   = data.get("session_app", "portal")
    msg      = data.get("message", "").strip()
    mfilter  = data.get("models_filter", [])

    if not username or not msg:
        return {"reply": ""}

    token = f"{username}_{app_id}"
    db    = load_db()

    if mfilter:
        models = {mid: m for mid, m in db.items() if mid in mfilter and m.get("input_size", 0) > 0}
    else:
        models = {mid: m for mid, m in db.items() if m.get("input_size", 0) > 0 and m.get("features")}

    state = get_state(token)

    if msg.lower().strip() in ["reset","restart","clear","start over","new"]:
        clear_state(token)
        return {"reply": "Sure, fresh start! What would you like to talk about?"}

    if state.get("model_id") and state.get("features"):
        miss = missing(state)
        if miss:
            val = parse_answer(miss[0], msg, models.get(state["model_id"], {}))
            if val is not None:
                state["data"][miss[0]] = val
                miss2 = missing(state)
                if not miss2:
                    return run_prediction(state, token)
                return {"reply": f"Got it! {friendly_q(miss2[0], models.get(state['model_id'], {}))}"}
            return {"reply": f"Sorry, I didn't catch that. {friendly_q(miss[0], models.get(state['model_id'], {}))}"}

    if state.get("model_id") and not missing(state):
        return run_prediction(state, token)

    st = smalltalk(msg, models)
    if st:
        return {"reply": st}

    cfg  = load_config()
    text = None

    model_desc = "\n".join(
        f"  [{mid}] {m.get('name','')} — {m.get('description','')} (predicts: {m.get('target','')})"
        for mid, m in models.items()
    ) or "  No trained models available yet."

    prompt = f"""You are a warm, friendly AI assistant. You can chat normally AND run health/risk assessments.

Available assessment models:
{model_desc}

User says: "{msg}"

Rules:
- For casual chat (greetings, general questions, off-topic): reply naturally in 1-2 sentences. Be warm and human.
- If the user's message relates to a model above (health, disease, risk, finance etc): acknowledge warmly and end your reply with exactly: START_ASSESSMENT:<model_id>
- Never use words like "features", "dataset", "input", "model weights" with the user.
- Reply as plain conversational text only. No bullet points, no headers, no JSON."""

    if cfg.get("use_ollama", True):
        try:
            text = call_ollama(prompt, cfg)
        except requests.exceptions.ConnectionError:
            print("[chat] Ollama offline, trying Gemini")
        except Exception as e:
            print(f"[chat] Ollama: {e}")

    if text is None:
        try:
            text = call_gemini(prompt, cfg)
        except Exception as e:
            print(f"[chat] Gemini: {e}")

    if text:
        text = text.strip()
        if "START_ASSESSMENT:" in text:
            parts    = text.split("START_ASSESSMENT:")
            reply    = parts[0].strip()
            mid_hint = parts[1].strip().split()[0].strip()
            if mid_hint in models:
                m = models[mid_hint]
                state["model_id"] = mid_hint
                state["features"] = m.get("features", [])
                miss = missing(state)
                if miss:
                    q = friendly_q(miss[0], m)
                    return {"reply": f"{reply}\n\n{q}".strip() if reply else q}
        return {"reply": text}

    mid = match_model(msg, models)
    if mid:
        m = models[mid]
        state["model_id"] = mid
        state["features"] = m.get("features", [])
        miss = missing(state)
        if miss:
            return {"reply": f"Sure! Let me help you with **{m['name']}**. I'll ask a few quick questions.\n\n{friendly_q(miss[0], m)}"}

    if models:
        names = ", ".join(f"**{m.get('name','')}**" for m in models.values())
        return {"reply": f"I can chat or run an assessment. Available topics: {names}. What would you like to explore?"}
    return {"reply": "Hi! I'm your AI assistant. How can I help you today?"}


@app.post("/chat/reset")
def chat_reset(data: dict):
    u   = data.get("username", "")
    app = data.get("session_app", "portal")
    if u:
        clear_state(f"{u}_{app}")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("  NeuralHub Server  →  http://0.0.0.0:8000")
    print("  LLM: phi3:mini (Ollama)  →  Gemini fallback")
    print("  Docs: http://localhost:8000/docs")
    print("="*50 + "\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
