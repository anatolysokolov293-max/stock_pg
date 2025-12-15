# Автоматическая замена во всех файлах в папке strategies
$files = Get-ChildItem -Path ".\strategies" -Recurse -Include *.py

Write-Host "Found $($files.Count) Python files" -ForegroundColor Cyan

foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    $changed = $false

    # Заменяем импорт
    if ($content -match "from utils_lot import getlotsize") {
        $content = $content -replace "from utils_lot import getlotsize", "from utils_lot import get_lotsize"
        $changed = $true
    }

    # Заменяем вызовы функции
    if ($content -match "\bgetlotsize\(") {
        $content = $content -replace "\bgetlotsize\(", "get_lotsize("
        $changed = $true
    }

    if ($changed) {
        Set-Content $file.FullName -Value $content -NoNewline -Encoding UTF8
        Write-Host "✓ Updated: $($file.Name)" -ForegroundColor Green
    }
}

Write-Host "`n✓ All files updated successfully!" -ForegroundColor Green
Write-Host "You can now re-run batch_optimize.py" -ForegroundColor Yellow
