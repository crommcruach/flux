# =============================================================================
# Flux — Windows Install Script (PowerShell)
# =============================================================================
# Downloads the latest version from GitHub, installs Python dependencies into
# a virtual environment, and sets up a launch script.
#
# Fresh install — run this from PowerShell (as normal user, NOT admin):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   irm https://raw.githubusercontent.com/crommcruach/flux/main/install.ps1 | iex
#
# Or clone manually first, then run:
#   git clone https://github.com/crommcruach/flux.git
#   cd flux
#   .\install.ps1
#
# After install, start the app with:
#   .\flux.bat
# or:
#   .venv\Scripts\python src\main.py
# =============================================================================

#Requires -Version 5.1

$ErrorActionPreference = 'Stop'

$REPO_URL    = 'https://github.com/crommcruach/flux.git'
$INSTALL_DIR = if ($env:FLUX_INSTALL_DIR) { $env:FLUX_INSTALL_DIR } else { Join-Path $HOME 'flux' }

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
function Write-Info    ($msg) { Write-Host "  [INFO]  $msg" -ForegroundColor Cyan }
function Write-Ok      ($msg) { Write-Host "  [OK]    $msg" -ForegroundColor Green }
function Write-Warn    ($msg) { Write-Host "  [WARN]  $msg" -ForegroundColor Yellow }
function Write-Fail    ($msg) { Write-Host "  [ERROR] $msg" -ForegroundColor Red }
function Exit-WithError($msg) { Write-Fail $msg; exit 1 }

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor White
Write-Host "    Flux — Windows Installation" -ForegroundColor White
Write-Host "  ============================================================" -ForegroundColor White
Write-Host ""

# --------------------------------------------------------------------------- #
# 1. Detect execution context — piped from web or local clone?
# --------------------------------------------------------------------------- #
$ScriptDir = $null
try {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
} catch { }

# If script is being run piped (iex), $ScriptDir will be empty or a temp path
$IsWebRun = (-not $ScriptDir) -or (-not (Test-Path (Join-Path $ScriptDir 'src')))

# --------------------------------------------------------------------------- #
# 2. Check / install Git
# --------------------------------------------------------------------------- #
Write-Info "Checking for Git..."
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Warn "Git not found. Attempting to install via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH','Machine') + ';' +
                    [System.Environment]::GetEnvironmentVariable('PATH','User')
        $git = Get-Command git -ErrorAction SilentlyContinue
        if (-not $git) {
            Exit-WithError "Git installation succeeded but 'git' still not in PATH. Restart PowerShell and re-run this script."
        }
    } else {
        Exit-WithError "Git is not installed and winget is unavailable.`n  Install Git manually from https://git-scm.com/download/win then re-run this script."
    }
}
Write-Ok "Git found: $(git --version)"

# --------------------------------------------------------------------------- #
# 3. Clone or update source
# --------------------------------------------------------------------------- #
if ($IsWebRun) {
    if (Test-Path (Join-Path $INSTALL_DIR '.git')) {
        Write-Info "Updating existing install at $INSTALL_DIR ..."
        git -C $INSTALL_DIR pull --ff-only
        Write-Ok "Source updated"
    } else {
        Write-Info "Cloning Flux from $REPO_URL into $INSTALL_DIR ..."
        git clone $REPO_URL $INSTALL_DIR
        Write-Ok "Source cloned to $INSTALL_DIR"
    }
    # Re-execute the freshly downloaded script from the correct directory
    & "$INSTALL_DIR\install.ps1"
    exit $LASTEXITCODE
} else {
    # Already inside the repo — pull updates
    $ScriptDir = (Resolve-Path $ScriptDir).Path
    Set-Location $ScriptDir
    if (Test-Path (Join-Path $ScriptDir '.git')) {
        Write-Info "Pulling latest changes..."
        $pullResult = git pull --ff-only 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Ok "Source up to date" }
        else { Write-Warn "Could not pull ($pullResult). Continuing with current version." }
    }
}

# --------------------------------------------------------------------------- #
# 4. Check Python version (requires 3.10+)
# --------------------------------------------------------------------------- #
Write-Info "Checking Python version..."
$pythonExe = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            $parts = $ver.Split('.')
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 10) {
                $pythonExe = $cmd.Source
                Write-Ok "Found Python $ver at $pythonExe"
                break
            }
        } catch { }
    }
}

if (-not $pythonExe) {
    Write-Warn "Python 3.10+ not found. Attempting to install via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH','Machine') + ';' +
                    [System.Environment]::GetEnvironmentVariable('PATH','User')
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        $pythonExe = if ($pythonCmd) { $pythonCmd.Source } else { $null }
        if (-not $pythonExe) {
            Exit-WithError "Python installed but not found in PATH. Restart PowerShell and re-run this script."
        }
        Write-Ok "Python installed: $(& $pythonExe --version)"
    } else {
        Exit-WithError "Python 3.10+ is required.`n  Download from https://www.python.org/downloads/ (check 'Add to PATH' during install)"
    }
}

