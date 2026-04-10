// gen_plasma.wgsl — Plasma generator: overlaid sine waves mapped to HSV color.
// All pixel colours are computed analytically from UV + time — no CPU data.
//
// Uniforms layout (u.data[]):
//   [0] time          — seconds (drives animation)
//   [1] canvas_width  — px (unused, UV-based)
//   [2] canvas_height — px (unused, UV-based)
//   [3] speed         — animation speed multiplier
//   [4] scale         — pattern scale (>1 = zoom out)
//   [5] hue_shift     — colour rotation speed (hue units/sec)

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
        case 0:       { rgb = vec3<f32>(c, x, 0.0); }
        case 1:       { rgb = vec3<f32>(x, c, 0.0); }
        case 2:       { rgb = vec3<f32>(0.0, c, x); }
        case 3:       { rgb = vec3<f32>(0.0, x, c); }
        case 4:       { rgb = vec3<f32>(x, 0.0, c); }
        default:      { rgb = vec3<f32>(c, 0.0, x); }
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
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0,  1.0),
        vec2<f32>(2.0,  1.0),
        vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(pos[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let t         = u.data[0].x;
    let speed     = u.data[0].w;
    let scale     = max(u.data[1].x, 0.001);
    let hue_shift = u.data[1].y;

    // Scale UV to canvas units (100 units across at scale=1).
    let cx = in.uv.x * 100.0 / scale;
    let cy = in.uv.y * 100.0 / scale;

    let v1     = sin(cx / 16.0 + t * speed);
    let v2     = sin(cy /  8.0 + t * speed);
    let v3     = sin((cx + cy) / 16.0 + t * speed);
    let v4     = sin(sqrt(cx * cx + cy * cy) / 8.0 + t * speed);
    let plasma = (v1 + v2 + v3 + v4) * 0.25;
    let norm   = (plasma + 1.0) * 0.5;

    let hue = fract(norm + t * hue_shift);
    let rgb = hsv_to_rgb(hue, 1.0, 1.0);
    return vec4<f32>(rgb, 1.0);
}
