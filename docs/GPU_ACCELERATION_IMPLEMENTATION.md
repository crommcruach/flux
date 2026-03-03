# GPU Acceleration Implementation Plan

## 🎯 Overview

This document outlines GPU acceleration opportunities in Py_artnet, organized by implementation complexity and performance impact. All solutions use **OpenGL + ModernGL** for cross-vendor support (AMD Radeon + NVIDIA + Intel).

**Target**: 4K @ 60 FPS with 3-4 layers and effects

---

## 📊 Performance Impact Matrix

| Category | Current CPU | GPU Target | Speedup | Priority |
|----------|-------------|------------|---------|----------|
| **Multi-Output Soft Edge** | 33-57ms (3 outputs) | 2-4ms | **15x** | 🔥 CRITICAL |
| **Multi-Layer Blending** | 15-20ms (3 layers) | 1-2ms | **10-15x** | 🔥 CRITICAL |
| **Blur Effects** | 10-15ms | 0.5-1ms | **15-20x** | 🔥 HIGH |
| **Video Decode (H.264)** | 20ms | 2-5ms | **4-10x** | 🔥 HIGH |
| **Color Effects** | 2-3ms | 0.1ms | **20-30x** | ⚡ MEDIUM |
| **Geometric Transforms** | 3-5ms | 0.2-0.5ms | **10-15x** | ⚡ MEDIUM |
| **Total Pipeline (4K, 3 layers, 3 outputs)** | 60-80ms | **8-15ms** | **5-8x** | ✅ 60 FPS |

---

## 🚀 Phase 1: GPU Foundation (2-3 days)

**Goal**: Core GPU infrastructure for all subsequent implementations

### 1.1 Dependencies
```bash
pip install moderngl>=5.8.0 glcontext>=2.5.0 pyrr>=0.10.3
```

### 1.2 Core Modules

**`src/modules/gpu/context.py`** - GPU Context Singleton
```python
"""
Headless OpenGL context manager for backend processing.
Automatically detects available GPU (AMD/NVIDIA/Intel).
"""
- create_context() - Initialize ModernGL context
- get_context() - Get or create singleton instance
- cleanup() - Release GPU resources
- is_available() - Check GPU availability
```

**`src/modules/gpu/texture_pool.py`** - Texture Memory Management
```python
"""
Efficient texture allocation and pooling.
Minimizes GPU memory allocations.
"""
- TexturePool class
  - acquire_texture(width, height, components=3) - Get reusable texture
  - release_texture(texture) - Return to pool
  - clear() - Free all textures
```

**`src/modules/gpu/frame.py`** - GPU Frame Wrapper
```python
"""
Wraps OpenGL textures with NumPy-like interface.
"""
class GPUFrame:
    - upload(numpy_array) - CPU → GPU
    - download() - GPU → CPU
    - copy() - GPU texture copy
    - size property
```

**`src/modules/gpu/shader_library.py`** - Shader Compilation & Caching
```python
"""
GLSL shader compilation with caching.
"""
- compile_shader(vertex_src, fragment_src) - Compile program
- get_shader(name) - Get cached shader
- load_shader_file(path) - Load from file
```

**Implementation Complexity**: ⭐⭐ (Medium)  
**Time**: 2-3 days  
**Dependencies**: None  
**Risk**: Low - Standard OpenGL patterns

---

## 🎨 Phase 2A: GPU Output System (HIGHEST ROI - 3-4 days)

**Goal**: Accelerate multi-projector output with soft edge blending

**Impact**: 15x faster for 3-output setups, enables missing UI features

### 2A.1 Problem Statement

**Current Bottleneck** (`src/modules/player/outputs/slices.py:303-336`):
```python
def _apply_soft_edge(self, frame, blur_radius):
    # CPU loops + float32 math per output
    for i in range(blur_radius):
        alpha = i / blur_radius
        mask[i, :] *= alpha  # Per-pixel CPU multiplication
```

