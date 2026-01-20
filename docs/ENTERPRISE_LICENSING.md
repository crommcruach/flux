# Enterprise Licensing Strategy

## Overview

This document outlines the strategy for making Py_artnet open source while keeping enterprise features (cluster, advanced sync, etc.) as paid additions.

**Model:** Open Core with separate enterprise modules

---

## License Structure

### Option 1: Open Core Model ⭐ (Recommended)
- **Base code:** MIT or Apache 2.0 license
- **Enterprise features:** Proprietary license with separate repository or private modules
- **Clear documentation:** Free vs paid feature matrix

**Benefits:**
- Clear separation of free vs paid
- Standard approach (GitLab, Grafana, Redis use this)
- Easy to understand for users
- Legally straightforward

### Option 2: Dual Licensing
- **Open Source:** AGPL (forces commercial users to open modifications)
- **Commercial:** Proprietary license for businesses wanting closed-source use

**Benefits:**
- Forces enterprises to pay or contribute back
- More aggressive protection
- Can be confusing for users

---

## Technical Implementation

### 1. Project Structure

```
Py_artnet/                      # Public GitHub repo (MIT License)
  src/
    core/                       # Open source features
      player.py
      artnet.py
      effects.py
      feature_flags.py          # Gate system
    cluster/                    # Stub implementation (shows what's available)
      __init__.py               # Raises "license required" error
      README.md                 # Points to enterprise docs
  frontend/
  docs/
  README.md
  LICENSE.txt (MIT)
  setup.py

Py_artnet_enterprise/           # Private repo (Commercial License)
  enterprise/
    __init__.py
    license.py                  # License validation
    cluster/                    # Full implementation
      __init__.py
      master.py
      slave.py
      sync.py
    advanced_effects/
    monitoring/
  LICENSE.txt (Proprietary)
  README.md                     # Enterprise installation guide
```

### 2. License Key System

```python
# enterprise/license.py
import hashlib
import hmac
import json
import base64
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

class LicenseValidator:
    """Validates enterprise license keys"""
    
    def __init__(self, config_path=None):
        self.server_url = "https://licensing.yourdomain.com"
        self._cached_license = None
        self._last_check = None
        self.config_path = config_path or "enterprise.key"
        
    def validate_license(self, license_key):
        """
        Validate license key signature and expiration
        
        License format (JWT-style):
        BASE64(header).BASE64(payload).RSA_SIGNATURE
        
        Returns:
            dict: License data if valid, None otherwise
        """
        try:
            # Split license key
            parts = license_key.split('.')
            if len(parts) != 3:
                return None
            
            header_b64, payload_b64, signature_b64 = parts
            
            # Verify signature with public key
            message = f"{header_b64}.{payload_b64}".encode()
            signature = base64.b64decode(signature_b64)
            
            if not self._verify_signature(message, signature):
                return None
            
            # Decode payload
            payload_json = base64.b64decode(payload_b64)
            data = json.loads(payload_json)
            
            # Check expiration
            expires = data.get('expires', 0)
            if datetime.now().timestamp() > expires:
                return None
            
            # Cache valid license
            self._cached_license = data
            self._last_check = datetime.now()
            
            return data
            
        except Exception as e:
            print(f"License validation error: {e}")
            return None
    
    def _verify_signature(self, message, signature):
        """Verify RSA signature with embedded public key"""
        # Public key embedded in code (can be obfuscated)
        public_key_pem = """
        -----BEGIN PUBLIC KEY-----
        [YOUR_PUBLIC_KEY_HERE]
        -----END PUBLIC KEY-----
        """
        
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode()
            )
            
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
    
    def has_feature(self, feature_name):
        """Check if license includes specific feature"""
        if not self._cached_license:
            return False
        return feature_name in self._cached_license.get('features', [])
    
    def get_node_limit(self):
        """Get maximum allowed cluster nodes"""
        if not self._cached_license:
            return 0
        return self._cached_license.get('max_nodes', 1)
    
    def get_license_info(self):
        """Get human-readable license information"""
        if not self._cached_license:
            return None
        
        return {
            'customer': self._cached_license.get('customer_id'),
            'email': self._cached_license.get('email'),
            'features': self._cached_license.get('features', []),
            'max_nodes': self._cached_license.get('max_nodes', 1),
            'expires': datetime.fromtimestamp(
                self._cached_license.get('expires', 0)
            ).strftime('%Y-%m-%d'),
            'license_type': self._cached_license.get('license_type', 'unknown')
        }
    
    def check_online(self):
        """Periodic online license check (every 7 days)"""
        if not self._cached_license:
            return False
        
        if self._last_check:
            days_since_check = (datetime.now() - self._last_check).days
            if days_since_check < 7:
                return True  # Recently validated
        
        # Call licensing server to verify license is still active
        # Implementation depends on your server setup
        try:
            import requests
            response = requests.post(
                f"{self.server_url}/api/verify",
                json={
                    'customer_id': self._cached_license.get('customer_id'),
                    'license_hash': hashlib.sha256(
                        str(self._cached_license).encode()
                    ).hexdigest()
                },
                timeout=5
            )
            
            if response.status_code == 200:
                self._last_check = datetime.now()
                return True
            
            return False
            
        except Exception:
            # If offline, allow 30 days grace period
            if self._last_check:
                days_offline = (datetime.now() - self._last_check).days
                return days_offline < 30
            
            return False
```

