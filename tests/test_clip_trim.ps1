# Test script for Clip Trimming & Playback Control API
# Usage: .\test_clip_trim.ps1

$BASE_URL = "http://localhost:5000"
$PLAYER_ID = "video"  # or "artnet"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Clip Trimming API Test" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 1. Get current playlist to find a clip_id
Write-Host "1. Getting playlist to find clip_id..." -ForegroundColor Yellow
$playlist = Invoke-RestMethod -Uri "$BASE_URL/api/player/$PLAYER_ID/playlist" -Method Get
if ($playlist.playlist -and $playlist.playlist.Count -gt 0) {
    $first_clip = $playlist.playlist[0]
    $clip_id = $first_clip.clip_id
    $video_name = $first_clip.name
    Write-Host "   Found clip: $video_name (ID: $clip_id)" -ForegroundColor Green
} else {
    Write-Host "   No clips in playlist! Please load a video first." -ForegroundColor Red
    exit 1
}

Write-Host ""

# 2. Get current playback info
Write-Host "2. Getting current playback info..." -ForegroundColor Yellow
try {
    $playback_info = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/playback" -Method Get
    Write-Host "   Current settings:" -ForegroundColor Green
    Write-Host "     In Point: $($playback_info.in_point)" -ForegroundColor White
    Write-Host "     Out Point: $($playback_info.out_point)" -ForegroundColor White
    Write-Host "     Reverse: $($playback_info.reverse)" -ForegroundColor White
    Write-Host "     Total Frames: $($playback_info.total_frames)" -ForegroundColor White
} catch {
    Write-Host "   Error getting playback info: $_" -ForegroundColor Red
}

Write-Host ""

# 3. Set trim points (first 30 frames)
Write-Host "3. Setting trim points (frames 10-30)..." -ForegroundColor Yellow
$trim_body = @{
    in_point = 10
    out_point = 30
} | ConvertTo-Json

try {
    $trim_result = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/trim" -Method Post -Body $trim_body -ContentType "application/json"
    Write-Host "   Trim set successfully: $($trim_result.message)" -ForegroundColor Green
} catch {
    Write-Host "   Error setting trim: $_" -ForegroundColor Red
}

Write-Host ""

# 4. Enable reverse playback
Write-Host "4. Enabling reverse playback..." -ForegroundColor Yellow
$reverse_body = @{
    enabled = $true
} | ConvertTo-Json

try {
    $reverse_result = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/reverse" -Method Post -Body $reverse_body -ContentType "application/json"
    Write-Host "   Reverse enabled: $($reverse_result.message)" -ForegroundColor Green
} catch {
    Write-Host "   Error setting reverse: $_" -ForegroundColor Red
}

Write-Host ""

# 5. Get updated playback info
Write-Host "5. Getting updated playback info..." -ForegroundColor Yellow
try {
    $playback_info = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/playback" -Method Get
    Write-Host "   Updated settings:" -ForegroundColor Green
    Write-Host "     In Point: $($playback_info.in_point)" -ForegroundColor White
    Write-Host "     Out Point: $($playback_info.out_point)" -ForegroundColor White
    Write-Host "     Reverse: $($playback_info.reverse)" -ForegroundColor White
    Write-Host "     Effective Duration: $($playback_info.effective_duration) frames" -ForegroundColor White
} catch {
    Write-Host "   Error getting playback info: $_" -ForegroundColor Red
}

Write-Host ""

# 6. Wait for user to test playback
Write-Host "6. Test playback now - you should see:" -ForegroundColor Cyan
Write-Host "   - Playback starts at frame 10" -ForegroundColor White
Write-Host "   - Playback ends at frame 30 (21 frames total)" -ForegroundColor White
Write-Host "   - Video plays in REVERSE (frame 30 -> 10)" -ForegroundColor White
Write-Host ""
Write-Host "   Press Enter when done testing..." -ForegroundColor Yellow
$null = Read-Host

Write-Host ""

# 7. Reset trim
Write-Host "7. Resetting trim to full clip..." -ForegroundColor Yellow
try {
    $reset_result = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/reset-trim" -Method Post
    Write-Host "   Trim reset: $($reset_result.message)" -ForegroundColor Green
} catch {
    Write-Host "   Error resetting trim: $_" -ForegroundColor Red
}

Write-Host ""

# 8. Disable reverse
Write-Host "8. Disabling reverse playback..." -ForegroundColor Yellow
$reverse_body = @{
    enabled = $false
} | ConvertTo-Json

try {
    $reverse_result = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/reverse" -Method Post -Body $reverse_body -ContentType "application/json"
    Write-Host "   Reverse disabled: $($reverse_result.message)" -ForegroundColor Green
} catch {
    Write-Host "   Error disabling reverse: $_" -ForegroundColor Red
}

Write-Host ""

# 9. Final playback info
Write-Host "9. Final playback info (should be back to defaults)..." -ForegroundColor Yellow
try {
    $playback_info = Invoke-RestMethod -Uri "$BASE_URL/api/clips/$clip_id/playback" -Method Get
    Write-Host "   Final settings:" -ForegroundColor Green
    Write-Host "     In Point: $($playback_info.in_point)" -ForegroundColor White
    Write-Host "     Out Point: $($playback_info.out_point)" -ForegroundColor White
    Write-Host "     Reverse: $($playback_info.reverse)" -ForegroundColor White
} catch {
    Write-Host "   Error getting playback info: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Test Complete!" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
