// slice.wgsl — GPU render pass: viewport crop, rotation, soft-edge, colour, mirror,
//              optional perspective warp, and optional numpy mask texture.
//
// Uniform layout (struct fields, byte offsets match Python flat f32 packing):
//   0-15  rect        vec4<f32>  src_x, src_y, src_w, src_h  (canvas UV fractions 0..1)
//   16    rotation    f32        radians, positive = CCW
//   20    soft_edge   f32        fraction of min(out_w, out_h) for edge fade (0 = off)
//   24    mirror      i32        0=none  1=horizontal  2=vertical  3=both
//   28    brightness  f32        -1..1  (added to linear colour, after contrast)
//   32    contrast    f32        factor  (1.0=unchanged; applied first, centered on 0.5)
//   36    r_shift     f32        -1..1  per-channel additive offset (after brightness)
//   40    g_shift     f32        -1..1
//   44    b_shift     f32        -1..1
//   48    use_persp   f32        1.0 = apply perspective warp; 0.0 = plain rect crop
//   52-60 _pad0-2     f32×3      explicit padding so h_row* align at 16-byte boundary
//   64-79 h_row0      vec4<f32>  row 0 of 3×3 homography (maps output UV → canvas UV)
//   80-95 h_row1      vec4<f32>  row 1
//   96-111 h_row2     vec4<f32>  row 2
//   112-127 soft_edges vec4<f32> per-edge fade fractions: x=top y=right z=bottom w=left (0=off)
//   128    soft_curve  f32       curve type: 0=linear  1=smooth(smoothstep)  2=exponential
//   132    use_mask    f32       1.0 = sample mask_tex (binding 3/4); 0.0 = no mask
//
// soft_edges takes priority over soft_edge when any component > 0.

struct Uniforms {
    rect:       vec4<f32>,  // src_x, src_y, src_w, src_h
    rotation:   f32,
    soft_edge:  f32,
    mirror:     i32,
    brightness: f32,
    contrast:   f32,
    r_shift:    f32,
    g_shift:    f32,
    b_shift:    f32,
    use_persp:  f32,        // offset 48
    _pad0:      f32,        // offset 52  — alignment padding
    _pad1:      f32,        // offset 56
    _pad2:      f32,        // offset 60
    h_row0:     vec4<f32>,  // offset 64  — homography row 0
    h_row1:     vec4<f32>,  // offset 80  — homography row 1
    h_row2:     vec4<f32>,  // offset 96  — homography row 2
    // Per-edge soft fade (fractions of output size).  Takes priority over soft_edge.
    // x=top  y=right  z=bottom  w=left.  0.0 = edge disabled.
    soft_edges: vec4<f32>,  // offset 112
    soft_curve: f32,        // offset 128  — 0=linear  1=smooth  2=exponential
    use_mask:   f32,        // offset 132  — 1.0 = sample mask_tex (binding 3/4)
}

@group(0) @binding(0) var<uniform> u:          Uniforms;
@group(0) @binding(1) var          canvas_tex: texture_2d<f32>;
@group(0) @binding(2) var          samp:       sampler;
@group(0) @binding(3) var          mask_tex:   texture_2d<f32>;
@group(0) @binding(4) var          mask_samp:  sampler;

struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0)       uv:  vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    // Full-screen triangle in NDC; UV (0,0) = top-left, (1,1) = bottom-right.
    var positions = array<vec2<f32>, 3>(
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
    out.pos = vec4<f32>(positions[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    var uv = in.uv;  // 0..1 in output texture space, (0,0) = top-left

    // ── Soft-edge: per-edge or symmetric fade to black ──────────────────────
    // Evaluated before mirror/rotation so that uv is still in pristine 0..1 output space.
    var edge_alpha = 1.0;
    let se = u.soft_edges;
    let se_any = max(max(se.x, se.y), max(se.z, se.w));
    if (se_any > 0.0) {
        // Per-edge mode: each component is a fraction of the output dimension.
        // Build a ramp t ∈ [0,1] for each active edge then take the minimum.
        var t = 1.0;
        if (se.x > 0.0) { t = min(t, clamp(uv.y         / se.x, 0.0, 1.0)); }  // top
        if (se.z > 0.0) { t = min(t, clamp((1.0 - uv.y) / se.z, 0.0, 1.0)); }  // bottom
        if (se.w > 0.0) { t = min(t, clamp(uv.x         / se.w, 0.0, 1.0)); }  // left
        if (se.y > 0.0) { t = min(t, clamp((1.0 - uv.x) / se.y, 0.0, 1.0)); }  // right
        // Apply curve
        let curve = i32(u.soft_curve);
        if (curve == 1) { t = t * t * (3.0 - 2.0 * t); }  // smooth (smoothstep)
        else if (curve == 2) { t = t * t; }                // exponential
        edge_alpha = t;
    } else if (u.soft_edge > 0.0) {
        // Legacy symmetric mode (int pixel radius passed as fraction).
        let d = min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y));
        edge_alpha = clamp(d / u.soft_edge, 0.0, 1.0);
    }

    // ── Mirror: flip UV before rotation ──────────────────────────────────
    let mirror = u.mirror;
    if (mirror == 1 || mirror == 3) { uv.x = 1.0 - uv.x; }
    if (mirror == 2 || mirror == 3) { uv.y = 1.0 - uv.y; }

    // ── Rotation around output UV centre (0.5, 0.5) ──────────────────────
    let rot = u.rotation;
    if (rot != 0.0) {
        let c   = cos(rot);
        let s   = sin(rot);
        let off = uv - vec2<f32>(0.5);
        uv = vec2<f32>(off.x * c - off.y * s, off.x * s + off.y * c)
           + vec2<f32>(0.5);
    }

    // ── Map output UV → canvas UV (perspective or plain rect) ───────────────
    var canvas_uv: vec2<f32>;
    if (u.use_persp > 0.5) {
        // Perspective warp: inverse homography maps output UV → canvas UV.
        // H is stored row-major; xyz components only (w is padding).
        let p  = vec3<f32>(uv.x, uv.y, 1.0);
        let q  = vec3<f32>(
            dot(u.h_row0.xyz, p),
            dot(u.h_row1.xyz, p),
            dot(u.h_row2.xyz, p),
        );
        canvas_uv = q.xy / q.z;
    } else {
        canvas_uv = vec2<f32>(
            u.rect.x + uv.x * u.rect.z,
            u.rect.y + uv.y * u.rect.w,
        );
    }

    // ── Sample canvas (clamp-to-edge sampler) ─────────────────────────────
    var colour = textureSample(canvas_tex, samp, canvas_uv).rgb;

    // ── Colour adjustments ────────────────────────────────────────────────
    let contrast   = u.contrast;
    let brightness = u.brightness;
    let r_shift    = u.r_shift;
    let g_shift    = u.g_shift;
    let b_shift    = u.b_shift;

    // Contrast centered on 0.5
    colour = (colour - vec3<f32>(0.5)) * contrast + vec3<f32>(0.5);
    // Brightness (additive)
    colour = colour + vec3<f32>(brightness);
    // Per-channel offset
    colour = colour + vec3<f32>(r_shift, g_shift, b_shift);
    colour = clamp(colour, vec3<f32>(0.0), vec3<f32>(1.0));

    // ── Apply soft-edge alpha (multiply into RGB, alpha always 1) ─────────
    // ── Apply mask texture (if present) ──────────────────────────────────
    // mask_tex is a grayscale mask: 1.0 = keep, 0.0 = remove.
    // We sample it in output UV space (same coords as the uv after mirror/rotation
    // but BEFORE the canvas UV mapping, i.e. plain 0..1 in output space).
    // use_mask is checked first so that when no mask is present the sampler
    // binding is still declared but the read result is simply discarded.
    var mask_alpha = 1.0;
    if (u.use_mask > 0.5) {
        mask_alpha = textureSample(mask_tex, mask_samp, in.uv).r;
    }

    return vec4<f32>(colour * edge_alpha * mask_alpha, 1.0);
}
