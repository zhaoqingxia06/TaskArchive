# Installs a daily local preview-only task. No content is published automatically.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = (Get-Command python -ErrorAction Stop).Source
$vault = 'D:\obidian\Tsing'
if (-not (Test-Path -LiteralPath $vault -PathType Container)) {
  throw "Obsidian 文件夹不存在：$vault"
}
$taskName = 'TaskArchive-Obsidian-Review'
$action = New-ScheduledTaskAction -Execute $python -Argument ('"' + (Join-Path $root 'scripts\sync_obsidian.py') + '" --vault "' + $vault + '"') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At '09:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Daily Obsidian knowledge review preview; never auto-publishes' -Force | Out-Null
Write-Host "已安装每天 09:00 的预览任务：$taskName（不会自动上传）"
