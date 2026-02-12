"""
Test Script for ArtNet Routing Backend Implementation

Tests Phase 1: Core Data Models
- ArtNetPoint: Serialization, coordinate handling
- ArtNetObject: Full serialization, LED types, universe calculations
- ArtNetOutput: Network configuration, assignments

Tests Phase 2: Point Generation
- Matrix: Grid patterns (zigzag-left, zigzag-right, etc.)
- Circle: Perimeter-based distribution
- Line: Linear LED strips
- Star: Multi-spike shapes
- Rect/Triangle/Polygon: Edge-based distribution

Tests Phase 3: Routing Manager
- Initialization: Manager setup with session state
- Sync: Generate objects from editor shapes
- Object CRUD: Create/Read/Update/Delete operations
- Output CRUD: Create/Read/Update/Delete operations
- Assignments: Many-to-many object-to-output routing
- Delete Cascade: Cleanup on object deletion
- State Persistence: Serialization/deserialization
- Shape Updates: Regenerate points while preserving config

Run: python tests/test_artnet_routing.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.artnet_routing.artnet_object import ArtNetPoint, ArtNetObject
from src.modules.artnet_routing.artnet_output import ArtNetOutput
from src.modules.artnet_routing.point_generator import PointGenerator
from src.modules.artnet_routing.artnet_routing_manager import ArtNetRoutingManager

# Test Results
test_results = []

# Mock SessionStateManager for testing
class MockSessionStateManager:
    """Mock session state manager for testing routing manager"""
    def __init__(self):
        self._state = {}
    
    def get_state(self, key):
        return self._state.get(key)
    
    def set_state(self, key, value):
        self._state[key] = value


def log_test(name, passed, message=""):
    """Log test result."""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status} - {name}"
    if message:
        result += f": {message}"
    print(result)
    test_results.append({"name": name, "passed": passed, "message": message})


def print_section(title):
    """Print section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


# =============================================================================
# ArtNetPoint Tests
# =============================================================================

def test_artnet_point_creation():
    """Test ArtNetPoint creation with coordinates."""
    print_section("ArtNetPoint Tests")
    
    try:
        point = ArtNetPoint(id=1, x=100.5, y=200.75)
        
        assert point.id == 1, "ID should be 1"
        assert point.x == 100.5, "X should be 100.5"
        assert point.y == 200.75, "Y should be 200.75"
        
        log_test("ArtNetPoint creation", True)
        return True
    except Exception as e:
        log_test("ArtNetPoint creation", False, str(e))
        return False


def test_artnet_point_serialization():
    """Test ArtNetPoint to_dict() and from_dict()."""
    try:
        # Create point
        point = ArtNetPoint(id=42, x=150.0, y=250.0)
        
        # Serialize
        data = point.to_dict()
        
        assert data['id'] == 42, "Serialized ID should match"
        assert data['x'] == 150.0, "Serialized X should match"
        assert data['y'] == 250.0, "Serialized Y should match"
        
        # Deserialize
        point2 = ArtNetPoint.from_dict(data)
        
        assert point2.id == point.id, "Deserialized ID should match original"
        assert point2.x == point.x, "Deserialized X should match original"
        assert point2.y == point.y, "Deserialized Y should match original"
        
        log_test("ArtNetPoint serialization round-trip", True)
        return True
    except Exception as e:
        log_test("ArtNetPoint serialization round-trip", False, str(e))
        return False


# =============================================================================
# ArtNetObject Tests
# =============================================================================

def test_artnet_object_creation_rgb():
    """Test ArtNetObject creation with RGB LED type."""
    print_section("ArtNetObject Tests - RGB")
    
    try:
        points = [
            ArtNetPoint(id=1, x=0.0, y=0.0),
            ArtNetPoint(id=2, x=10.0, y=0.0),
            ArtNetPoint(id=3, x=20.0, y=0.0)
        ]
        
        obj = ArtNetObject(
            id="obj-test-1",
            name="Test Matrix",
            source_shape_id="shape-1",
            type="matrix",
            points=points,
            led_type='RGB',
            channels_per_pixel=3,
            channel_order='RGB',
            universe_start=1,
            universe_end=1
        )
        
        assert obj.id == "obj-test-1", "ID should match"
        assert obj.name == "Test Matrix", "Name should match"
        assert obj.led_type == 'RGB', "LED type should be RGB"
        assert obj.channels_per_pixel == 3, "RGB should use 3 channels"
        assert len(obj.points) == 3, "Should have 3 points"
        
        log_test("ArtNetObject creation (RGB)", True)
        return True
    except Exception as e:
        log_test("ArtNetObject creation (RGB)", False, str(e))
        return False


def test_artnet_object_creation_rgbw():
    """Test ArtNetObject creation with RGBW LED type (white channel)."""
    try:
        points = [ArtNetPoint(id=i, x=i*10.0, y=0.0) for i in range(1, 6)]
        
        obj = ArtNetObject(
            id="obj-test-2",
            name="RGBW Strip",
            source_shape_id="shape-2",
            type="line",
            points=points,
            led_type='RGBW',
            channels_per_pixel=4,
            channel_order='RGBW',
            universe_start=1,
            universe_end=1,
            white_detection=True,
            white_mode='luminance',
            white_threshold=200,
            white_behavior='hybrid'
        )
        
        assert obj.led_type == 'RGBW', "LED type should be RGBW"
        assert obj.channels_per_pixel == 4, "RGBW should use 4 channels"
        assert obj.white_detection == True, "White detection should be enabled"
        assert obj.white_mode == 'luminance', "White mode should be luminance"
        
        log_test("ArtNetObject creation (RGBW)", True)
        return True
    except Exception as e:
        log_test("ArtNetObject creation (RGBW)", False, str(e))
        return False