### 3. Feature Gate System

```python
# src/core/feature_flags.py
import os
from pathlib import Path

class FeatureGate:
    """Central feature gating system"""
    
    # Free features (always available)
    FREE_FEATURES = [
        'basic_playback',
        'artnet_output',
        'basic_effects',
        'midi_control',
        'playlist_management',
        'single_output',
        'clip_editor'
    ]
    
    # Enterprise features (require license)
    ENTERPRISE_FEATURES = [
        'cluster',                # Multi-node render cluster
        'advanced_sync',          # NTP time synchronization
        'multi_output',           # Multiple simultaneous outputs
        'advanced_effects',       # Advanced effect library
        'priority_support',       # Technical support
        'monitoring_dashboard',   # Health monitoring
        'api_access',             # Advanced API endpoints
        'load_balancing'          # Automatic load distribution
    ]
    
    def __init__(self):
        self.license_validator = None
        self._enterprise_available = False
        
        # Try to load enterprise module
        try:
            from enterprise.license import LicenseValidator
            self.license_validator = LicenseValidator()
            self._enterprise_available = True
            
            # Auto-load license if exists
            license_path = Path('enterprise.key')
            if license_path.exists():
                with open(license_path, 'r') as f:
                    license_key = f.read().strip()
                    self.license_validator.validate_license(license_key)
                    
        except ImportError:
            pass  # Enterprise module not installed
    
    def is_feature_enabled(self, feature_name):
        """Check if feature is available"""
        # Free features always available
        if feature_name in self.FREE_FEATURES:
            return True
        
        # Enterprise features require license
        if feature_name in self.ENTERPRISE_FEATURES:
            if not self._enterprise_available:
                return False
            
            if not self.license_validator:
                return False
            
            return self.license_validator.has_feature(feature_name)
        
        # Unknown feature, assume free for backwards compatibility
        return True
    
    def require_feature(self, feature_name):
        """Decorator to gate functions behind license"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not self.is_feature_enabled(feature_name):
                    raise PermissionError(
                        f"Feature '{feature_name}' requires an enterprise license.\n"
                        f"Visit https://yourdomain.com/pricing for more information.\n"
                        f"Contact: sales@yourdomain.com"
                    )
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_upgrade_message(self, feature_name):
        """Get user-friendly upgrade message"""
        return {
            'feature': feature_name,
            'available': self.is_feature_enabled(feature_name),
            'message': f"Upgrade to Enterprise to unlock '{feature_name}'",
            'url': 'https://yourdomain.com/pricing',
            'contact': 'sales@yourdomain.com'
        }
    
    def list_available_features(self):
        """List all available features (free + licensed)"""
        available = self.FREE_FEATURES.copy()
        
        for feature in self.ENTERPRISE_FEATURES:
            if self.is_feature_enabled(feature):
                available.append(feature)
        
        return available
    
    def get_license_info(self):
        """Get current license information"""
        if not self._enterprise_available or not self.license_validator:
            return {'status': 'community', 'features': self.FREE_FEATURES}
        
        info = self.license_validator.get_license_info()
        if info:
            return {'status': 'enterprise', **info}
        
        return {'status': 'unlicensed', 'features': self.FREE_FEATURES}

# Global singleton instance
_feature_gate = None

def get_feature_gate():
    """Get global feature gate instance"""
    global _feature_gate
    if _feature_gate is None:
        _feature_gate = FeatureGate()
    return _feature_gate
```

