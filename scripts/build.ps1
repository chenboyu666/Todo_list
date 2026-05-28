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
    "--onefile",
    "--windowed",
    "--name",
    "Todo list",
    "--add-data",
    "src/floating_todo/assets;floating_todo/assets",
    "--hidden-import",
    "PySide6.QtCore",
    "--hidden-import",
    "PySide6.QtGui",
    "--hidden-import",
    "PySide6.QtWidgets",
    "--hidden-import",
    "PySide6.QtSvg",
    "--hidden-import",
    "PySide6.QtWebEngineCore",
    "--hidden-import",
    "PySide6.QtWebEngineWidgets",
    "--hidden-import",
    "PySide6.QtWebChannel",
    "--exclude-module",
    "PySide6.Qt3DAnimation",
    "--exclude-module",
    "PySide6.Qt3DCore",
    "--exclude-module",
    "PySide6.Qt3DExtras",
    "--exclude-module",
    "PySide6.Qt3DInput",
    "--exclude-module",
    "PySide6.Qt3DRender",
    "--exclude-module",
    "PySide6.QtBluetooth",
    "--exclude-module",
    "PySide6.QtCharts",
    "--exclude-module",
    "PySide6.QtConcurrent",
    "--exclude-module",
    "PySide6.QtDataVisualization",
    "--exclude-module",
    "PySide6.QtDesigner",
    "--exclude-module",
    "PySide6.QtHelp",
    "--exclude-module",
    "PySide6.QtLocation",
    "--exclude-module",
    "PySide6.QtMultimedia",
    "--exclude-module",
    "PySide6.QtMultimediaWidgets",
    "--exclude-module",
    "PySide6.QtNfc",
    "--exclude-module",
    "PySide6.QtOpenGLWidgets",
    "--exclude-module",
    "PySide6.QtPositioning",
    "--exclude-module",
    "PySide6.QtPrintSupport",
    "--exclude-module",
    "PySide6.QtQml",
    "--exclude-module",
    "PySide6.QtQuick",
    "--exclude-module",
    "PySide6.QtQuickControls2",
    "--exclude-module",
    "PySide6.QtQuickWidgets",
    "--exclude-module",
    "PySide6.QtRemoteObjects",
    "--exclude-module",
    "PySide6.QtSensors",
    "--exclude-module",
    "PySide6.QtSerialPort",
    "--exclude-module",
    "PySide6.QtSpatialAudio",
    "--exclude-module",
    "PySide6.QtSql",
    "--exclude-module",
    "PySide6.QtStateMachine",
    "--exclude-module",
    "PySide6.QtTest",
    "--exclude-module",
    "PySide6.QtTextToSpeech",
    "--exclude-module",
    "PySide6.QtUiTools",
    "src/floating_todo/__main__.py"
)

New-Item -ItemType Directory -Force -Path "dist/data" | Out-Null
Write-Host "Build complete: dist/Todo list.exe"