def test_artnet_object_serialization():
    """Test ArtNetObject full serialization."""
    try:
        points = [
            ArtNetPoint(id=1, x=0.0, y=0.0),
            ArtNetPoint(id=2, x=100.0, y=100.0)
        ]
        
        obj = ArtNetObject(
            id="obj-serialize",
            name="Serialization Test",
            source_shape_id="shape-serial",
            type="circle",
            points=points,
            led_type='RGBAW',
            channels_per_pixel=5,
            channel_order='RGBAW',
            universe_start=2,
            universe_end=3,
            white_detection=True,
            white_mode='minimum',
            white_threshold=180,
            white_behavior='replace',
            color_temp=4500,
            brightness=10,
            contrast=-5,
            red=0,
            green=5,
            blue=-10,
            delay=50,
            input_layer='layer1',
            master_id='obj-master-123'
        )
        
        # Serialize
        data = obj.to_dict()
        
        assert data['id'] == "obj-serialize", "Serialized ID should match"
        assert data['ledType'] == 'RGBAW', "LED type should match"
        assert data['channelsPerPixel'] == 5, "Channels should match"
        assert len(data['points']) == 2, "Should have 2 points"
        assert data['whiteDetection'] == True, "White detection should match"
        assert data['whiteMode'] == 'minimum', "White mode should match"
        assert data['inputLayer'] == 'layer1', "Input layer should match"
        assert data['masterId'] == 'obj-master-123', "Master ID should match"
        
        # Deserialize
        obj2 = ArtNetObject.from_dict(data)
        
        assert obj2.id == obj.id, "Deserialized ID should match"
        assert obj2.led_type == obj.led_type, "LED type should match"
        assert obj2.channels_per_pixel == obj.channels_per_pixel, "Channels should match"
        assert len(obj2.points) == len(obj.points), "Point count should match"
        assert obj2.white_detection == obj.white_detection, "White detection should match"
        assert obj2.input_layer == obj.input_layer, "Input layer should match"
        assert obj2.master_id == obj.master_id, "Master ID should match"
        
        log_test("ArtNetObject full serialization round-trip", True)
        return True
    except Exception as e:
        log_test("ArtNetObject full serialization round-trip", False, str(e))
        return False


def test_universe_calculations_rgb():
    """Test universe range calculation for RGB LEDs."""
    print_section("Universe Calculation Tests")
    
    try:
        # RGB: 3 channels per pixel, 510 channels per universe = 170 pixels per universe
        points = [ArtNetPoint(id=i, x=i*10.0, y=0.0) for i in range(1, 171)]  # 170 pixels
        
        obj = ArtNetObject(
            id="obj-universe-1",
            name="Universe Test RGB",
            source_shape_id="shape-u1",
            type="matrix",
            points=points,
            led_type='RGB',
            channels_per_pixel=3,
            channel_order='RGB',
            universe_start=1,
            universe_end=1
        )
        
        # Calculate max pixels per universe
        max_pixels = obj.get_max_pixels_per_universe()
        assert max_pixels == 170, f"RGB should fit 170 pixels per universe, got {max_pixels}"
        
        # Calculate required universe range
        start, end = obj.calculate_universe_range()
        assert start == 1, f"Start universe should be 1, got {start}"
        assert end == 1, f"End universe should be 1 for 170 pixels, got {end}"
        
        log_test("Universe calculation (RGB, 170 pixels = 1 universe)", True)
        return True
    except Exception as e:
        log_test("Universe calculation (RGB, 170 pixels = 1 universe)", False, str(e))
        return False


def test_universe_calculations_rgb_multi():
    """Test universe range calculation for RGB LEDs spanning multiple universes."""
    try:
        # RGB: 3 channels per pixel, 510 channels per universe = 170 pixels per universe
        # 340 pixels = 2 universes
        points = [ArtNetPoint(id=i, x=i*10.0, y=0.0) for i in range(1, 341)]  # 340 pixels
        
        obj = ArtNetObject(
            id="obj-universe-2",
            name="Universe Test RGB Multi",
            source_shape_id="shape-u2",
            type="matrix",
            points=points,
            led_type='RGB',
            channels_per_pixel=3,
            channel_order='RGB',
            universe_start=1,
            universe_end=2
        )
        
        start, end = obj.calculate_universe_range()
        assert start == 1, f"Start universe should be 1, got {start}"
        assert end == 2, f"End universe should be 2 for 340 pixels, got {end}"
        
        log_test("Universe calculation (RGB, 340 pixels = 2 universes)", True)
        return True
    except Exception as e:
        log_test("Universe calculation (RGB, 340 pixels = 2 universes)", False, str(e))
        return False


def test_universe_calculations_rgbw():
    """Test universe range calculation for RGBW LEDs."""
    try:
        # RGBW: 4 channels per pixel, 510 channels per universe = 127 pixels per universe
        points = [ArtNetPoint(id=i, x=i*10.0, y=0.0) for i in range(1, 128)]  # 127 pixels
        
        obj = ArtNetObject(
            id="obj-universe-3",
            name="Universe Test RGBW",
            source_shape_id="shape-u3",
            type="line",
            points=points,
            led_type='RGBW',
            channels_per_pixel=4,
            channel_order='RGBW',
            universe_start=1,
            universe_end=1
        )
        
        max_pixels = obj.get_max_pixels_per_universe()
        assert max_pixels == 127, f"RGBW should fit 127 pixels per universe, got {max_pixels}"
        
        start, end = obj.calculate_universe_range()
        assert start == 1, f"Start universe should be 1, got {start}"
        assert end == 1, f"End universe should be 1 for 127 pixels, got {end}"
        
        log_test("Universe calculation (RGBW, 127 pixels = 1 universe)", True)
        return True
    except Exception as e:
        log_test("Universe calculation (RGBW, 127 pixels = 1 universe)", False, str(e))
        return False


