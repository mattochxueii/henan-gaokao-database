[CmdletBinding()]
param(
    [switch]$OfficialPyPI,
    [string]$Destination
)

$ErrorActionPreference = 'Stop'

function Find-Python {
    $candidates = @(
        @{ Name = 'py'; Arguments = @('-3') },
        @{ Name = 'python'; Arguments = @() },
        @{ Name = 'python3'; Arguments = @() }
    )
    foreach ($candidate in $candidates) {
        $app = Get-Command $candidate.Name -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $app) { continue }
        $arguments = $candidate.Arguments
        $path = & $app.Source @arguments -c "import sys; print(sys.executable); sys.exit(sys.version_info < (3, 11))"
        if ($LASTEXITCODE -eq 0 -and $path) { return $path }
    }
    throw '需要 Python 3.11 或更高版本。请从 https://www.python.org/downloads/windows/ 安装并勾选 Add Python to PATH，然后重新打开 PowerShell。'
}

function Invoke-Python {
    & $script:pythonExe @args
    if ($LASTEXITCODE -ne 0) { throw "Python 命令失败（退出码 $LASTEXITCODE）。" }
}

$pythonExe = Find-Python
$index = if ($OfficialPyPI) { 'https://pypi.org/simple' } else { 'https://pypi.tuna.tsinghua.edu.cn/simple' }
$env:PYTHONUTF8 = '1'
Push-Location -LiteralPath $PSScriptRoot
try {
    Invoke-Python -m pip install --index-url $index -r requirements.txt
    if ($Destination) {
        Invoke-Python scripts/install_skill.py --destination $Destination
    } else {
        Invoke-Python scripts/install_skill.py
    }
    Invoke-Python scripts/gaokao_platform.py exam-policy english 2027
    Write-Host '安装完成。在 AI 助手中打开本仓库，说：请用 gaokao-platform 给我出一套 2027 年河南新高考数学模拟卷。'
} finally {
    Pop-Location
}
