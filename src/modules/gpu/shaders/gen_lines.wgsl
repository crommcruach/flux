// gen_lines.wgsl — Evenly-spaced horizontal coloured lines on black.
//
// Uniforms layout (u.data[]):
//   [0] time          — unused
//   [1] canvas_width  — unused
//   [2] canvas_height — px (used for line_width pixel conversion)
//   [3] line_count    — bitcast<i32>
//   [4] line_width    — bitcast<i32> pixels
//   [5] r             — red   (0–255)
//   [6] g             — green (0–255)
//   [7] b             — blue  (0–255)

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;

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
    let ch      = u.data[0].z;
    let lc      = f32(bitcast<i32>(u.data[0].w));
    let lw      = f32(bitcast<i32>(u.data[1].x));
    let r       = u.data[1].y / 255.0;
    let g       = u.data[1].z / 255.0;
    let b       = u.data[1].w / 255.0;

    // Pixel distance from top of current row
    let row_px = fract(in.uv.y * lc) * (ch / lc);
    let in_line = step(row_px, lw - 1.0);
    return vec4<f32>(r * in_line, g * in_line, b * in_line, 1.0);
}
