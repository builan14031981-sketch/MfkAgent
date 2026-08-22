
# 查找electron或python监听的端口
Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -in @(9116, 19344, 4536, 12108) -or (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName -match 'python|uvicorn' } | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -AutoSize
Write-Output '---'
# 测试常见端口 8000-8010
$ports = 8000..8010
foreach ($p in $ports) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/health" -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) {
            Write-Output "Port $p is alive: $($r.Content)"
        }
    } catch {}
}
