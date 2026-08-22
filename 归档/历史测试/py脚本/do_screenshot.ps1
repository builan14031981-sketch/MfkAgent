
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# 截图到用户临时目录
$tmpPath = Join-Path $env:TEMP 'mfkagent_app.png'
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save($tmpPath, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
Write-Output "Screenshot saved: $tmpPath"
Write-Output "File size: $([math]::Round((Get-Item $tmpPath).Length/1KB, 1)) KB"
