// fade_transition.wgsl — crossfade between two frames.
// progress 0.0 = 100% tex_a (outgoing), 1.0 = 100% tex_b (incoming).
// progress is pre-eased in Python before passing as uniform.
//
// Uniforms (u.data slots):
//   [0] progress  (f32, 0..1)
//
// Textures: binding 1 = tex_a (outgoing), binding 3 = tex_b (incoming)

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var tex_a: texture_2d<f32>;
@group(0) @binding(2) var samp_a: sampler;
@group(0) @binding(3) var tex_b: texture_2d<f32>;
@group(0) @binding(4) var samp_b: sampler;

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
    let progress = u.data[0].x;
    let ca = textureSample(tex_a, samp_a, in.uv);
    let cb = textureSample(tex_b, samp_b, in.uv);
    return mix(ca, cb, progress);
}
