# Complete Clip Trimming Test Script
# This script tests the full trim/reverse workflow including loading a video

$BASE_URL = "http://localhost:5000"
$PLAYER_ID = "video"
$VIDEO_DIR = "video/kanal_1"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Clip Trimming Complete Test" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Check server
Write-Host "[1/10] Checking server status..." -ForegroundColor Yellow
try {
    $status = Invoke-RestMethod -Uri "$BASE_URL/api/player/$PLAYER_ID/status" -Method Get -TimeoutSec 5
    Write-Host "   Success: Server is running" -ForegroundColor Green
}
catch {
    Write-Host "   Error: Server not responding" -ForegroundColor Red
    Write-Host "   Please start: python src/main.py" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Test 2: Prepare video path
Write-Host "[2/10] Preparing video path..." -ForegroundColor Yellow
Write-Host "   Using default path: $VIDEO_DIR" -ForegroundColor White
Write-Host "   Note: Adjust VIDEO_DIR variable if needed" -ForegroundColor Yellow

# List actual files in directory
$videoFolder = Join-Path $PSScriptRoot $VIDEO_DIR
if (Test-Path $videoFolder) {
    $localFiles = Get-ChildItem -Path $videoFolder -Filter *.* | Select-Object -First 1
    if ($localFiles) {
        $videoFileName = $localFiles.Name
        Write-Host "   Found: $videoFileName" -ForegroundColor Green
    }
    else {
        $videoFileName = "test.mp4"
        Write-Host "   Warning: No files found, using: $videoFileName" -ForegroundColor Yellow
    }
}
else {
    $videoFileName = "test.mp4"
    Write-Host "   Warning: Directory not found, using: $videoFileName" -ForegroundColor Yellow
}

Write-Host ""

# Test 3: Load video
Write-Host "[3/10] Loading video..." -ForegroundColor Yellow
# Build absolute path
$absolutePath = Join-Path $PSScriptRoot "$VIDEO_DIR/$videoFileName"
$absolutePath = $absolutePath.Replace('\', '/')
Write-Host "   Path: $absolutePath" -ForegroundColor White
try {
    $body = @{type="video"; path=$absolutePath} | ConvertTo-Json
    $loadResult = Invoke-RestMethod -Uri "$BASE_URL/api/player/$PLAYER_ID/clip/load" -Method Post -Headers @{"Content-Type"="application/json"} -Body $body
    
    if ($loadResult.success) {
        $clip_id = $loadResult.clip_id
        Write-Host "   Success: Video loaded" -ForegroundColor Green
        Write-Host "   Clip ID: $clip_id" -ForegroundColor White
    }
    else {
        Write-Host "   Error: $($loadResult.error)" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "   Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test 4: Get video info
Write-Host "[4/10] Getting video info..." -ForegroundColor Yellow
try {
    $playbackInfo = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/playback" -Method Get
    
    if ($playbackInfo.success) {
        Write-Host "   Success: Info retrieved" -ForegroundColor Green
        Write-Host "   Total Frames: $($playbackInfo.total_frames)" -ForegroundColor White
        
        $totalFrames = $playbackInfo.total_frames
        if ($totalFrames -lt 50) {
            $trimIn = [Math]::Floor($totalFrames * 0.2)
            $trimOut = [Math]::Floor($totalFrames * 0.8)
        }
        else {
            $trimIn = 10
            $trimOut = 40
        }
    }
    else {
        Write-Host "   Error: Failed to get info" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "   Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test 5: Set trim
Write-Host "[5/10] Setting trim ($trimIn to $trimOut)..." -ForegroundColor Yellow
try {
    $body = @{in_point=$trimIn; out_point=$trimOut} | ConvertTo-Json
    $trimResult = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/trim" -Method Post -Headers @{"Content-Type"="application/json"} -Body $body
    
    if ($trimResult.success) {
        Write-Host "   Success: $($trimResult.message)" -ForegroundColor Green
    }
    else {
        Write-Host "   Error: $($trimResult.error)" -ForegroundColor Red
    }
}
catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""

# Test 6: Verify trim
Write-Host "[6/10] Verifying trim..." -ForegroundColor Yellow
try {
    $playbackInfo = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/playback" -Method Get
    
    if ($playbackInfo.in_point -eq $trimIn -and $playbackInfo.out_point -eq $trimOut) {
        Write-Host "   Success: Trim verified" -ForegroundColor Green
        Write-Host "   In: $($playbackInfo.in_point), Out: $($playbackInfo.out_point)" -ForegroundColor White
        Write-Host "   Duration: $($playbackInfo.effective_duration) frames" -ForegroundColor White
    }
    else {
        Write-Host "   Error: Trim mismatch" -ForegroundColor Red
    }
}
catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""

# Test 7: Enable reverse
Write-Host "[7/10] Enabling reverse..." -ForegroundColor Yellow
try {
    $body = @{enabled=$true} | ConvertTo-Json
    $reverseResult = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/reverse" -Method Post -Headers @{"Content-Type"="application/json"} -Body $body
    
    if ($reverseResult.success) {
        Write-Host "   Success: Reverse enabled" -ForegroundColor Green
    }
    else {
        Write-Host "   Error: $($reverseResult.error)" -ForegroundColor Red
    }
}
catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""

# Test 8: Verify reverse
Write-Host "[8/10] Verifying reverse..." -ForegroundColor Yellow
try {
    $playbackInfo = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/playback" -Method Get
    
    if ($playbackInfo.reverse -eq $true) {
        Write-Host "   Success: Reverse verified" -ForegroundColor Green
        Write-Host "   Settings: In=$($playbackInfo.in_point), Out=$($playbackInfo.out_point), Reverse=True" -ForegroundColor White
    }
    else {
        Write-Host "   Error: Reverse not enabled" -ForegroundColor Red
    }
}
catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}

Write-Host ""

# Test 9: Manual playback test
Write-Host "[9/10] Ready for playback test..." -ForegroundColor Yellow
Write-Host "   Expected behavior:" -ForegroundColor Cyan
Write-Host "   - Starts at frame $trimOut" -ForegroundColor White
Write-Host "   - Plays BACKWARDS ($trimOut -> $trimIn)" -ForegroundColor White
Write-Host "   - Loops at frame $trimIn" -ForegroundColor White
Write-Host ""
Write-Host "   Open: http://localhost:5000/player.html" -ForegroundColor Cyan
Write-Host "   Press Enter when done..." -ForegroundColor Yellow
$null = Read-Host

Write-Host ""

# Test 10: Reset
Write-Host "[10/10] Resetting..." -ForegroundColor Yellow

try {
    $resetResult = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/reset-trim" -Method Post
    if ($resetResult.success) {
        Write-Host "   Success: Trim reset" -ForegroundColor Green
    }
}
catch {
    Write-Host "   Error resetting: $_" -ForegroundColor Red
}

try {
    $body = @{enabled=$false} | ConvertTo-Json
    $reverseResult = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/reverse" -Method Post -Headers @{"Content-Type"="application/json"} -Body $body
    if ($reverseResult.success) {
        Write-Host "   Success: Reverse disabled" -ForegroundColor Green
    }
}
catch {
    Write-Host "   Error disabling: $_" -ForegroundColor Red
}

try {
    $playbackInfo = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/playback" -Method Get
    Write-Host "   Final: In=$($playbackInfo.in_point), Out=$($playbackInfo.out_point), Reverse=$($playbackInfo.reverse)" -ForegroundColor White
}
catch {
    Write-Host "   Error verifying: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Test Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
