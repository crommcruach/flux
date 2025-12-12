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
            debug: options.debug || false, // Debug logging disabled by default
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
        this.pendingUrls = new Set(); // Track URLs for cleanup
        this.frameImage = null; // Reuse image object
        this.isConnecting = false; // Prevent connection spam
    }
    
    /**
     * Internal logger - only logs when debug is enabled
     */
    log(...args) {
        if (this.options.debug) {
            console.log('[WebSocket]', ...args);
        }
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
        
        this.log('Starting WebSocket preview:', {
            player: this.options.playerId,
            quality: this.options.quality,
            fps: this.options.fps
        });
        
        try {
            // Connect to Socket.IO server
            await this.connect();
            // Note: autoStart is handled in the connect() event handler after connection is established
            
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
            // Prevent connection spam
            if (this.isConnecting) {
                reject(new Error('Connection already in progress'));
                return;
            }
            
            // Disconnect existing socket before creating new one
            if (this.socket && this.socket.connected) {
                this.log('Disconnecting existing video socket before reconnecting');
                this.socket.disconnect();
                this.socket = null;
            }
            
            this.isConnecting = true;
            
            try {
                // Load Socket.IO library if not already loaded
                if (typeof io === 'undefined') {
                    // Socket.IO should be loaded in HTML
                    this.isConnecting = false;
                    reject(new Error('Socket.IO library not loaded'));
                    return;
                }
                
                // Connect to Socket.IO namespace with stability settings
                this.socket = io('/video', {
                    path: this.options.socketPath,
                    transports: ['polling', 'websocket'],  // Start with polling, upgrade to WebSocket
                    upgrade: true,
                    rememberUpgrade: true,
                    reconnection: true,
                    reconnectionDelay: 2000,        // Increased from 1000ms
                    reconnectionDelayMax: 10000,    // Increased from 5000ms
                    reconnectionAttempts: 3,        // Reduced from 10 to prevent spam
                    timeout: 15000,                 // Increased from 10000ms
                    pingTimeout: 30000,
                    pingInterval: 10000,
                    perMessageDeflate: false,
                    maxHttpBufferSize: 5e6  // 5MB max buffer
                });
                
                // Connection successful
                this.socket.on('connect', () => {
                    this.log('WebSocket connected:', this.socket.id);
                    this.isConnecting = false;
                    this.options.onConnected();
                    
                    // Auto-start stream if enabled (must happen AFTER resolve to ensure socket.connected is true)
                    setTimeout(() => {
                        if (this.options.autoStart && !this.isStreaming) {
                            this.startStream();
                        }
                    }, 100);
                    
                    resolve();
                });
                
                // Connection error
                this.socket.on('connect_error', (error) => {
                    console.error('WebSocket connection error:', error);
                    this.isConnecting = false;
                    this.options.onError(error);
                    reject(error);
                });
                
                // Disconnected
                this.socket.on('disconnect', (reason) => {
                    this.log('WebSocket disconnected:', reason);
                    this.isStreaming = false;
                    this.options.onDisconnected(reason);
                    
                    // Only auto-reconnect if we didn't manually disconnect
                    // and connection was unexpected lost
                    const shouldReconnect = this.socket && 
                                          !this.isConnecting && 
                                          (reason === 'io server disconnect' || 
                                           reason === 'ping timeout' || 
                                           reason === 'transport close');
                    
                    if (shouldReconnect) {
                        this.log('Attempting auto-reconnect...');
                        setTimeout(() => {
                            if (this.socket && !this.socket.connected) {
                                this.socket.connect();
                            }
                        }, 2000);
                    }
                });
                
                // Reconnection events
                this.socket.on('reconnect', (attemptNumber) => {
                    this.log(`Reconnected after ${attemptNumber} attempts`);
                    // Restart stream after reconnect
                    if (this.options.autoStart) {
                        setTimeout(() => this.startStream(), 500);
                    }
                });
                
                this.socket.on('reconnect_error', (error) => {
                    console.warn('Reconnection error:', error.message);
                });
                
                this.socket.on('reconnect_failed', () => {
                    console.error('Reconnection failed after all attempts');
                    this.options.onError(new Error('Failed to reconnect'));
                });
                
                // Server confirms connection
                this.socket.on('connected', (data) => {
                    this.log('Server confirmed connection:', data);
                });
                
                // Stream started confirmation
                this.socket.on('stream_started', (data) => {
                    this.log('Stream started:', data);
                    this.isStreaming = true;
                    this.frameCount = 0;
                    this.startTime = Date.now();
                });
                
                // Stream stopped confirmation
                this.socket.on('stream_stopped', () => {
                    this.log('Stream stopped');
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
        if (!this.socket) {
            console.error('Socket not initialized');
            return;
        }
        
        if (!this.socket.connected) {
            console.error('Socket not connected (connected=' + this.socket.connected + ', id=' + this.socket.id + ')');
            return;
        }
        
        this.log('Requesting stream start...', {
            player: this.options.playerId,
            quality: this.options.quality,
            fps: this.options.fps,
            socket_id: this.socket.id
        });
        
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
        
        this.log('Requesting stream stop...');
        this.isStreaming = false;
        this.socket.emit('stop_stream');
    }
    
    /**
     * Handle incoming video frame
     * @param {ArrayBuffer} frameData - JPEG encoded frame data
     */
    handleFrame(frameData) {
        // Ignore frames if we're not streaming or connection is closing
        if (!this.isStreaming || !this.socket || !this.socket.connected) return;
        if (!this.ctx || !this.canvas) return;
        
        try {
            // Convert ArrayBuffer to Blob
            const blob = new Blob([frameData], { type: 'image/jpeg' });
            
            // Create object URL
            const url = URL.createObjectURL(blob);
            this.pendingUrls.add(url);
            
            // Reuse image object or create new one
            const img = this.frameImage || new Image();
            this.frameImage = img;
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
                
                // Clean up URL immediately
                URL.revokeObjectURL(url);
                this.pendingUrls.delete(url);
                
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
                // Clean up URL on error
                URL.revokeObjectURL(url);
                this.pendingUrls.delete(url);
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
        this.log('Stopping WebSocket preview...');
        
        // Set flags first to prevent race conditions
        this.isStreaming = false;
        this.isConnecting = false;
        
        // Stop stream if socket is still connected
        if (this.socket && this.socket.connected) {
            try {
                this.socket.emit('stop_stream');
            } catch (e) {
                this.log('Error sending stop_stream:', e);
            }
        }
        
        // Clean up all pending URLs
        this.pendingUrls.forEach(url => URL.revokeObjectURL(url));
        this.pendingUrls.clear();
        
        // Clean up image
        if (this.frameImage) {
            this.frameImage.src = '';
            this.frameImage = null;
        }
        
        // Disconnect and remove all listeners
        if (this.socket) {
            try {
                // Remove all event listeners to prevent stale callbacks
                this.socket.removeAllListeners();
                // Disconnect gracefully
                this.socket.disconnect();
            } catch (e) {
                this.log('Error during socket cleanup:', e);
            }
            this.socket = null;
        }
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
