// gen_pulse.wgsl — Full-frame pulsing solid colour with hue rotation.
//
// Uniforms layout (u.data[]):
//   [0] time           — seconds
//   [1] canvas_width   — unused
//   [2] canvas_height  — unused
//   [3] frequency      — pulse frequency (Hz)
//   [4] min_brightness — brightness lower bound (0–1)
//   [5] max_brightness — brightness upper bound (0–1)
//   [6] hue_rotation   — hue change speed (hue-units/sec)
//   [7] saturation     — HSV saturation (0–1)

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;

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
    let t          = u.data[0].x;
    let freq       = u.data[0].w;
    let min_b      = u.data[1].x;
    let max_b      = u.data[1].y;
    let hue_rot    = u.data[1].z;
    let sat        = u.data[1].w;

    // Sine-based brightness oscillation
    let brightness = mix(min_b, max_b, (sin(t * freq * 6.28318) + 1.0) * 0.5);
    let hue        = fract(t * hue_rot);
    let rgb        = hsv_to_rgb(hue, sat, brightness);
    return vec4<f32>(rgb, 1.0);
}
