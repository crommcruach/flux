// scale_mode.wgsl — scale input texture into canvas with configurable fit/fill/off modes.
//
// Uniforms (packed as flat f32 array):
//   u.data[0] = vec4(src_x0, src_y0, src_x1, src_y1)  — source UV sub-rect to sample
//   u.data[1] = vec4(dst_x0, dst_y0, dst_x1, dst_y1)  — destination UV rect on canvas
//
// Pixels outside the destination rect are output as black (letterbox / pillarbox bars).
// The source rect defines which portion of the input is sampled (for 'fill' / 'off' crop).
//
// Modes implemented by computing the rects in Python (see compositor.py):
//   stretch — src=(0,0,1,1), dst=(0,0,1,1)        — full stretch, same as passthrough
//   fit     — src=(0,0,1,1), dst computed          — letterbox / pillarbox, preserve aspect
//   fill    — src sub-rect, dst=(0,0,1,1)          — crop to fill, preserve aspect
//   off     — both rects computed for 1:1 pixels, centered, excess cropped

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var tex0: texture_2d<f32>;
@group(0) @binding(2) var samp0: sampler;

struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    // Full-screen triangle (covers viewport exactly once)
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
    // UV: (0,0)=top-left, (1,1)=bottom-right
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0),
        vec2<f32>(2.0, 1.0),
        vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(pos[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let src = u.data[0];  // (src_x0, src_y0, src_x1, src_y1)
    let dst = u.data[1];  // (dst_x0, dst_y0, dst_x1, dst_y1)
    let uv = in.uv;

    // Outside destination rect → black (letterbox / pillarbox bars)
    if (uv.x < dst.x || uv.x > dst.z || uv.y < dst.y || uv.y > dst.w) {
        return vec4<f32>(0.0, 0.0, 0.0, 1.0);
    }

    // Map output UV within dst rect → source UV within src rect
    let t = vec2<f32>(
        (uv.x - dst.x) / (dst.z - dst.x),
        (uv.y - dst.y) / (dst.w - dst.y),
    );
    let src_uv = src.xy + t * (src.zw - src.xy);
    return textureSample(tex0, samp0, src_uv);
}
