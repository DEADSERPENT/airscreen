<#
  Removes the installed app and shortcuts. Your settings, paired TVs and logs in %APPDATA%\AirScreen are kept
  unless you pass -RemoveData.
#>
param([switch]$RemoveData)
Get-Process AirScreen -ErrorAction SilentlyContinue | Stop-Process -Force
$dest = Join-Path $env:LOCALAPPDATA "Programs\AirScreen"
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
foreach ($dir in @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop"))) {
  Remove-Item (Join-Path $dir "AirScreen.lnk") -ErrorAction SilentlyContinue
}
if ($RemoveData) { Remove-Item (Join-Path $env:APPDATA "AirScreen") -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "AirScreen removed."
