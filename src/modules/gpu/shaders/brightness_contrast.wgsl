// brightness_contrast.wgsl — adjust brightness and contrast.
// Formula: output = clamp(contrast * input + brightness, 0, 1)
//
// Uniforms (u.data slots):
//   [0] brightness  (f32,  -1.0..+1.0; pass value/100.0)
//   [1] contrast    (f32,  multiplier  0..3, default 1.0)
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

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let brightness = u.data[0].x;
    let contrast   = u.data[0].y;

    let src    = textureSample(tex0, samp0, in.uv);
    let result = clamp(src.rgb * contrast + brightness, vec3<f32>(0.0), vec3<f32>(1.0));
    return vec4<f32>(result, src.a);
}
