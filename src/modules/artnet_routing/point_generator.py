"""
Point Generation Engine

Converts editor shape parameters to LED coordinates.
Python port of frontend/js/editor.js shape generation logic.
"""

import math
from typing import List, Tuple
from .artnet_object import ArtNetPoint


class PointGenerator:
    """Generate LED coordinates from shape parameters"""
    
    @staticmethod
    def generate_points(shape: dict) -> List[ArtNetPoint]:
        """
        Generate LED points from editor shape parameters
        
        Args:
            shape: Dictionary from editor.shapes[] (session state)
        
        Returns:
            List of ArtNetPoint with calculated coordinates
        """
        shape_type = shape['type']
        
        if shape_type == 'matrix':
            return PointGenerator._generate_matrix(shape)
        elif shape_type == 'circle':
            return PointGenerator._generate_circle(shape)
        elif shape_type == 'line':
            return PointGenerator._generate_line(shape)
        elif shape_type == 'star':
            return PointGenerator._generate_star(shape)
        elif shape_type == 'rect':
            return PointGenerator._generate_rect(shape)
        elif shape_type == 'triangle':
            return PointGenerator._generate_triangle(shape)
        elif shape_type == 'polygon':
            return PointGenerator._generate_polygon(shape)
        elif shape_type == 'arc':
            return PointGenerator._generate_arc(shape)
        else:
            raise ValueError(f"Unknown shape type: {shape_type}")
    
    @staticmethod
    def _generate_matrix(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for matrix (grid) shape"""
        rows = max(1, shape.get('rows', 4))
        cols = max(1, shape.get('cols', 4))
        pattern = shape.get('pattern', 'zigzag-left')
        size = shape.get('size', 100)
        half = size / 2
        
        # Generate all points in a 2D array
        temp_pts = []
        for r in range(rows):
            row_pts = []
            ty = 0.5 if rows == 1 else (r / (rows - 1))
            y = -half + ty * size
            
            for c in range(cols):
                tx = 0.5 if cols == 1 else (c / (cols - 1))
                x = -half + tx * size
                row_pts.append([x, y])
            
            temp_pts.append(row_pts)
        
        # Apply the selected pattern
        pts = []
        if pattern == 'zigzag-left':
            # Zigzag starting from left: row by row, alternating direction
            for r in range(rows):
                if r % 2 == 0:
                    # Even rows: left to right
                    pts.extend(temp_pts[r])
                else:
                    # Odd rows: right to left
                    pts.extend(reversed(temp_pts[r]))
        
        elif pattern == 'zigzag-right':
            # Zigzag starting from right: row by row, alternating direction
            for r in range(rows):
                if r % 2 == 0:
                    # Even rows: right to left
                    pts.extend(reversed(temp_pts[r]))
                else:
                    # Odd rows: left to right
                    pts.extend(temp_pts[r])
        
        elif pattern == 'zigzag-top':
            # Zigzag starting from top: column by column, alternating direction
            for c in range(cols):
                if c % 2 == 0:
                    # Even columns: top to bottom
                    for r in range(rows):
                        pts.append(temp_pts[r][c])
                else:
                    # Odd columns: bottom to top
                    for r in range(rows - 1, -1, -1):
                        pts.append(temp_pts[r][c])
        
        elif pattern == 'zigzag-bottom':
            # Zigzag starting from bottom: column by column, alternating direction
            for c in range(cols):
                if c % 2 == 0:
                    # Even columns: bottom to top
                    for r in range(rows - 1, -1, -1):
                        pts.append(temp_pts[r][c])
                else:
                    # Odd columns: top to bottom
                    for r in range(rows):
                        pts.append(temp_pts[r][c])
        
        else:
            # Default: raster pattern (left to right, top to bottom)
            for r in range(rows):
                pts.extend(temp_pts[r])
        
        # Convert to ArtNetPoint with world coordinates
        points = []
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        for i, (local_x, local_y) in enumerate(pts):
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_circle(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for circle shape with perimeter-based distribution"""
        count = max(1, shape.get('pointCount', 60))
        size = shape.get('size', 100)
        rx = size / 2
        ry = size / 2
        scale_x = shape.get('scaleX', 1)
        scale_y = shape.get('scaleY', 1)
        
        # Sample the circle with high resolution for accurate perimeter calculation
        sample_n = max(128, count * 6)
        samples = []
        for i in range(sample_n + 1):
            a = (i / sample_n) * math.pi * 2
            samples.append([math.cos(a) * rx, math.sin(a) * ry])
        
        # Calculate cumulative perimeter lengths
        cum = [0]
        for i in range(1, len(samples)):
            dx = (samples[i][0] - samples[i-1][0]) * scale_x
            dy = (samples[i][1] - samples[i-1][1]) * scale_y
            length = math.hypot(dx, dy)
            cum.append(cum[-1] + length)
        
        total = cum[-1]
        if total == 0:
            # Degenerate case: return first point multiple times
            x_center = shape.get('x', 0)
            y_center = shape.get('y', 0)
            return [ArtNetPoint(id=i + 1, x=x_center, y=y_center) for i in range(count)]
        
        # Distribute points evenly along perimeter
        pts = []
        for i in range(count):
            target = (i / count) * total
            
            # Find segment
            idx = 0
            while idx < len(cum) - 1 and cum[idx + 1] < target:
                idx += 1
            
            # Interpolate within segment
            seg_len = cum[idx + 1] - cum[idx]
            t = 0 if seg_len == 0 else ((target - cum[idx]) / seg_len)
            
            a = samples[idx]
            b = samples[idx + 1] if idx + 1 < len(samples) else samples[idx]
            
            local_x = a[0] + t * (b[0] - a[0])
            local_y = a[1] + t * (b[1] - a[1])
            
            pts.append([local_x, local_y])
        
        # Convert to ArtNetPoint with world coordinates
        points = []
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        for i, (local_x, local_y) in enumerate(pts):
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_line(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for line shape"""
        count = max(2, shape.get('pointCount', 50))
        size = shape.get('size', 100)
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        # Simple line from -size/2 to +size/2
        points = []
        for i in range(count):
            t = i / (count - 1) if count > 1 else 0
            local_x = -size / 2 + t * size
            local_y = 0
            
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_star(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for star shape"""
        count = max(1, shape.get('pointCount', 50))
        spikes = max(2, shape.get('spikes', 5))
        size = shape.get('size', 100)
        outer = size / 2
        inner = outer * shape.get('innerRatio', 0.5)
        
        # Generate star vertices
        verts = []
        rot = -math.pi / 2  # Start at top
        step = math.pi / spikes
        
        for i in range(spikes):
            # Outer point
            verts.append([math.cos(rot) * outer, math.sin(rot) * outer])
            rot += step
            # Inner point
            verts.append([math.cos(rot) * inner, math.sin(rot) * inner])
            rot += step
        
        # Create edges
        edges = []
        for i in range(len(verts)):
            edges.append([verts[i], verts[(i + 1) % len(verts)]])
        
        # Distribute points along edges
        pts = PointGenerator._distribute_along_edges(shape, edges, count)
        
        # Convert to ArtNetPoint
        points = []
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        for i, (local_x, local_y) in enumerate(pts):
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_rect(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for rectangle shape"""
        count = max(1, shape.get('pointCount', 40))
        size = shape.get('size', 100)
        half = size / 2
        
        # Rectangle vertices
        verts = [[-half, -half], [half, -half], [half, half], [-half, half]]
        edges = [[verts[0], verts[1]], [verts[1], verts[2]], [verts[2], verts[3]], [verts[3], verts[0]]]
        
        # Distribute points along edges
        pts = PointGenerator._distribute_along_edges(shape, edges, count)
        
        # Convert to ArtNetPoint
        points = []
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        for i, (local_x, local_y) in enumerate(pts):
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_triangle(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for triangle shape"""
        count = max(1, shape.get('pointCount', 30))
        size = shape.get('size', 100)
        half = size / 2
        
        # Triangle vertices
        verts = [[-half, half], [half, half], [0, -half]]
        edges = [[verts[0], verts[1]], [verts[1], verts[2]], [verts[2], verts[0]]]
        
        # Distribute points along edges
        pts = PointGenerator._distribute_along_edges(shape, edges, count)
        
        # Convert to ArtNetPoint
        points = []
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        for i, (local_x, local_y) in enumerate(pts):
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_polygon(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for polygon shape"""
        count = max(1, shape.get('pointCount', 40))
        sides = max(3, shape.get('sides', 6))
        size = shape.get('size', 100)
        radius = size / 2
        
        # Generate polygon vertices
        verts = []
        angle_step = (math.pi * 2) / sides
        rot = -math.pi / 2  # Start at top
        
        for i in range(sides):
            verts.append([math.cos(rot) * radius, math.sin(rot) * radius])
            rot += angle_step
        
        # Create edges
        edges = []
        for i in range(len(verts)):
            edges.append([verts[i], verts[(i + 1) % len(verts)]])
        
        # Distribute points along edges
        pts = PointGenerator._distribute_along_edges(shape, edges, count)
        
        # Convert to ArtNetPoint
        points = []
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        for i, (local_x, local_y) in enumerate(pts):
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_arc(shape: dict) -> List[ArtNetPoint]:
        """
        Generate LED points for arc shape (Bezier curves)
        
        Note: This is a simplified implementation. Full implementation would
        require handling control points from the shape data.
        """
        count = max(2, shape.get('pointCount', 50))
        size = shape.get('size', 100)
        
        # For now, generate a simple arc (quarter circle)
        # TODO: Implement full Bezier curve support with control points
        points = []
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = math.radians(shape.get('rotation', 0))
        
        for i in range(count):
            t = i / (count - 1) if count > 1 else 0
            angle = t * (math.pi / 2)  # Quarter circle
            
            local_x = math.cos(angle) * size / 2
            local_y = math.sin(angle) * size / 2
            
            # Apply rotation
            if rotation != 0:
                cos_r = math.cos(rotation)
                sin_r = math.sin(rotation)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
            else:
                rotated_x = local_x
                rotated_y = local_y
            
            # Translate to world coordinates
            world_x = x_center + rotated_x
            world_y = y_center + rotated_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _distribute_along_edges(shape: dict, edges: List[Tuple], count: int) -> List[List[float]]:
        """
        Distribute points evenly along a series of edges
        
        Args:
            shape: Shape dictionary (for scale information)
            edges: List of edge pairs [[x1,y1], [x2,y2]]
            count: Number of points to distribute
        
        Returns:
            List of [x, y] coordinate pairs
        """
        scale_x = shape.get('scaleX', 1)
        scale_y = shape.get('scaleY', 1)
        
        # Calculate edge lengths
        lengths = []
        for a, b in edges:
            dx = (b[0] - a[0]) * scale_x
            dy = (b[1] - a[1]) * scale_y
            lengths.append(math.hypot(dx, dy))
        
        perimeter = sum(lengths)
        
        if perimeter == 0:
            # Degenerate case: return first point multiple times
            return [edges[0][0][:] for _ in range(count)]
        
        step = perimeter / count
        points = []
        dist = 0
        
        for i in range(count):
            remaining = dist
            
            for ei, (a, b) in enumerate(edges):
                length = lengths[ei]
                
                if remaining <= length:
                    t = 0 if length == 0 else (remaining / length)
                    x = a[0] + t * (b[0] - a[0])
                    y = a[1] + t * (b[1] - a[1])
                    points.append([x, y])
                    break
                
                remaining -= length
            
            dist += step
        
        return points
