# Test script for 偏爱 personality testing
$chatId = 141
$baseUrl = "http://127.0.0.1:8001/api/chat/$chatId/send"

function Send-Message {
    param([string]$content)
    $body = @{ content = $content } | ConvertTo-Json -Compress
    try {
        $response = Invoke-RestMethod -Uri $baseUrl -Method POST -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
        return $response
    } catch {
        return @{ error = $_.Exception.Message }
    }
}

$messages = @(
    "今天好累",
    "我感觉人生一直在证明别人错",
    "你是不是不喜欢我了",
    "你烦不烦",
    "哦",
    "我今天被老板骂了，好委屈",
    "其实我也没做错什么，就是他不讲道理",
    "算了不说了",
    "你觉得我是什么样的人",
    "我们认识多久了"
)

foreach ($msg in $messages) {
    Write-Output "`n=== USER: $msg ==="
    $result = Send-Message $msg
    if ($result.content) {
        Write-Output "AI: $($result.content)"
    } else {
        Write-Output "Error: $($result | ConvertTo-Json -Compress)"
    }
    Start-Sleep -Seconds 2
}
