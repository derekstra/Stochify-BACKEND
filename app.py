from flask import Flask, request, jsonify, send_from_directory
import os, requests, re, json

app = Flask(__name__)

# === Paths ===
BASE_DIR = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

# === Config ===
GROQ_API_KEY = "..."   # move to .env in production
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OPENAI_API_KEY = "..."
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-5-mini"

def call_groq(prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(GROQ_URL, headers=headers, json=data)
    res = r.json()
    return res.get("choices", [{}])[0].get("message", {}).get("content", "")

def call_gpt5(prompt):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {"model": OPENAI_MODEL, "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(OPENAI_URL, headers=headers, json=data)
    res = r.json()
    return res.get("choices", [{}])[0].get("message", {}).get("content", "")

@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")

    with open(os.path.join(PUBLIC_DIR, "dissection.txt"), encoding="utf-8") as f:
        p1 = f.read()
    dissected_raw = call_groq(f"{p1}\n\nUser request:\n{user_input}")

    dimension, cartesian, chat_response = "2d", False, "✅ Visualization ready."
    try:
        parsed = json.loads(re.sub(r"^```json|```$", "", dissected_raw.strip()))
        dimension = parsed.get("dimension", "2d").lower().strip()
        cartesian = str(parsed.get("cartesian", "false")).lower() == "true"
        chat_response = parsed.get("chat_response", chat_response)
    except Exception as e:
        print("⚠️ JSON parse error:", e)

    if cartesian:
        gen_file = "3D_Cartesian.txt" if dimension == "3d" else "2D_Cartesian.txt"
    else:
        gen_file = "3D_General.txt" if dimension == "3d" else "2D_General.txt"

    gen_path = os.path.join(PUBLIC_DIR, gen_file)
    if not os.path.exists(gen_path):
        return jsonify({"status": "error", "message": f"{gen_file} missing"}), 404

    with open(gen_path, encoding="utf-8") as f:
        p2 = f.read()

    final_code = call_gpt5(f"{p2}\n\nStructured Request:\n{dissected_raw}")

    cleaned_code = (
        final_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    cleaned_code = re.sub(r"```[a-zA-Z]*", "", cleaned_code)
    cleaned_code = cleaned_code.replace("```", "").strip()
    cleaned_code = re.sub(r'd3\.select\(["\']body["\']\)', 'd3.select("#viz")', cleaned_code)

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
    return send_from_directory(PUBLIC_DIR, "index.html")

if __name__ == "__main__":
    app.run(debug=True)
