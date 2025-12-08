/**
 * WebRTC Preview Client
 * Hardware-accelerated video streaming with automatic MJPEG fallback
 * 
 * Performance Improvement vs MJPEG:
 * - CPU Usage: ~40-60% → ~5-10% (10x reduction)
 * - Bandwidth: 2-5 Mbps → 0.2-1 Mbps (5x reduction)
 * - Latency: ~100-200ms → <100ms
 */

class WebRTCPreview {
    constructor(videoElementId, options = {}) {
        this.videoElement = document.getElementById(videoElementId);
        this.apiBase = options.apiBase || '';  // API base URL
        this.options = {
            quality: options.quality || 'medium',  // low, medium, high
            playerId: options.playerId || 'video', // video, artnet
            autoStart: options.autoStart !== false,
            fallbackToMJPEG: options.fallbackToMJPEG !== false,
            onStateChange: options.onStateChange || null,
            onStats: options.onStats || null,
            ...options
        };
        
        this.pc = null;  // RTCPeerConnection
        this.connectionId = null;
        this.isConnected = false;
        this.useWebRTC = true;  // Try WebRTC first, fallback to MJPEG if fails
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.statsInterval = null;
        
        // MJPEG fallback
        this.mjpegImg = null;
        this.mjpegInterval = null;
        
        console.log('WebRTC Preview initialized:', this.options);
        
        if (this.options.autoStart) {
            this.start();
        }
    }
    
    /**
     * Start video preview (WebRTC or MJPEG fallback)
     */
    async start() {
        if (this.useWebRTC) {
            try {
                await this.startWebRTC();
            } catch (error) {
                console.error('WebRTC failed, falling back to MJPEG:', error);
                if (this.options.fallbackToMJPEG) {
                    this.useWebRTC = false;
                    this.startMJPEG();
                }
            }
        } else {
            this.startMJPEG();
        }
    }
    
