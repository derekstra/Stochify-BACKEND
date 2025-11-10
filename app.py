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
GENERATOR_MODEL = "gpt-5-mini"
STYLER_MODEL = "gpt-4o-mini"

# === Task store (in-memory) ===
TASKS = {}  # { task_id: {"status": "Reading prompt...", "data": {...}} }

def inject_spec_into_template(spec: dict, dimension: str) -> str:
    """
    Reads base JS template (2D or 3D) and injects plotting logic
    from AI-generated JSON spec.
    """
    file_path = os.path.join(PUBLIC_DIR, f"{dimension}cartesian.js")
    with open(file_path, "r", encoding="utf-8") as f:
        base_js = f.read()

    json_spec = json.dumps(spec, indent=2)

    # ✅ Injected D3 + Three plotting logic
    injected_script = f"""
  // === INJECTED BY BACKEND ===
  const spec = {json_spec};

  if (spec.dimension === "2d") {{
    const plotG = d3.select("#viz").append("g").attr("class", "plot-layer");

    spec.functions?.forEach(f => {{
      try {{
        const expr = f.expr.replace(/y\\s*=\\s*/, "");
        const fn = new Function("x", `return ${{expr}};`);
        const domain = f.domain || [-3, 3];
        const step = (domain[1] - domain[0]) / 300;
        const X = d3.range(domain[0], domain[1] + step, step);
        const pts = X.map(x => [x, fn(x)]);
        const line = d3.line()
          .x(d => worldToScreen(d[0], d[1])[0])
          .y(d => worldToScreen(d[0], d[1])[1]);
        plotG.append("path")
          .datum(pts)
          .attr("fill", "none")
          .attr("stroke", f.color || "#8b5cf6")
          .attr("stroke-width", 2)
          .attr("stroke-dasharray", f.style === "dashed" ? "6 4" : null)
          .attr("d", line);
      }} catch (err) {{
        console.error("Plot error:", f.expr, err);
      }}
    }});
  }}

  else if (spec.dimension === "3d") {{
    const plotGroup = new THREE.Group();
    scene.add(plotGroup);

    spec.functions?.forEach(f => {{
      try {{
        const expr = f.expr.replace(/z\\s*=\\s*/, "");
        const fn = new Function("x", "y", `return ${{expr}};`);
        const color = new THREE.Color(f.color || 0x8b5cf6);
        const mat = new THREE.LineBasicMaterial({{ color, linewidth: 2 }});
        const domain = f.domain || [-3, 3];
        const step = (domain[1] - domain[0]) / 100;
        const points = [];
        for (let x = domain[0]; x <= domain[1]; x += step) {{
          const y = 0;
          const z = fn(x, y);
          points.push(new THREE.Vector3(x, z, y));
        }}
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        plotGroup.add(new THREE.Line(geo, mat));
      }} catch (err) {{
        console.error("3D function plot error:", f.expr, err);
      }}
    }});
  }}
    """

    # Replace marker in base file
    combined = base_js.replace("// === INJECT_SPEC_HERE ===", injected_script)
    return combined

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

