$ErrorActionPreference='Stop'
$site=(Read-Host 'Sayt manzili (https://...)').TrimEnd('/')
foreach ($path in @('/api/health','/api/config','/api/catalog','/api/posts')) {
 try { $r=Invoke-WebRequest -UseBasicParsing "$site$path" -TimeoutSec 20; Write-Host "$path  OK $($r.StatusCode)" -ForegroundColor Green }
 catch { Write-Host "$path  ERROR: $($_.Exception.Message)" -ForegroundColor Red }
}