def test_universe_calculations_rgbcww():
    """Test universe range calculation for RGBCWW LEDs (6 channels)."""
    try:
        # RGBCWW: 6 channels per pixel, 510 channels per universe = 85 pixels per universe
        points = [ArtNetPoint(id=i, x=i*10.0, y=0.0) for i in range(1, 86)]  # 85 pixels
        
        obj = ArtNetObject(
            id="obj-universe-4",
            name="Universe Test RGBCWW",
            source_shape_id="shape-u4",
            type="star",
            points=points,
            led_type='RGBCWW',
            channels_per_pixel=6,
            channel_order='RGBCWW',
            universe_start=1,
            universe_end=1
        )
        
        max_pixels = obj.get_max_pixels_per_universe()
        assert max_pixels == 85, f"RGBCWW should fit 85 pixels per universe, got {max_pixels}"
        
        start, end = obj.calculate_universe_range()
        assert start == 1, f"Start universe should be 1, got {start}"
        assert end == 1, f"End universe should be 1 for 85 pixels, got {end}"
        
        log_test("Universe calculation (RGBCWW, 85 pixels = 1 universe)", True)
        return True
    except Exception as e:
        log_test("Universe calculation (RGBCWW, 85 pixels = 1 universe)", False, str(e))
        return False


# =============================================================================
# ArtNetOutput Tests
# =============================================================================

def test_artnet_output_creation():
    """Test ArtNetOutput creation with network configuration."""
    print_section("ArtNetOutput Tests")
    
    try:
        output = ArtNetOutput(
            id="out-test-1",
            name="Main LED Wall",
            target_ip="192.168.1.10",
            subnet="255.255.255.0",
            start_universe=1,
            fps=30,
            delay=0,
            active=True
        )
        
        assert output.id == "out-test-1", "ID should match"
        assert output.name == "Main LED Wall", "Name should match"
        assert output.target_ip == "192.168.1.10", "IP should match"
        assert output.start_universe == 1, "Start universe should match"
        assert output.fps == 30, "FPS should match"
        assert output.active == True, "Active should be True"
        assert len(output.assigned_objects) == 0, "Should start with no assigned objects"
        
        log_test("ArtNetOutput creation", True)
        return True
    except Exception as e:
        log_test("ArtNetOutput creation", False, str(e))
        return False


def test_artnet_output_serialization():
    """Test ArtNetOutput full serialization."""
    try:
        output = ArtNetOutput(
            id="out-serialize",
            name="Serialization Test Output",
            target_ip="10.0.0.50",
            subnet="255.255.0.0",
            start_universe=5,
            fps=60,
            delay=100,
            active=False,
            brightness=20,
            contrast=-10,
            red=5,
            green=-5,
            blue=10,
            delta_enabled=True,
            delta_threshold=10,
            full_frame_interval=60,
            assigned_objects=["obj-1", "obj-2", "obj-3"]
        )
        
        # Serialize
        data = output.to_dict()
        
        assert data['id'] == "out-serialize", "ID should match"
        assert data['targetIP'] == "10.0.0.50", "IP should match"
        assert data['startUniverse'] == 5, "Start universe should match"
        assert data['fps'] == 60, "FPS should match"
        assert data['delay'] == 100, "Delay should match"
        assert data['active'] == False, "Active should match"
        assert data['brightness'] == 20, "Brightness should match"
        assert data['deltaEnabled'] == True, "Delta enabled should match"
        assert len(data['assignedObjects']) == 3, "Should have 3 assigned objects"
        
        # Deserialize
        output2 = ArtNetOutput.from_dict(data)
        
        assert output2.id == output.id, "IDs should match"
        assert output2.target_ip == output.target_ip, "IPs should match"
        assert output2.fps == output.fps, "FPS should match"
        assert output2.delta_enabled == output.delta_enabled, "Delta enabled should match"
        assert len(output2.assigned_objects) == len(output.assigned_objects), "Assigned objects count should match"
        
        log_test("ArtNetOutput full serialization round-trip", True)
        return True
    except Exception as e:
        log_test("ArtNetOutput full serialization round-trip", False, str(e))
        return False


def test_artnet_output_assignments():
    """Test ArtNet object assignment management."""
    try:
        output = ArtNetOutput(
            id="out-assign",
            name="Assignment Test",
            target_ip="192.168.1.20",
            subnet="255.255.255.0",
            start_universe=1
        )
        
        # Initially empty
        assert len(output.assigned_objects) == 0, "Should start empty"
        
        # Manually add objects (assignment logic will be in routing manager)
        output.assigned_objects.append("obj-1")
        output.assigned_objects.append("obj-2")
        
        assert len(output.assigned_objects) == 2, "Should have 2 assignments"
        assert "obj-1" in output.assigned_objects, "Should contain obj-1"
        assert "obj-2" in output.assigned_objects, "Should contain obj-2"
        
        # Remove assignment
        output.assigned_objects.remove("obj-1")
        assert len(output.assigned_objects) == 1, "Should have 1 assignment left"
        assert "obj-2" in output.assigned_objects, "Should still contain obj-2"
        
        log_test("ArtNetOutput assignment management", True)
        return True
    except Exception as e:
        log_test("ArtNetOutput assignment management", False, str(e))
        return False


# =============================================================================
# Integration Tests
# =============================================================================

def test_integration_object_output_workflow():
    """Test complete workflow: create object and output, assign."""
    print_section("Integration Tests")
    
    try:
        # Create object
        points = [ArtNetPoint(id=i, x=i*5.0, y=i*5.0) for i in range(1, 51)]
        
        obj = ArtNetObject(
            id="obj-workflow",
            name="Workflow Test Object",
            source_shape_id="shape-wf",
            type="circle",
            points=points,
            led_type='RGB',
            channels_per_pixel=3,
            channel_order='RGB',
            universe_start=1,
            universe_end=1
        )
        
        # Create output
        output = ArtNetOutput(
            id="out-workflow",
            name="Workflow Test Output",
            target_ip="192.168.1.100",
            subnet="255.255.255.0",
            start_universe=1
        )
        
        # Assign object to output
        output.assigned_objects.append(obj.id)
        
        # Verify assignment
        assert obj.id in output.assigned_objects, "Object should be assigned to output"
        
        # Serialize both
        obj_data = obj.to_dict()
        output_data = output.to_dict()
        
        # Deserialize both
        obj2 = ArtNetObject.from_dict(obj_data)
        output2 = ArtNetOutput.from_dict(output_data)
        
        # Verify assignment persists
        assert obj2.id in output2.assigned_objects, "Assignment should persist through serialization"
        
        log_test("Complete object-output workflow", True)
        return True
    except Exception as e:
        log_test("Complete object-output workflow", False, str(e))
        return False


