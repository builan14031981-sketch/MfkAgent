
# 查看chat_id=260的状态，然后发送消息
Write-Output '=== Chat 260 status ==='
try {
    $chat = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/chat/260' -Method Get -TimeoutSec 3
    Write-Output "Chat exists: $($chat.title), mode=$($chat.mode)"
} catch {
    Write-Output "Chat check: $($_.Exception.Message)"
}

Write-Output ''
Write-Output '=== Sending message to chat 260 (will trigger tool approval) ==='
$body = @{
    content = '请帮我执行以下操作：首先创建一个测试文件 E:\智慧项目\Mfkagent\_notify_test_del.txt，写入内容"test"，然后使用 run_command 工具执行 del 命令删除该文件。这两个步骤都必须使用工具实际执行，不是写代码示例。'
    mode = 'build'
} | ConvertTo-Json -Depth 3

try {
    $result = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/chat/260/send' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 60
    Write-Output "Send result:"
    $result | ConvertTo-Json -Depth 5
} catch {
    Write-Output "Send failed: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $resp = $reader.ReadToEnd()
            Write-Output "Response body: $resp"
        } catch {}
    }
}
