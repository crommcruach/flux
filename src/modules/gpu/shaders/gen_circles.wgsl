// gen_circles.wgsl — Uniform grid of circles using SDF.
//
// circle_count is interpreted as circles-per-side of a square grid,
// so circle_count=5 produces a 5×5 grid of 25 circles.
//
// Uniforms layout (u.data[]):
//   [0] time         — unused
//   [1] canvas_width  — px (for pixel-accurate radius and thickness)
//   [2] canvas_height — px
//   [3] circle_count  — bitcast<i32> circles per grid side
//   [4] radius        — px
//   [5] thickness     — bitcast<i32> px; -1 = filled
//   [6] r             — red   (0–255)
//   [7] g             — green (0–255)
//   [8] b             — blue  (0–255)

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
    let cw        = u.data[0].y;
    let ch        = u.data[0].z;
    let count     = f32(bitcast<i32>(u.data[0].w));
    let radius_px = u.data[1].x;
    let thick_px  = f32(bitcast<i32>(u.data[1].y));
    let r         = u.data[1].z / 255.0;
    let g         = u.data[1].w / 255.0;
    let b         = u.data[2].x / 255.0;

    // Pixel coordinates
    let px = in.uv * vec2<f32>(cw, ch);

    // Grid cell index and cell-local position
    let cell_sz  = vec2<f32>(cw / count, ch / count);
    let cell_idx = floor(px / cell_sz);
    let cell_pos = px - cell_idx * cell_sz;           // 0..cell_sz
    let center   = cell_sz * 0.5;
    let dist_px  = length(cell_pos - center);         // distance from circle centre

    var in_circle = false;
    if thick_px < 0.0 {
        // Filled circle
        in_circle = dist_px <= radius_px;
    } else {
        // Outline ring
        in_circle = abs(dist_px - radius_px) <= thick_px * 0.5;
    }

    if in_circle {
        return vec4<f32>(r, g, b, 1.0);
    }
    return vec4<f32>(0.0, 0.0, 0.0, 1.0);
}
