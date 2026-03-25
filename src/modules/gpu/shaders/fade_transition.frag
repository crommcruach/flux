#version 330
// Fade / crossfade transition.
// progress 0.0 = 100% tex_a (outgoing clip),  1.0 = 100% tex_b (incoming clip)
// progress is pre-eased (easing applied in Python before passing as uniform).

in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D tex_a;    // outgoing frame (unit 0)
uniform sampler2D tex_b;    // incoming frame (unit 1)
uniform float progress;     // 0.0 .. 1.0

void main() {
    vec4 ca = texture(tex_a, v_uv);
    vec4 cb = texture(tex_b, v_uv);
    fragColor = mix(ca, cb, progress);
}
