#version 330
// Colorize effect: replace hue + saturation from a target color, keep luminance (V).
// brightness scales the V channel (1.0 = full, 0.0 = black).
// alpha blends between original and colorized (1.0 = fully colorized, 0.0 = original).
// invert is applied to the final blended result, independent of colorize alpha.
in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D inputTexture;
uniform float hue;         // target hue, normalized 0..1  (OpenCV_H / 180.0)
uniform float saturation;  // target saturation 0..1       (OpenCV_S / 255.0)
uniform float brightness;  // V scale factor 0..1          (OpenCV_V / 255.0)
uniform float alpha;       // blend 0=original .. 1=colorized
uniform int   invert;      // 0 = normal, 1 = invert V after colorize

vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
    vec4 src = texture(inputTexture, v_uv);
    vec3 hsv = rgb2hsv(src.rgb);
    hsv.x = hue;
    hsv.y = saturation;
    hsv.z = hsv.z * brightness;
    vec3 colorized = hsv2rgb(hsv);
    vec3 result = mix(src.rgb, colorized, alpha);
    if (invert != 0) {
        result = 1.0 - result;
    }
    fragColor = vec4(result, src.a);
}
