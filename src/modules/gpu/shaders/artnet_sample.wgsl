// artnet_sample.wgsl — GPU compute: sample N LED UV positions from a texture.
//
// Bindings:
//   0: input texture (texture_2d<f32>)
//   1: UV positions  (storage read:  array<vec2<f32>>)
//   2: RGB output    (storage read_write: array<u32> packed as R | G<<8 | B<<16)

@group(0) @binding(0) var input_tex: texture_2d<f32>;
@group(0) @binding(1) var<storage, read> uv_positions: array<vec2<f32>>;
@group(0) @binding(2) var<storage, read_write> output_rgb: array<u32>;

@compute @workgroup_size(256)
fn cs_main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let i = gid.x;
    let n = arrayLength(&output_rgb);
    if (i >= n) { return; }

    let uv   = uv_positions[i];
    let dims = textureDimensions(input_tex);
    let x = i32(clamp(uv.x * f32(dims.x), 0.0, f32(dims.x) - 1.0));
    let y = i32(clamp(uv.y * f32(dims.y), 0.0, f32(dims.y) - 1.0));

    let pixel = textureLoad(input_tex, vec2<i32>(x, y), 0);
    let r = u32(clamp(pixel.r * 255.0, 0.0, 255.0));
    let g = u32(clamp(pixel.g * 255.0, 0.0, 255.0));
    let b = u32(clamp(pixel.b * 255.0, 0.0, 255.0));
    output_rgb[i] = r | (g << 8u) | (b << 16u);
}