def run_pipeline(task_id, user_input):
    total_start = time.perf_counter()

    # === Dissector Stage ===
    update_status(task_id, "Dissecting request and understanding request...")
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
        print("JSON parse error:", e)
        parsed = {}

    intent_text = (parsed.get("intent") or "").strip()
    dimension = parsed.get("dimension", "2d").lower().strip()
    cartesian = str(parsed.get("cartesian", "false")).lower().strip() == "true"
    chat_response = parsed.get("description", "Visualization ready.")

    if not intent_text:
        intent_text = (parsed.get("description") or clean_raw[:1000]).strip()

    # === Generator Stage ===
    update_status(task_id, "Generating visualization logic...")

    if cartesian:
        gen_file = "Cartesian.txt"
    elif dimension == "2d":
        gen_file = "2D_General.txt"
    elif dimension == "3d":
        gen_file = "3D_General.txt"
    else:
        gen_file = "2D_General.txt"

    gen_path = os.path.join(PUBLIC_DIR, gen_file)
    with open(gen_path, encoding="utf-8") as f:
        p2 = f.read()

    if cartesian:
        # === 1. Generate structured JSON spec ===
        generator_input = f"{p2}\n\nUser input:\n{user_input}"
        generated_json, generator_time = call_openai(GENERATOR_MODEL, generator_input)

        # === 2. Parse the JSON safely ===
        try:
            parsed = json.loads(generated_json)
        except json.JSONDecodeError:
            print(f"⚠️ [CARTESIAN] JSON parsing failed, attempting cleanup…")
            cleaned = re.sub(r"```[a-zA-Z]*", "", generated_json)
            cleaned = cleaned.replace("```", "").strip()
            try:
                parsed = json.loads(cleaned)
            except Exception as e:
                update_status(task_id, "error", {"error": f"JSON parsing failed: {e}"})
                return

        # === 3. Choose correct template (2D or 3D) ===
        dim = (parsed.get("dimension") or dimension or "2d").lower().strip()
        if dim not in ["2d", "3d"]:
            print(f"⚠️ Unknown dimension '{dim}', defaulting to 2D.")
            dim = "2d"

        dimension_upper = "2D" if dim == "2d" else "3D"

        # === 4. Inject spec into template ===
        try:
            final_code = inject_spec_into_template(parsed, dimension_upper)
        except Exception as e:
            update_status(task_id, "error", {"error": f"Template injection failed: {e}"})
            return

        # === 5. Complete and return ===
        total_time = time.perf_counter() - total_start
        update_status(
            task_id,
            "complete",
            {
                "chat_response": chat_response,
                "dimension": dimension,  # "2d" or "3d"
                "cartesian": cartesian,  # True
                "code": final_code,      # injected JS
            },
        )


        TASKS[task_id]["timing"] = {
            "dissector_s": round(dissector_time, 2),
            "generator_s": round(generator_time, 2),
            "styler_s": 0.0,
            "total_s": round(total_time, 2),
        }

        print(f"✅ [CARTESIAN] Rendered code task {task_id} complete in {total_time:.2f}s")
        return


    user_input_section = f"User request: {intent_text}"
    generator_input = f"{p2}\n\n{user_input_section}"

    generated_code, generator_time = call_openai(GENERATOR_MODEL, generator_input)

    cleaned_code = (
        generated_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    cleaned_code = re.sub(r"```[a-zA-Z]*", "", cleaned_code)
    cleaned_code = cleaned_code.replace("```", "").strip()
    cleaned_code = re.sub(r'd3\.select\(["\']body["\']\)', 'd3.select("#viz")', cleaned_code)

    # === Styler Stage ===
    update_status(task_id, "Refining styles and ensuring correct execution...")
    styler_file = "3D_Styler.txt" if dimension == "3d" else "2D_Styler.txt"
    styler_path = os.path.join(PUBLIC_DIR, styler_file)
    with open(styler_path, encoding="utf-8") as f:
        p3 = f.read()

    styled_code, styler_time = call_openai(
        STYLER_MODEL,
        f"{p3}\n\nUser request: {intent_text}\n\nCode:\n{cleaned_code}"
    )

    styled_code = (
        styled_code.replace("\r", "")
        .replace("</script>", "")
        .replace("<script>", "")
    )
    styled_code = re.sub(r"```[a-zA-Z]*", "", styled_code)
    styled_code = styled_code.replace("```", "").strip()

    total_time = time.perf_counter() - total_start
    update_status(
        task_id,
        "complete",
        {
            "chat_response": chat_response,
            "dimension": dimension,
            "cartesian": cartesian,
            "code": styled_code,
        },
    )

    TASKS[task_id]["timing"] = {
        "dissector_s": round(dissector_time, 2),
        "generator_s": round(generator_time, 2),
        "styler_s": round(styler_time, 2),
        "total_s": round(total_time, 2),
    }

    print(f"✅ [NON-CARTESIAN] Task {task_id} complete in {total_time:.2f}s")

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
    return "✅ Stochify backend is running."


if __name__ == "__main__":
    app.run(debug=True, port=5000)
