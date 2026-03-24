#version 330
// Brightness / Contrast effect.
// Formula (matching CPU plugin): output = clamp(contrast * input + brightness, 0, 1)
// brightness uniform is pre-normalized to 0..1 range: pass brightness_value / 255.0
in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D inputTexture;
uniform float brightness;  // normalized: range -100..+100 → pass value/100.0  (-1.0 = black, +1.0 = white)
uniform float contrast;    // multiplier: 0..3, default 1.0

void main() {
    vec4 src = texture(inputTexture, v_uv);
    vec3 result = clamp(src.rgb * contrast + brightness, 0.0, 1.0);
    fragColor = vec4(result, src.a);
}
