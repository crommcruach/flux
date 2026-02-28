/**
 * DMX 3D Visualizer - Core Engine
 * Using Three.js for WebGL rendering
 */

class DMXVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.fixtures = [];
        this.selectedFixture = null;
        
        // Stage dimensions
        this.stageWidth = 10;
        this.stageDepth = 10;
        this.stageHeight = 4; // Room height
        
        // Visualization options
        this.showGrid = true;
        this.showBeams = true;
        this.showLabels = true;
        
        // Performance tracking
        this.frameCount = 0;
        this.lastTime = performance.now();
        this.fps = 60;
        this.lastFrameTime = 0;
        
        // Video element for video wall
        this.videoElement = null;
        this.videoTexture = null;
        
        this.init();
        this.animate();
    }
    
    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0a);
        this.scene.fog = new THREE.Fog(0x0a0a0a, 20, 100);
        
        // Camera setup
        const aspect = this.canvas.clientWidth / this.canvas.clientHeight;
        this.camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
        this.camera.position.set(8, 8, 8);
        this.camera.lookAt(0, 0, 0);
        
        // Renderer setup
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: true,
            alpha: false
        });
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // Post-processing for bloom effect
        this.composer = new EffectComposer(this.renderer);
        const renderPass = new RenderPass(this.scene, this.camera);
        this.composer.addPass(renderPass);
        
        // Bloom pass for glowing beams (strength, radius, threshold)
        this.bloomPass = new UnrealBloomPass(
            new THREE.Vector2(this.canvas.clientWidth, this.canvas.clientHeight),
            0.8,  // strength - subtle bloom
            0.4,  // radius
            0.85  // threshold - only bright objects bloom
        );
        this.composer.addPass(this.bloomPass);
        
        // God rays pass for volumetric lighting effect (disabled)
        // this.godRaysPass = this.createGodRaysPass();
        // this.composer.addPass(this.godRaysPass);
        
        // Track light sources for god rays
        this.lightSources = [];
        
        // Create noise texture for volumetric beam effect
        this.beamNoiseTexture = this.createNoiseTexture(512);
        
        // Orbit controls
        this.controls = new OrbitControls(this.camera, this.canvas);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.maxPolarAngle = Math.PI / 2; // Prevent going below ground
        
        // Disable OrbitControls built-in zoom to use custom handler
        this.controls.enableZoom = false;
        this.controls.panSpeed = 0.8;
        this.controls.rotateSpeed = 0.5;
        
        // Custom wheel handler for smooth, gradual zoom
        this.canvas.addEventListener('wheel', (event) => {
            event.preventDefault();
            event.stopPropagation();
            
            const delta = Math.sign(event.deltaY); // Normalize to -1 or 1
            const zoomStep = 0.95; // 5% change per scroll tick
            
            const direction = this.camera.position.clone().sub(this.controls.target).normalize();
            const currentDistance = this.camera.position.distanceTo(this.controls.target);
            
            // Zoom in (delta > 0) or out (delta < 0)
            const newDistance = delta > 0 
                ? currentDistance * zoomStep 
                : currentDistance / zoomStep;
            
            // Clamp to min/max
            const clampedDistance = THREE.MathUtils.clamp(newDistance, 2, 50);
            
            // Update camera position
            const offset = direction.multiplyScalar(clampedDistance);
            this.camera.position.copy(this.controls.target).add(offset);
        }, { passive: false });
        
        // Lights
        this.setupLights();
        
        // Stage
        this.setupStage();
        
        // Raycaster for selection
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        
        // Transform controls for moving fixtures
        this.transformControls = new TransformControls(this.camera, this.canvas);
        this.transformControls.addEventListener('change', () => this.onTransformChange());
        this.transformControls.addEventListener('dragging-changed', (event) => {
            this.controls.enabled = !event.value; // Disable orbit controls while dragging
        });
        this.scene.add(this.transformControls);
        
        // Event listeners
        this.canvas.addEventListener('click', (e) => this.onMouseClick(e));
        window.addEventListener('resize', () => this.onWindowResize());
        window.addEventListener('keydown', (e) => this.onKeyDown(e));
    }
    
    setupLights() {
        // Ambient light
        const ambient = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambient);
        
        // Main directional light
        const directional = new THREE.DirectionalLight(0xffffff, 0.8);
        directional.position.set(5, 10, 5);
        directional.castShadow = true;
        directional.shadow.camera.left = -20;
        directional.shadow.camera.right = 20;
        directional.shadow.camera.top = 20;
        directional.shadow.camera.bottom = -20;
        directional.shadow.mapSize.width = 2048;
        directional.shadow.mapSize.height = 2048;
        this.scene.add(directional);
        
        // Fill light
        const fill = new THREE.DirectionalLight(0x4488ff, 0.3);
        fill.position.set(-5, 5, -5);
        this.scene.add(fill);
    }
    
    createGodRaysPass() {
        // Custom shader for volumetric god rays effect
        const GodRaysShader = {
            uniforms: {
                'tDiffuse': { value: null },
                'lightPositions': { value: [] },
                'lightColors': { value: [] },
                'exposure': { value: 0.3 },
                'decay': { value: 0.95 },
                'density': { value: 0.6 },
                'weight': { value: 0.4 }
            },
            vertexShader: `
                varying vec2 vUv;
                void main() {
                    vUv = uv;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform sampler2D tDiffuse;
                uniform vec2 lightPositions[10];
                uniform vec3 lightColors[10];
                uniform float exposure;
                uniform float decay;
                uniform float density;
                uniform float weight;
                
                varying vec2 vUv;
                
                const int NUM_SAMPLES = 40;
                
                void main() {
                    vec4 color = texture2D(tDiffuse, vUv);
                    vec3 godRays = vec3(0.0);
                    
                    // Apply god rays from each light source
                    for (int i = 0; i < 10; i++) {
                        vec2 lightPos = lightPositions[i];
                        
                        // Skip invalid lights
                        if (lightPos.x < -99.0) continue;
                        
                        vec2 deltaTexCoord = (vUv - lightPos) * density / float(NUM_SAMPLES);
                        vec2 coord = vUv;
                        float illuminationDecay = 1.0;
                        
                        // Ray marching from pixel to light source
                        for (int s = 0; s < NUM_SAMPLES; s++) {
                            coord -= deltaTexCoord;
                            vec4 sampleColor = texture2D(tDiffuse, coord);
                            sampleColor *= illuminationDecay * weight;
                            godRays += sampleColor.rgb * lightColors[i];
                            illuminationDecay *= decay;
                        }
                    }
                    
                    gl_FragColor = vec4(color.rgb + godRays * exposure, color.a);
                }
            `
        };
        
        return new ShaderPass(GodRaysShader);
    }
    
    createNoiseTexture(size = 512) {
        // Generate Perlin-like noise texture for beam volumetric effect
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        const imageData = ctx.createImageData(size, size);
        
        // Simple noise generation
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const i = (y * size + x) * 4;
                // Multi-octave noise
                let value = 0;
                let scale = 1;
                let amplitude = 1;
                
                for (let octave = 0; octave < 4; octave++) {
                    value += this.simpleNoise(x * scale / size, y * scale / size) * amplitude;
                    scale *= 2;
                    amplitude *= 0.5;
                }
                
                // Normalize to 0-255
                const normalized = Math.floor(((value + 1) * 0.5) * 255);
                imageData.data[i] = normalized;
                imageData.data[i + 1] = normalized;
                imageData.data[i + 2] = normalized;
                imageData.data[i + 3] = 255;
            }
        }
        
        ctx.putImageData(imageData, 0, 0);
        
        const texture = new THREE.CanvasTexture(canvas);
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        texture.needsUpdate = true;
        
        return texture;
    }
    
    simpleNoise(x, y) {
        // Simple pseudo-random noise function
        const n = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
        return (n - Math.floor(n)) * 2 - 1;
    }
    
    createVolumetricBeamMaterial(color, noiseTexture) {
        // Custom shader material for volumetric beam with vertex-based fog
        return new THREE.ShaderMaterial({
            uniforms: {
                color: { value: new THREE.Color(color) },
                noiseTexture: { value: noiseTexture },
                time: { value: 0 },
                opacity: { value: 0.4 },
                glowIntensity: { value: 1.5 },
                fogDensity: { value: 0.8 }
            },
            vertexShader: `
                varying vec2 vUv;
                varying vec3 vPosition;
                varying vec3 vNormal;
                varying float vDistanceFromCenter;
                
                void main() {
                    vUv = uv;
                    vPosition = position;
                    vNormal = normalize(normalMatrix * normal);
                    
                    // Calculate distance from beam center axis for fog effect
                    // For cone: distance in XZ plane from Y axis
                    vDistanceFromCenter = length(position.xz);
                    
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 color;
                uniform sampler2D noiseTexture;
                uniform float time;
                uniform float opacity;
                uniform float glowIntensity;
                uniform float fogDensity;
                
                varying vec2 vUv;
                varying vec3 vPosition;
                varying vec3 vNormal;
                varying float vDistanceFromCenter;
                
                void main() {
                    // Sample animated noise
                    vec2 scrollUv = vUv + vec2(0.0, time);
                    float noise = texture2D(noiseTexture, scrollUv).r;
                    
                    // Distance-based fog (brighter at center, fades to edges)
                    float centerGlow = 1.0 - smoothstep(0.0, 1.0, vDistanceFromCenter);
                    
                    // Vertex color fade (from geometry)
                    float fadeFactor = smoothstep(-0.5, 0.5, vPosition.y);
                    
                    // Combine effects
                    float volumetricDensity = noise * fogDensity * centerGlow * fadeFactor;
                    float finalAlpha = opacity * (0.3 + volumetricDensity * 0.7);
                    
                    // Rim lighting effect
                    vec3 viewDir = normalize(cameraPosition - vPosition);
                    float rimPower = 1.0 - abs(dot(viewDir, vNormal));
                    rimPower = pow(rimPower, 2.0);
                    
                    // Final color with glow
                    vec3 finalColor = color * (1.0 + rimPower * glowIntensity);
                    
                    gl_FragColor = vec4(finalColor, finalAlpha);
                }
            `,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });
    }
    
    createGoboTexture(imagePath = 'gobotest.png') {
        // Load gobo texture from image file
        const textureLoader = new THREE.TextureLoader();
        const texture = textureLoader.load(
            imagePath,
            // onLoad,
            () => {
                console.log('Gobo texture loaded:', imagePath);
            },
            // onProgress
            undefined,
            // onError
            (err) => {
                console.error('Error loading gobo texture:', err);
            }
        );
        
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.center = new THREE.Vector2(0.5, 0.5);
        return texture;
    }
    
    setupStage() {
        // Remove existing stage if any
        if (this.stageGroup) {
            this.scene.remove(this.stageGroup);
        }
        
        this.stageGroup = new THREE.Group();
        
        // Floor
        const floorGeometry = new THREE.PlaneGeometry(this.stageWidth, this.stageDepth);
        const floorMaterial = new THREE.MeshStandardMaterial({
            color: 0x222222,
            roughness: 0.8,
            metalness: 0.2
        });
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        floor.name = 'floor';
        this.floor = floor;
        this.stageGroup.add(floor);
        
        // Grid
        if (this.showGrid) {
            const gridHelper = new THREE.GridHelper(
                Math.max(this.stageWidth, this.stageDepth),
                20,
                0x00aaff,
                0x333333
            );
            gridHelper.position.y = 0.01; // Slightly above floor
            this.stageGroup.add(gridHelper);
        }
        
        // Room walls
        const wallMaterial = new THREE.MeshStandardMaterial({
            color: 0x808080, // Grey
            roughness: 0.9,
            metalness: 0.1,
            side: THREE.DoubleSide // Render both sides
        });
        
        // Back wall (negative Z)
        const backWall = new THREE.Mesh(
            new THREE.PlaneGeometry(this.stageWidth, this.stageHeight),
            wallMaterial
        );
        backWall.position.z = -this.stageDepth / 2;
        backWall.position.y = this.stageHeight / 2;
        backWall.receiveShadow = true;
        backWall.name = 'backWall';
        this.backWall = backWall;
        this.stageGroup.add(backWall);
        
        // Front wall (positive Z)
        const frontWall = new THREE.Mesh(
            new THREE.PlaneGeometry(this.stageWidth, this.stageHeight),
            wallMaterial
        );
        frontWall.position.z = this.stageDepth / 2;
        frontWall.position.y = this.stageHeight / 2;
        frontWall.rotation.y = Math.PI;
        frontWall.receiveShadow = true;
        frontWall.name = 'frontWall';
        this.frontWall = frontWall;
        this.stageGroup.add(frontWall);
        
        // Left wall (negative X)
        const leftWall = new THREE.Mesh(
            new THREE.PlaneGeometry(this.stageDepth, this.stageHeight),
            wallMaterial
        );
        leftWall.position.x = -this.stageWidth / 2;
        leftWall.position.y = this.stageHeight / 2;
        leftWall.rotation.y = Math.PI / 2;
        leftWall.receiveShadow = true;
        leftWall.name = 'leftWall';
        this.leftWall = leftWall;
        this.stageGroup.add(leftWall);
        
        // Right wall (positive X)
        const rightWall = new THREE.Mesh(
            new THREE.PlaneGeometry(this.stageDepth, this.stageHeight),
            wallMaterial
        );
        rightWall.position.x = this.stageWidth / 2;
        rightWall.position.y = this.stageHeight / 2;
        rightWall.rotation.y = -Math.PI / 2;
        rightWall.receiveShadow = true;
        rightWall.name = 'rightWall';
        this.rightWall = rightWall;
        this.stageGroup.add(rightWall);
        
        // Ceiling
        const ceiling = new THREE.Mesh(
            new THREE.PlaneGeometry(this.stageWidth, this.stageDepth),
            wallMaterial
        );
        ceiling.position.y = this.stageHeight;
        ceiling.rotation.x = Math.PI / 2;
        ceiling.receiveShadow = true;
        ceiling.name = 'ceiling';
        this.ceiling = ceiling;
        this.stageGroup.add(ceiling);
        
        // Axes helper (optional)
        const axesHelper = new THREE.AxesHelper(2);
        this.stageGroup.add(axesHelper);
        
        this.scene.add(this.stageGroup);
    }
    
    addFixture(type = 'moving_head', position = null) {
        const fixtureType = type || document.getElementById('fixtureType').value;
        
        // Random position if not specified
        if (!position) {
            position = {
                x: (Math.random() - 0.5) * (this.stageWidth - 2),
                y: 0,
                z: (Math.random() - 0.5) * (this.stageDepth - 2)
            };
        }
        
        // Create fixture based on type
        let fixture;
        switch (fixtureType) {
            case 'moving_head':
                fixture = this.createMovingHead(position);
                break;
            case 'par':
                fixture = this.createLEDPar(position);
                break;
            case 'strobe':
                fixture = this.createStrobe(position);
                break;
            case 'led_strip':
                fixture = this.createLEDStrip(position);
                break;
            case 'led_matrix':
                fixture = this.createLEDMatrix(position);
                break;
            case 'display':
                fixture = this.createDisplay(position);
                break;
            default:
                console.warn('Unknown fixture type:', fixtureType);
                return;
        }
        
        // Add to scene and tracking
        this.scene.add(fixture.group);
        this.fixtures.push(fixture);
        
        // Update UI
        this.updateFixtureCount();
        this.updateFixtureList();
        
        return fixture;
    }
    
    createMovingHead(position) {
        const group = new THREE.Group();
        group.position.set(position.x, position.y, position.z);
        
        // Base plate (cube)
        const baseGeometry = new THREE.BoxGeometry(0.6, 0.15, 0.4);
        const baseMaterial = new THREE.MeshStandardMaterial({ color: 0x1a1a1a });
        const base = new THREE.Mesh(baseGeometry, baseMaterial);
        base.position.y = 0.075; // Half height above ground
        base.castShadow = true;
        group.add(base);
        
        // Yoke (rotates for pan around base midpoint)
        const yoke = new THREE.Group();
        yoke.position.y = 0.15; // At top of base
        
        // Yoke arms (two vertical supports)
        const yokeArmGeometry = new THREE.BoxGeometry(0.08, 0.5, 0.08);
        const yokeMaterial = new THREE.MeshStandardMaterial({ color: 0x2a2a2a });
        
        const yokeArmLeft = new THREE.Mesh(yokeArmGeometry, yokeMaterial);
        yokeArmLeft.position.set(-0.25, 0.25, 0);
        yokeArmLeft.castShadow = true;
        yoke.add(yokeArmLeft);
        
        const yokeArmRight = new THREE.Mesh(yokeArmGeometry, yokeMaterial);
        yokeArmRight.position.set(0.25, 0.25, 0);
        yokeArmRight.castShadow = true;
        yoke.add(yokeArmRight);
        
        // Yoke top bar (connects arms)
        const yokeBarGeometry = new THREE.BoxGeometry(0.58, 0.08, 0.08);
        const yokeBar = new THREE.Mesh(yokeBarGeometry, yokeMaterial);
        yokeBar.position.y = 0.5;
        yokeBar.castShadow = true;
        yoke.add(yokeBar);
        
        group.add(yoke);
        
        // Head (can tilt, mounted on yoke)
        const head = new THREE.Group();
        head.position.y = 0.5; // At top of yoke arms
        
        const headGeometry = new THREE.BoxGeometry(0.4, 0.4, 0.5);
        const headMaterial = new THREE.MeshStandardMaterial({ color: 0x3a3a3a });
        const headMesh = new THREE.Mesh(headGeometry, headMaterial);
        headMesh.castShadow = true;
        head.add(headMesh);
        
        // Beam parameters (configurable)
        const beamParams = {
            length: 16,         // meters
            outletRadius: 0.05, // meters - beam radius at fixture opening (5cm)
            angle: 10,          // degrees - beam divergence angle
            goboRotation: 0,    // -100..100, rotation speed
            goboAngle: 0        // current gobo angle (radians)
        };
        
        // Calculate beam spread from angle (wide end radius)
        const beamSpread = Math.tan(THREE.MathUtils.degToRad(beamParams.angle / 2)) * beamParams.length;
        
        // Light beam (frustum/truncated cone from narrow opening to wide spread)
        const beamGeometry = new THREE.CylinderGeometry(beamParams.outletRadius, beamSpread, beamParams.length, 64, 1, true); // 64 segments for smooth appearance
        
        // Add vertex colors for fade effect (darker at wide end)
        const colors = [];
        const positionAttribute = beamGeometry.attributes.position;
        for (let i = 0; i < positionAttribute.count; i++) {
            const y = positionAttribute.getY(i);
            const alpha = (y + beamParams.length / 2) / beamParams.length; // Fade from 0 (wide end) to 1 (narrow end)
            colors.push(alpha, alpha, alpha);
        }
        beamGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        
        const beamMaterial = new THREE.MeshBasicMaterial({
            color: 0xffff00,
            transparent: true,
            opacity: 0.35,
            side: THREE.DoubleSide,
            vertexColors: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            map: this.beamNoiseTexture
        });
        // Animated texture scrolling for dynamic volumetric feel
        beamMaterial.map.repeat.set(2, 4);
        beamMaterial.userData.scrollSpeed = 0.15;
        
        const beam = new THREE.Mesh(beamGeometry, beamMaterial);
        beam.userData.currentLength = beamParams.length; // Track for collision updates
        // Position beam so narrow end is at front face (z = 0.25), wide end extends forward
        beam.position.z = 0.25 + beamParams.length / 2; // Front of box + half beam length
        beam.rotation.x = -Math.PI / 2; // Point forward with narrow end at fixture
        beam.visible = this.showBeams;
        head.add(beam);

        // Prism beams (3-facet split)
        const prismBeams = [];
        for (let i = 0; i < 3; i++) {
            const prismBeam = new THREE.Mesh(beamGeometry.clone(), beamMaterial.clone());
            prismBeam.userData.currentLength = beamParams.length;
            prismBeam.visible = false;
            head.add(prismBeam);
            prismBeams.push(prismBeam);
        }
        
        // Beam start disc (shows beam origin, matches beam color)
        const beamStartGeometry = new THREE.CircleGeometry(beamParams.outletRadius, 32);
        const beamStartMaterial = new THREE.MeshBasicMaterial({
            color: 0xffff00,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide
        });
        const beamStartDisc = new THREE.Mesh(beamStartGeometry, beamStartMaterial);
        beamStartDisc.position.z = 0.25;
        head.add(beamStartDisc);
        
        // Spot light at front of moving head with gobo (increased intensity for brighter gobo)
        // Calculate angle to precisely match beam cone size on surfaces
        // Spotlight angle in Three.js is the full cone angle from axis to edge
        const halfAngle = Math.atan(beamSpread / beamParams.length);
        const beamAngle = halfAngle * 2 * 0.95; // Reduce by 5% to match actual beam cone tightly
        const light = new THREE.SpotLight(0xffffff, 5.0, beamParams.length * 1.5, beamAngle, 0.02, 0);
        light.position.z = 0.25; // At front face of moving head
        light.target.position.set(0, 0, beamParams.length + 0.25); // Target at end of beam
        light.castShadow = true;
        light.shadow.mapSize.width = 1024;
        light.shadow.mapSize.height = 1024;
        light.shadow.camera.near = 0.1;
        light.shadow.camera.far = beamParams.length * 1.5;
        light.shadow.camera.fov = THREE.MathUtils.radToDeg(beamAngle);
        
        // Add gobo texture from image file
        const goboTexture = this.createGoboTexture('gobotest.png');
        light.map = goboTexture;

        // Gobo projection planes (visual projection on surfaces)
        const goboPlaneGroup = new THREE.Group();
        const goboPlaneGeometry = new THREE.PlaneGeometry(1, 1);
        const goboPlaneMaterial = new THREE.MeshBasicMaterial({
            map: goboTexture,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide,
            depthWrite: false
        });
        const goboPlane = new THREE.Mesh(goboPlaneGeometry, goboPlaneMaterial);
        goboPlane.visible = false;
        goboPlaneGroup.add(goboPlane);

        const prismPlanes = [];
        for (let i = 0; i < 3; i++) {
            const prismPlane = new THREE.Mesh(goboPlaneGeometry, goboPlaneMaterial.clone());
            prismPlane.material.opacity = 0.85;
            prismPlane.material.color = new THREE.Color(i === 0 ? 0x00ffff : i === 1 ? 0xffaa00 : 0x00ff66);
            prismPlane.visible = false;
            prismPlanes.push(prismPlane);
            goboPlaneGroup.add(prismPlane);
        }
        this.scene.add(goboPlaneGroup);
        
        head.add(light);
        head.add(light.target);
        
        yoke.add(head);
        
        // Fixture data
        const fixture = {
            id: `fixture_${this.fixtures.length}`,
            type: 'moving_head',
            name: `Moving Head ${this.fixtures.length + 1}`,
            group: group,
            yoke: yoke,
            head: head,
            beam: beam,
            prismBeams: prismBeams,
            beamStartDisc: beamStartDisc,
            light: light,
            goboPlaneGroup: goboPlaneGroup,
            goboPlane: goboPlane,
            prismPlanes: prismPlanes,
            beamParams: beamParams,  // Store beam parameters for updates
            dmx: {
                pan: 127,
                tilt: 127,
                dimmer: 255,
                color: { r: 255, g: 255, b: 255 }
            }
        };
        
        // Store reference for raycasting
        group.userData.fixture = fixture;
        
        return fixture;
    }
    
    createLEDPar(position) {
        const group = new THREE.Group();
        group.position.set(position.x, position.y + 0.2, position.z);
        
        // Par can body
        const bodyGeometry = new THREE.CylinderGeometry(0.2, 0.25, 0.3, 16);
        const bodyMaterial = new THREE.MeshStandardMaterial({ color: 0x1a1a1a });
        const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
        body.castShadow = true;
        group.add(body);
        
        // White lens/front at exit point (bottom of PAR)
        const lensGeometry = new THREE.CircleGeometry(0.2, 16);
        const lensMaterial = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide
        });
        const lens = new THREE.Mesh(lensGeometry, lensMaterial);
        lens.position.y = -0.16; // Slightly below bottom of PAR to prevent clipping
        lens.rotation.x = Math.PI / 2; // Face downward
        group.add(lens);
        
        // Beam parameters (configurable)
        const beamParams = {
            length: 6,          // meters
            outletRadius: 0.1,  // meters - beam radius at fixture opening (10cm)
            angle: 20           // degrees - beam divergence angle
        };
        
        // Calculate beam end radius from angle
        const beamEndRadius = Math.tan(THREE.MathUtils.degToRad(beamParams.angle / 2)) * beamParams.length;
        
        // Light beam (wider cone, starts at bottom of PAR with wider opening)
        const beamGeometry = new THREE.CylinderGeometry(beamParams.outletRadius, beamEndRadius, beamParams.length, 64, 1, true); // 64 segments for smooth appearance
        
        // Add vertex colors for fade effect (darker at wide end)
        const colors = [];
        const positionAttribute = beamGeometry.attributes.position;
        for (let i = 0; i < positionAttribute.count; i++) {
            const y = positionAttribute.getY(i);
            const alpha = (y + beamParams.length / 2) / beamParams.length; // Fade from 0 (wide end) to 1 (narrow end)
            colors.push(alpha, alpha, alpha);
        }
        beamGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        
        const beamMaterial = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.25,
            side: THREE.DoubleSide,
            vertexColors: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            map: this.beamNoiseTexture
        });
        // Animated texture scrolling for dynamic volumetric feel
        beamMaterial.map.repeat.set(1.5, 3);
        beamMaterial.userData.scrollSpeed = 0.1;
        
        const beam = new THREE.Mesh(beamGeometry, beamMaterial);
        beam.userData.currentLength = beamParams.length; // Track for collision updates
        // Position beam so narrow end is at bottom of PAR (y = -0.15), wide end extends downward
        beam.position.y = -0.15 - beamParams.length / 2; // Bottom of PAR + half beam length
        // No rotation needed - cone naturally points downward in this orientation
        beam.visible = this.showBeams;
        group.add(beam);
        
        // Point light at bottom of PAR (intensity boosted 30% for brighter wall spots)
        const light = new THREE.PointLight(0xffffff, 1.3, 5);
        light.position.y = -0.15; // At bottom of PAR can
        light.castShadow = true;
        group.add(light);
        
        const fixture = {
            id: `fixture_${this.fixtures.length}`,
            type: 'par',
            name: `LED PAR ${this.fixtures.length + 1}`,
            group: group,
            beam: beam,
            beamStartDisc: lens,
            light: light,
            beamParams: beamParams,  // Store beam parameters for updates
            dmx: {
                dimmer: 255,
                color: { r: 255, g: 255, b: 255 }
            }
        };
        
        group.userData.fixture = fixture;
        return fixture;
    }
    
    createStrobe(position) {
        const group = new THREE.Group();
        group.position.set(position.x, position.y + 0.5, position.z);
        
        // Strobe housing
        const housingGeometry = new THREE.BoxGeometry(0.6, 0.2, 0.3);
        const housingMaterial = new THREE.MeshStandardMaterial({ color: 0x1a1a1a });
        const housing = new THREE.Mesh(housingGeometry, housingMaterial);
        housing.castShadow = true;
        group.add(housing);
        
        // Strobe lights (multiple)
        const lightGroup = new THREE.Group();
        for (let i = 0; i < 4; i++) {
            const light = new THREE.PointLight(0xffffff, 0, 3);
            light.position.x = (i - 1.5) * 0.15;
            lightGroup.add(light);
        }
        group.add(lightGroup);
        
        const fixture = {
            id: `fixture_${this.fixtures.length}`,
            type: 'strobe',
            name: `Strobe ${this.fixtures.length + 1}`,
            group: group,
            lights: lightGroup,
            dmx: {
                dimmer: 0,
                rate: 0
            }
        };
        
        group.userData.fixture = fixture;
        return fixture;
    }
    
    createLEDStrip(position) {
        const group = new THREE.Group();
        group.position.set(position.x, position.y + 0.1, position.z);
        
        const pixelCount = 50;
        const spacing = 0.05;
        const pixels = [];
        
        // Create backing case
        const caseWidth = pixelCount * spacing + 0.1;
        const caseHeight = 0.1;
        const caseDepth = 0.05;
        const caseGeometry = new THREE.BoxGeometry(caseWidth, caseHeight, caseDepth);
        const caseMaterial = new THREE.MeshStandardMaterial({ color: 0x1a1a1a });
        const caseBox = new THREE.Mesh(caseGeometry, caseMaterial);
        caseBox.position.z = -0.025; // Behind pixels
        caseBox.castShadow = true;
        group.add(caseBox);
        
        for (let i = 0; i < pixelCount; i++) {
            const pixelGeometry = new THREE.SphereGeometry(0.02, 8, 8);
            const pixelMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });
            const pixel = new THREE.Mesh(pixelGeometry, pixelMaterial);
            pixel.position.x = (i - pixelCount / 2) * spacing;
            group.add(pixel);
            pixels.push(pixel);
        }
        
        const fixture = {
            id: `fixture_${this.fixtures.length}`,
            type: 'led_strip',
            name: `LED Strip ${this.fixtures.length + 1}`,
            group: group,
            pixels: pixels,
            dmx: {
                colors: Array(pixelCount).fill({ r: 255, g: 255, b: 255 })
            }
        };
        
        group.userData.fixture = fixture;
        return fixture;
    }
    
    createLEDMatrix(position) {
        const group = new THREE.Group();
        group.position.set(position.x, position.y + 1, position.z);
        
        const rows = 16;
        const cols = 16;
        const pixelSize = 0.03;
        const spacing = 0.04;
        const pixels = [];
        
        // Create backing panel
        const panelWidth = cols * spacing;
        const panelHeight = rows * spacing;
        const panelGeometry = new THREE.PlaneGeometry(panelWidth, panelHeight);
        const panelMaterial = new THREE.MeshStandardMaterial({ color: 0x0a0a0a });
        const panel = new THREE.Mesh(panelGeometry, panelMaterial);
        panel.position.z = -0.01; // Behind pixels
        group.add(panel);
        
        // Create 2D grid of LED pixels
        for (let row = 0; row < rows; row++) {
            pixels[row] = [];
            for (let col = 0; col < cols; col++) {
                const pixelGeometry = new THREE.BoxGeometry(pixelSize, pixelSize, pixelSize);
                const pixelMaterial = new THREE.MeshBasicMaterial({ 
                    color: 0x000000,
                    emissive: 0x000000,
                    emissiveIntensity: 1
                });
                const pixel = new THREE.Mesh(pixelGeometry, pixelMaterial);
                
                // Position in grid (centered)
                pixel.position.x = (col - cols / 2 + 0.5) * spacing;
                pixel.position.y = (row - rows / 2 + 0.5) * spacing;
                pixel.position.z = 0;
                
                group.add(pixel);
                pixels[row][col] = pixel;
            }
        }
        
        const fixture = {
            id: `fixture_${this.fixtures.length}`,
            type: 'led_matrix',
            name: `LED Matrix ${this.fixtures.length + 1}`,
            group: group,
            pixels: pixels,
            rows: rows,
            cols: cols,
            dmx: {
                colors: Array(rows).fill(null).map(() => 
                    Array(cols).fill({ r: 0, g: 0, b: 0 })
                )
            }
        };
        
        group.userData.fixture = fixture;
        return fixture;
    }
    
    createDisplay(position) {
        const group = new THREE.Group();
        group.position.set(position.x, position.y + 1, position.z);
        
        // Create video element if not exists
        if (!this.videoElement) {
            this.videoElement = document.createElement('video');
            this.videoElement.crossOrigin = 'anonymous';
            this.videoElement.src = '/video/kanal_3/test.mp4';
            this.videoElement.loop = true;
            this.videoElement.muted = true;
            this.videoElement.playsInline = true;
            
            this.videoElement.play().catch(e => console.log('Video autoplay prevented:', e));
            
            // Create video texture
            this.videoTexture = new THREE.VideoTexture(this.videoElement);
            this.videoTexture.minFilter = THREE.LinearFilter;
            this.videoTexture.magFilter = THREE.LinearFilter;
        }
        
        // Display screen with video texture
        const screenGeometry = new THREE.PlaneGeometry(1.6, 0.9); // 16:9 aspect
        const screenMaterial = new THREE.MeshBasicMaterial({
            map: this.videoTexture,
            side: THREE.DoubleSide
        });
        const screen = new THREE.Mesh(screenGeometry, screenMaterial);
        screen.position.z = 0.001; // Slightly forward to prevent z-fighting
        screen.castShadow = true;
        group.add(screen);
        
        // Frame
        const frameGeometry = new THREE.BoxGeometry(1.7, 1.0, 0.05);
        const frameMaterial = new THREE.MeshStandardMaterial({ color: 0x1a1a1a });
        const frame = new THREE.Mesh(frameGeometry, frameMaterial);
        frame.position.z = -0.025;
        group.add(frame);
        
        const fixture = {
            id: `fixture_${this.fixtures.length}`,
            type: 'display',
            name: `Display ${this.fixtures.length + 1}`,
            group: group,
            screen: screen,
            dmx: {
                active: true
            }
        };
        
        group.userData.fixture = fixture;
        return fixture;
    }
    
    updateFixture(fixture, dmxData) {
        if (!fixture) return;
        
        // Update fixture DMX data
        Object.assign(fixture.dmx, dmxData);
        
        switch (fixture.type) {
            case 'moving_head':
                this.updateMovingHead(fixture);
                break;
            case 'par':
                this.updatePar(fixture);
                break;
            case 'strobe':
                this.updateStrobe(fixture);
                break;
            case 'led_strip':
                this.updateLEDStrip(fixture);
                break;
        }
    }
    
    updateMovingHead(fixture) {
        const { pan, tilt, dimmer, color } = fixture.dmx;
        
        // Pan: Rotate yoke around Y axis (0-255 = -180 to +180 degrees)
        const panRad = ((pan - 127) / 127) * Math.PI;
        fixture.yoke.rotation.y = panRad;
        
        // Tilt: Rotate head around X axis (-90 to +90 degrees)
        const tiltRad = ((tilt - 127) / 127) * (Math.PI / 2);
        fixture.head.rotation.x = -tiltRad;
        
        // Dimmer
        const intensity = dimmer / 255;
        fixture.light.intensity = intensity * 2;
        this.applyBeamOpacity(fixture, intensity);
        
        // Color
        const colorValue = new THREE.Color(
            color.r / 255,
            color.g / 255,
            color.b / 255
        );
        fixture.light.color = colorValue;
        fixture.beam.material.color = colorValue;
        if (fixture.prismBeams) {
            fixture.prismBeams.forEach(prismBeam => {
                prismBeam.material.color = colorValue;
            });
        }
        if (fixture.beamStartDisc) {
            fixture.beamStartDisc.material.color = colorValue;
            fixture.beamStartDisc.material.opacity = Math.min(1, 0.3 + intensity * 0.7);
        }

        this.updatePrismBeams(fixture);
    }
    
    updatePar(fixture) {
        const { dimmer, color } = fixture.dmx;
        
        // Dimmer
        const intensity = dimmer / 255;
        fixture.light.intensity = intensity;
        this.applyBeamOpacity(fixture, intensity);
        
        // Color
        const colorValue = new THREE.Color(
            color.r / 255,
            color.g / 255,
            color.b / 255
        );
        fixture.light.color = colorValue;
        fixture.beam.material.color = colorValue;
        if (fixture.beamStartDisc) {
            fixture.beamStartDisc.material.color = colorValue;
            fixture.beamStartDisc.material.opacity = Math.min(1, 0.3 + intensity * 0.7);
        }
    }
    
    updateStrobe(fixture) {
        // Simple strobe effect (would be more complex in real implementation)
        const { dimmer } = fixture.dmx;
        const active = dimmer > 0;
        
        fixture.lights.children.forEach(light => {
            light.intensity = active ? 2 : 0;
        });
    }
    
    updateLEDStrip(fixture) {
        const { colors } = fixture.dmx;
        
        fixture.pixels.forEach((pixel, i) => {
            if (colors[i]) {
                const color = new THREE.Color(
                    colors[i].r / 255,
                    colors[i].g / 255,
                    colors[i].b / 255
                );
                pixel.material.color = color;
            }
        });
    }

    applyBeamOpacity(fixture, intensity) {
        if (!fixture.beam || !fixture.beamParams) return;
        const angle = fixture.beamParams.angle || 0;
        const angleFactor = THREE.MathUtils.clamp(angle / 60, 0, 1);
        const baseOpacity = fixture.type === 'par' ? 0.26 : 0.3;
        const minFactor = fixture.type === 'par' ? 0.25 : 0.55;
        const diffusedFactor = THREE.MathUtils.lerp(1, minFactor, angleFactor);
        const opacity = intensity * baseOpacity * diffusedFactor;
        fixture.beam.material.opacity = opacity;
        if (fixture.prismBeams) {
            fixture.prismBeams.forEach(prismBeam => {
                prismBeam.material.opacity = opacity;
            });
        }
    }

    updatePrismBeams(fixture) {
        if (!fixture || fixture.type !== 'moving_head' || !fixture.prismBeams) return;
        const enabled = fixture.beamParams?.prismEnabled === true;
        const showBeams = this.showBeams === true;
        fixture.beam.visible = showBeams && !enabled;
        if (fixture.beamStartDisc) {
            fixture.beamStartDisc.visible = showBeams && !enabled;
        }

        if (!enabled) {
            fixture.prismBeams.forEach(prismBeam => { prismBeam.visible = false; });
            return;
        }

        const params = fixture.beamParams;
        const spreadAngle = Math.atan((params.prismSpread ?? 0.15) / Math.max(params.length, 0.01));
        const minAngle = THREE.MathUtils.degToRad(1.5);
        const offsetAngle = Math.max(spreadAngle, minAngle);
        const forwardDistance = 0.25 + params.length / 2;
        const upAxis = new THREE.Vector3(0, 1, 0);

        for (let i = 0; i < fixture.prismBeams.length; i++) {
            const azimuth = (i / fixture.prismBeams.length) * Math.PI * 2;
            const dir = new THREE.Vector3(
                Math.sin(offsetAngle) * Math.cos(azimuth),
                Math.sin(offsetAngle) * Math.sin(azimuth),
                Math.cos(offsetAngle)
            ).normalize();
            const prismBeam = fixture.prismBeams[i];
            prismBeam.visible = showBeams;
            prismBeam.position.copy(dir.clone().multiplyScalar(forwardDistance));
            prismBeam.quaternion.setFromUnitVectors(upAxis, dir);
        }
    }
    
    updateTestFixture(param, value) {
        // Update first fixture for testing
        if (this.fixtures.length === 0) return;
        
        const fixture = this.fixtures[0];
        
        if (param === 'pan') {
            fixture.dmx.pan = parseInt(value);
            document.getElementById('panValue').textContent = value;
        } else if (param === 'tilt') {
            fixture.dmx.tilt = parseInt(value);
            document.getElementById('tiltValue').textContent = value;
        } else if (param === 'dimmer') {
            fixture.dmx.dimmer = parseInt(value);
            document.getElementById('dimmerValue').textContent = value;
        } else if (param === 'color') {
            const color = this.hexToRgb(value);
            fixture.dmx.color = color;
        }
        
        this.updateFixture(fixture, fixture.dmx);
    }
    
    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : { r: 255, g: 255, b: 255 };
    }
    
    setCameraView(view) {
        const distance = 10;
        
        switch (view) {
            case 'top':
                this.camera.position.set(0, distance, 0);
                this.camera.lookAt(0, 0, 0);
                break;
            case 'front':
                this.camera.position.set(0, distance / 2, distance);
                this.camera.lookAt(0, 0, 0);
                break;
            case 'side':
                this.camera.position.set(distance, distance / 2, 0);
                this.camera.lookAt(0, 0, 0);
                break;
            case 'perspective':
            default:
                this.camera.position.set(8, 8, 8);
                this.camera.lookAt(0, 0, 0);
                break;
        }
        
        this.controls.update();
    }
    
    updateBeamCollisions() {
        if (!this.stageGroup) return;
        
        // Create array of room surfaces for raycasting
        const roomSurfaces = [];
        if (this.floor) roomSurfaces.push(this.floor);
        if (this.ceiling) roomSurfaces.push(this.ceiling);
        if (this.backWall) roomSurfaces.push(this.backWall);
        if (this.frontWall) roomSurfaces.push(this.frontWall);
        if (this.leftWall) roomSurfaces.push(this.leftWall);
        if (this.rightWall) roomSurfaces.push(this.rightWall);
        
        // Update each fixture's beam
        this.fixtures.forEach(fixture => {
            if (!fixture.beam || !fixture.light || !fixture.beamParams) return;
            
            const maxBeamLength = fixture.beamParams.length;
            const beamSpread = fixture.type === 'moving_head' 
                ? Math.tan(THREE.MathUtils.degToRad(fixture.beamParams.angle / 2)) * maxBeamLength
                : Math.tan(THREE.MathUtils.degToRad(fixture.beamParams.angle / 2)) * maxBeamLength;
            
            // Get beam world position and direction
            const beamWorldPos = new THREE.Vector3();
            const beamWorldDir = new THREE.Vector3();
            
            if (fixture.type === 'moving_head') {
                // Moving head beam follows head forward axis
                fixture.head.getWorldPosition(beamWorldPos);
                fixture.head.getWorldDirection(beamWorldDir);
                // Offset to the front face along the beam direction
                beamWorldPos.add(beamWorldDir.clone().multiplyScalar(0.25));
            } else if (fixture.type === 'par') {
                // PAR beam points downward
                fixture.group.getWorldPosition(beamWorldPos);
                beamWorldPos.y -= 0.15; // Bottom of PAR
                beamWorldDir.set(0, -1, 0); // Straight down
            }
            
            // Cast ray to find intersection
            const raycaster = new THREE.Raycaster(beamWorldPos, beamWorldDir, 0, maxBeamLength);
            const intersects = raycaster.intersectObjects(roomSurfaces, false);
            
            let actualBeamLength = maxBeamLength;
            let hitPoint = null;
            let hitNormal = null;
            if (intersects.length > 0) {
                actualBeamLength = Math.min(intersects[0].distance, maxBeamLength);
                hitPoint = intersects[0].point;
                const normal = intersects[0].face?.normal;
                if (normal) {
                    const normalMatrix = new THREE.Matrix3().getNormalMatrix(intersects[0].object.matrixWorld);
                    hitNormal = normal.clone().applyMatrix3(normalMatrix).normalize();
                }
            }
            if (!hitNormal && hitPoint) {
                hitNormal = beamWorldDir.clone().negate();
            }
            
            // Update light target to match beam direction and hit point
            if (fixture.type === 'moving_head' && fixture.light && fixture.light.target) {
                if (hitPoint) {
                    // Point light at intersection
                    fixture.light.target.position.copy(fixture.head.worldToLocal(hitPoint.clone()));
                } else {
                    // Point along beam direction
                    const targetPos = beamWorldDir.clone().multiplyScalar(actualBeamLength);
                    fixture.light.target.position.copy(fixture.head.worldToLocal(beamWorldPos.clone().add(targetPos)));
                }
                fixture.light.distance = actualBeamLength * 1.5;
                
                // Calculate actual beam radius at intersection distance
                const actualSpreadAtHit = beamSpread * (actualBeamLength / maxBeamLength);
                // Calculate spotlight angle to match this radius at the hit distance
                // SpotLight.angle is the half-angle from axis to edge, not full cone angle
                const actualAngle = Math.atan(actualSpreadAtHit / actualBeamLength);
                fixture.light.angle = actualAngle;
                fixture.light.penumbra = 0.02;
            }

            if (fixture.type === 'moving_head' && fixture.goboPlane) {
                if (hitPoint && hitNormal) {
                    const actualSpreadAtHit = beamSpread * (actualBeamLength / maxBeamLength);
                    const diameter = Math.max(0.01, actualSpreadAtHit * 2);
                    const planePos = hitPoint.clone().add(hitNormal.clone().multiplyScalar(0.005));
                    const baseRotation = fixture.beamParams.goboAngle ?? 0;

                    const prismEnabled = fixture.beamParams.prismEnabled === true;
                    if (prismEnabled && fixture.prismPlanes?.length === 3) {
                        fixture.goboPlane.visible = false;
                        const spread = Math.max(fixture.beamParams.prismSpread ?? 0.15, diameter * 1.2);
                        const up = Math.abs(hitNormal.y) < 0.99 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
                        const tangent = new THREE.Vector3().crossVectors(hitNormal, up).normalize();
                        const bitangent = new THREE.Vector3().crossVectors(hitNormal, tangent).normalize();

                        for (let i = 0; i < 3; i++) {
                            const angle = (i / 3) * Math.PI * 2;
                            const offset = tangent.clone().multiplyScalar(Math.cos(angle) * spread)
                                .add(bitangent.clone().multiplyScalar(Math.sin(angle) * spread));
                            const plane = fixture.prismPlanes[i];
                            plane.visible = true;
                            plane.position.copy(planePos)
                                .add(offset)
                                .add(hitNormal.clone().multiplyScalar(0.002));
                            plane.scale.set(diameter * 0.9, diameter * 0.9, 1);
                            plane.lookAt(planePos.clone().add(hitNormal));
                            plane.rotation.z = baseRotation;
                        }
                    } else {
                        if (fixture.prismPlanes) {
                            fixture.prismPlanes.forEach(plane => { plane.visible = false; });
                        }
                        fixture.goboPlane.visible = true;
                        fixture.goboPlane.position.copy(planePos);
                        fixture.goboPlane.scale.set(diameter, diameter, 1);
                        fixture.goboPlane.lookAt(planePos.clone().add(hitNormal));
                        fixture.goboPlane.rotation.z = baseRotation;
                    }
                } else {
                    fixture.goboPlane.visible = false;
                    if (fixture.prismPlanes) {
                        fixture.prismPlanes.forEach(plane => { plane.visible = false; });
                    }
                }
            }
            
            // Update beam geometry if length changed significantly
            if (Math.abs(actualBeamLength - fixture.beam.userData.currentLength) > 0.1) {
                fixture.beam.userData.currentLength = actualBeamLength;
                
                const actualSpread = beamSpread * (actualBeamLength / maxBeamLength);
                
                // Use appropriate geometry based on fixture type
                let newGeometry;
                if (fixture.type === 'par') {
                    // Cylinder for PAR - narrow at fixture, wide at end
                    const beamStartRadius = 0.2;
                    newGeometry = new THREE.CylinderGeometry(beamStartRadius, actualSpread, actualBeamLength, 64, 1, true);
                } else {
                    // Truncated cone for moving heads (keep a small flat tip)
                    const beamStartRadius = fixture.beamParams.outletRadius;
                    newGeometry = new THREE.CylinderGeometry(beamStartRadius, actualSpread, actualBeamLength, 64, 1, true);
                }
                
                // Reapply vertex colors
                const colors = [];
                const positionAttribute = newGeometry.attributes.position;
                for (let i = 0; i < positionAttribute.count; i++) {
                    const y = positionAttribute.getY(i);
                    const alpha = (y + actualBeamLength / 2) / actualBeamLength;
                    colors.push(alpha, alpha, alpha);
                }
                newGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
                
                fixture.beam.geometry.dispose();
                fixture.beam.geometry = newGeometry;
                
                // Update position
                if (fixture.type === 'moving_head') {
                    fixture.beam.position.z = 0.25 + actualBeamLength / 2;
                } else if (fixture.type === 'par') {
                    fixture.beam.position.y = -0.15 - actualBeamLength / 2;
                }
            }
        });
    }
    
    updateWallVisibility() {
        if (!this.stageGroup) return;
        
        const camPos = this.camera.position;
        const sceneCenter = new THREE.Vector3(0, this.stageHeight / 2, 0);
        
        // Hide walls/floor/ceiling that are between camera and scene center
        // This allows viewing inside the room without obstruction
        
        // Floor - hide if camera is below floor level
        if (this.floor) {
            this.floor.visible = camPos.y >= 0.1;
        }
        
        // Ceiling - hide if camera is above ceiling
        if (this.ceiling) {
            this.ceiling.visible = camPos.y <= this.stageHeight - 0.1;
        }
        
        // Back wall (negative Z) - hide if camera is behind it (more negative Z)
        if (this.backWall) {
            this.backWall.visible = camPos.z >= -this.stageDepth / 2 + 0.1;
        }
        
        // Front wall (positive Z) - hide if camera is in front of it (more positive Z)
        if (this.frontWall) {
            this.frontWall.visible = camPos.z <= this.stageDepth / 2 - 0.1;
        }
        
        // Left wall (negative X) - hide if camera is to the left of it
        if (this.leftWall) {
            this.leftWall.visible = camPos.x >= -this.stageWidth / 2 + 0.1;
        }
        
        // Right wall (positive X) - hide if camera is to the right of it
        if (this.rightWall) {
            this.rightWall.visible = camPos.x <= this.stageWidth / 2 - 0.1;
        }
    }
    
    updateStage() {
        this.stageWidth = parseInt(document.getElementById('stageWidth').value);
        this.stageDepth = parseInt(document.getElementById('stageDepth').value);
        this.stageHeight = parseFloat(document.getElementById('stageHeight').value);
        this.setupStage();
    }
    
    toggleGrid() {
        this.showGrid = document.getElementById('showGrid').checked;
        this.setupStage();
    }
    
    toggleBeams() {
        this.showBeams = document.getElementById('showBeams').checked;
        this.fixtures.forEach(fixture => {
            if (fixture.type === 'moving_head' && fixture.prismBeams) {
                this.updatePrismBeams(fixture);
            } else if (fixture.beam) {
                fixture.beam.visible = this.showBeams;
            }
        });
    }
    
    toggleLabels() {
        this.showLabels = document.getElementById('showLabels').checked;
        // TODO: Implement label sprites
    }
    
    updateFixtureCount() {
        document.getElementById('fixtureCount').textContent = this.fixtures.length;
    }
    
    updateFixtureList() {
        const listContainer = document.getElementById('fixture-list');
        
        if (this.fixtures.length === 0) {
            listContainer.innerHTML = '<div class="no-fixtures">No fixtures added yet</div>';
            return;
        }
        
        listContainer.innerHTML = '';
        
        this.fixtures.forEach(fixture => {
            const item = document.createElement('div');
            item.className = 'fixture-item';
            if (this.selectedFixture === fixture) {
                item.classList.add('selected');
            }
            
            const pos = fixture.group.position;
            
            item.innerHTML = `
                <div class="fixture-name">${fixture.name}</div>
                <div class="fixture-type">${fixture.type.replace('_', ' ')}</div>
                <div class="fixture-position">X:${pos.x.toFixed(1)} Y:${pos.y.toFixed(1)} Z:${pos.z.toFixed(1)}</div>
                <button class="delete-fixture-btn" title="Delete fixture">❌</button>
            `;
            
            item.addEventListener('click', (e) => {
                // Don't select if clicking delete button
                if (e.target.classList.contains('delete-fixture-btn')) {
                    return;
                }
                this.selectFixture(fixture);
            });
            
            // Add delete button handler
            const deleteBtn = item.querySelector('.delete-fixture-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteFixture(fixture);
            });
            
            listContainer.appendChild(item);
        });
    }
    
    onMouseClick(event) {
        // Don't process clicks if transform controls are being used
        if (this.transformControls.dragging) return;
        
        // Calculate mouse position in normalized device coordinates
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        // Raycast
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.scene.children, true);
        
        if (intersects.length > 0) {
            // Find the fixture
            let object = intersects[0].object;
            while (object.parent && !object.userData.fixture) {
                object = object.parent;
            }
            
            if (object.userData.fixture) {
                this.selectFixture(object.userData.fixture);
            }
        } else {
            // Click on empty space - deselect
            this.deselectFixture();
        }
    }
    
    onKeyDown(event) {
        // Keyboard shortcuts for transform modes
        switch (event.key.toLowerCase()) {
            case 'w':
                this.setTransformMode('translate');
                break;
            case 'e':
                this.setTransformMode('rotate');
                break;
            case 'r':
                this.setTransformMode('scale');
                break;
            case 'escape':
                this.deselectFixture();
                break;
            case 'delete':
            case 'backspace':
                if (this.selectedFixture) {
                    event.preventDefault();
                    this.deleteSelectedFixture();
                }
                break;
        }
    }
    
    onTransformChange() {
        // Called when transform controls change fixture position/rotation/scale
        if (this.selectedFixture) {
            // Update fixture list with new position
            this.updateFixtureList();
            
            // You can add persistence here (save positions to config, etc.)
            console.log('Fixture moved:', this.selectedFixture.name, 
                       'Position:', this.selectedFixture.group.position);
        }
    }
    
    setTransformMode(mode) {
        this.transformControls.setMode(mode);
        
        // Update button states
        document.querySelectorAll('#control-panel button').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const buttonIds = {
            'translate': 'btnTranslate',
            'rotate': 'btnRotate',
            'scale': 'btnScale'
        };
        
        const button = document.getElementById(buttonIds[mode]);
        if (button) button.classList.add('active');
    }
    
    selectFixture(fixture) {
        this.selectedFixture = fixture;
        
        // Attach transform controls to fixture
        this.transformControls.attach(fixture.group);
        
        // Show info panel
        const infoPanel = document.getElementById('selected-info');
        const detailsDiv = document.getElementById('fixture-details');
        
        const pos = fixture.group.position;
        const rot = fixture.group.rotation;
        
        infoPanel.style.display = 'block';
        detailsDiv.innerHTML = `
            <div><strong>Name:</strong> ${fixture.name}</div>
            <div><strong>Type:</strong> ${fixture.type}</div>
            <div><strong>ID:</strong> ${fixture.id}</div>
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #444;">
                <strong>Position:</strong><br>
                X: ${pos.x.toFixed(2)}m<br>
                Y: ${pos.y.toFixed(2)}m<br>
                Z: ${pos.z.toFixed(2)}m
            </div>
            <div style="margin-top: 8px;">
                <strong>Rotation:</strong><br>
                ${(rot.x * 180 / Math.PI).toFixed(1)}°, 
                ${(rot.y * 180 / Math.PI).toFixed(1)}°, 
                ${(rot.z * 180 / Math.PI).toFixed(1)}°
            </div>
            ${fixture.dmx.pan !== undefined ? `<div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #444;"><strong>Pan:</strong> ${fixture.dmx.pan}</div>` : ''}
            ${fixture.dmx.tilt !== undefined ? `<div><strong>Tilt:</strong> ${fixture.dmx.tilt}</div>` : ''}
            ${fixture.dmx.dimmer !== undefined ? `<div><strong>Dimmer:</strong> ${fixture.dmx.dimmer}</div>` : ''}
        `;
        
        console.log('Selected:', fixture.name);
        
        // Update fixture list highlighting
        this.updateFixtureList();
        
        // Enable and update beam controls if fixture has beams
        this.updateBeamControls(fixture);
    }
    
    deselectFixture() {
        this.selectedFixture = null;
        this.transformControls.detach();
        
        // Hide info panel
        const infoPanel = document.getElementById('selected-info');
        infoPanel.style.display = 'none';
        
        console.log('Deselected');
        
        // Update fixture list highlighting
        this.updateFixtureList();
        
        // Disable beam controls
        const beamControls = document.getElementById('beam-controls');
        beamControls.style.opacity = '0.5';
        beamControls.style.pointerEvents = 'none';
    }
    
    updateBeamControls(fixture) {
        const beamControls = document.getElementById('beam-controls');
        
        if (fixture && fixture.beamParams && (fixture.type === 'moving_head' || fixture.type === 'par')) {
            // Enable controls
            beamControls.style.opacity = '1';
            beamControls.style.pointerEvents = 'auto';
            
            // Update values
            document.getElementById('beamLength').value = fixture.beamParams.length;
            document.getElementById('beamTipDiameter').value = (fixture.beamParams.outletRadius * 200).toFixed(1);
            document.getElementById('beamAngle').value = fixture.beamParams.angle;
            const goboSlider = document.getElementById('beamGoboRotation');
            goboSlider.value = fixture.beamParams.goboRotation ?? 0;
            goboSlider.disabled = fixture.type !== 'moving_head';
            const prismEnabled = document.getElementById('beamPrismEnabled');
            const prismSpread = document.getElementById('beamPrismSpread');
            prismEnabled.checked = fixture.beamParams.prismEnabled ?? false;
            prismEnabled.disabled = fixture.type !== 'moving_head';
            prismSpread.value = ((fixture.beamParams.prismSpread ?? 0.15) * 100).toFixed(0);
            prismSpread.disabled = fixture.type !== 'moving_head';
        } else {
            // Disable controls for fixtures without beams
            beamControls.style.opacity = '0.5';
            beamControls.style.pointerEvents = 'none';
        }
    }
    
    updateBeamParameter(param, value) {
        if (!this.selectedFixture || !this.selectedFixture.beamParams) {
            console.warn('No fixture with beam parameters selected');
            return;
        }
        
        const fixture = this.selectedFixture;
        const numValue = parseFloat(value);
        
        console.log(`Updating beam ${param} to ${numValue} for ${fixture.name}`);
        
        // Update parameter
        switch(param) {
            case 'length':
                fixture.beamParams.length = numValue;
                break;
            case 'tipDiameterCm':
                fixture.beamParams.outletRadius = Math.max(0.001, numValue / 200);
                break;
            case 'angle':
                fixture.beamParams.angle = numValue;
                break;
            case 'goboRotation':
                fixture.beamParams.goboRotation = numValue;
                break;
            case 'prismEnabled':
                fixture.beamParams.prismEnabled = value === true || value === 'true';
                break;
            case 'prismSpreadCm':
                fixture.beamParams.prismSpread = Math.max(0.01, numValue / 100);
                break;
        }
        
        // Rebuild beam geometry
        this.rebuildBeam(fixture);

        if (fixture.type === 'moving_head') {
            this.updatePrismBeams(fixture);
        }
    }
    
    rebuildBeam(fixture) {
        if (!fixture.beam || !fixture.beamParams) return;
        
        const params = fixture.beamParams;
        let newGeometry;
        
        if (fixture.type === 'moving_head') {
            // Frustum/truncated cone beam for moving head
            const beamSpread = Math.tan(THREE.MathUtils.degToRad(params.angle / 2)) * params.length;
            newGeometry = new THREE.CylinderGeometry(params.outletRadius, beamSpread, params.length, 64, 1, true);
            
            // Update spotlight to match
            if (fixture.light) {
                const halfAngle = Math.atan(beamSpread / params.length);
                fixture.light.angle = halfAngle * 2 * 0.95;
                fixture.light.distance = params.length * 1.5;
                fixture.light.target.position.set(0, 0, params.length + 0.25);
                fixture.light.shadow.camera.far = params.length * 1.5;
            }
            
        } else if (fixture.type === 'par') {
            // Cylinder beam for PAR
            const beamEndRadius = Math.tan(THREE.MathUtils.degToRad(params.angle / 2)) * params.length;
            newGeometry = new THREE.CylinderGeometry(params.outletRadius, beamEndRadius, params.length, 64, 1, true);
        }
        
        if (!newGeometry) return;
        
        // Add vertex colors for fade effect
        const colors = [];
        const positionAttribute = newGeometry.attributes.position;
        for (let i = 0; i < positionAttribute.count; i++) {
            const y = positionAttribute.getY(i);
            const alpha = (y + params.length / 2) / params.length;
            colors.push(alpha, alpha, alpha);
        }
        newGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        
        // Replace geometry
        fixture.beam.geometry.dispose();
        fixture.beam.geometry = newGeometry;

        if (fixture.prismBeams) {
            fixture.prismBeams.forEach(prismBeam => {
                prismBeam.geometry.dispose();
                prismBeam.geometry = newGeometry.clone();
            });
        }

        if (fixture.beamStartDisc) {
            const segments = fixture.type === 'moving_head' ? 32 : 16;
            fixture.beamStartDisc.geometry.dispose();
            fixture.beamStartDisc.geometry = new THREE.CircleGeometry(params.outletRadius, segments);
        }
        
        // Mark attributes for update
        fixture.beam.geometry.attributes.position.needsUpdate = true;
        fixture.beam.geometry.attributes.color.needsUpdate = true;
        
        // Update beam position
        fixture.beam.userData.currentLength = params.length;
        if (fixture.type === 'moving_head') {
            fixture.beam.position.z = 0.25 + params.length / 2;
        } else if (fixture.type === 'par') {
            fixture.beam.position.y = -0.15 - params.length / 2;
        }

        if (fixture.prismBeams) {
            fixture.prismBeams.forEach(prismBeam => {
                prismBeam.userData.currentLength = params.length;
            });
        }

        const dimmer = fixture.dmx?.dimmer ?? 255;
        this.applyBeamOpacity(fixture, dimmer / 255);
        
        console.log(`Beam rebuilt - Length: ${params.length}m, Tip Diameter: ${(params.outletRadius * 200).toFixed(1)}cm, Angle: ${params.angle}°`);
    }
    
    deleteSelectedFixture() {
        if (!this.selectedFixture) return;
        this.deleteFixture(this.selectedFixture);
    }
    
    deleteFixture(fixture) {
        if (!fixture) return;
        
        // Remove from scene
        this.scene.remove(fixture.group);
        
        // Remove from fixtures array
        const index = this.fixtures.indexOf(fixture);
        if (index > -1) {
            this.fixtures.splice(index, 1);
        }
        
        // Deselect if this was selected
        if (this.selectedFixture === fixture) {
            this.deselectFixture();
        }
        
        // Update UI
        this.updateFixtureCount();
        this.updateFixtureList();
        
        console.log('Deleted:', fixture.name);
    }
    
    onWindowResize() {
        this.camera.aspect = this.canvas.clientWidth / this.canvas.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
        this.composer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
    }
    
    animateBeamTextures() {
        // Scroll beam textures for dynamic volumetric effect
        const delta = 0.016; // Approximate frame time
        
        this.fixtures.forEach(fixture => {
            if (fixture.beam && fixture.beam.material.map) {
                const material = fixture.beam.material;
                if (material.userData.scrollSpeed) {
                    material.map.offset.y += material.userData.scrollSpeed * delta;
                }
            }
        });
    }
    
    updateGodRaysLights() {
        // Update light positions in screen space for god rays effect
        const lightPositions = [];
        const lightColors = [];
        
        this.fixtures.forEach(fixture => {
            if (fixture.light) {
                const light = fixture.light;
                
                // Get world position of light
                const worldPos = new THREE.Vector3();
                light.getWorldPosition(worldPos);
                
                // Project to screen space
                const screenPos = worldPos.clone().project(this.camera);
                
                // Convert to UV coordinates (0-1)
                const x = (screenPos.x + 1) / 2;
                const y = (screenPos.y + 1) / 2;
                
                // Only add lights that are in front of camera and visible
                if (screenPos.z < 1 && x >= 0 && x <= 1 && y >= 0 && y <= 1) {
                    lightPositions.push(x, y);
                    
                    // Extract light color
                    const color = light.color;
                    lightColors.push(color.r, color.g, color.b);
                }
            }
        });
        
        // Pad arrays to fixed size (max 10 lights)
        while (lightPositions.length < 20) {
            lightPositions.push(-999, -999); // Invalid marker
            lightColors.push(0, 0, 0);
        }
        
        // Update shader uniforms
        if (this.godRaysPass && this.godRaysPass.uniforms) {
            // Convert to array of Vector2 for positions
            const posArray = [];
            for (let i = 0; i < 10; i++) {
                posArray.push(new THREE.Vector2(lightPositions[i * 2], lightPositions[i * 2 + 1]));
            }
            this.godRaysPass.uniforms.lightPositions.value = posArray;
            
            // Convert to array of Color for colors
            const colorArray = [];
            for (let i = 0; i < 10; i++) {
                colorArray.push(new THREE.Vector3(lightColors[i * 3], lightColors[i * 3 + 1], lightColors[i * 3 + 2]));
            }
            this.godRaysPass.uniforms.lightColors.value = colorArray;
        }
    }
    
    updateStats() {
        this.frameCount++;
        const now = performance.now();
        
        if (now >= this.lastTime + 1000) {
            this.fps = Math.round((this.frameCount * 1000) / (now - this.lastTime));
            document.getElementById('fps').textContent = this.fps;
            
            this.frameCount = 0;
            this.lastTime = now;
        }
        
        // Draw calls (approximate)
        document.getElementById('drawCalls').textContent = this.renderer.info.render.calls;
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());

        const now = performance.now();
        const delta = this.lastFrameTime ? (now - this.lastFrameTime) / 1000 : 0.016;
        this.lastFrameTime = now;
        
        // Update controls
        this.controls.update();
        
        // Update wall visibility based on camera position
        this.updateWallVisibility();
        
        // Update beam collisions with room surfaces
        this.updateBeamCollisions();
        
        // Update video texture if it exists
        if (this.videoTexture && this.videoElement && 
            !this.videoElement.paused && 
            this.videoElement.readyState >= this.videoElement.HAVE_CURRENT_DATA) {
            this.videoTexture.needsUpdate = true;
        }
        
        // Animate beam textures for volumetric effect
        this.animateBeamTextures();

        // Animate gobo rotation for moving heads
        this.animateGoboRotation(delta);
        
        // Update god rays light positions (disabled)
        // this.updateGodRaysLights();
        
        // Render with bloom post-processing
        this.composer.render();
        
        // Update stats
        this.updateStats();
    }

    animateGoboRotation(deltaSeconds) {
        const maxSpeed = Math.PI * 2; // rad/s at slider max
        this.fixtures.forEach(fixture => {
            if (fixture.type !== 'moving_head' || !fixture.light || !fixture.light.map) return;
            const rotationValue = fixture.beamParams?.goboRotation ?? 0;
            if (rotationValue === 0) return;
            const speed = (rotationValue / 100) * maxSpeed;
            const deltaAngle = speed * deltaSeconds;
            fixture.light.map.rotation += deltaAngle;
            fixture.light.map.needsUpdate = true;
            if (fixture.goboPlane?.material?.map) {
                fixture.goboPlane.material.map.rotation = fixture.light.map.rotation;
                fixture.goboPlane.material.map.needsUpdate = true;
            }
            if (fixture.beamParams) {
                fixture.beamParams.goboAngle = (fixture.beamParams.goboAngle ?? 0) + deltaAngle;
                if (fixture.goboPlane) {
                    fixture.goboPlane.rotation.z = fixture.beamParams.goboAngle;
                }
            }
        });
    }
}
