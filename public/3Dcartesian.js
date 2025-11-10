// === THREE.JS 3D CARTESIAN BASE TEMPLATE ===
// This file is dynamically injected by the backend
// Injection placeholder: // === INJECT_SPEC_HERE ===

(async function() {
  const THREE = await import("https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js");
  const { OrbitControls } = await import("https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js");

  const container = document.getElementById("viz") || document.body;
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setClearColor(0x0e0e0f, 1);
  container.innerHTML = "";
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 10000);
  camera.position.set(12, 10, 12);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.target.set(0, 0, 0);
  controls.minDistance = 5;
  controls.maxDistance = 500;

  // === Lighting ===
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.4);
  dirLight.position.set(10, 20, 10);
  scene.add(dirLight);

  // === Materials ===
  const minorGridMat = new THREE.LineBasicMaterial({ color: 0x1b1b1f, transparent: true, opacity: 0.5 });
  const majorGridMat = new THREE.LineBasicMaterial({ color: 0x2a2a30, transparent: true, opacity: 0.7 });
  const axisMat = new THREE.LineBasicMaterial({ color: 0xb8b8c2, linewidth: 3, transparent: false, opacity: 1 });

  // === Groups ===
  const gridGroup = new THREE.Group();
  const axisGroup = new THREE.Group();
  const labelGroup = new THREE.Group();
  scene.add(gridGroup, axisGroup, labelGroup);

  // === Text Sprite Helper ===
  function createTextSprite(text, color = 0xd9d9e0) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    canvas.width = 256;
    canvas.height = 128;

    ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
    ctx.font = "bold 48px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 128, 64);

    ctx.fillStyle = "#d9d9e0";
    ctx.fillText(text, 128, 64);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMat = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.5, 0.75, 1);
    sprite.renderOrder = 999;
    return sprite;
  }

  // === Utility functions ===
  function formatNumber(n) {
    if (n === 0) return "0";
    const abs = Math.abs(n);
    if (abs >= 1000 || abs < 0.001) return n.toExponential(1);
    return parseFloat(n.toFixed(4)).toString();
  }

  function niceStep(range, targetSteps = 6) {
    const raw = range / targetSteps;
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

  function getVisibleRange() {
    const dist = camera.position.length();
    const vFov = (camera.fov * Math.PI) / 180;
    const height = 2 * Math.tan(vFov / 2) * dist;
    const aspect = camera.aspect;
    const width = height * aspect;
    const range = Math.max(width, height) * 0.6;
    return range;
  }

  // === Render Grid and Axes ===
  function render3D() {
    gridGroup.clear();
    axisGroup.clear();
    labelGroup.clear();

    const range = getVisibleRange();
    const { major, minor } = niceStep(range);
    const min = -range, max = range;

    const xsMinor = ticksInRange(min, max, minor);
    const zsMinor = ticksInRange(min, max, minor);
    const xsMajor = ticksInRange(min, max, major);
    const zsMajor = ticksInRange(min, max, major);
    const ysMajor = ticksInRange(min, max, major);

    // Minor grid lines (XZ plane)
    zsMinor.forEach(z => {
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(min, 0, z), new THREE.Vector3(max, 0, z)]);
      gridGroup.add(new THREE.Line(geo, minorGridMat));
    });
    xsMinor.forEach(x => {
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, 0, min), new THREE.Vector3(x, 0, max)]);
      gridGroup.add(new THREE.Line(geo, minorGridMat));
    });

    // Major grid lines
    zsMajor.forEach(z => {
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(min, 0, z), new THREE.Vector3(max, 0, z)]);
      gridGroup.add(new THREE.Line(geo, majorGridMat));
    });
    xsMajor.forEach(x => {
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, 0, min), new THREE.Vector3(x, 0, max)]);
      gridGroup.add(new THREE.Line(geo, majorGridMat));
    });

    // Axes
    const xAxisGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(min, 0, 0), new THREE.Vector3(max, 0, 0)]);
    axisGroup.add(new THREE.Line(xAxisGeo, axisMat));

    const yAxisGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, min, 0), new THREE.Vector3(0, max, 0)]);
    axisGroup.add(new THREE.Line(yAxisGeo, axisMat));

    const zAxisGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, min), new THREE.Vector3(0, 0, max)]);
    axisGroup.add(new THREE.Line(zAxisGeo, axisMat));

    // Labels
    const labelScale = range / 30;
    xsMajor.forEach(x => {
      if (x !== 0 && Math.abs(x) > minor * 0.5) {
        const sprite = createTextSprite(formatNumber(x));
        sprite.position.set(x, -labelScale * 2, 0);
        sprite.scale.multiplyScalar(labelScale);
        labelGroup.add(sprite);
      }
    });
    zsMajor.forEach(z => {
      if (z !== 0 && Math.abs(z) > minor * 0.5) {
        const sprite = createTextSprite(formatNumber(z));
        sprite.position.set(0, -labelScale * 2, z);
        sprite.scale.multiplyScalar(labelScale);
        labelGroup.add(sprite);
      }
    });
    ysMajor.forEach(y => {
      if (y !== 0 && Math.abs(y) > minor * 0.5) {
        const sprite = createTextSprite(formatNumber(y));
        sprite.position.set(-labelScale * 2, y, 0);
        sprite.scale.multiplyScalar(labelScale);
        labelGroup.add(sprite);
      }
    });

    // Axis labels
    const xLabel = createTextSprite("X");
    xLabel.position.set(max * 0.95, -labelScale * 3, 0);
    xLabel.scale.multiplyScalar(labelScale * 1.2);
    labelGroup.add(xLabel);

    const zLabel = createTextSprite("Z");
    zLabel.position.set(0, -labelScale * 3, max * 0.95);
    zLabel.scale.multiplyScalar(labelScale * 1.2);
    labelGroup.add(zLabel);

    const yLabel = createTextSprite("Y");
    yLabel.position.set(-labelScale * 3, max * 0.95, 0);
    yLabel.scale.multiplyScalar(labelScale * 1.2);
    labelGroup.add(yLabel);
  }

  // === Animation Loop ===
  let lastRange = 0;
  function animate() {
    controls.update();
    const currentRange = getVisibleRange();
    if (Math.abs(currentRange - lastRange) / currentRange > 0.1) {
      render3D();
      lastRange = currentRange;
    }
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }

  window.addEventListener("resize", () => {
    const w = container.clientWidth, h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    render3D();
  });

  render3D();
  animate();

  // === INJECT_SPEC_HERE ===
})();
