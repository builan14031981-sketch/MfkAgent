# ============================================================
# Windows 原生 Toast 最小测试（不依赖 Electron）
# 运行： powershell -NoProfile -ExecutionPolicy Bypass -File electron/test-toast-native.ps1
# 判定：
#   - 弹出 toast → 系统层正常，问题在 Electron 侧
#   - 不弹 → 系统设置/专注助手拦截（Win10 需注册表项）
# ============================================================

$ErrorActionPreference = "Stop"

# 第一步：确保 AUMID 快捷方式存在（复用补建脚本）
$script = Join-Path $PSScriptRoot "dev-notification-shortcut.ps1"
$electronExe = "E:\智慧项目\Mfkagent\frontend\node_modules\electron\dist\electron.exe"
& $script -TargetExe $electronExe | Out-Null

# 第二步：用 Windows Runtime 直接发一条原生 toast（AUMID 对齐）
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
  [Windows.UI.Notifications.ToastTemplateType]::ToastText02
)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($template.CreateTextNode("MfkAgent 原生 Toast 测试")) | Out-Null
$textNodes.Item(1).AppendChild($template.CreateTextNode("如果看到这条，系统通知链路正常")) | Out-Null

$toast = New-Object Windows.UI.Notifications.ToastNotification $template
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("com.mfkagent.app")
$notifier.Show($toast)

Write-Output "NATIVE_TOAST_SHOWN"
