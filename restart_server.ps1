# Restart the Py_artnet server

Write-Host "Stopping all Python processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

Start-Sleep -Seconds 2

Write-Host "Starting server..." -ForegroundColor Green
cd $PSScriptRoot
python src\main.py

Write-Host "Server started!" -ForegroundColor Green
