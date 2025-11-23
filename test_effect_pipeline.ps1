# Effect Pipeline Integration - Test Script
# Fuehre diesen Test aus nachdem Flux neu gestartet wurde

Write-Host "=== Effect Pipeline Integration Tests ===" -ForegroundColor Cyan
Write-Host ""

# Pre-Check: Load a video first to have an active player
Write-Host "Pre-Check: Loading video..." -ForegroundColor Magenta
try {
    $videos = Invoke-WebRequest -Uri "http://localhost:5000/api/videos/list" -Method GET | ConvertFrom-Json
    if ($videos.videos.Count -gt 0) {
        $videoPath = $videos.videos[0].path
        $loadBody = @{ video_path = $videoPath } | ConvertTo-Json
        $loadResult = Invoke-WebRequest -Uri "http://localhost:5000/api/load" -Method POST -ContentType "application/json" -Body $loadBody | ConvertFrom-Json
        Write-Host "Video loaded: $videoPath" -ForegroundColor Green
    } else {
        Write-Host "No videos found, effects API may return 404" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Could not load video: $($_.Exception.Message)" -ForegroundColor Yellow
}
Write-Host ""

# Test 1: Get empty effect chain
Write-Host "Test 1: GET /api/player/effects (leer)" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 3
Write-Host ""

# Test 2: Add blur effect
Write-Host "Test 2: POST /api/player/effects/add (blur)" -ForegroundColor Yellow
$body = @{
    plugin_id = "blur"
    config = @{
        strength = 5.0
    }
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/add" -Method POST -ContentType "application/json" -Body $body
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 3
Write-Host ""

# Test 3: Get effect chain (should have 1 effect)
Write-Host "Test 3: GET /api/player/effects (mit blur)" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 5
Write-Host ""

# Test 4: Update blur strength parameter
Write-Host "Test 4: POST /api/player/effects/0/parameters/strength" -ForegroundColor Yellow
$body = @{
    value = 15.0
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/0/parameters/strength" -Method POST -ContentType "application/json" -Body $body
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 3
Write-Host ""

# Test 5: Get effect chain (strength should be 15.0)
Write-Host "Test 5: GET /api/player/effects (strength updated)" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 5
Write-Host ""

# Test 6: Remove effect
Write-Host "Test 6: DELETE /api/player/effects/0" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/0" -Method DELETE
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 3
Write-Host ""

# Test 7: Get empty effect chain again
Write-Host "Test 7: GET /api/player/effects (leer nach remove)" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 3
Write-Host ""

# Test 8: Add multiple effects
Write-Host "Test 8: Add multiple effects" -ForegroundColor Yellow
$body1 = @{ plugin_id = "blur"; config = @{ strength = 3.0 } } | ConvertTo-Json
$body2 = @{ plugin_id = "blur"; config = @{ strength = 7.0 } } | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/add" -Method POST -ContentType "application/json" -Body $body1 | Out-Null
Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/add" -Method POST -ContentType "application/json" -Body $body2 | Out-Null

$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET
$data = $response.Content | ConvertFrom-Json
Write-Host "Effect Chain (2 effects):" -ForegroundColor Green
$data | ConvertTo-Json -Depth 5
Write-Host ""

# Test 9: Clear all effects
Write-Host "Test 9: POST /api/player/effects/clear" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/clear" -Method POST
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 3
Write-Host ""

# Test 10: Verify empty chain
Write-Host "Test 10: GET /api/player/effects (leer nach clear)" -ForegroundColor Yellow
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET
$data = $response.Content | ConvertFrom-Json
Write-Host "Response:" -ForegroundColor Green
$data | ConvertTo-Json -Depth 3
Write-Host ""

Write-Host "=== Alle Tests abgeschlossen ===" -ForegroundColor Cyan
