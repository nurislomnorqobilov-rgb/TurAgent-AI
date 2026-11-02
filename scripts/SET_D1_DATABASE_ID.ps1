$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host 'Cloudflare D1: npx wrangler d1 create turagent-ai-db' -ForegroundColor Cyan
$id = Read-Host 'Cloudflare javobidagi database_id (UUID) ni kiriting'
if ($id -notmatch '^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$') { throw 'Database ID formati noto‘g‘ri. Hech qanday fayl o‘zgarmadi.' }
$cfg=Join-Path (Get-Location) 'wrangler.jsonc'
$text=Get-Content -Raw -Encoding UTF8 $cfg
$text=[regex]::Replace($text,'"database_id"\s*:\s*"[^"]+"','"database_id": "'+$id+'"')
[IO.File]::WriteAllText($cfg,$text,(New-Object System.Text.UTF8Encoding($false)))
Write-Host 'D1 database_id sozlandi. Keyingi qadam: npm run db:remote' -ForegroundColor Green
