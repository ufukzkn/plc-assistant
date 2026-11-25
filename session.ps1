param([string]$Folder,[string]$Cdm)
$ErrorActionPreference='Stop'
$c=$null; $opened=$false; $connected=$false
try {
 Add-Type -AssemblyName System.Windows.Forms
 [void][Reflection.Assembly]::LoadFrom('C:\Program Files (x86)\OMRON\CX-Server Lite\dot net\Examples\C#\LITEC#Net\exe\cxslite.dll')
 $c=New-Object CXSLite.CXSLiteCtrl
 $connected=$c.Connect($Cdm); if (!$connected) {throw $c.GetLastError()}
 [string[]]$names=$null; [void]$c.ListDevices([ref]$names)
 $names=@($names | Where-Object {$_}); if ($names.Count -ne 1) {throw 'Select exactly one PLC'}
 $plc=$names[0]; $opened=$c.OpenDevice($plc); if (!$opened) {throw $c.GetLastError()}
 while (!(Test-Path -LiteralPath (Join-Path $Folder 'stop'))) {
  [System.Windows.Forms.Application]::DoEvents()
  $p=Join-Path $Folder 'request.json'
  if (!(Test-Path -LiteralPath $p)) {Start-Sleep -Milliseconds 10; continue}
  $out=@{responses=@{};error='';plc=$plc}
  try {
   $req=Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
   Remove-Item -LiteralPath $p
   foreach ($cmd in $req.commands) {
    if ($cmd -cnotmatch '^0101(B0|B1|B2|B3|82|09|89)([0-9A-F]{4})00([0-9A-F]{4})$') {throw 'Read command rejected'}
    $area=$Matches[1]; $start=[Convert]::ToInt32($Matches[2],16); $count=[Convert]::ToInt32($Matches[3],16); $end=$start+$count-1
    if ($count -lt 1 -or $count -gt 16 -or $end -gt 65535) {throw 'Read block range rejected'}
    if (($area -eq '09' -or $area -eq '89') -and !(($end -le 4095) -or ($start -ge 32768 -and $end -le 36863))) {throw 'TC range rejected'}
    [string]$response=''
    $ok=$c.RawFINS([string]$cmd,$plc,[CXSLite.UnitNumber]::PLC_CPU,$true,[ref]$response)
    $out.responses[$cmd]=@{ok=$ok;response=$response}
   }
  } catch {$out.error=[string]$_}
  $out | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Folder 'result.tmp') -Encoding UTF8
  Move-Item -LiteralPath (Join-Path $Folder 'result.tmp') -Destination (Join-Path $Folder 'result.json')
 }
} catch { [string]$_ | Set-Content -LiteralPath (Join-Path $Folder 'error.txt') -Encoding UTF8 } finally {
 if ($opened) {try {[void]$c.CloseDevice($plc)} catch {}}
 if ($connected) {try {[void]$c.Disconnect()} catch {}}
 if ($c) {try {$c.Dispose()} catch {}}
}
