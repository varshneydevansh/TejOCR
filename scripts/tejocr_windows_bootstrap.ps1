# TejOCR Windows bootstrap helper for LibreOffice Python
#
# Usage examples:
#   powershell -ExecutionPolicy Bypass -File .\scripts\tejocr_windows_bootstrap.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\tejocr_windows_bootstrap.ps1 -InstallPdfFallback
#   powershell -ExecutionPolicy Bypass -File .\scripts\tejocr_windows_bootstrap.ps1 -InstallPdfFallback -InstallCompatExtras

param(
    [string]$LibreOfficePython = "C:\Program Files\LibreOffice\program\python.exe",
    [switch]$InstallPdfFallback,
    [switch]$InstallCompatExtras
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Ensure-LibreOfficePython {
    if (-not (Test-Path $LibreOfficePython)) {
        throw "LibreOffice Python not found at: $LibreOfficePython"
    }
}

function Test-PipAvailable {
    try {
        & $LibreOfficePython -m pip --version *> $null
        return $true
    }
    catch {
        return $false
    }
}

function Ensure-Pip {
    if (Test-PipAvailable) {
        Write-Host "pip is already available in LibreOffice Python." -ForegroundColor Green
        return
    }

    Write-Step "Bootstrapping pip in LibreOffice Python"
    $programDir = Split-Path -Parent $LibreOfficePython
    Push-Location $programDir
    try {
        (Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -UseBasicParsing).Content | & $LibreOfficePython -
    }
    finally {
        Pop-Location
    }
}

function Install-Packages {
    param([string[]]$Packages)
    if (-not $Packages -or $Packages.Count -eq 0) {
        return
    }
    Write-Step ("Installing LibreOffice Python packages: " + ($Packages -join ", "))
    & $LibreOfficePython -m pip install @Packages
}

function Show-BinaryStatus {
    param(
        [string]$Name,
        [string]$Hint
    )
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        Write-Host "$Name: found at $($command.Source)" -ForegroundColor Green
    }
    else {
        Write-Host "$Name: not found. $Hint" -ForegroundColor Yellow
    }
}

Write-Step "Checking LibreOffice Python"
Ensure-LibreOfficePython
Write-Host "LibreOffice Python: $LibreOfficePython" -ForegroundColor Green

Ensure-Pip

Install-Packages -Packages @("pillow")

if ($InstallPdfFallback) {
    Install-Packages -Packages @("pdf2image")
}

if ($InstallCompatExtras) {
    Install-Packages -Packages @("numpy", "pytesseract")
}

Write-Step "Checking OCR runtime tools"
Show-BinaryStatus -Name "tesseract" -Hint "Install Tesseract from UB Mannheim or Chocolatey."
Show-BinaryStatus -Name "pdftoppm" -Hint "Install Poppler if you want PDF OCR support."
Show-BinaryStatus -Name "mutool" -Hint "Install MuPDF tools if you want an alternative PDF renderer."

Write-Step "Done"
Write-Host "Restart LibreOffice or use Validate / Refresh in TejOCR Setup & Diagnostics." -ForegroundColor Green
