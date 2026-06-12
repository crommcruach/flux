/**
 * Flux Shader Editor — Pure client-side WGSL development tool
 * Uses WebGPU with the same binding convention as src/modules/gpu/renderer.py
 *
 * Binding layout (matches Python Renderer):
 *   @binding(0) var<uniform> u: Uniforms;            // 256 bytes = 64×f32 = 16×vec4
 *   @binding(1) var tex0: texture_2d<f32>;           // slot 0
 *   @binding(2) var samp0: sampler;
 *   @binding(3) var tex1: texture_2d<f32>;           // slot 1 (blend/transition)
 *   @binding(4) var samp1: sampler;
 */

'use strict';

// ═══════════════════════════════════════════════════════════════════════════
// WGSL TEMPLATES
// ═══════════════════════════════════════════════════════════════════════════

const WGSL_HEADER = `// ── Standard binding layout (DO NOT CHANGE) ───────────────────────────────
struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;
`;

const WGSL_TEX1 = `@group(0) @binding(1) var tex0: texture_2d<f32>;
@group(0) @binding(2) var samp0: sampler;
`;

const WGSL_TEX2 = `@group(0) @binding(1) var tex0: texture_2d<f32>;
@group(0) @binding(2) var samp0: sampler;
@group(0) @binding(3) var tex1: texture_2d<f32>;
@group(0) @binding(4) var samp1: sampler;
`;

const WGSL_VERTEX = `
struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0),
        vec2<f32>(2.0, 1.0),
        vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(pos[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}
`;

const TEMPLATES = {
  effect: `// my_effect.wgsl — one-sentence description of what this effect does.
//
// Uniforms (u.data slots):
//   [0].x  strength   (f32, 0.0..1.0, default: 0.5)   Effect strength
//   [0].y  threshold  (f32, 0.0..1.0, default: 0.5)   Threshold value
//
// Textures: binding 1 = inputTexture (one frame in, one frame out)

${WGSL_HEADER}
${WGSL_TEX1}
${WGSL_VERTEX}
@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let strength  = u.data[0].x;
    let threshold = u.data[0].y;

    let src = textureSample(tex0, samp0, in.uv);

    // ── Your pixel math here ───────────────────────────────────────────────
    // All values are linear 0..1 float. Output alpha should normally be preserved.
    let result = mix(src.rgb, 1.0 - src.rgb, strength);  // example: invert

    return vec4<f32>(result, src.a);
}
`,

  source: `// my_source.wgsl — procedural generator (no input texture).
//
// Uniforms (u.data slots):
//   [0].x  time       (f32, 0.0..1e9, default: 0.0)   Seconds (auto-updated)
//   [0].y  speed      (f32, 0.1..4.0, default: 1.0)   Animation speed
//   [0].z  scale      (f32, 0.1..8.0, default: 2.0)   Pattern scale
//   [0].w  hue_shift  (f32, 0.0..1.0, default: 0.0)   Hue offset
//
// Textures: none (generator, writes pixels from scratch)

${WGSL_HEADER}
${WGSL_VERTEX}
fn hsv_to_rgb(h: f32, s: f32, v: f32) -> vec3<f32> {
    let c  = v * s;
    let x  = c * (1.0 - abs(fract(h * 3.0) * 2.0 - 1.0));
    let m  = v - c;
    let h6 = h * 6.0;
    var rgb: vec3<f32>;
    if      (h6 < 1.0) { rgb = vec3<f32>(c, x, 0.0); }
    else if (h6 < 2.0) { rgb = vec3<f32>(x, c, 0.0); }
    else if (h6 < 3.0) { rgb = vec3<f32>(0.0, c, x); }
    else if (h6 < 4.0) { rgb = vec3<f32>(0.0, x, c); }
    else if (h6 < 5.0) { rgb = vec3<f32>(x, 0.0, c); }
    else               { rgb = vec3<f32>(c, 0.0, x); }
    return rgb + m;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let t         = u.data[0].x;
    let speed     = u.data[0].y;
    let scale     = max(u.data[0].z, 0.001);
    let hue_shift = u.data[0].w;

    let uv = in.uv * scale;

    // ── Your generator math here ───────────────────────────────────────────
    let v1 = sin(uv.x + t * speed);
    let v2 = sin(uv.y + t * speed * 0.7);
    let v3 = sin((uv.x + uv.y) * 0.5 + t * speed * 0.5);
    let val = (v1 + v2 + v3) / 3.0 * 0.5 + 0.5;

    let hue = fract(val + hue_shift + t * 0.05);
    let rgb = hsv_to_rgb(hue, 0.8, 0.9);

    return vec4<f32>(rgb, 1.0);
}
`,

  blend: `// my_blend.wgsl — composite two layers with custom blend math.
//
// Uniforms (u.data slots):
//   [0].x  opacity  (f32, 0.0..1.0, default: 1.0)   Overlay opacity
//   [0].y  mix_amt  (f32, 0.0..1.0, default: 0.5)   Blend mix amount
//
// Textures: binding 1 = base layer, binding 3 = overlay layer

${WGSL_HEADER}
${WGSL_TEX2}
${WGSL_VERTEX}
@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let opacity = u.data[0].x;
    let mix_amt = u.data[0].y;

    let base    = textureSample(tex0, samp0, in.uv);
    let overlay = textureSample(tex1, samp1, in.uv);

    // ── Your blend math here ───────────────────────────────────────────────
    // Example: screen blend
    let blended = 1.0 - (1.0 - base.rgb) * (1.0 - overlay.rgb);
    let result  = mix(base.rgb, blended, opacity * mix_amt);

    return vec4<f32>(result, base.a);
}
`,

  transition: `// my_transition.wgsl — animated transition between two clips.
//
// Uniforms (u.data slots):
//   [0].x  progress  (f32, 0.0..1.0, default: 0.5)  0=full A, 1=full B (pre-eased)
//
// Textures: binding 1 = clip_a (outgoing), binding 3 = clip_b (incoming)

${WGSL_HEADER}
${WGSL_TEX2}
${WGSL_VERTEX}
@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let progress = u.data[0].x;

    let ca = textureSample(tex0, samp0, in.uv);
    let cb = textureSample(tex1, samp1, in.uv);

    // ── Your transition math here ──────────────────────────────────────────
    // Example: slide wipe from left to right
    let edge     = progress;
    let softness = 0.05;
    let mask     = smoothstep(edge - softness, edge + softness, in.uv.x);

    return mix(ca, cb, mask);
}
`,
};

