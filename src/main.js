import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const $ = (s) => document.querySelector(s);
const TAU = Math.PI * 2;
const rng = (() => { let a = 1337; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; })();
const rand = (a, b) => a + rng() * (b - a);
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const lerp = THREE.MathUtils.lerp;
const clamp = THREE.MathUtils.clamp;

// ------------------------------------------------------------------ renderer / cena
const canvas = $('#c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
const PR_MAX = Math.min(devicePixelRatio, 1.5); let prScale = 1;   // resolucao adaptativa: cai sozinha se o FPS ficar baixo
renderer.setPixelRatio(PR_MAX);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.VSMShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.12;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.3, 500);
scene.fog = new THREE.Fog(0xbfe9ff, 55, 160);

const hemi = new THREE.HemisphereLight(0xd8e9ff, 0xa8d98a, 1);
const sun = new THREE.DirectionalLight(0xfff4e0, 1.6);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -34, right: 34, top: 34, bottom: -34, near: 1, far: 140 });
sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03; sun.shadow.radius = 5; sun.shadow.blurSamples = 12;
if ('intensity' in sun.shadow) sun.shadow.intensity = 0.8;
scene.add(hemi, sun, sun.target);
{ const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.35; }

const mainRT = new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, samples: 4 });
mainRT.depthTexture = new THREE.DepthTexture(2, 2); mainRT.depthTexture.type = THREE.UnsignedIntType;
const composer = new EffectComposer(renderer, mainRT);
const bloom = new UnrealBloomPass(new THREE.Vector2(512, 512), 0.3, 0.35, 0.95);
const dofPass = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, tDepth: { value: null }, cameraNear: { value: 0.3 }, cameraFar: { value: 500 },
    focus: { value: 10.5 }, maxBlur: { value: 4.0 }, texel: { value: new THREE.Vector2(1 / 1024, 1 / 1024) } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D tDiffuse; uniform sampler2D tDepth; uniform float cameraNear, cameraFar, focus, maxBlur; uniform vec2 texel; varying vec2 vUv;
    float linZ(float d){ float z = d * 2.0 - 1.0; return (2.0 * cameraNear * cameraFar) / (cameraFar + cameraNear - z * (cameraFar - cameraNear)); }
    float coc(float z){ // desfoque so no fundo (e leve no primeiro plano muito proximo)
      float far = smoothstep(focus + 12.0, focus + 45.0, z);
      float near = smoothstep(focus * 0.4, focus * 0.22, z) * 0.4;
      return max(far, near);
    }
    void main(){
      float zc = linZ(texture2D(tDepth, vUv).r);
      float c = coc(zc);
      vec4 base = texture2D(tDiffuse, vUv);
      if (c < 0.01) { gl_FragColor = base; return; }
      vec4 sum = base; float tot = 1.0;
      for (int i = 0; i < 20; i++) {
        float a = float(i) * 2.39996; float r = sqrt((float(i) + 0.5) / 20.0);
        vec2 o = vec2(cos(a), sin(a)) * r * c * maxBlur * texel;
        float zs = linZ(texture2D(tDepth, vUv + o).r);
        float w = (zs < zc - 1.0) ? coc(zs) : 1.0; // evita que o personagem nitido "vaze" no fundo
        sum += texture2D(tDiffuse, vUv + o) * w; tot += w;
      }
      gl_FragColor = sum / tot;
    }`,
});
const gradePass = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, uSat: { value: 1.04 }, uTint: { value: new THREE.Vector3(1.01, 1.0, 0.985) }, uContrast: { value: 1.0 }, uLift: { value: 0.05 }, uVig: { value: 0.1 }, uSharp: { value: 0.55 }, texel: { value: new THREE.Vector2(1 / 1024, 1 / 1024) } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uSat, uContrast, uLift, uVig, uSharp; uniform vec3 uTint; uniform vec2 texel; varying vec2 vUv;
    void main(){
      vec3 c = texture2D(tDiffuse, vUv).rgb;
      // nitidez (unsharp mask leve)
      vec3 nb = texture2D(tDiffuse, vUv + vec2(texel.x, 0.0)).rgb + texture2D(tDiffuse, vUv - vec2(texel.x, 0.0)).rgb
              + texture2D(tDiffuse, vUv + vec2(0.0, texel.y)).rgb + texture2D(tDiffuse, vUv - vec2(0.0, texel.y)).rgb;
      c = clamp(c + (c - nb * 0.25) * uSharp, 0.0, 1.0);
      float l = dot(c, vec3(0.299, 0.587, 0.114));
      c = mix(vec3(l), c, uSat) * uTint;
      c = (c - 0.5) * uContrast + 0.5; c = c * (1.0 - uLift) + uLift; // contraste e pretos levantados (tom pastel)
      float v = smoothstep(0.95, 0.3, distance(vUv, vec2(0.5)));
      c *= mix(1.0 - uVig, 1.0, v);
      gl_FragColor = vec4(c, 1.0);
    }`,
});
const aoPass = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, tDepth: { value: null }, cameraNear: { value: 0.3 }, cameraFar: { value: 500 },
    uStrength: { value: 0.6 }, uRadius: { value: 0.55 }, uFocal: { value: 800 }, texel: { value: new THREE.Vector2(1 / 1024, 1 / 1024) }, uRes: { value: new THREE.Vector2(1024, 1024) } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D tDiffuse; uniform sampler2D tDepth; uniform float cameraNear, cameraFar, uStrength, uRadius, uFocal; uniform vec2 texel, uRes; varying vec2 vUv;
    float linZ(float d){ float z = d * 2.0 - 1.0; return (2.0 * cameraNear * cameraFar) / (cameraFar + cameraNear - z * (cameraFar - cameraNear)); }
    float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    void main(){
      vec4 col = texture2D(tDiffuse, vUv);
      float zc = linZ(texture2D(tDepth, vUv).r);
      if (zc > 70.0) { gl_FragColor = col; return; }
      float wc = 1.0 / zc;                                   // 1/z e linear na tela para superficies planas
      float rpx = min(uRadius * uFocal / zc, 42.0);
      float ang = hash(floor(vUv * uRes)) * 6.2831, occ = 0.0;
      for (int i = 0; i < 6; i++) {
        float a = ang + float(i) * 2.39996, r = sqrt((float(i) + 0.5) / 6.0) * rpx;
        vec2 o = vec2(cos(a), sin(a)) * r * texel;
        float z1 = linZ(texture2D(tDepth, vUv + o).r), z2 = linZ(texture2D(tDepth, vUv - o).r);
        float crease = ((1.0 / z1 + 1.0 / z2) * 0.5 - wc) / wc;   // concavidade (cantos, contato) e ignora planos
        float near = 1.0 - smoothstep(0.8, 2.0, max(abs(z1 - zc), abs(z2 - zc)));
        occ += smoothstep(0.003, 0.05, crease) * near;
      }
      occ /= 6.0;
      col.rgb *= 1.0 - uStrength * occ;
      gl_FragColor = col;
    }`,
});
const outlinePass = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, tDepth: { value: null }, cameraNear: { value: 0.3 }, cameraFar: { value: 500 },
    texel: { value: new THREE.Vector2(1 / 1024, 1 / 1024) }, uStrength: { value: 0.62 }, uWidth: { value: 1.0 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D tDiffuse; uniform sampler2D tDepth; uniform float cameraNear, cameraFar, uStrength, uWidth; uniform vec2 texel; varying vec2 vUv;
    float linZ(float d){ float z = d * 2.0 - 1.0; return (2.0 * cameraNear * cameraFar) / (cameraFar + cameraNear - z * (cameraFar - cameraNear)); }
    float W(vec2 o){ return 1.0 / linZ(texture2D(tDepth, vUv + o * texel * uWidth).r); }
    void main(){
      vec4 col = texture2D(tDiffuse, vUv);
      float zc = linZ(texture2D(tDepth, vUv).r);
      float wc = 1.0 / zc;
      // Laplaciano de 1/z (linear na tela para superficies planas): so acende em bordas/silhuetas
      float lap = abs(4.0 * wc - W(vec2(1, 0)) - W(vec2(-1, 0)) - W(vec2(0, 1)) - W(vec2(0, -1)));
      float lapD = abs(4.0 * wc - W(vec2(1, 1)) - W(vec2(-1, -1)) - W(vec2(-1, 1)) - W(vec2(1, -1))) * 0.5;
      float e = smoothstep(0.015, 0.05, max(lap, lapD) / wc);
      float fade = 1.0 - smoothstep(26.0, 60.0, zc);          // contorno some aos poucos ao longe
      vec3 ink = col.rgb * vec3(0.32, 0.27, 0.3);              // tinta: tom escuro da propria cor (nao preto chapado)
      col.rgb = mix(col.rgb, ink, e * fade * uStrength);
      gl_FragColor = col;
    }`,
});
composer.addPass(new RenderPass(scene, camera)); composer.addPass(aoPass); composer.addPass(outlinePass); composer.addPass(bloom); composer.addPass(new OutputPass()); composer.addPass(gradePass);

// "mundo curvo" estilo planetinha: o horizonte desce com a distância
function bend(m) {
  if (m.userData.bent) return m;
  m.userData.bent = true;
  m.onBeforeCompile = (s) => {
    s.vertexShader = s.vertexShader.replace('#include <project_vertex>',
      `#include <project_vertex>
       mvPosition.y -= mvPosition.z * mvPosition.z * 0.0011 + mvPosition.x * mvPosition.x * 0.0004;
       gl_Position = projectionMatrix * mvPosition;`);
  };
  return m;
}

// ------------------------------------------------------------------ texturas procedurais (estilo "cozy")
function wrapDraw(g, x, y, r, fn) { for (const ox of [-512, 0, 512]) for (const oy of [-512, 0, 512]) { g.save(); g.translate(ox, oy); fn(); g.restore(); } }
function makeTex(base, blobs, speck, repeat) {
  const c = document.createElement('canvas'); c.width = c.height = 512; const g = c.getContext('2d');
  g.fillStyle = base; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 240; i++) {
    const x = Math.random() * 512, y = Math.random() * 512, r = 20 + Math.random() * 55;
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    grd.addColorStop(0, blobs[i % blobs.length]); grd.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grd; wrapDraw(g, x, y, r, () => g.fillRect(x - r, y - r, r * 2, r * 2));
  }
  g.strokeStyle = speck; g.lineWidth = 2; g.lineCap = 'round';
  for (let i = 0; i < 520; i++) { const x = Math.random() * 512, y = Math.random() * 512; g.beginPath(); g.moveTo(x, y); g.lineTo(x + rand(-3, 3), y - rand(5, 11)); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; t.repeat.set(repeat, repeat);
  return t;
}
function acGroundTex(base, light, dark) {
  const S = 1024, c = document.createElement('canvas'); c.width = c.height = S; const g = c.getContext('2d');
  g.fillStyle = base; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 70; i++) { // manchas largas e suaves
    const x = Math.random() * S, y = Math.random() * S, r = 80 + Math.random() * 160, gr = g.createRadialGradient(x, y, 0, x, y, r);
    gr.addColorStop(0, i % 2 ? 'rgba(255,255,170,.13)' : 'rgba(40,150,90,.10)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr;
    for (const ox of [-S, 0, S]) for (const oy of [-S, 0, S]) g.fillRect(x - r + ox, y - r + oy, r * 2, r * 2);
  }
  for (let i = 0; i < 1500; i++) { // triângulos de grama
    const x = Math.random() * S, y = Math.random() * S, s = 9 + Math.random() * 12, a = Math.random() * TAU;
    g.fillStyle = Math.random() < 0.7 ? light : dark;
    for (const ox of [-S, 0, S]) for (const oy of [-S, 0, S]) {
      g.beginPath(); for (let k = 0; k < 3; k++) { const aa = a + k * TAU / 3; g.lineTo(x + ox + Math.cos(aa) * s, y + oy + Math.sin(aa) * s); } g.closePath(); g.fill();
    }
  }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 16; return t;
}
const grassTex = acGroundTex('#79c85f', 'rgba(158,222,112,.55)', 'rgba(88,172,84,.45)');
const sandTex = makeTex('#f6e3ac', ['rgba(255,244,205,.4)', 'rgba(230,200,140,.25)'], 'rgba(200,170,110,.25)', 1);
const shadowTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d'); const gr = g.createRadialGradient(32, 32, 2, 32, 32, 32); gr.addColorStop(0, 'rgba(40,60,30,.45)'); gr.addColorStop(1, 'rgba(40,60,30,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); })();
const shadowMat = bend(new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }));
const shadowGeo = new THREE.CircleGeometry(1, 20).rotateX(-Math.PI / 2);
function addShadow(x, z, r, parent = scene) { const m = new THREE.Mesh(shadowGeo, shadowMat); m.position.set(x, 0.06, z); m.scale.setScalar(r); m.visible = false; parent.add(m); return m; }

// ------------------------------------------------------------------ mundo: ilha, praia, mar
function disc(radius, mat, y, rings = 40) {
  const g = new THREE.RingGeometry(0, radius, 96, rings).rotateX(-Math.PI / 2);
  const p = g.attributes.position, uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i) * 0.08, p.getZ(i) * 0.08);
  const m = new THREE.Mesh(g, bend(mat)); m.position.y = y; m.receiveShadow = true; scene.add(m); return m;
}
const ocean = disc(260, new THREE.MeshLambertMaterial({ color: 0x78d6ea }), -0.7, 60);
const beach = disc(60, new THREE.MeshLambertMaterial({ map: sandTex }), -0.12);
// ---- chão estilo AC: shader procedural em coordenadas de mundo (cor em manchas, triângulos de grama, terra com borda irregular)
const pathCanvas = document.createElement('canvas'); pathCanvas.width = pathCanvas.height = 1024;
const pctx = pathCanvas.getContext('2d'); pctx.fillStyle = '#000'; pctx.fillRect(0, 0, 1024, 1024);
const w2c = (v) => (v + 60) / 120 * 1024;
function paintDirt(x, z, r) { pctx.fillStyle = '#fff'; pctx.beginPath(); pctx.arc(w2c(x), w2c(z), r / 120 * 1024, 0, TAU); pctx.fill(); }
const pathTex = new THREE.CanvasTexture(pathCanvas); pathTex.flipY = false;
function finishDirt() { // suaviza a máscara e envia para a GPU
  const tmp = document.createElement('canvas'); tmp.width = tmp.height = 1024; const t = tmp.getContext('2d');
  t.filter = 'blur(5px)'; t.drawImage(pathCanvas, 0, 0); pctx.clearRect(0, 0, 1024, 1024); pctx.drawImage(tmp, 0, 0); pathTex.needsUpdate = true;
}
// Textura de detalhe da grama (estilo ACNH: grama "pintada" com fios curtos, sem cara de cor lisa).
// Dado codificado: R = luminância do fio, G = desvio de matiz (amarelado ↔ azulado). Repete sem emenda.
const grassDetail = (() => {
  const S = 1024, c = document.createElement('canvas'); c.width = c.height = S; const g = c.getContext('2d');
  g.fillStyle = 'rgb(128,100,0)'; g.fillRect(0, 0, S, S);
  const wrap = (x, y, pad, fn) => { for (const ox of [-S, 0, S]) for (const oy of [-S, 0, S]) { if ((ox && Math.abs(x + ox - S / 2) > S / 2 + pad) || (oy && Math.abs(y + oy - S / 2) > S / 2 + pad)) continue; fn(x + ox, y + oy); } };
  for (let i = 0; i < 420; i++) { // tufos/manchas suaves
    const x = Math.random() * S, y = Math.random() * S, r = 18 + Math.random() * 60, L = Math.random() < 0.5 ? 70 : 190;
    wrap(x, y, r, (px, py) => { const gr = g.createRadialGradient(px, py, 0, px, py, r); gr.addColorStop(0, `rgba(${L},${80 + Math.random() * 90},0,.28)`); gr.addColorStop(1, `rgba(${L},100,0,0)`); g.fillStyle = gr; g.fillRect(px - r, py - r, r * 2, r * 2); });
  }
  g.lineCap = 'round';
  const layers = [[18000, 55, 105, 2.4], [20000, 110, 165, 2.0], [9000, 175, 230, 1.6]]; // sombra → meio → brilho
  for (const [n, l0, l1, w] of layers) {
    for (let i = 0; i < n; i++) {
      const x = Math.random() * S, y = Math.random() * S, len = 5 + Math.random() * 9, a = Math.random() * TAU, bendK = (Math.random() - 0.5) * 0.9;
      const L = l0 + Math.random() * (l1 - l0), H = 30 + Math.random() * 190;
      g.strokeStyle = `rgba(${L | 0},${H | 0},0,${0.55 + Math.random() * 0.4})`; g.lineWidth = w * (0.7 + Math.random() * 0.6);
      wrap(x, y, 16, (px, py) => {
        const ex = px + Math.cos(a) * len, ey = py + Math.sin(a) * len, mx = (px + ex) / 2 - Math.sin(a) * len * bendK * 0.5, my = (py + ey) / 2 + Math.cos(a) * len * bendK * 0.5;
        g.beginPath(); g.moveTo(px, py); g.quadraticCurveTo(mx, my, ex, ey); g.stroke();
      });
    }
  }
  const d = g.getImageData(0, 0, S, S).data; let sum = 0; for (let i = 0; i < d.length; i += 64) sum += d[i]; const mean = sum / (d.length / 64) / 255;
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 16; t.colorSpace = THREE.NoColorSpace;
  return { tex: t, mean };
})();

