
# 获取聊天列表
try {
    $chats = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/chat' -Method Get -ContentType 'application/json' -TimeoutSec 3
    Write-Output '=== Chat List (first 3) ==='
    $chats | Select-Object -First 3 | ConvertTo-Json -Depth 5
} catch {
    Write-Output "Failed to get chats: $($_.Exception.Message)"
}

Write-Output ''
Write-Output '=== Testing command-risk preview to find require_approval command ==='
# 尝试发送一个写操作命令来测试需要审批的风险级别
$body1 = @{ command = 'rm -rf /test'; mode = 'build' } | ConvertTo-Json
try {
    $risk = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/security/command-risk' -Method Post -Body $body1 -ContentType 'application/json' -TimeoutSec 3
    Write-Output 'Risk for rm command:'
    $risk | ConvertTo-Json
} catch {
    Write-Output "Risk check failed: $($_.Exception.Message)"
}

Write-Output ''
# 再试另一个写命令
$body2 = @{ command = 'del important_file.txt'; mode = 'build'; engine = 'run_command' } | ConvertTo-Json
try {
    $risk2 = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/security/command-risk' -Method Post -Body $body2 -ContentType 'application/json' -TimeoutSec 3
    Write-Output 'Risk2:'
    $risk2 | ConvertTo-Json
} catch {
    Write-Output "Risk2 check failed: $($_.Exception.Message)"
}
