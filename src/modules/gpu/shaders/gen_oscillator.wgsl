// gen_oscillator.wgsl — Multiple waveform lines (sine/square/sawtooth/triangle).
//
// Uniforms layout (u.data[]):
//   [0] time       — seconds
//   [1] cw         — canvas width  (px)
//   [2] ch         — canvas height (px)
//   [3] waveform   — bitcast<i32>: 0=sine, 1=square, 2=sawtooth, 3=triangle
//   [4] frequency  — wave frequency
//   [5] amplitude  — vertical amplitude (0–1 fraction of canvas height)
//   [6] line_count — bitcast<i32> (1–10)
//   [7] line_width — bitcast<i32> pixels
//   [8] animated   — bitcast<i32> bool

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;

fn wave_val(wtype: i32, phase: f32) -> f32 {
    let p = phase;
    switch wtype {
        case 0:  { return sin(p * 6.28318) * 0.5 + 0.5; }
        case 1:  { return select(0.0, 1.0, sin(p * 6.28318) >= 0.0); }
        case 2:  { return fract(p); }
        default: {
            // Triangle
            let t2 = fract(p);
            return select(t2 * 2.0, (1.0 - t2) * 2.0, t2 < 0.5);
        }
    }
    return 0.0;
}

fn hue_to_rgb(hue: f32) -> vec3<f32> {
    let h6 = hue * 6.0;
    let c  = 1.0;
    let x  = 1.0 - abs(fract(h6 * 0.5) * 2.0 - 1.0);
    let hi = i32(h6) % 6;
    switch hi {
        case 0:  { return vec3<f32>(1.0, x,   0.0); }
        case 1:  { return vec3<f32>(x,   1.0, 0.0); }
        case 2:  { return vec3<f32>(0.0, 1.0, x  ); }
        case 3:  { return vec3<f32>(0.0, x,   1.0); }
        case 4:  { return vec3<f32>(x,   0.0, 1.0); }
        default: { return vec3<f32>(1.0, 0.0, x  ); }
    }
    return vec3<f32>(1.0);
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
    let ch       = u.data[0].z;
    let wtype    = bitcast<i32>(u.data[0].w);
    let freq     = u.data[1].x;
    let amp      = u.data[1].y;
    let lc       = bitcast<i32>(u.data[1].z);
    let lw_px    = f32(bitcast<i32>(u.data[1].w));
    let animated = bitcast<i32>(u.data[2].x) != 0;

    let time_phase = select(0.0, t, animated);
    let x_phase    = in.uv.x * freq + time_phase;
    let y_px       = in.uv.y * ch;

    for (var i = 0; i < lc; i++) {
        let offset      = f32(i) / f32(max(lc, 1));
        let wave_y_norm = 0.5 + (wave_val(wtype, x_phase + offset) - 0.5) * amp;
        let wave_y_px   = wave_y_norm * ch;
        if abs(y_px - wave_y_px) < lw_px * 0.5 {
            return vec4<f32>(hue_to_rgb(offset), 1.0);
        }
    }
    return vec4<f32>(0.0, 0.0, 0.0, 1.0);
}
