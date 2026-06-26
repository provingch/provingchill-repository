(function () {
  const mount = document.getElementById("hero-seal");
  if (!mount || typeof THREE === "undefined") {
    return;
  }

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  mount.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
  camera.position.set(0, 0, 4.4);

  scene.add(new THREE.AmbientLight(0xffffff, 0.4));
  const keyLight = new THREE.PointLight(0xf4f4f2, 2.8, 24);
  keyLight.position.set(-3.5, 2.5, 4);
  scene.add(keyLight);
  const rimLight = new THREE.PointLight(0xffffff, 1.6, 24);
  rimLight.position.set(3.5, -2, 3);
  scene.add(rimLight);
  const fillLight = new THREE.PointLight(0xc9c9c6, 0.8, 20);
  fillLight.position.set(0, 3, -2);
  scene.add(fillLight);

  const group = new THREE.Group();
  scene.add(group);

  const geoIco = new THREE.IcosahedronGeometry(1.1, 2);
  const matIco = new THREE.MeshStandardMaterial({
    color: 0x18181a,
    metalness: 0.72,
    roughness: 0.22,
    emissive: 0x222224,
    emissiveIntensity: 0.35,
  });
  const icoMesh = new THREE.Mesh(geoIco, matIco);
  group.add(icoMesh);

  const geoWire = new THREE.IcosahedronGeometry(1.14, 2);
  const matWire = new THREE.MeshBasicMaterial({
    color: 0xf4f4f2,
    wireframe: true,
    transparent: true,
    opacity: 0.55,
  });
  const wireMesh = new THREE.Mesh(geoWire, matWire);
  group.add(wireMesh);

  const geoOuter = new THREE.IcosahedronGeometry(1.38, 1);
  const matOuter = new THREE.MeshBasicMaterial({
    color: 0xf4f4f2,
    wireframe: true,
    transparent: true,
    opacity: 0.12,
  });
  const outerMesh = new THREE.Mesh(geoOuter, matOuter);
  group.add(outerMesh);

  function makeRing(radius, tube, opacity, tiltX) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, tube, 8, 120),
      new THREE.MeshBasicMaterial({ color: 0xf4f4f2, transparent: true, opacity })
    );
    ring.rotation.x = tiltX;
    return ring;
  }

  const ringA = makeRing(1.72, 0.007, 0.35, Math.PI / 2.4);
  const ringB = makeRing(1.95, 0.004, 0.18, Math.PI / 3.8);
  group.add(ringA, ringB);

  const particleCount = 48;
  const particleGeo = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount; i += 1) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const radius = 1.55 + Math.random() * 0.55;
    positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = radius * Math.cos(phi);
  }
  particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const particles = new THREE.Points(
    particleGeo,
    new THREE.PointsMaterial({
      color: 0xf4f4f2,
      size: 0.035,
      transparent: true,
      opacity: 0.55,
      sizeAttenuation: true,
    })
  );
  group.add(particles);

  const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
  window.addEventListener("mousemove", (event) => {
    mouse.tx = (event.clientX / window.innerWidth - 0.5) * 2;
    mouse.ty = (event.clientY / window.innerHeight - 0.5) * 2;
  });

  function resize() {
    const size = mount.clientWidth || 220;
    renderer.setSize(size, size);
    camera.aspect = 1;
    camera.updateProjectionMatrix();
  }

  let frame = 0;
  function animate() {
    requestAnimationFrame(animate);
    frame += 0.006;

    mouse.x += (mouse.tx - mouse.x) * 0.04;
    mouse.y += (mouse.ty - mouse.y) * 0.04;

    group.rotation.x = frame * 0.35 + mouse.y * 0.18;
    group.rotation.y = frame * 0.45 + mouse.x * 0.18;

    outerMesh.rotation.x = -group.rotation.x * 0.6;
    outerMesh.rotation.y = group.rotation.y * 0.8 + frame * 0.15;

    ringA.rotation.z = frame * 0.28;
    ringB.rotation.z = -frame * 0.2;
    ringB.rotation.y = frame * 0.12;

    particles.rotation.y = frame * 0.08;
    particles.rotation.x = frame * 0.05;

    keyLight.intensity = 2.6 + Math.sin(frame * 2.2) * 0.25;

    renderer.render(scene, camera);
  }

  resize();
  animate();
  window.addEventListener("resize", resize);

  document.querySelectorAll(".reveal").forEach((el, index) => {
    el.style.transitionDelay = `${index * 90}ms`;
    requestAnimationFrame(() => el.classList.add("visible"));
  });
})();
