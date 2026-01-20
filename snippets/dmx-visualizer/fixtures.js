/**
 * Fixture definitions and DMX channel mappings
 * Based on Open Fixture Library format
 */

const FixtureLibrary = {
    // Common fixture types with channel mappings
    
    moving_head_14ch: {
        name: 'Generic Moving Head (14 Channel)',
        channels: {
            pan: 0,
            pan_fine: 1,
            tilt: 2,
            tilt_fine: 3,
            color_wheel: 4,
            gobo_wheel: 5,
            gobo_rotation: 6,
            prism: 7,
            focus: 8,
            dimmer: 9,
            shutter: 10,
            control: 11,
            movement_speed: 12,
            dimmer_mode: 13
        },
        ranges: {
            pan: { min: 0, max: 540 },
            tilt: { min: 0, max: 270 }
        }
    },
    
    led_par_7ch: {
        name: 'Generic LED PAR (7 Channel)',
        channels: {
            dimmer: 0,
            red: 1,
            green: 2,
            blue: 3,
            white: 4,
            strobe: 5,
            mode: 6
        }
    },
    
    led_strip_rgb: {
        name: 'Generic LED Strip (RGB per pixel)',
        channels: {
            // 3 channels per pixel (R, G, B)
            // Channel count = pixel_count * 3
        },
        pixelMode: true
    },
    
    strobe_2ch: {
        name: 'Generic Strobe (2 Channel)',
        channels: {
            dimmer: 0,
            rate: 1
        }
    }
};

/**
 * DMX Universe Manager
 * Handles DMX data distribution to fixtures
 */
class DMXUniverseManager {
    constructor() {
        this.universes = new Map(); // universe_id -> 512 byte array
        this.fixturePatches = []; // Array of {fixture, universe, address, channels}
    }
    
    /**
     * Patch a fixture to a DMX address
     */
    patchFixture(fixture, universe, address, channelMap) {
        this.fixturePatches.push({
            fixture: fixture,
            universe: universe,
            address: address,
            channels: channelMap
        });
    }
    
    /**
     * Update DMX data for a universe
     */
    updateUniverse(universeId, data) {
        this.universes.set(universeId, new Uint8Array(data));
        
        // Update all patched fixtures in this universe
        this.fixturePatches.forEach(patch => {
            if (patch.universe === universeId) {
                this.updateFixtureFromDMX(patch, data);
            }
        });
    }
    
    /**
     * Extract DMX values for a fixture and update it
     */
    updateFixtureFromDMX(patch, universeData) {
        const { fixture, address, channels } = patch;
        const dmxData = {};
        
        // Extract channel values
        Object.keys(channels).forEach(param => {
            const channelOffset = channels[param];
            const dmxChannel = address + channelOffset - 1; // DMX is 1-indexed
            
            if (dmxChannel < universeData.length) {
                dmxData[param] = universeData[dmxChannel];
            }
        });
        
        // Convert DMX values to fixture parameters
        this.convertDMXToFixtureParams(fixture, dmxData);
    }
    
    /**
     * Convert raw DMX values to fixture-specific parameters
     */
    convertDMXToFixtureParams(fixture, dmxData) {
        const params = {};
        
        // Pan/Tilt (16-bit if fine channels available)
        if (dmxData.pan !== undefined) {
            params.pan = dmxData.pan_fine !== undefined
                ? (dmxData.pan * 256 + dmxData.pan_fine) / 65535 * 255
                : dmxData.pan;
        }
        
        if (dmxData.tilt !== undefined) {
            params.tilt = dmxData.tilt_fine !== undefined
                ? (dmxData.tilt * 256 + dmxData.tilt_fine) / 65535 * 255
                : dmxData.tilt;
        }
        
        // Color (RGB)
        if (dmxData.red !== undefined && dmxData.green !== undefined && dmxData.blue !== undefined) {
            params.color = {
                r: dmxData.red,
                g: dmxData.green,
                b: dmxData.blue
            };
        }
        
        // Dimmer
        if (dmxData.dimmer !== undefined) {
            params.dimmer = dmxData.dimmer;
        }
        
        // Update fixture (assuming visualizer instance available)
        if (window.visualizer) {
            window.visualizer.updateFixture(fixture, params);
        }
    }
    
    /**
     * Simulate Art-Net packet reception
     */
    receiveArtNetPacket(universe, data) {
        this.updateUniverse(universe, data);
    }
}

// Global instance
const dmxManager = new DMXUniverseManager();
