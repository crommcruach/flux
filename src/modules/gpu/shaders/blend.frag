/*
 * blend.frag — Multi-mode layer blend shader
 *
 * Blends `overlay` onto `base` using Photoshop-compatible blend modes.
 * All operations are in linear [0, 1] space (GL textures read as float).
 *
 * Uniforms:
 *   opacity  — 0.0 … 1.0  (layer opacity from UI, already divided by 100)
 *   mode     — int matching BLEND_MODES table in composite.py:
 *                0 = normal
 *                1 = add
 *                2 = subtract
 *                3 = multiply
 *                4 = screen
 *                5 = overlay
 *                6 = mask
 *
 * Alpha support:
 *   When overlay has alpha (BGRA source), the effective opacity is
 *   opacity * overlay.a — so fully transparent pixels contribute nothing.
 *   For RGB sources OpenGL fills alpha = 1.0 automatically, so the formula
 *   degrades to plain `opacity` — no shader branching needed.
 */
#version 330

in vec2 v_uv;

uniform sampler2D base;
uniform sampler2D overlay;
uniform float opacity;   // 0.0 … 1.0
uniform int   mode;      // blend mode index

out vec4 fragColor;

// ── blend mode helpers ──────────────────────────────────────────────────────

vec3 blend_normal(vec3 b, vec3 o)    { return o; }
vec3 blend_add(vec3 b, vec3 o)       { return clamp(b + o, 0.0, 1.0); }
vec3 blend_subtract(vec3 b, vec3 o)  { return clamp(b - o, 0.0, 1.0); }
vec3 blend_multiply(vec3 b, vec3 o)  { return b * o; }
vec3 blend_screen(vec3 b, vec3 o)    { return 1.0 - (1.0 - b) * (1.0 - o); }

vec3 blend_overlay(vec3 b, vec3 o) {
    // component-wise: if base < 0.5 → multiply, else → screen
    vec3 dark  = 2.0 * b * o;
    vec3 light = 1.0 - 2.0 * (1.0 - b) * (1.0 - o);
    return mix(dark, light, step(0.5, b));
}

vec3 blend_mask(vec3 b, vec3 o) {
    // Overlay luminance used as mask weight on base
    float luma = dot(o, vec3(0.2126, 0.7152, 0.0722));
    return b * luma;
}

// ── main ────────────────────────────────────────────────────────────────────

void main() {
    vec4 base_px    = texture(base,    v_uv);
    vec4 overlay_px = texture(overlay, v_uv);

    vec3 b = base_px.rgb;
    vec3 o = overlay_px.rgb;

    vec3 blended;
    if      (mode == 0) blended = blend_normal(b, o);
    else if (mode == 1) blended = blend_add(b, o);
    else if (mode == 2) blended = blend_subtract(b, o);
    else if (mode == 3) blended = blend_multiply(b, o);
    else if (mode == 4) blended = blend_screen(b, o);
    else if (mode == 5) blended = blend_overlay(b, o);
    else if (mode == 6) blended = blend_mask(b, o);
    else                blended = blend_normal(b, o);   // unknown → normal

    // effective alpha: layer opacity × overlay alpha
    // For RGB sources, overlay_px.a == 1.0 (GL default), so this is just opacity.
    float alpha = opacity * overlay_px.a;

    fragColor = vec4(mix(b, blended, alpha), base_px.a);
}
