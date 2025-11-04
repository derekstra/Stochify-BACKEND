from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests, json, re

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://stochify.com"]}})

# === Paths ===
BASE_DIR = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# === Config ===
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-5-mini"


# --- API Call Helpers ---
def call_groq(prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(GROQ_URL, headers=headers, json=data)
    res = r.json()
    raw = res.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("\n=== 🧠 GROQ RAW RESPONSE ===\n", raw, "\n============================\n")
    return raw


def call_gpt5(prompt):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": OPENAI_MODEL, "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(OPENAI_URL, headers=headers, json=data)
    res = r.json()
    raw = res.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("\n=== 🎨 GPT-5 RAW RESPONSE ===\n", raw, "\n============================\n")
    return raw


# --- Chat Endpoint ---
@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    print(f"\n=== 💬 USER INPUT ===\n{user_input}\n=====================\n")

    # Stage 1: Dissection (Groq)
    with open(os.path.join(PUBLIC_DIR, "dissection.txt"), encoding="utf-8") as f:
        p1 = f.read()
    dissected_raw = call_groq(f"{p1}\n\nUser request:\n{user_input}")

    # Parse JSON safely
    dimension, cartesian, chat_response = "2d", False, "✅ Visualization ready."
    try:
        json_match = re.search(r"\{[\s\S]*\}", dissected_raw)
        parsed = json.loads(json_match.group(0)) if json_match else {}
    except Exception as e:
        print("⚠️ JSON parse error:", e)
        parsed = {}

    # Extract keys
    dimension = parsed.get("dimension", "2d").lower().strip()
    cartesian = str(parsed.get("cartesian", "false")).lower() == "true"
    chat_response = parsed.get("chat_response", "✅ Visualization ready.")

    # Pick correct generation template
    gen_file = (
        "3D_Cartesian.txt" if (cartesian and dimension == "3d")
        else "2D_Cartesian.txt" if cartesian
        else "3D_General.txt" if dimension == "3d"
        else "2D_General.txt"
    )

    gen_path = os.path.join(PUBLIC_DIR, gen_file)
    if not os.path.exists(gen_path):
        return jsonify({"status": "error", "message": f"{gen_file} missing"}), 404

    with open(gen_path, encoding="utf-8") as f:
        p2 = f.read()

    # Stage 2: Code Generation (GPT-5)
    final_code = call_gpt5(f"{p2}\n\nStructured Request:\n{dissected_raw}")

    # Clean code
    cleaned_code = (
        final_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    cleaned_code = re.sub(r"```[a-zA-Z]*", "", cleaned_code)
    cleaned_code = cleaned_code.replace("```", "").strip()
    cleaned_code = re.sub(r'd3\.select\(["\']body["\']\)', 'd3.select("#viz")', cleaned_code)

    print("\n=== ✅ FINAL CLEANED CODE ===\n", cleaned_code[:1000], "\n...\n=============================\n")

    return jsonify({
        "analysis": dissected_raw,
        "dimension": dimension,
        "cartesian": cartesian,
        "chat_response": chat_response,
        "code": cleaned_code,
        "status": "complete"
    })


@app.route("/")
def index():
    return "✅ Welcome! Flask backend is running successfully."


if __name__ == "__main__":
    app.run(debug=True)