### 4. Usage Examples

```python
# Example 1: Gating cluster initialization
# src/cluster/__init__.py (public repo, stub implementation)

from core.feature_flags import get_feature_gate

def initialize_cluster(config):
    """Initialize multi-video render cluster (enterprise only)"""
    gate = get_feature_gate()
    
    if not gate.is_feature_enabled('cluster'):
        raise PermissionError(
            "Multi-video render cluster is an enterprise feature.\n"
            "Free version supports single output only.\n"
            "Visit https://yourdomain.com/pricing"
        )
    
    # If enterprise module is available, import and use it
    from enterprise.cluster import ClusterManager
    return ClusterManager(config)


# Example 2: Using decorator
from core.feature_flags import get_feature_gate

@get_feature_gate().require_feature('advanced_effects')
def load_advanced_effect_library():
    """Load advanced effects (enterprise only)"""
    from enterprise.effects import AdvancedEffectLibrary
    return AdvancedEffectLibrary()


# Example 3: Conditional UI elements
# In REST API endpoint
from flask import Flask, jsonify
from core.feature_flags import get_feature_gate

app = Flask(__name__)

@app.route('/api/features')
def get_features():
    """Return available features for UI"""
    gate = get_feature_gate()
    return jsonify({
        'available_features': gate.list_available_features(),
        'license_info': gate.get_license_info()
    })

@app.route('/api/cluster/status')
def cluster_status():
    """Cluster status endpoint"""
    gate = get_feature_gate()
    
    if not gate.is_feature_enabled('cluster'):
        return jsonify({
            'enabled': False,
            'message': 'Cluster feature requires enterprise license',
            'upgrade_url': 'https://yourdomain.com/pricing'
        })
    
    # Return actual cluster status
    from enterprise.cluster import get_cluster_status
    return jsonify(get_cluster_status())
```

---

## License Format

### JWT-Style License Key

```json
{
  "customer_id": "CUST-12345",
  "company": "Acme Productions Ltd",
  "email": "admin@acme.com",
  "features": [
    "cluster",
    "advanced_sync",
    "multi_output",
    "advanced_effects",
    "priority_support",
    "monitoring_dashboard"
  ],
  "max_nodes": 10,
  "license_type": "enterprise",
  "issued": 1704067200,
  "expires": 1735689600,
  "version": "1.0"
}
```

**Encoded Format:**
```
BASE64(header).BASE64(payload).RSA_SIGNATURE
```

### Key Generation (Server-Side Only)

```python
# Server-side license generation
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import json
import base64
from datetime import datetime, timedelta

def generate_license_key(customer_data):
    """Generate signed license key"""
    
    # Load your private key (keep this SECURE on server only!)
    with open('private_key.pem', 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None
        )
    
    # Create license payload
    payload = {
        'customer_id': customer_data['customer_id'],
        'company': customer_data['company'],
        'email': customer_data['email'],
        'features': customer_data['features'],
        'max_nodes': customer_data.get('max_nodes', 5),
        'license_type': 'enterprise',
        'issued': int(datetime.now().timestamp()),
        'expires': int((datetime.now() + timedelta(days=365)).timestamp()),
        'version': '1.0'
    }
    
    # Encode header and payload
    header = base64.b64encode(json.dumps({'typ': 'license', 'alg': 'RS256'}).encode())
    payload_b64 = base64.b64encode(json.dumps(payload).encode())
    
    # Sign
    message = f"{header.decode()}.{payload_b64.decode()}".encode()
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    signature_b64 = base64.b64encode(signature).decode()
    
    # Return complete license key
    return f"{header.decode()}.{payload_b64.decode()}.{signature_b64}"
```

