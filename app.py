from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests, json, re

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://stochify.com"]}})

# === Paths ===
BASE_DIR = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# === Config ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Models
DISSECTOR_MODEL = "gpt-4-mini"
GENERATOR_MODEL = "gpt-5-mini"
STYLER_MODEL = "gpt-4-mini"

# --- API Call Helper ---
def call_openai(model, prompt):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(OPENAI_URL, headers=headers, json=data)
    res = r.json()
    raw = res.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(f"\n=== 🧠 {model.upper()} RAW RESPONSE ===\n{raw}\n============================\n")
    return raw

@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    print(f"\n=== 💬 USER INPUT ===\n{user_input}\n=====================\n")

    # === Stage 1: Dissection (GPT-4-mini) ===
    with open(os.path.join(PUBLIC_DIR, "dissection.txt"), encoding="utf-8") as f:
        p1 = f.read()

    dissected_raw = call_openai(DISSECTOR_MODEL, f"{p1}\n\nUser request:\n{user_input}")

    # ✅ NEW: Explicit debug print for dissector output
    print("\n=== 🧩 RAW DISSECTOR RESPONSE (PRE-PARSE) ===")
    print(dissected_raw)
    print("=============================================\n")

    # --- Safer JSON parsing (handles markdown and multiple blocks) ---
    dimension, description = "2d", "✅ Visualization ready."
    try:
        clean_raw = re.sub(r"```[a-zA-Z]*", "", dissected_raw)
        clean_raw = clean_raw.replace("```", "").strip()
        json_blocks = re.findall(r"\{[\s\S]*\}", clean_raw)
        parsed = json.loads(json_blocks[-1]) if json_blocks else {}
    except Exception as e:
        print("⚠️ JSON parse error:", e)
        parsed = {}

    # --- Extract useful fields ---
    dimension = parsed.get("dimension", "2d").lower().strip()
    description = parsed.get("description") or "✅ Visualization ready."

    # === Stage 2: Code Generation (GPT-5-mini) ===
    gen_file = "3D_General.txt" if dimension == "3d" else "2D_General.txt"
    gen_path = os.path.join(PUBLIC_DIR, gen_file)
    if not os.path.exists(gen_path):
        return jsonify({"status": "error", "message": f"{gen_file} missing"}), 404

    with open(gen_path, encoding="utf-8") as f:
        p2 = f.read()

    generated_code = call_openai(
        GENERATOR_MODEL,
        f"{p2}\n\nThe following structured JSON describes the user's visualization request:\n"
        f"{json.dumps(parsed, indent=2)}"
    )

    # --- Clean generator output ---
    cleaned_code = (
        generated_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    cleaned_code = re.sub(r"```[a-zA-Z]*", "", cleaned_code)
    cleaned_code = cleaned_code.replace("```", "").strip()
    cleaned_code = re.sub(r'd3\.select\(["\']body["\']\)', 'd3.select("#viz")', cleaned_code)

    # === Stage 3: Styler/Enhancer (GPT-4-mini) ===
    styler_file = "3D_Styler.txt" if dimension == "3d" else "2D_Styler.txt"
    styler_path = os.path.join(PUBLIC_DIR, styler_file)
    if not os.path.exists(styler_path):
        return jsonify({"status": "error", "message": f"{styler_file} missing"}), 404

    with open(styler_path, encoding="utf-8") as f:
        p3 = f.read()

    styled_code = call_openai(STYLER_MODEL, f"{p3}\n\nBase Visualization Code:\n{cleaned_code}")

    # --- Final clean (strip backticks or tags) ---
    styled_code = (
        styled_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    styled_code = re.sub(r"```[a-zA-Z]*", "", styled_code)
    styled_code = styled_code.replace("```", "").strip()

    print("\n=== 🎨 FINAL STYLED CODE (first 1000 chars) ===\n")
    print(styled_code[:1000])
    print("\n...\n==============================================\n")

    return jsonify({
        "analysis_raw": dissected_raw,   # ✅ full dissector response
        "analysis_parsed": parsed,       # ✅ parsed JSON for debug
        "dimension": dimension,
        "description": description,
        "code": styled_code,
        "status": "complete"
    })

@app.route("/")
def index():
    return "✅ Welcome! Flask backend with Dissector → Generator → Styler is running successfully."


if __name__ == "__main__":
    app.run(debug=True)
