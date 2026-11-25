param([string]$Request,[string]$Result)
$ErrorActionPreference='Stop'
$c=$null; $opened=$false; $connected=$false
$out=@{responses=@{};error='';plc=''}
try {
 $req=Get-Content -LiteralPath $Request -Raw -Encoding UTF8 | ConvertFrom-Json
 Add-Type -AssemblyName System.Windows.Forms
 $dll='C:\Program Files (x86)\OMRON\CX-Server Lite\dot net\Examples\C#\LITEC#Net\exe\cxslite.dll'
 [void][Reflection.Assembly]::LoadFrom($dll)
 $c=New-Object CXSLite.CXSLiteCtrl
 $connected=$c.Connect([string]$req.cdm); if (!$connected) {throw $c.GetLastError()}
 [string[]]$names=$null
 [void]$c.ListDevices([ref]$names)
 $names=@($names | Where-Object {$_})
 if ($names.Count -ne 1) {throw 'Select a CDM with exactly one PLC'}
 $plc=$names[0]; $out.plc=$plc
 if ($req.mode -eq 'upload') {
   $ok=$c.UploadProgram($plc, '', [string]$req.dest, $true, $false)
   if (!$ok) {throw $c.GetLastError()}
   if (!(Test-Path -LiteralPath $req.dest -PathType Leaf)) {throw 'No program file'}
 } else {
 $opened=$c.OpenDevice($plc); if (!$opened) {throw $c.GetLastError()}
 foreach ($cmd in $req.commands) {
   if ($cmd -notmatch '^0101(B0|B1|B2|B3|82|09|89)[0-9A-F]{4}000001$') {throw 'Read command rejected'}
   [string]$response=''
   try {
     $ok=$c.RawFINS([string]$cmd,$plc,[CXSLite.UnitNumber]::PLC_CPU,$true,[ref]$response)
     $out.responses[$cmd]=@{ok=$ok;response=$response}
   } catch {$out.responses[$cmd]=@{ok=$false;response=[string]$_}}
 }
}
} catch {$out.error=[string]$_} finally {
 if ($opened) {try {[void]$c.CloseDevice($plc)} catch {}}
 if ($connected) {try {[void]$c.Disconnect()} catch {}}
 if ($c) {try {$c.Dispose()} catch {}}
 $out | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Result -Encoding UTF8
}
