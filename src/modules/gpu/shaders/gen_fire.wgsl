// gen_fire.wgsl — Procedural fire using hash-based noise + colour ramp.
//
// Heat at each pixel = layered hash noise attenuated by height (more near
// bottom).  The result is mapped through a fire colour ramp:
//   0.0 → black,  0.4 → dark red,  0.65 → orange,  0.85 → yellow,  1.0 → white.
//
// Uniforms layout (u.data[]):
//   [0] time        — seconds (drives upward flow)
//   [1] cw          — canvas width  (px, unused — UV-based)
//   [2] ch          — canvas height (px, unused — UV-based)
//   [3] intensity   — overall heat multiplier (0–2)
//   [4] turbulence  — number of noise octaves (0–3)
//   [5] speed       — upward scroll speed (0.1–5)
//   [6] detail      — noise frequency scale (5–20)

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;

fn hash21(p: vec2<f32>) -> f32 {
    var q = fract(p * vec2<f32>(0.1031, 0.1030));
    q += dot(q, q.yx + 33.33);
    return fract((q.x + q.y) * q.x);
}

// Value-noise with bilinear interpolation
fn vnoise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let s = f * f * (3.0 - 2.0 * f);
    let a = hash21(i);
    let b = hash21(i + vec2<f32>(1.0, 0.0));
    let c = hash21(i + vec2<f32>(0.0, 1.0));
    let d = hash21(i + vec2<f32>(1.0, 1.0));
    return mix(mix(a, b, s.x), mix(c, d, s.x), s.y);
}

fn fire_ramp(t: f32) -> vec3<f32> {
    let c0 = vec3<f32>(0.0, 0.0, 0.0);
    let c1 = vec3<f32>(0.5, 0.0, 0.0);
    let c2 = vec3<f32>(0.9, 0.4, 0.0);
    let c3 = vec3<f32>(1.0, 0.9, 0.0);
    let c4 = vec3<f32>(1.0, 1.0, 1.0);
    if t < 0.4 {
        return mix(c0, c1, t / 0.4);
    } else if t < 0.65 {
        return mix(c1, c2, (t - 0.4) / 0.25);
    } else if t < 0.85 {
        return mix(c2, c3, (t - 0.65) / 0.20);
    } else {
        return mix(c3, c4, (t - 0.85) / 0.15);
    }
}

struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0)       uv:  vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0), vec2<f32>(2.0, 1.0), vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(pos[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let t          = u.data[0].x;
    let intensity  = u.data[0].w;
    let turbulence = u.data[1].x;
    let speed      = u.data[1].y;
    let detail     = u.data[1].z;

    // uv.y=0 is top, uv.y=1 is bottom (wgpu convention)
    // Fire rises from bottom → invert Y so heat is high at bottom
    let fy = 1.0 - in.uv.y;        // 0=top, 1=bottom

    // Base noise coordinates: scroll upward with time
    let p0    = vec2<f32>(in.uv.x * detail, fy * detail - t * speed);
    var heat  = vnoise(p0);

    // Add turbulence octaves (1–3 extra octaves based on turbulence param)
    let oct = clamp(i32(turbulence), 0, 3);
    var amp  = 0.5;
    var freq = 2.0;
    for (var i = 0; i < oct; i++) {
        heat += vnoise(p0 * freq) * amp;
        amp  *= 0.5;
        freq *= 2.0;
    }
    // Normalise accumulated octaves
    heat /= (1.0 + (1.0 - pow(0.5, f32(oct + 1))));

    // Height attenuation: fire dies off at the top
    heat *= fy * fy * intensity;
    heat  = clamp(heat, 0.0, 1.0);

    let rgb = fire_ramp(heat);
    return vec4<f32>(rgb, 1.0);
}