# =============================================================================
# Point Generation Tests
# =============================================================================

def test_point_generation_matrix():
    """Test matrix point generation with zigzag patterns."""
    print_section("Point Generation Tests - Matrix")
    
    try:
        # 3x3 matrix with zigzag-left pattern
        shape = {
            'type': 'matrix',
            'rows': 3,
            'cols': 3,
            'pattern': 'zigzag-left',
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 9, f"Should generate 9 points, got {len(points)}"
        assert all(isinstance(p, ArtNetPoint) for p in points), "All points should be ArtNetPoint instances"
        
        # Check IDs are sequential
        for i, p in enumerate(points):
            assert p.id == i + 1, f"Point {i} should have ID {i + 1}, got {p.id}"
        
        # First point should be top-left (-50, -50)
        assert abs(points[0].x - (-50)) < 0.1, f"First point X should be -50, got {points[0].x}"
        assert abs(points[0].y - (-50)) < 0.1, f"First point Y should be -50, got {points[0].y}"
        
        log_test("Matrix generation (3x3 zigzag-left)", True)
        return True
    except Exception as e:
        log_test("Matrix generation (3x3 zigzag-left)", False, str(e))
        return False


def test_point_generation_matrix_zigzag_right():
    """Test matrix with zigzag-right pattern."""
    try:
        shape = {
            'type': 'matrix',
            'rows': 2,
            'cols': 4,
            'pattern': 'zigzag-right',
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 8, f"Should generate 8 points (2x4), got {len(points)}"
        
        # First point should be top-right with zigzag-right
        assert points[0].x > 0, "First point should be on right side"
        
        log_test("Matrix generation (zigzag-right)", True)
        return True
    except Exception as e:
        log_test("Matrix generation (zigzag-right)", False, str(e))
        return False


def test_point_generation_circle():
    """Test circle point generation with perimeter distribution."""
    print_section("Point Generation Tests - Circle")
    
    try:
        shape = {
            'type': 'circle',
            'pointCount': 60,
            'size': 100,
            'x': 200,
            'y': 300,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 60, f"Should generate 60 points, got {len(points)}"
        
        # Check points are roughly on a circle centered at (200, 300)
        radius = 50  # size / 2
        for p in points:
            dist = ((p.x - 200) ** 2 + (p.y - 300) ** 2) ** 0.5
            assert abs(dist - radius) < 1.0, f"Point distance from center should be ~{radius}, got {dist}"
        
        log_test("Circle generation (60 points, radius 50)", True)
        return True
    except Exception as e:
        log_test("Circle generation (60 points, radius 50)", False, str(e))
        return False


def test_point_generation_circle_ellipse():
    """Test circle with non-uniform scaling (ellipse)."""
    try:
        shape = {
            'type': 'circle',
            'pointCount': 40,
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0,
            'scaleX': 2,  # Ellipse: 2x width
            'scaleY': 0.5  # 0.5x height
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 40, f"Should generate 40 points, got {len(points)}"
        
        # Points should be distributed along ellipse perimeter
        # (not just uniformly in angle)
        
        log_test("Circle generation (ellipse with scaleX=2, scaleY=0.5)", True)
        return True
    except Exception as e:
        log_test("Circle generation (ellipse with scaleX=2, scaleY=0.5)", False, str(e))
        return False


def test_point_generation_line():
    """Test line point generation."""
    print_section("Point Generation Tests - Line")
    
    try:
        shape = {
            'type': 'line',
            'pointCount': 50,
            'size': 200,
            'x': 100,
            'y': 50,
            'rotation': 45  # 45 degrees
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 50, f"Should generate 50 points, got {len(points)}"
        
        # Line should span from -100 to +100 (size/2 in each direction)
        # After rotation, points should be distributed along the rotated line
        
        # Check first and last points
        # First point should be at start of line
        # Last point should be at end of line
        
        log_test("Line generation (50 points, 200 length, 45° rotation)", True)
        return True
    except Exception as e:
        log_test("Line generation (50 points, 200 length, 45° rotation)", False, str(e))
        return False


def test_point_generation_star():
    """Test star point generation."""
    print_section("Point Generation Tests - Star")
    
    try:
        shape = {
            'type': 'star',
            'pointCount': 50,
            'spikes': 5,
            'size': 100,
            'innerRatio': 0.5,
            'x': 0,
            'y': 0,
            'rotation': 0
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 50, f"Should generate 50 points, got {len(points)}"
        
        # Star should have points distributed along its perimeter
        # (alternating outer and inner vertices)
        
        log_test("Star generation (5 spikes, 50 points)", True)
        return True
    except Exception as e:
        log_test("Star generation (5 spikes, 50 points)", False, str(e))
        return False


def test_point_generation_rect():
    """Test rectangle point generation."""
    print_section("Point Generation Tests - Rect")
    
    try:
        shape = {
            'type': 'rect',
            'pointCount': 40,
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 40, f"Should generate 40 points, got {len(points)}"
        
        # Rectangle should have points distributed along its perimeter
        
        log_test("Rectangle generation (40 points)", True)
        return True
    except Exception as e:
        log_test("Rectangle generation (40 points)", False, str(e))
        return False


def test_point_generation_triangle():
    """Test triangle point generation."""
    try:
        shape = {
            'type': 'triangle',
            'pointCount': 30,
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 30, f"Should generate 30 points, got {len(points)}"
        
        log_test("Triangle generation (30 points)", True)
        return True
    except Exception as e:
        log_test("Triangle generation (30 points)", False, str(e))
        return False


def test_point_generation_polygon():
    """Test polygon point generation."""
    try:
        shape = {
            'type': 'polygon',
            'pointCount': 40,
            'sides': 6,  # Hexagon
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1
        }
        
        points = PointGenerator.generate_points(shape)
        
        assert len(points) == 40, f"Should generate 40 points, got {len(points)}"
        
        log_test("Polygon generation (hexagon, 40 points)", True)
        return True
    except Exception as e:
        log_test("Polygon generation (hexagon, 40 points)", False, str(e))
        return False


def test_point_generation_with_rotation():
    """Test point generation with rotation applied."""
    print_section("Point Generation Tests - Rotation")
    
    try:
        # Matrix without rotation
        shape_0 = {
            'type': 'matrix',
            'rows': 2,
            'cols': 2,
            'pattern': 'raster',
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0
        }
        
        points_0 = PointGenerator.generate_points(shape_0)
        
        # Matrix with 90 degree rotation
        shape_90 = {**shape_0, 'rotation': 90}
        points_90 = PointGenerator.generate_points(shape_90)
        
        # Rotated coordinates should be different
        assert abs(points_0[0].x - points_90[0].x) > 1.0 or abs(points_0[0].y - points_90[0].y) > 1.0, \
            "Rotation should change coordinates"
        
        log_test("Point generation with rotation (90°)", True)
        return True
    except Exception as e:
        log_test("Point generation with rotation (90°)", False, str(e))
        return False


def test_point_generation_world_coordinates():
    """Test that points are correctly translated to world coordinates."""
    try:
        # Matrix at origin
        shape_origin = {
            'type': 'matrix',
            'rows': 2,
            'cols': 2,
            'pattern': 'raster',
            'size': 100,
            'x': 0,
            'y': 0,
            'rotation': 0
        }
        
        points_origin = PointGenerator.generate_points(shape_origin)
        
        # Matrix offset to (500, 300)
        shape_offset = {**shape_origin, 'x': 500, 'y': 300}
        points_offset = PointGenerator.generate_points(shape_offset)
        
        # Check offset is applied correctly
        for i in range(len(points_origin)):
            assert abs((points_offset[i].x - points_origin[i].x) - 500) < 0.1, \
                f"X offset should be 500, got {points_offset[i].x - points_origin[i].x}"
            assert abs((points_offset[i].y - points_origin[i].y) - 300) < 0.1, \
                f"Y offset should be 300, got {points_offset[i].y - points_origin[i].y}"
        
        log_test("Point generation with world coordinates (offset)", True)
        return True
    except Exception as e:
        log_test("Point generation with world coordinates (offset)", False, str(e))
        return False


# =============================================================================
# Phase 3: Routing Manager Tests
# =============================================================================

def test_routing_manager_initialization():
    """Test routing manager initialization with mock session state."""
    print_section("Routing Manager - Initialization")
    
    try:
        mock_session = MockSessionStateManager()
        manager = ArtNetRoutingManager(mock_session)
        
        assert manager.session == mock_session, "Expected session reference"
        assert isinstance(manager.objects, dict), "Expected objects dict"
        assert isinstance(manager.outputs, dict), "Expected outputs dict"
        assert len(manager.objects) == 0, "Expected empty objects"
        assert len(manager.outputs) == 0, "Expected empty outputs"
        
        log_test("Routing Manager - Initialization", True, "Manager initialized correctly")
        return True
    except Exception as e:
        log_test("Routing Manager - Initialization", False, str(e))
        return False


def test_routing_manager_sync_from_editor():
    """Test syncing objects from editor shapes."""
    print_section("Routing Manager - Sync from Editor")
    
    try:
        # Setup mock session with editor shapes
        mock_session = MockSessionStateManager()
        mock_session._state['editor'] = {
            'shapes': [
                {
                    'id': 'shape-1',
                    'name': 'Test Matrix',
                    'type': 'matrix',
                    'x': 100,
                    'y': 100,
                    'size': 100,
                    'rows': 3,
                    'cols': 3,
                    'pattern': 'zigzag-left',
                    'rotation': 0,
                    'scaleX': 1,
                    'scaleY': 1
                },
                {
                    'id': 'shape-2',
                    'name': 'Test Circle',
                    'type': 'circle',
                    'x': 300,
                    'y': 300,
                    'size': 200,
                    'pointCount': 60,
                    'rotation': 0,
                    'scaleX': 1,
                    'scaleY': 1
                }
            ],
            'canvas': {'width': 1920, 'height': 1080}
        }
        
        manager = ArtNetRoutingManager(mock_session)
        result = manager.sync_from_editor_shapes()
        
        assert 'created' in result, "Expected created in result"
        assert 'updated' in result, "Expected updated in result"
        assert 'removed' in result, "Expected removed in result"
        
        created = result['created']
        assert len(created) == 2, "Expected 2 objects created"
        assert len(manager.objects) == 2, "Expected 2 objects in manager"
        
        # Check first object (matrix)
        obj1 = created[0]
        assert obj1.source_shape_id == 'shape-1', "Expected correct shape ID"
        assert obj1.name == 'Test Matrix', "Expected correct name"
        assert obj1.type == 'matrix', "Expected matrix type"
        assert len(obj1.points) == 9, "Expected 9 points (3x3 matrix)"
        assert obj1.led_type == 'RGB', "Expected default RGB"
        
        # Check second object (circle)
        obj2 = created[1]
        assert obj2.source_shape_id == 'shape-2', "Expected correct shape ID"
        assert obj2.name == 'Test Circle', "Expected correct name"
        assert obj2.type == 'circle', "Expected circle type"
        assert len(obj2.points) == 60, "Expected 60 points"
        
        log_test("Routing Manager - Sync from Editor", True, "Synced 2 objects from shapes")
        return True
    except Exception as e:
        log_test("Routing Manager - Sync from Editor", False, str(e))
        return False


def test_routing_manager_object_crud():
    """Test object CRUD operations."""
    print_section("Routing Manager - Object CRUD")
    
    try:
        mock_session = MockSessionStateManager()
        manager = ArtNetRoutingManager(mock_session)
        
        # Create object
        obj = ArtNetObject(
            id='obj-test-1',
            name='Test Object',
            source_shape_id='shape-1',
            type='matrix',
            points=[ArtNetPoint(1, 0, 0), ArtNetPoint(2, 10, 10)],
            led_type='RGB',
            channels_per_pixel=3,
            channel_order='RGB',
            universe_start=1,
            universe_end=1
        )
        
        manager.create_object(obj)
        assert len(manager.objects) == 1, "Expected 1 object"
        assert manager.get_object('obj-test-1') == obj, "Expected object retrieval"
        
        # Update object
        manager.update_object('obj-test-1', {'name': 'Updated Name', 'ledType': 'RGBW'})
        updated_obj = manager.get_object('obj-test-1')
        assert updated_obj.name == 'Updated Name', "Expected name update"
        assert updated_obj.led_type == 'RGBW', "Expected LED type update"
        
        # Get all objects
        all_objs = manager.get_all_objects()
        assert len(all_objs) == 1, "Expected 1 object in list"
        
        # Delete object
        manager.delete_object('obj-test-1')
        assert len(manager.objects) == 0, "Expected empty objects"
        assert manager.get_object('obj-test-1') is None, "Expected None for deleted object"
        
        log_test("Routing Manager - Object CRUD", True, "Create/Read/Update/Delete working")
        return True
    except Exception as e:
        log_test("Routing Manager - Object CRUD", False, str(e))
        return False


def test_routing_manager_output_crud():
    """Test output CRUD operations."""
    print_section("Routing Manager - Output CRUD")
    
    try:
        mock_session = MockSessionStateManager()
        manager = ArtNetRoutingManager(mock_session)
        
        # Create output
        output = ArtNetOutput(
            id='out-test-1',
            name='Test Output',
            target_ip='192.168.1.10',
            subnet='255.255.255.0',
            start_universe=1,
            fps=30
        )
        
        manager.create_output(output)
        assert len(manager.outputs) == 1, "Expected 1 output"
        assert manager.get_output('out-test-1') == output, "Expected output retrieval"
        
        # Update output
        manager.update_output('out-test-1', {'name': 'Updated Output', 'fps': 60})
        updated_out = manager.get_output('out-test-1')
        assert updated_out.name == 'Updated Output', "Expected name update"
        assert updated_out.fps == 60, "Expected FPS update"
        
        # Get all outputs
        all_outs = manager.get_all_outputs()
        assert len(all_outs) == 1, "Expected 1 output in list"
        
        # Delete output
        manager.delete_output('out-test-1')
        assert len(manager.outputs) == 0, "Expected empty outputs"
        assert manager.get_output('out-test-1') is None, "Expected None for deleted output"
        
        log_test("Routing Manager - Output CRUD", True, "Create/Read/Update/Delete working")
        return True
    except Exception as e:
        log_test("Routing Manager - Output CRUD", False, str(e))
        return False


def test_routing_manager_assignments():
    """Test object-to-output assignments (many-to-many)."""
    print_section("Routing Manager - Assignments")
    
    try:
        mock_session = MockSessionStateManager()
        manager = ArtNetRoutingManager(mock_session)
        
        # Create objects and outputs
        obj1 = ArtNetObject(
            id='obj-1', name='Object 1', source_shape_id='shape-1', type='matrix',
            points=[], led_type='RGB', channels_per_pixel=3, channel_order='RGB',
            universe_start=1, universe_end=1
        )
        obj2 = ArtNetObject(
            id='obj-2', name='Object 2', source_shape_id='shape-2', type='circle',
            points=[], led_type='RGB', channels_per_pixel=3, channel_order='RGB',
            universe_start=1, universe_end=1
        )
        
        out1 = ArtNetOutput(
            id='out-1', name='Output 1', target_ip='192.168.1.10',
            subnet='255.255.255.0', start_universe=1
        )
        out2 = ArtNetOutput(
            id='out-2', name='Output 2', target_ip='192.168.1.20',
            subnet='255.255.255.0', start_universe=1
        )
        
        manager.create_object(obj1)
        manager.create_object(obj2)
        manager.create_output(out1)
        manager.create_output(out2)
        
        # Test assignments
        manager.assign_object_to_output('obj-1', 'out-1')
        assert 'obj-1' in out1.assigned_objects, "Expected obj-1 assigned to out-1"
        
        manager.assign_object_to_output('obj-2', 'out-1')
        assert 'obj-2' in out1.assigned_objects, "Expected obj-2 assigned to out-1"
        assert len(out1.assigned_objects) == 2, "Expected 2 objects on out-1"
        
        # Test many-to-many (obj-1 to multiple outputs)
        manager.assign_object_to_output('obj-1', 'out-2')
        assert 'obj-1' in out2.assigned_objects, "Expected obj-1 assigned to out-2"
        
        # Test get_objects_for_output
        objs_for_out1 = manager.get_objects_for_output('out-1')
        assert len(objs_for_out1) == 2, "Expected 2 objects for out-1"
        assert obj1 in objs_for_out1, "Expected obj1 in list"
        assert obj2 in objs_for_out1, "Expected obj2 in list"
        
        # Test get_outputs_for_object
        outs_for_obj1 = manager.get_outputs_for_object('obj-1')
        assert len(outs_for_obj1) == 2, "Expected 2 outputs for obj-1"
        assert out1 in outs_for_obj1, "Expected out1 in list"
        assert out2 in outs_for_obj1, "Expected out2 in list"
        
        # Test removal
        manager.remove_object_from_output('obj-1', 'out-1')
        assert 'obj-1' not in out1.assigned_objects, "Expected obj-1 removed from out-1"
        assert len(out1.assigned_objects) == 1, "Expected 1 object remaining on out-1"
        
        log_test("Routing Manager - Assignments", True, "Many-to-many assignments working")
        return True
    except Exception as e:
        log_test("Routing Manager - Assignments", False, str(e))
        return False


def test_routing_manager_delete_cascade():
    """Test that deleting an object removes it from all outputs."""
    print_section("Routing Manager - Delete Cascade")
    
    try:
        mock_session = MockSessionStateManager()
        manager = ArtNetRoutingManager(mock_session)
        
        # Setup
        obj = ArtNetObject(
            id='obj-1', name='Object 1', source_shape_id='shape-1', type='matrix',
            points=[], led_type='RGB', channels_per_pixel=3, channel_order='RGB',
            universe_start=1, universe_end=1
        )
        out1 = ArtNetOutput(
            id='out-1', name='Output 1', target_ip='192.168.1.10',
            subnet='255.255.255.0', start_universe=1
        )
        out2 = ArtNetOutput(
            id='out-2', name='Output 2', target_ip='192.168.1.20',
            subnet='255.255.255.0', start_universe=1
        )
        
        manager.create_object(obj)
        manager.create_output(out1)
        manager.create_output(out2)
        
        # Assign to both outputs
        manager.assign_object_to_output('obj-1', 'out-1')
        manager.assign_object_to_output('obj-1', 'out-2')
        
        assert 'obj-1' in out1.assigned_objects, "Expected obj-1 in out-1"
        assert 'obj-1' in out2.assigned_objects, "Expected obj-1 in out-2"
        
        # Delete object
        manager.delete_object('obj-1')
        
        # Verify removed from all outputs
        assert 'obj-1' not in out1.assigned_objects, "Expected obj-1 removed from out-1"
        assert 'obj-1' not in out2.assigned_objects, "Expected obj-1 removed from out-2"
        
        log_test("Routing Manager - Delete Cascade", True, "Object removed from all outputs on delete")
        return True
    except Exception as e:
        log_test("Routing Manager - Delete Cascade", False, str(e))
        return False


def test_routing_manager_state_persistence():
    """Test state serialization and deserialization."""
    print_section("Routing Manager - State Persistence")
    
    try:
        mock_session = MockSessionStateManager()
        manager = ArtNetRoutingManager(mock_session)
        
        # Create objects and outputs with assignments
        obj = ArtNetObject(
            id='obj-1', name='Test Object', source_shape_id='shape-1', type='matrix',
            points=[ArtNetPoint(1, 0, 0), ArtNetPoint(2, 10, 10)],
            led_type='RGBW', channels_per_pixel=4, channel_order='RGBW',
            universe_start=1, universe_end=1
        )
        out = ArtNetOutput(
            id='out-1', name='Test Output', target_ip='192.168.1.10',
            subnet='255.255.255.0', start_universe=1, fps=60,
            assigned_objects=['obj-1']
        )
        
        manager.create_object(obj)
        manager.create_output(out)
        
        # Get state
        state = manager.get_state()
        assert 'objects' in state, "Expected objects in state"
        assert 'outputs' in state, "Expected outputs in state"
        assert 'obj-1' in state['objects'], "Expected obj-1 in state"
        assert 'out-1' in state['outputs'], "Expected out-1 in state"
        
        # Create new manager and restore state
        manager2 = ArtNetRoutingManager(mock_session)
        manager2.set_state(state)
        
        # Verify restored objects
        assert len(manager2.objects) == 1, "Expected 1 object restored"
        assert len(manager2.outputs) == 1, "Expected 1 output restored"
        
        restored_obj = manager2.get_object('obj-1')
        assert restored_obj is not None, "Expected object restored"
        assert restored_obj.name == 'Test Object', "Expected correct name"
        assert restored_obj.led_type == 'RGBW', "Expected correct LED type"
        assert len(restored_obj.points) == 2, "Expected 2 points"
        
        restored_out = manager2.get_output('out-1')
        assert restored_out is not None, "Expected output restored"
        assert restored_out.name == 'Test Output', "Expected correct name"
        assert restored_out.fps == 60, "Expected correct FPS"
        assert 'obj-1' in restored_out.assigned_objects, "Expected assignment restored"
        
        log_test("Routing Manager - State Persistence", True, "State save/restore working")
        return True
    except Exception as e:
        log_test("Routing Manager - State Persistence", False, str(e))
        return False


def test_routing_manager_update_shape_sync():
    """Test that syncing with updated shapes regenerates points."""
    print_section("Routing Manager - Update Shape Sync")
    
    try:
        mock_session = MockSessionStateManager()
        mock_session._state['editor'] = {
            'shapes': [
                {
                    'id': 'shape-1',
                    'name': 'Test Matrix',
                    'type': 'matrix',
                    'x': 100,
                    'y': 100,
                    'size': 100,
                    'rows': 2,
                    'cols': 2,
                    'pattern': 'zigzag-left',
                    'rotation': 0,
                    'scaleX': 1,
                    'scaleY': 1
                }
            ]
        }
        
        manager = ArtNetRoutingManager(mock_session)
        result = manager.sync_from_editor_shapes()
        
        obj1 = result['created'][0]
        obj1_id = obj1.id
        assert len(obj1.points) == 4, "Expected 4 points (2x2 matrix)"
        
        # Update LED config (should be preserved on resync)
        manager.update_object(obj1_id, {'ledType': 'RGBW', 'name': 'Updated Name'})
        
        # Modify shape in session state (increase to 3x3)
        mock_session._state['editor']['shapes'][0]['rows'] = 3
        mock_session._state['editor']['shapes'][0]['cols'] = 3
        
        # Resync
        result = manager.sync_from_editor_shapes()
        
        # Should be in updated list
        assert len(result['updated']) == 1, "Expected 1 updated object"
        assert len(result['created']) == 0, "Expected 0 created objects"
        
        # Verify points regenerated but LED config preserved
        obj1_updated = manager.get_object(obj1_id)
        assert len(obj1_updated.points) == 9, "Expected 9 points after resync (3x3)"
        assert obj1_updated.led_type == 'RGBW', "Expected LED type preserved"
        assert obj1_updated.name == 'Updated Name', "Expected name preserved"
        
        log_test("Routing Manager - Update Shape Sync", True, "Shape updates regenerate points, preserve config")
        return True
    except Exception as e:
        log_test("Routing Manager - Update Shape Sync", False, str(e))
        return False


def test_routing_manager_orphaned_objects():
    """Test that orphaned objects (deleted shapes) are removed when remove_orphaned=True."""
    print_section("Routing Manager - Orphaned Objects")
    
    try:
        mock_session = MockSessionStateManager()
        mock_session._state['editor'] = {
            'shapes': [
                {
                    'id': 'shape-1',
                    'name': 'Matrix 1',
                    'type': 'matrix',
                    'x': 100,
                    'y': 100,
                    'size': 100,
                    'rows': 2,
                    'cols': 2,
                    'pattern': 'zigzag-left',
                    'rotation': 0,
                    'scaleX': 1,
                    'scaleY': 1
                },
                {
                    'id': 'shape-2',
                    'name': 'Circle 1',
                    'type': 'circle',
                    'x': 300,
                    'y': 300,
                    'size': 200,
                    'pointCount': 60,
                    'rotation': 0,
                    'scaleX': 1,
                    'scaleY': 1
                }
            ]
        }
        
        manager = ArtNetRoutingManager(mock_session)
        result = manager.sync_from_editor_shapes()
        
        # Create 2 objects
        assert len(result['created']) == 2, "Expected 2 objects created"
        assert len(manager.objects) == 2, "Expected 2 objects"
        
        obj1_id = result['created'][0].id
        obj2_id = result['created'][1].id
        
        # Assign object 1 to an output
        output = ArtNetOutput(
            id='out-1', name='Output 1', target_ip='192.168.1.10',
            subnet='255.255.255.0', start_universe=1
        )
        manager.create_output(output)
        manager.assign_object_to_output(obj1_id, 'out-1')
        
        assert obj1_id in output.assigned_objects, "Expected obj1 assigned"
        
        # Remove shape-1 from editor (delete it)
        mock_session._state['editor']['shapes'] = [
            {
                'id': 'shape-2',
                'name': 'Circle 1',
                'type': 'circle',
                'x': 300,
                'y': 300,
                'size': 200,
                'pointCount': 60,
                'rotation': 0,
                'scaleX': 1,
                'scaleY': 1
            }
        ]
        
        # Sync WITHOUT removing orphaned (default behavior)
        result = manager.sync_from_editor_shapes(remove_orphaned=False)
        
        assert len(result['removed']) == 0, "Expected no removals when remove_orphaned=False"
        assert len(manager.objects) == 2, "Expected 2 objects still (orphan not removed)"
        
        # Sync WITH removing orphaned
        result = manager.sync_from_editor_shapes(remove_orphaned=True)
        
        assert len(result['removed']) == 1, "Expected 1 removal"
        assert obj1_id in result['removed'], "Expected obj1 removed"
        assert len(manager.objects) == 1, "Expected 1 object remaining"
        assert manager.get_object(obj1_id) is None, "Expected obj1 deleted"
        assert manager.get_object(obj2_id) is not None, "Expected obj2 still exists"
        
        # Verify obj1 removed from output assignments
        assert obj1_id not in output.assigned_objects, "Expected obj1 removed from output"
        
        log_test("Routing Manager - Orphaned Objects", True, "Orphaned objects removed correctly")
        return True
    except Exception as e:
        log_test("Routing Manager - Orphaned Objects", False, str(e))
        return False


# =============================================================================
# Main Test Runner
# =============================================================================

def run_all_tests():
    """Run all tests and print summary."""
    print("\n" + "=" * 60)
    print("  ArtNet Routing Backend Tests")
    print("  Phase 1: Data Models | Phase 2: Point Generation | Phase 3: Routing Manager")
    print("=" * 60)
    
    # Phase 1: Data Models
    test_artnet_point_creation()
    test_artnet_point_serialization()
    
    test_artnet_object_creation_rgb()
    test_artnet_object_creation_rgbw()
    test_artnet_object_serialization()
    
    test_universe_calculations_rgb()
    test_universe_calculations_rgb_multi()
    test_universe_calculations_rgbw()
    test_universe_calculations_rgbcww()
    
    test_artnet_output_creation()
    test_artnet_output_serialization()
    test_artnet_output_assignments()
    
    test_integration_object_output_workflow()
    
    # Phase 2: Point Generation
    test_point_generation_matrix()
    test_point_generation_matrix_zigzag_right()
    test_point_generation_circle()
    test_point_generation_circle_ellipse()
    test_point_generation_line()
    test_point_generation_star()
    test_point_generation_rect()
    test_point_generation_triangle()
    test_point_generation_polygon()
    test_point_generation_with_rotation()
    test_point_generation_world_coordinates()
    
    # Phase 3: Routing Manager
    test_routing_manager_initialization()
    test_routing_manager_sync_from_editor()
    test_routing_manager_object_crud()
    test_routing_manager_output_crud()
    test_routing_manager_assignments()
    test_routing_manager_delete_cascade()
    test_routing_manager_state_persistence()
    test_routing_manager_update_shape_sync()
    test_routing_manager_orphaned_objects()
    
    # Print summary
    print_section("Test Summary")
    
    passed = sum(1 for r in test_results if r['passed'])
    failed = sum(1 for r in test_results if not r['passed'])
    total = len(test_results)
    
    print(f"Total Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    if failed > 0:
        print("\n❌ Failed Tests:")
        for r in test_results:
            if not r['passed']:
                print(f"  - {r['name']}: {r['message']}")
    
    print("\n" + "=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
