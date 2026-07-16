import os, json, re, threading, hashlib, base64
import torch, pandas as pd, requests, joblib, numpy as np
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from model_manager import AdaptiveNN
from train_manager import train_model

app = Flask(__name__)
app.secret_key = "neuralhub-client-2025"

SERVER_URL = " https://eternal-debtless-rebuff.ngrok-free.dev"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def srv(path, method="GET", body=None, timeout=10):
    try:
        url = SERVER_URL.rstrip("/") + path
        r   = requests.get(url, timeout=timeout) if method == "GET" else requests.post(url, json=body or {}, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def me():
    return session.get("username")


@app.route("/")
def index():
    if not me():
        return redirect(url_for("login_page"))
    return render_template("dashboard.html")


@app.route("/login")
def login_page():
    if me():
        return redirect(url_for("index"))
    return render_template("login.html")



@app.route("/api/me")
def api_me():
    u = me()
    return jsonify({"logged_in": bool(u), "username": u or ""})


@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.get_json()
    u, p = d.get("username", "").strip(), d.get("password", "").strip()
    r = srv("/auth/login", "POST", {"username": u, "password": p})
    if r.get("ok"):
        session["username"] = u
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": r.get("error", "Login failed")})


@app.route("/api/register", methods=["POST"])
def api_register():
    d = request.get_json()
    u, p = d.get("username", "").strip(), d.get("password", "").strip()
    if not u or not p:
        return jsonify({"ok": False, "error": "Fill all fields"})
    r = srv("/auth/register", "POST", {"username": u, "password": p})
    if r.get("ok"):
        session["username"] = u
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": r.get("error", "Registration failed")})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/delete_account", methods=["POST"])
def api_delete_account():
    u = me()
    if u:
        srv("/auth/delete", "POST", {"username": u})
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/models")
def api_models():
    u = me()
    if not u:
        return jsonify([])
    db = srv("/models")
    if "error" in db:
        return jsonify({"error": db["error"]}), 503
    result = []
    for mid, m in db.items():
        if u in m.get("users", []):
            result.append({
                "id": mid, "name": m.get("name", ""),
                "description": m.get("description", ""),
                "target": m.get("target", ""),
                "creator": m.get("creator", ""),
                "role": "owner" if m.get("creator") == u else "joined",
                "users": m.get("users", []),
                "version": m.get("version", 0),
                "performance": m.get("performance", 0.0),
                "improvement": m.get("improvement"),
                "last_updated": m.get("last_updated", ""),
                "features": m.get("features", []),
                "features_info": m.get("features_info", ""),
            })
    return jsonify(result)


@app.route("/api/models/create", methods=["POST"])
def api_create_model():
    u = me()
    if not u:
        return jsonify({"ok": False, "error": "Not logged in"})
    d = request.get_json()
    if not d.get("name") or not d.get("target"):
        return jsonify({"ok": False, "error": "Name and target required"})
    import uuid
    mid = "model_" + str(uuid.uuid4())[:8]
    r = srv("/models/create", "POST", {
        "model_id": mid, "name": d["name"], "description": d.get("description", ""),
        "features_info": d.get("features_info", ""), "target": d["target"], "creator": u
    })
    if r.get("ok"):
        return jsonify({"ok": True, "model_id": mid})
    return jsonify({"ok": False, "error": r.get("detail", r.get("error", "Server error"))})


@app.route("/api/models/join", methods=["POST"])
def api_join_model():
    u = me()
    if not u:
        return jsonify({"ok": False})
    d = request.get_json()
    return jsonify(srv(f"/models/{d.get('model_id','')}/join", "POST", {"username": u}))


@app.route("/api/models/<mid>")
def api_model_detail(mid):
    u = me()
    if not u:
        return jsonify({}), 401
    db = srv("/models")
    if mid not in db:
        return jsonify({"error": "Not found"}), 404
    m = db[mid]
    return jsonify({
        "id": mid, "name": m.get("name", ""),
        "description": m.get("description", ""),
        "target": m.get("target", ""),
        "creator": m.get("creator", ""),
        "features_info": m.get("features_info", ""),
        "features": m.get("features", []),
        "role": "owner" if m.get("creator") == u else "joined",
        "users": m.get("users", []),
        "version": m.get("version", 0),
        "performance": m.get("performance", 0.0),
        "improvement": m.get("improvement"),
        "last_updated": m.get("last_updated", ""),
        "input_size": m.get("input_size", 0),
    })


