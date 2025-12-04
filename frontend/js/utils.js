/**
 * Utility Functions
 * Hilfsfunktionen für den Editor
 */

import { setNeedsRedraw } from './state.js';

export function markForRedraw() { 
    setNeedsRedraw(true); 
}

/**
 * Transform from local shape coordinates to world (canvas) coordinates
 */
export function localToWorld(s, lx, ly) {
    const cosA = Math.cos(s.rotation);
    const sinA = Math.sin(s.rotation);
    const wx = s.x + (lx * s.scaleX * cosA - ly * s.scaleY * sinA);
    const wy = s.y + (lx * s.scaleX * sinA + ly * s.scaleY * cosA);
    return [wx, wy];
}

/**
 * Transform from world (canvas) coordinates to local shape coordinates
 */
export function worldToLocal(s, wx, wy) {
    const dx = wx - s.x;
    const dy = wy - s.y;
    const cosA = Math.cos(s.rotation);
    const sinA = Math.sin(s.rotation);
    const lx = (dx * cosA + dy * sinA) / s.scaleX;
    const ly = (-dx * sinA + dy * cosA) / s.scaleY;
    return [lx, ly];
}

/**
 * Calculate world-space distance between two local points
 */
export function worldLenBetweenLocal(s, p1, p2) {
    const [wx1, wy1] = localToWorld(s, p1[0], p1[1]);
    const [wx2, wy2] = localToWorld(s, p2[0], p2[1]);
    return Math.hypot(wx2 - wx1, wy2 - wy1);
}

/**
 * Distribute points evenly along edges
 */
export function distributeAlongEdges(s, edges, count) {
    const pts = [];
    const segLengths = edges.map(([a, b]) => worldLenBetweenLocal(s, a, b));
    const total = segLengths.reduce((sum, len) => sum + len, 0);
    
    if (total === 0) return edges.map(([a]) => a).slice(0, count);
    
    for (let i = 0; i < count; i++) {
        const target = (i / count) * total;
        let cumulative = 0, segIndex = 0;
        
        while (segIndex < segLengths.length && cumulative + segLengths[segIndex] < target) {
            cumulative += segLengths[segIndex];
            segIndex++;
        }
        
        if (segIndex >= edges.length) segIndex = edges.length - 1;
        
        const segLen = segLengths[segIndex];
        const t = segLen === 0 ? 0 : ((target - cumulative) / segLen);
        const [a, b] = edges[segIndex];
        pts.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
    }
    
    return pts;
}
