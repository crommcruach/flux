// gen_checkerboard.wgsl — Black-and-white checkerboard grid.
//
// Uniforms layout (u.data[]):
//   [0] time          — unused
//   [1] canvas_width  — unused (UV-based)
//   [2] canvas_height — unused (UV-based)
//   [3] columns       — bitcast<i32> number of columns
//   [4] rows          — bitcast<i32> number of rows

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
    let cols  = f32(bitcast<i32>(u.data[0].w));
    let rows  = f32(bitcast<i32>(u.data[1].x));
    let gx    = floor(in.uv.x * cols);
    let gy    = floor(in.uv.y * rows);
    let check = (gx + gy) % 2.0;
    let v     = select(0.0, 1.0, check < 0.5);
    return vec4<f32>(v, v, v, 1.0);
}
