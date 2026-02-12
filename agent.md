# Agent Guidelines - Python Backend with APIs and Frontend

## Project Overview
This document provides best practices and guidelines for developing and maintaining this Python backend application with REST APIs and a web frontend.

**Important**: 
- This is a **CLI (Command Line Interface) application** running locally
- The **backend is a CLI application** that runs in a terminal
- Authentication, encryption, and security measures are NOT required
- **Performance and low latency are the top priorities** - optimize for speed and responsiveness
- **Always ask before adding features**: Before implementing extra features, buttons, settings, or UI elements that weren't explicitly requested, ALWAYS ask the user if they want it

**Data Persistence Strategy**:
- **session_state.json**: ALL session + live data (save everything here!)
- **config.json**: ONLY global application settings
- **Memory**: Live parameters during runtime, but MUST be saved to session_state.json when persisting

## Architecture Principles

### Separation of Concerns
- **Backend (src/)**: CLI application, business logic, data processing, API endpoints
- **Frontend (frontend/)**: User interface, client-side interactions
- **Plugins (plugins/)**: Modular, extensible functionality
- **Tests (tests/)**: Comprehensive test coverage

### CLI Application Architecture
- Backend runs as a **command-line application**
- Provides REST API endpoints for frontend communication
- Single-user local application
- No authentication/session management required

### API-First Design
- Design APIs before implementing features
- Document all endpoints in API.md
- Use consistent REST conventions
- Version APIs appropriately

## Python Backend Best Practices

### Code Organization

#### Directory Structure
```
src/
├── api/              # API routes and controllers
├── models/           # Data models and schemas
├── services/         # Business logic layer
├── utils/            # Utility functions
├── middleware/       # Request/response middleware
└── config/           # Configuration management
```

#### Module Design
- **Search before creating**: Always check if similar modules exist
- **Reuse existing patterns**: Follow established project patterns
- One class per file for major components
- Group related functions in modules
- Keep files under 500 lines
- Use clear, descriptive names
- **Ask before adding**: Consult before creating new major components

### Code Quality

#### Type Hints
```python
def process_data(input: dict[str, Any]) -> Result:
    """Always use type hints for better IDE support and documentation."""
    pass
```

#### Documentation
- Use docstrings for all public functions and classes
- Follow Google or NumPy docstring style
- Document parameters, return values, and exceptions
- Keep inline comments meaningful

#### Error Handling
```python
class APIError(Exception):
    """Custom exception for API errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

# Use specific exception types
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise APIError("Invalid input", 400)
except Exception as e:
    logger.exception("Unexpected error")
    raise APIError("Internal server error", 500)
```

### API Development

#### RESTful Conventions
- Use appropriate HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Use plural nouns for resources: `/api/v1/users`, `/api/v1/projects`
- Nest resources logically: `/api/v1/projects/{id}/clips`
- Use query parameters for filtering: `/api/v1/clips?status=active`

#### Request/Response Format
```python
# Consistent JSON response structure
{
    "success": true,
    "data": { ... },
    "message": "Operation completed successfully",
    "timestamp": "2026-02-11T10:30:00Z"
}

# Error response
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid parameter",
        "details": { ... }
    },
    "timestamp": "2026-02-11T10:30:00Z"
}
```

#### Status Codes
- 200: Success
- 201: Created
- 204: No Content
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 422: Unprocessable Entity
- 500: Internal Server Error

#### Validation
```python
from pydantic import BaseModel, Field, validator

class ClipRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    duration: float = Field(..., gt=0)
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
```

### Database & Data Management

#### Use ORM or Query Builders
- Prefer SQLAlchemy for relational databases
- Use async drivers when possible (asyncpg, aiomysql)
- Implement connection pooling
- Use migrations (Alembic)

#### Data Validation
- Validate at API layer (request validation)
- Validate at service layer (business rules)
- Validate at database layer (constraints)