// Textura de detalhe da terra (estilo ACNH: granulado fino de pontinhos claros/escuros + pedrinhas raras). R = luminância.
const dirtDetail = (() => {
  const S = 1024, c = document.createElement('canvas'); c.width = c.height = S; const g = c.getContext('2d');
  g.fillStyle = 'rgb(128,128,128)'; g.fillRect(0, 0, S, S);
  const wrap = (x, y, pad, fn) => { for (const ox of [-S, 0, S]) for (const oy of [-S, 0, S]) { if ((ox && Math.abs(x + ox - S / 2) > S / 2 + pad) || (oy && Math.abs(y + oy - S / 2) > S / 2 + pad)) continue; fn(x + ox, y + oy); } };
  for (let i = 0; i < 300; i++) { // manchas suaves
    const x = Math.random() * S, y = Math.random() * S, r = 25 + Math.random() * 90, L = Math.random() < 0.5 ? 85 : 175;
    wrap(x, y, r, (px, py) => { const gr = g.createRadialGradient(px, py, 0, px, py, r); gr.addColorStop(0, `rgba(${L},${L},${L},.22)`); gr.addColorStop(1, `rgba(${L},${L},${L},0)`); g.fillStyle = gr; g.fillRect(px - r, py - r, r * 2, r * 2); });
  }
  for (let i = 0; i < 60000; i++) { // granulado
    const x = Math.random() * S, y = Math.random() * S, r = 1.2 + Math.random() * 2.6, light = Math.random() < 0.55;
    const L = light ? 175 + Math.random() * 70 : 45 + Math.random() * 60;
    g.fillStyle = `rgba(${L | 0},${L | 0},${L | 0},${0.3 + Math.random() * 0.45})`;
    wrap(x, y, 6, (px, py) => { g.beginPath(); g.ellipse(px, py, r, r * (0.6 + Math.random() * 0.4), Math.random() * TAU, 0, TAU); g.fill(); });
  }
  for (let i = 0; i < 260; i++) { // pedrinhas: corpo claro + sombra embaixo
    const x = Math.random() * S, y = Math.random() * S, r = 3.5 + Math.random() * 4, a = Math.random() * TAU;
    wrap(x, y, 12, (px, py) => {
      g.fillStyle = 'rgba(40,40,40,.45)'; g.beginPath(); g.ellipse(px + 1.2, py + 1.6, r, r * 0.75, a, 0, TAU); g.fill();
      g.fillStyle = 'rgba(205,205,205,.85)'; g.beginPath(); g.ellipse(px, py, r, r * 0.75, a, 0, TAU); g.fill();
    });
  }
  const d = g.getImageData(0, 0, S, S).data; let sum = 0; for (let i = 0; i < d.length; i += 64) sum += d[i]; const mean = sum / (d.length / 64) / 255;
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 16; t.colorSpace = THREE.NoColorSpace;
  return { tex: t, mean };
})();

const GROUND = {
  uDirtTex: { value: dirtDetail.tex }, uDirtMean: { value: dirtDetail.mean }, uDirtL: { value: new THREE.Color('#e7d3a8') },
  uPath: { value: pathTex },
  uGrass: { value: grassDetail.tex }, uMeanL: { value: grassDetail.mean },
  uG1: { value: new THREE.Color('#8dbb5a') }, uG2: { value: new THREE.Color('#b2c268') }, uG3: { value: new THREE.Color('#6fa253') },
  uTriL: { value: new THREE.Color('#d6df8f') }, uTriD: { value: new THREE.Color('#6da64f') },
  uDirt: { value: new THREE.Color('#d2b27f') }, uDirt2: { value: new THREE.Color('#b8925e') },
};
const groundMat = new THREE.MeshLambertMaterial({ color: 0xffffff });
groundMat.userData.bent = true;
groundMat.onBeforeCompile = (s) => {
  Object.assign(s.uniforms, GROUND);
  s.vertexShader = 'varying vec3 vWP;\n' + s.vertexShader
    .replace('#include <begin_vertex>', '#include <begin_vertex>\n vWP = (modelMatrix * vec4(position, 1.0)).xyz;')
    .replace('#include <project_vertex>', `#include <project_vertex>
       mvPosition.y -= mvPosition.z * mvPosition.z * 0.0011 + mvPosition.x * mvPosition.x * 0.0004;
       gl_Position = projectionMatrix * mvPosition;`);
  s.fragmentShader = `varying vec3 vWP; uniform sampler2D uPath; uniform sampler2D uGrass; uniform float uMeanL; uniform sampler2D uDirtTex; uniform float uDirtMean; uniform vec3 uDirtL; uniform vec3 uG1, uG2, uG3, uTriL, uTriD, uDirt, uDirt2;
    float h21(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
    vec2 h22(vec2 p){ float n = h21(p); return vec2(n, h21(p + n * 17.0)); }
    float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
      return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y); }
    float fbm2(vec2 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * vnoise(p); p = p * 2.03 + 7.1; a *= 0.5; } return s; }
    float sdTri(vec2 p, float r){ const float k = 1.7320508; p.x = abs(p.x) - r; p.y = p.y + r / k;
      if (p.x + k * p.y > 0.0) p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0; p.x -= clamp(p.x, -2.0 * r, 0.0); return -length(p) * sign(p.y); }
    float triLayer(vec2 wp, float cell, float dens, float reg, out float kind){
      vec2 id = floor(wp / cell); float best = 0.0; kind = 0.0;
      for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
        vec2 c = id + vec2(float(x), float(y));
        if (h21(c + 0.37) > dens) continue;
        vec2 ctr = (c + 0.15 + 0.7 * h22(c + 7.1)) * cell;
        float ang = h21(c + 3.3) * 6.2831, sz = cell * (0.1 + 0.06 * h21(c + 9.7));
        vec2 q = wp - ctr; float cs = cos(ang), sn = sin(ang); q = mat2(cs, -sn, sn, cs) * q;
        float d = sdTri(q, sz); float aa = fwidth(d) * 1.2; float m = 1.0 - smoothstep(-aa, aa, d);
        m *= mix(0.3, 0.8, reg) * (0.6 + 0.4 * h21(c + 5.9));
        if (m > best) { best = m; kind = h21(c + 1.7); }
      }
      return best;
    }
    ` + s.fragmentShader.replace('#include <map_fragment>', `
      vec2 p = vWP.xz;
      float n1 = fbm2(p * 0.05), n2 = fbm2(p * 0.17 + 13.0);
      // 1) cor de base em manchas grandes
      vec3 col = mix(uG1, uG2, smoothstep(0.38, 0.72, n1));
      col = mix(col, uG3, smoothstep(0.52, 0.8, n2) * 0.45);
      // 2) fios de grama pintados, em duas escalas/ângulos (quebra a repetição)
      vec2 dA = texture2D(uGrass, p / 3.4).rg;
      vec2 dB = texture2D(uGrass, mat2(0.8, -0.6, 0.6, 0.8) * p / 5.1 + 0.37).rg;
      vec2 dt = mix(dA, dB, smoothstep(0.35, 0.65, fbm2(p * 0.15 + 4.0)));
      col = mix(col * vec3(0.9, 1.0, 1.05), col * vec3(1.12, 1.05, 0.78), dt.g);
      col *= 1.0 + (dt.r - uMeanL) * 0.95;
      // 3) padrão de formas semitransparente, mais denso em certas regiões
      float reg = smoothstep(0.3, 0.72, fbm2(p * 0.07 + 21.0));
      float kind; float tri = triLayer(p, 0.75, mix(0.45, 0.85, reg), reg, kind);
      float fade = 1.0 - smoothstep(0.04, 0.25, fwidth(p.x));
      vec3 shapeCol = kind > 0.22 ? mix(col * 1.3, uTriL, 0.55) : col * 0.82;
      col = mix(col, shapeCol, tri * fade);
      float pm = texture2D(uPath, (p + 60.0) / 120.0).r;
      float edge = pm + (fbm2(p * 1.4) - 0.5) * 0.3 + (vnoise(p * 7.0) - 0.5) * 0.22 + (vnoise(p * 17.0) - 0.5) * 0.12; // borda serrilhada
      float dirt = smoothstep(0.44, 0.52, edge);
      float rim = smoothstep(0.3, 0.44, edge) * (1.0 - dirt);
      col *= 1.0 + rim * 0.1; // pontas da grama mais claras na borda
      // terra: tom dourado em manchas grandes + manchas médias claras + granulado fino em duas escalas
      vec3 dc = mix(uDirt, uDirt2, smoothstep(0.35, 0.78, fbm2(p * 0.22 + 3.0)) * 0.65);
      dc = mix(dc, uDirtL, smoothstep(0.55, 0.85, fbm2(p * 0.9 + 11.0)) * 0.4);
      float dgA = texture2D(uDirtTex, p / 2.2).r, dgB = texture2D(uDirtTex, mat2(0.6, -0.8, 0.8, 0.6) * p / 3.1 + 0.21).r;
      float dg = mix(dgA, dgB, smoothstep(0.35, 0.65, fbm2(p * 0.3 + 9.0)));
      dc *= 1.0 + (dg - uDirtMean) * 1.25;
      float lip = dirt * (1.0 - smoothstep(0.5, 0.68, edge)); // a grama é mais alta: projeta sombra na terra
      dc *= 1.0 - 0.3 * lip;
      col = mix(col, dc, dirt);
      diffuseColor.rgb *= col;`);
};
disc(54, groundMat, 0);
const foam = disc(63, new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55 }), -0.5, 6);

const POND = { x: 6, z: 17, r: 6 };
const pondSand = new THREE.Mesh(new THREE.CircleGeometry(POND.r + 1.1, 48).rotateX(-Math.PI / 2), bend(new THREE.MeshLambertMaterial({ map: sandTex })));
pondSand.position.set(POND.x, 0.02, POND.z); scene.add(pondSand);
const pondMat = bend(new THREE.MeshLambertMaterial({ color: 0x6fd0f0, transparent: true, opacity: 0.92 }));
const pond = new THREE.Mesh(new THREE.CircleGeometry(POND.r, 48).rotateX(-Math.PI / 2), pondMat);
pond.position.set(POND.x, 0.05, POND.z); pond.receiveShadow = true; scene.add(pond);
for (let i = 0; i < 5; i++) { // vitórias-régias
  const a = rand(0, TAU), d = rand(1, 4);
  const lp = new THREE.Mesh(new THREE.CircleGeometry(rand(0.35, 0.55), 12).rotateX(-Math.PI / 2), bend(new THREE.MeshLambertMaterial({ color: 0x5fbf6a })));
  lp.position.set(POND.x + Math.cos(a) * d, 0.07, POND.z + Math.sin(a) * d); scene.add(lp);
}

