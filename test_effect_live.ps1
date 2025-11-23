# Effect Pipeline Live Test
# Testet Blur-Effect auf laufendem Video

Write-Host "=== Effect Pipeline Live Test ===" -ForegroundColor Cyan
Write-Host ""

# 1. Video laden
Write-Host "1. Loading video..." -ForegroundColor Yellow
$body = @{ path = "kanal_1/test.mp4" } | ConvertTo-Json
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/api/video/load" -Method POST -ContentType "application/json" -Body $body
    Write-Host "   Video loaded successfully" -ForegroundColor Green
} catch {
    Write-Host "   Error loading video: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 2. Video abspielen
Write-Host "2. Starting playback..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri "http://localhost:5000/api/play" -Method POST | Out-Null
    Write-Host "   Playback started" -ForegroundColor Green
} catch {
    Write-Host "   Error starting playback: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 3. Warte kurz damit Video läuft
Write-Host "3. Waiting 2 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Write-Host "   Video is playing" -ForegroundColor Green
Write-Host ""

# 4. Blur Effect hinzufügen (schwach)
Write-Host "4. Adding Blur Effect (strength: 3.0)..." -ForegroundColor Yellow
$body = @{ plugin_id = "blur"; config = @{ strength = 3.0 } } | ConvertTo-Json
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/add" -Method POST -ContentType "application/json" -Body $body | ConvertFrom-Json
    Write-Host "   Effect added: $($response.message)" -ForegroundColor Green
} catch {
    Write-Host "   Error adding effect: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 5. Zeige aktuelle Effect Chain
Write-Host "5. Current Effect Chain:" -ForegroundColor Yellow
$effects = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET | ConvertFrom-Json
$effects | ConvertTo-Json -Depth 3
Write-Host ""

# 6. Warte und erhöhe Blur-Stärke schrittweise
Write-Host "6. Increasing blur strength in steps..." -ForegroundColor Yellow
$strengths = @(5.0, 8.0, 12.0, 15.0)
foreach ($strength in $strengths) {
    Write-Host "   Setting strength to $strength..." -ForegroundColor Cyan
    $body = @{ value = $strength } | ConvertTo-Json
    Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/0/parameters/strength" -Method POST -ContentType "application/json" -Body $body | Out-Null
    Start-Sleep -Seconds 2
}
Write-Host "   Blur strength progression complete" -ForegroundColor Green
Write-Host ""

# 7. Zeige finale Config
Write-Host "7. Final Effect Config:" -ForegroundColor Yellow
$effects = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET | ConvertFrom-Json
$effects.effects[0] | ConvertTo-Json -Depth 2
Write-Host ""

# 8. Effect entfernen
Write-Host "8. Removing blur effect..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects/0" -Method DELETE | Out-Null
Write-Host "   Effect removed - video should be clear again" -ForegroundColor Green
Write-Host ""

# 9. Zeige leere Chain
Write-Host "9. Effect Chain after removal:" -ForegroundColor Yellow
$effects = Invoke-WebRequest -Uri "http://localhost:5000/api/player/effects" -Method GET | ConvertFrom-Json
Write-Host "   Effects count: $($effects.count)" -ForegroundColor Cyan
Write-Host ""

Write-Host "=== Live Test Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "What you should have seen:" -ForegroundColor Yellow
Write-Host "  1. Video started playing (clear)" -ForegroundColor White
Write-Host "  2. Blur effect applied (slightly blurred)" -ForegroundColor White
Write-Host "  3. Blur increased gradually (3.0 -> 5.0 -> 8.0 -> 12.0 -> 15.0)" -ForegroundColor White
Write-Host "  4. Effect removed (clear again)" -ForegroundColor White
Write-Host ""
Write-Host "Video is still playing. To stop:" -ForegroundColor Yellow
Write-Host "  Invoke-WebRequest -Uri 'http://localhost:5000/api/stop' -Method POST" -ForegroundColor Cyan
