# Library Update Script for Py_artnet
# Run this script periodically to check for and download updated library versions

Write-Host "=== Frontend Library Update Script ===" -ForegroundColor Cyan
Write-Host ""

# Library definitions
$libraries = @(
    @{
        Name = "Bootstrap"
        Version = "5.3.0"
        Files = @(
            @{ Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"; Path = "bootstrap/css/bootstrap.min.css" }
            @{ Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"; Path = "bootstrap/js/bootstrap.bundle.min.js" }
        )
    },
    @{
        Name = "Ion RangeSlider"
        Version = "2.3.1"
        Files = @(
            @{ Url = "https://cdnjs.cloudflare.com/ajax/libs/ion-rangeslider/2.3.1/css/ion.rangeSlider.min.css"; Path = "ion-rangeslider/css/ion.rangeSlider.min.css" }
            @{ Url = "https://cdnjs.cloudflare.com/ajax/libs/ion-rangeslider/2.3.1/js/ion.rangeSlider.min.js"; Path = "ion-rangeslider/js/ion.rangeSlider.min.js" }
        )
    },
    @{
        Name = "Chart.js"
        Version = "latest"
        Files = @(
            @{ Url = "https://cdn.jsdelivr.net/npm/chart.js"; Path = "chartjs/chart.min.js" }
        )
    },
    @{
        Name = "Bootstrap Icons"
        Version = "1.11.1"
        Files = @(
            @{ Url = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css"; Path = "bootstrap-icons/bootstrap-icons.css" }
        )
    },
    @{
        Name = "WaveSurfer.js"
        Version = "7.x"
        Files = @(
            @{ Url = "https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js"; Path = "wavesurfer/dist/wavesurfer.esm.js" }
            @{ Url = "https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/regions.esm.js"; Path = "wavesurfer/dist/plugins/regions.esm.js" }
            @{ Url = "https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/timeline.esm.js"; Path = "wavesurfer/dist/plugins/timeline.esm.js" }
        )
    }
)

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Function to download file with progress
function Download-Library {
    param(
        [string]$Url,
        [string]$OutputPath
    )
    
    $fullPath = Join-Path $scriptDir $OutputPath
    
    # Create directory if it doesn't exist
    $directory = Split-Path -Parent $fullPath
    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    
    try {
        Write-Host "  Downloading: $OutputPath..." -NoNewline
        Invoke-WebRequest -Uri $Url -OutFile $fullPath -ErrorAction Stop
        $fileSize = (Get-Item $fullPath).Length
        $fileSizeKB = [math]::Round($fileSize / 1KB, 2)
        Write-Host " OK ($fileSizeKB KB)" -ForegroundColor Green
        return $true
    } catch {
        Write-Host " FAILED" -ForegroundColor Red
        Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Main update loop
$totalFiles = 0
$successFiles = 0
$failedFiles = 0

foreach ($library in $libraries) {
    Write-Host ""
    Write-Host "$($library.Name) v$($library.Version)" -ForegroundColor Yellow
    Write-Host ("-" * 50)
    
    foreach ($file in $library.Files) {
        $totalFiles++
        if (Download-Library -Url $file.Url -OutputPath $file.Path) {
            $successFiles++
        } else {
            $failedFiles++
        }
    }
}

# Summary
Write-Host ""
Write-Host "=== Update Summary ===" -ForegroundColor Cyan
Write-Host "Total files: $totalFiles"
Write-Host "Success: $successFiles" -ForegroundColor Green
Write-Host "Failed: $failedFiles" -ForegroundColor $(if ($failedFiles -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($failedFiles -eq 0) {
    Write-Host "All libraries updated successfully!" -ForegroundColor Green
} else {
    Write-Host "Some libraries failed to update. Check errors above." -ForegroundColor Yellow
}

# Pause at the end
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