// ═══════════════════════════════════════════════════════════════════════════
// UNIFORM PARSER
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Parse uniform declarations from WGSL comment header.
 * Supported format:
 *   //   [N].x  name  (f32, min..max, default: val)  Description
 *   //   [N].y  name  (i32, 0..N)  Description  (→ integer, select or number input)
 */
function parseUniforms(wgsl) {
  const uniforms = [];
  const componentMap = { x: 0, y: 1, z: 2, w: 3 };
  // Pattern: //   [N].comp  name  (type, min..max, default: val)  desc
  const re = /\/\/\s+\[(\d+)\]\.([xyzw])\s+(\w+)\s+\((f32|i32|u32),\s*([-\d.e+]+)\.\.([-\d.e+]+)(?:,\s*default:\s*([-\d.e+]+))?\)(?:\s+(.+))?/g;
  let m;
  while ((m = re.exec(wgsl)) !== null) {
    const vec4idx = parseInt(m[1], 10);
    const comp    = componentMap[m[2]] ?? 0;
    const bufIdx  = vec4idx * 4 + comp;
    uniforms.push({
      bufIdx,
      vec4idx,
      comp: m[2],
      name:    m[3],
      type:    m[4],          // f32 | i32 | u32
      min:     parseFloat(m[5]),
      max:     parseFloat(m[6]),
      default: m[7] !== undefined ? parseFloat(m[7]) : parseFloat(m[5]),
      desc:    m[8] ? m[8].trim() : '',
    });
  }
  return uniforms;
}

// ═══════════════════════════════════════════════════════════════════════════
// TEST PATTERN GENERATOR (CPU → ImageBitmap)
// ═══════════════════════════════════════════════════════════════════════════

const PATTERNS = ['checkerboard', 'gradient_h', 'gradient_v', 'gradient_r',
                  'solid_red', 'solid_blue', 'noise', 'uv_map'];

async function makePatternBitmap(pattern, w, h, time = 0) {
  const c = new OffscreenCanvas(w, h);
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(w, h);
  const d = img.data;

  switch (pattern) {
    case 'checkerboard': {
      const sz = Math.max(8, Math.floor(w / 16));
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const v = (((x / sz) | 0) + ((y / sz) | 0)) % 2 === 0 ? 200 : 55;
        const i = (y * w + x) * 4;
        d[i] = d[i+1] = d[i+2] = v; d[i+3] = 255;
      }
      break;
    }
    case 'gradient_h': {
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const t = x / (w - 1);
        const i = (y * w + x) * 4;
        d[i] = t * 255; d[i+1] = 80; d[i+2] = (1 - t) * 200; d[i+3] = 255;
      }
      break;
    }
    case 'gradient_v': {
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const t = y / (h - 1);
        const i = (y * w + x) * 4;
        d[i] = 80; d[i+1] = t * 255; d[i+2] = (1 - t) * 200; d[i+3] = 255;
      }
      break;
    }
    case 'gradient_r': {
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const dx = x / w - 0.5, dy = y / h - 0.5;
        const r = Math.min(1, Math.sqrt(dx*dx + dy*dy) * 2);
        const i = (y * w + x) * 4;
        d[i] = (1-r)*255; d[i+1] = r*150; d[i+2] = 100; d[i+3] = 255;
      }
      break;
    }
    case 'solid_red': {
      for (let i = 0; i < d.length; i += 4) { d[i]=220; d[i+1]=60; d[i+2]=60; d[i+3]=255; }
      break;
    }
    case 'solid_blue': {
      for (let i = 0; i < d.length; i += 4) { d[i]=60; d[i+1]=80; d[i+2]=220; d[i+3]=255; }
      break;
    }
    case 'noise': {
      for (let i = 0; i < d.length; i += 4) {
        const v = (Math.random() * 255) | 0;
        d[i] = v; d[i+1] = v; d[i+2] = v; d[i+3] = 255;
      }
      break;
    }
    case 'uv_map': {
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const i = (y * w + x) * 4;
        d[i] = (x / w) * 255; d[i+1] = (y / h) * 255; d[i+2] = 100; d[i+3] = 255;
      }
      break;
    }
  }
  ctx.putImageData(img, 0, 0);
  return createImageBitmap(c);
}

// ═══════════════════════════════════════════════════════════════════════════
// WEBGPU ENGINE
// ═══════════════════════════════════════════════════════════════════════════

class WebGPUEngine {
  constructor(canvas, onLog) {
    this.canvas      = canvas;
    this.onLog       = onLog;
    this.device      = null;
    this.context     = null;
    this.format      = null;
    this.sampler     = null;
    this.uniformBuf  = null;
    this.pipeline    = null;
    this.bgl         = null;
    this.textures    = [];      // GPUTexture[]
    this.raf         = null;
    this.startTime   = 0;
    this.frameCount  = 0;
    this.fps         = 0;
    this._lastFpsTs  = 0;
    this._fpsFrames  = 0;
    this.onFPS       = null;
  }

