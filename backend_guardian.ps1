# MfkAgent Backend 守护脚本 v3
# 改进：用 main.py 自动端口检测 + 日志文件 + 最大重启次数 + 优雅关闭 + 启动前清理旧进程

$ErrorActionPreference = "Continue"

# ── 配置 ──────────────────────────────────────────────
$python = "C:\Users\Asus\AppData\Local\Programs\Python\Python314\python.exe"
$workdir = "E:\智慧项目\Mfkagent\backend"
$logFile = Join-Path $workdir "logs\watchdog.log"
$maxRestarts = 30       # 最大连续重启次数（防止死循环）
$restartDelay = 3       # 重启间隔（秒）

# 确保日志目录存在
$logDir = Split-Path $logFile -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log {
    param([string]$msg, [string]$color = "White")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [watchdog] $msg"
    Write-Host $line -ForegroundColor $color
    try { Add-Content -Path $logFile -Value $line -Encoding UTF8 } catch {}
}

# ── 启动前清理旧后端进程 ──────────────────────────────
function Clear-OldBackends {
    Write-Log "清理旧后端进程..." "Cyan"
    $killed = 0
    # 方法1：通过端口查找（8000-8010 范围内的监听进程）
    for ($port = 8000; $port -le 8010; $port++) {
        $conns = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
        foreach ($conn in $conns) {
            if ($conn -match '(\d+)\s*$') {
                $pid = $matches[1]
                try {
                    $proc = Get-Process -Id $pid -ErrorAction Stop
                    if ($proc.ProcessName -match "python") {
                        Write-Log "  杀掉端口 $port 上的旧进程 PID=$pid" "Yellow"
                        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                        $killed++
                    }
                } catch {}
            }
        }
    }
    # 方法2：通过命令行查找（运行 main.py 的 python 进程，排除守护脚本自己）
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.CommandLine -match "main\.py" -and $_.CommandLine -notmatch "run_backend") {
            try {
                Write-Log "  杀掉残留 main.py 进程 PID=$($_.ProcessId)" "Yellow"
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                $killed++
            } catch {}
        }
    }
    # 清理端口文件
    $portFile = Join-Path $workdir ".mfkagent_port"
    if (Test-Path $portFile) { Remove-Item $portFile -Force; Write-Log "  清理残留端口文件" "Gray" }
    if ($killed -gt 0) {
        Write-Log "已清理 $killed 个旧进程，等待端口释放..." "Cyan"
        Start-Sleep -Seconds 2
    } else {
        Write-Log "无旧进程" "Gray"
    }
}

# ── 优雅关闭处理 ──────────────────────────────────────
$global:shuttingDown = $false
$global:backendProc = $null

function Stop-Backend {
    if ($global:backendProc -and -not $global:backendProc.HasExited) {
        Write-Log "关闭后端进程 PID=$($global:backendProc.Id)..." "Yellow"
        try { $global:backendProc.Kill() } catch {}
        try { $global:backendProc.WaitForExit(5000) } catch {}
        Write-Log "后端已关闭" "Gray"
    }
}

# 注册控制台关闭事件
$null = Register-EngineEvent -SourceIdentifier ConsoleExit -Action {
    if (-not $global:shuttingDown) {
        $global:shuttingDown = $true
        Write-Log "收到关闭信号，正在退出..." "Yellow"
        Stop-Backend
        Write-Log "守护脚本退出" "Gray"
    }
}

# ── 主循环 ────────────────────────────────────────────
Write-Log "========================================" "Green"
Write-Log "MfkAgent Backend 守护脚本 v3 启动" "Green"
Write-Log "工作目录: $workdir" "Gray"
Write-Log "日志文件: $logFile" "Gray"
Write-Log "========================================" "Green"

# 启动前清理
Clear-OldBackends

$restartCount = 0

while (-not $global:shuttingDown) {
    $restartCount++

    if ($restartCount -gt $maxRestarts) {
        Write-Log "已达到最大重启次数 $maxRestarts，停止自动重启（请检查后端是否有启动错误）" "Red"
        break
    }

    Write-Log "启动后端 (第 $restartCount 次)..." "Cyan"

    try {
        # 启动后端进程（不使用易引发 Windows 管道死锁的同步重定向，日志统一由 backend/logs/app.log 负责）
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = $python
        $processInfo.Arguments = "main.py"
        $processInfo.WorkingDirectory = $workdir
        $processInfo.UseShellExecute = $false
        $processInfo.CreateNoWindow = $true

        $proc = [System.Diagnostics.Process]::Start($processInfo)
        $global:backendProc = $proc

        Write-Log "后端已启动 PID=$($proc.Id)" "Green"

        # 循环监听后端进程存活（响应关闭信号，避免阻塞式 WaitForExit 冻结事件循环）
        while (-not $proc.HasExited -and -not $global:shuttingDown) {
            Start-Sleep -Milliseconds 500
        }

        if ($global:shuttingDown) { break }

        $exitCode = $proc.ExitCode
        Write-Log "后端进程退出 (退出码: $exitCode)" "Yellow"

    } catch {
        Write-Log "启动后端失败: $_" "Red"
    }

    if ($global:shuttingDown) { break }

    Write-Log "$restartDelay 秒后自动重启... (连续重启 $restartCount/$maxRestarts)" "Yellow"
    Start-Sleep -Seconds $restartDelay
}

# 清理
Stop-Backend
Write-Log "守护脚本结束" "Gray"
