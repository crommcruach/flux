#!/usr/bin/env bash
# =============================================================================
# Flux — Linux Install Script
# =============================================================================
# Downloads the latest version from GitHub, installs system dependencies,
# creates a Python virtual environment, installs all Python packages, and
# sets up a launch script.
#
# Fresh install (run this from anywhere):
#   bash <(curl -fsSL https://raw.githubusercontent.com/crommcruach/flux/main/install.sh)
#
# Or clone manually first, then run:
#   git clone https://github.com/crommcruach/flux.git
#   cd flux
#   chmod +x install.sh && ./install.sh
#
# After install, start the app with:
#   ./flux.sh
# or:
#   .venv/bin/python src/main.py
# =============================================================================

set -euo pipefail

REPO_URL="https://github.com/crommcruach/flux.git"
INSTALL_DIR="${FLUX_INSTALL_DIR:-$HOME/flux}"

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Colour

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD}  Flux — Installation${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""

# --------------------------------------------------------------------------- #
# 1. Check OS
# --------------------------------------------------------------------------- #
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    warn "This script is designed for Linux. Detected OS: $OSTYPE"
    warn "Continuing anyway — you may need to install system deps manually."
fi

# --------------------------------------------------------------------------- #
# 2. Clone or update source from GitHub
# --------------------------------------------------------------------------- #
if [[ -n "${BASH_SOURCE[0]}" && "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" != "$INSTALL_DIR" ]]; then
    # Script is being run from outside the install dir (e.g. piped from curl)
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Updating existing install at $INSTALL_DIR ..."
        git -C "$INSTALL_DIR" pull --ff-only
        success "Source updated"
    else
        info "Cloning Flux from $REPO_URL into $INSTALL_DIR ..."
        if ! command -v git &>/dev/null; then
            die "git is not installed. Install with: sudo apt install git"
        fi
        git clone "$REPO_URL" "$INSTALL_DIR"
        success "Source cloned"
    fi
    # Re-execute the freshly cloned script so the rest runs from the correct dir
    exec bash "$INSTALL_DIR/install.sh"
else
    # Already inside the repo directory — just make sure it's up to date
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"
    if [[ -d "$SCRIPT_DIR/.git" ]]; then
        info "Pulling latest changes..."
        git pull --ff-only 2>/dev/null && success "Source up to date" || warn "Could not pull (offline or local changes). Continuing with current version."
    fi
fi
# --------------------------------------------------------------------------- #
# 3. Check Python version (requires 3.10+)
# --------------------------------------------------------------------------- #
info "Checking Python version..."
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major=${ver%%.*}
        minor=${ver##*.}
        if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    die "Python 3.10 or newer is required but not found.\n  Install with: sudo apt install python3.12 python3.12-venv"
fi
success "Found $PYTHON ($($PYTHON --version))"

# --------------------------------------------------------------------------- #
# 3. Install system dependencies
# --------------------------------------------------------------------------- #
info "Installing system dependencies..."

APT_PACKAGES=(
    # Vulkan — required by wgpu (GPU rendering pipeline)
    libvulkan1
    mesa-vulkan-drivers
    vulkan-tools

    # Audio — required by sounddevice / PyAudio
    libasound2
    libportaudio2
    portaudio19-dev

    # OpenGL / display — required by wgpu and preview output
    libgl1
    libglib2.0-0
    libsm6
    libxext6
    libxrender1

    # Video / FFmpeg — required by av (PyAV)
    ffmpeg
    libavcodec-dev
    libavformat-dev
    libavutil-dev
    libswscale-dev

    # Python build tools (needed if any package compiles a C extension)
    python3-dev
    python3-venv
    build-essential
)

if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y "${APT_PACKAGES[@]}" 2>&1 | tail -5
    success "System packages installed"
elif command -v dnf &>/dev/null; then
    warn "dnf detected (Fedora/RHEL). Auto-install not supported — install manually:"
    echo "  sudo dnf install vulkan mesa-vulkan-drivers portaudio-devel ffmpeg-devel python3-devel gcc"
elif command -v pacman &>/dev/null; then
    warn "pacman detected (Arch). Auto-install not supported — install manually:"
    echo "  sudo pacman -S vulkan-icd-loader mesa portaudio ffmpeg python base-devel"
else
    warn "Unknown package manager. Install these manually:"
    echo "  vulkan, portaudio, ffmpeg, libgl, python3-dev"
fi

# --------------------------------------------------------------------------- #
# 4. Create virtual environment
# --------------------------------------------------------------------------- #
VENV_DIR="$SCRIPT_DIR/.venv"

if [[ -d "$VENV_DIR" ]]; then
    info "Virtual environment already exists at .venv — skipping creation"
else
    info "Creating virtual environment at .venv ..."
    "$PYTHON" -m venv "$VENV_DIR"
    success "Virtual environment created"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# --------------------------------------------------------------------------- #
# 5. Upgrade pip / wheel / setuptools
# --------------------------------------------------------------------------- #
info "Upgrading pip, wheel, setuptools..."
"$VENV_PIP" install --quiet --upgrade pip wheel setuptools
success "pip upgraded to $("$VENV_PIP" --version | awk '{print $2}')"

# --------------------------------------------------------------------------- #
# 6. Install Python dependencies
# --------------------------------------------------------------------------- #
if [[ -f "requirements.txt" ]]; then
    info "Installing Python dependencies from requirements.txt..."
    "$VENV_PIP" install -r requirements.txt
    success "Python dependencies installed"
else
    die "requirements.txt not found in $SCRIPT_DIR"
fi

# --------------------------------------------------------------------------- #
# 7. Verify critical imports
# --------------------------------------------------------------------------- #
info "Verifying critical imports..."
FAILED=()
for pkg in flask wgpu numpy PIL sounddevice av; do
    if ! "$VENV_PYTHON" -c "import $pkg" 2>/dev/null; then
        FAILED+=("$pkg")
    fi
done

if [[ ${#FAILED[@]} -gt 0 ]]; then
    warn "The following packages failed to import: ${FAILED[*]}"
    warn "Run: .venv/bin/pip install ${FAILED[*]}"
else
    success "All critical packages verified"
fi

# --------------------------------------------------------------------------- #
# 8. Create required runtime directories
# --------------------------------------------------------------------------- #
info "Creating runtime directories..."
for dir in logs data projects records snapshots thumbnails video audio backgrounds; do
    mkdir -p "$SCRIPT_DIR/$dir"
done
success "Runtime directories ready"

# --------------------------------------------------------------------------- #
# 9. Write flux.sh launch script
# --------------------------------------------------------------------------- #
LAUNCH_SCRIPT="$SCRIPT_DIR/flux.sh"
cat > "$LAUNCH_SCRIPT" <<'EOF'
#!/usr/bin/env bash
# Flux launch script — generated by install.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/src/main.py" "$@"
EOF
chmod +x "$LAUNCH_SCRIPT"
success "Launch script written to flux.sh"

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #
echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""
echo -e "  Start Flux:    ${CYAN}./flux.sh${NC}"
echo -e "  Direct run:    ${CYAN}.venv/bin/python src/main.py${NC}"
echo -e "  Web UI:        ${CYAN}http://localhost:5000${NC}  (after starting)"
echo ""
echo -e "  ${YELLOW}Note:${NC} A Vulkan-capable GPU driver is required for the"
echo -e "        GPU rendering pipeline (wgpu). On headless systems,"
echo -e "        install the llvmpipe software renderer:"
echo -e "        ${CYAN}sudo apt install mesa-software-renderer${NC}"
echo ""