---

## Protection Mechanisms

### What Works ✅

1. **RSA/HMAC License Signing**
   - Use 2048-bit RSA keys
   - Sign licenses with private key (server-only)
   - Validate with public key (embedded in app)
   - Very hard to forge without private key

2. **Online Activation**
   - Periodic check-in (weekly recommended)
   - Grace period for offline use (30 days)
   - Prevents infinite license sharing

3. **Hardware Fingerprinting**
   - Tie license to specific machines
   - Allow license transfer with deactivation
   - Prevents casual copying

4. **Time-Based Licenses**
   - Annual subscriptions
   - Automatic expiration
   - Renewal reminder system

5. **Feature Binaries** (optional)
   - Distribute as compiled .pyc or .pyd
   - Use Cython for C extensions
   - Adds friction to reverse engineering

6. **Legal Terms**
   - Strong EULA with audit rights
   - Clear penalties for violations
   - Most enterprises respect this

### What Doesn't Work ❌

1. **Client-Side Obfuscation**
   - Python can always be decompiled
   - Adds complexity, minimal security
   - Frustrates legitimate debugging

2. **Hidden Activation in JavaScript**
   - Easy to inspect in browser
   - Can be bypassed easily
   - Not recommended

3. **Over-Complicated DRM**
   - Frustrates legitimate users
   - Still gets cracked
   - Bad reputation

---

## Distribution Strategy

### Community Edition (Free)
```bash
# Install via PyPI
pip install py-artnet

# Or from GitHub
git clone https://github.com/yourusername/py-artnet
cd py-artnet
pip install -e .
```

**Includes:**
- Basic playback
- Art-Net output
- Basic effects
- MIDI control
- Playlist management
- Single output
- Clip editor

### Enterprise Edition (Paid)

```bash
# Install community first
pip install py-artnet

# Then install enterprise module (requires license key)
pip install py-artnet-enterprise --extra-index-url https://pypi.yourdomain.com

# Activate license
py-artnet-license activate YOUR-LICENSE-KEY-HERE
```

**Additional Features:**
- Multi-node render cluster
- NTP time synchronization
- Multiple simultaneous outputs
- Advanced effect library
- Priority technical support
- Health monitoring dashboard
- Advanced API access
- Automatic load balancing

---

## Frontend Integration

### Feature Detection

```javascript
// frontend/js/license.js

class LicenseManager {
    constructor() {
        this.features = [];
        this.licenseInfo = null;
    }
    
    async checkLicense() {
        try {
            const response = await fetch('/api/features');
            const data = await response.json();
            
            this.features = data.available_features;
            this.licenseInfo = data.license_info;
            
            return data;
        } catch (error) {
            console.error('License check failed:', error);
            return null;
        }
    }
    
    hasFeature(featureName) {
        return this.features.includes(featureName);
    }
    
    showUpgradePrompt(featureName) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">🚀 Enterprise Feature</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p><strong>${featureName}</strong> is an enterprise feature.</p>
                        <p>Upgrade to unlock:</p>
                        <ul>
                            <li>Multi-video render cluster</li>
                            <li>Advanced synchronization</li>
                            <li>Multiple outputs</li>
                            <li>Priority support</li>
                            <li>Advanced monitoring</li>
                        </ul>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            Maybe Later
                        </button>
                        <a href="https://yourdomain.com/pricing" class="btn btn-primary" target="_blank">
                            View Pricing
                        </a>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
        
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
    }
}

// Global instance
const licenseManager = new LicenseManager();
```

### UI Gating Example