@app.route("/api/models/<mid>/delete", methods=["POST"])
def api_delete_model(mid):
    u = me()
    return jsonify(srv(f"/models/{mid}/delete", "POST", {"username": u}))


@app.route("/api/models/<mid>/leave", methods=["POST"])
def api_leave_model(mid):
    u = me()
    return jsonify(srv(f"/models/{mid}/leave", "POST", {"username": u}))


def build_schema(features_info, features, target):
    fi = features_info.lower()
    schema = []
    for f in features:
        if f.lower() in [target.lower(), "id"]:
            continue
        fl    = f.lower()
        field = {"key": f, "label": f.replace("_", " ").title(), "type": "number", "default": 0}

        for pat in [rf"{fl}[:\s]+([^\.;\n]+(?:=\d+[,\s]*)+)", rf"{fl}\s*\(([^)]+)\)"]:
            m = re.search(pat, fi)
            if m:
                pairs = re.findall(r"([a-zA-Z][a-zA-Z\s]*)=(\d+)|(\d+)=([a-zA-Z][a-zA-Z\s]*)", m.group(1))
                opts  = []
                for p in pairs:
                    if p[0]: opts.append({"label": p[0].strip().title(), "value": int(p[1])})
                    elif p[2]: opts.append({"label": p[3].strip().title(), "value": int(p[2])})
                if opts:
                    field.update({"type": "select", "options": opts, "default": opts[0]["value"]})
                break

        if field["type"] != "select":
            if fl in ["smoke","smoking","alco","alcohol","active","activity"]:
                field.update({"type": "select", "options": [{"label":"No","value":0},{"label":"Yes","value":1}], "default": 0})
            elif fl in ["cholesterol","chol","glucose","gluc"]:
                field.update({"type": "select", "options": [{"label":"Normal","value":1},{"label":"High","value":2},{"label":"Very High","value":3}], "default": 1})
            elif fl in ["gender","sex"]:
                field.update({"type": "select", "options": [{"label":"Male","value":0},{"label":"Female","value":1}], "default": 0})

        if fl == "age":    field["default"] = 45
        if fl == "height": field.update({"default": 170, "unit": "cm"})
        if fl == "weight": field.update({"default": 70,  "unit": "kg"})
        if fl in ["ap_hi","systolic"]:  field.update({"default": 120, "unit": "mmHg"})
        if fl in ["ap_lo","diastolic"]: field.update({"default": 80,  "unit": "mmHg"})
        schema.append(field)
    return schema


@app.route("/api/models/<mid>/schema")
def api_schema(mid):
    db = srv("/models")
    if mid not in db:
        return jsonify([])
    m = db[mid]
    return jsonify(build_schema(m.get("features_info",""), m.get("features",[]), m.get("target","")))


