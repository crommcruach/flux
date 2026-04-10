// colorize.wgsl — replace hue + saturation from a target colour, keep luminance.
//
// Uniforms (u.data slots):
//   [0] hue         (f32, 0..1,  OpenCV_H / 180.0)
//   [1] saturation  (f32, 0..1,  OpenCV_S / 255.0)
//   [2] brightness  (f32, 0..1,  V scale factor)
//   [3] alpha       (f32, 0..1,  0=original 1=fully colorized)
//   [4] invert      (i32 as bitcast f32,  0=normal 1=invert V)
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

fn rgb2hsv(c: vec3<f32>) -> vec3<f32> {
    let K = vec4<f32>(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    let p = mix(vec4<f32>(c.bg, K.wz), vec4<f32>(c.gb, K.xy), step(c.b, c.g));
    let q = mix(vec4<f32>(p.xyw, c.r), vec4<f32>(c.r, p.yzx), step(p.x, c.r));
    let d = q.x - min(q.w, q.y);
    let e = 1.0e-10;
    return vec3<f32>(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

fn hsv2rgb(c: vec3<f32>) -> vec3<f32> {
    let K = vec4<f32>(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    let p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, vec3<f32>(0.0), vec3<f32>(1.0)), c.y);
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let hue        = u.data[0].x;
    let saturation = u.data[0].y;
    let brightness = u.data[0].z;
    let alpha      = u.data[0].w;
    let invert     = bitcast<i32>(u.data[1].x);

    let src = textureSample(tex0, samp0, in.uv);
    var hsv = rgb2hsv(src.rgb);
    hsv.x = hue;
    hsv.y = saturation;
    hsv.z = hsv.z * brightness;
    let colorized = hsv2rgb(hsv);
    var result    = mix(src.rgb, colorized, alpha);
    if (invert != 0) {
        result = 1.0 - result;
    }
    return vec4<f32>(result, src.a);
}
