// comp_blit.wgsl — viewport-aware blit for GPU composition.
//
// Blits a source (slice) texture into a viewport-constrained region of the
// composition output frame.  The render pass caller sets set_viewport() to
// the target rectangle so rasterisation is confined to that region.
//
// UV mapping: @builtin(position) gives framebuffer pixel-centre coordinates.
// Subtracting the viewport origin and dividing by its size maps exactly to
// [0, 1] UV space of the source texture — pixel centres align with texel
// centres, so no half-pixel correction is needed.
//
// Uniforms:
//   viewport  vec4<f32>  x, y, width, height  (pixel coords of target rectangle)

struct Uniforms {
    viewport: vec4<f32>,  // x, y, w, h
}

@group(0) @binding(0) var<uniform> u:    Uniforms;
@group(0) @binding(1) var          tex:  texture_2d<f32>;
@group(0) @binding(2) var          samp: sampler;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertexOutput {
    // Oversized full-screen triangle; set_viewport() on the render pass clips
    // rasterisation to the desired target rectangle.
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
    var out: VertexOutput;
    out.position = vec4<f32>(pos[vi], 0.0, 1.0);
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let vp_x = u.viewport.x;
    let vp_y = u.viewport.y;
    let vp_w = u.viewport.z;
    let vp_h = u.viewport.w;
    // Map framebuffer pixel coords → [0, 1] UV within the source slice.
    let uv = (in.position.xy - vec2<f32>(vp_x, vp_y)) / vec2<f32>(vp_w, vp_h);
    return textureSample(tex, samp, clamp(uv, vec2<f32>(0.0), vec2<f32>(1.0)));
}
