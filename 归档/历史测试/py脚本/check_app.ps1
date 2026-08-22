
# 获取Electron/MfkAgent窗口信息
Get-Process | Where-Object { $_.ProcessName -match 'electron|MfkAgent' } | Select-Object Id, ProcessName, MainWindowTitle, StartTime | Format-Table -AutoSize

Write-Output '---SCREENSHOT---'

# 截取整个屏幕
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$path = 'E:智慧项目Mfkagentscreenshot_' + $timestamp + '.png'
$bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output ('Screenshot saved to: ' + $path)
