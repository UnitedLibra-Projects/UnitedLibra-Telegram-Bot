$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectPath ".venv\\Scripts\\python.exe"
$envPath = Join-Path $projectPath ".env"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Не найден .venv. Сначала создай окружение и установи зависимости."
    exit 1
}

if (-not (Test-Path $envPath)) {
    Write-Error "Не найден .env. Открой $envPath и заполни BOT_TOKEN."
    exit 1
}

$envContent = Get-Content -LiteralPath $envPath -Raw
if ($envContent -match "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE") {
    Write-Error "Открой .env и вставь реальный BOT_TOKEN."
    exit 1
}

& $pythonPath (Join-Path $projectPath "bot.py")
