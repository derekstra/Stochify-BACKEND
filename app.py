# === app.py (Unified Dev + Prod Backend with Live Stage Streaming) ===
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import os, requests, json, re, time

# === App Setup ===
app = Flask(__name__)

# Allow both local and production origins
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://stochify.com"
        ]
    }
})
socketio = SocketIO(app, cors_allowed_origins="*")

# === Paths ===
BASE_DIR = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# === Config ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# === Models ===
DISSECTOR_MODEL = "gpt-3.5-turbo"
GENERATOR_MODEL = "gpt-4o-mini"
STYLER_MODEL = "gpt-3.5-turbo"


# --- Helper: Emit live status updates to frontend ---
def send_status(stage, data=None):
    payload = {"stage": stage}
    if data:
        payload["data"] = data
    socketio.emit("status_update", payload)
    print(f"📡 STATUS: {stage}")


# --- Helper: Call OpenAI with timing ---
def call_openai(model, prompt):
    start_time = time.perf_counter()
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": model, "messages": [{"role": "user", "content": prompt}]}

    r = requests.post(OPENAI_URL, headers=headers, json=data)
    duration = time.perf_counter() - start_time

    try:
        res = r.json()
        raw = res.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"⚠️ Error reading response: {e}")
        raw = ""

    print(f"\n=== 🧠 {model.upper()} RAW RESPONSE ===\n{raw[:400]}...\n============================")
    print(f"⏱️  {model.upper()} execution time: {duration:.2f}s\n")
    return raw, duration


# === Main API Endpoint ===
@app.route("/api/chat", methods=["POST"])
def chat():
    total_start = time.perf_counter()
    user_input = request.json.get("message", "")
    print(f"\n=== 💬 USER INPUT ===\n{user_input}\n=====================\n")

    # === 1️⃣ Dissector Stage ===
    send_status("Reading prompt...")
    with open(os.path.join(PUBLIC_DIR, "dissection.txt"), encoding="utf-8") as f:
        p1 = f.read()

    dissected_raw, dissector_time = call_openai(
        DISSECTOR_MODEL, f"{p1}\n\nUser request:\n{user_input}"
    )

    try:
        clean_raw = re.sub(r"```[a-zA-Z]*", "", dissected_raw)
        clean_raw = clean_raw.replace("```", "").strip()
        json_blocks = re.findall(r"\{[\s\S]*\}", clean_raw)
        parsed = json.loads(json_blocks[-1]) if json_blocks else {}
    except Exception as e:
        print("⚠️ JSON parse error:", e)
        parsed = {}

    dimension = parsed.get("dimension", "2d").lower().strip()
    chat_response = parsed.get("description", "✅ Visualization ready.")

    # === 2️⃣ Generator Stage ===
    send_status("Generating code...")
    gen_file = "3D_General.txt" if dimension == "3d" else "2D_General.txt"
    gen_path = os.path.join(PUBLIC_DIR, gen_file)
    if not os.path.exists(gen_path):
        return jsonify({"status": "error", "message": f"{gen_file} missing"}), 404

    with open(gen_path, encoding="utf-8") as f:
        p2 = f.read()

    generated_code, generator_time = call_openai(
        GENERATOR_MODEL,
        f"{p2}\n\nThe following structured JSON describes the user's visualization request:\n"
        f"{json.dumps(parsed, indent=2)}"
    )

    cleaned_code = (
        generated_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    cleaned_code = re.sub(r"```[a-zA-Z]*", "", cleaned_code)
    cleaned_code = cleaned_code.replace("```", "").strip()
    cleaned_code = re.sub(r'd3\.select\(["\']body["\']\)', 'd3.select("#viz")', cleaned_code)

    # === 3️⃣ Styler Stage ===
    send_status("Refining generation...")
    styler_file = "3D_Styler.txt" if dimension == "3d" else "2D_Styler.txt"
    styler_path = os.path.join(PUBLIC_DIR, styler_file)
    if not os.path.exists(styler_path):
        return jsonify({"status": "error", "message": f"{styler_file} missing"}), 404

    with open(styler_path, encoding="utf-8") as f:
        p3 = f.read()

    styled_code, styler_time = call_openai(
        STYLER_MODEL, f"{p3}\n\nBase Visualization Code:\n{cleaned_code}"
    )

    styled_code = (
        styled_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    styled_code = re.sub(r"```[a-zA-Z]*", "", styled_code)
    styled_code = styled_code.replace("```", "").strip()

    total_time = time.perf_counter() - total_start

    # === ✅ Final stage ===
    send_status("complete", {"chat_response": chat_response})

    print("\n=== 🎨 FINAL STYLED CODE (first 1000 chars) ===")
    print(styled_code[:1000])
    print("\n==============================================")
    print(f"🕓 Timing Summary:")
    print(f"  • Dissector: {dissector_time:.2f}s")
    print(f"  • Generator: {generator_time:.2f}s")
    print(f"  • Styler:    {styler_time:.2f}s")
    print(f"  • TOTAL:     {total_time:.2f}s")
    print("==============================================\n")

    return jsonify({
        "analysis_raw": dissected_raw,
        "analysis_parsed": parsed,
        "dimension": dimension,
        "description": chat_response,
        "code": styled_code,
        "status": "complete",
        "timing": {
            "dissector_s": round(dissector_time, 2),
            "generator_s": round(generator_time, 2),
            "styler_s": round(styler_time, 2),
            "total_s": round(total_time, 2)
        }
    })


@app.route("/")
def index():
    return "✅ Stochify unified backend (Flask + SocketIO) is running."


if __name__ == "__main__":
    # Debug auto-reload for dev, normal run for prod
    socketio.run(app, debug=True, port=5000)
