$ErrorActionPreference = "Stop"

$LO_PATH = "C:\Program Files\LibreOffice\program"
$UNOPKG = Join-Path $LO_PATH "unopkg.com"
$SOFFICE = Join-Path $LO_PATH "soffice.exe"
$EXT_ID = "org.libreoffice.extensions.autosave"

Write-Host "1. Building the extension..." -ForegroundColor Cyan
python build_oxt.py

Write-Host "2. Killing open LibreOffice instances..." -ForegroundColor Cyan
# Kill both the launcher and the main binary, silently ignoring if they aren't running
Stop-Process -Name "soffice" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "soffice.bin" -Force -ErrorAction SilentlyContinue

# Give the OS a moment to fully release file locks on the UNO packages
Start-Sleep -Seconds 2  

Write-Host "3. Uninstalling existing extension..." -ForegroundColor Cyan
# We catch and ignore errors here because 'unopkg remove' will throw an error if the extension isn't currently installed
try {
    & $UNOPKG remove $EXT_ID *>&1 | Out-Null
} catch {
    # Ignore "package not found" errors
}

Write-Host "4. Installing the new extension..." -ForegroundColor Cyan
& $UNOPKG add -f dist\AutoSave.oxt

Write-Host "5. Starting LibreOffice Writer..." -ForegroundColor Cyan
Start-Process -FilePath $SOFFICE -ArgumentList "--writer"

Write-Host "Deployment complete! Writer is launching in the background." -ForegroundColor Green
