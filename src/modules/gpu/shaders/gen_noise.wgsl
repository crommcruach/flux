// gen_noise.wgsl — Noise generator: white / smooth / colored variants.
//
// Uniforms layout (u.data[]):
//   [0] time          — seconds (drives animation seed)
//   [1] canvas_width  — px
//   [2] canvas_height — px
//   [3] noise_type    — bitcast<i32>: 0=white, 1=smooth, 2=colored
//   [4] scale         — cell scale for smooth noise (higher = larger blobs)
//   [5] animated      — bitcast<i32> bool: 1 = seed changes each frame

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;

fn hash21(p: vec2<f32>) -> f32 {
    var q = fract(p * vec2<f32>(0.1031, 0.1030));
    q += dot(q, q.yx + 33.33);
    return fract((q.x + q.y) * q.x);
}

fn hsv_to_rgb(h: f32, s: f32, v: f32) -> vec3<f32> {
    let c  = v * s;
    let h6 = h * 6.0;
    let x  = c * (1.0 - abs(fract(h6 * 0.5) * 2.0 - 1.0));
    let m  = v - c;
    var rgb: vec3<f32>;
    let hi = i32(h6) % 6;
    switch hi {
        case 0:  { rgb = vec3<f32>(c, x, 0.0); }
        case 1:  { rgb = vec3<f32>(x, c, 0.0); }
        case 2:  { rgb = vec3<f32>(0.0, c, x); }
        case 3:  { rgb = vec3<f32>(0.0, x, c); }
        case 4:  { rgb = vec3<f32>(x, 0.0, c); }
        default: { rgb = vec3<f32>(c, 0.0, x); }
    }
    return rgb + m;
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
    let t        = u.data[0].x;
    let cw       = u.data[0].y;
    let ch       = u.data[0].z;
    let ntype    = bitcast<i32>(u.data[0].w);
    let scale    = max(u.data[1].x, 0.1);
    let animated = bitcast<i32>(u.data[1].y) != 0;

    // Animated seed: 30 unique seeds/sec
    let seed = select(0.0, floor(t * 30.0), animated);
    let px   = in.uv * vec2<f32>(cw, ch);

    var color: vec3<f32>;
    if ntype == 0 {
        // White noise: independent random per pixel
        let h = hash21(floor(px) + seed);
        color = vec3<f32>(h);
    } else if ntype == 1 {
        // Smooth noise: bilinear interpolation over a coarser grid
        let cell_size = max(1.0, cw / (scale * 10.0));
        let gp  = px / cell_size;
        let i   = floor(gp);
        let f   = fract(gp);
        let s   = f * f * (3.0 - 2.0 * f);        // smoothstep
        let a   = hash21(i + vec2<f32>(seed,       0.0));
        let b   = hash21(i + vec2<f32>(1.0 + seed, 0.0));
        let c2  = hash21(i + vec2<f32>(seed,       1.0));
        let d   = hash21(i + vec2<f32>(1.0 + seed, 1.0));
        let h   = mix(mix(a, b, s.x), mix(c2, d, s.x), s.y);
        color   = vec3<f32>(h);
    } else {
        // Colored noise: hash → hue
        let h      = hash21(floor(px) + seed);
        let hue    = fract(h + t * select(0.0, 0.1, animated));
        color      = hsv_to_rgb(hue, 1.0, h);
    }

    return vec4<f32>(color, 1.0);
}
