(async function() {
  const d3lib = window.d3 || await import("https://cdn.jsdelivr.net/npm/d3@7/+esm");
  const d3 = d3lib.default || d3lib;

  const svg = d3.select("#viz");
  svg.selectAll("*").remove();

  const gridG   = svg.append("g").attr("class", "grid");
  const axesG   = svg.append("g").attr("class", "axes");
  const labelsG = svg.append("g").attr("class", "labels");

  let width = svg.node().clientWidth;
  let height = svg.node().clientHeight;
  let cx = width / 2, cy = height / 2;

  const BASE_PX_PER_UNIT = 100;
  const MIN_K = 1e-6;
  const MAX_K = 2e4;
  let t = d3.zoomIdentity;

  // --- Panning ---
  svg.call(d3.drag()
    .on("start", () => svg.style("cursor", "grabbing"))
    .on("drag", (event) => {
      t = d3.zoomIdentity.translate(t.x + event.dx, t.y + event.dy).scale(t.k);
      render();
    })
    .on("end", () => svg.style("cursor", "grab"))
  );

  // --- Cursor-anchored zoom ---
  svg.on("wheel", function(event) {
    event.preventDefault();

    const [sx, sy] = d3.pointer(event);
    const { x, y, k } = t;

    const wx = (sx - cx - x) / (BASE_PX_PER_UNIT * k);
    const wy = -(sy - cy - y) / (BASE_PX_PER_UNIT * k);

    const zoomFactor = Math.pow(2, -event.deltaY / 500);
    let newK = k * zoomFactor;
    newK = Math.min(Math.max(newK, MIN_K), MAX_K);

    const newX = sx - cx - BASE_PX_PER_UNIT * newK * wx;
    const newY = sy - cy + BASE_PX_PER_UNIT * newK * wy;

    if (newK === MAX_K && zoomFactor > 1) return;
    if (newK === MIN_K && zoomFactor < 1) return;

    t = d3.zoomIdentity.translate(newX, newY).scale(newK);
    render();
  }, { passive: false });

  window.addEventListener("resize", () => {
    width = svg.node().clientWidth;
    height = svg.node().clientHeight;
    cx = width / 2; cy = height / 2;
    render();
  });

  function pxPerUnit() { return BASE_PX_PER_UNIT * t.k; }
  function worldToScreen(x, y) {
    return [cx + t.x + pxPerUnit() * x, cy + t.y - pxPerUnit() * y];
  }
  function screenToWorld(x, y) {
    return [(x - cx - t.x) / pxPerUnit(), -(y - cy - t.y) / pxPerUnit()];
  }

  function niceStep(targetPx) {
    const raw = targetPx / pxPerUnit();
    const p = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1e-12))));
    const n = raw / p;
    const nice = n >= 5 ? 5 : n >= 2 ? 2 : 1;
    const major = nice * p;
    const minor = major / (nice === 2 ? 2 : 5);
    return { major, minor };
  }

  function ticksInRange(a, b, step) {
    const start = Math.ceil(a / step) * step;
    const end = Math.floor(b / step) * step;
    const out = [];
    for (let v = start; v <= end + 1e-9; v += step) out.push(+v.toFixed(12));
    return out;
  }

  function render() {
    gridG.selectAll("*").remove();
    axesG.selectAll("*").remove();
    labelsG.selectAll("*").remove();

    const { major, minor } = niceStep(100);
    const [x0, y0] = screenToWorld(0, height);
    const [x1, y1] = screenToWorld(width, 0);

    const xsMinor = ticksInRange(x0, x1, minor);
    const ysMinor = ticksInRange(y0, y1, minor);
    const xsMajor = ticksInRange(x0, x1, major);
    const ysMajor = ticksInRange(y0, y1, major);

    // Minor grid
    gridG.selectAll(".gx-minor")
      .data(xsMinor).join("line")
      .attr("class", "grid-minor")
      .attr("x1", d => worldToScreen(d, 0)[0])
      .attr("x2", d => worldToScreen(d, 0)[0])
      .attr("y1", 0).attr("y2", height);
    gridG.selectAll(".gy-minor")
      .data(ysMinor).join("line")
      .attr("class", "grid-minor")
      .attr("y1", d => worldToScreen(0, d)[1])
      .attr("y2", d => worldToScreen(0, d)[1])
      .attr("x1", 0).attr("x2", width);

    // Major grid
    gridG.selectAll(".gx-major")
      .data(xsMajor).join("line")
      .attr("class", "grid-major")
      .attr("x1", d => worldToScreen(d, 0)[0])
      .attr("x2", d => worldToScreen(d, 0)[0])
      .attr("y1", 0).attr("y2", height);
    gridG.selectAll(".gy-major")
      .data(ysMajor).join("line")
      .attr("class", "grid-major")
      .attr("y1", d => worldToScreen(0, d)[1])
      .attr("y2", d => worldToScreen(0, d)[1])
      .attr("x1", 0).attr("x2", width);

    // Axes
    axesG.append("line").attr("class", "axis")
      .attr("x1", 0).attr("x2", width)
      .attr("y1", worldToScreen(0, 0)[1])
      .attr("y2", worldToScreen(0, 0)[1]);
    axesG.append("line").attr("class", "axis")
      .attr("y1", 0).attr("y2", height)
      .attr("x1", worldToScreen(0, 0)[0])
      .attr("x2", worldToScreen(0, 0)[0]);

    // Labels
    const fmt = d3.format(".4~f");
    const skipLabels = t.k > MAX_K * 0.9;
    if (!skipLabels) {
      xsMajor.forEach(x => {
        const [sx, sy] = worldToScreen(x, 0);
        if (sx > 25 && sx < width - 25)
          labelsG.append("text")
            .attr("x", sx)
            .attr("y", worldToScreen(0, 0)[1] + 14)
            .attr("class", "tick-label")
            .attr("text-anchor", "middle")
            .text(fmt(x));
      });
      ysMajor.forEach(y => {
        const [sx, sy] = worldToScreen(0, y);
        if (sy > 20 && sy < height - 10)
          labelsG.append("text")
            .attr("x", worldToScreen(0, 0)[0] - 8)
            .attr("y", sy + 4)
            .attr("class", "tick-label")
            .attr("text-anchor", "end")
            .text(fmt(y));
      });
    }
  }

  render();

  // === INJECT_SPEC_HERE ===
})();
