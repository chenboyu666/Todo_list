$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

function Remove-ProjectDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $targetPath = Join-Path -Path $ProjectRoot -ChildPath $RelativePath
    if (-not (Test-Path -LiteralPath $targetPath)) {
        return
    }

    $rootPath = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ProjectRoot).Path).TrimEnd('\', '/')
    $resolvedTarget = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $targetPath).Path)

    if (-not $resolvedTarget.StartsWith($rootPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove '$resolvedTarget' because it is outside project root '$rootPath'."
    }

    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

if (-not (Test-Path -LiteralPath ".venv")) {
    python -m venv ".venv"
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r "requirements.txt"

Remove-ProjectDirectory -RelativePath "build"
Remove-ProjectDirectory -RelativePath "dist"

& ".venv\Scripts\pyinstaller.exe" @(
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name",
    "FloatingTodo",
    "--add-data",
    "src/floating_todo/assets;floating_todo/assets",
    "--collect-all",
    "PySide6",
    "src/floating_todo/__main__.py"
)

New-Item -ItemType Directory -Force -Path "dist/FloatingTodo/data" | Out-Null
Write-Host "Build complete: dist/FloatingTodo/FloatingTodo.exe"
