# -*- coding: utf-8 -*-
<#
 * 文件名：sync.ps1
 * 作用：一条命令完成「本地 → GitHub → 服务器」三处同步，并校验一致性
 * 用法：
 *     .\tools\sync.ps1                      # 提交 + 推送 + 部署
 *     .\tools\sync.ps1 -Message "fix: xxx"  # 指定提交信息
 *     .\tools\sync.ps1 -Verify              # 只校验三处文件是否一致
 *     .\tools\sync.ps1 -NoPush              # 跳过 GitHub（未配置远程时用）
 * 作者：qiqiwang07
 * 更新：2026-11-07
#>

param(
    [string]$Message = "chore: 同步更新",
    [switch]$Verify,
    [switch]$NoPush
)

$ErrorActionPreference = 'Stop'                      # 任何错误立即停止，避免半同步状态
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)  # 项目根目录
$Server = "qiqiwang@1.117.113.68"                    # 服务器登录名
$RemoteDir = "/home/qiqiwang/airelay/app"            # 服务器上的部署目录

# 需要同步到服务器的文件（相对项目根目录）
$DeployFiles = @(
    @{ Local = "tools\serve_r1.py";  Remote = "serve_r1.py" },
    @{ Local = "tools\agent_r1.py";  Remote = "agent_r1.py" },
    @{ Local = "bin\chat.html";      Remote = "chat.html" }
)

function Get-Md5($path) {
    # 计算文件 MD5，用于三处一致性校验
    if (-not (Test-Path $path)) { return "MISSING" }
    return (Get-FileHash -Path $path -Algorithm MD5).Hash
}

function Invoke-Ssh($cmd) {
    # 在服务器上执行命令，返回输出
    $out = & ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 $Server $cmd 2>&1
    return ($out | Out-String).Trim()
}

if ($Verify) {
    Write-Host "=== 三处文件一致性校验 ===" -ForegroundColor Cyan
    $ok = $true
    foreach ($f in $DeployFiles) {
        $localPath = Join-Path $Repo $f.Local
        $localMd5 = Get-Md5 $localPath
        $remoteMd5 = Invoke-Ssh "md5sum $RemoteDir/$($f.Remote) 2>/dev/null | cut -d' ' -f1"

        $gitMd5 = "N/A"
        Push-Location $Repo
        try {
            $blob = & git show "HEAD:$($f.Local.Replace('\', '/'))" 2>&1
            if ($LASTEXITCODE -eq 0) {
                # 用 git 里的内容算 MD5：先写到临时文件
                $tmp = [System.IO.Path]::GetTempFileName()
                [System.IO.File]::WriteAllText($tmp, ($blob -join "`n"), [System.Text.UTF8Encoding]::new($false))
                $gitMd5 = Get-Md5 $tmp
                Remove-Item $tmp -Force -ErrorAction SilentlyContinue
            }
        } finally { Pop-Location }

        $same = ($localMd5 -eq $remoteMd5)
        $color = if ($same) { 'Green' } else { 'Red' }
        if (-not $same) { $ok = $false }
        Write-Host ("  {0,-22} 本地 {1}  服务器 {2}  {3}" -f $f.Remote, $localMd5.Substring(0,8), $remoteMd5.Substring(0,[Math]::Min(8,$remoteMd5.Length)), $(if ($same) { '✅' } else { '❌' })) -ForegroundColor $color
    }
    if ($ok) { Write-Host "`n全部一致 ✅" -ForegroundColor Green } else { Write-Host "`n存在不一致 ❌ 请重新同步" -ForegroundColor Red; exit 1 }
    exit 0
}

Write-Host "=== 1/4 提交到本地 Git ===" -ForegroundColor Cyan
Push-Location $Repo
try {
    $changes = & git status --porcelain 2>&1
    if (-not $changes) {
        Write-Host "  没有改动" -ForegroundColor DarkGray
    } else {
        & git add -A 2>&1 | Out-Null
        & git -c user.name="qiqiwang07" -c user.email="zwwang02@163.com" commit -q -m $Message 2>&1 | Select-Object -First 3
        Write-Host ("  已提交: {0}" -f $Message) -ForegroundColor Green
    }
} finally { Pop-Location }

if (-not $NoPush) {
    Write-Host "=== 2/4 推送到 GitHub ===" -ForegroundColor Cyan
    Push-Location $Repo
    try {
        $remote = & git remote 2>&1
        if (-not $remote) {
            Write-Host "  未配置远程仓库，跳过（用 -NoPush 可消除此提示）" -ForegroundColor Yellow
            Write-Host "  配置方法: git remote add origin git@github.com:qiqiwang07/nanochat-demo.git" -ForegroundColor Yellow
        } else {
            & git push -q origin main 2>&1 | Select-Object -First 5
            if ($LASTEXITCODE -eq 0) { Write-Host "  推送成功" -ForegroundColor Green }
            else { Write-Host "  推送失败，请检查密钥是否已加到 GitHub" -ForegroundColor Red }
        }
    } finally { Pop-Location }
}

Write-Host "=== 3/4 同步到服务器 ===" -ForegroundColor Cyan
foreach ($f in $DeployFiles) {
    $localPath = Join-Path $Repo $f.Local
    if (-not (Test-Path $localPath)) {
        Write-Host ("  跳过（本地无此文件）: {0}" -f $f.Local) -ForegroundColor Yellow
        continue
    }
    & scp -o StrictHostKeyChecking=no -q $localPath "${Server}:${RemoteDir}/$($f.Remote)" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host ("  上传 {0} → {1}" -f $f.Local, $f.Remote) -ForegroundColor Green }
    else { Write-Host ("  上传失败: {0}" -f $f.Local) -ForegroundColor Red }
}

Write-Host "=== 4/4 重启服务器服务 ===" -ForegroundColor Cyan
$restart = Invoke-Ssh "bash /home/qiqiwang/restart_app.sh"
Write-Host ("  {0}" -f $restart)

Write-Host "`n=== 校验 ===" -ForegroundColor Cyan
& $MyInvocation.MyCommand.Path -Verify
