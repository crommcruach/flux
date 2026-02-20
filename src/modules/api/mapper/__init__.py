"""
LED Visual Mapper API
2D webcam-based LED position detection
"""
from flask import Blueprint

mapper_bp = Blueprint('mapper', __name__, url_prefix='/api/mapper')

from . import routes
