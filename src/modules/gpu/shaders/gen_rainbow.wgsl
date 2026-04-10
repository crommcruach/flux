// gen_rainbow.wgsl — Scrolling rainbow gradient (horizontal or vertical).
//
// Uniforms layout (u.data[]):
//   [0] time          — seconds
//   [1] canvas_width  — px
//   [2] canvas_height — px
//   [3] speed         — scroll speed (hue cycles/sec)
//   [4] wave_length   — pixels per full hue cycle
//   [5] vertical      — bitcast<i32> bool: 0=horizontal, 1=vertical

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
    let t        = u.data[0].x;
    let cw       = u.data[0].y;
    let ch       = u.data[0].z;
    let speed    = u.data[0].w;
    let wlen     = max(u.data[1].x, 1.0);
    let vertical = bitcast<i32>(u.data[1].y) != 0;

    let pos = select(in.uv.x * cw, in.uv.y * ch, vertical);
    let hue = fract(pos / wlen + t * speed);
    let rgb = hsv_to_rgb(hue, 1.0, 1.0);
    return vec4<f32>(rgb, 1.0);
}
