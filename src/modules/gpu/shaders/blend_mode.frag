#version 330
// Blend Mode effect — blends the input frame against a solid colour using one of
// 14 blend modes.  Matches the CPU BlendModeEffect math exactly.
//
// Modes (uniform int mode):
//   0=normal  1=multiply  2=screen   3=overlay   4=add       5=subtract
//   6=darken  7=lighten   8=color_dodge  9=color_burn  10=hard_light
//   11=soft_light  12=difference  13=exclusion

in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D inputTexture;
uniform vec3  color;        // solid blend colour (0..1 RGB)
uniform float opacity;      // 0..1  (plugin param / 100)
uniform float mix_amount;   // 0..1  (plugin 'mix' param / 100)
uniform int   mode;         // see table above

// ── blend mode helpers ──────────────────────────────────────────────────────

vec3 blend_normal(vec3 b, vec3 c)    { return c; }
vec3 blend_multiply(vec3 b, vec3 c)  { return b * c; }
vec3 blend_screen(vec3 b, vec3 c)    { return 1.0 - (1.0 - b) * (1.0 - c); }
vec3 blend_overlay(vec3 b, vec3 c)   {
    return mix(2.0*b*c, 1.0 - 2.0*(1.0-b)*(1.0-c), step(0.5, b));
}
vec3 blend_add(vec3 b, vec3 c)      { return clamp(b + c, 0.0, 1.0); }
vec3 blend_subtract(vec3 b, vec3 c) { return clamp(b - c, 0.0, 1.0); }
vec3 blend_darken(vec3 b, vec3 c)   { return min(b, c); }
vec3 blend_lighten(vec3 b, vec3 c)  { return max(b, c); }
vec3 blend_color_dodge(vec3 b, vec3 c) {
    return clamp(b / max(1.0 - c, vec3(1e-5)), 0.0, 1.0);
}
vec3 blend_color_burn(vec3 b, vec3 c) {
    return clamp(1.0 - (1.0 - b) / max(c, vec3(1e-5)), 0.0, 1.0);
}
vec3 blend_hard_light(vec3 b, vec3 c) {
    return mix(2.0*b*c, 1.0 - 2.0*(1.0-b)*(1.0-c), step(0.5, c));
}
vec3 blend_soft_light(vec3 b, vec3 c) {
    return clamp((1.0 - 2.0*c)*b*b + 2.0*c*b, 0.0, 1.0);
}
vec3 blend_difference(vec3 b, vec3 c) { return abs(b - c); }
vec3 blend_exclusion(vec3 b, vec3 c)  { return b + c - 2.0*b*c; }

// ── main ────────────────────────────────────────────────────────────────────

void main() {
    vec3 base = texture(inputTexture, v_uv).rgb;
    vec3 result;

    if      (mode ==  0) result = blend_normal(base, color);
    else if (mode ==  1) result = blend_multiply(base, color);
    else if (mode ==  2) result = blend_screen(base, color);
    else if (mode ==  3) result = blend_overlay(base, color);
    else if (mode ==  4) result = blend_add(base, color);
    else if (mode ==  5) result = blend_subtract(base, color);
    else if (mode ==  6) result = blend_darken(base, color);
    else if (mode ==  7) result = blend_lighten(base, color);
    else if (mode ==  8) result = blend_color_dodge(base, color);
    else if (mode ==  9) result = blend_color_burn(base, color);
    else if (mode == 10) result = blend_hard_light(base, color);
    else if (mode == 11) result = blend_soft_light(base, color);
    else if (mode == 12) result = blend_difference(base, color);
    else if (mode == 13) result = blend_exclusion(base, color);
    else                 result = base;

    // opacity: blend between base and blended result (matches CPU line 143)
    result = mix(base, result, opacity);
    // mix_amount: further reduce effect (matches CPU line 144)
    result = mix(base, result, mix_amount);

    fragColor = vec4(result, 1.0);
}
