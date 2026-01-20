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
        
        // Orbit controls
        this.controls = new OrbitControls(this.camera, this.canvas);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.maxPolarAngle = Math.PI / 2; // Prevent going below ground
        
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
    
    createGoboTexture(symbol = '☺', size = 512) {
        // Create canvas for gobo pattern
        const canvas = document.createElement('canvas');
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        
        // Black background
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, size, size);
        
        // White symbol in center
        ctx.fillStyle = '#ffffff';
        ctx.font = `${size * 0.6}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(symbol, size / 2, size / 2);
        
        // Create texture
        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
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
        this.stageGroup.add(rightWall);
        
        // Ceiling
        const ceiling = new THREE.Mesh(
            new THREE.PlaneGeometry(this.stageWidth, this.stageDepth),
            wallMaterial
        );
        ceiling.position.y = this.stageHeight;
        ceiling.rotation.x = Math.PI / 2;
        ceiling.receiveShadow = true;
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
        
        // Light beam (starts at front face of moving head)
        const beamLength = 8; // Shorter beam to fit within room
        const beamSpread = 1.28; // Proportional spread
        const beamGeometry = new THREE.ConeGeometry(beamSpread, beamLength, 64, 1, true); // 64 segments for smooth appearance
        
        // Add vertex colors for fade effect (darker at wide end)
        const colors = [];
        const positionAttribute = beamGeometry.attributes.position;
        for (let i = 0; i < positionAttribute.count; i++) {
            const y = positionAttribute.getY(i);
            const alpha = (y + beamLength / 2) / beamLength; // Fade from 0 (wide end) to 1 (narrow end)
            colors.push(alpha, alpha, alpha);
        }
        beamGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        
        const beamMaterial = new THREE.MeshBasicMaterial({
            color: 0xffff00,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide,
            vertexColors: true
        });
        const beam = new THREE.Mesh(beamGeometry, beamMaterial);
        // Position beam so narrow end is at front face (z = 0.25), wide end extends forward
        beam.position.z = 0.25 + beamLength / 2; // Front of box + half beam length
        beam.rotation.x = -Math.PI / 2; // Point forward with narrow end at fixture
        beam.visible = this.showBeams;
        head.add(beam);
        
        // Spot light at front of moving head with gobo (intensity boosted 30% for brighter wall spots)
        const light = new THREE.SpotLight(0xffffff, 2.6, 10, Math.PI / 6, 0.5, 1);
        light.position.z = 0.25; // At front face of moving head
        light.target.position.set(0, 0, 5);
        light.castShadow = true;
        
        // Add gobo texture
        const goboTexture = this.createGoboTexture('☺');
        light.map = goboTexture;
        
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
            light: light,
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
        
        // Light beam (wider cone, starts at bottom of PAR)
        const beamLength = 3; // Fits within 4m room height
        const beamSpread = 0.6; // Proportional spread
        const beamGeometry = new THREE.ConeGeometry(beamSpread, beamLength, 64, 1, true); // 64 segments for smooth appearance
        
        // Add vertex colors for fade effect (darker at wide end)
        const colors = [];
        const positionAttribute = beamGeometry.attributes.position;
        for (let i = 0; i < positionAttribute.count; i++) {
            const y = positionAttribute.getY(i);
            const alpha = (y + beamLength / 2) / beamLength; // Fade from 0 (wide end) to 1 (narrow end)
            colors.push(alpha, alpha, alpha);
        }
        beamGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        
        const beamMaterial = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.2,
            side: THREE.DoubleSide,
            vertexColors: true
        });
        const beam = new THREE.Mesh(beamGeometry, beamMaterial);
        // Position beam so narrow end is at bottom of PAR (y = -0.15), wide end extends downward
        beam.position.y = -0.15 - beamLength / 2; // Bottom of PAR + half beam length
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
            light: light,
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
    
    createDisplay(position) {
        const group = new THREE.Group();
        group.position.set(position.x, position.y + 1, position.z);
        
        // Display screen
        const screenGeometry = new THREE.PlaneGeometry(1.6, 0.9); // 16:9 aspect
        const screenMaterial = new THREE.MeshBasicMaterial({
            color: 0x000000,
            side: THREE.DoubleSide
        });
        const screen = new THREE.Mesh(screenGeometry, screenMaterial);
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
        fixture.beam.material.opacity = intensity * 0.3;
        
        // Color
        const colorValue = new THREE.Color(
            color.r / 255,
            color.g / 255,
            color.b / 255
        );
        fixture.light.color = colorValue;
        fixture.beam.material.color = colorValue;
    }
    
    updatePar(fixture) {
        const { dimmer, color } = fixture.dmx;
        
        // Dimmer
        const intensity = dimmer / 255;
        fixture.light.intensity = intensity;
        fixture.beam.material.opacity = intensity * 0.2;
        
        // Color
        const colorValue = new THREE.Color(
            color.r / 255,
            color.g / 255,
            color.b / 255
        );
        fixture.light.color = colorValue;
        fixture.beam.material.color = colorValue;
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
            if (fixture.beam) {
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
            `;
            
            item.addEventListener('click', () => {
                this.selectFixture(fixture);
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
    }
    
    deleteSelectedFixture() {
        if (!this.selectedFixture) return;
        
        const fixture = this.selectedFixture;
        
        // Remove from scene
        this.scene.remove(fixture.group);
        
        // Remove from fixtures array
        const index = this.fixtures.indexOf(fixture);
        if (index > -1) {
            this.fixtures.splice(index, 1);
        }
        
        // Deselect
        this.deselectFixture();
        
        // Update UI
        this.updateFixtureCount();
        this.updateFixtureList();
        
        console.log('Deleted:', fixture.name);
    }
    
    onWindowResize() {
        this.camera.aspect = this.canvas.clientWidth / this.canvas.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
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
        
        // Update controls
        this.controls.update();
        
        // Render
        this.renderer.render(this.scene, this.camera);
        
        // Update stats
        this.updateStats();
    }
}
