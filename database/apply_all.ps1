## Scout — Apply all migrations and seeds
## Run from PowerShell: .\database\apply_all.ps1
## You will be prompted for the scout password once.

$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$db = "scout"
$user = "scout"

# Set this to avoid password prompts (or leave blank to be prompted each time)
$env:PGPASSWORD = "scout"

$base = Split-Path -Parent $PSScriptRoot
if (-not $base) { $base = "C:\Users\rober\OneDrive\Scout" }

$migrations = @(
    "database\migrations\003_calendar.sql",
    "database\migrations\004_connector_ical_support.sql",
    "database\migrations\005_meals.sql",
    "database\migrations\006_personal_tasks.sql",
    "database\migrations\007_second_brain.sql",
    "database\migrations\008_finance.sql",
    "database\migrations\009_health_fitness.sql"
)

$seeds = @(
    "database\seeds\003_calendar_seed.sql",
    "database\seeds\005_meals_seed.sql",
    "database\seeds\006_personal_tasks_seed.sql",
    "database\seeds\007_second_brain_seed.sql",
    "database\seeds\008_finance_seed.sql",
    "database\seeds\009_health_fitness_seed.sql"
)

Write-Host "`n=== Applying migrations ===" -ForegroundColor Cyan

foreach ($file in $migrations) {
    $path = Join-Path $base $file
    Write-Host "  Running: $file" -ForegroundColor Yellow
    & $psql -U $user -d $db -f $path
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  FAILED: $file" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK" -ForegroundColor Green
}

Write-Host "`n=== Applying seeds ===" -ForegroundColor Cyan

foreach ($file in $seeds) {
    $path = Join-Path $base $file
    Write-Host "  Running: $file" -ForegroundColor Yellow
    & $psql -U $user -d $db -f $path
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  FAILED: $file" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK" -ForegroundColor Green
}

# Clear password from environment
$env:PGPASSWORD = ""

Write-Host "`n=== All migrations and seeds applied successfully ===" -ForegroundColor Green