```javascript
// frontend/js/cluster-ui.js

async function initializeCluster() {
    // Check if cluster feature is available
    if (!licenseManager.hasFeature('cluster')) {
        licenseManager.showUpgradePrompt('Multi-Video Render Cluster');
        return;
    }
    
    // User has license, proceed with initialization
    try {
        const response = await fetch('/api/cluster/initialize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config: getClusterConfig() })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showClusterDashboard();
        }
        
    } catch (error) {
        console.error('Cluster init failed:', error);
    }
}

// Show enterprise badge in menu
function renderMenuItems() {
    const menu = document.getElementById('main-menu');
    
    menu.innerHTML = `
        <li><a href="/player">Player</a></li>
        <li><a href="/editor">Editor</a></li>
        <li>
            <a href="/cluster" id="cluster-menu">
                Cluster 
                ${!licenseManager.hasFeature('cluster') ? 
                    '<span class="badge bg-warning">Enterprise</span>' : ''}
            </a>
        </li>
    `;
    
    // Add click handler for gated features
    if (!licenseManager.hasFeature('cluster')) {
        document.getElementById('cluster-menu').addEventListener('click', (e) => {
            e.preventDefault();
            licenseManager.showUpgradePrompt('Multi-Video Render Cluster');
        });
    }
}
```

---

## Best Practices

### 1. Make It Convenient
- **Easy purchase process** - Online checkout, instant license delivery
- **Simple activation** - One command or GUI button
- **Good documentation** - Clear setup instructions
- **Free trial** - 30-day trial of enterprise features

### 2. Value Proposition
- **Enterprise features actually useful** - Solve real problems
- **Include support** - Priority email/chat support
- **Regular updates** - New features for paid users
- **Professional image** - Shows you're serious

### 3. Honor System
- **Don't over-protect** - Small users might crack it anyway
- **Target enterprises** - They won't risk legal issues
- **Build trust** - Transparent pricing and terms
- **Community goodwill** - Open source builds reputation

### 4. Legal Protection
- **Strong EULA** - Clear terms and penalties
- **Audit rights** - Right to verify compliance
- **Anti-circumvention clause** - Illegal to crack or share
- **Geographic pricing** - Different pricing for different markets

### 5. Support & Services
- **Priority support** - Paid users get faster responses
- **Training & consulting** - Additional revenue stream
- **Custom development** - Enterprise custom features
- **Managed hosting** - SaaS option for enterprises

### 6. Graceful Degradation
- **No crashes** - Show upgrade prompts, don't break
- **Feature discovery** - Show what's available in Enterprise
- **Trial mode** - Let users test before buying
- **Clear messaging** - Honest about limitations

### 7. Monitoring (Optional)
- **Anonymous telemetry** - Detect unusual usage patterns
- **License usage stats** - How many nodes, what features
- **Error reporting** - Help debug customer issues
- **Opt-out option** - Respect privacy

---

## Pricing Strategy

### Tier Structure (Example)

| Feature | Community (Free) | Professional ($49/mo) | Enterprise ($199/mo) |
|---------|------------------|----------------------|---------------------|
| Basic Playback | ✅ | ✅ | ✅ |
| Art-Net Output | ✅ | ✅ | ✅ |
| Basic Effects | ✅ | ✅ | ✅ |
| Clip Editor | ✅ | ✅ | ✅ |
| **Multi-Output** | ❌ | ✅ (3 outputs) | ✅ (Unlimited) |
| **Cluster Nodes** | ❌ | ✅ (2 nodes) | ✅ (Unlimited) |
| **Advanced Sync** | ❌ | ✅ | ✅ |
| **Priority Support** | ❌ | Email (48h) | Email + Chat (4h) |
| **Monitoring** | ❌ | ✅ | ✅ + API |
| **Custom Effects** | ❌ | ❌ | ✅ |

### Volume Licensing
- **1-5 seats:** Full price
- **6-20 seats:** 15% discount
- **21+ seats:** Custom pricing

### Educational/Non-Profit
- **50% discount** with verification
- **Free for students** (personal projects)

---

## Reality Check

### Honest Assessment

✅ **Will This Stop Determined Hackers?**
- No. Determined hackers will crack anything.
- That's okay - they weren't paying customers anyway.

✅ **Will Enterprises Pay?**
- Yes. Enterprises need:
  - Legal compliance
  - Support and reliability
  - Professional invoicing
  - Risk mitigation

✅ **Is This Worth It?**
- Yes. Many successful open-source companies use this model:
  - GitLab (CE vs EE)
  - Grafana (OSS vs Enterprise)
  - Redis (OSS vs Enterprise Modules)
  - Elastic (Open vs Licensed Features)

### Success Factors

