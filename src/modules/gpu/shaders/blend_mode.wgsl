// blend_mode.wgsl — blend input frame against a solid colour using 14 modes.
//
// Uniforms (u.data slots):
//   [0,1,2] color      (vec3 RGB 0..1)
//   [3]     opacity    (f32 0..1)
//   [4]     mix_amount (f32 0..1)
//   [5]     mode       (i32 as bitcast f32)
//     0=normal  1=multiply  2=screen   3=overlay   4=add       5=subtract
//     6=darken  7=lighten   8=color_dodge  9=color_burn  10=hard_light
//     11=soft_light  12=difference  13=exclusion
//
// Textures: binding 1 = inputTexture

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

fn bm_normal(b: vec3<f32>, c: vec3<f32>)    -> vec3<f32> { return c; }
fn bm_multiply(b: vec3<f32>, c: vec3<f32>)  -> vec3<f32> { return b * c; }
fn bm_screen(b: vec3<f32>, c: vec3<f32>)    -> vec3<f32> { return 1.0 - (1.0 - b) * (1.0 - c); }
fn bm_overlay(b: vec3<f32>, c: vec3<f32>)   -> vec3<f32> {
    return mix(2.0*b*c, 1.0 - 2.0*(1.0-b)*(1.0-c), step(vec3<f32>(0.5), b));
}
fn bm_add(b: vec3<f32>, c: vec3<f32>)       -> vec3<f32> { return clamp(b + c, vec3<f32>(0.0), vec3<f32>(1.0)); }
fn bm_subtract(b: vec3<f32>, c: vec3<f32>)  -> vec3<f32> { return clamp(b - c, vec3<f32>(0.0), vec3<f32>(1.0)); }
fn bm_darken(b: vec3<f32>, c: vec3<f32>)    -> vec3<f32> { return min(b, c); }
fn bm_lighten(b: vec3<f32>, c: vec3<f32>)   -> vec3<f32> { return max(b, c); }
fn bm_color_dodge(b: vec3<f32>, c: vec3<f32>) -> vec3<f32> {
    return clamp(b / max(1.0 - c, vec3<f32>(1e-5)), vec3<f32>(0.0), vec3<f32>(1.0));
}
fn bm_color_burn(b: vec3<f32>, c: vec3<f32>) -> vec3<f32> {
    return clamp(1.0 - (1.0 - b) / max(c, vec3<f32>(1e-5)), vec3<f32>(0.0), vec3<f32>(1.0));
}
fn bm_hard_light(b: vec3<f32>, c: vec3<f32>) -> vec3<f32> {
    return mix(2.0*b*c, 1.0 - 2.0*(1.0-b)*(1.0-c), step(vec3<f32>(0.5), c));
}
fn bm_soft_light(b: vec3<f32>, c: vec3<f32>) -> vec3<f32> {
    return clamp((1.0 - 2.0*c)*b*b + 2.0*c*b, vec3<f32>(0.0), vec3<f32>(1.0));
}
fn bm_difference(b: vec3<f32>, c: vec3<f32>) -> vec3<f32> { return abs(b - c); }
fn bm_exclusion(b: vec3<f32>, c: vec3<f32>)  -> vec3<f32> { return b + c - 2.0*b*c; }

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let color      = vec3<f32>(u.data[0].x, u.data[0].y, u.data[0].z);
    let opacity    = u.data[0].w;
    let mix_amount = u.data[1].x;
    let mode       = bitcast<i32>(u.data[1].y);

    let base = textureSample(tex0, samp0, in.uv).rgb;

    var result: vec3<f32>;
    if      (mode ==  0) { result = bm_normal(base, color); }
    else if (mode ==  1) { result = bm_multiply(base, color); }
    else if (mode ==  2) { result = bm_screen(base, color); }
    else if (mode ==  3) { result = bm_overlay(base, color); }
    else if (mode ==  4) { result = bm_add(base, color); }
    else if (mode ==  5) { result = bm_subtract(base, color); }
    else if (mode ==  6) { result = bm_darken(base, color); }
    else if (mode ==  7) { result = bm_lighten(base, color); }
    else if (mode ==  8) { result = bm_color_dodge(base, color); }
    else if (mode ==  9) { result = bm_color_burn(base, color); }
    else if (mode == 10) { result = bm_hard_light(base, color); }
    else if (mode == 11) { result = bm_soft_light(base, color); }
    else if (mode == 12) { result = bm_difference(base, color); }
    else if (mode == 13) { result = bm_exclusion(base, color); }
    else                 { result = base; }

    result = mix(base, result, opacity);
    result = mix(base, result, mix_amount);
    return vec4<f32>(result, 1.0);
}