// céu em degradê: segue a câmera, sem névoa
const skyUniforms = { uTop: { value: new THREE.Color('#5fb8f5') }, uHorizon: { value: new THREE.Color('#d6eefc') }, uSunDir: { value: new THREE.Vector3(0, 1, 0) }, uSunCol: { value: new THREE.Color('#fff4d8') }, uGlow: { value: 1 } };
const skyDome = new THREE.Mesh(new THREE.SphereGeometry(320, 32, 16), new THREE.ShaderMaterial({
  uniforms: skyUniforms, side: THREE.BackSide, depthWrite: false, fog: false,
  vertexShader: 'varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform vec3 uTop, uHorizon, uSunDir, uSunCol; uniform float uGlow; varying vec3 vP;
    void main(){
      vec3 d = normalize(vP); float h = d.y; float t = smoothstep(-0.02, 0.45, h);
      vec3 c = mix(uHorizon, uTop, t);
      float sd = max(dot(d, normalize(uSunDir)), 0.0);
      c += uSunCol * (pow(sd, 6.0) * 0.35 + pow(sd, 60.0) * 0.6 + smoothstep(0.9993, 0.9997, sd) * 1.2) * uGlow; // halo + disco
      gl_FragColor = vec4(c, 1.0);
    }`,
}));
skyDome.renderOrder = -10; scene.add(skyDome);

// nuvens
const clouds = [];
const cloudMat = bend(new THREE.MeshLambertMaterial({ color: 0xffffff, transparent: true, opacity: 0.95 }));
for (let i = 0; i < 12; i++) {
  const g = new THREE.Group();
  for (let k = 0; k < 4; k++) { const s = new THREE.Mesh(new THREE.SphereGeometry(rand(3, 5), 12, 8), cloudMat); s.position.set(k * 3.5 - 5, rand(-.5, 1), rand(-1, 1)); s.scale.y = 0.6; g.add(s); }
  g.position.set(rand(-120, 120), rand(28, 40), rand(-120, 60)); scene.add(g); clouds.push(g);
}
// estrelas
const starGeo = new THREE.BufferGeometry();
{ const a = []; for (let i = 0; i < 350; i++) { const u = rand(0, TAU), v = rand(0.1, 1.4); a.push(Math.cos(u) * Math.cos(v) * 200, Math.sin(v) * 200, Math.sin(u) * Math.cos(v) * 200); } starGeo.setAttribute('position', new THREE.Float32BufferAttribute(a, 3)); }
const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, transparent: true, opacity: 0, fog: false, depthWrite: false });
const stars = new THREE.Points(starGeo, starMat); scene.add(stars);

// ------------------------------------------------------------------ carregamento dos modelos feitos no Blender
const MODELS = ['villager_bear', 'villager_cat', 'villager_capy', 'tree_round', 'tree_fruit', 'tree_cedar', 'fruit_apple', 'fruit_orange', 'house_player', 'house_shop', 'house_neighbor', 'flower_white', 'flower_red', 'flower_yellow', 'flower_pink', 'flower_blue', 'weed', 'rock', 'bush', 'bench', 'lamp', 'sign'];
const tpl = {};
const BUILD = Date.now(); // evita cache antigo dos modelos ao recarregar
const loader = new GLTFLoader();
await Promise.all(MODELS.map((n) => loader.loadAsync(`assets/models/${n}.glb?v=${BUILD}`).then((g) => { tpl[n] = g.scene; })));
const inst = (n) => { const o = tpl[n].clone(true); o.traverse((c) => { if (c.isMesh) { c.material = bend(c.material); c.castShadow = c.receiveShadow = true; c.material.envMapIntensity = 1; } }); return o; };
let lampBulbMat = null;
tpl.lamp.traverse((c) => { if (c.isMesh && c.material.name === 'glow') lampBulbMat = c.material; });
if (lampBulbMat) lampBulbMat.emissive = new THREE.Color(0xffe27a);
for (const n of MODELS) tpl[n].traverse((c) => {
  if (c.isMesh && c.material.name.startsWith('leafcard') || c.isMesh && c.material.name === 'weedmat') {
    Object.assign(c.material, { alphaTest: 0.5, transparent: false, depthWrite: true, side: THREE.DoubleSide }); c.material.needsUpdate = true;
  }
});
const TITLE_READY = true;

// ------------------------------------------------------------------ colisores e posicionamento
const circles = [], boxes = [], noGo = [];
const free = (x, z, r) => !noGo.some((n) => Math.hypot(n.x - x, n.z - z) < n.r + r);
const place = (name, x, z, rot = 0, sc = 1, shadowR = 0) => { const o = inst(name); o.position.set(x, 0, z); o.rotation.y = rot; o.scale.setScalar(sc); scene.add(o); if (shadowR) addShadow(x, z, shadowR); return o; };

const HOUSES = {
  player: { x: -12, z: -12, model: 'house_player' },
  shop: { x: 13, z: -14, model: 'house_shop' },
  bear: { x: -22, z: 6, model: 'house_neighbor' },
  cat: { x: 22, z: 4, model: 'house_neighbor' },
  capy: { x: -13, z: 27, model: 'house_neighbor' },
};
for (const h of Object.values(HOUSES)) {
  const o = place(h.model, h.x, h.z, 0, 1.15, 3.6);
  if (h.model === 'house_neighbor') o.traverse((c) => { if (c.isMesh && c.material.name.startsWith('roofhouse_neighbor')) { c.material = c.material.clone(); c.material.color.set(h === HOUSES.cat ? 0x78b6ee : h === HOUSES.capy ? 0x8fcf8a : 0xb79ced); } });
  h.door = new THREE.Vector3(h.x, 0, h.z + 3.1);
  boxes.push({ x: h.x, z: h.z, hw: 2.1, hd: 1.9 });
  noGo.push({ x: h.x, z: h.z + 1.5, r: 5.2 });
}
noGo.push({ x: POND.x, z: POND.z, r: POND.r + 2.2 }, { x: 0, z: 0, r: 4.5 });
circles.push({ x: POND.x, z: POND.z, r: POND.r - 0.5 });

// caminhos de terra
function path(a, b) { // trilha levemente curva pintada na máscara do chão
  const n = Math.ceil(a.distanceTo(b) / 0.5), bendAmt = rand(-2.5, 2.5);
  const nx = -(b.z - a.z), nz = b.x - a.x, nl = Math.hypot(nx, nz) || 1;
  for (let i = 0; i <= n; i++) {
    const t = i / n, off = Math.sin(t * Math.PI) * bendAmt;
    const x = lerp(a.x, b.x, t) + nx / nl * off, z = lerp(a.z, b.z, t) + nz / nl * off;
    paintDirt(x, z, 0.7);
    if (i % 2 === 0) noGo.push({ x, z, r: 1.3 });
  }
}
const plaza = new THREE.Vector3(0, 0, 0);
for (const h of Object.values(HOUSES)) { path(h.door, plaza); paintDirt(h.door.x, h.door.z - 0.2, 1.4); }
paintDirt(0, 0, 3.0);
finishDirt();

// decoração fixa
const sign = place('sign', 3.2, -3.4, -0.3, 1.2, 0.7); circles.push({ x: 3.2, z: -3.4, r: 0.4 });
const bench = place('bench', -6.5, -5, 0, 1.3, 1.4); boxes.push({ x: -6.5, z: -5, hw: 1.0, hd: 0.45 });
const lamps = [];
for (const [x, z] of [[-4, -3], [5, -8], [-14, -4], [16, -7]]) { place('lamp', x, z, 0, 1, 0.6); circles.push({ x, z, r: 0.3 }); lamps.push(new THREE.Vector3(x, 2.15, z)); }
const lampLights = lamps.map((p) => { const l = new THREE.PointLight(0xffe0a0, 0, 12, 1.6); l.position.copy(p); scene.add(l); return l; });

// árvores
const trees = [];
function addTree(kind, x, z, fruitType = null) {
  const model = kind === 'fruit' ? 'tree_fruit' : kind === 'cedar' ? 'tree_cedar' : 'tree_round';
  const o = place(model, x, z, rand(0, TAU), rand(1.05, 1.35), kind === 'cedar' ? 1.6 : 2.2);
  o.userData.phase = rand(0, TAU);
  circles.push({ x, z, r: 0.7 }); noGo.push({ x, z, r: 2.3 });
  const t = { o, x, z, fruitType, fruit: [], shake: 0, regrow: 0, kind };
  if (fruitType) {
    for (let i = 0; i < 3; i++) {
      const f = inst(fruitType === 'apple' ? 'fruit_apple' : 'fruit_orange'); f.scale.setScalar(1.8);
      const a = i * TAU / 3 + 0.5; f.position.set(Math.cos(a) * 1.45, 2.15 + (i % 2) * 0.25, Math.sin(a) * 1.45);
      o.add(f); t.fruit.push(f);
    }
  }
  trees.push(t); return t;
}
const rpol = (rmin, rmax) => { const a = rand(0, TAU), r = rand(rmin, rmax); return [Math.cos(a) * r, Math.sin(a) * r]; };
function scatter(count, rmin, rmax, minGap, fn) {
  let tries = 0, n = 0;
  while (n < count && tries++ < 900) { const [x, z] = rpol(rmin, rmax); if (!free(x, z, minGap)) continue; fn(x, z); n++; }
}
scatter(3, 12, 40, 3, (x, z) => addTree('fruit', x, z, 'apple'));
scatter(3, 12, 40, 3, (x, z) => addTree('fruit', x, z, 'orange'));
scatter(13, 10, 44, 2.5, (x, z) => addTree('round', x, z));
scatter(18, 34, 49, 2, (x, z) => addTree('cedar', x, z));
scatter(8, 8, 40, 1.6, (x, z) => { place('bush', x, z, rand(0, TAU), rand(1, 1.4), 1.0); circles.push({ x, z, r: 0.6 }); noGo.push({ x, z, r: 1.2 }); });
scatter(7, 8, 46, 1.6, (x, z) => { place('rock', x, z, rand(0, TAU), rand(1, 1.6), 1.0); circles.push({ x, z, r: 0.7 }); noGo.push({ x, z, r: 1.3 }); });

// grama: lâminas curvas e afiladas, em tufos, com gradiente base→ponta e vento
const grassTime = { value: 0 };
{
  const pos = [], nor = [], colr = [], idx = [];
  const base = new THREE.Color(0x5a8c3a), tip = new THREE.Color(0xc4d476), c = new THREE.Color();
  const SEG = 4, BLADES = 9;
  for (let b = 0; b < BLADES; b++) {
    const ang = rng() * TAU, dist = rng() * 0.22, ox = Math.cos(ang) * dist, oz = Math.sin(ang) * dist;
    const face = rng() * TAU, ca = Math.cos(face), sa = Math.sin(face);
    const hgt = 0.22 + rng() * 0.3, wid = 0.022 + rng() * 0.014, lean = 0.1 + rng() * 0.35, tint = 0.85 + rng() * 0.3;
    const v0 = pos.length / 3;
    for (let i = 0; i <= SEG; i++) {
      const t = i / SEG, w = wid * (1 - t * t * 0.95), y = t * hgt, fwd = lean * t * t * hgt * 2.2;
      for (const side of [-1, 1]) {
        const lx = side * w, lz = fwd;
        pos.push(ox + lx * ca + lz * sa, y, oz - lx * sa + lz * ca);
        nor.push(0, 1, 0);
        c.copy(base).lerp(tip, Math.pow(t, 0.8)).multiplyScalar(tint); colr.push(c.r, c.g, c.b);
      }
    }
    for (let i = 0; i < SEG; i++) { const k = v0 + i * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(colr, 3)); g.setIndex(idx);
  const mat = bend(new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }));
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh) => {
    prev(sh); sh.uniforms.uTime = grassTime;
    sh.vertexShader = 'uniform float uTime;\n' + sh.vertexShader.replace('#include <begin_vertex>',
      `#include <begin_vertex>
       vec3 ip = vec3(0.0);
       #ifdef USE_INSTANCING
         ip = instanceMatrix[3].xyz;
       #endif
       float sway = position.y * position.y * 6.0;
       transformed.x += sin(uTime * 1.7 + ip.x * 0.45 + ip.z * 0.3) * 0.09 * sway;
       transformed.z += cos(uTime * 1.3 + ip.z * 0.4 + ip.x * 0.2) * 0.06 * sway;`);
  };
  const COUNT = 5200;
  const pdata = pctx.getImageData(0, 0, 1024, 1024).data;
  const maskAt = (x, z) => { const cx = Math.floor(w2c(x)), cz = Math.floor(w2c(z)); return cx < 0 || cz < 0 || cx > 1023 || cz > 1023 ? 0 : pdata[(cz * 1024 + cx) * 4] / 255; };
  const blocked = (x, z) => boxes.some((b) => Math.abs(x - b.x) < b.hw + 0.2 && Math.abs(z - b.z) < b.hd + 0.2) || Math.hypot(x - POND.x, z - POND.z) < POND.r + 1.3;
  const tuft = new THREE.InstancedMesh(g, mat, COUNT);
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), col = new THREE.Color();
  let n = 0, tries = 0;
  while (n < COUNT && tries++ < 400000) {
    const [x, z] = rpol(0, 52);
    const m = maskAt(x, z), border = m > 0.26 && m < 0.5; // franja na borda grama↔terra
    if (border ? blocked(x, z) : (n % 7 !== 0 || !free(x, z, 0.05))) continue;
    e.set(0, rand(0, TAU), 0); q.setFromEuler(e);
    m4.compose(new THREE.Vector3(x, 0, z), q, new THREE.Vector3().setScalar(border ? rand(0.3, 0.48) : rand(0.35, 0.55))); tuft.setMatrixAt(n, m4);
    tuft.setColorAt(n, col.setHSL(rand(.0, .05), rand(0, .25), rand(.88, 1.0)).setRGB(rand(.85, 1.1), rand(.9, 1.05), rand(.75, .95)));
    n++;
  }
  tuft.count = n; tuft.receiveShadow = true; tuft.frustumCulled = false; scene.add(tuft);
}

// coletáveis: flores e ervas
const pickups = [];
const FLOWERS = ['white', 'red', 'yellow', 'pink', 'blue'];
const FLOWER_NAMES = { white: 'branca', red: 'vermelha', yellow: 'amarela', pink: 'rosa', blue: 'azul' };
function addPickup(type, model, x, z, sc = 1, y = 0) {
  const o = place(model, x, z, rand(0, TAU), sc); o.position.y = y; o.userData.phase = rand(0, TAU);
  const p = { type, o, x, z, respawn: 0, baseSc: sc }; pickups.push(p); return p;
}
for (let patch = 0; patch < 9; patch++) {
  const [cx, cz] = rpol(8, 42); const col = pick(FLOWERS);
  for (let i = 0; i < 6; i++) { const x = cx + rand(-2.5, 2.5), z = cz + rand(-2.5, 2.5); if (free(x, z, 0.6) && Math.hypot(x, z) < 49) addPickup('flower_' + (Math.random() < 0.75 ? col : pick(FLOWERS)), 'flower_' + col, x, z, 1.5); }
}
// corrige o modelo para a cor sorteada
for (const p of pickups) { const col = p.type.split('_')[1]; p.o.removeFromParent(); p.o = place('flower_' + col, p.x, p.z, rand(0, TAU), 1.5); p.o.userData.phase = rand(0, TAU); p.type = 'flower_' + col; }
scatter(22, 4, 46, 1, (x, z) => addPickup('weed', 'weed', x, z, 1.5));

// ------------------------------------------------------------------ personagens
// ------------------------------------------------------------------ guarda-roupa: corpo-base + pecas (cada uma em seu .glb)
const WARD = await fetch(`assets/models/char2/wardrobe2.json?v=${BUILD}`).then((r) => r.json());
WARD.hairColors = { 'Castanho': '#7a4a2c', 'Preto': '#2b2523', 'Loiro': '#f0c35a', 'Laranja': '#f08a3c', 'Rosa': '#f49ac1', 'Azul': '#5d8fe0', 'Branco': '#f4f1ea' };
const CLOTH_COLORS = { 'Branco': '#f4f1ea', 'Azul': '#6fa8dc', 'Rosa': '#f49ac1', 'Laranja': '#f4a259', 'Verde': '#7cc57a', 'Amarelo': '#f2c94c', 'Roxo': '#a58bd8', 'Vermelho': '#d9534f', 'Bege': '#d8c39a', 'Cinza': '#8e939b', 'Preto': '#34343a' };
const PIECE_DEFAULT_COLOR = { hoodie: 'Branco', pants: 'Azul', shoes: 'Verde', bag: 'Azul' };
const PIVOTS = ['Root', 'Head', 'ArmL', 'ArmR', 'FootL', 'FootR'];
const pieceCache = {};
async function loadPiece(id) {
  if (!pieceCache[id]) { const it = WARD.items.find((i) => i.id === id); pieceCache[id] = (await loader.loadAsync(`${it.file}?v=${BUILD}`)).scene; }
  return pieceCache[id];
}
const DEFAULT_LOOK = { hair: 'hair_curto', hairColor: 'Castanho', top: 'top_moletom', bottom: 'bottom_calca', shoes: 'shoes_tenis', skin: 'Dourada', eyes: 'Castanho', blush: true, topColor: 'Branco', bottomColor: 'Azul', shoesColor: 'Verde', bag: false, bagColor: 'Azul' };
const SKIN_TONES = { 'Clara': '#f7d6bd', 'Pêssego': '#f2bb92', 'Dourada': '#e8955c', 'Morena': '#c47645', 'Canela': '#955732', 'Escura': '#653a24' };
const EYE_COLORS = { 'Castanho': '#5a3216', 'Preto': '#241c18', 'Azul': '#3f73cc', 'Verde': '#3a9a55', 'Cinza': '#7a8290', 'Mel': '#c08a2c' };
const BEND_GLSL = '';
const colorOf = (set, name, fallback) => new THREE.Color(set[name] || fallback);
function sanitizeLook(look) { // saves antigos podem apontar para pecas que nao existem mais
  const L = Object.assign({}, DEFAULT_LOOK, look || {});
  for (const k of ['hair', 'top', 'bottom', 'shoes']) if (!WARD.items.find((i) => i.id === L[k])) L[k] = DEFAULT_LOOK[k];
  if (!SKIN_TONES[L.skin]) L.skin = DEFAULT_LOOK.skin;
  if (!EYE_COLORS[L.eyes]) L.eyes = DEFAULT_LOOK.eyes;
  for (const k of ['topColor', 'bottomColor', 'shoesColor', 'bagColor']) if (!CLOTH_COLORS[L[k]]) L[k] = DEFAULT_LOOK[k];
  if (!WARD.hairColors[L.hairColor]) L.hairColor = DEFAULT_LOOK.hairColor;
  return L;
}
// recolore pelo NOME do material exportado pelo Blender (pele, iris, roupas, cabelo)
function tintMaterial(mat, look) {
  const n = mat.name;
  const skin = colorOf(SKIN_TONES, look.skin, '#e8955c');
  const map = {
    c2_skin: () => skin,
    c2_nose: () => skin.clone().multiplyScalar(0.93).offsetHSL(-0.005, 0.12, -0.02),
    c2_iris: () => colorOf(EYE_COLORS, look.eyes, '#5a3216'),
    c2_hair: () => colorOf(WARD.hairColors, look.hairColor, '#7a4a2c'),
    c2_hoodie: () => colorOf(CLOTH_COLORS, look.topColor, '#f4f1ea'),
    c2_pants: () => colorOf(CLOTH_COLORS, look.bottomColor, '#6fa8dc'),
    c2_shoe: () => colorOf(CLOTH_COLORS, look.shoesColor, '#7cc57a'),
    c2_bag: () => colorOf(CLOTH_COLORS, look.bagColor, '#6fa8dc'),
  };
  if (!map[n]) return mat;
  const m = mat.clone(); m.color.copy(map[n]()); return m;
}
async function buildAvatar(look) {
  // esqueleto compartilhado: corpo + roupas + cabelo sao malhas "skinned" presas aos MESMOS ossos (sem costuras ao mexer)
  const avatar = SkeletonUtils.clone(await loadPiece('body'));
  let skel = null; avatar.traverse((o) => { if (o.isSkinnedMesh && !skel) skel = o.skeleton; });
  look = sanitizeLook(look);
  const ids = [look.hair, look.top, look.bottom, look.shoes, look.bag ? 'acc_bolsa' : null].filter(Boolean);
  for (const id of ids) {
    const src = await loadPiece(id);
    src.traverse((o) => {
      if (!o.isSkinnedMesh) return;
      const m = new THREE.SkinnedMesh(o.geometry, o.material);
      m.name = o.name; m.bind(skel, o.bindMatrix); avatar.add(m);
    });
  }
  avatar.traverse((c) => {
    if (!c.isMesh) return;
    c.frustumCulled = false;
    c.material = tintMaterial(c.material, look);
    if (c.material.name === 'blush') { c.material = c.material.clone(); Object.assign(c.material, { transparent: true, opacity: 0.55, depthWrite: false }); c.visible = look.blush !== false; c.castShadow = false; }
    c.material = bend(c.material); c.castShadow = c.castShadow !== false && c.material.name !== 'blush'; c.receiveShadow = true;
  });
  return avatar;
}
const player = {
  obj: new THREE.Group(), pos: new THREE.Vector3(HOUSES.player.x + 1, 0, HOUSES.player.z + 5.5), vel: new THREE.Vector3(),
  face: Math.PI, walkT: 0, swing: 0, hit: false,
};
player.obj.scale.setScalar(1.05); scene.add(player.obj);
const pShadow = addShadow(0, 0, 0.9);
const rig = (o) => {
  const r = { armL: o.getObjectByName('ArmL'), armR: o.getObjectByName('ArmR'), footL: o.getObjectByName('FootL'), footR: o.getObjectByName('FootR'), head: o.getObjectByName('Head'), root: o.getObjectByName('Root'),
    kneeL: o.getObjectByName('KneeL'), kneeR: o.getObjectByName('KneeR'), ankleL: o.getObjectByName('AnkleL'), ankleR: o.getObjectByName('AnkleR'), elbowL: o.getObjectByName('ElbowL'), elbowR: o.getObjectByName('ElbowR') };
  // ossos exportados do Blender tem rotacao de repouso propria: guarda repouso + orientacao do pai (no referencial do avatar)
  o.updateMatrixWorld(true);
  for (const k of Object.keys(r)) {
    const b = r[k]; if (!b) continue;
    const u = b.userData; u.q0 = b.quaternion.clone(); u.p0 = b.position.clone();
    const chain = []; for (let n = b.parent; n && n !== o; n = n.parent) chain.push(n);
    const Wp = new THREE.Quaternion(); for (let i = chain.length - 1; i >= 0; i--) Wp.multiply(chain[i].quaternion);
    u.Wp = Wp; u.WpInv = Wp.clone().invert();
  }
  // comprimentos dos segmentos da perna (no referencial do avatar): coxa, canela e altura quadril->tornozelo em repouso
  if (r.footL && r.kneeL && r.ankleL) {
    const P = (b) => o.worldToLocal(b.getWorldPosition(new THREE.Vector3()));
    const h = P(r.footL), k = P(r.kneeL), a = P(r.ankleL);
    r.L1 = h.distanceTo(k); r.L2 = k.distanceTo(a); r.Hrest = h.y - a.y;
  }
  return r;
};
const _qa = new THREE.Quaternion(), _eu = new THREE.Euler(), _vv = new THREE.Vector3();
// rotacao e deslocamento expressos nos eixos do AVATAR (x lateral, y cima, z frente), somados ao repouso do osso
function setRot(b, x = 0, y = 0, z = 0) { const u = b.userData; _qa.setFromEuler(_eu.set(x, y, z)); b.quaternion.copy(u.WpInv).multiply(_qa).multiply(u.Wp).multiply(u.q0); }
function setPos(b, dx, dy, dz) { const u = b.userData; b.position.copy(u.p0).add(_vv.set(dx, dy, dz).applyQuaternion(u.WpInv)); }
async function equip(look) {
  const av = await buildAvatar(look);
  if (player.avatar) player.obj.remove(player.avatar);
  player.avatar = av; player.obj.add(av); player.rig = rig(av);
}

// rede de captura
const net = new THREE.Group();
{
  const wood = bend(new THREE.MeshLambertMaterial({ color: 0xb98550 }));
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 1.7, 8).rotateX(Math.PI / 2), wood); pole.position.z = 0.85; net.add(pole);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.035, 8, 20).rotateY(Math.PI / 2), bend(new THREE.MeshLambertMaterial({ color: 0xff9aa8 }))); ring.position.z = 2.05; net.add(ring);
  const mesh = new THREE.Mesh(new THREE.CircleGeometry(0.42, 20).rotateY(Math.PI / 2), bend(new THREE.MeshLambertMaterial({ color: 0xffffff, transparent: true, opacity: 0.4, side: THREE.DoubleSide }))); mesh.position.z = 2.05; net.add(mesh);
  net.position.set(0.55, 1.0, 0.1); net.visible = false; player.obj.add(net);
}

const LINES = {
  capy: [
    ['Ahh... oi. Tô de boa.', 'Quer sentar aqui comigo? Não precisa fazer nada.'],
    ['Esse yuzu na cabeça? Ele só... apareceu. Agora somos amigos.'],
    ['Já reparou como o lago fica bonito à tarde?', 'Eu podia ficar olhando pra sempre...'],
    ['Dizem que capivaras se dão bem com todo mundo.', 'Acho que é porque a gente não tem pressa.'],
    ['Se encontrar laranjas, me avisa. Combinam com o meu chapéu.'],
  ],
  bear: [
    ['Olá! Que dia lindo para um passeio, não é?'],
    ['Ouvi dizer que as laranjas estão madurinhas.', 'Sacuda a árvore e elas caem!'],
    ['Eu adoro tirar uma soneca debaixo daquelas árvores grandes...'],
    ['Já tentou pescar no lago?', 'Às vezes aparece um peixe ENORME!'],
    ['Venda o que coletar na loja, perto do caminho do leste.'],
  ],
  cat: [
    ['Miau~ Oi! Eu estava procurando flores novas pra minha casa.'],
    ['As borboletas só aparecem de dia.', 'Aperte Espaço pra balançar a rede!'],
    ['Esta ilha é tão tranquila... Por que as pessoas têm tanta pressa?'],
    ['Cuidado com as ervas daninhas. Elas crescem do nada!'],
    ['Uma flor no bolso deixa o dia mais bonito.'],
  ],
};
const NIGHT_LINES = { capy: ['Zzz... ah, oi. A noite é ótima pra boiar no lago...'], bear: ['Já está tão tarde... Olha só quantas estrelas!'], cat: ['Miau... estou com sono. Boa noite!'] };
const villagers = [];
function addVillager(id, model, name, house, pitch) {
  const o = inst(model); o.scale.setScalar(1.05);
  const home = new THREE.Vector3(house.x, 0, house.z + 6);
  o.position.copy(home); scene.add(o);
  const v = { id, name, o, rig: rig(o), home, pos: o.position, target: home.clone(), wait: rand(1, 4), walkT: 0, face: 0, pitch, shadow: addShadow(0, 0, 0.9), speed: 0 };
  villagers.push(v); return v;
}
addVillager('bear', 'villager_bear', 'Bento', HOUSES.bear, 150);
addVillager('cat', 'villager_cat', 'Mimi', HOUSES.cat, 360);
addVillager('capy', 'villager_capy', 'Capi', HOUSES.capy, 120);

// borboletas
const butterflies = [];
const bfWingGeo = new THREE.CircleGeometry(0.15, 10);
function addButterfly() {
  const g = new THREE.Group();
  const col = pick([0xffd24a, 0xff8fb8, 0x8ec5ff, 0xffffff]);
  const mat = bend(new THREE.MeshLambertMaterial({ color: col, side: THREE.DoubleSide }));
  const wl = new THREE.Mesh(bfWingGeo, mat), wr = new THREE.Mesh(bfWingGeo, mat);
  wl.position.x = -0.2; wr.position.x = 0.2; const pl = new THREE.Group(), pr = new THREE.Group();
  pl.add(wl); pr.add(wr); g.add(pl, pr);
  const [x, z] = rpol(4, 40); g.position.set(x, 1.5, z); scene.add(g);
  butterflies.push({ g, pl, pr, target: new THREE.Vector3(x, 1.5, z), t: rand(0, 9), respawn: 0, alive: true });
}
for (let i = 0; i < 7; i++) addButterfly();

// partículas de brilho
const sparks = [];
const sparkGeo = new THREE.SphereGeometry(0.07, 6, 4);
function burst(pos, color = 0xfff3a0, n = 9) {
  for (let i = 0; i < n; i++) {
    const m = new THREE.Mesh(sparkGeo, new THREE.MeshBasicMaterial({ color, transparent: true }));
    m.position.copy(pos); const a = rand(0, TAU);
    sparks.push({ m, v: new THREE.Vector3(Math.cos(a) * rand(.5, 1.8), rand(1.5, 3.5), Math.sin(a) * rand(.5, 1.8)), life: 0.7 });
    scene.add(m);
  }
}

// ------------------------------------------------------------------ itens, inventário, save
const ITEMS = {
  apple: { n: 'Maçã', e: '🍎', v: 100 }, orange: { n: 'Laranja', e: '🍊', v: 100 },
  weed: { n: 'Erva daninha', e: '🌿', v: 10 }, butterfly: { n: 'Borboleta', e: '🦋', v: 320 },
  fish_a: { n: 'Peixe-dourado', e: '🐟', v: 150 }, fish_b: { n: 'Robalo', e: '🐠', v: 400 }, fish_c: { n: 'Baiacu raro', e: '🐡', v: 1200 },
};
for (const c of FLOWERS) ITEMS['flower_' + c] = { n: 'Flor ' + FLOWER_NAMES[c], e: '🌼', v: 40 };
const POCKET = 20;
let save = { bells: 0, inv: {}, hour: 9, day: 1 };
try { Object.assign(save, JSON.parse(localStorage.getItem('ilha_save') || '{}')); } catch { }
save.look = sanitizeLook(save.look);
await equip(save.look);
const STACK = (id) => id === 'apple' || id === 'orange' || id.startsWith('flower') ? 10 : id === 'weed' ? 30 : 1;
const slotsOf = (inv) => Object.entries(inv).reduce((a, [k, n]) => a + Math.ceil(n / STACK(k)), 0);
const invCount = () => slotsOf(save.inv);
function persist() { try { localStorage.setItem('ilha_save', JSON.stringify(save)); } catch { } }
function renderHud() {
  $('#bellN').textContent = save.bells.toLocaleString('pt-BR');
  $('#hotbar').innerHTML = `<span class="chip"><kbd>I</kbd> Bolso ${invCount()}/${POCKET}</span>`;
  if (inv.open) renderInv();
}
function toast(t) { const d = document.createElement('div'); d.className = 'toast'; d.textContent = t; $('#toasts').append(d); setTimeout(() => d.remove(), 3200); }
function give(id) {
  if (slotsOf({ ...save.inv, [id]: (save.inv[id] || 0) + 1 }) > POCKET) { toast('Seus bolsos estão cheios! Venda algo na loja.'); sfx.nope(); return false; }
  save.inv[id] = (save.inv[id] || 0) + 1; toast(`${ITEMS[id].e} Você pegou: ${ITEMS[id].n}!`); sfx.pop(); renderHud(); persist(); return true;
}

// ------------------------------------------------------------------ inventário estilo ACNH (tecla I)
// ícones: renderiza os próprios modelos 3D do jogo em miniatura (como os ícones do ACNH)
const ICON_MODEL = { apple: 'fruit_apple', orange: 'fruit_orange', weed: 'weed' };
for (const c of FLOWERS) ICON_MODEL['flower_' + c] = 'flower_' + c;
const ICONS = {};
{
  const r = new THREE.WebGLRenderer({ alpha: true, antialias: true, preserveDrawingBuffer: true });
  r.setSize(160, 160); r.outputColorSpace = THREE.SRGBColorSpace; r.toneMapping = THREE.NeutralToneMapping; r.toneMappingExposure = 1.15;
  const sc = new THREE.Scene(); sc.add(new THREE.HemisphereLight(0xffffff, 0xb9c9a0, 2.2));
  const dl = new THREE.DirectionalLight(0xffffff, 1.6); dl.position.set(2, 4, 3); sc.add(dl);
  const cam = new THREE.PerspectiveCamera(28, 1, 0.01, 50);
  for (const [id, model] of Object.entries(ICON_MODEL)) {
    const o = tpl[model].clone(true); o.rotation.set(0.25, -0.5, 0); sc.add(o);
    const box = new THREE.Box3().setFromObject(o), size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3());
    const dist = Math.max(size.x, size.y, size.z) / (2 * Math.tan(THREE.MathUtils.degToRad(14))) * 1.15;
    cam.position.set(ctr.x, ctr.y + dist * 0.25, ctr.z + dist); cam.lookAt(ctr);
    r.render(sc, cam); ICONS[id] = r.domElement.toDataURL('image/png'); sc.remove(o);
  }
  r.dispose();
}
const inv = { open: false, sel: 0, menu: null, menuSel: 0 };
const COLS = 10;
function invSlots() {
  const out = [];
  for (const [id, n] of Object.entries(save.inv)) { let left = n; while (left > 0) { const q = Math.min(left, STACK(id)); out.push({ id, n: q }); left -= q; } }
  return out;
}
function iconHtml(id) { return ICONS[id] ? `<img src="${ICONS[id]}" alt="">` : `<span class="emo">${ITEMS[id].e}</span>`; }
function renderInv() {
  const slots = invSlots(), grid = $('#inv-grid');
  inv.sel = clamp(inv.sel, 0, POCKET - 1);
  grid.innerHTML = '';
  for (let i = 0; i < POCKET; i++) {
    const s = slots[i], d = document.createElement('div');
    d.className = 'slot' + (i === inv.sel ? ' sel' : '') + (s ? '' : ' empty');
    d.innerHTML = s ? `${iconHtml(s.id)}${s.n > 1 ? `<b class="cnt">${s.n}</b>` : ''}` : '<i></i>';
    grid.append(d);
  }
  const cur = slots[inv.sel], label = $('#inv-label'), selEl = grid.children[inv.sel];
  label.classList.toggle('hidden', !cur);
  if (cur) {
    label.textContent = ITEMS[cur.id].n;
    const pr = $('#inv .inv-panel').getBoundingClientRect(), r = selEl.getBoundingClientRect();
    label.style.left = (r.left - pr.left + r.width / 2) + 'px'; label.style.top = (r.top - pr.top - 8) + 'px';
  }
  const hand = $('#inv-hand'), r = selEl.getBoundingClientRect(), pr = $('#inv .inv-panel').getBoundingClientRect();
  hand.style.left = (r.left - pr.left + r.width * 0.55) + 'px'; hand.style.top = (r.top - pr.top + r.height * 0.55) + 'px';
  $('#inv-bellN').textContent = save.bells.toLocaleString('pt-BR');
  $('#inv').style.setProperty('--panelH', ($('#inv .inv-panel').offsetHeight + 26) + 'px');
  const m = $('#inv-menu');
  m.classList.toggle('hidden', !inv.menu);
  if (inv.menu) m.innerHTML = inv.menu.map((o, i) => `<div class="opt${i === inv.menuSel ? ' on' : ''}">${o.t}</div>`).join('');
}
function openInv() { inv.open = true; inv.menu = null; $('#inv').classList.remove('hidden'); $('#prompt').classList.remove('on'); sfx.pop(); renderInv(); }
function closeInv() { inv.open = false; inv.menu = null; $('#inv').classList.add('hidden'); note(520, .08, 'triangle', .08); }
function removeItem(id, n) { save.inv[id] -= n; if (save.inv[id] <= 0) delete save.inv[id]; renderHud(); persist(); }
function dropItem(s) {
  removeItem(s.id, s.n);
  const model = ICON_MODEL[s.id], dir = dirOf(player.face);
  if (model) {
    for (let k = 0; k < s.n; k++) {
      const x = player.pos.x + dir.x * 1.1 + rand(-.35, .35), z = player.pos.z + dir.z * 1.1 + rand(-.35, .35);
      const p = addPickup(s.id, model, x, z, s.id.startsWith('fruit') || s.id === 'apple' || s.id === 'orange' ? 1.8 : 1.5, 0);
      p.respawn = -1; p.fixedGone = true;
    }
    toast(`Você soltou: ${ITEMS[s.id].n}`);
  } else toast(`${ITEMS[s.id].e} ${ITEMS[s.id].n} voltou para a natureza.`);
}
function openMenu() {
  const s = invSlots()[inv.sel]; if (!s) { sfx.nope(); return; }
  const opts = [];
  if (s.id === 'apple' || s.id === 'orange') opts.push({ t: 'Comer', f: () => { removeItem(s.id, 1); toast('Nhac! Que delícia. 😋'); sfx.pop(); } });
  opts.push({ t: s.id.startsWith('fish') || s.id === 'butterfly' ? 'Soltar' : 'Soltar item', f: () => dropItem(s) });
  opts.push({ t: 'Cancelar', f: () => {} });
  inv.menu = opts; inv.menuSel = 0; note(700, .06, 'triangle', .08); renderInv();
}
function invKey(code) {
  if (code === 'KeyI' || code === 'Escape' || (code === 'KeyQ')) { if (inv.menu) { inv.menu = null; renderInv(); } else closeInv(); return; }
  if (inv.menu) {
    if (code === 'ArrowUp' || code === 'KeyW') inv.menuSel = (inv.menuSel + inv.menu.length - 1) % inv.menu.length;
    else if (code === 'ArrowDown' || code === 'KeyS') inv.menuSel = (inv.menuSel + 1) % inv.menu.length;
    else if (code === 'KeyE' || code === 'Enter' || code === 'Space') { const o = inv.menu[inv.menuSel]; inv.menu = null; o.f(); }
    else return;
    note(880, .04, 'triangle', .05); renderInv(); return;
  }
  const row = Math.floor(inv.sel / COLS), col = inv.sel % COLS, rows = POCKET / COLS;
  if (code === 'ArrowLeft' || code === 'KeyA') inv.sel = row * COLS + (col + COLS - 1) % COLS;
  else if (code === 'ArrowRight' || code === 'KeyD') inv.sel = row * COLS + (col + 1) % COLS;
  else if (code === 'ArrowUp' || code === 'KeyW') inv.sel = ((row + rows - 1) % rows) * COLS + col;
  else if (code === 'ArrowDown' || code === 'KeyS') inv.sel = ((row + 1) % rows) * COLS + col;
  else if (code === 'KeyE' || code === 'Enter' || code === 'Space') { openMenu(); return; }
  else return;
  note(880, .04, 'triangle', .05); renderInv();
}

// ------------------------------------------------------------------ tela de visual (guarda-roupa)
const ward = { open: false, row: 0, busy: false };
const WROWS = [
  { key: 'hair', label: 'Cabelo', list: () => WARD.items.filter((i) => i.slot === 'hair').map((i) => i.id), name: (v) => WARD.items.find((i) => i.id === v).name },
  { key: 'hairColor', label: 'Cor do cabelo', list: () => Object.keys(WARD.hairColors), name: (v) => v, swatch: (v) => WARD.hairColors[v] },
  { key: 'topColor', label: 'Moletom', list: () => Object.keys(CLOTH_COLORS), name: (v) => v, swatch: (v) => CLOTH_COLORS[v] },
  { key: 'bottomColor', label: 'Calça', list: () => Object.keys(CLOTH_COLORS), name: (v) => v, swatch: (v) => CLOTH_COLORS[v] },
  { key: 'shoesColor', label: 'Tênis', list: () => Object.keys(CLOTH_COLORS), name: (v) => v, swatch: (v) => CLOTH_COLORS[v] },
  { key: 'bag', label: 'Bolsa a tiracolo', list: () => [false, true], name: (v) => (v ? 'Com bolsa' : 'Sem bolsa') },
  { key: 'bagColor', label: 'Cor da bolsa', list: () => Object.keys(CLOTH_COLORS), name: (v) => v, swatch: (v) => CLOTH_COLORS[v] },
];
function renderWard() {
  $('#ward-rows').innerHTML = WROWS.map((r, i) => {
    const v = save.look[r.key], off = false;
    return `<div class="wrow${i === ward.row ? ' on' : ''}${off ? ' off' : ''}"><span class="wl">${r.label}</span>
      <span class="wv"><b class="arr">◀</b>${r.swatch ? `<i class="sw" style="background:${r.swatch(v)}"></i>` : ''}${off ? 'Vestido inteiro' : r.name(v)}<b class="arr">▶</b></span></div>`;
  }).join('');
}
function openWard() { ward.open = true; ward.prevFace = player.face; player.face = 0; $('#ward').classList.remove('hidden'); $('#prompt').classList.remove('on'); sfx.pop(); renderWard(); }
function closeWard() { ward.open = false; $('#ward').classList.add('hidden'); persist(); note(520, .08, 'triangle', .08); }
async function wardKey(code) {
  if (code === 'KeyC' || code === 'Escape' || code === 'KeyI') { closeWard(); return; }
  if (code === 'ArrowUp' || code === 'KeyW') ward.row = (ward.row + WROWS.length - 1) % WROWS.length;
  else if (code === 'ArrowDown' || code === 'KeyS') ward.row = (ward.row + 1) % WROWS.length;
  else if (code === 'ArrowLeft' || code === 'KeyA' || code === 'ArrowRight' || code === 'KeyD' || code === 'KeyE' || code === 'Enter') {
    if (ward.busy) return;
    const r = WROWS[ward.row], list = r.list(), d = code === 'ArrowLeft' || code === 'KeyA' ? -1 : 1;
    save.look[r.key] = list[(list.indexOf(save.look[r.key]) + d + list.length) % list.length];
    ward.busy = true; renderWard(); await equip(save.look); ward.busy = false; sfx.pop();
  } else return;
  note(880, .04, 'triangle', .05); renderWard();
}
document.querySelector('#inv .inv-clothes').addEventListener('click', () => { if (inv.open) closeInv(); openWard(); });

// ------------------------------------------------------------------ áudio (tudo sintetizado, sem arquivos)
let ac = null, master = null;
function note(freq, dur = 0.25, type = 'sine', vol = 0.12, when = 0) {
  if (!ac) return; const t = ac.currentTime + when, o = ac.createOscillator(), g = ac.createGain();
  o.type = type; o.frequency.setValueAtTime(freq, t); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(master); o.start(t); o.stop(t + dur + 0.05);
}
const sfx = {
  pop() { note(660, .1, 'triangle', .15); note(990, .15, 'triangle', .15, .07); },
  coin() { note(1318, .12, 'square', .06); note(1760, .35, 'square', .06, .09); },
  nope() { note(220, .2, 'sawtooth', .07); },
  splash() { note(300, .25, 'sine', .15); note(180, .3, 'sine', .12, .05); },
  swish() { note(500, .12, 'sawtooth', .04); },
  voice(p) { note(p * rand(.9, 1.4), 0.07, 'triangle', 0.09); },
  bite() { note(880, .1, 'square', .08); note(1175, .2, 'square', .08, .1); },
};
// ---- musica "cozy": piano suave + pad quente + baixo, progressao de acordes em loop, reverb; dia alegre, noite lenta e grave
const midi = (m) => 440 * Math.pow(2, (m - 69) / 12);
const MUS = { bus: null, step: 0, next: 0, started: false };
const PROG_DAY = [[48, 52, 55, 59], [45, 48, 52, 55], [41, 45, 48, 52], [43, 47, 50, 52]];   // Cmaj7 - Am7 - Fmaj7 - G6
const PROG_NIGHT = [[45, 48, 52, 55], [41, 45, 48, 52], [48, 52, 55, 59], [40, 43, 47, 50]]; // Am7 - Fmaj7 - Cmaj7 - Em7
const MEL_DAY = [72, 74, 76, 79, 81];   // pentatonica de Do (nunca destoa dos acordes)
function musicInit() {
  const bus = ac.createGain(); bus.gain.value = 0.55;
  const dry = ac.createGain(), wet = ac.createGain(); dry.gain.value = 0.8; wet.gain.value = 0.42;
  const conv = ac.createConvolver(), len = ac.sampleRate * 2.6, ir = ac.createBuffer(2, len, ac.sampleRate);
  for (let c = 0; c < 2; c++) { const d = ir.getChannelData(c); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.6); }
  conv.buffer = ir;
  const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 3200;
  bus.connect(lp); lp.connect(dry); lp.connect(conv); conv.connect(wet); dry.connect(master); wet.connect(master);
  MUS.bus = bus; MUS.next = ac.currentTime + 0.4;
}
function pnote(m, t, dur = 2.2, vol = 0.1) { // piano macio: seno + harmonico triangular, ataque rapido, decaimento longo
  const f = midi(m);
  for (const [mul, type, v] of [[1, 'sine', 1], [2, 'triangle', 0.22], [3, 'sine', 0.06]]) {
    const o = ac.createOscillator(), g = ac.createGain();
    o.type = type; o.frequency.value = f * mul; o.detune.value = (Math.random() - 0.5) * 4;
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(vol * v, t + 0.012); g.gain.exponentialRampToValueAtTime(vol * v * 0.35, t + 0.25); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(MUS.bus); o.start(t); o.stop(t + dur + 0.05);
  }
}
function pad(ms, t, dur, vol = 0.035) { // acordes longos e quentes por baixo
  for (const m of ms) {
    const o = ac.createOscillator(), g = ac.createGain();
    o.type = 'triangle'; o.frequency.value = midi(m); o.detune.value = (Math.random() - 0.5) * 8;
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(vol, t + dur * 0.35); g.gain.linearRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(MUS.bus); o.start(t); o.stop(t + dur + 0.05);
  }
}
function musicBar(bar) {
  const night = hour > 20.3 || hour < 5.5, prog = night ? PROG_NIGHT : PROG_DAY, ch = prog[bar % 4];
  const beat = night ? 1.0 : 0.78, t0 = MUS.next;
  pad(ch.map((m) => m + 12), t0, beat * 4.4, night ? 0.04 : 0.03);
  pnote(ch[0] - 12, t0, beat * 3.6, 0.13);                                   // baixo
  const arp = night ? [0, 2, 1, 3] : [0, 1, 2, 3, 2, 1, 3, 2];              // arpejo calmo
  const stepLen = night ? beat : beat / 2;
  arp.forEach((k, i) => { if (night && i % 2 && Math.random() < 0.4) return; pnote(ch[k] + 12, t0 + i * stepLen, 2.4, night ? 0.075 : 0.07); });
  if (!night && bar % 2 === 1 || night && bar % 2 === 0) { // melodia esparsa, sempre em tempo forte
    const n = night ? 1 : 2;
    for (let i = 0; i < n; i++) if (Math.random() < 0.8) pnote(pick(MEL_DAY) - (night ? 12 : 0), t0 + (i * 2 + (night ? 1 : 0.5)) * beat, 2.8, 0.06);
  }
  MUS.next += beat * 4;
}
setInterval(() => {
  if (!ac || !master) return;
  if (!MUS.bus) musicInit();
  MUS.bus.gain.setTargetAtTime(typeof dialog !== 'undefined' && dialog.open ? 0.3 : 0.55, ac.currentTime, 0.5); // abaixa nas conversas
  while (MUS.next < ac.currentTime + 0.6) { if (MUS.next < ac.currentTime) MUS.next = ac.currentTime + 0.1; musicBar(MUS.step++); }
}, 150);

// ------------------------------------------------------------------ diálogo
const dialog = { open: false, pages: [], i: 0, shown: 0, pitch: 300, done: null, timer: 0 };
function say(name, pages, pitch = 300, done = null) {
  dialog.open = true; dialog.pages = pages; dialog.i = 0; dialog.shown = 0; dialog.pitch = pitch; dialog.done = done;
  $('#dname').textContent = name; $('#dialog').classList.remove('hidden'); $('#prompt').classList.remove('on');
}
function dialogAdvance() {
  const full = dialog.pages[dialog.i];
  if (dialog.shown < full.length) { dialog.shown = full.length; }
  else if (++dialog.i >= dialog.pages.length) { dialog.open = false; $('#dialog').classList.add('hidden'); dialog.done?.(); return; }
  else dialog.shown = 0;
}
function dialogTick(dt) {
  const full = dialog.pages[dialog.i]; if (dialog.shown >= full.length) { $('#dtext').textContent = full; $('#dnext').style.visibility = 'visible'; return; }
  $('#dnext').style.visibility = 'hidden'; dialog.timer += dt;
  while (dialog.timer > 0.028 && dialog.shown < full.length) { dialog.timer -= 0.028; dialog.shown++; if (dialog.shown % 2 === 0 && full[dialog.shown - 1] !== ' ') sfx.voice(dialog.pitch); }
  $('#dtext').textContent = full.slice(0, dialog.shown);
}
$('#dtext').textContent = '';
const _say = say; // garante texto inicial correto
// ------------------------------------------------------------------ input
const keys = {};
addEventListener('keydown', (e) => {
  if (e.repeat) return; keys[e.code] = true;
  if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
  if (!started) return;
  if (dialog.open) { if (e.code === 'KeyE' || e.code === 'Space' || e.code === 'Enter') dialogAdvance(); return; }
  if (ward.open) { wardKey(e.code); return; }
  if (inv.open) { if (e.code === 'KeyC') { closeInv(); openWard(); return; } invKey(e.code); return; }
  if (e.code === 'KeyI') { openInv(); return; }
  if (e.code === 'KeyC') { openWard(); return; }
  if (e.code === 'KeyE' || e.code === 'Enter') interact();
  if (e.code === 'Space') swingNet();
});
addEventListener('keyup', (e) => { keys[e.code] = false; });
const camYaw = 0, camPitch = 0.5, camDist = 10.5;
// câmera travada: ângulo fixo seguindo o jogador (sem rotação nem zoom)

// ------------------------------------------------------------------ interações
let fishing = { state: 'idle', t: 0, bob: null, bobPos: new THREE.Vector3() };
const bobber = new THREE.Mesh(new THREE.SphereGeometry(0.16, 10, 8), bend(new THREE.MeshLambertMaterial({ color: 0xff5a5f }))); bobber.visible = false; scene.add(bobber);
const dirOf = (a) => new THREE.Vector3(Math.sin(a), 0, Math.cos(a));
const d2 = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
let current = null;

function findInteraction() {
  if (fishing.state !== 'idle') return { label: fishing.state === 'bite' ? 'Puxar!' : 'Aguarde a fisgada…  (E: recolher)', act: fishAct, pri: 0 };
  const cands = [];
  for (const v of villagers) { const d = d2(v.pos, player.pos); if (d < 2.8) cands.push({ d, label: `Conversar com ${v.name}`, act: () => talk(v) }); }
  const sd = d2(HOUSES.shop.door, player.pos);
  if (sd < 2.8) cands.push({ d: sd, label: 'Falar com o lojista (vender tudo)', act: sell });
  for (const t of trees) if (t.fruit.some((f) => f.visible) && d2(t, player.pos) < 2.6) cands.push({ d: d2(t, player.pos), label: 'Sacudir a árvore', act: () => shakeTree(t) });
  for (const p of pickups) if (p.o.visible && d2(p, player.pos) < 1.6) cands.push({ d: d2(p, player.pos), label: p.type === 'weed' ? 'Arrancar erva daninha' : p.type.startsWith('flower') ? 'Colher flor' : 'Pegar ' + ITEMS[p.type].n, act: () => take(p) });
  const pd = Math.hypot(POND.x - player.pos.x, POND.z - player.pos.z);
  const toPond = new THREE.Vector3(POND.x - player.pos.x, 0, POND.z - player.pos.z).normalize();
  if (pd < POND.r + 2.6 && dirOf(player.face).dot(toPond) > 0.45) cands.push({ d: 50, label: 'Pescar', act: startFishing });
  cands.sort((a, b) => a.d - b.d);
  return cands[0] || null;
}
function interact() { current?.act(); }
function take(p) {
  if (!give(p.type)) return;
  burst(new THREE.Vector3(p.x, 0.6, p.z), p.type === 'weed' ? 0xa6e07a : 0xfff3a0);
  p.o.visible = false; if (!p.fixedGone) p.respawn = p.type === 'weed' ? 80 : p.type.startsWith('flower') ? 120 : -1;
  if (p.respawn < 0) { p.o.removeFromParent(); pickups.splice(pickups.indexOf(p), 1); }
}
function shakeTree(t) {
  t.shake = 0.9; sfx.swish();
  t.fruit.forEach((f, i) => {
    if (!f.visible) return;
    f.visible = false; const a = rand(0, TAU), r = rand(1.4, 2.3);
    const o = place(t.fruitType === 'apple' ? 'fruit_apple' : 'fruit_orange', t.x + Math.cos(a) * r, t.z + Math.sin(a) * r, 0, 1.8);
    o.position.y = 2.4; const p = { type: t.fruitType, o, x: o.position.x, z: o.position.z, respawn: -1, falling: true, vy: 0, falling_delay: i * 0.12 };
    pickups.push(p);
  });
  t.regrow = 100;
}
function talk(v) {
  const dir = new THREE.Vector3(player.pos.x - v.pos.x, 0, player.pos.z - v.pos.z); v.face = Math.atan2(dir.x, dir.z);
  const night = hour > 20.5 || hour < 5.5;
  const pages = night && Math.random() < 0.6 ? NIGHT_LINES[v.id] : pick(LINES[v.id]);
  v.speaking = true; say(v.name, pages, v.pitch, () => { v.speaking = false; v.wait = 1; });
}
function sell() {
  const keys = Object.keys(save.inv).filter((k) => save.inv[k] > 0);
  if (!keys.length) { say('Lojista Tom', ['Olá! Traga frutas, flores, peixes ou insetos', 'e eu compro tudo por um bom preço!'], 220); return; }
  let total = 0, count = 0; for (const k of keys) { total += ITEMS[k].v * save.inv[k]; count += save.inv[k]; }
  save.inv = {}; save.bells += total; renderHud(); persist(); sfx.coin(); setTimeout(sfx.coin, 160);
  say('Lojista Tom', [`Hmm, ${count} ${count > 1 ? 'itens' : 'item'}... Ótimo estado!`, `Aqui estão ${total.toLocaleString('pt-BR')} sinos. Volte sempre!`], 220);
}
function startFishing() {
  const dir = dirOf(player.face);
  const b = player.pos.clone().add(dir.multiplyScalar(3.2)); const c = new THREE.Vector3(POND.x, 0, POND.z);
  const off = b.clone().sub(c); if (off.length() > POND.r - 0.7) b.copy(c).add(off.setLength(POND.r - 0.7));
  fishing.state = 'cast'; fishing.t = rand(2, 5); fishing.bobPos.copy(b); fishing.bobPos.y = 0.1; bobber.visible = true; bobber.position.copy(fishing.bobPos); sfx.swish();
  player.vel.set(0, 0, 0);
}
function stopFishing() { fishing.state = 'idle'; bobber.visible = false; $('#bang').classList.remove('on'); }
function fishAct() {
  if (fishing.state === 'bite') {
    const r = Math.random(); const id = r < 0.6 ? 'fish_a' : r < 0.9 ? 'fish_b' : 'fish_c';
    stopFishing(); sfx.splash(); burst(fishing.bobPos.clone().setY(0.4), 0x9fe3ff, 14);
    if (give(id) && id === 'fish_c') toast('✨ Uau, um peixe raríssimo!');
  } else if (fishing.state === 'cast') { stopFishing(); toast('Você puxou cedo demais...'); }
}
function swingNet() {
  if (player.swing > 0 || fishing.state !== 'idle') return;
  player.swing = 0.01; player.hit = false; net.visible = true; sfx.swish();
}

// ------------------------------------------------------------------ física do personagem
function collide(pos, rad) {
  for (const c of circles) { const dx = pos.x - c.x, dz = pos.z - c.z, d = Math.hypot(dx, dz), m = c.r + rad; if (d < m && d > 0.0001) { pos.x = c.x + dx / d * m; pos.z = c.z + dz / d * m; } }
  for (const b of boxes) {
    const dx = pos.x - b.x, dz = pos.z - b.z, ox = b.hw + rad - Math.abs(dx), oz = b.hd + rad - Math.abs(dz);
    if (ox > 0 && oz > 0) { if (ox < oz) pos.x += Math.sign(dx || 1) * ox; else pos.z += Math.sign(dz || 1) * oz; }
  }
  const r = Math.hypot(pos.x, pos.z); if (r > 49) { pos.x *= 49 / r; pos.z *= 49 / r; }
}
function animateRig(rg, st, speed, dt, extra = 0, turn = 0) {
  // ---- caminhada com esqueleto articulado: pernas por cinematica inversa (pe fixo no chao no apoio, joelho dobra no balanco)
  const run = clamp((speed - 3.6) / 2.4, 0, 1);
  st.amp = lerp(st.amp || 0, clamp(speed / 3.0, 0, 1), Math.min(1, dt * (speed > 0.3 ? 8 : 6)));
  st.turn = lerp(st.turn || 0, clamp(turn, -6, 6), Math.min(1, dt * 5));
  st.idle = (st.idle || 0) + dt;
  const cadence = 0.95 + 0.2 * speed;                                     // ciclos/s: ~1.6 andando (3.2 passos/s), ~2.2 correndo
  if (speed > 0.08) st.ph = ((st.ph || 0) + cadence * dt) % 1;
  else { const t = st.ph || 0; st.ph = lerp(t, t < 0.75 ? (t < 0.25 ? 0 : 0.5) : 1, Math.min(1, dt * 6)) % 1; }   // termina o passo
  const ph = st.ph, a = st.amp, breath = Math.sin(st.idle * 2.2) * (1 - a);
  const T2 = Math.PI * 2, ease = (x) => x * x * (3 - 2 * x);
  const foot = (phi) => {                                                  // phi 0 = pe toca o chao a frente; 0.6 = sai do chao
    phi = ((phi % 1) + 1) % 1;
    if (phi < 0.55) { const u = phi / 0.55; return { f: 1 - 2 * u, up: 0, pitch: lerp(-0.15, 0.4, u * u) }; }       // apoio: pe recua; calcanhar sobe no fim
    const s2 = (phi - 0.55) / 0.45;
    return { f: -1 + 2 * ease(s2), up: Math.sin(Math.PI * s2) ** 0.9, pitch: lerp(0.4, -0.15, ease(Math.min(1, s2 * 1.3))) };   // balanco: passa rapido, levantando
  };
  const dip = (1 - Math.cos(2 * T2 * ph)) * 0.5;                           // 0 no contato (corpo baixo), 1 na passagem (corpo alto)
  const H = rg.Hrest || 0.45, L1 = rg.L1 || H * 0.5, L2 = rg.L2 || H * 0.5;
  const crouch = H * a * (0.05 + 0.11 * (1 - dip));                        // quadril desce no contato (joelhos dobram)
  const reach = H * (0.5 + 0.06 * run) * a, liftH = H * (0.22 + 0.08 * run) * a;
  const leg = (hip, knee, ankle, phi) => {
    if (!hip || !knee || !ankle || !rg.Hrest) return;
    const F = foot(phi);
    const zf = F.f * reach, h = Math.max(0.05, H - crouch - F.up * liftH);   // alvo do tornozelo relativo ao quadril (frente, baixo)
    const d = Math.min(Math.hypot(zf, h), (L1 + L2) * 0.999);
    const cosK = clamp((L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2), -1, 1), beta = Math.PI - Math.acos(cosK);     // flexao do joelho
    const alpha = Math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1));
    const gamma = Math.atan2(zf, h) + alpha;                                // coxa: angulo a frente da vertical
    setRot(hip, -gamma);
    setRot(knee, beta);
    setRot(ankle, F.pitch * a - (-gamma + beta));                           // mantem o pe nivelado/inclinado no mundo
  };
  leg(rg.footL, rg.kneeL, rg.ankleL, ph);
  leg(rg.footR, rg.kneeR, rg.ankleR, ph + 0.5);
  const g = Math.cos(T2 * (ph - 0.07)), armA = (0.6 + 0.3 * run) * a;      // bracos: oposto as pernas, com leve atraso
  const swL = armA * g + breath * 0.035, swR = -armA * g + breath * 0.035;
  if (rg.armL) setRot(rg.armL, swL);
  if (rg.armR && !extra) setRot(rg.armR, swR);
  if (rg.elbowL) setRot(rg.elbowL, -(0.18 * a + Math.max(0, -swL) * 0.9));   // antebraco dobra para frente quando o braco vai a frente
  if (rg.elbowR && !extra) setRot(rg.elbowR, -(0.18 * a + Math.max(0, -swR) * 0.9));
  if (rg.root) {
    setPos(rg.root, Math.sin(T2 * ph) * 0.02 * a, -crouch, 0);
    setRot(rg.root, (0.05 + 0.08 * run) * a, Math.sin(T2 * ph) * 0.06 * a, Math.sin(T2 * ph) * 0.035 * a - st.turn * 0.02 * a);
  }
  if (rg.head) setRot(rg.head, -0.04 * a - dip * 0.02 * a + breath * 0.015, -Math.sin(T2 * ph) * 0.05 * a, -Math.sin(T2 * ph) * 0.02 * a + st.turn * 0.012 * a);
}

// ------------------------------------------------------------------ dia e noite
let hour = save.hour, day = save.day;
// cada momento do dia: ceu (zenite/horizonte), sol/lua, luz ambiente, nevoa, mar, nuvens e pos-processamento
const TOD = [
  { h: 0,    top: '#0e1840', hor: '#2c3c78', sun: '#9fb4ff', sunI: 0.55, hs: '#6f86c8', hg: '#26324a', hI: 0.95, fog: [28, 125], sea: '#22406f', cloud: '#3c4c7c', exp: 1.0,  tint: [0.88, 0.94, 1.12], sat: 0.85, con: 0.95, lift: 0.03, vig: 0.22, bloom: 0.55, ao: 0.35, moon: 1 },
  { h: 4.8,  top: '#1d2a5c', hor: '#6f6aa2', sun: '#a8b0ff', sunI: 0.5,  hs: '#8a8ec4', hg: '#3a3f58', hI: 0.95, fog: [30, 130], sea: '#3a5888', cloud: '#7c7aaa', exp: 1.02, tint: [0.96, 0.93, 1.08], sat: 0.9,  con: 0.96, lift: 0.03, vig: 0.18, bloom: 0.45, ao: 0.4,  moon: 1 },
  { h: 6.2,  top: '#6aa6e0', hor: '#ffd2b0', sun: '#ffc89a', sunI: 1.75, hs: '#fff0e2', hg: '#c8d2a2', hI: 1.6,  fog: [40, 145], sea: '#72c0d8', cloud: '#ffdac6', exp: 1.15, tint: [1.05, 1.0, 0.96],  sat: 1.04, con: 1.0,  lift: 0.02, vig: 0.1,  bloom: 0.38, ao: 0.5,  moon: 0 },
  { h: 8.5,  top: '#58b6f2', hor: '#cdeefe', sun: '#fff0d8', sunI: 2.1,  hs: '#dbeaff', hg: '#bfe39a', hI: 1.55, fog: [55, 160], sea: '#72d0e8', cloud: '#ffffff', exp: 1.1,  tint: [1.01, 1.0, 0.99],  sat: 1.05, con: 1.02, lift: 0.01, vig: 0.1,  bloom: 0.3,  ao: 0.6,  moon: 0 },
  { h: 12,   top: '#4db0f5', hor: '#d4f0ff', sun: '#fffaf0', sunI: 2.4,  hs: '#e2eeff', hg: '#c4ec9f', hI: 1.7,  fog: [60, 170], sea: '#78d6ea', cloud: '#ffffff', exp: 1.1,  tint: [1.0, 1.0, 1.0],    sat: 1.06, con: 1.03, lift: 0.01, vig: 0.08, bloom: 0.28, ao: 0.62, moon: 0 },
  { h: 15.5, top: '#52b2f2', hor: '#daf0fb', sun: '#fff0d6', sunI: 2.25, hs: '#e6eefa', hg: '#c6e69a', hI: 1.6,  fog: [58, 165], sea: '#74d0e4', cloud: '#fffaf0', exp: 1.1,  tint: [1.02, 1.0, 0.97],  sat: 1.06, con: 1.03, lift: 0.01, vig: 0.09, bloom: 0.3,  ao: 0.62, moon: 0 },
  { h: 17.6, top: '#62a8ea', hor: '#ffdcaa', sun: '#ffc47e', sunI: 2.0,  hs: '#fff0d8', hg: '#d2dca2', hI: 1.55, fog: [45, 150], sea: '#7cc0d0', cloud: '#ffe0b8', exp: 1.14, tint: [1.06, 1.0, 0.94],  sat: 1.06, con: 1.03, lift: 0.01, vig: 0.1,  bloom: 0.38, ao: 0.58, moon: 0 },
  { h: 19,   top: '#5a6cb6', hor: '#ffa684', sun: '#ff9a6a', sunI: 1.2,  hs: '#eab8cf', hg: '#a2929e', hI: 1.25, fog: [36, 138], sea: '#5c7cab', cloud: '#ffadab', exp: 1.1,  tint: [1.06, 0.96, 0.98], sat: 1.02, con: 1.0,  lift: 0.02, vig: 0.14, bloom: 0.5,  ao: 0.5,  moon: 0 },
  { h: 20.3, top: '#25306a', hor: '#6c5c9c', sun: '#a4b2ff', sunI: 0.55, hs: '#7c80c2', hg: '#34385a', hI: 0.95, fog: [30, 128], sea: '#2c4a7c', cloud: '#4c4c82', exp: 1.02, tint: [0.92, 0.93, 1.1],  sat: 0.9,  con: 0.97, lift: 0.03, vig: 0.2,  bloom: 0.55, ao: 0.38, moon: 1 },
  { h: 24,   top: '#0e1840', hor: '#2c3c78', sun: '#9fb4ff', sunI: 0.55, hs: '#6f86c8', hg: '#26324a', hI: 0.95, fog: [28, 125], sea: '#22406f', cloud: '#3c4c7c', exp: 1.0,  tint: [0.88, 0.94, 1.12], sat: 0.85, con: 0.95, lift: 0.03, vig: 0.22, bloom: 0.55, ao: 0.35, moon: 1 },
].map((k) => Object.assign({}, k, { top: new THREE.Color(k.top), hor: new THREE.Color(k.hor), sun: new THREE.Color(k.sun), hs: new THREE.Color(k.hs), hg: new THREE.Color(k.hg), sea: new THREE.Color(k.sea), cloud: new THREE.Color(k.cloud) }));
const tmpC = new THREE.Color();
let windowMats = null;
const sunDirW = new THREE.Vector3();
function applyTime() {
  let i = 0; while (i < TOD.length - 2 && hour >= TOD[i + 1].h) i++;
  const A = TOD[i], B = TOD[i + 1], t = clamp((hour - A.h) / (B.h - A.h), 0, 1);
  const k = t * t * (3 - 2 * t);
  const L = (x) => lerp(A[x], B[x], k), C = (x) => A[x].clone().lerp(B[x], k);
  // ceu, nevoa e mar
  const top = C('top'), hor = C('hor');
  scene.background = hor; skyUniforms.uTop.value.copy(top); skyUniforms.uHorizon.value.copy(hor);
  scene.fog.color.copy(hor); scene.fog.near = lerp(A.fog[0], B.fog[0], k); scene.fog.far = lerp(A.fog[1], B.fog[1], k);
  ocean.material.color.copy(C('sea'));
  cloudMat.color.copy(C('cloud')); cloudMat.emissive = cloudMat.emissive || new THREE.Color(); cloudMat.emissive.copy(cloudMat.color).multiplyScalar(0.35);
  // sol de dia, lua de noite (direcao propria)
  const moon = L('moon');
  const ang = clamp((hour - 6) / 12.5, -0.05, 1.05) * Math.PI;
  const sunD = new THREE.Vector3(Math.cos(ang), Math.max(Math.sin(ang), 0.18), 0.45).normalize();
  const moonD = new THREE.Vector3(-0.45, 0.85, 0.5).normalize();
  sunDirW.copy(sunD).lerp(moonD, moon).normalize();
  skyUniforms.uSunDir.value.copy(sunDirW); skyUniforms.uSunCol.value.copy(C('sun')).multiplyScalar(moon > 0.5 ? 0.35 : 1); skyUniforms.uGlow.value = lerp(1, 0.5, moon);
  sun.color.copy(C('sun')); sun.intensity = L('sunI');
  hemi.color.copy(C('hs')); hemi.groundColor.copy(C('hg')); hemi.intensity = L('hI');
  scene.environmentIntensity = lerp(0.35, 0.15, moon);
  // pos-processamento do horario
  renderer.toneMappingExposure = L('exp');
  gradePass.uniforms.uTint.value.set(lerp(A.tint[0], B.tint[0], k), lerp(A.tint[1], B.tint[1], k), lerp(A.tint[2], B.tint[2], k));
  gradePass.uniforms.uSat.value = L('sat'); gradePass.uniforms.uContrast.value = L('con'); gradePass.uniforms.uLift.value = L('lift'); gradePass.uniforms.uVig.value = L('vig');
  bloom.strength = L('bloom'); aoPass.uniforms.uStrength.value = L('ao');
  // noite: estrelas, postes e janelas acesas
  const night = clamp(hour > 12 ? (hour - 18.6) / 1.6 : (6.2 - hour) / 1.4, 0, 1);
  starMat.opacity = night; lampLights.forEach((l) => { l.intensity = night * 2.4; }); if (lampBulbMat) lampBulbMat.emissiveIntensity = 0.15 + night * 2.2;
  if (!windowMats) { windowMats = new Set(); scene.traverse((o) => { if (o.isMesh && (o.material.name === 'window' || o.material.name === 'porchglow')) windowMats.add(o.material); }); }
  windowMats.forEach((m) => { m.emissive = m.emissive || new THREE.Color(); m.emissive.set(m.name === 'window' ? 0xffcf6e : 0xffd878); m.emissiveIntensity = m.name === 'window' ? night * 1.4 : 0.2 + night * 1.5; });
  const hh = Math.floor(hour), mm = Math.floor((hour % 1) * 60 / 10) * 10;
  $('#clock').textContent = `Dia ${day} · ${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
}

// ------------------------------------------------------------------ loop principal
let started = false;
const clock = new THREE.Clock();
function resize() { renderer.setSize(innerWidth, innerHeight, false); composer.setPixelRatio(PR_MAX * prScale); composer.setSize(innerWidth, innerHeight); dofPass.uniforms.texel.value.set(1 / innerWidth, 1 / innerHeight); outlinePass.uniforms.texel.value.set(1 / (innerWidth * composer._pixelRatio), 1 / (innerHeight * composer._pixelRatio)); outlinePass.uniforms.uWidth.value = Math.max(1, composer._pixelRatio * 0.9); gradePass.uniforms.texel.value.set(1 / (innerWidth * composer._pixelRatio), 1 / (innerHeight * composer._pixelRatio)); aoPass.uniforms.texel.value.set(1 / innerWidth, 1 / innerHeight); aoPass.uniforms.uRes.value.set(innerWidth, innerHeight); aoPass.uniforms.uFocal.value = innerHeight * 0.5 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)); bloom.resolution.set(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); }
addEventListener('resize', resize); resize();
const camPos = new THREE.Vector3(), camLook = new THREE.Vector3();
let saveT = 0;

function update(dt, time) {
  grassTime.value = time;
  // tempo
  if (started) { hour += dt / 25; if (hour >= 24) { hour -= 24; day++; } }
  applyTime();

  // movimento do jogador
  const locked = dialog.open || inv.open || ward.open;
  let ix = (keys.KeyD || keys.ArrowRight ? 1 : 0) - (keys.KeyA || keys.ArrowLeft ? 1 : 0);
  let iy = (keys.KeyW || keys.ArrowUp ? 1 : 0) - (keys.KeyS || keys.ArrowDown ? 1 : 0);
  if (locked || !started) ix = iy = 0;
  if ((ix || iy) && fishing.state !== 'idle') stopFishing();
  const wish = new THREE.Vector3(Math.cos(camYaw) * ix - Math.sin(camYaw) * iy, 0, -Math.sin(camYaw) * ix - Math.cos(camYaw) * iy);
  const maxV = (keys.ShiftLeft || keys.ShiftRight) ? 6.2 : 3.3;   // andar: ~1.4 alturas/s; correr com Shift
  if (player.swing > 0 || fishing.state !== 'idle') wish.set(0, 0, 0);
  if (wish.lengthSq() > 0) { wish.normalize(); const ta = Math.atan2(wish.x, wish.z); let da = ta - player.face; da = Math.atan2(Math.sin(da), Math.cos(da)); const step = da * Math.min(1, dt * 9); player.face += step; player.turnRate = step / Math.max(dt, 1e-3); } else player.turnRate = 0;
  player.vel.lerp(wish.multiplyScalar(maxV), Math.min(1, dt * (wish.lengthSq() > 0 ? 6 : 9))); // aceleracao suave
  if (!window.__walkDemo) { player.pos.addScaledVector(player.vel, dt); collide(player.pos, 0.45); }
  const sp = window.__walkDemo ? window.__walkDemo : player.vel.length();   // __walkDemo: modo de teste (anda no lugar)
  player.obj.position.copy(player.pos); player.obj.rotation.y = player.face;
  animateRig(player.rig, player.anim || (player.anim = {}), sp, dt * (window.__walkSlow || 1), player.swing > 0 ? 1 : 0, player.turnRate || 0);
  pShadow.position.set(player.pos.x, 0.06, player.pos.z);

  // rede
  if (player.swing > 0) {
    player.swing += dt; const k = player.swing / 0.55;
    net.rotation.x = lerp(-1.3, 0.55, Math.min(1, k) ** 1.5); setRot(player.rig.armR, -2.2 + k * 1.2); if (player.rig.elbowR) setRot(player.rig.elbowR, -0.35);
    if (!player.hit && k > 0.5) {
      player.hit = true; const dir = dirOf(player.face), tip = player.pos.clone().add(dir.clone().multiplyScalar(1.9));
      for (const b of butterflies) if (b.alive && b.g.position.distanceTo(tip.setY(b.g.position.y)) < 2.2 && b.g.position.y < 3.2) {
        b.alive = false; b.g.visible = false; b.respawn = 25; burst(b.g.position, 0xff9fd0, 12); give('butterfly');
      }
    }
    if (k >= 1) { player.swing = 0; net.visible = false; setRot(player.rig.armR, 0); }
  }

  // pesca
  if (fishing.state !== 'idle') {
    fishing.t -= dt; bobber.position.y = 0.12 + Math.sin(time * 3) * 0.03 - (fishing.state === 'bite' ? 0.1 + Math.abs(Math.sin(time * 25)) * 0.08 : 0);
    if (fishing.state === 'cast' && fishing.t <= 0) { fishing.state = 'bite'; fishing.t = 1.1; $('#bang').classList.add('on'); sfx.bite(); }
    else if (fishing.state === 'bite' && fishing.t <= 0) { stopFishing(); toast('O peixe escapou...'); }
  }

  // aldeões
  for (const v of villagers) {
    let moving = false;
    if (!v.speaking) {
      if (v.wait > 0) v.wait -= dt;
      else {
        const dx = v.target.x - v.pos.x, dz = v.target.z - v.pos.z, d = Math.hypot(dx, dz);
        if (d < 0.3) { v.wait = rand(2, 6); const a = rand(0, TAU), r = rand(1, 7); v.target.set(v.home.x + Math.cos(a) * r, 0, v.home.z + Math.sin(a) * r); }
        else { v.pos.x += dx / d * 1.7 * dt; v.pos.z += dz / d * 1.7 * dt; v.face = Math.atan2(dx, dz); moving = true; collide(v.pos, 0.45); }
      }
    }
    v.speed = lerp(v.speed, moving ? 1.7 * 3.2 : 0, dt * 8); v.walkT += dt * (moving ? 9 : 0);
    v.o.rotation.y += (() => { let da = v.face - v.o.rotation.y; da = Math.atan2(Math.sin(da), Math.cos(da)); return da * Math.min(1, dt * 8); })();
    animateRig(v.rig, v.anim || (v.anim = {}), moving ? 1.7 : 0, dt); v.shadow.position.set(v.pos.x, 0.06, v.pos.z);
  }

  // borboletas
  const dayTime = hour > 6 && hour < 19;
  for (const b of butterflies) {
    if (!b.alive) { if ((b.respawn -= dt) <= 0 && dayTime) { b.alive = true; b.g.visible = true; } continue; }
    b.g.visible = dayTime; b.t += dt;
    if (b.g.position.distanceTo(b.target) < 0.6) { const [x, z] = rpol(2, 42); b.target.set(x, rand(1, 2.8), z); }
    const dir = b.target.clone().sub(b.g.position).normalize();
    b.g.position.addScaledVector(dir, dt * 1.6); b.g.position.y += Math.sin(b.t * 5) * dt * 0.8;
    b.g.rotation.y = Math.atan2(dir.x, dir.z); const f = Math.sin(b.t * 22) * 0.9; b.pl.rotation.z = f; b.pr.rotation.z = -f;
  }

  // árvores, plantas, itens caindo, respawn
  for (const t of trees) {
    t.shake = Math.max(0, t.shake - dt); const sw = Math.sin(time * 1.2 + t.o.userData.phase) * 0.012;
    t.o.rotation.z = sw + Math.sin(time * 40) * t.shake * 0.05; t.o.rotation.x = Math.cos(time * 1.1 + t.o.userData.phase) * 0.01;
    if (t.regrow > 0 && (t.regrow -= dt) <= 0) t.fruit.forEach((f) => { f.visible = true; });
  }
  for (const p of [...pickups]) {
    if (p.falling) {
      if ((p.falling_delay -= dt) > 0) continue; p.vy -= 14 * dt; p.o.position.y += p.vy * dt;
      if (p.o.position.y <= 0.05) { p.o.position.y = 0.05; if (Math.abs(p.vy) > 2) p.vy *= -0.35; else { p.falling = false; sfx.pop(); } }
    }
    if (p.respawn > 0 && (p.respawn -= dt) <= 0) { p.o.visible = true; p.o.scale.setScalar(0.01); p.growing = true; }
    if (p.growing) { const s = p.o.scale.x + dt * 3; p.o.scale.setScalar(Math.min(s, p.baseSc)); if (s >= p.baseSc) p.growing = false; }
    if (p.o.visible && !p.falling && p.type !== 'weed' && p.type.startsWith('flower')) p.o.rotation.z = Math.sin(time * 2 + p.o.userData.phase) * 0.08;
  }

  // partículas
  for (let i = sparks.length - 1; i >= 0; i--) {
    const s = sparks[i]; s.life -= dt; s.v.y -= 7 * dt; s.m.position.addScaledVector(s.v, dt); s.m.material.opacity = Math.max(0, s.life / 0.7); s.m.scale.setScalar(Math.max(0.1, s.life));
    if (s.life <= 0) { scene.remove(s.m); s.m.material.dispose(); sparks.splice(i, 1); }
  }

  // ambiente
  clouds.forEach((c, i) => { c.position.x += dt * (0.6 + (i % 3) * 0.3); if (c.position.x > 140) c.position.x = -140; });
  pondMat.color.setHSL(0.54 + Math.sin(time * .6) * 0.008, 0.75, 0.68 + Math.sin(time * 1.3) * 0.02);
  foam.material.opacity = 0.4 + Math.sin(time * 1.2) * 0.15; foam.scale.setScalar(1 + Math.sin(time * 1.2) * 0.008);
  stars.position.copy(camera.position); skyDome.position.copy(camera.position);

  // câmera
  if (titleMode) {
    hour = 10; player.pos.set(0, 0, 0.8); player.face = 0; player.obj.position.copy(player.pos); player.obj.rotation.y = 0;
    const cv = villagers.find((v) => v.id === 'capy');
    if (cv) { cv.pos.set(2.3, 0, 0.2); cv.face = -0.5; cv.o.rotation.y = -0.5; cv.wait = 5; }
    camera.position.set(0.7, 3.6, 10.5); camera.lookAt(0.4, 2.2, 0); camPos.copy(camera.position); camLook.set(0.4, 2.2, 0);
    return;
  }
  // guarda-roupa aberto: camera mais perto e baixa, personagem de frente e a esquerda da tela (painel a direita)
  if (ward.open) { player.face = 0; player.obj.rotation.y = 0; }
  const wd = ward.open ? 5.2 : camDist, wp = ward.open ? 0.2 : camPitch, cp = Math.cos(wp);
  const target = new THREE.Vector3(player.pos.x + (ward.open ? 1.35 : 0), ward.open ? 1.15 : 1.3, player.pos.z);
  const want = new THREE.Vector3(target.x + Math.sin(camYaw) * cp * wd, target.y + Math.sin(wp) * wd, target.z + Math.cos(camYaw) * cp * wd);
  camPos.lerp(want, Math.min(1, dt * 6)); camLook.lerp(target, Math.min(1, dt * 9));
  camera.position.copy(camPos); camera.lookAt(camLook);
  // luz das sombras com altura minima (sol rasante gera faixas de sombra e escurece a grama); o ceu usa a posicao real
  const ld = new THREE.Vector3(sunDirW.x, Math.max(sunDirW.y, 0.5), sunDirW.z).normalize();
  sun.target.position.set(player.pos.x, 0, player.pos.z); sun.position.set(player.pos.x + ld.x * 50, ld.y * 50, player.pos.z + ld.z * 50);

  // prompt
  if (started && !dialog.open && !inv.open && !ward.open) {
    current = findInteraction();
    const pr = $('#prompt'); if (current) { pr.innerHTML = `<kbd>E</kbd>${current.label}`; pr.classList.add('on'); } else pr.classList.remove('on');
  }
  if (dialog.open) dialogTick(dt);
  if ((saveT += dt) > 5) { saveT = 0; save.hour = hour; save.day = day; persist(); }
}

let fpsAcc = 0, fpsN = 0;
function adaptQuality(dt) {
  fpsAcc += dt; fpsN++;
  if (fpsAcc < 2.0) return;
  const fps = fpsN / fpsAcc; fpsAcc = 0; fpsN = 0;
  let ns = prScale;
  if (fps < 52 && prScale > 0.55) ns = Math.max(0.55, prScale - 0.15);
  else if (fps > 68 && prScale < 1) ns = Math.min(1, prScale + 0.1);
  if (ns !== prScale) { prScale = ns; resize(); }
}
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  update(dt, clock.elapsedTime); adaptQuality(dt);
  if (CR.open) { CR.t += dt; crRender(); }
  dofPass.uniforms.tDepth.value = composer.readBuffer.depthTexture; aoPass.uniforms.tDepth.value = composer.readBuffer.depthTexture; outlinePass.uniforms.tDepth.value = composer.readBuffer.depthTexture;
  dofPass.uniforms.focus.value = camera.position.distanceTo(camLook);
  composer.render();
  requestAnimationFrame(frame);
}
camPos.set(player.pos.x, 8, player.pos.z + 10); camLook.copy(player.pos);
renderHud(); applyTime();
// ------------------------------------------------------------------ criacao de personagem (estilo ACNH)
const CR = { open: false, tab: 0, look: null, r: null, scene: null, cam: null, avatar: null, t: 0, onDone: null };
const CR_TABS = [
  { id: 'pele', icon: '🙂', label: 'Pele' },
  { id: 'cabelo', icon: '✂️', label: 'Cabelo' },
  { id: 'olhos', icon: '👀', label: 'Olhos' },
  { id: 'bochechas', icon: '🌸', label: 'Bochechas' },
  { id: 'roupa', icon: '👕', label: 'Roupa' },
];
const PIECE_ICONS = {};
async function pieceIcons() {
  // miniaturas renderizadas das proprias pecas 3D (como os icones do ACNH)
  const r = new THREE.WebGLRenderer({ alpha: true, antialias: true, preserveDrawingBuffer: true });
  r.setSize(150, 150); r.outputColorSpace = THREE.SRGBColorSpace; r.toneMapping = THREE.NeutralToneMapping; r.toneMappingExposure = 1.1;
  const sc = new THREE.Scene(); sc.add(new THREE.HemisphereLight(0xffffff, 0xc9d4b0, 2.4));
  const dl = new THREE.DirectionalLight(0xffffff, 1.4); dl.position.set(1, 3, 4); sc.add(dl);
  const cam = new THREE.PerspectiveCamera(26, 1, 0.01, 50);
  for (const it of WARD.items) {
    if (it.slot === 'body') continue;
    const o = SkeletonUtils.clone(await loadPiece(it.id));
    if (it.slot === 'hair') o.traverse((m) => { if (m.isMesh) { m.material = m.material.clone(); m.material.color.set(WARD.hairColors.Castanho); } });
    o.rotation.y = it.slot === 'hair' ? 0.5 : 0.35; sc.add(o); o.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(o), size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3());
    const dist = Math.max(size.x, size.y) / (2 * Math.tan(THREE.MathUtils.degToRad(13))) * 1.12;
    cam.position.set(ctr.x, ctr.y + dist * 0.12, ctr.z + dist); cam.lookAt(ctr);
    r.render(sc, cam); PIECE_ICONS[it.id] = r.domElement.toDataURL(); sc.remove(o);
  }
  r.dispose();
}
function crEnsure() {
  if (CR.r) return;
  const cv = $('#cr-canvas');
  CR.r = new THREE.WebGLRenderer({ canvas: cv, alpha: true, antialias: true });
  CR.r.setPixelRatio(Math.min(devicePixelRatio, 2)); CR.r.outputColorSpace = THREE.SRGBColorSpace; CR.r.toneMapping = THREE.NeutralToneMapping; CR.r.toneMappingExposure = 1.08;
  CR.scene = new THREE.Scene();
  CR.scene.add(new THREE.HemisphereLight(0xfffbf0, 0xbcd3a0, 2.0));
  const d = new THREE.DirectionalLight(0xffffff, 1.6); d.position.set(-1.5, 3, 4); CR.scene.add(d);
  { const pm = new THREE.PMREMGenerator(CR.r); CR.scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; CR.scene.environmentIntensity = 0.3; }
  CR.cam = new THREE.PerspectiveCamera(30, 1, 0.05, 50);
}
async function crRefresh() {
  const av = await buildAvatar(CR.look);
  if (CR.avatar) CR.scene.remove(CR.avatar);
  CR.avatar = av; CR.scene.add(av);
  crRender();
}
function crTiles() {
  const t = CR_TABS[CR.tab].id, L = CR.look;
  const tile = (key, val, inner, on) => `<div class="cr-tile${on ? ' on' : ''}" data-k="${key}" data-v="${val}">${inner}</div>`;
  const pieceTile = (it) => tile(it.slot, it.id, `<img src="${PIECE_ICONS[it.id] || ''}"><span>${it.name}</span>`, L[it.slot] === it.id);
  let tiles = '', sw = '';
  if (t === 'pele') sw = Object.entries(SKIN_TONES).map(([n, c]) => `<div class="cr-sw${L.skin === n ? ' on' : ''}" data-k="skin" data-v="${n}" style="background:${c}" title="${n}"></div>`).join('');
  if (t === 'cabelo') {
    tiles = WARD.items.filter((i) => i.slot === 'hair').map(pieceTile).join('');
    sw = Object.entries(WARD.hairColors).map(([n, c]) => `<div class="cr-sw${L.hairColor === n ? ' on' : ''}" data-k="hairColor" data-v="${n}" style="background:${c}" title="${n}"></div>`).join('');
  }
  if (t === 'olhos') {
    tiles = Object.entries(EYE_COLORS).map(([n, c]) => tile('eyes', n, `<b class="eye"><i style="background:${c}"></i></b><b class="eye"><i style="background:${c}"></i></b><span>${n}</span>`, L.eyes === n)).join('');
  }
  if (t === 'bochechas') tiles = tile('blush', 'true', '<b class="face blush">🙂</b><span>Com blush</span>', L.blush !== false) + tile('blush', 'false', '<b class="face">🙂</b><span>Sem blush</span>', L.blush === false);
  if (t === 'roupa') {
    CR.piece = CR.piece || 'top';
    const PIECES = [['top', 'topColor', 'top_moletom', 'Moletom'], ['bottom', 'bottomColor', 'bottom_calca', 'Calça'], ['shoes', 'shoesColor', 'shoes_tenis', 'Tênis'], ['bag', 'bagColor', 'acc_bolsa', 'Bolsa']];
    tiles = PIECES.map(([sl, , id, nm]) => `<div class="cr-tile${CR.piece === sl ? ' on' : ''}" data-piece="${sl}"><img src="${PIECE_ICONS[id] || ''}"><span>${nm}</span></div>`).join('');
    const cur = PIECES.find((x) => x[0] === CR.piece);
    if (CR.piece === 'bag') tiles += tile('bag', L.bag ? 'false' : 'true', `<b class="face">${L.bag ? '✖' : '✔'}</b><span>${L.bag ? 'Tirar bolsa' : 'Usar bolsa'}</span>`, false);
    sw = Object.entries(CLOTH_COLORS).map(([n, c]) => `<div class="cr-sw${L[cur[1]] === n ? ' on' : ''}" data-k="${cur[1]}" data-v="${n}" style="background:${c}" title="${n}"></div>`).join('');
  }
  $('#cr-grid').innerHTML = tiles; $('#cr-sw').innerHTML = sw;
  $('#cr-tabs').innerHTML = CR_TABS.map((tb, i) => `<div class="cr-tab${i === CR.tab ? ' on' : ''}" data-i="${i}">${tb.icon}</div>`).join('');
  $('#cr-tablabel').textContent = CR_TABS[CR.tab].label;
}
function crRender() {
  if (!CR.open || !CR.avatar) return;
  const cv = $('#cr-canvas'), w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== Math.floor(w * CR.r.getPixelRatio())) { CR.r.setSize(w, h, false); CR.cam.aspect = w / h; CR.cam.updateProjectionMatrix(); }
  CR.avatar.rotation.y = Math.sin(CR.t * 0.6) * 0.25;
  CR.cam.position.set(0, 1.55, 7.3); CR.cam.lookAt(0, 1.3, 0);
  CR.r.render(CR.scene, CR.cam);
}
async function openCreator(done) {
  CR.open = true; CR.onDone = done; CR.look = Object.assign({}, save.look); CR.tab = 0;
  crEnsure(); $('#creator').classList.remove('hidden');
  if (!Object.keys(PIECE_ICONS).length) await pieceIcons();
  crTiles(); await crRefresh();
}
async function crSet(k, v) {
  CR.look[k] = (k === 'blush' || k === 'bag') ? v === 'true' : v;
  sfx.pop(); crTiles(); await crRefresh();
}
async function crConfirm() {
  save.look = Object.assign({}, CR.look); save.created = true; persist();
  await equip(save.look);
  CR.open = false; $('#creator').classList.add('hidden'); sfx.coin();
  CR.onDone?.();
}
$('#creator').addEventListener('click', (e) => {
  const tile = e.target.closest('[data-k]'); if (tile) { crSet(tile.dataset.k, tile.dataset.v); return; }
  const pc = e.target.closest('[data-piece]'); if (pc) { CR.piece = pc.dataset.piece; sfx.pop(); crTiles(); return; }
  const tab = e.target.closest('.cr-tab'); if (tab) { CR.tab = +tab.dataset.i; note(880, .04, 'triangle', .05); crTiles(); return; }
  if (e.target.closest('.cr-confirm')) crConfirm();
});
addEventListener('keydown', (e) => {
  if (!CR.open) return;
  if (e.code === 'KeyQ' || e.code === 'ArrowLeft') { CR.tab = (CR.tab + CR_TABS.length - 1) % CR_TABS.length; crTiles(); note(880, .04, 'triangle', .05); }
  if (e.code === 'KeyE' || e.code === 'ArrowRight') { CR.tab = (CR.tab + 1) % CR_TABS.length; crTiles(); note(880, .04, 'triangle', .05); }
  if (e.code === 'Enter') crConfirm();
  e.stopImmediatePropagation();
}, true);

function startGame() {
  started = true; document.body.classList.remove('on-title');
  say('Ilha Aconchego', ['Bem-vindo(a) à sua nova ilha! 🌴', 'Passeie, colha frutas, pesque no lago e venda tudo na loja. Não há pressa!'], 300);
}
let titleMode = true;
document.body.classList.add('on-title');
function leaveTitle(e) {
  if (!titleMode || CR.open) return;
  if (e && e.type === 'keydown' && ['F5', 'F12', 'ControlLeft', 'ControlRight', 'AltLeft', 'MetaLeft'].includes(e.code)) return;
  titleMode = false;
  ac = ac || new (window.AudioContext || window.webkitAudioContext)();
  if (!master) { master = ac.createGain(); master.gain.value = 0.9; master.connect(ac.destination); }
  sfx.coin();
  $('#title').classList.add('leaving');
  setTimeout(() => { $('#title').classList.add('hidden'); openCreator(startGame); }, 450);
}
addEventListener('keydown', leaveTitle);
$('#title').addEventListener('click', leaveTitle);
window.__game = { animateRig, setRot, player, villagers, trees, pickups, butterflies, POND, HOUSES, get hour() { return hour; }, set hour(v) { hour = v; } };
frame();
