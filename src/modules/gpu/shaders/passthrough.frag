#version 330
in vec2 v_uv;
uniform sampler2D inputTexture;
out vec4 fragColor;
void main() {
    fragColor = texture(inputTexture, v_uv);
}
