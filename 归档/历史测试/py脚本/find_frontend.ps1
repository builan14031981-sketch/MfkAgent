
# 测试常见前端端口
$ports = @(3000, 3001, 5173, 5174, 8080, 1420)
foreach ($p in $ports) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/" -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200 -and $r.Content -match 'MfkAgent|html') {
            Write-Output "Frontend on port $p : Content length=$($r.Content.Length)"
        }
    } catch {}
}

# 查找监听端口的进程
Write-Output '---Listening TCP ports---'
Get-NetTCPConnection -State Listen | ForEach-Object {
    $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    [PSCustomObject]@{
        Port = $_.LocalPort
        PID = $_.OwningProcess
        ProcessName = if ($proc) { $proc.ProcessName } else { 'unknown' }
    }
} | Where-Object { $_.Port -lt 10000 -and $_.Port -gt 1000 } | Sort-Object Port | Format-Table -AutoSize
