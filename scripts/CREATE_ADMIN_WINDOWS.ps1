$ErrorActionPreference = 'Stop'
Write-Host 'TurAgent AI - birinchi admin yaratish' -ForegroundColor Cyan
$site=(Read-Host 'Sayt manzili (masalan https://turagent-ai.username.workers.dev)').TrimEnd('/')
$name=Read-Host 'Administrator ismi'
$email=Read-Host 'Administrator emaili'
$setup=Read-Host 'ADMIN_SETUP_TOKEN' -AsSecureString
$password=Read-Host 'Admin paroli (kamida 12 belgi)' -AsSecureString
$tokenText=[System.Net.NetworkCredential]::new('',$setup).Password
$passText=[System.Net.NetworkCredential]::new('',$password).Password
try {
  $payload=@{token=$tokenText;name=$name;email=$email;password=$passText}|ConvertTo-Json -Compress
  $result=Invoke-RestMethod -Method Post -Uri "$site/api/admin/bootstrap" -Headers @{'X-Turagent-Request'='1'; Origin=$site} -ContentType 'application/json' -Body $payload
  Write-Host 'ADMIN YARATILDI. Saytdan Kirish orqali akkauntga kiring.' -ForegroundColor Green
} finally { $tokenText=$null; $passText=$null; $payload=$null }
