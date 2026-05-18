// auto_mask.wgsl — key out (near-)black pixels by setting alpha to 0.
//
// Computes perceptual luminance of each pixel. If luminance <= threshold
// the pixel becomes fully transparent (alpha = 0). Otherwise alpha is kept.
// With invert = 1 the logic flips: bright pixels become transparent.
//
// Uniforms (u.data slots):
//   [0].x  threshold  (f32, 0.0..1.0)   — luminance cutoff
//   [0].y  invert     (f32, 0.0 or 1.0) — 1 = invert mask
//
// Textures: binding 1 = inputTexture (rgba32f, premultiplied linear)

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
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
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
    let threshold = u.data[0].x;
    let invert    = u.data[0].y;

    let src = textureSample(tex0, samp0, in.uv);

    // Rec.709 perceptual luminance
    let luma = dot(src.rgb, vec3<f32>(0.2126, 0.7152, 0.0722));

    // is_dark: 1.0 when pixel is below threshold (should be masked)
    var is_dark = select(0.0, 1.0, luma <= threshold);

    // invert flips which side gets masked
    var masked = select(is_dark, 1.0 - is_dark, invert > 0.5);

    // masked == 1.0  →  alpha 0 (transparent)
    let out_alpha = src.a * (1.0 - masked);
    return vec4<f32>(src.rgb, out_alpha);
}
