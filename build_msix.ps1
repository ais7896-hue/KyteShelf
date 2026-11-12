param(
    [string]$Publisher = "CN=DEB06DA5-350C-4F65-AA47-ABBA1EDB5BC4",
    [string]$PublisherDisplayName = "Aisming",
    [string]$IdentityName = "Aisming.kyteshelf",
    [switch]$SkipSign
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Set-Location -Path $PSScriptRoot

$appName = "KyteShelf"
$appVersion = "1.4.5"
if (Test-Path "version.json") {
    try {
        $vJson = Get-Content "version.json" -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($vJson.version) { $appVersion = $vJson.version }
    } catch {}
}

$versionParts = $appVersion.Split('.')
while ($versionParts.Count -lt 4) { $versionParts += "0" }
$msixVersion = ($versionParts[0..3]) -join "."

Write-Host "`n>>> [MSIX] Packaging $appName v$appVersion (MSIX Version: $msixVersion)..." -ForegroundColor Cyan

$distDir = Join-Path $PSScriptRoot "dist\$appName"
if (-not (Test-Path (Join-Path $distDir "$appName.exe"))) {
    Write-Error "PyInstaller output not found at $distDir. Please run build_installer.ps1 first."
    exit 1
}

# 1. Ensure MSIX PNG assets exist
$assetsDir = Join-Path $PSScriptRoot "msix\Assets"
if (-not (Test-Path (Join-Path $assetsDir "StoreLogo.png"))) {
    New-Item -ItemType Directory -Force $assetsDir | Out-Null
    $pyCmd = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
    $genCode = @"
import sys, os
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QIcon, QColor
from PySide6.QtCore import Qt
app = QGuiApplication(sys.argv)
icon = QIcon(r'icon.ico')
src_img = icon.pixmap(256, 256).toImage()
for name, w, h in [('StoreLogo.png',50,50),('Square44x44Logo.png',44,44),('Square150x150Logo.png',150,150),('Wide310x150Logo.png',310,150)]:
    c = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    c.fill(QColor(0,0,0,0))
    p = QPainter(c)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    side = int(min(w,h)*0.72) if w>=150 else min(w,h)
    s = src_img.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    p.drawImage((w-s.width())//2, (h-s.height())//2, s)
    p.end()
    c.save(os.path.join(r'msix\Assets', name), 'PNG')
"@
    & $pyCmd -c $genCode
}

# 2. Update AppxManifest.xml version and publisher (only in Identity/Properties, preserving MinVersion)
$manifestPath = Join-Path $PSScriptRoot "msix\AppxManifest.xml"
[xml]$xmlDoc = Get-Content -Path $manifestPath -Encoding UTF8
$xmlDoc.Package.Identity.Name = $IdentityName
$xmlDoc.Package.Identity.Publisher = $Publisher
$xmlDoc.Package.Identity.Version = $msixVersion
$xmlDoc.Package.Properties.PublisherDisplayName = $PublisherDisplayName
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$sw = New-Object System.IO.StreamWriter($manifestPath, $false, $utf8NoBom)
$xmlDoc.Save($sw)
$sw.Close()

# 3. Locate or bootstrap MakeAppx.exe and SignTool.exe
function Find-SdkTool([string]$toolName) {
    $searchRoots = @(
        "C:\Program Files (x86)\Windows Kits\10\bin",
        (Join-Path $env:LOCALAPPDATA "KyteTools\WindowsSDK\bin")
    )
    foreach ($root in $searchRoots) {
        if (Test-Path $root) {
            $found = Get-ChildItem -Path $root -Recurse -Filter $toolName -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match "\\x64\\" } |
                Sort-Object FullName -Descending |
                Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    return $null
}

$makeAppx = Find-SdkTool "makeappx.exe"
$signTool = Find-SdkTool "signtool.exe"

if (-not $makeAppx -or -not $signTool) {
    Write-Host ">>> Downloading official Microsoft.Windows.SDK.BuildTools NuGet package..." -ForegroundColor Yellow
    $sdkCacheDir = Join-Path $env:LOCALAPPDATA "KyteTools\WindowsSDK"
    New-Item -ItemType Directory -Force $sdkCacheDir | Out-Null
    $nupkgZip = Join-Path $sdkCacheDir "sdk_buildtools.zip"
    Invoke-WebRequest -Uri "https://www.nuget.org/api/v2/package/Microsoft.Windows.SDK.BuildTools" -OutFile $nupkgZip -UseBasicParsing
    Expand-Archive -Path $nupkgZip -DestinationPath $sdkCacheDir -Force
    Remove-Item $nupkgZip -Force -ErrorAction SilentlyContinue
    $makeAppx = Find-SdkTool "makeappx.exe"
    $signTool = Find-SdkTool "signtool.exe"
}

if (-not $makeAppx) {
    Write-Error "Could not locate makeappx.exe"
    exit 1
}

# 4. Generate MakeAppx mapping file
$mappingPath = Join-Path $PSScriptRoot "msix\mapping.txt"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("[Files]")
$lines.Add("`"$manifestPath`" `"AppxManifest.xml`"")

Get-ChildItem -Path $assetsDir -File | ForEach-Object {
    $lines.Add("`"$($_.FullName)`" `"Assets\$($_.Name)`"")
}

$distResolved = (Resolve-Path $distDir).Path.TrimEnd('\')
Get-ChildItem -Path $distResolved -Recurse -File | ForEach-Object {
    $relPath = $_.FullName.Substring($distResolved.Length + 1)
    $lines.Add("`"$($_.FullName)`" `"$relPath`"")
}

[System.IO.File]::WriteAllLines($mappingPath, $lines, (New-Object System.Text.UTF8Encoding($false)))

# 5. Pack MSIX
$outDir = Join-Path $PSScriptRoot "Output"
New-Item -ItemType Directory -Force $outDir | Out-Null
$outMsix = Join-Path $outDir "${appName}_Setup_v${appVersion}.msix"
if (Test-Path $outMsix) { Remove-Item $outMsix -Force }

Write-Host ">>> Running MakeAppx.exe..." -ForegroundColor Yellow
& $makeAppx pack /f $mappingPath /p $outMsix /o /nv
if ($LASTEXITCODE -ne 0) {
    Write-Error "MakeAppx packaging failed with exit code $LASTEXITCODE"
    exit 1
}
Remove-Item $mappingPath -Force -ErrorAction SilentlyContinue

# 6. Sign MSIX with self-signed certificate
if (-not $SkipSign -and $signTool) {
    Write-Host ">>> Signing MSIX package with $Publisher..." -ForegroundColor Yellow
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -eq $Publisher -and $_.NotAfter -gt (Get-Date) } |
        Select-Object -First 1

    if (-not $cert) {
        $cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher -KeyUsage DigitalSignature `
            -FriendlyName "Kyte Apps MSIX Developer Certificate" `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}") `
            -NotAfter (Get-Date).AddYears(5)
    }

    $cerPath = Join-Path $PSScriptRoot "msix\ais7896-hue.cer"
    Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null

    & $signTool sign /fd SHA256 /sha1 $cert.Thumbprint $outMsix
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "SignTool failed with exit code $LASTEXITCODE (MSIX was created unsigned)"
    } else {
        Write-Host "[OK] Signed MSIX package (Certificate exported to msix\ais7896-hue.cer)" -ForegroundColor Green
    }
}

Write-Host "[SUCCESS] MSIX Installer created: $outMsix" -ForegroundColor Green