  async init() {
    if (!navigator.gpu) throw new Error('WebGPU not supported in this browser. Use Chrome 113+ or Edge 113+.');
    const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
    if (!adapter) throw new Error('No WebGPU adapter found. GPU acceleration may be disabled.');
    const adapterInfo = adapter.info || {};
    this.device  = await adapter.requestDevice();
    this.format  = navigator.gpu.getPreferredCanvasFormat();
    this.context = this.canvas.getContext('webgpu');
    this.context.configure({ device: this.device, format: this.format, alphaMode: 'opaque' });
    this.sampler = this.device.createSampler({ minFilter: 'linear', magFilter: 'linear', addressModeU: 'clamp-to-edge', addressModeV: 'clamp-to-edge' });
    this.uniformBuf = this.device.createBuffer({ size: 256, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    return adapterInfo.description || adapterInfo.device || 'WebGPU GPU';
  }

  /**
   * Build pipeline from WGSL source.
   * texCount = 0 (source), 1 (effect), 2 (blend/transition)
   * Returns { ok, errors[] }
   */
  async compile(wgsl, texCount) {
    const device = this.device;

    // BGL exactly mirrors Python Renderer
    const bglEntries = [
      { binding: 0, visibility: GPUShaderStage.VERTEX | GPUShaderStage.FRAGMENT,
        buffer: { type: 'uniform' } },
    ];
    for (let i = 0; i < texCount; i++) {
      bglEntries.push(
        { binding: 1 + i * 2, visibility: GPUShaderStage.FRAGMENT, texture: { sampleType: 'float', viewDimension: '2d' } },
        { binding: 2 + i * 2, visibility: GPUShaderStage.FRAGMENT, sampler: { type: 'filtering' } },
      );
    }
    const bgl = device.createBindGroupLayout({ entries: bglEntries });

    const shaderModule = device.createShaderModule({ code: wgsl });

    // Get compile errors
    let errors = [];
    try {
      const info = await shaderModule.getCompilationInfo();
      errors = info.messages.filter(m => m.type === 'error').map(m => `Line ${m.lineNum}: ${m.message}`);
    } catch (_) { /* getCompilationInfo not available in all builds */ }

    if (errors.length > 0) return { ok: false, errors };

    let pipeline;
    try {
      pipeline = device.createRenderPipeline({
        layout: device.createPipelineLayout({ bindGroupLayouts: [bgl] }),
        vertex:   { module: shaderModule, entryPoint: 'vs_main' },
        fragment: { module: shaderModule, entryPoint: 'fs_main', targets: [{ format: this.format }] },
        primitive: { topology: 'triangle-list' },
      });
    } catch (e) {
      // Try to extract the error message
      const msg = e?.message || String(e);
      return { ok: false, errors: [msg] };
    }

    this.pipeline = pipeline;
    this.bgl      = bgl;
    this.texCount = texCount;
    return { ok: true, errors: [] };
  }

  /** Upload a bitmap as a GPU texture (replaces slot i). */
  async uploadBitmap(bitmap, slot = 0) {
    const w = bitmap.width, h = bitmap.height;
    const tex = this.device.createTexture({
      size: [w, h, 1],
      format: 'rgba8unorm',
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT,
    });
    this.device.queue.copyExternalImageToTexture({ source: bitmap }, { texture: tex }, [w, h]);
    if (this.textures[slot]) this.textures[slot].destroy();
    this.textures[slot] = tex;
  }

  /** Upload a <video> element frame to slot i. Returns false if video not ready. */
  uploadVideoFrame(videoEl, slot = 0) {
    if (!videoEl || videoEl.readyState < 2) return false;
    const w = videoEl.videoWidth || 320, h = videoEl.videoHeight || 240;
    // Re-create texture lazily when size changes
    if (!this.textures[slot] || this.textures[slot].width !== w || this.textures[slot].height !== h) {
      if (this.textures[slot]) this.textures[slot].destroy();
      this.textures[slot] = this.device.createTexture({
        size: [w, h, 1],
        format: 'rgba8unorm',
        usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT,
      });
    }
    try {
      this.device.queue.copyExternalImageToTexture({ source: videoEl }, { texture: this.textures[slot] }, [w, h]);
      return true;
    } catch (_) { return false; }
  }

  /** Write uniform Float32Array (64 floats) to GPU. */
  writeUniforms(data /* Float32Array */) {
    this.device.queue.writeBuffer(this.uniformBuf, 0, data.buffer, 0, 256);
  }

  /** Render one frame using current pipeline + textures. */
  renderFrame(uniformData) {
    if (!this.pipeline) return;
    this.writeUniforms(uniformData);

    const canvasTex = this.context.getCurrentTexture();
    const entries   = [{ binding: 0, resource: { buffer: this.uniformBuf } }];
    for (let i = 0; i < (this.texCount || 0); i++) {
      const tex = this.textures[i];
      if (!tex) return; // texture not loaded yet
      entries.push(
        { binding: 1 + i * 2, resource: tex.createView() },
        { binding: 2 + i * 2, resource: this.sampler },
      );
    }

    const bg  = this.device.createBindGroup({ layout: this.bgl, entries });
    const enc = this.device.createCommandEncoder();
    const pass = enc.beginRenderPass({
      colorAttachments: [{ view: canvasTex.createView(), loadOp: 'clear', storeOp: 'store', clearValue: [0, 0, 0, 1] }],
    });
    pass.setPipeline(this.pipeline);
    pass.setBindGroup(0, bg);
    pass.draw(3);
    pass.end();
    this.device.queue.submit([enc.finish()]);

    // FPS counter
    this._fpsFrames++;
    const now = performance.now();
    if (now - this._lastFpsTs >= 500) {
      this.fps = Math.round(this._fpsFrames / ((now - this._lastFpsTs) / 1000));
      this._fpsFrames = 0;
      this._lastFpsTs = now;
      if (this.onFPS) this.onFPS(this.fps);
    }
  }

  stopLoop() {
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = null; }
  }

  destroy() {
    this.stopLoop();
    this.textures.forEach(t => t?.destroy());
    this.textures = [];
    this.uniformBuf?.destroy();
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// PYTHON STUB GENERATOR
// ═══════════════════════════════════════════════════════════════════════════

function generatePythonStub(category, filename, uniforms) {
  const noExt   = filename.replace(/\.wgsl$/, '');
  const clsName = noExt.split(/[_\-]/).map(w => w[0].toUpperCase() + w.slice(1)).join('');
  const pluginType = category === 'source' ? 'GENERATOR' : 'EFFECT';
  const category_label = { effect: 'Custom Effects', source: 'Generators', blend: 'Blend', transition: 'Transitions' }[category] || 'Custom';

  // Build PARAMETERS list
  const params = uniforms.map(u => {
    const ptype = u.type === 'f32' ? 'ParameterType.FLOAT' : 'ParameterType.INT';
    return `        {'id': '${u.name}', 'name': '${u.name}', 'type': ${ptype},\n` +
           `         'default': ${u.default}, 'min': ${u.min}, 'max': ${u.max}},`;
  }).join('\n');

  // Build get_uniforms body
  const uniformLines = uniforms.map(u =>
    `            '${u.name}': self.get_param('${u.name}'),`
  ).join('\n');

  // Source path relative to plugin file
  const isSource = category === 'source';
  const shaderRelPath = isSource
    ? `os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', '${filename}')`
    : `os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', '${filename}')`;

  const twoTexNote = (category === 'blend' || category === 'transition')
    ? '\n# NOTE: This shader expects TWO input textures (tex0 = base/A, tex1 = overlay/B).\n# Integration: used by compositor blend pass or transition manager, not as a standalone effect.\n'
    : '';

  return `"""
${clsName} — ${category} plugin for Flux.
Generated by Flux Shader Editor. Customize as needed.
"""
import os
import time
from plugins import PluginBase, PluginType, ParameterType
${twoTexNote}
_SHADER_PATH = ${shaderRelPath}


class ${clsName}(PluginBase):

    # Shader source cached at class level — loaded once, reused every frame
    _shader_src: str | None = None

    METADATA = {
        'id': '${noExt}',
        'name': '${clsName.replace(/([A-Z])/g, ' $1').trim()}',
        'description': 'Generated ${category} shader plugin',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.${pluginType},
        'category': '${category_label}',
    }

    PARAMETERS = [
${params || "        # No uniforms detected — add parameters here"}
    ]
${isSource ? `
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_time = time.time()
` : ''}
    def process_frame(self, frame, **kwargs):
        """GPU-native — this stub is never called on live frames."""
        return frame

    def get_shader(self) -> str | None:
        if ${clsName}._shader_src is None:
            with open(_SHADER_PATH, encoding='utf-8') as f:
                ${clsName}._shader_src = f.read()
        return ${clsName}._shader_src

    def get_uniforms(self, **kwargs) -> dict:
        ${isSource ? `t = time.time() - self._start_time` : ''}
        return {
${isSource && uniforms.some(u => u.name === 'time') ? `            'time': t,` : ''}
${uniformLines || '            # no uniforms'}
        }
`;
}

// ═══════════════════════════════════════════════════════════════════════════
// AI PROMPT BUILDER
// ═══════════════════════════════════════════════════════════════════════════

function buildAIPrompt(category, filename, wgslCode, userGoal) {
  const texDesc = {
    effect:     'binding 1/2 = tex0 (input frame)',
    source:     'no textures — generate pixels from scratch',
    blend:      'binding 1/2 = tex0 (base), binding 3/4 = tex1 (overlay)',
    transition: 'binding 1/2 = tex0 (outgoing), binding 3/4 = tex1 (incoming)',
  }[category];

  return `You are helping me write a WGSL fragment shader for the Flux VJ application.
This app uses wgpu (WebGPU) via Python, rendered with a full-screen triangle.

## SHADER CATEGORY: ${category.toUpperCase()}
## FILE: ${filename}

## MANDATORY BINDING CONVENTION (do not change these declarations)
\`\`\`wgsl
struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;

// Uniform access: u.data[N].x / .y / .z / .w  (64 total f32 slots)
// Textures: ${texDesc}
\`\`\`

## UNIFORM COMMENT FORMAT (required in every shader you write)
\`\`\`
//   [N].x  param_name  (f32, min..max, default: val)  Short description
//   [N].y  param_name  (i32, 0..6)                    Integer / enum
\`\`\`

## VERTEX SHADER (always identical — do not change)
\`\`\`wgsl
struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}
@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut { ... /* full-screen triangle */ }
\`\`\`

## CURRENT SHADER CODE
\`\`\`wgsl
${wgslCode.trim()}
\`\`\`

## WHAT I WANT TO ACHIEVE
${userGoal || '[ Describe your effect here before copying this prompt ]'}

## REQUIREMENTS
- Keep the exact binding declarations shown above
- Document ALL uniforms in the comment header (format shown above)
- Fragment shader entry point must be \`fs_main\`
- Output linear 0..1 f32 color: \`@location(0) vec4<f32>\`
- Preserve alpha from source texture unless intentionally modifying it
- No CPU fallback logic — pure WGSL fragment shader only
- Keep it GPU-friendly: avoid unbounded loops, prefer math over branching
`;
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════

class ShaderEditorApp {
  constructor() {
    this.category  = 'effect';
    this.editor    = null;    // Monaco editor instance
    this.gpu       = null;    // WebGPUEngine
    this.uniforms  = [];      // parsed uniform definitions
    this.uniformBuf = new Float32Array(64); // 256-byte packed uniform buffer
    this.animating = false;
    this.startTime = 0;
    this.texSources = ['checkerboard', 'checkerboard']; // patterns for slot 0 and 1
    this.videoEls   = [null, null];  // <video> elements for video inputs
    this.fsaDirHandles = {};  // File System Access directory handles
    this._rafHandle = null;
    // Map [vecIdx*4+comp] → uniform def
    this.uniformMap = new Map();
  }

  // ── Bootstrap ────────────────────────────────────────────────────────────
  async init() {
    // Init GPU
    this.gpu = new WebGPUEngine(document.getElementById('preview-canvas'), (msg, level) => this.log(msg, level));
    this.gpu.onFPS = fps => {
      document.getElementById('fps-display').textContent = `${fps} fps`;
    };

    try {
      const gpuName = await this.gpu.init();
      this.setGPUStatus(true, gpuName);
      this.log(`WebGPU ready: ${gpuName}`, 'success');
    } catch (e) {
      this.setGPUStatus(false, e.message);
      this.log(e.message, 'error');
    }

    this.buildTestPanelUI();
    this.bindUIEvents();
    this.setCategory('effect');  // loads template + calls compileAndRun
  }

  // ── Category ─────────────────────────────────────────────────────────────
  setCategory(cat) {
    this.category = cat;
    document.querySelectorAll('.cat-pill').forEach(p => p.classList.toggle('active', p.dataset.cat === cat));
    // Load template only if editor is currently showing a template (not user work)
    if (this.editor) {
      const currentVal = this.editor.getValue().trim();
      const isTemplate = Object.values(TEMPLATES).some(t => t.trim() === currentVal) || currentVal === '';
      if (isTemplate || currentVal === '') {
        this.editor.setValue(TEMPLATES[cat]);
        this.editor.revealLine(1);
      }
    }
    this.updateTestPanelForCategory();
    this.runShader();
  }

  // ── Monaco editor init (called after Monaco loads) ───────────────────────
  initEditor() {
    // Register WGSL as a language with basic highlighting
    monaco.languages.register({ id: 'wgsl' });
    monaco.languages.setMonarchTokensProvider('wgsl', {
      keywords: ['fn', 'struct', 'var', 'let', 'const', 'if', 'else', 'return', 'loop', 'for', 'while',
                 'break', 'continue', 'switch', 'case', 'default', 'override', 'enable', 'alias'],
      types: ['f32', 'i32', 'u32', 'bool', 'vec2', 'vec3', 'vec4', 'mat2x2', 'mat3x3', 'mat4x4',
              'mat2x4', 'mat4x2', 'texture_2d', 'sampler', 'array', 'ptr', 'atomic'],
      builtins: ['textureSample', 'textureLoad', 'textureDimensions', 'sin', 'cos', 'tan', 'abs',
                 'clamp', 'mix', 'step', 'smoothstep', 'length', 'distance', 'dot', 'cross',
                 'normalize', 'reflect', 'refract', 'floor', 'ceil', 'round', 'fract', 'sqrt',
                 'pow', 'exp', 'log', 'min', 'max', 'sign', 'mod', 'atan', 'atan2', 'asin',
                 'acos', 'bitcast', 'select'],
      tokenizer: {
        root: [
          [/@[a-z_]+/, 'keyword.control'],  // decorators
          [/\/\/.*$/, 'comment'],
          [/"[^"]*"/, 'string'],
          [/\d+\.\d*([eE][-+]?\d+)?[f]?/, 'number.float'],
          [/\d+[ui]?/, 'number'],
          [/[a-zA-Z_]\w*/, { cases: { '@keywords': 'keyword', '@types': 'type', '@builtins': 'support.function', '@default': 'identifier' } }],
          [/[+\-*\/=<>!&|^~%?:]+/, 'operator'],
        ],
      },
    });

    this.editor = monaco.editor.create(document.getElementById('editor-container'), {
      value:     TEMPLATES[this.category],
      language:  'wgsl',
      theme:     'vs-dark',
      fontSize:  13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
      fontLigatures: true,
      minimap:   { enabled: false },
      lineNumbers: 'on',
      wordWrap:  'off',
      automaticLayout: true,
      scrollBeyondLastLine: false,
      renderWhitespace: 'selection',
      padding: { top: 10 },
      quickSuggestions: { other: true, comments: false, strings: false },
    });

    // Auto-run on Ctrl+Enter
    this.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => this.runShader());
    // Format document (Shift+Alt+F)
    this.editor.addAction({
      id: 'run-shader',
      label: 'Run Shader',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: () => this.runShader(),
    });

    // Rebuild uniform sliders on content change (debounced)
    let debounce;
    this.editor.onDidChangeModelContent(() => {
      clearTimeout(debounce);
      debounce = setTimeout(() => this.refreshUniformsUI(), 400);
    });

    this.refreshUniformsUI();
  }

  // ── Run Shader ────────────────────────────────────────────────────────────
  async runShader() {
    if (!this.gpu || !this.gpu.device) {
      this.log('WebGPU not available', 'error');
      return;
    }
    const wgsl = this.editor ? this.editor.getValue() : TEMPLATES[this.category];
    if (!wgsl.trim()) return;

    this.setStatus('Compiling…', 'accent');
    this.gpu.stopLoop();

    // Detect texture count from WGSL source
    const texCount = (wgsl.match(/@group\(0\)\s+@binding\([13]\)/g) || []).length;

    const result = await this.gpu.compile(wgsl, texCount);
    if (!result.ok) {
      result.errors.forEach(e => this.log(e, 'error'));
      this.setStatus('Compile error', 'error');
      return;
    }
    this.log(`Compiled (${texCount} texture${texCount !== 1 ? 's' : ''}) — Ctrl+Enter to recompile`, 'success');
    this.setStatus(`Running · ${texCount} tex`, 'idle');

    // Load test textures
    await this.loadTestTextures();

    // Update uniforms UI (in case shader changed)
    this.refreshUniformsUI();

    // Start render loop
    this.startTime = performance.now();
    document.getElementById('preview-placeholder').classList.add('hidden');
    this.startRenderLoop();
  }

  startRenderLoop() {
    this.gpu.stopLoop();
    const loop = () => {
      this.tickUniforms();
      this.tickVideoFrames();
      this.gpu.renderFrame(this.uniformBuf);
      document.getElementById('preview-overlay').textContent =
        `${this.gpu.canvas.width}×${this.gpu.canvas.height}`;
      this.gpu.raf = requestAnimationFrame(loop);
    };
    loop();
  }

  /** Update time uniform (slot 0 if named 'time') + any animated uniforms. */
  tickUniforms() {
    const t = (performance.now() - this.startTime) / 1000;
    // Auto-fill any uniform named 'time' with elapsed seconds
    for (const u of this.uniforms) {
      if (u.name === 'time') {
        this.uniformBuf[u.bufIdx] = t;
      }
    }
  }

  /** Copy latest video frames to GPU textures. */
  tickVideoFrames() {
    for (let slot = 0; slot < 2; slot++) {
      const v = this.videoEls[slot];
      if (v && !v.paused && v.readyState >= 2) {
        this.gpu.uploadVideoFrame(v, slot);
      }
    }
  }

  // ── Test Textures ─────────────────────────────────────────────────────────
  async loadTestTextures() {
    const needed = this.category === 'blend' || this.category === 'transition' ? 2 : 1;
    for (let slot = 0; slot < needed; slot++) {
      const src = this.texSources[slot];
      if (src === 'video') continue; // handled per-frame in tickVideoFrames
      if (src && PATTERNS.includes(src)) {
        const bmp = await makePatternBitmap(src, 512, 288);
        await this.gpu.uploadBitmap(bmp, slot);
      }
    }
  }

  async loadFileTexture(slot, file) {
    try {
      const bmp = await createImageBitmap(file);
      await this.gpu.uploadBitmap(bmp, slot);
      this.texSources[slot] = 'file';
      this.setTexStatus(slot, `${file.name} (${bmp.width}×${bmp.height})`, 'ok');
    } catch (e) {
      this.setTexStatus(slot, `Error: ${e.message}`, 'err');
    }
  }

  async loadURLTexture(slot, url) {
    this.setTexStatus(slot, 'Fetching…', '');
    try {
      // Try image first
      const resp = await fetch(url);
      const blob = await resp.blob();
      if (blob.type.startsWith('video/')) {
        await this.loadVideoTexture(slot, url);
      } else {
        const bmp = await createImageBitmap(blob);
        await this.gpu.uploadBitmap(bmp, slot);
        this.texSources[slot] = 'url';
        this.setTexStatus(slot, `Loaded (${bmp.width}×${bmp.height})`, 'ok');
      }
    } catch (e) {
      this.setTexStatus(slot, `Fetch failed: ${e.message}`, 'err');
    }
  }

  async loadVideoTexture(slot, src) {
    const v = document.createElement('video');
    v.src = src; v.loop = true; v.muted = true; v.playsInline = true; v.crossOrigin = 'anonymous';
    v.style.display = 'none';
    document.body.appendChild(v);
    await v.play().catch(() => {});
    this.videoEls[slot] = v;
    this.texSources[slot] = 'video';
    this.setTexStatus(slot, `Video: ${src.split('/').pop()}`, 'ok');
  }

  // ── Uniform UI ────────────────────────────────────────────────────────────
  refreshUniformsUI() {
    const wgsl = this.editor ? this.editor.getValue() : '';
    this.uniforms = parseUniforms(wgsl);
    // Rebuild map
    this.uniformMap.clear();
    this.uniforms.forEach(u => this.uniformMap.set(u.bufIdx, u));
    // Set defaults in buffer
    this.uniforms.forEach(u => { if (this.uniformBuf[u.bufIdx] === 0) this.uniformBuf[u.bufIdx] = u.default; });

    const container = document.getElementById('uniforms-container');
    container.innerHTML = '';

    if (this.uniforms.length === 0) {
      container.innerHTML = '<div class="no-uniforms">No @uniform comments found in shader</div>';
      document.querySelector('[data-panel="uniforms"] .badge').textContent = '0';
      return;
    }
    document.querySelector('[data-panel="uniforms"] .badge').textContent = this.uniforms.length;

    this.uniforms.forEach(u => {
      const div = document.createElement('div');
      div.className = 'uniform-ctrl';
      const valId = `uval-${u.bufIdx}`;
      const ctrlId = `uctrl-${u.bufIdx}`;

      if (u.type === 'i32' || u.type === 'u32') {
        div.innerHTML = `
          <div class="uniform-label">
            <span class="uniform-label-name">${u.name}</span>
            <span class="uniform-label-val" id="${valId}">${u.default | 0}</span>
          </div>
          <input type="number" class="uniform-number" id="${ctrlId}"
            value="${u.default | 0}" min="${u.min | 0}" max="${u.max | 0}" step="1">
          ${u.desc ? `<div class="uniform-hint">${u.desc}</div>` : ''}`;
        div.querySelector(`#${ctrlId}`).addEventListener('input', e => {
          const v = parseInt(e.target.value, 10) || 0;
          document.getElementById(valId).textContent = v;
          // Store as bitcast f32 (same as Python)
          const tmp = new Int32Array(1); tmp[0] = v;
          this.uniformBuf[u.bufIdx] = new Float32Array(tmp.buffer)[0];
        });
      } else {
        const step = (u.max - u.min) / 200;
        div.innerHTML = `
          <div class="uniform-label">
            <span class="uniform-label-name">${u.name}</span>
            <span class="uniform-label-val" id="${valId}">${u.default.toFixed(3)}</span>
          </div>
          <input type="range" class="uniform-range" id="${ctrlId}"
            min="${u.min}" max="${u.max}" step="${step}" value="${u.default}">
          ${u.desc ? `<div class="uniform-hint">${u.desc}</div>` : ''}`;
        div.querySelector(`#${ctrlId}`).addEventListener('input', e => {
          const v = parseFloat(e.target.value);
          document.getElementById(valId).textContent = v.toFixed(3);
          this.uniformBuf[u.bufIdx] = v;
          if (u.name !== 'time') {} // time is auto-ticked
        });
        // Init buffer
        this.uniformBuf[u.bufIdx] = u.default;
      }
      container.appendChild(div);
    });
  }

  // ── Test Panel UI ─────────────────────────────────────────────────────────
  buildTestPanelUI() {
    this.updateTestPanelForCategory();
  }

  updateTestPanelForCategory() {
    const twoTex = this.category === 'blend' || this.category === 'transition';
    const noTex  = this.category === 'source';
    const wrap   = document.getElementById('test-inputs-wrap');
    wrap.innerHTML = '';

    const slots = noTex ? [] : twoTex ? [0, 1] : [0];
    const labels = twoTex
      ? (this.category === 'transition' ? ['Clip A (outgoing)', 'Clip B (incoming)'] : ['Base Layer', 'Overlay Layer'])
      : ['Input Texture'];

    if (noTex) {
      wrap.innerHTML = '<div class="no-uniforms">Source generates pixels — no input texture</div>';
      return;
    }

    slots.forEach(slot => {
      const g = document.createElement('div');
      g.className = 'tex-input-group';
      g.innerHTML = `<div class="tex-input-label">${labels[slot]}</div>`;

      // Pattern grid
      const grid = document.createElement('div');
      grid.className = 'tex-pattern-grid';
      const patLabels = { checkerboard: 'Check', gradient_h: 'Grad H', gradient_v: 'Grad V',
                          gradient_r: 'Radial', solid_red: 'Red', solid_blue: 'Blue',
                          noise: 'Noise', uv_map: 'UV Map' };
      PATTERNS.forEach(pat => {
        const btn = document.createElement('button');
        btn.className = 'pat-btn' + (this.texSources[slot] === pat ? ' active' : '');
        btn.textContent = patLabels[pat] || pat;
        btn.title = pat;
        btn.addEventListener('click', async () => {
          this.texSources[slot] = pat;
          grid.querySelectorAll('.pat-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const bmp = await makePatternBitmap(pat, 512, 288);
          await this.gpu.uploadBitmap(bmp, slot);
        });
        grid.appendChild(btn);
      });
      g.appendChild(grid);

      // File + URL
      const statusId = `tex-status-${slot}`;
      g.insertAdjacentHTML('beforeend', `
        <div class="tex-file-row">
          <button class="tex-file-btn" id="tex-file-btn-${slot}">📂 Load File</button>
          <button class="tex-file-btn" id="tex-vid-btn-${slot}">🎬 Load Video</button>
        </div>
        <div class="tex-url-row">
          <input class="tex-url-input" id="tex-url-${slot}" placeholder="Image / video URL…" type="text">
          <button class="tex-url-btn" id="tex-url-btn-${slot}">↵</button>
        </div>
        <div class="tex-status" id="${statusId}"></div>
      `);
      wrap.appendChild(g);

      // Bind file loaders
      document.getElementById(`tex-file-btn-${slot}`).addEventListener('click', () => {
        const inp = document.createElement('input');
        inp.type = 'file'; inp.accept = 'image/*';
        inp.onchange = e => { if (e.target.files[0]) this.loadFileTexture(slot, e.target.files[0]); };
        inp.click();
      });
      document.getElementById(`tex-vid-btn-${slot}`).addEventListener('click', () => {
        const inp = document.createElement('input');
        inp.type = 'file'; inp.accept = 'video/*';
        inp.onchange = e => {
          if (!e.target.files[0]) return;
          const url = URL.createObjectURL(e.target.files[0]);
          this.loadVideoTexture(slot, url).then(() => this.setTexStatus(slot, `Video: ${e.target.files[0].name}`, 'ok'));
        };
        inp.click();
      });
      document.getElementById(`tex-url-btn-${slot}`).addEventListener('click', () => {
        const url = document.getElementById(`tex-url-${slot}`).value.trim();
        if (url) this.loadURLTexture(slot, url);
      });
      document.getElementById(`tex-url-${slot}`).addEventListener('keydown', e => {
        if (e.key === 'Enter') {
          const url = e.target.value.trim();
          if (url) this.loadURLTexture(slot, url);
        }
      });
    });

    // Animate row
    wrap.insertAdjacentHTML('beforeend', `
      <div class="animate-row">
        <label><input type="checkbox" id="animate-chk" checked> Auto-animate (time uniform)</label>
        <span id="fps-display">-- fps</span>
      </div>
    `);
    document.getElementById('animate-chk').addEventListener('change', e => {
      if (!e.target.checked) this.startTime = performance.now(); // reset time when re-enabled
    });
  }

  setTexStatus(slot, msg, cls) {
    const el = document.getElementById(`tex-status-${slot}`);
    if (el) { el.textContent = msg; el.className = `tex-status ${cls}`; }
  }

  // ── Preview canvas resize ─────────────────────────────────────────────────
  setPreviewRes(w, h) {
    const canvas = document.getElementById('preview-canvas');
    canvas.width  = w; canvas.height = h;
    const wrap = document.getElementById('preview-canvas-wrap');
    const maxW = wrap.clientWidth  || 370;
    const maxH = Math.round(maxW * h / w);
    wrap.style.height = `${Math.min(maxH, 240)}px`;
    if (this.gpu && this.gpu.context) {
      this.gpu.context.configure({ device: this.gpu.device, format: this.gpu.format, alphaMode: 'opaque' });
    }
  }

  // ── UI Event Bindings ─────────────────────────────────────────────────────
  bindUIEvents() {
    // Category pills
    document.querySelectorAll('.cat-pill').forEach(p =>
      p.addEventListener('click', () => this.setCategory(p.dataset.cat)));

    // Run button
    document.getElementById('btn-run').addEventListener('click', () => this.runShader());

    // Export buttons
    document.getElementById('btn-dl-wgsl').addEventListener('click', () => this.downloadWGSL());
    document.getElementById('btn-dl-py').addEventListener('click', () => this.downloadPython());
    document.getElementById('btn-save-app').addEventListener('click', () => this.saveToApp());

    // AI prompt
    document.getElementById('btn-ai-prompt').addEventListener('click', () => this.openAIModal());
    document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
    document.getElementById('modal-copy-btn').addEventListener('click', () => this.copyAIPrompt());
    document.getElementById('modal-backdrop').addEventListener('click', e => {
      if (e.target === document.getElementById('modal-backdrop')) this.closeModal();
    });
    document.getElementById('modal-goal-input').addEventListener('input', () => this.rebuildPromptText());

    // Preview resolution
    document.getElementById('res-select').addEventListener('change', e => {
      const [w, h] = e.target.value.split('x').map(Number);
      this.setPreviewRes(w, h);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') this.closeModal();
    });

    // Init preview size
    this.setPreviewRes(512, 288);
  }

  // ── Export ────────────────────────────────────────────────────────────────
  getFilename() {
    return (document.getElementById('filename-input').value.trim() || 'my_shader') + '.wgsl';
  }

  downloadWGSL() {
    const code = this.editor ? this.editor.getValue() : '';
    const fn   = this.getFilename();
    this._download(fn, code, 'text/plain');
    this.log(`Downloaded ${fn}`, 'success');
  }

  downloadPython() {
    const wgsl = this.editor ? this.editor.getValue() : '';
    const uni  = parseUniforms(wgsl);
    const fn   = this.getFilename();
    const py   = generatePythonStub(this.category, fn, uni);
    this._download(fn.replace('.wgsl', '.py'), py, 'text/x-python');
    this.log(`Downloaded ${fn.replace('.wgsl', '.py')}`, 'success');
  }

  _download(filename, content, mime) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([content], { type: mime }));
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async saveToApp() {
    if (!('showDirectoryPicker' in window)) {
      this.log('File System Access API not available — use Chrome/Edge. Falling back to download.', 'warning');
      this.downloadWGSL(); this.downloadPython();
      return;
    }

    const wgsl = this.editor ? this.editor.getValue() : '';
    const fn   = this.getFilename();
    const noExt = fn.replace('.wgsl', '');

    try {
      // Pick the shaders dir
      let shaderDir = this.fsaDirHandles['shaders'];
      if (!shaderDir || await shaderDir.requestPermission({ mode: 'readwrite' }) !== 'granted') {
        this.log('Pick the src/modules/gpu/shaders/ directory…', 'info');
        shaderDir = await window.showDirectoryPicker({ mode: 'readwrite', startIn: 'documents' });
        this.fsaDirHandles['shaders'] = shaderDir;
      }

      // Write .wgsl
      const wgslHandle = await shaderDir.getFileHandle(fn, { create: true });
      const wgslW = await wgslHandle.createWritable();
      await wgslW.write(wgsl); await wgslW.close();
      this.log(`Saved ${fn} → ${shaderDir.name}/`, 'success');

      // Ask for plugins dir
      const cat  = this.category;
      const subDir = cat === 'source' ? 'generators' : 'effects';
      this.log(`Pick the plugins/${subDir}/ directory to save Python stub…`, 'info');
      let pluginDir = this.fsaDirHandles['plugins'];
      if (!pluginDir || await pluginDir.requestPermission({ mode: 'readwrite' }) !== 'granted') {
        pluginDir = await window.showDirectoryPicker({ mode: 'readwrite', startIn: 'documents' });
        this.fsaDirHandles['plugins'] = pluginDir;
      }
      const uni = parseUniforms(wgsl);
      const py  = generatePythonStub(cat, fn, uni);
      const pyHandle = await pluginDir.getFileHandle(noExt + '.py', { create: true });
      const pyW = await pyHandle.createWritable();
      await pyW.write(py); await pyW.close();
      this.log(`Saved ${noExt}.py → ${pluginDir.name}/`, 'success');

      this.setStatus('Saved to app!', 'accent');
    } catch (e) {
      if (e.name !== 'AbortError') this.log(`Save failed: ${e.message}`, 'error');
    }
  }

  // ── AI Prompt Modal ───────────────────────────────────────────────────────
  openAIModal() {
    document.getElementById('modal-backdrop').classList.add('open');
    this.rebuildPromptText();
  }

  closeModal() {
    document.getElementById('modal-backdrop').classList.remove('open');
  }

  rebuildPromptText() {
    const goal = document.getElementById('modal-goal-input').value;
    const wgsl = this.editor ? this.editor.getValue() : '';
    const fn   = this.getFilename();
    const text = buildAIPrompt(this.category, fn, wgsl, goal);
    document.getElementById('modal-prompt-area').textContent = text;
  }

  async copyAIPrompt() {
    const text = document.getElementById('modal-prompt-area').textContent;
    try {
      await navigator.clipboard.writeText(text);
      const btn = document.getElementById('modal-copy-btn');
      const orig = btn.textContent; btn.textContent = '✔ Copied!';
      setTimeout(() => { btn.textContent = orig; }, 2000);
      this.log('AI prompt copied to clipboard', 'success');
    } catch (e) {
      this.log('Clipboard access denied — select all text in the box and copy manually', 'warning');
    }
  }

  // ── Logging ───────────────────────────────────────────────────────────────
  log(msg, level = 'info') {
    const console_ = document.getElementById('error-console');
    const div = document.createElement('div');
    div.className = `console-msg ${level}`;
    const ts = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    div.innerHTML = `<span class="console-timestamp">${ts}</span>${msg}`;
    console_.appendChild(div);
    console_.scrollTop = console_.scrollHeight;
    // Keep max 80 lines
    while (console_.children.length > 80) console_.removeChild(console_.firstChild);
  }

  setStatus(msg, type = 'idle') {
    const bar = document.getElementById('status-bar');
    bar.className = type;
    document.getElementById('status-msg').textContent = msg;
  }

  setGPUStatus(ok, label) {
    const dot  = document.getElementById('gpu-dot');
    const text = document.getElementById('gpu-label');
    dot.className  = 'gpu-dot ' + (ok ? 'ok' : 'err');
    text.textContent = label;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// ENTRY POINT — called after Monaco loads
// ═══════════════════════════════════════════════════════════════════════════

window.initApp = async function () {
  const app = new ShaderEditorApp();
  window._shaderApp = app;  // expose for debugging
  app.initEditor();
  await app.init();
};
