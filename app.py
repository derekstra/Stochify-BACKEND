# === app.py (Stochify Backend with HTTP Polling Status Updates) ===
from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests, json, re, time, threading

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

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

# === Task store (in-memory) ===
TASKS = {}  # { task_id: {"status": "Reading prompt...", "data": {...}} }


# --- Helper: Update and store current task status ---
def update_status(task_id, stage, data=None):
    TASKS[task_id] = {"status": stage, "data": data or {}}
    print(f"📡 STATUS [{task_id}]: {stage}")


# --- Helper: OpenAI call with timing ---
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

    print(f"🧠 {model.upper()} completed in {duration:.2f}s")
    return raw, duration


# --- Worker thread: run full pipeline asynchronously ---
def run_pipeline(task_id, user_input):
    total_start = time.perf_counter()

    # === 1️⃣ Dissector Stage ===
    update_status(task_id, "Reading prompt...")
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
    update_status(task_id, "Generating code...")
    gen_file = "3D_General.txt" if dimension == "3d" else "2D_General.txt"
    gen_path = os.path.join(PUBLIC_DIR, gen_file)
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
    update_status(task_id, "Refining generation...")
    styler_file = "3D_Styler.txt" if dimension == "3d" else "2D_Styler.txt"
    styler_path = os.path.join(PUBLIC_DIR, styler_file)
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
    update_status(task_id, "complete", {"chat_response": chat_response})

    TASKS[task_id]["timing"] = {
        "dissector_s": round(dissector_time, 2),
        "generator_s": round(generator_time, 2),
        "styler_s": round(styler_time, 2),
        "total_s": round(total_time, 2),
    }

    print(f"✅ Task {task_id} complete in {total_time:.2f}s")


# === API ROUTES ===

@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    task_id = str(int(time.time() * 1000))
    TASKS[task_id] = {"status": "starting"}
    threading.Thread(target=run_pipeline, args=(task_id, user_input)).start()
    return jsonify({"task_id": task_id})


@app.route("/api/status/<task_id>", methods=["GET"])
def status(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({"status": "unknown"})
    return jsonify(task)


@app.route("/")
def index():
    return "✅ Stochify backend running with polling-based stage updates."


if __name__ == "__main__":
    app.run(debug=True, port=5000)