@app.route("/api/models/<mid>/train", methods=["POST"])
def api_train(mid):
    u = me()
    if not u:
        return jsonify({"ok": False})
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded"})

    global_data = srv(f"/get_global/{mid}")
    local_path  = f"saved_models/{mid}"
    os.makedirs(local_path, exist_ok=True)

    db = srv("/models")
    if mid not in db:
        return jsonify({"ok": False, "error": "Model not found on server"})

    m_info    = db[mid]
    local_cfg = {
        "model_id": mid, "target": m_info["target"],
        "features": global_data.get("features", []),
        "input_size": len(global_data.get("features", []))
    }
    json.dump(local_cfg, open(f"{local_path}/config.json", "w"), indent=2)

    if global_data.get("global_weights") and local_cfg["input_size"] > 0:
        mdl = AdaptiveNN(local_cfg["input_size"])
        mdl.load_state_dict({k: torch.tensor(v) for k, v in global_data["global_weights"].items()})
        torch.save(mdl.state_dict(), f"{local_path}/model.pth")

    f        = request.files["file"]
    csv_path = os.path.join(UPLOAD_DIR, f"{mid}_train.csv")
    f.save(csv_path)
    with open(csv_path, "rb") as fh:
        csv_hash = hashlib.md5(fh.read()).hexdigest()

    try:
        weights_dict  = train_model(mid, csv_path)
        updated_cfg   = json.load(open(f"{local_path}/config.json"))
        features      = updated_cfg.get("features", [])
        input_size    = updated_cfg.get("input_size", 0)

        perf = 0.0
        try:
            for sep in [";", ",", "\t", "|"]:
                df = pd.read_csv(csv_path, sep=sep)
                df.columns = df.columns.str.strip()
                if len(df.columns) > 1:
                    break
            target = updated_cfg["target"]
            col_map = {c.lower(): c for c in df.columns}
            if target not in df.columns and target.lower() in col_map:
                df = df.rename(columns={col_map[target.lower()]: target})
            af = [c for c in features if c in df.columns]
            if target in df.columns and input_size > 0 and af:
                n    = len(df)
                dv   = df.iloc[int(n * 0.8):].copy()
                X    = dv[af].fillna(0).values
                y    = dv[target].values.astype(float)
                sp   = f"{local_path}/scaler.pkl"
                if os.path.exists(sp):
                    X = joblib.load(sp).transform(X)
                mdl2 = AdaptiveNN(input_size)
                mdl2.load_state_dict({k: v for k, v in weights_dict.items()})
                mdl2.eval()
                with torch.no_grad():
                    preds = (torch.sigmoid(mdl2(torch.tensor(X, dtype=torch.float32))).squeeze() >= 0.5).float()
                perf = float((preds == torch.tensor(y, dtype=torch.float32)).float().mean())
        except Exception as pe:
            print(f"[train] perf calc skipped: {pe}")

        weights_json = {k: v.cpu().numpy().tolist() for k, v in weights_dict.items()}

        # Send scaler to server so server-side predictions are correctly scaled
        scaler_b64 = None
        sp = f"{local_path}/scaler.pkl"
        if os.path.exists(sp):
            with open(sp, "rb") as fh:
                scaler_b64 = base64.b64encode(fh.read()).decode("utf-8")

        srv_resp = srv("/send_weights", "POST", {
            "client_id": u, "model_id": mid,
            "weights": weights_json, "features": features,
            "input_size": input_size, "performance": perf, "csv_hash": csv_hash,
            "scaler_b64": scaler_b64
        }, timeout=30)

        version  = srv_resp.get("version", "?")
        is_dup   = srv_resp.get("duplicate", False)
        perf_pct = round(perf * 100, 1)
        impr     = None
        if not is_dup:
            fresh = srv("/models")
            if mid in fresh:
                impr = fresh[mid].get("improvement")

        if is_dup:
            msg = f"Same CSV as before — no update (still v{version})"
        else:
            parts = [f"Training complete — pushed v{version}"]
            if perf > 0:
                parts.append(f"{perf_pct}% val accuracy")
            if impr is not None:
                sign = "+" if impr >= 0 else ""
                parts.append(f"{sign}{impr}pp vs last")
            msg = " · ".join(parts)

        return jsonify({"ok": True, "message": msg, "version": version,
                        "performance": perf_pct, "improvement": impr,
                        "features": features, "duplicate": is_dup})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)


@app.route("/api/models/<mid>/predict", methods=["POST"])
def api_predict(mid):
    r = srv(f"/predict/{mid}", "POST", request.get_json(), timeout=10)
    if "error" in r:
        return jsonify({"ok": False, "error": r["error"]})
    return jsonify({"ok": True, **r})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    u = me()
    if not u:
        return jsonify({"reply": "Please log in."})
    d   = request.get_json()
    msg = d.get("message", "").strip()
    if not msg:
        return jsonify({"reply": ""})
    db  = srv("/models")
    ids = [mid for mid, m in db.items() if u in m.get("users", [])] if isinstance(db, dict) else []
    return jsonify(srv("/chat", "POST", {
        "username": u, "session_app": "client",
        "message": msg, "models_filter": ids
    }, timeout=120))


@app.route("/api/chat/reset", methods=["POST"])
def api_chat_reset():
    u = me()
    if u:
        srv("/chat/reset", "POST", {"username": u, "session_app": "client"})
    return jsonify({"ok": True})


@app.route("/api/server/status")
def api_server_status():
    r = srv("/status")
    return jsonify({"online": "status" in r})


if __name__ == "__main__":
    import webbrowser
    print("\n" + "="*46)
    print("  NeuralHub Client  →  http://localhost:5000")
    print("="*46 + "\n")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
