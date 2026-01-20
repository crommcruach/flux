/**
 * Demo animations and test sequences
 */

function startDemo() {
    console.log('Starting DMX Visualizer Demo...');
    
    // Add some fixtures automatically
    setTimeout(() => {
        // Add moving heads
        visualizer.addFixture('moving_head', { x: -3, y: 0, z: -3 });
        visualizer.addFixture('moving_head', { x: 3, y: 0, z: -3 });
        visualizer.addFixture('moving_head', { x: -3, y: 0, z: 3 });
        visualizer.addFixture('moving_head', { x: 3, y: 0, z: 3 });
        
        // Add LED PARs
        visualizer.addFixture('par', { x: -2, y: 0, z: 0 });
        visualizer.addFixture('par', { x: 2, y: 0, z: 0 });
        
        // Add LED strip
        visualizer.addFixture('led_strip', { x: 0, y: 0, z: -4 });
        
        // Add display
        visualizer.addFixture('display', { x: 0, y: 1, z: 4 });
        
        console.log(`Added ${visualizer.fixtures.length} fixtures`);
        
        // Start animation sequences
        startAnimationSequences();
    }, 500);
}

function startAnimationSequences() {
    let time = 0;
    
    setInterval(() => {
        time += 0.016; // ~60fps
        
        // Animate moving heads
        visualizer.fixtures.forEach((fixture, index) => {
            if (fixture.type === 'moving_head') {
                // Circular pan/tilt movement
                const speed = 0.5;
                const phase = (index / visualizer.fixtures.length) * Math.PI * 2;
                
                const pan = 127 + Math.sin(time * speed + phase) * 60;
                const tilt = 127 + Math.cos(time * speed + phase) * 40;
                
                // Color cycle
                const hue = (time * 50 + index * 60) % 360;
                const color = hslToRgb(hue / 360, 1.0, 0.5);
                
                visualizer.updateFixture(fixture, {
                    pan: pan,
                    tilt: tilt,
                    dimmer: 255,
                    color: color
                });
            }
            
            if (fixture.type === 'par') {
                // Pulsing dimmer
                const dimmer = 127 + Math.sin(time * 2 + index) * 128;
                
                // Color cycle
                const hue = (time * 100 + index * 180) % 360;
                const color = hslToRgb(hue / 360, 1.0, 0.5);
                
                visualizer.updateFixture(fixture, {
                    dimmer: dimmer,
                    color: color
                });
            }
            
            if (fixture.type === 'led_strip') {
                // Rainbow chase effect
                const colors = [];
                for (let i = 0; i < 50; i++) {
                    const hue = ((time * 100 + i * 7.2) % 360) / 360;
                    colors.push(hslToRgb(hue, 1.0, 0.5));
                }
                
                visualizer.updateFixture(fixture, {
                    colors: colors
                });
            }
        });
    }, 16); // ~60fps
}

/**
 * HSL to RGB conversion
 */
function hslToRgb(h, s, l) {
    let r, g, b;
    
    if (s === 0) {
        r = g = b = l;
    } else {
        const hue2rgb = (p, q, t) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };
        
        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        
        r = hue2rgb(p, q, h + 1/3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1/3);
    }
    
    return {
        r: Math.round(r * 255),
        g: Math.round(g * 255),
        b: Math.round(b * 255)
    };
}

/**
 * WebSocket connection for live DMX data
 */
function connectDMXWebSocket() {
    const ws = new WebSocket('ws://localhost:5000/dmx-output');
    
    ws.onopen = () => {
        console.log('Connected to DMX output stream');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        // data format: { universe: 1, channels: [0-512] }
        if (data.universe && data.channels) {
            dmxManager.receiveArtNetPacket(data.universe, data.channels);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        console.log('Disconnected from DMX output stream');
        // Attempt reconnect after 5 seconds
        setTimeout(connectDMXWebSocket, 5000);
    };
}

// Uncomment to enable live WebSocket connection
// connectDMXWebSocket();