#### File Operations
```python
from pathlib import Path
import json

# Use pathlib for file operations
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

# Atomic file writes (critical for session_state.json!)
temp_file = data_dir / f"{filename}.tmp"
final_file = data_dir / f"{filename}.json"

with temp_file.open('w') as f:
    json.dump(data, f)
    
temp_file.replace(final_file)  # Atomic operation
```

**Important**: See [State Management & Data Persistence](#state-management--data-persistence) section for rules on where to save different types of data:
- `session_state.json` - ALL session + live data
- `config.json` - ONLY global settings

### Logging

#### Structured Logging
```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/app_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed debugging information")
logger.info("General information")
logger.warning("Warning messages")
logger.error("Error messages")
logger.critical("Critical issues")

# Include context
logger.info(f"Processing clip {clip_id} for user {user_id}")
```

#### Log What Matters
- API requests/responses (with sanitized data)
- Database operations
- External service calls
- Errors and exceptions
- Performance metrics
- Security events

### Asynchronous Programming

#### Use async/await
```python
import asyncio
from aiohttp import ClientSession

async def fetch_data(url: str) -> dict:
    """Async HTTP requests for better performance."""
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def process_multiple_requests():
    """Process multiple requests concurrently."""
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Local Application Guidelines

#### No Authentication Required
- This is a **localhost application** - no authentication needed
- No encryption required for local communication
- No CORS restrictions for local development
- Focus on functionality and performance

#### Input Validation for Stability
- Validate inputs to prevent crashes and errors
- Sanitize data to ensure proper data types
- Use parameterized queries to prevent injection issues
- Keep validation lightweight for performance

```python
from pydantic import BaseModel, validator

class ClipRequest(BaseModel):
    """Lightweight validation for stability, not security."""
    name: str
    duration: float
    
    @validator('duration')
    def duration_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Duration must be positive')
        return v
```

### Performance (TOP PRIORITY)

**Performance and low latency always come first!**

#### Optimization Principles
- Minimize response times
- Reduce computational overhead
- Avoid unnecessary processing
- Use efficient data structures
- Profile and optimize hot paths

#### Caching
```python
from functools import lru_cache
import redis

# In-memory caching
@lru_cache(maxsize=128)
def expensive_computation(param: str) -> Result:
    return compute(param)

# Redis caching
redis_client = redis.Redis(host='localhost', port=6379)

def get_cached_data(key: str) -> Optional[dict]:
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def set_cached_data(key: str, data: dict, ttl: int = 3600):
    redis_client.setex(key, ttl, json.dumps(data))
```

#### Database Optimization
- Use indexes on frequently queried columns
- Avoid N+1 queries (use joins or eager loading)
- Paginate large result sets
- Use database connection pooling

#### Background Tasks
```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

executor = ThreadPoolExecutor(max_workers=4)

def process_in_background(task_id: str):
    """CPU-bound tasks in background threads."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, heavy_computation, task_id)
```

## Frontend Integration

### API Communication
```javascript
// Use async/await for API calls
async function fetchData(endpoint) {
    try {
        const response = await fetch(`/api/v1/${endpoint}`, {
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}
```

### Real-time Communication
- Use WebSockets for real-time updates
- Implement Server-Sent Events (SSE) for one-way streaming
- Consider Socket.IO for complex scenarios

### CORS Configuration
```python
from flask_cors import CORS

# Allow all for local development - no restrictions needed
CORS(app, resources={r"/*": {"origins": "*"}})
```

## Testing

### Test Structure
```
tests/
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for API endpoints
├── e2e/              # End-to-end tests
└── fixtures/         # Test data and fixtures
```

### Unit Tests
```python
import pytest
from src.services.clip_service import ClipService

class TestClipService:
    @pytest.fixture
    def service(self):
        return ClipService()
    
    def test_create_clip(self, service):
        clip = service.create_clip(name="Test", duration=10.0)
        assert clip.name == "Test"
        assert clip.duration == 10.0
    
    def test_invalid_duration(self, service):
        with pytest.raises(ValueError):
            service.create_clip(name="Test", duration=-1.0)
```

### API Tests
```python
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_get_clips():
    response = client.get("/api/v1/clips")
    assert response.status_code == 200
    assert "data" in response.json()

def test_create_clip():
    payload = {"name": "Test Clip", "duration": 10.0}
    response = client.post("/api/v1/clips", json=payload)
    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Test Clip"
```

### Test Coverage
- Aim for 80%+ code coverage
- Focus on critical business logic
- Test error paths and edge cases
- Mock external dependencies

## State Management & Data Persistence

### Data Storage Strategy

**CRITICAL**: This application uses a specific data persistence strategy that MUST be followed:

#### Storage Locations

1. **session_state.json** - Session & Live Data
   - **ALL session data** must be stored here
   - **ALL live parameters** must be saved here when persisting a session
   - User settings and preferences
   - Current application state
   - Active parameters and runtime values
   - UI state (selected items, active views, etc.)

2. **config.json** - Global Application Settings
   - **ONLY global/static configuration**
   - Application-wide settings
   - Default values
   - System configuration
   - NOT for session-specific or user data

3. **Memory** - Runtime/Live Parameters
   - Live parameters stay in memory during execution
   - Temporary calculations and intermediate states
   - **MUST be persisted to session_state.json when saving**

#### Save Session Rules

**When saving a session, you MUST:**
- ✅ Save ALL session data to `session_state.json`
- ✅ Save ALL live parameters from memory to `session_state.json`
- ✅ Include runtime states and active parameters
- ✅ Preserve complete application state
- ❌ Never lose live data during save operations
- ❌ Never split session data across multiple files

```python
from pathlib import Path
import json
from typing import Any

class StateManager:
    """Manages application state and persistence."""
    
    def __init__(self):
        self.session_file = Path("session_state.json")
        self.config_file = Path("config.json")
        self.live_data = {}  # In-memory live parameters
        self.session_data = {}  # Session data
        
    def load_session(self):
        """Load session state from file."""
        if self.session_file.exists():
            with self.session_file.open('r') as f:
                data = json.load(f)
                self.session_data = data.get('session', {})
                self.live_data = data.get('live', {})
        
    def save_session(self):
        """Save complete session including ALL live data."""
        # CRITICAL: Save both session AND live data together
        complete_state = {
            'session': self.session_data,
            'live': self.live_data,  # Must include all live parameters!
            'timestamp': datetime.now().isoformat()
        }
        
        # Atomic save
        temp_file = self.session_file.with_suffix('.tmp')
        with temp_file.open('w') as f:
            json.dump(complete_state, f, indent=2)
        temp_file.replace(self.session_file)
        
    def update_live_parameter(self, key: str, value: Any):
        """Update a live parameter in memory."""
        self.live_data[key] = value
        
    def get_live_parameter(self, key: str, default=None):
        """Get a live parameter from memory."""
        return self.live_data.get(key, default)
    
    def load_config(self) -> dict:
        """Load global configuration (read-only during runtime)."""
        with self.config_file.open('r') as f:
            return json.load(f)
```

#### Usage Example

```python
# Initialize state manager
state_mgr = StateManager()
state_mgr.load_session()

# Work with live parameters in memory
state_mgr.update_live_parameter('bpm', 120)
state_mgr.update_live_parameter('effect_intensity', 0.8)
state_mgr.update_live_parameter('active_layer', 2)

# Session data
state_mgr.session_data['project_name'] = "My Show"
state_mgr.session_data['clips'] = [...]

# When user saves session - EVERYTHING gets saved
state_mgr.save_session()  # Saves session + ALL live data!

# Global config (separate, rarely changes)
config = state_mgr.load_config()
api_port = config['api_port']
```

#### Auto-Save Strategy

```python
import time
from threading import Thread

class AutoSaveManager:
    """Automatically saves session state periodically."""
    
    def __init__(self, state_manager: StateManager, interval: int = 60):
        self.state_manager = state_manager
        self.interval = interval  # seconds
        self.running = False
        
    def start(self):
        """Start auto-save thread."""
        self.running = True
        thread = Thread(target=self._auto_save_loop, daemon=True)
        thread.start()
        
    def stop(self):
        """Stop auto-save."""
        self.running = False
        
    def _auto_save_loop(self):
        """Auto-save loop running in background."""
        while self.running:
            time.sleep(self.interval)
            try:
                self.state_manager.save_session()
                logger.info("Auto-saved session state")
            except Exception as e:
                logger.error(f"Auto-save failed: {e}")
```

#### State Management Best Practices

1. **Always use StateManager** - Don't bypass the state management system
2. **Save frequently** - User expectations for data persistence are high
3. **Atomic writes** - Use temp files and replace for safe writes
4. **Include timestamps** - Track when state was last saved
5. **Validate on load** - Check data integrity when loading
6. **Handle corruption** - Keep backup of last known good state
7. **Log state changes** - Track important state transitions
8. **Fast saves** - Keep save operations < 100ms for good UX

#### Data Flow

```
User Action
    ↓
Update Live Parameters (Memory)
    ↓
Update Session Data (Memory)
    ↓
[User clicks Save / Auto-save triggers]
    ↓
Save ALL Data → session_state.json
    ↓
Atomic File Write
    ↓
Success!
```

## Configuration Management

### Environment-Based Config
```python
import os
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class Config:
    def __init__(self):
        self.env = Environment(os.getenv("ENV", "development"))
        self.debug = self.env == Environment.DEVELOPMENT
        self.db_url = os.getenv("DATABASE_URL")
        self.api_port = int(os.getenv("API_PORT", "8000"))
        
    @classmethod
    def from_file(cls, path: str):
        """Load config from JSON file - GLOBAL settings only!"""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

# config.json for development - GLOBAL settings only!
{
    "env": "development",
    "debug": true,
    "db_url": "sqlite:///dev.db",
    "api_port": 8000,
    "artnet_universe": 1,
    "default_framerate": 30
}
```

## Dependency Management

### Requirements Files
```
# requirements.txt - Production dependencies
flask==2.3.0
sqlalchemy==2.0.0
pydantic==2.0.0

# requirements-dev.txt - Development dependencies
pytest==7.4.0
black==23.0.0
flake8==6.0.0
mypy==1.5.0
```

### Virtual Environments
```bash
# Always use virtual environments
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Deployment

### Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Code linted and formatted
- [ ] Performance benchmarks met
- [ ] Dependencies updated
- [ ] Configuration files set
- [ ] Data migrations ready
- [ ] Logging configured
- [ ] Low latency verified

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY frontend/ ./frontend/
COPY plugins/ ./plugins/

EXPOSE 8000

# CLI application entry point
CMD ["python", "src/main.py"]
```

### Health Checks
```python
@app.route('/health')
def health_check():
    """Health check endpoint for load balancers."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/ready')
def readiness_check():
    """Readiness check - verify all dependencies."""
    checks = {
        "database": check_database(),
        "redis": check_redis(),
    }
    
    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503
    
    return jsonify({
        "ready": all_ready,
        "checks": checks
    }), status_code
```

## Monitoring & Observability

### Metrics
- Request rate and latency
- Error rates
- Database query performance
- Memory and CPU usage
- Active connections

### Alerting
- Set up alerts for critical errors
- Monitor API response times
- Track failed requests
- Monitor resource usage

## Documentation

### Keep Documentation Updated
- API documentation (API.md)
- Architecture documentation (ARCHITECTURE.md)
- Setup and deployment guides (README.md)
- Change logs (CHANGELOG.md)

### Code Documentation
- Document public APIs thoroughly
- Explain complex algorithms
- Document assumptions and limitations
- Include usage examples

## Git Workflow

### Commit Messages
```
feat: Add clip export functionality
fix: Resolve WebSocket connection issue
docs: Update API documentation
refactor: Simplify authentication middleware
test: Add tests for clip service
```

### Branch Strategy
- `main`: Production-ready code
- `develop`: Integration branch
- `feature/*`: New features
- `fix/*`: Bug fixes
- `hotfix/*`: Production hotfixes

### Git Commands
- **NEVER** automatically push to remote repositories
- Commit locally only
- Let the user decide when to push
- Use `git status` to check current state
- Use `git add` and `git commit` for local commits

```bash
# Good: Local commit only
git add .
git commit -m "feat: Add new feature"

# Bad: Don't automatically push!
# git push  # ❌ Never do this automatically!
```

## Performance Optimization

### Profiling
```python
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Your code here
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
```

### Optimization Priorities (CRITICAL)
1. **Performance first** - Always prioritize speed and low latency
2. Identify bottlenecks with profiling
3. Optimize database queries
4. Implement aggressive caching
5. Use async operations everywhere possible
6. Minimize network roundtrips
7. Optimize frontend rendering
8. Reduce payload sizes

## Terminal & CLI Safety

### CRITICAL: Running Application

**⚠️ NEVER send commands to a terminal where the application is running!**

#### Before Executing Terminal Commands:
1. **Check if the CLI application is running in the terminal**
2. **Use a different terminal** if the application is active
3. **Stop the application first** if you need to use that terminal
4. **Ask the user** if unsure about terminal state

```bash
# ❌ WRONG: Sending command while app is running
# Terminal 1: python src/main.py  (application running)
# You: git status  # This will be sent TO the running app!

# ✅ CORRECT: Use separate terminal
# Terminal 1: python src/main.py  (application running)
# Terminal 2: git status  # Use this terminal for commands
```

#### Safe Terminal Usage:
- **Always check** which terminals are available
- **Ask user** before sending commands if uncertain
- **Never interrupt** a running CLI application
- **Use background terminals** for Git, file operations, etc.

#### CLI Application States:
```
Running State:
- Terminal shows application output
- Application is processing commands
- DON'T send shell commands here!

Idle State:
- Terminal shows command prompt (PS C:\...>)
- Safe to execute commands
- Can run git, file operations, etc.
```

## Common Pitfalls to Avoid

1. **Not checking existing code first**: Always search for existing implementations before creating new ones ⭐
2. **Duplicating functionality**: Reuse and extend existing code instead of recreating it ⭐
3. **Creating without asking**: Ask before adding new classes or API endpoints ⭐
4. **Wrong data storage**: Remember - session_state.json for ALL session+live data, config.json ONLY for globals ⭐
5. **Losing live data on save**: ALWAYS save ALL live parameters when persisting session ⭐
6. **Writing to active terminal**: NEVER send commands to terminal where CLI app is running ⭐
7. **Not validating input**: Always validate and sanitize user input
8. **Ignoring errors**: Handle and log all exceptions properly
9. **Blocking operations**: Use async for I/O-bound operations
10. **Memory leaks**: Close connections and files properly
11. **Tight coupling**: Keep components loosely coupled
12. **No tests**: Write tests as you code
13. **Hardcoded values**: Use configuration files
14. **Poor logging**: Log meaningful information
15. **Unnecessary overhead**: Don't add features that slow down the application
16. **Premature optimization**: Profile before optimizing
17. **Auto-pushing to Git**: Never automatically push commits ⭐

## Code Reusability & Exploration

### Always Check Existing Code First

**CRITICAL**: Before creating any new modules, classes, components, or API endpoints, you MUST:

1. **Search for existing implementations**
   ```bash
   # Search for similar functionality
   grep -r "ClassName" src/
   grep -r "function_name" src/
   ```

2. **Review existing modules**
   - Check `src/` for backend services and utilities
   - Check `plugins/` for extensible functionality
   - Check `frontend/` for UI components
   - Review existing API endpoints in API documentation

3. **Analyze existing patterns**
   - How are similar problems solved?
   - What design patterns are used?
   - Which base classes or mixins exist?
   - What utilities are available?

### Before Creating New Code

#### Ask These Questions:
- ✅ Does a similar class/function already exist?
- ✅ Can existing code be extended or refactored?
- ✅ Are there utility functions that can be reused?
- ✅ Does this duplicate existing functionality?
- ✅ Can this be achieved by composing existing components?

#### When New Code Is Needed

**ALWAYS ASK FIRST** before creating:
- New API endpoints
- New classes or services
- New database models
- New frontend components
- New plugins or extensions

**Example Questions to Ask:**
```
"I need to add user authentication. I found AuthService in src/services/. 
Should I extend this or create a new service?"

"I need a /api/v1/clips/export endpoint. I see we have /api/v1/clips. 
Should I add the export as a sub-resource or separate endpoint?"

"I need to process video files. Is there existing video processing code 
I should use or extend?"
```

### DRY Principle (Don't Repeat Yourself)

- **Reuse over Recreate**: Prefer using existing code
- **Extend over Duplicate**: Inherit or compose rather than copy-paste
- **Refactor over Replicate**: If you need similar functionality, refactor existing code to be reusable

### Code Discovery Tools

```python
# Use grep/ripgrep to find existing code
rg "class.*Service" src/  # Find all service classes
rg "def.*api.*endpoint" src/  # Find API endpoint definitions
rg "^def " src/utils/  # Find utility functions

# Use IDE features
# - "Find References" to see usage
# - "Go to Implementation" to find concrete classes
# - "Find Symbol" to search for classes/functions
```

### Refactoring for Reuse

When you identify reusable code:

```python
# Before: Duplicated logic
def process_clip_audio():
    # 50 lines of audio processing
    pass

def process_effect_audio():
    # Same 50 lines of audio processing
    pass

# After: Extracted reusable function
def process_audio(source, options):
    """Reusable audio processing logic."""
    # 50 lines of audio processing
    pass

def process_clip_audio():
    return process_audio(clip.audio, clip_options)

def process_effect_audio():
    return process_audio(effect.audio, effect_options)
```

### Documentation of Existing Code

- Maintain an up-to-date API.md with all endpoints
- Document reusable utilities in docstrings
- Keep ARCHITECTURE.md current with system design
- Use code comments to explain reusable patterns

## Development Workflow

### Step-by-Step Process

1. **Understand the requirement**
   - What problem are we solving?
   - What are the acceptance criteria?

2. **Check terminal state** ⭐
   - Is the CLI application running?
   - Which terminal is safe to use?
   - Do I need a separate terminal for commands?

3. **Explore existing code** ⭐
   - Search for similar implementations
   - Identify reusable components
   - Ask about existing patterns

4. **Design the solution**
   - Plan to reuse existing code where possible
   - Identify what needs to be created
   - **Ask before creating new classes/endpoints**

5. **Write tests first** (TDD)
   - Test existing functionality if extending
   - Write tests for new functionality

6. **Implement the feature**
   - Reuse and extend existing code
   - Follow established patterns
   - Keep it modular
   - **Use StateManager for data persistence**
   - Save session+live data to session_state.json

7. **Test thoroughly**
   - Unit tests
   - Integration tests
   - Manual testing (use separate terminal!)

8. **Review code**
   - Check for unnecessary duplication
   - Ensure proper reuse
   - Verify patterns are followed

9. **Document changes**
   - Update API.md for new endpoints
   - Update ARCHITECTURE.md for significant changes
   - Add inline documentation

10. **Commit locally** (no automatic push!)
    - `git add .`
    - `git commit -m "descriptive message"`
    - Let user decide when to push

11. **Deploy to staging**
12. **Monitor and validate**
13. **Deploy to production**

## Resources

### Python
- [PEP 8 - Style Guide](https://pep8.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [asyncio Documentation](https://docs.python.org/3/library/asyncio.html)

### API Design
- [REST API Best Practices](https://restfulapi.net/)
- [OpenAPI Specification](https://swagger.io/specification/)

### Testing
- [pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://testdriven.io/)

### Performance
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed)
- [Profiling Python Code](https://docs.python.org/3/library/profile.html)

---

**Last Updated**: February 11, 2026
**Project**: Py_artnet
**Version**: 1.0
