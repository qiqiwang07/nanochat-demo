# -*- coding: utf-8 -*-
<#
 * 文件名：sync.ps1
 * 作用：一条命令完成「本地 → GitHub → 服务器」三处同步，并校验一致性
 * 用法：
 *     .\tools\sync.ps1                      # 提交 + 推送 + 部署 + 校验
 *     .\tools\sync.ps1 -Message "fix: xxx"  # 指定提交信息
 *     .\tools\sync.ps1 -Verify              # 只校验三处是否一致
 *     .\tools\sync.ps1 -NoPush              # 跳过 GitHub 推送
 * 说明：PowerShell 5.1 会把原生命令的 stderr 当成错误，故用 Continue + 手动判断退出码
 * 作者：qiqiwang07
 * 更新：2026-11-07
#>

param(
    [string]$Message = "chore: 同步更新",
    [switch]$Verify,
    [switch]$NoPush
)

# 用 Continue 而不是 Stop：git/scp/ssh 的进度信息会写到 stderr，
# 在 Stop 模式下会被误判为致命错误导致脚本中断
$ErrorActionPreference = 'Continue'

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)  # 项目根目录
$Server = "qiqiwang@1.117.113.68"                                            # 服务器登录名
$RemoteDir = "/home/qiqiwang/airelay/app"                                    # 服务器部署目录

# 需要同步到服务器的文件清单（本地相对路径 → 服务器文件名）
$DeployFiles = @(
    @{ Local = "tools\serve_r1.py"; Remote = "serve_r1.py" },
    @{ Local = "tools\agent_r1.py"; Remote = "agent_r1.py" },
    @{ Local = "bin\chat.html";      Remote = "chat.html" }
)


function Get-Md5($path) {
    # 计算文件 MD5，用于三处一致性校验
    if (-not (Test-Path $path)) { return "MISSING" }
    return (Get-FileHash -Path $path -Algorithm MD5).Hash
}


function Invoke-Ssh($cmd) {
    # 在服务器执行命令，返回合并后的输出文本
    $out = & ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 $Server $cmd 2>&1
    return ($out | Out-String).Trim()
}


function Invoke-Git($argList) {
    # 包装 git 调用：统一吞掉 stderr 的进度信息，只返回 stdout 和退出码
    $out = & git @argList 2>&1 | Out-String
    return @{ Out = $out; Code = $LASTEXITCODE }
}


# ---------------------------------------------------------------- 校验模式
if ($Verify) {
    Write-Host "=== 三处文件一致性校验 ===" -ForegroundColor Cyan
    $allOk = $true

    foreach ($f in $DeployFiles) {
        $localPath = Join-Path $Repo $f.Local
        $localMd5 = Get-Md5 $localPath

        # 服务器端 MD5
        $remoteMd5 = (Invoke-Ssh "md5sum $RemoteDir/$($f.Remote) 2>/dev/null | cut -d' ' -f1")
        if (-not $remoteMd5) { $remoteMd5 = "MISSING" }

        # GitHub 端 MD5：从 git 索引取出内容算哈希
        $gitMd5 = "N/A"
        Push-Location $Repo
        $gitShow = & git show "HEAD:$($f.Local.Replace('\','/'))" 2>$null
        $showCode = $LASTEXITCODE
        Pop-Location
        if ($showCode -eq 0 -and $gitShow) {
            # 写入临时文件后计算 MD5，避免编码差异
            $tmp = [System.IO.Path]::GetTempFileName()
            Set-Content -Path $tmp -Value ($gitShow -join "`r`n") -NoNewline -Encoding UTF8
            $gitMd5 = Get-Md5 $tmp
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        }

        $same = ($localMd5 -ieq $remoteMd5 -and $localMd5 -ieq $gitMd5)
        if (-not $same) { $allOk = $false }
        $color = if ($same) { 'Green' } else { 'Red' }
        $mark = if ($same) { 'OK' } else { 'DIFF' }

        Write-Host ("  {0,-16} 本地 {1} | GitHub {2} | 服务器 {3}  {4}" -f `
            $f.Remote,
            $localMd5.Substring(0, [Math]::Min(8, $localMd5.Length)),
            $gitMd5.Substring(0, [Math]::Min(8, $gitMd5.Length)),
            $remoteMd5.Substring(0, [Math]::Min(8, $remoteMd5.Length)),
            $mark) -ForegroundColor $color
    }

    if ($allOk) {
        Write-Host "`n三处完全一致" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "`n存在不一致，请重新运行同步" -ForegroundColor Red
        exit 1
    }
}


# ---------------------------------------------------------------- 提交
Write-Host "=== 1/5 提交到本地 Git ===" -ForegroundColor Cyan
Push-Location $Repo
$status = (Invoke-Git @('status', '--porcelain')).Out
if (-not $status.Trim()) {
    Write-Host "  无改动" -ForegroundColor DarkGray
} else {
    Invoke-Git @('add', '-A') | Out-Null
    $commit = Invoke-Git @('-c', 'user.name=qiqiwang07', '-c', 'user.email=zwwang02@163.com',
                            'commit', '-q', '-m', $Message)
    if ($commit.Code -eq 0) {
        Write-Host ("  已提交: {0}" -f $Message) -ForegroundColor Green
    } else {
        Write-Host ("  提交失败: {0}" -f ($commit.Out.Trim())) -ForegroundColor Red
    }
}
Pop-Location


# ---------------------------------------------------------------- 推送
if (-not $NoPush) {
    Write-Host "=== 2/5 推送到 GitHub ===" -ForegroundColor Cyan
    Push-Location $Repo
    $remotes = (Invoke-Git @('remote')).Out
    if (-not $remotes.Trim()) {
        Write-Host "  未配置远程仓库，跳过" -ForegroundColor Yellow
    } else {
        $push = Invoke-Git @('push', '-q', 'origin', 'main')
        if ($push.Code -eq 0) {
            Write-Host "  推送成功" -ForegroundColor Green
        } else {
            Write-Host "  推送失败：" -ForegroundColor Red
            Write-Host ("    {0}" -f (($push.Out.Trim() -split "`n" | Select-Object -Last 2) -join ' / ')) -ForegroundColor Red
        }
    }
    Pop-Location
} else {
    Write-Host "=== 2/5 跳过 GitHub 推送（-NoPush）===" -ForegroundColor DarkGray
}


# ---------------------------------------------------------------- 部署
Write-Host "=== 3/5 同步到服务器 ===" -ForegroundColor Cyan
foreach ($f in $DeployFiles) {
    $localPath = Join-Path $Repo $f.Local
    if (-not (Test-Path $localPath)) {
        Write-Host ("  跳过（本地缺）: {0}" -f $f.Local) -ForegroundColor Yellow
        continue
    }
    $scp = & scp -o StrictHostKeyChecking=no -q $localPath "${Server}:${RemoteDir}/$($f.Remote)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ("  上传 {0} -> {1}" -f $f.Local, $f.Remote) -ForegroundColor Green
    } else {
        Write-Host ("  上传失败 {0}: {1}" -f $f.Local, $scp) -ForegroundColor Red
    }
}


# ---------------------------------------------------------------- 重启
Write-Host "=== 4/5 重启服务器服务 ===" -ForegroundColor Cyan
$restartOut = Invoke-Ssh "bash /home/qiqiwang/restart_app.sh"
Write-Host ("  {0}" -f $restartOut)


# ---------------------------------------------------------------- 校验
Write-Host "=== 5/5 一致性校验 ===" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File $MyInvocation.MyCommand.Path -Verify
exit $LASTEXITCODE
