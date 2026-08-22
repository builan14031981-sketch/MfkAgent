# Pianai V17 多人格预设实际对话测试脚本
# 创建多个会话，每个切换不同预设，发送相同测试消息，对比回复

$base = "http://127.0.0.1:8000/api/chat"
$presets = @(
    @{ name = "默认偏爱"; switch = $null; test = "我不太好，很多东西压得我喘不过气，事太多了烦人" },
    @{ name = "傲娇"; switch = "切换傲娇模式"; test = "我不太好，很多东西压得我喘不过气，事太多了烦人" },
    @{ name = "霸总"; switch = "切换霸总模式"; test = "我不太好，很多东西压得我喘不过气，事太多了烦人" },
    @{ name = "暖心姐姐"; switch = "暖心大姐姐"; test = "我不太好，很多东西压得我喘不过气，事太多了烦人" },
    @{ name = "高冷"; switch = "切换高冷模式"; test = "我不太好，很多东西压得我喘不过气，事太多了烦人" }
)

$results = @()

foreach ($p in $presets) {
    Write-Host "`n========== 测试预设：$($p.name) ==========" -ForegroundColor Cyan

    # 1. 创建会话
    $body = @{ agent_id = "pianai"; title = "测试-$($p.name)" } | ConvertTo-Json
    $chat = Invoke-RestMethod -Uri "$base/" -Method Post -Body $body -ContentType "application/json"
    $chatId = $chat.id
    Write-Host "  会话创建: id=$chatId"

    # 2. 如果有切换指令，先发送切换指令
    if ($p.switch) {
        $switchBody = @{ content = $p.switch } | ConvertTo-Json
        $switchResp = Invoke-RestMethod -Uri "$base/$chatId/send" -Method Post -Body $switchBody -ContentType "application/json"
        Write-Host "  切换指令: $($p.switch)"
        Write-Host "  切换回复: $($switchResp.message.content)"
        Start-Sleep -Seconds 1
    }

    # 3. 发送测试消息
    $testBody = @{ content = $p.test } | ConvertTo-Json
    $testResp = Invoke-RestMethod -Uri "$base/$chatId/send" -Method Post -Body $testBody -ContentType "application/json"
    $reply = $testResp.message.content
    Write-Host "  测试消息: $($p.test)"
    Write-Host "  预设回复: $reply"

    $results += @{ preset = $p.name; reply = $reply }
    Start-Sleep -Seconds 1
}

Write-Host "`n`n========== 对比总结 ==========" -ForegroundColor Yellow
foreach ($r in $results) {
    Write-Host "`n【$($r.preset)】" -ForegroundColor Green
    Write-Host $r.reply
}
