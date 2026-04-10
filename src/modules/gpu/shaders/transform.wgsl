// transform.wgsl — scale, translate, rotate-Z around an anchor point.
// All parameters in normalised UV space (0..1).  Inverse mapping: for each
// output UV, compute where it reads in the source.
//
// Uniforms (u.data slots):
//   [0,1] anchor     (vec2, default 0.5,0.5 = centre)
//   [2,3] scale      (vec2, 1.0 = no scale, 2.0 = double size)
//   [4,5] translate  (vec2, normalised offset; +x right, +y down)
//   [6]   rotation   (f32,  radians, clockwise)
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
    let anchor    = vec2<f32>(u.data[0].x, u.data[0].y);
    let scale     = vec2<f32>(u.data[0].z, u.data[0].w);
    let translate = vec2<f32>(u.data[1].x, u.data[1].y);
    let rotation  = u.data[1].z;

    // Move to anchor-relative UV space
    var uv = in.uv - anchor;

    // Inverse scale
    let safe_scale = max(scale, vec2<f32>(0.001));
    uv = uv / safe_scale;

    // Inverse rotation (clockwise input → counter-clockwise inverse)
    let c = cos(-rotation);
    let s = sin(-rotation);
    uv = vec2<f32>(c * uv.x - s * uv.y, s * uv.x + c * uv.y);

    // Restore anchor + apply translation.
    // In wgpu UV space y increases downward (same as screen), so we do NOT
    // negate translate.y (unlike the old GLSL shader which negated it because
    // OpenGL UV had y increasing upward).
    uv = uv + anchor - translate;

    // Out-of-bounds → transparent black
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        return vec4<f32>(0.0, 0.0, 0.0, 1.0);
    }

    return textureSample(tex0, samp0, uv);
}