# --------------------------------------------------------------------------- #
# 5. Check for Vulkan runtime (wgpu requirement)
# --------------------------------------------------------------------------- #
Write-Info "Checking Vulkan runtime..."
$vulkanDll = @(
    "$env:SystemRoot\System32\vulkan-1.dll",
    "$env:SystemRoot\SysWOW64\vulkan-1.dll"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($vulkanDll) {
    Write-Ok "Vulkan runtime found: $vulkanDll"
} else {
    Write-Warn "Vulkan runtime (vulkan-1.dll) not found."
    Write-Warn "Install GPU drivers or the Vulkan SDK: https://vulkan.lunarg.com/sdk/home#windows"
    Write-Warn "Flux will fail to start the GPU pipeline without it."
}

# --------------------------------------------------------------------------- #
# 6. Check / install FFmpeg (needed by PyAV)
# --------------------------------------------------------------------------- #
Write-Info "Checking for FFmpeg..."
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Warn "FFmpeg not found in PATH."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "Installing FFmpeg via winget..."
        winget install --id Gyan.FFmpeg -e --source winget --accept-package-agreements --accept-source-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH','Machine') + ';' +
                    [System.Environment]::GetEnvironmentVariable('PATH','User')
    } else {
        Write-Warn "Could not auto-install FFmpeg. Download from https://ffmpeg.org/download.html and add to PATH."
    }
} else {
    Write-Ok "FFmpeg found: $(ffmpeg -version 2>&1 | Select-Object -First 1)"
}

# --------------------------------------------------------------------------- #
# 7. Create virtual environment
# --------------------------------------------------------------------------- #
$VenvDir    = Join-Path $ScriptDir '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$VenvPip    = Join-Path $VenvDir 'Scripts\pip.exe'

if (Test-Path $VenvDir) {
    Write-Info "Virtual environment already exists at .venv — skipping creation"
} else {
    Write-Info "Creating virtual environment at .venv ..."
    & $pythonExe -m venv $VenvDir
    Write-Ok "Virtual environment created"
}

# --------------------------------------------------------------------------- #
# 8. Upgrade pip / wheel / setuptools
# --------------------------------------------------------------------------- #
Write-Info "Upgrading pip, wheel, setuptools..."
& $VenvPip install --quiet --upgrade pip wheel setuptools
Write-Ok "pip ready"

# --------------------------------------------------------------------------- #
# 9. Install Python dependencies
# --------------------------------------------------------------------------- #
$reqFile = Join-Path $ScriptDir 'requirements.txt'
if (Test-Path $reqFile) {
    Write-Info "Installing Python dependencies from requirements.txt..."
    & $VenvPip install -r $reqFile
    Write-Ok "Python dependencies installed"
} else {
    Exit-WithError "requirements.txt not found in $ScriptDir"
}

# --------------------------------------------------------------------------- #
# 10. Verify critical imports
# --------------------------------------------------------------------------- #
Write-Info "Verifying critical imports..."
$failed = @()
foreach ($pkg in @('flask','wgpu','numpy','PIL','sounddevice','av')) {
    $null = & $VenvPython -c "import $pkg" 2>&1
    if ($LASTEXITCODE -ne 0) { $failed += $pkg }
}
if ($failed.Count -gt 0) {
    Write-Warn "These packages failed to import: $($failed -join ', ')"
    Write-Warn "Run: .venv\Scripts\pip install $($failed -join ' ')"
} else {
    Write-Ok "All critical packages verified"
}

# --------------------------------------------------------------------------- #
# 11. Create required runtime directories
# --------------------------------------------------------------------------- #
Write-Info "Creating runtime directories..."
foreach ($dir in @('logs','data','projects','records','snapshots','thumbnails','video','audio','backgrounds')) {
    $path = Join-Path $ScriptDir $dir
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
}
Write-Ok "Runtime directories ready"

# --------------------------------------------------------------------------- #
# 12. Write flux.bat launch script
# --------------------------------------------------------------------------- #
$LaunchBat = Join-Path $ScriptDir 'flux.bat'
@"
@echo off
REM Flux launch script — generated by install.ps1
cd /d "%~dp0"
".venv\Scripts\python.exe" "src\main.py" %*
"@ | Set-Content -Encoding ASCII $LaunchBat
Write-Ok "Launch script written to flux.bat"

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "    Installation complete!" -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Start Flux:    " -NoNewline; Write-Host ".\flux.bat" -ForegroundColor Cyan
Write-Host "  Direct run:    " -NoNewline; Write-Host ".venv\Scripts\python src\main.py" -ForegroundColor Cyan
Write-Host "  Web UI:        " -NoNewline; Write-Host "http://localhost:5000" -ForegroundColor Cyan -NoNewline; Write-Host "  (after starting)"
Write-Host ""
Write-Host "  Note: A Vulkan-capable GPU driver is required for the GPU" -ForegroundColor Yellow
Write-Host "        rendering pipeline. If you see wgpu errors, update" -ForegroundColor Yellow
Write-Host "        your GPU drivers or install the Vulkan SDK." -ForegroundColor Yellow
Write-Host ""
