// gen_triangles.wgsl — Alternating up/down triangle grid.
//
// Each grid cell is split along its diagonal: pixels above the diagonal
// (upper-left triangle) receive one colour; pixels below get black.
// Odd+even cells flip the diagonal direction so adjacent cells alternate.
//
// Uniforms layout (u.data[]):
//   [0] time          — unused
//   [1] canvas_width  — unused (UV-based)
//   [2] canvas_height — unused (UV-based)
//   [3] columns       — bitcast<i32>
//   [4] rows          — bitcast<i32>
//   [5] r             — red   (0–255) of the filled triangle
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
    let cols = f32(bitcast<i32>(u.data[0].w));
    let rows = f32(bitcast<i32>(u.data[1].x));
    let r    = u.data[1].y / 255.0;
    let g    = u.data[1].z / 255.0;
    let b    = u.data[1].w / 255.0;

    // Cell index and local UV within cell (0..1)
    let ci  = floor(in.uv.x * cols);
    let ri  = floor(in.uv.y * rows);
    let lx  = fract(in.uv.x * cols);   // 0..1 within cell (x)
    let ly  = fract(in.uv.y * rows);   // 0..1 within cell (y)

    // Even cells: upper-left triangle when lx + ly < 1
    // Odd cells:  upper-left triangle when lx > ly  (flipped diagonal)
    let even   = ((i32(ci) + i32(ri)) % 2) == 0;
    let filled = select(lx > ly, lx + ly < 1.0, even);

    if filled {
        return vec4<f32>(r, g, b, 1.0);
    }
    return vec4<f32>(0.0, 0.0, 0.0, 1.0);
}