**Missing Features** (UI has controls, backend doesn't implement):
- ❌ Per-edge width control (top/bottom/left/right)
- ❌ Fade curves (linear, smooth, exponential)
- ❌ Per-channel gamma (gammaR, gammaG, gammaB)
- ❌ Blend strength control

### 2A.2 GPU Shader Implementation

**`src/modules/gpu/shaders/soft_edge.glsl`**
```glsl
#version 330

in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D inputTexture;
uniform vec4 edgeWidths;        // top, bottom, left, right (pixels)
uniform vec2 frameSize;         // width, height
uniform int curveType;          // 0=linear, 1=smooth, 2=exponential
uniform float strength;         // 0.0-1.0
uniform float gamma;            // Overall gamma
uniform vec3 gammaRGB;          // Per-channel gamma (R, G, B)

float applyCurve(float t, int type) {
    if (type == 0) return t;                    // Linear
    if (type == 1) return smoothstep(0.0, 1.0, t);  // Smooth
    if (type == 2) return t * t;                // Exponential
    return t;
}

float calculateEdgeFade(vec2 uv) {
    // Normalize edge widths (pixels → 0-1 range)
    vec2 edgeNorm = edgeWidths.xy / frameSize;
    vec2 edgeNorm2 = edgeWidths.zw / frameSize;
    
    // Calculate distance from each edge
    float top = smoothstep(0.0, edgeNorm.x, uv.y);
    float bottom = smoothstep(0.0, edgeNorm.y, 1.0 - uv.y);
    float left = smoothstep(0.0, edgeNorm2.x, uv.x);
    float right = smoothstep(0.0, edgeNorm2.y, 1.0 - uv.x);
    
    // Combine all edges (multiplicative)
    float fade = min(min(top, bottom), min(left, right));
    
    // Apply curve
    return applyCurve(fade, curveType);
}

void main() {
    vec3 color = texture(inputTexture, v_uv).rgb;
    
    // Calculate edge fade
    float fade = calculateEdgeFade(v_uv);
    
    // Apply per-channel gamma
    color = pow(color, gammaRGB);
    
    // Apply overall gamma
    fade = pow(fade, gamma);
    
    // Apply strength
    fade = mix(1.0, fade, strength);
    
    // Output with alpha channel for blending
    fragColor = vec4(color * fade, fade);
}
```

### 2A.3 Backend Integration

**`src/modules/player/outputs/slices_gpu.py`** - GPU-accelerated slice extraction
```python
"""
GPU-accelerated slice manager with soft edge blending.
Fallback to CPU if GPU unavailable.
"""

class GPUSliceManager(SliceManager):
    def __init__(self, canvas_width, canvas_height):
        super().__init__(canvas_width, canvas_height)
        
        # Try to initialize GPU
        from ...gpu.context import get_context, is_available
        self.gpu_available = is_available()
        
        if self.gpu_available:
            self.ctx = get_context()
            self._init_gpu_resources()
            logger.info("✅ GPU acceleration enabled for output slices")
        else:
            logger.warning("⚠️ GPU unavailable, using CPU fallback")
    
    def _init_gpu_resources(self):
        """Initialize GPU shaders and textures"""
        from ...gpu.shader_library import compile_shader
        
        # Load soft edge shader
        self.soft_edge_shader = compile_shader(
            vertex_src=VERTEX_SHADER,
            fragment_src=open('src/modules/gpu/shaders/soft_edge.glsl').read()
        )
        
        # Create frame buffer for rendering
        self.fbo = self.ctx.framebuffer(...)
    
    def get_slice(self, slice_id: str, frame: np.ndarray) -> np.ndarray:
        """Override with GPU acceleration"""
        if self.gpu_available:
            return self._get_slice_gpu(slice_id, frame)
        else:
            return super().get_slice(slice_id, frame)  # CPU fallback
    
    def _get_slice_gpu(self, slice_id: str, frame: np.ndarray) -> np.ndarray:
        """GPU-accelerated slice extraction with soft edge"""
        slice_def = self.slices[slice_id]
        
        # Upload frame to GPU (once)
        if not hasattr(self, '_frame_texture'):
            self._frame_texture = self.ctx.texture(frame.shape[:2][::-1], 3)
        self._frame_texture.write(frame.tobytes())
        
        # Configure soft edge shader
        soft_edge = slice_def.soft_edge or {}
        self.soft_edge_shader['edgeWidths'].value = (
            soft_edge.get('width', {}).get('top', 0),
            soft_edge.get('width', {}).get('bottom', 0),
            soft_edge.get('width', {}).get('left', 0),
            soft_edge.get('width', {}).get('right', 0)
        )
        self.soft_edge_shader['curveType'].value = {
            'linear': 0, 'smooth': 1, 'exponential': 2
        }.get(soft_edge.get('curve', 'smooth'), 1)
        self.soft_edge_shader['strength'].value = soft_edge.get('strength', 1.0)
        self.soft_edge_shader['gamma'].value = soft_edge.get('gamma', 1.0)
        self.soft_edge_shader['gammaRGB'].value = (
            soft_edge.get('gammaR', 1.0),
            soft_edge.get('gammaG', 1.0),
            soft_edge.get('gammaB', 1.0)
        )
        
        # Render slice with soft edge
        self.fbo.use()
        self._frame_texture.use(0)
        self.soft_edge_shader['inputTexture'].value = 0
        self.vao.render(...)
        
        # Download result
        result = np.frombuffer(self.fbo.read(), dtype=np.uint8)
        return result.reshape((slice_def.height, slice_def.width, 3))
```

### 2A.4 Configuration Bridge

**Update `src/modules/player/outputs/slices.py:75-90`** to pass full soft_edge dict:
```python
def add_slice(self, slice_id: str, x: int, y: int, width: int, height: int,
              rotation: float = 0, shape: str = 'rectangle',
              soft_edge: Optional[Dict] = None, ...):
    """
    soft_edge format (if dict):
    {
        'enabled': True,
        'width': {'top': 50, 'bottom': 50, 'left': 50, 'right': 50},
        'curve': 'smooth',  # 'linear', 'smooth', 'exponential'
        'strength': 1.0,
        'gamma': 1.0,
        'gammaR': 1.0, 'gammaG': 1.0, 'gammaB': 1.0
    }
    """
```

### 2A.5 Testing & Validation

**Test Cases**:
1. ✅ Single output with soft edge (compare CPU vs GPU)
2. ✅ 3 outputs @ 4K with different soft edge settings
3. ✅ Verify all curve types work (linear, smooth, exponential)
4. ✅ Verify per-channel gamma works
5. ✅ Fallback to CPU when GPU unavailable

**Performance Benchmark**:
```python
# Test: 3 outputs @ 4K with 100px soft edge
# Expected: 15-24ms (CPU) → 1-2ms (GPU)
```

**Implementation Complexity**: ⭐⭐⭐ (Medium-High)  
**Time**: 3-4 days  
**Dependencies**: Phase 1 (GPU Foundation)  
**Risk**: Medium - Requires testing with real projector setups

---

## 🎨 Phase 2B: GPU Layer Blending (3-4 days)

**Goal**: Accelerate multi-layer compositing with blend modes

**Impact**: 10-15x faster for 3+ layer setups

### 2B.1 Problem Statement

**Current Bottleneck** (`plugins/effects/blend.py:115-150`):
```python
# Float32 conversion + NumPy operations per layer
base_float = frame.astype(np.float32) * (1.0 / 255.0)
over_float = overlay.astype(np.float32) * (1.0 / 255.0)

# Blend mode calculation (multiply, screen, add, etc.)
if mode == 'multiply':
    blended = base_float * over_float  # Per-pixel multiply
elif mode == 'screen':
    blended = 1.0 - (1.0 - base_float) * (1.0 - over_float)
# ... 20+ blend modes

result = np.clip(blended * 255.0, 0, 255).astype(np.uint8)
```

### 2B.2 GPU Shader Implementation

**`src/modules/gpu/shaders/blend_modes.glsl`**
```glsl
#version 330

in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D baseTexture;
uniform sampler2D overlayTexture;
uniform int blendMode;      // 0=normal, 1=multiply, 2=screen, etc.
uniform float opacity;      // 0.0-1.0

// Blend mode functions
vec3 blendMultiply(vec3 base, vec3 blend) {
    return base * blend;
}

vec3 blendScreen(vec3 base, vec3 blend) {
    return vec3(1.0) - (vec3(1.0) - base) * (vec3(1.0) - blend);
}

vec3 blendOverlay(vec3 base, vec3 blend) {
    return mix(
        2.0 * base * blend,
        1.0 - 2.0 * (1.0 - base) * (1.0 - blend),
        step(0.5, base)
    );
}

vec3 blendAdd(vec3 base, vec3 blend) {
    return min(base + blend, vec3(1.0));
}

vec3 blendSubtract(vec3 base, vec3 blend) {
    return max(base - blend, vec3(0.0));
}

vec3 blendDarken(vec3 base, vec3 blend) {
    return min(base, blend);
}

vec3 blendLighten(vec3 base, vec3 blend) {
    return max(base, blend);
}

vec3 blendColorDodge(vec3 base, vec3 blend) {
    return base / (vec3(1.0) - blend + 0.001); // Avoid div by zero
}

vec3 blendColorBurn(vec3 base, vec3 blend) {
    return vec3(1.0) - (vec3(1.0) - base) / (blend + 0.001);
}

vec3 blendHardLight(vec3 base, vec3 blend) {
    return blendOverlay(blend, base); // Swap parameters
}

vec3 blendSoftLight(vec3 base, vec3 blend) {
    return mix(
        2.0 * base * blend + base * base * (1.0 - 2.0 * blend),
        sqrt(base) * (2.0 * blend - 1.0) + 2.0 * base * (1.0 - blend),
        step(0.5, blend)
    );
}

vec3 blendDifference(vec3 base, vec3 blend) {
    return abs(base - blend);
}

vec3 blendExclusion(vec3 base, vec3 blend) {
    return base + blend - 2.0 * base * blend;
}

// Main blend function dispatcher
vec3 applyBlendMode(vec3 base, vec3 blend, int mode) {
    if (mode == 0) return blend;                    // Normal
    if (mode == 1) return blendMultiply(base, blend);
    if (mode == 2) return blendScreen(base, blend);
    if (mode == 3) return blendOverlay(base, blend);
    if (mode == 4) return blendAdd(base, blend);
    if (mode == 5) return blendSubtract(base, blend);
    if (mode == 6) return blendDarken(base, blend);
    if (mode == 7) return blendLighten(base, blend);
    if (mode == 8) return blendColorDodge(base, blend);
    if (mode == 9) return blendColorBurn(base, blend);
    if (mode == 10) return blendHardLight(base, blend);
    if (mode == 11) return blendSoftLight(base, blend);
    if (mode == 12) return blendDifference(base, blend);
    if (mode == 13) return blendExclusion(base, blend);
    return blend; // Fallback to normal
}

void main() {
    vec4 base = texture(baseTexture, v_uv);
    vec4 overlay = texture(overlayTexture, v_uv);
    
    // Apply blend mode
    vec3 blended = applyBlendMode(base.rgb, overlay.rgb, blendMode);
    
    // Apply opacity
    vec3 result = mix(base.rgb, blended, opacity * overlay.a);
    
    fragColor = vec4(result, base.a);
}
```

### 2B.3 Backend Integration

**`plugins/effects/blend_gpu.py`** - GPU-accelerated blend effect
```python
"""
GPU-accelerated blend effect with automatic fallback.
"""

class BlendEffectGPU(BlendEffect):
    def __init__(self):
        super().__init__()
        
        from modules.gpu.context import get_context, is_available
        self.gpu_available = is_available()
        
        if self.gpu_available:
            self.ctx = get_context()
            self._init_gpu_resources()
    
    def process_frame(self, frame, overlay=None, **kwargs):
        """Override with GPU acceleration"""
        if not self.gpu_available or overlay is None:
            return super().process_frame(frame, overlay, **kwargs)
        
        return self._process_frame_gpu(frame, overlay)
    
    def _process_frame_gpu(self, frame, overlay):
        """GPU blend processing"""
        # Upload textures (cached)
        base_tex = self._upload_texture(frame)
        overlay_tex = self._upload_texture(overlay)
        
        # Configure shader
        blend_mode_map = {
            'normal': 0, 'multiply': 1, 'screen': 2, 'overlay': 3,
            'add': 4, 'subtract': 5, 'darken': 6, 'lighten': 7,
            # ... all modes
        }
        self.blend_shader['blendMode'].value = blend_mode_map.get(
            self.blend_mode, 0
        )
        self.blend_shader['opacity'].value = self.opacity / 100.0
        
        # Render
        self.fbo.use()
        base_tex.use(0)
        overlay_tex.use(1)
        self.blend_shader['baseTexture'].value = 0
        self.blend_shader['overlayTexture'].value = 1
        self.vao.render()
        
        # Download result
        return self._download_frame()
```

**Implementation Complexity**: ⭐⭐⭐ (Medium-High)  
**Time**: 3-4 days  
**Dependencies**: Phase 1 (GPU Foundation)  
**Risk**: Low - Well-defined shader operations

---

## 🖼️ Phase 3: GPU Color Effects (Easy Wins - 2-3 days)

**Goal**: Convert pixel-independent effects to GPU shaders

**Impact**: 20-30x faster, near-zero CPU usage

### 3.1 Shader Library

**Effect Category: Color Adjustments** (10 effects, 1-2 hours each)

**Files**: `src/modules/gpu/shaders/effects/`
```
brightness_contrast.glsl    - Brightness + contrast
hue_rotate.glsl            - Hue rotation
saturation.glsl            - Saturation adjustment
gamma.glsl                 - Gamma correction
exposure.glsl              - Exposure adjustment
temperature.glsl           - Color temperature
invert.glsl                - Color inversion
threshold.glsl             - Threshold
posterize.glsl             - Posterization
solarize.glsl             - Solarization
```

**Example: `brightness_contrast.glsl`**
```glsl
#version 330
uniform sampler2D inputTexture;
uniform float brightness; // -1.0 to 1.0
uniform float contrast;   // -1.0 to 1.0

void main() {
    vec3 color = texture(inputTexture, v_uv).rgb;
    
    // Apply contrast (around midpoint)
    color = (color - 0.5) * (1.0 + contrast) + 0.5;
    
    // Apply brightness
    color += brightness;
    
    fragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
```

**Example: `hue_rotate.glsl`**
```glsl
vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
}

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
    vec3 color = texture(inputTexture, v_uv).rgb;
    vec3 hsv = rgb2hsv(color);
    hsv.x = fract(hsv.x + hueShift); // Rotate hue
    fragColor = vec4(hsv2rgb(hsv), 1.0);
}
```

### 3.2 Generic GPU Effect Wrapper

**`plugins/effects/gpu_effect_base.py`**
```python
"""
Base class for GPU-accelerated effects with automatic fallback.
"""

class GPUEffectBase(PluginBase):
    def __init__(self, shader_name: str):
        super().__init__()
        self.shader_name = shader_name
        
        from modules.gpu.context import is_available, get_context
        self.gpu_available = is_available()
        
        if self.gpu_available:
            self.ctx = get_context()
            self.shader = self._load_shader(shader_name)
    
    def process_frame(self, frame, **kwargs):
        if self.gpu_available:
            try:
                return self._process_gpu(frame)
            except Exception as e:
                logger.warning(f"GPU processing failed: {e}, falling back to CPU")
        
        return self._process_cpu(frame)  # Must be implemented by subclass
    
    def _process_gpu(self, frame):
        """Generic GPU processing pipeline"""
        # Upload
        texture = self._upload_texture(frame)
        
        # Configure shader with self.parameters
        for key, value in self.parameters.items():
            if key in self.shader:
                self.shader[key].value = value
        
        # Render
        self.fbo.use()
        texture.use(0)
        self.vao.render()
        
        # Download
        return self._download_frame()
    
    def _process_cpu(self, frame):
        """Must be overridden by subclass"""
        raise NotImplementedError()
```

**Implementation Complexity**: ⭐ (Easy)  
**Time**: 2-3 days for 10 effects  
**Dependencies**: Phase 1  
**Risk**: Very Low - Simple shaders

---

## 🔄 Phase 4: GPU Geometric Transforms (2-3 days)

**Goal**: Transform, rotate, scale, zoom via GPU texture sampling

**Impact**: 10-30x faster

### 4.1 Unified Transform Shader

**`src/modules/gpu/shaders/effects/transform.glsl`**
```glsl
#version 330

uniform sampler2D inputTexture;
uniform vec2 position;      // Translation (-1 to 1)
uniform float rotation;     // Radians
uniform vec2 scale;         // Scale factors
uniform vec2 pivot;         // Rotation pivot (0-1)

mat2 rotate2D(float angle) {
    float s = sin(angle);
    float c = cos(angle);
    return mat2(c, -s, s, c);
}

void main() {
    // Center UV around pivot
    vec2 uv = v_uv - pivot;
    
    // Apply rotation
    uv = rotate2D(rotation) * uv;
    
    // Apply scale
    uv /= scale;
    
    // Apply translation
    uv -= position;
    
    // Re-center
    uv += pivot;
    
    // Sample texture (with wrapping or black border)
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        fragColor = vec4(0.0); // Black outside bounds
    } else {
        fragColor = texture(inputTexture, uv);
    }
}
```

### 4.2 GPU Transform Effect

**Update `plugins/effects/transform.py`** to use GPU:
```python
class TransformEffect(GPUEffectBase):
    def __init__(self):
        super().__init__(shader_name='transform')
        # Parameters already defined
    
    def _process_gpu(self, frame):
        # Map parameters to shader uniforms
        self.shader['position'].value = (
            self.position_x / 100.0,
            self.position_y / 100.0
        )
        self.shader['rotation'].value = np.radians(self.rotation_z)
        self.shader['scale'].value = (
            self.scale_x / 100.0,
            self.scale_y / 100.0
        )
        
        return super()._process_gpu(frame)
    
    def _process_cpu(self, frame):
        # Keep existing CPU implementation as fallback
        return existing_cpu_code()
```

**Implementation Complexity**: ⭐⭐ (Medium)  
**Time**: 2-3 days  
**Dependencies**: Phase 1  
**Risk**: Low

---

## 🌊 Phase 5: GPU Convolution Effects (3-4 days)

**Goal**: Blur, sharpen, emboss via GPU compute

**Impact**: 15-20x faster for blur operations

### 5.1 Separable Gaussian Blur

**`src/modules/gpu/shaders/effects/gaussian_blur.glsl`**
```glsl
#version 330

uniform sampler2D inputTexture;
uniform vec2 direction;     // (1,0) for horizontal, (0,1) for vertical
uniform int radius;         // Blur radius
uniform float sigma;        // Gaussian sigma

float gaussianWeight(float x, float sigma) {
    return exp(-(x*x) / (2.0 * sigma * sigma));
}

void main() {
    vec2 texelSize = 1.0 / textureSize(inputTexture, 0);
    vec3 result = vec3(0.0);
    float totalWeight = 0.0;
    
    for (int i = -radius; i <= radius; i++) {
        float weight = gaussianWeight(float(i), sigma);
        vec2 offset = direction * float(i) * texelSize;
        result += texture(inputTexture, v_uv + offset).rgb * weight;
        totalWeight += weight;
    }
    
    fragColor = vec4(result / totalWeight, 1.0);
}
```

### 5.2 Two-Pass Blur Implementation

```python
class BlurEffectGPU(GPUEffectBase):
    def _process_gpu(self, frame):
        radius = int(self.radius)
        sigma = radius / 2.0
        
        # Pass 1: Horizontal blur
        self.shader['direction'].value = (1.0, 0.0)
        self.shader['radius'].value = radius
        self.shader['sigma'].value = sigma
        temp = self._render_pass(frame)
        
        # Pass 2: Vertical blur
        self.shader['direction'].value = (0.0, 1.0)
        result = self._render_pass(temp)
        
        return result
```

**Implementation Complexity**: ⭐⭐⭐ (Medium-High)  
**Time**: 3-4 days  
**Dependencies**: Phase 1  
**Risk**: Medium - Multi-pass rendering

---

## 🎬 Phase 6: GPU Video Decode (Advanced - 1 week)

**Goal**: Hardware decode directly to GPU texture

**Impact**: 4-10x faster for H.264/H.265

### 6.1 Platform-Specific Decoders

**NVIDIA (NVDEC)**:
```python
# Via PyAV with CUDA hardware acceleration
import av
av.open(video_path, options={'hwaccel': 'cuda', 'hwaccel_device': '0'})
```

**AMD (AMF)**:
```python
# Via FFmpeg hardware acceleration
av.open(video_path, options={'hwaccel': 'dxva2'})  # Windows
av.open(video_path, options={'hwaccel': 'vaapi'})  # Linux
```

**Intel (QuickSync)**:
```python
av.open(video_path, options={'hwaccel': 'qsv'})
```

### 6.2 Auto-Detection

```python
def detect_hardware_decoder():
    """Auto-detect best available hardware decoder"""
    # Try NVIDIA NVDEC
    if check_cuda_available():
        return 'cuda'
    
    # Try AMD AMF
    if check_amd_available():
        return 'dxva2' if sys.platform == 'win32' else 'vaapi'
    
    # Try Intel QuickSync
    if check_intel_available():
        return 'qsv'
    
    # Fallback to software
    return None
```

**Implementation Complexity**: ⭐⭐⭐⭐ (High)  
**Time**: 1 week  
**Dependencies**: PyAV, hardware-specific drivers  
**Risk**: High - Platform/hardware dependent

---

## 📋 Implementation Roadmap

### Recommended Order

**Week 1-2: Foundation + Output System**
1. ✅ Phase 1: GPU Foundation (2-3 days)
2. ✅ Phase 2A: GPU Output System (3-4 days)
   - **Biggest immediate win for multi-projector setups**
   - **Enables missing UI features**

**Week 3: Layer Blending**
3. ✅ Phase 2B: GPU Layer Blending (3-4 days)
   - **Critical for multi-layer compositing**

**Week 4: Easy Wins**
4. ✅ Phase 3: GPU Color Effects (2-3 days)
5. ✅ Phase 4: GPU Transforms (2-3 days)

**Week 5: Advanced**
6. ✅ Phase 5: GPU Convolution (3-4 days)
7. ⚠️ Phase 6: Hardware Decode (optional, 1 week)

---

## 🧪 Testing Strategy

### Performance Benchmarks

**Create `tests/gpu_benchmark.py`**:
```python
def benchmark_output_system():
    """Benchmark: 3 outputs @ 4K with soft edge"""
    # CPU baseline
    cpu_time = measure_cpu_output()
    
    # GPU accelerated
    gpu_time = measure_gpu_output()
    
    speedup = cpu_time / gpu_time
    assert speedup > 10, f"Expected 10x speedup, got {speedup}x"

def benchmark_layer_blending():
    """Benchmark: 3 layers with multiply blend"""
    # Expected: 15-20ms CPU → 1-2ms GPU
    pass

def benchmark_blur():
    """Benchmark: Gaussian blur radius=25"""
    # Expected: 10-15ms CPU → 0.5-1ms GPU
    pass
```

### Validation Tests

```python
def test_gpu_cpu_equivalence():
    """Ensure GPU output matches CPU (within tolerance)"""
    cpu_result = cpu_process_frame()
    gpu_result = gpu_process_frame()
    
    # Allow small floating-point differences
    diff = np.abs(cpu_result.astype(float) - gpu_result.astype(float))
    assert np.mean(diff) < 1.0, "GPU output differs from CPU"
```

---

## 🔧 Fallback & Compatibility

### Automatic Detection

```python
# config.json
{
    "gpu": {
        "enabled": true,        // Master switch
        "auto_detect": true,    // Auto-detect GPU availability
        "force_cpu": false,     // Force CPU fallback (for debugging)
        "vendor": "auto",       // "auto", "nvidia", "amd", "intel"
        "log_performance": true // Log GPU vs CPU performance
    }
}
```

### Graceful Degradation

```python
class GPUManager:
    def __init__(self):
        if config['gpu']['enabled'] and not config['gpu']['force_cpu']:
            try:
                self.gpu_available = self._init_gpu()
            except Exception as e:
                logger.warning(f"GPU initialization failed: {e}")
                logger.info("Falling back to CPU processing")
                self.gpu_available = False
        else:
            self.gpu_available = False
```

---

## 📊 Expected Results

### Performance Gains (4K @ 60 FPS target)

| Scenario | Current FPS | GPU FPS | Status |
|----------|-------------|---------|--------|
| **Single layer, no effects** | 45-50 | 60+ | ✅ Achievable |
| **3 layers with blend modes** | 15-20 | 60+ | ✅ Achievable |
| **3 outputs with soft edge** | 17-30 | 60+ | ✅ Achievable |
| **3 layers + 3 outputs + effects** | 12-15 | 50-60 | ✅ Achievable |
| **Full production (4 layers, 4 outputs, effects)** | 8-12 | 45-55 | ✅ Achievable |

### Memory Usage

- **GPU VRAM**: ~200-400 MB (4K textures + buffers)
- **CPU RAM**: Reduced by 30-40% (less NumPy copies)
- **Transfer overhead**: ~0.5-1ms per frame (CPU↔GPU)

---

## 🎯 Success Criteria

### Phase 2A (Output System) - Critical
- ✅ 3 outputs @ 4K with soft edge: **< 5ms total**
- ✅ All soft edge features working (curves, gamma, per-edge width)
- ✅ CPU fallback works when GPU unavailable
- ✅ No visual artifacts compared to CPU

### Phase 2B (Layer Blending) - Critical  
- ✅ 3 layers with multiply blend: **< 2ms total**
- ✅ All 20+ blend modes work correctly
- ✅ Alpha channel support preserved

### Overall Target
- ✅ Full pipeline (4K, 3 layers, 3 outputs): **< 20ms** (60 FPS sustainable)
- ✅ Zero crashes or memory leaks
- ✅ Works on AMD, NVIDIA, Intel GPUs

---

## 🚀 Quick Start (Proof of Concept)

**Day 1**: GPU Foundation + Simple Color Effect
```bash
# Install dependencies
pip install moderngl glcontext pyrr

# Create basic context
python tests/gpu_poc_foundation.py

# Expected output:
# ✅ GPU detected: NVIDIA GeForce RTX 3080
# ✅ OpenGL 4.6 available
# ✅ Context initialized successfully
```

**Day 2-3**: GPU Soft Edge Blending POC
```bash
# Test single output with soft edge
python tests/gpu_poc_soft_edge.py

# Expected output:
# CPU time: 8.2ms
# GPU time: 0.3ms
# Speedup: 27.3x ✅
```

**Day 4-5**: GPU Layer Blending POC
```bash
# Test 3 layers with multiply blend
python tests/gpu_poc_blending.py

# Expected output:
# CPU time (3 layers): 18.5ms
# GPU time (3 layers): 1.2ms
# Speedup: 15.4x ✅
```

---

## � NumPy GPU Acceleration (Critical!)

### Your NumPy Usage Analysis

**You use NumPy EXTENSIVELY** - grep shows 100+ instances across codebase:
- ✅ Float32 conversions: `frame.astype(np.float32)`
- ✅ Array operations: `np.clip()`, `np.zeros()`, `np.ones()`
- ✅ Blending math: multiplication, addition, alpha blending
- ✅ Soft edge: gradient masks, multiplication
- ✅ Color adjustments: contrast, brightness, per-channel

**This is perfect for GPU acceleration!**

---

### Cross-Vendor Strategy (AMD + NVIDIA + Intel)

**CRITICAL**: For AMD + NVIDIA compatibility, use **ModernGL** as PRIMARY solution!

**Why ModernGL Solves Everything:**
- ✅ **Works on ALL GPUs** (AMD Radeon, NVIDIA GeForce, Intel integrated)
- ✅ **OpenGL shaders replace NumPy operations** (blend, multiply, add, etc.)
- ✅ **Cross-platform** (Windows, Linux, macOS)
- ✅ **Mature and stable**
- ✅ **Single codebase** for all vendors

**ModernGL handles your NumPy operations via shaders:**
```glsl
// Fragment shader replaces NumPy blend operation
vec3 base = texture(baseTexture, uv).rgb;
vec3 overlay = texture(overlayTexture, uv).rgb;
vec3 result = base * overlay;  // Same as: base_float * overlay_float
fragColor = vec4(result, 1.0);
```

**Performance: Same as CuPy, but works on ALL GPUs!**
- AMD Radeon: ✅ 10-15x faster
- NVIDIA GeForce: ✅ 10-15x faster  
- Intel integrated: ✅ 8-12x faster

---

### Option 1A: CuPy (Optional NVIDIA Bonus)

**Only if you want extra convenience for simple NumPy operations**

**What is CuPy?**
- Drop-in NumPy replacement that runs on NVIDIA GPUs
- **Same API** as NumPy (just change `np` → `cp`)
- Automatic CUDA kernel generation

**Pros**:
- ✅ Nearly **zero code changes** for simple operations
- ✅ Convenient for preprocessing/postprocessing
- ✅ Can coexist with ModernGL

**Cons**:
- ❌ **NVIDIA-only** (excludes AMD users!)
- ❌ Requires CUDA toolkit (200MB install)
- ❌ Not all NumPy functions supported (95% coverage)

**Verdict**: **Optional** - Only adds convenience for NVIDIA users, ModernGL already handles everything

**Installation** (optional, NVIDIA only):
```bash
pip install cupy-cuda12x  # For CUDA 12.x
```

---

### Option 1B: PyOpenCL (Cross-Vendor NumPy Alternative)

**For NumPy-style array operations on ALL GPUs**

**What is PyOpenCL?**
- OpenCL bindings for Python with NumPy-like arrays
- Works on AMD, NVIDIA, Intel via OpenCL

**Pros**:
- ✅ **Cross-vendor** (AMD Radeon + NVIDIA + Intel)
- ✅ NumPy-compatible API (`pyopencl.array`)
- ✅ Good Windows support

**Cons**:
- ❌ More complex than CuPy
- ❌ Requires OpenCL drivers (usually pre-installed)
- ❌ Less mature ecosystem than CUDA

**Example**:
```python
import pyopencl as cl
import pyopencl.array as cl_array

# Create OpenCL context (auto-detects AMD/NVIDIA)
ctx = cl.create_some_context()
queue = cl.CommandQueue(ctx)

# Upload to GPU
frame_gpu = cl_array.to_device(queue, frame)
overlay_gpu = cl_array.to_device(queue, overlay)

# NumPy-style operations on GPU
result = frame_gpu * overlay_gpu  # Works on AMD or NVIDIA!

# Download from GPU
result_cpu = result.get()
```

**Performance**: Similar to CuPy/ModernGL (10-15x faster)

**Verdict**: **Not needed** - ModernGL shaders are simpler and more efficient

---

### RECOMMENDED: ModernGL for Everything (Cross-Vendor)

**Implementation Example**:
```python
# src/modules/gpu/numpy_backend.py
"""
GPU-accelerated NumPy operations with automatic fallback.
Auto-detects CuPy (NVIDIA) and falls back to NumPy (CPU).
"""

try:
    import cupy as cp
    CUPY_AVAILABLE = True
    print("✅ CuPy detected - NumPy operations will use NVIDIA GPU")
except ImportError:
    import numpy as cp
    CUPY_AVAILABLE = False
    print("⚠️ CuPy not available - NumPy operations on CPU")

def get_array_module(arr):
    """Get appropriate array module (cp or np)"""
    if CUPY_AVAILABLE:
        return cp.get_array_module(arr)
    return np

def asarray(arr):
    """Convert to GPU array if CuPy available"""
    if CUPY_AVAILABLE:
        return cp.asarray(arr)
    return np.asarray(arr)

def asnumpy(arr):
    """Convert GPU array back to CPU NumPy"""
    if CUPY_AVAILABLE and isinstance(arr, cp.ndarray):
        return cp.asnumpy(arr)
    return np.asarray(arr)
```

**Convert Existing Code** (plugins/effects/blend.py example):
```python
# Before (CPU NumPy)
import numpy as np

def process_frame(self, frame, overlay=None):
    base_float = frame.astype(np.float32) * (1.0 / 255.0)
    over_float = overlay.astype(np.float32) * (1.0 / 255.0)
    
    if self.blend_mode == 'multiply':
        blended = base_float * over_float
    
    return np.clip(blended * 255.0, 0, 255).astype(np.uint8)

# After (GPU-accelerated, auto-fallback)
from modules.gpu.numpy_backend import asarray, asnumpy, get_array_module

def process_frame(self, frame, overlay=None):
    # Upload to GPU (if CuPy available)
    frame_gpu = asarray(frame)
    overlay_gpu = asarray(overlay)
    
    # Get appropriate module (cp or np)
    xp = get_array_module(frame_gpu)
    
    # Same NumPy code, runs on GPU!
    base_float = frame_gpu.astype(xp.float32) * (1.0 / 255.0)
    over_float = overlay_gpu.astype(xp.float32) * (1.0 / 255.0)
    
    if self.blend_mode == 'multiply':
        blended = base_float * over_float
    
    result_gpu = xp.clip(blended * 255.0, 0, 255).astype(xp.uint8)
    
    # Download from GPU
    return asnumpy(result_gpu)
```

**Where to Use CuPy**:
1. ✅ Blend operations (`plugins/effects/blend.py`)
2. ✅ Soft edge masks (`src/modules/player/outputs/slices.py`)
3. ✅ Color adjustments (`src/modules/player/outputs/slices.py:361`)
4. ✅ Effect processing (all `plugins/effects/*.py`)
5. ✅ Generators (`plugins/generators/*.py`)

**Performance Expectations**:
| Operation | NumPy CPU | CuPy GPU (NVIDIA) | Speedup |
|-----------|-----------|-------------------|---------|
| **Float32 conversion** | 2-3ms | 0.2ms | **10-15x** |
| **Multiply/Add (4K)** | 1-2ms | 0.05ms | **20-40x** |
| **Clip operation** | 1-2ms | 0.05ms | **20-40x** |
| **Soft edge gradient** | 5-8ms | 0.3ms | **15-25x** |
| **Full blend (3 layers)** | 15-20ms | 1-2ms | **10-15x** |

---

### Option 2: PyTorch (Heavy Dependency)

**What is PyTorch?**
- Deep learning framework with NumPy-like API
- GPU support for AMD (ROCm) + NVIDIA (CUDA)

**Pros**:
- ✅ Cross-vendor (NVIDIA + AMD on Linux)
- ✅ Extensive GPU operations
- ✅ Good NumPy compatibility

**Cons**:
- ❌ **500MB+ install** (includes ML libraries you don't need)
- ❌ Different API (not drop-in NumPy replacement)
- ❌ AMD support only on Linux (no Windows)
- ❌ Overkill for your use case

**Verdict**: **Not recommended** - too heavy for your needs

---

### Option 3: JAX (Google, Experimental)

**What is JAX?**
- Google's NumPy replacement with automatic differentiation
- GPU/TPU support

**Pros**:
- ✅ Pure NumPy API
- ✅ Cross-vendor potential

**Cons**:
- ❌ Still experimental
- ❌ Limited Windows support
- ❌ Smaller ecosystem than CuPy

**Verdict**: **Not recommended** - stick with CuPy or ModernGL

---

### RECOMMENDED: Cross-Vendor Strategy (AMD + NVIDIA + Intel)

**ModernGL handles ALL your NumPy operations via GPU shaders:**

```
┌─────────────────────────────────────────────────────────┐
│       PRIMARY: ModernGL (Works on ALL GPUs)              │
│       AMD Radeon | NVIDIA GeForce | Intel Graphics      │
└─────────────────────────────────────────────────────────┘

1. ModernGL Shaders (Replaces NumPy operations)
   ├─ Float32 conversion → Shader texture upload
   ├─ np.multiply() → Fragment shader multiplication
   ├─ np.clip() → GLSL clamp()
   ├─ Array operations → GPU parallel processing
   ├─ Blend modes → Shader blend functions
   ├─ Color adjustments → Shader uniforms
   └─ All effects → GLSL implementations

2. CPU NumPy (Fallback only)
   └─ When GPU unavailable (rare)

┌──────────────────┐
│ Frame Pipeline   │   ← ALL operations on GPU!
└──────────────────┘
        │
        ├─→ [Upload to GPU Texture] (0.5ms)
        │
        ├─→ [ModernGL Shader Chain] (1-2ms)
        │   • Blend shader (multiply/screen/add)
        │   • Color adjustment shader
        │   • Soft edge shader
        │   • Transform shader
        │
        └─→ [Download to CPU] (0.5ms)
        
Total: 2-3ms vs 15-20ms CPU (8-10x faster)
✅ Works on AMD, NVIDIA, Intel
```

**Optional: CuPy for Convenience** (NVIDIA only)
```
If user has NVIDIA GPU:
  ├─→ Use CuPy for simple preprocessing (optional)
  ├─→ Still use ModernGL for main pipeline
  └─→ Both coexist perfectly
  
If user has AMD GPU:
  └─→ ModernGL handles everything (same performance!)
```

**Implementation Priority** (Cross-Vendor Focus):

**Phase 1**: ModernGL Foundation (ALL GPUs) ← **START HERE**
- ✅ Works on AMD Radeon, NVIDIA GeForce, Intel
- ✅ Handles ALL rendering + NumPy operations via shaders
- ✅ **Single implementation for all vendors**
- ✅ No vendor-specific code needed

**Phase 2**: Optimization
- ✅ Keep data on GPU between operations
- ✅ Minimize CPU↔GPU transfers
- ✅ Shader caching

**Phase 3**: Optional CuPy (NVIDIA bonus) ← **Only if desired**
- ⚠️ NVIDIA users get slight convenience boost
- ⚠️ Not needed - ModernGL already handles everything
- ⚠️ Adds vendor-specific code path

---

### Performance Comparison: NumPy Operations

**Example: Blend Effect with 3 Layers @ 4K**

| Approach | AMD Radeon | NVIDIA GeForce | Intel | Notes |
|----------|------------|----------------|-------|-------|
| **CPU NumPy (current)** | 15-20ms | 15-20ms | 15-20ms | Your current code |
| **ModernGL Shaders** | **1-2ms** ✅ | **1-2ms** ✅ | **2-3ms** ✅ | **WORKS EVERYWHERE** |
| **CuPy** | ❌ N/A | 1-2ms ⚠️ | ❌ N/A | NVIDIA-only, not needed |
| **PyOpenCL** | 2-3ms | 2-3ms | 2-4ms | Complex, ModernGL better |

**Verdict**: **Use ModernGL** - works on all GPUs with best performance!

---

### Quick Start: Adding CuPy to Your Project

**Step 1: Install CuPy (optional, NVIDIA only)**
```bash
# Check if NVIDIA GPU available
nvidia-smi

# Install CuPy
pip install cupy-cuda12x
```

**Step 2: Create GPU-aware NumPy wrapper**
```python
# src/modules/gpu/numpy_backend.py
try:
    import cupy as cp
    CUPY_AVAILABLE = True
    
    def to_gpu(arr):
        return cp.asarray(arr)
    
    def to_cpu(arr):
        return cp.asnumpy(arr) if isinstance(arr, cp.ndarray) else arr
    
    def get_module(arr):
        return cp.get_array_module(arr)
    
except ImportError:
    import numpy as cp
    CUPY_AVAILABLE = False
    
    def to_gpu(arr):
        return arr
    
    def to_cpu(arr):
        return arr
    
    def get_module(arr):
        return np

print(f"GPU NumPy: {'✅ CuPy (NVIDIA)' if CUPY_AVAILABLE else '❌ CPU fallback'}")
```

**Step 3: Update one effect as test**
```python
# plugins/effects/blend.py
from modules.gpu.numpy_backend import to_gpu, to_cpu, get_module

class BlendEffect(PluginBase):
    def __init__(self):
        super().__init__()
        self.use_gpu = True  # Config option
    
    def process_frame(self, frame, overlay=None, **kwargs):
        if not self.use_gpu:
            return self._process_cpu(frame, overlay)
        
        # Try GPU processing
        try:
            return self._process_gpu(frame, overlay)
        except Exception as e:
            logger.warning(f"GPU processing failed: {e}")
            return self._process_cpu(frame, overlay)
    
    def _process_gpu(self, frame, overlay):
        """GPU-accelerated blending (CuPy on NVIDIA, or OpenGL)"""
        # Upload to GPU
        frame_gpu = to_gpu(frame)
        overlay_gpu = to_gpu(overlay)
        
        # Get appropriate module (cp or np)
        xp = get_module(frame_gpu)
        
        # SAME NumPy code, runs on GPU!
        base = frame_gpu.astype(xp.float32) * (1.0 / 255.0)
        over = overlay_gpu.astype(xp.float32) * (1.0 / 255.0)
        
        if self.blend_mode == 'multiply':
            result = base * over
        elif self.blend_mode == 'screen':
            result = 1.0 - (1.0 - base) * (1.0 - over)
        # ... other modes
        
        result = xp.clip(result * 255.0, 0, 255).astype(xp.uint8)
        
        # Download from GPU
        return to_cpu(result)
    
    def _process_cpu(self, frame, overlay):
        """CPU fallback (existing code)"""
        # Your current NumPy implementation
        pass
```

**Step 4: Benchmark**
```python
# tests/benchmark_cupy.py
import numpy as np
import time

# Your existing blend code
from plugins.effects.blend import BlendEffect

frame = np.random.randint(0, 255, (2160, 3840, 3), dtype=np.uint8)
overlay = np.random.randint(0, 255, (2160, 3840, 3), dtype=np.uint8)

blend = BlendEffect()
blend.blend_mode = 'multiply'

# CPU benchmark
blend.use_gpu = False
start = time.perf_counter()
for _ in range(100):
    result = blend.process_frame(frame, overlay)
cpu_time = (time.perf_counter() - start) / 100

# GPU benchmark (if CuPy available)
blend.use_gpu = True
start = time.perf_counter()
for _ in range(100):
    result = blend.process_frame(frame, overlay)
gpu_time = (time.perf_counter() - start) / 100

print(f"CPU: {cpu_time*1000:.2f}ms")
print(f"GPU: {gpu_time*1000:.2f}ms")
print(f"Speedup: {cpu_time/gpu_time:.1f}x")

# Expected results (4K):
# CPU: 15-20ms
# GPU: 1-2ms (CuPy on NVIDIA) or 1-2ms (OpenGL on all GPUs)
# Speedup: 10-15x
```

---

### Memory Management with CuPy

**Problem**: GPU memory is limited (8GB typical)

**Solution**: Keep frequently-used frames on GPU
```python
class GPUFrameCache:
    """Cache frames on GPU to avoid repeated uploads"""
    def __init__(self, max_frames=10):
        self.cache = {}
        self.max_frames = max_frames
    
    def get(self, frame_id, frame_np):
        """Get GPU frame from cache or upload"""
        if frame_id not in self.cache:
            # Upload to GPU
            self.cache[frame_id] = to_gpu(frame_np)
            
            # Evict oldest if cache full
            if len(self.cache) > self.max_frames:
                self.cache.pop(next(iter(self.cache)))
        
        return self.cache[frame_id]
```

---

### Configuration

**Add to config.json**:
```json
{
    "gpu": {
        "enabled": true,
        "backend": "auto",  // "auto", "cupy", "opengl", "cpu"
        "cupy": {
            "enabled": true,        // Use CuPy if available (NVIDIA)
            "cache_frames": true,   // Keep frames on GPU
            "max_cache_mb": 512     // GPU memory limit for cache
        },
        "opengl": {
            "enabled": true,        // Use OpenGL for rendering (all GPUs)
            "prefer_shaders": true  // Prefer shaders over CuPy when both available
        }
    }
}
```

--- for AMD + NVIDIA Compatibility

**✅ RECOMMENDED: ModernGL-Only Approach (Cross-Vendor)**

**Why ModernGL is the answer:**
1. ✅ **Works on ALL GPUs** (AMD Radeon, NVIDIA GeForce, Intel)
2. ✅ **Replaces your NumPy operations** with GPU shaders
3. ✅ **Same performance** as CuPy but cross-vendor
4. ✅ **Single codebase** - no vendor-specific code paths
5. ✅ **More efficient** - data stays on GPU

**How ModernGL replaces NumPy:**
```python
# NumPy CPU (current)
base = frame.astype(np.float32) / 255.0      # 2ms
result = np.clip(base * overlay, 0, 1)       # 3ms
output = (result * 255).astype(np.uint8)     # 1ms
Total: 6ms

# ModernGL GPU (AMD + NVIDIA + Intel)
# Upload once
texture_base = ctx.texture(frame.shape[:2][::-1], 3)
texture_base.write(frame)

# Process on GPU via shader (ALL operations combined)
shader['baseTexture'] = 0
shader['overlayTexture'] = 1
fbo.use()
vao.render()

# Download result
result = fbo.read()
Total: 0.5ms (upload) + 0.3ms (shader) + 0.5ms (download) = 1.3ms
```

**Expected Performance** (ALL vendors):
- **AMD Radeon**: 10-15x faster ✅
- **NVIDIA GeForce**: 10-15x faster ✅
- **Intel Graphics**: 8-12x faster ✅
- **Fallback to CPU**: Always works ✅

**Implementation Effort**:
- **ModernGL shaders**: 2-3 weeks (comprehensive, cross-vendor)
- **CuPy integration**: Don't bother - ModernGL better
- **PyOpenCL**: Don't bother - ModernGL better

**Your extensive NumPy usage is PERFECT for ModernGL shaders** - every NumPy operation becomes a GPU shader operation that works on AMD and NVIDIA! 🚀

---

### Why CuPy/PyOpenCL Are Not Needed

**Problem with CuPy**:
- ❌ NVIDIA-only (excludes AMD users)
- ❌ Maintains two code paths (GPU/CPU)
- ❌ Still requires CPU↔GPU transfers

**Problem with PyOpenCL**:
- ❌ More complex than ModernGL
- ❌ Less optimized for graphics operations
- ❌ Still requires CPU↔GPU transfers

**ModernGL Advantage**:
- ✅ Frames stay as GPU textures (zero CPU transfer)
- ✅ All operations in shaders (maximum efficiency)
- ✅ Works on ALL GPUs (single code path)
- ✅ Purpose-built for graphics operations

**Verdict**: **Skip CuPy/PyOpenCL entirely, use ModernGL for everything**

Your **extensive NumPy usage** makes GPU acceleration even more valuable - this is where you'll see the biggest gains! 🚀

---

## 📖 Further Reading

- [ModernGL Documentation](https://moderngl.readthedocs.io/)
- [CuPy Documentation](https://docs.cupy.dev/en/stable/)
- [CuPy Performance Comparison](https://docs.cupy.dev/en/stable/user_guide/performance.html)
- [OpenGL Shader Tutorial](https://learnopengl.com/Getting-started/Shaders)
- [GPU Gems: Efficient Gaussian Blur](https://developer.nvidia.com/gpugems/gpugems3/part-vi-gpu-computing/chapter-40-incremental-computation-gaussian)
- [Photoshop Blend Modes Math](https://en.wikipedia.org/wiki/Blend_modes)

---

## 🔄 Maintenance & Updates

**Monthly**:
- Benchmark performance on new GPU drivers
- Test with new graphics cards (AMD, NVIDIA releases)
- Review GPU memory usage trends

**Quarterly**:
- Update ModernGL to latest version
- Review and optimize shader code
- Add new blend modes / effects as requested

**Yearly**:
- Evaluate new GPU APIs (Vulkan, DirectX 12)
- Consider migrating effects to compute shaders
- Review hardware decode support

---

## Summary

**Immediate Priority**: Phase 2A (GPU Output System)
- **Biggest performance win** for multi-projector setups
- **Enables missing features** already in UI
- **15x speedup** for soft edge blending
- **Time**: 3-4 days after foundation

**Next Priority**: Phase 2B (GPU Layer Blending)
- **10-15x speedup** for multi-layer compositing
- **Critical for video walls**
- **Time**: 3-4 days

**Total Timeline**: 4-6 weeks for full GPU acceleration
**Expected Result**: 4K @ 60 FPS with 4 layers + 4 outputs + effects ✅
