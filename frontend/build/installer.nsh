!macro customInit
  ; 安装开始前，强力杀掉运行中的旧版进程，防止覆盖安装时文件被占用导致失败
  nsExec::Exec "taskkill /F /IM MfkAgent.exe"
  nsExec::Exec "taskkill /F /IM backend.exe"
!macroend

!macro customUnInstall
  ; 卸载前清理进程
  nsExec::Exec "taskkill /F /IM MfkAgent.exe"
  nsExec::Exec "taskkill /F /IM backend.exe"
!macroend
