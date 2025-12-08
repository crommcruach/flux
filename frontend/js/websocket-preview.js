/**
 * WebSocket Video Preview Component
 * Real-time video streaming via WebSocket for live preview
 * Simpler and more efficient than WebRTC for LAN environments
 */

class WebSocketPreview {
    constructor(options = {}) {
        this.options = {
            playerId: options.playerId || 'video',
            quality: options.quality || 'medium',
            fps: options.fps || 30,
            autoStart: options.autoStart !== false,
            socketPath: options.socketPath || '/socket.io',
            onError: options.onError || (() => {}),
            onConnected: options.onConnected || (() => {}),
            onDisconnected: options.onDisconnected || (() => {})
        };
        
        this.socket = null;
        this.canvas = null;
        this.ctx = null;
        this.isStreaming = false;
        this.frameCount = 0;
        this.startTime = null;
        this.fpsDisplay = options.fpsDisplay || null;
    }
    
    /**
     * Initialize the preview with a canvas element
     * @param {HTMLCanvasElement} canvas - Canvas element to render video frames
     */
    async start(canvas) {
        if (!canvas) {
            throw new Error('Canvas element is required');
        }
        
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        
        console.log('Starting WebSocket preview:', {
            player: this.options.playerId,
            quality: this.options.quality,
            fps: this.options.fps
        });
        
        try {
            // Connect to Socket.IO server
            await this.connect();
            
            // Start streaming
            if (this.options.autoStart) {
                this.startStream();
            }
            
        } catch (error) {
            console.error('WebSocket preview start error:', error);
            this.options.onError(error);
            throw error;
        }
    }
    
    /**
     * Connect to WebSocket server
     */
    connect() {
        return new Promise((resolve, reject) => {
            try {
                // Load Socket.IO library if not already loaded
                if (typeof io === 'undefined') {
                    // Socket.IO should be loaded in HTML
                    reject(new Error('Socket.IO library not loaded'));
                    return;
                }
                
                // Connect to Socket.IO namespace
                this.socket = io('/video', {
                    path: this.options.socketPath,
                    transports: ['websocket', 'polling']
                });
                
                // Connection successful
                this.socket.on('connect', () => {
                    console.log('WebSocket connected:', this.socket.id);
                    this.options.onConnected();
                    resolve();
                });
                
                // Connection error
                this.socket.on('connect_error', (error) => {
                    console.error('WebSocket connection error:', error);
                    this.options.onError(error);
                    reject(error);
                });
                
                // Disconnected
                this.socket.on('disconnect', (reason) => {
                    console.log('WebSocket disconnected:', reason);
                    this.isStreaming = false;
                    this.options.onDisconnected(reason);
                });
                
                // Server confirms connection
                this.socket.on('connected', (data) => {
                    console.log('Server confirmed connection:', data);
                });
                
                // Stream started confirmation
                this.socket.on('stream_started', (data) => {
                    console.log('Stream started:', data);
                    this.isStreaming = true;
                    this.frameCount = 0;
                    this.startTime = Date.now();
                });
                
                // Stream stopped confirmation
                this.socket.on('stream_stopped', () => {
                    console.log('Stream stopped');
                    this.isStreaming = false;
                });
                
                // Receive video frames
                this.socket.on('video_frame', (frameData) => {
                    this.handleFrame(frameData);
                });
                
            } catch (error) {
                reject(error);
            }
        });
    }
    
    /**
     * Start streaming video frames
     */
    startStream() {
        if (!this.socket || !this.socket.connected) {
            console.error('Socket not connected');
            return;
        }
        
        console.log('Requesting stream start...');
        this.socket.emit('start_stream', {
            player_id: this.options.playerId,
            quality: this.options.quality,
            fps: this.options.fps
        });
    }
    
    /**
     * Stop streaming video frames
     */
    stopStream() {
        if (!this.socket) return;
        
        console.log('Requesting stream stop...');
        this.isStreaming = false;
        this.socket.emit('stop_stream');
    }
    
    /**
     * Handle incoming video frame
     * @param {ArrayBuffer} frameData - JPEG encoded frame data
     */
    handleFrame(frameData) {
        if (!this.ctx || !this.canvas) return;
        
        try {
            // Convert ArrayBuffer to Blob
            const blob = new Blob([frameData], { type: 'image/jpeg' });
            
            // Create object URL
            const url = URL.createObjectURL(blob);
            
            // Load image
            const img = new Image();
            img.onload = () => {
                // Clear canvas with black background
                this.ctx.fillStyle = '#000000';
                this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
                
                // Calculate aspect ratio preserving dimensions
                const canvasAspect = this.canvas.width / this.canvas.height;
                const imageAspect = img.width / img.height;
                
                let drawWidth, drawHeight, drawX, drawY;
                
                if (imageAspect > canvasAspect) {
                    // Image is wider - fit to width
                    drawWidth = this.canvas.width;
                    drawHeight = this.canvas.width / imageAspect;
                    drawX = 0;
                    drawY = (this.canvas.height - drawHeight) / 2;
                } else {
                    // Image is taller - fit to height
                    drawHeight = this.canvas.height;
                    drawWidth = this.canvas.height * imageAspect;
                    drawX = (this.canvas.width - drawWidth) / 2;
                    drawY = 0;
                }
                
                // Draw image centered with aspect ratio preserved
                this.ctx.drawImage(img, drawX, drawY, drawWidth, drawHeight);
                
                // Clean up
                URL.revokeObjectURL(url);
                
                // Update stats
                this.frameCount++;
                if (this.fpsDisplay && this.frameCount % 10 === 0) {
                    const elapsed = (Date.now() - this.startTime) / 1000;
                    const fps = this.frameCount / elapsed;
                    this.fpsDisplay.textContent = `${fps.toFixed(1)} FPS`;
                }
            };
            img.onerror = (error) => {
                console.error('Frame image load error:', error);
            };
            img.src = url;
            
        } catch (error) {
            console.error('Frame handling error:', error);
        }
    }
    
    /**
     * Stop streaming and disconnect
     */
    stop() {
        console.log('Stopping WebSocket preview...');
        
        this.stopStream();
        
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        
        this.isStreaming = false;
    }
    
    /**
     * Change streaming quality
     * @param {string} quality - 'low', 'medium', or 'high'
     */
    setQuality(quality) {
        this.options.quality = quality;
        if (this.isStreaming) {
            // Restart stream with new quality
            this.stopStream();
            setTimeout(() => this.startStream(), 100);
        }
    }
    
    /**
     * Change target FPS
     * @param {number} fps - Target frames per second
     */
    setFPS(fps) {
        this.options.fps = fps;
        if (this.isStreaming) {
            // Restart stream with new FPS
            this.stopStream();
            setTimeout(() => this.startStream(), 100);
        }
    }
    
    /**
     * Get current streaming status
     * @returns {boolean} True if currently streaming
     */
    isActive() {
        return this.isStreaming && this.socket && this.socket.connected;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketPreview;
} else if (typeof window !== 'undefined') {
    window.WebSocketPreview = WebSocketPreview;
}
