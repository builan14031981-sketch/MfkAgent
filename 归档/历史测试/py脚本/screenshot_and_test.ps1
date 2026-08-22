
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$path = 'E:\智慧项目\Mfkagent\app_screenshot.png'
$bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output "Screenshot saved: $path (exists: $(Test-Path $path))"

# 同时运行test-toast验证通知链路
Write-Output '---TEST NOTIFICATION---'
Set-Location 'E:智慧项目Mfkagentrontend'
# 检查是否有electron和脚本
$toastPath = 'E:智慧项目Mfkagentrontendelectron	est-toast.js'
Write-Output "test-toast.js exists: $(Test-Path $toastPath)"
# 不直接运行（会退出当前Electron），改为检查快捷方式和通知支持
