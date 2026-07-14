// Minimal Three.js pump view. Exposes createPump3D(container) -> object with updatePumpFromJSON().
// This file is intended to be placed at static/js/pump3d.js
(function(){
  function createPump3D(container) {
    if (!container) throw new Error('container required');
    const width = container.clientWidth || 480;
    const height = container.clientHeight || 320;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // lights
    const ambient = new THREE.AmbientLight(0x808080);
    scene.add(ambient);
    const dir = new THREE.DirectionalLight(0xffffff, 0.6);
    dir.position.set(5, 10, 7.5);
    scene.add(dir);

    // pump body (cylinder)
    const bodyGeom = new THREE.CylinderGeometry(1.2, 1.2, 2.5, 32);
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x333333, metalness: 0.2, roughness: 0.6 });
    const body = new THREE.Mesh(bodyGeom, bodyMat);
    body.rotation.z = Math.PI / 2;
    scene.add(body);

    // rotating/pulsing element (status ring)
    const ringGeom = new THREE.TorusGeometry(0.8, 0.12, 16, 100);
    const ringMat = new THREE.MeshStandardMaterial({ color: 0x888888, emissive: 0x000000, emissiveIntensity: 0 });
    const ring = new THREE.Mesh(ringGeom, ringMat);
    ring.position.set(0, 0.75, 0);
    scene.add(ring);

    // small indicator light
    const lightGeom = new THREE.SphereGeometry(0.18, 16, 16);
    const lightMat = new THREE.MeshStandardMaterial({ color: 0x888888, emissive: 0x000000, emissiveIntensity: 0 });
    const light = new THREE.Mesh(lightGeom, lightMat);
    light.position.set(0, -0.9, 0.6);
    scene.add(light);

    camera.position.set(4, 2, 4);
    camera.lookAt(0, 0, 0);

    let lastState = { status: 'STOPPED', flow_rate_ml_h: null, phase: null };
    let pulsePhase = 0;

    function applyStatusStyle(status) {
      if (!status) status = 'STOPPED';
      if (status === 'RUNNING') {
        ringMat.color.setHex(0x00cc66);
        ringMat.emissive.setHex(0x00cc66);
        lightMat.color.setHex(0x00cc66);
        ringMat.emissiveIntensity = 0.6;
        lightMat.emissiveIntensity = 0.9;
      } else if (status && status.startsWith('ALARM')) {
        ringMat.color.setHex(0xcc0000);
        ringMat.emissive.setHex(0xcc0000);
        lightMat.color.setHex(0xcc0000);
        ringMat.emissiveIntensity = 0.1;
        lightMat.emissiveIntensity = 0.1;
      } else {
        ringMat.color.setHex(0x888888);
        ringMat.emissive.setHex(0x444444);
        lightMat.color.setHex(0x666666);
        ringMat.emissiveIntensity = 0.05;
        lightMat.emissiveIntensity = 0.05;
      }
    }

    function updateOverlay(state) {
      if (!state) return;
      const flowEl = document.getElementById('pump-flow');
      const phaseEl = document.getElementById('pump-phase');
      const statusEl = document.getElementById('pump-status');
      if (flowEl) flowEl.textContent = state.flow_rate_ml_h ?? '—';
      if (phaseEl) phaseEl.textContent = state.phase ?? '—';
      if (statusEl) statusEl.textContent = state.status ?? '—';
    }

    function updatePumpFromJSON(json) {
      const state = json && json.state ? json.state : json;
      if (!state) return;
      lastState = state;
      applyStatusStyle(state.status);
      updateOverlay(state);
    }

    function animate() {
      requestAnimationFrame(animate);
      ring.rotation.y += 0.02;
      pulsePhase += 0.08;
      if (lastState && lastState.status && lastState.status.startsWith('ALARM')) {
        const pulse = 0.5 + 0.5 * Math.abs(Math.sin(pulsePhase));
        ringMat.emissiveIntensity = 0.2 + pulse * 1.2;
        lightMat.emissiveIntensity = 0.2 + pulse * 1.8;
        ring.scale.set(1 + pulse * 0.03, 1 + pulse * 0.03, 1 + pulse * 0.03);
      } else {
        if (lastState && lastState.status === 'RUNNING') {
          const breath = 0.9 + 0.1 * Math.sin(pulsePhase / 2);
          ringMat.emissiveIntensity = 0.6 * breath;
        }
        ring.scale.lerp(new THREE.Vector3(1,1,1), 0.1);
      }
      renderer.render(scene, camera);
    }
    animate();

    let fallbackPoll = setInterval(async () => {
      try {
        const resp = await fetch('/data/infusions');
        if (!resp.ok) return;
        const data = await resp.json();
        const pumpState = Array.isArray(data) ? data[0] : data;
        updatePumpFromJSON(pumpState);
      } catch (e) {
      }
    }, 3000);

    return {
      updatePumpFromJSON,
      dispose: () => {
        clearInterval(fallbackPoll);
        renderer.dispose();
      }
    };
  }

  window.createPump3D = createPump3D;
})();