1. **Make free version genuinely useful**
   - Don't cripple basic features
   - Build community and reputation
   - Free users become advocates

2. **Make paid features compelling**
   - Solve real enterprise problems
   - Not just "limits" but actual functionality
   - Worth more than the price

3. **Legal protection > Technical protection**
   - Enterprises respect licenses
   - Clear terms and penalties
   - Right to audit

4. **Focus on convenience**
   - Easier to buy than to crack
   - Instant activation
   - Good support

---

## Implementation Roadmap

### Phase 1: Structure Setup (1-2 days)
- [ ] Split repository (public vs private)
- [ ] Create enterprise module structure
- [ ] Define feature lists
- [ ] Write MIT license for public repo

### Phase 2: License System (3-5 days)
- [ ] Implement LicenseValidator class
- [ ] Create FeatureGate system
- [ ] Generate RSA key pair
- [ ] Build license server (basic)
- [ ] Test validation logic

### Phase 3: Code Integration (2-3 days)
- [ ] Add feature gates to cluster code
- [ ] Create stub implementations in public repo
- [ ] Move enterprise code to private repo
- [ ] Test import separation

### Phase 4: Frontend (2-3 days)
- [ ] Add license detection API
- [ ] Create upgrade modals
- [ ] Add enterprise badges to UI
- [ ] Build license activation UI

### Phase 5: Distribution (1-2 days)
- [ ] Package community edition
- [ ] Package enterprise edition
- [ ] Set up private PyPI (optional)
- [ ] Write installation docs

### Phase 6: Business Setup (ongoing)
- [ ] Create pricing page
- [ ] Set up payment processing (Stripe/Paddle)
- [ ] Build license delivery system
- [ ] Create customer portal
- [ ] Write EULA/Terms

---

## Example Companies Using This Model

### GitLab
- **CE (Community):** Free, full source on GitHub
- **EE (Enterprise):** Closed modules, licensed features
- **Success:** $15B valuation, thousands of paying customers

### Grafana Labs
- **Grafana OSS:** Free monitoring tool
- **Enterprise:** Add-ons for SSO, reports, support
- **Success:** $6B valuation, widely adopted

### Redis
- **Redis OSS:** Free in-memory database
- **Redis Enterprise:** Clustering, geo-replication
- **Success:** Acquired for $8B

### Elastic
- **Elasticsearch:** Free under ELv2 license
- **Licensed Features:** Security, alerting, ML
- **Success:** $4B market cap

---

## Resources

### Tools & Libraries
- **License Generation:** `cryptography` (Python)
- **Payment Processing:** Stripe, Paddle, Lemon Squeezy
- **Customer Portal:** Memberful, Chargebee
- **Analytics:** PostHog, Mixpanel

### Legal Resources
- **Choose a License:** https://choosealicense.com/
- **EULA Generator:** https://www.eulatemplate.com/
- **Lawyer Consultation:** Recommended for enterprise contracts

### Inspiration
- **Open Core Summit:** Annual conference on open-core business
- **COSS (Commercial OSS):** https://coss.media/
- **SaaStr:** Resources for B2B SaaS businesses

---

## Next Steps

When ready to implement:

1. **Decide on license model** (Open Core recommended)
2. **Define feature split** (free vs paid)
3. **Set up repositories** (public + private)
4. **Implement license system** (validation + gates)
5. **Create pricing** (tiers, volume discounts)
6. **Build sales funnel** (website, checkout, delivery)
7. **Launch gradually** (beta, early customers, public)

---

## Questions to Answer

Before implementing, decide:

- [ ] What features will be free vs paid?
- [ ] What price points? ($49/mo? $99/mo? Custom?)
- [ ] Annual vs monthly billing?
- [ ] Node-based pricing or flat fee?
- [ ] Self-hosted vs SaaS options?
- [ ] Support included or separate?
- [ ] Trial period length?
- [ ] Refund policy?

---

## Contact & Support

**For Implementation Questions:**
- Review this document
- Check example code above
- Research similar companies

**For Legal Questions:**
- Consult a lawyer (seriously)
- Review open-core case studies
- Join COSS community

**For Business Strategy:**
- Study successful open-core companies
- Join founder communities
- Consider advisors/mentors
