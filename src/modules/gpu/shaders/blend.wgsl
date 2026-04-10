// blend.wgsl — multi-mode layer compositing (Photoshop-compatible).
//
// Blends 'overlay' onto 'base' with configurable blend mode and opacity.
//
// Uniforms (u.data slots):
//   [0] opacity  (f32, 0..1)
//   [1] mode     (i32 stored as bitcast f32)
//     0=normal 1=add 2=subtract 3=multiply 4=screen 5=overlay 6=mask
//
// Textures: binding 1 = base, binding 3 = overlay

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var tex_base: texture_2d<f32>;
@group(0) @binding(2) var samp_base: sampler;
@group(0) @binding(3) var tex_overlay: texture_2d<f32>;
@group(0) @binding(4) var samp_overlay: sampler;

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

fn blend_normal(b: vec3<f32>, o: vec3<f32>)   -> vec3<f32> { return o; }
fn blend_add(b: vec3<f32>, o: vec3<f32>)      -> vec3<f32> { return clamp(b + o, vec3<f32>(0.0), vec3<f32>(1.0)); }
fn blend_subtract(b: vec3<f32>, o: vec3<f32>) -> vec3<f32> { return clamp(b - o, vec3<f32>(0.0), vec3<f32>(1.0)); }
fn blend_multiply(b: vec3<f32>, o: vec3<f32>) -> vec3<f32> { return b * o; }
fn blend_screen(b: vec3<f32>, o: vec3<f32>)   -> vec3<f32> { return 1.0 - (1.0 - b) * (1.0 - o); }

fn blend_overlay(b: vec3<f32>, o: vec3<f32>) -> vec3<f32> {
    let dark  = 2.0 * b * o;
    let light = 1.0 - 2.0 * (1.0 - b) * (1.0 - o);
    return mix(dark, light, step(vec3<f32>(0.5), b));
}

fn blend_mask(b: vec3<f32>, o: vec3<f32>) -> vec3<f32> {
    let luma = dot(o, vec3<f32>(0.2126, 0.7152, 0.0722));
    return b * luma;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let opacity = u.data[0].x;
    let mode    = bitcast<i32>(u.data[0].y);

    let base_px    = textureSample(tex_base,    samp_base,    in.uv);
    let overlay_px = textureSample(tex_overlay, samp_overlay, in.uv);

    let b = base_px.rgb;
    let o = overlay_px.rgb;

    var blended: vec3<f32>;
    if      (mode == 0) { blended = blend_normal(b, o); }
    else if (mode == 1) { blended = blend_add(b, o); }
    else if (mode == 2) { blended = blend_subtract(b, o); }
    else if (mode == 3) { blended = blend_multiply(b, o); }
    else if (mode == 4) { blended = blend_screen(b, o); }
    else if (mode == 5) { blended = blend_overlay(b, o); }
    else if (mode == 6) { blended = blend_mask(b, o); }
    else                { blended = blend_normal(b, o); }

    // effective alpha: layer opacity × overlay alpha
    let alpha = opacity * overlay_px.a;
    return vec4<f32>(mix(b, blended, alpha), base_px.a);
}
