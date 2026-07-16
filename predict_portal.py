import os, requests
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__, template_folder="templates_portal")
app.secret_key = "neuralhub-portal-2025"

SERVER_URL = "https://eternal-debtless-rebuff.ngrok-free.dev"


def srv(path, method="GET", body=None, timeout=10):
    try:
        url = SERVER_URL.rstrip("/") + path
        r   = requests.get(url, timeout=timeout) if method == "GET" else requests.post(url, json=body or {}, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def puser():
    return session.get("portal_user")


@app.route("/")
def index():
    if not puser():
        return render_template("portal_login.html")
    return render_template("portal.html")


@app.route("/login")
def login_page():
    if puser():
        return render_template("portal.html")
    return render_template("portal_login.html")


@app.route("/api/portal/me")
def api_me():
    u = puser()
    return jsonify({"logged_in": bool(u), "username": u or ""})


@app.route("/api/portal/login", methods=["POST"])
def api_login():
    d    = request.get_json()
    u, p = d.get("username", "").strip(), d.get("password", "").strip()
    r    = srv("/portal/auth/login", "POST", {"username": u, "password": p})
    if r.get("ok"):
        session["portal_user"] = u
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": r.get("error", "Login failed")})


@app.route("/api/portal/register", methods=["POST"])
def api_register():
    d    = request.get_json()
    u, p = d.get("username", "").strip(), d.get("password", "").strip()
    if not u or not p:
        return jsonify({"ok": False, "error": "Fill all fields"})
    r = srv("/portal/auth/register", "POST", {"username": u, "password": p})
    if r.get("ok"):
        session["portal_user"] = u
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": r.get("error", "Registration failed")})


@app.route("/api/portal/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/portal/delete_account", methods=["POST"])
def api_delete():
    u = puser()
    if u:
        srv("/portal/auth/delete", "POST", {"username": u})
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/portal/models")
def api_models():
    if not puser():
        return jsonify({"error": "not_logged_in"})
    db = srv("/models")
    if "error" in db:
        return jsonify({"error": db["error"]})
    return jsonify([{
        "id": mid, "name": m.get("name", ""),
        "description": m.get("description", ""),
        "target": m.get("target", ""),
        "version": m.get("version", 0),
        "features": m.get("features", []),
        "features_info": m.get("features_info", ""),
        "performance": m.get("performance"),
        "last_updated": m.get("last_updated", ""),
    } for mid, m in db.items() if m.get("input_size", 0) > 0 and m.get("features")])


@app.route("/api/portal/predict/<mid>", methods=["POST"])
def api_predict(mid):
    if not puser():
        return jsonify({"ok": False, "error": "not_logged_in"})
    r = srv(f"/predict/{mid}", "POST", request.get_json(), timeout=10)
    if "error" in r:
        return jsonify({"ok": False, "error": r["error"]})
    return jsonify({"ok": True, "prediction": r["prediction"],
                    "probability": float(r["probability"]), "label": r.get("label", "")})


@app.route("/api/portal/chat", methods=["POST"])
def api_chat():
    u = puser()
    if not u:
        return jsonify({"reply": "Please log in first."})
    msg = request.get_json().get("message", "").strip()
    if not msg:
        return jsonify({"reply": ""})
    return jsonify(srv("/chat", "POST", {
        "username": u, "session_app": "portal",
        "message": msg, "models_filter": []
    }, timeout=120))


@app.route("/api/portal/chat/reset", methods=["POST"])
def api_chat_reset():
    u = puser()
    if u:
        srv("/chat/reset", "POST", {"username": u, "session_app": "portal"})
    return jsonify({"ok": True})


@app.route("/api/portal/status")
def api_status():
    r = srv("/status")
    return jsonify({"online": "status" in r})


if __name__ == "__main__":
    import webbrowser, threading
    print("\n" + "="*50)
    print("  NeuralHub Portal  →  http://localhost:5001")
    print("="*50 + "\n")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5001")).start()
    app.run(host="0.0.0.0", port=5001, debug=False)