    /**
     * Start WebRTC connection
     */
    async startWebRTC() {
        console.log('Starting WebRTC preview...');
        this._updateState('connecting');
        
        // Close any existing connection first
        if (this.pc) {
            try {
                this.pc.close();
            } catch (e) {
                console.warn('Error closing old connection:', e);
            }
            this.pc = null;
        }
        
        // Notify server to cleanup old connection if exists
        if (this.connectionId) {
            try {
                await fetch(`${this.apiBase}/api/webrtc/close`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ connection_id: this.connectionId })
                });
            } catch (e) {
                console.warn('Error notifying server of connection close:', e);
            }
            this.connectionId = null;
        }
        
        try {
            // Create RTCPeerConnection
            // LAN-only mode: no STUN servers needed, uses host candidates only
            this.pc = new RTCPeerConnection({
                iceServers: []  // Empty for LAN - much faster connection
            });
            
            // Handle incoming video track
            this.pc.ontrack = (event) => {
                console.log('WebRTC: Video track received');
                if (this.videoElement) {
                    this.videoElement.srcObject = event.streams[0];
                    this.videoElement.play().catch(e => {
                        console.warn('Auto-play failed:', e);
                    });
                }
            };
            
            // Handle connection state changes
            this.pc.onconnectionstatechange = () => {
                console.log('WebRTC connection state:', this.pc.connectionState);
                this._updateState(this.pc.connectionState);
                
                if (this.pc.connectionState === 'connected') {
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    this.startStatsMonitoring();
                } else if (this.pc.connectionState === 'failed' || this.pc.connectionState === 'closed') {
                    this.isConnected = false;
                    this.stopStatsMonitoring();
                    this.handleConnectionFailure();
                }
            };
            
            this.pc.oniceconnectionstatechange = () => {
                console.log('ICE connection state:', this.pc.iceConnectionState);
            };
            
            // Add transceiver to receive video from server
            this.pc.addTransceiver('video', { direction: 'recvonly' });
            
            // Create offer
            const offer = await this.pc.createOffer();
            await this.pc.setLocalDescription(offer);
            
            // Send offer to server
            const response = await fetch(`${this.apiBase}/api/webrtc/offer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sdp: offer.sdp,
                    type: offer.type,
                    quality: this.options.quality,
                    player_id: this.options.playerId
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            const answer = await response.json();
            
            if (!answer.success) {
                throw new Error(answer.error || 'Server rejected offer');
            }
            
            this.connectionId = answer.connection_id;
            console.log('WebRTC: Answer received, connection_id:', this.connectionId);
            console.log('Quality settings:', {
                quality: answer.quality,
                resolution: answer.resolution,
                fps: answer.fps
            });
            console.log('Answer SDP (first 500 chars):', answer.sdp.substring(0, 500));
            
            // Set remote description (answer)
            console.log('Setting remote description...');
            try {
                await this.pc.setRemoteDescription(new RTCSessionDescription({
                    sdp: answer.sdp,
                    type: answer.type
                }));
                console.log('Remote description set successfully');
                console.log('ICE connection state after setRemoteDescription:', this.pc.iceConnectionState);
                console.log('Connection state after setRemoteDescription:', this.pc.connectionState);
            } catch (e) {
                console.error('Failed to set remote description:', e);
                throw e;
            }
            
            console.log('WebRTC: Connection established');
            
        } catch (error) {
            console.error('WebRTC setup error:', error);
            if (this.pc) {
                this.pc.close();
                this.pc = null;
            }
            throw error;
        }
    }
    
    /**
     * Start MJPEG fallback
     */
    startMJPEG() {
        console.log('Starting MJPEG fallback preview...');
        this._updateState('mjpeg_fallback');
        
        // Create img element for MJPEG
        if (!this.mjpegImg) {
            this.mjpegImg = document.createElement('img');
            this.mjpegImg.style.width = '100%';
            this.mjpegImg.style.height = '100%';
            this.mjpegImg.style.objectFit = 'contain';
            
            // Replace video element with img
            if (this.videoElement && this.videoElement.parentNode) {
                this.videoElement.parentNode.replaceChild(this.mjpegImg, this.videoElement);
                this.videoElement = this.mjpegImg;
            }
        }
        
        // Start polling MJPEG endpoint
        const updateMJPEG = () => {
            const endpoint = this.options.playerId === 'artnet' ? '/preview/artnet' : '/preview';
            this.mjpegImg.src = `${this.apiBase}${endpoint}?t=${Date.now()}`;
        };
        
        updateMJPEG();
        this.mjpegInterval = setInterval(updateMJPEG, 100);  // 10 FPS
        
        this.isConnected = true;
    }
    
    /**
     * Stop video preview
     */
    async stop() {
        console.log('Stopping video preview...');
        
        if (this.useWebRTC && this.pc) {
            try {
                // Notify server to close connection
                if (this.connectionId) {
                    await fetch(`${this.apiBase}/api/webrtc/close`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ connection_id: this.connectionId })
                    });
                }
                
                // Close peer connection
                this.pc.close();
                this.pc = null;
                this.connectionId = null;
            } catch (error) {
                console.error('Error closing WebRTC:', error);
            }
        }
        
        if (this.mjpegInterval) {
            clearInterval(this.mjpegInterval);
            this.mjpegInterval = null;
        }
        
        this.stopStatsMonitoring();
        this.isConnected = false;
        this._updateState('stopped');
    }
    
    /**
     * Change quality (requires reconnection)
     */
    async changeQuality(quality) {
        if (!['low', 'medium', 'high'].includes(quality)) {
            console.error('Invalid quality:', quality);
            return false;
        }
        
        console.log('Changing quality to:', quality);
        this.options.quality = quality;
        
        if (this.isConnected) {
            await this.stop();
            await this.start();
        }
        
        return true;
    }
    
    /**
     * Handle connection failure
     */
    handleConnectionFailure() {
        this.reconnectAttempts++;
        
        if (this.reconnectAttempts <= this.maxReconnectAttempts) {
            console.log(`Reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}...`);
            // Stop and cleanup before reconnecting
            setTimeout(async () => {
                await this.stop();
                await this.start();
            }, 2000 * this.reconnectAttempts);
        } else {
            console.error('Max reconnect attempts reached');
            if (this.options.fallbackToMJPEG && !this.mjpegInterval) {
                console.log('Falling back to MJPEG');
                this.useWebRTC = false;
                this.stop().then(() => this.startMJPEG());
            }
        }
    }
    
    /**
     * Start stats monitoring
     */
    startStatsMonitoring() {
        if (this.statsInterval) return;
        
        this.statsInterval = setInterval(async () => {
            if (!this.pc || !this.isConnected) {
                this.stopStatsMonitoring();
                return;
            }
            
            try {
                const stats = await this.pc.getStats();
                const inboundStats = Array.from(stats.values()).find(s => s.type === 'inbound-rtp' && s.kind === 'video');
                
                if (inboundStats && this.options.onStats) {
                    const statsData = {
                        bytesReceived: inboundStats.bytesReceived || 0,
                        framesReceived: inboundStats.framesReceived || 0,
                        framesDecoded: inboundStats.framesDecoded || 0,
                        framesDropped: inboundStats.framesDropped || 0,
                        timestamp: inboundStats.timestamp || Date.now()
                    };
                    
                    this.options.onStats(statsData);
                }
            } catch (error) {
                console.error('Stats error:', error);
            }
        }, 2000);  // Update every 2 seconds
    }
    
    /**
     * Stop stats monitoring
     */
    stopStatsMonitoring() {
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
            this.statsInterval = null;
        }
    }
    
    /**
     * Update connection state
     */
    _updateState(state) {
        if (this.options.onStateChange) {
            this.options.onStateChange(state);
        }
    }
    
    /**
     * Get current status
     */
    getStatus() {
        return {
            isConnected: this.isConnected,
            useWebRTC: this.useWebRTC,
            quality: this.options.quality,
            playerId: this.options.playerId,
            connectionId: this.connectionId,
            connectionState: this.pc?.connectionState || (this.mjpegInterval ? 'mjpeg' : 'disconnected')
        };
    }
}

// Export for use in player.js
window.WebRTCPreview = WebRTCPreview;
