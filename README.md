# bili一键部署

## Termux (Android)
```bash
termux-setup-storage && sleep 3 && pkg update -y && pkg upgrade -y && pkg install python ffmpeg termux-api -y && pkg reinstall python-pip -y && pip install requests pillow mutagen && curl -L -o /storage/emulated/0/Download/termux.txt "https://cnb.cool/mengzhiruling/lanzoul/-/releases/download/lanzoul/termux.txt" && cp /storage/emulated/0/Download/termux.txt ~/bili.py && chmod +x ~/bili.py && echo "alias run='python ~/bili.py'" >> ~/.bashrc && source ~/.bashrc && python ~/bili.py
```

## Windows PowerShell (管理员)
```powershell
# ========== bili一键部署 ==========
# 使用方法：右键开始菜单 → Windows PowerShell (管理员) → 粘贴回车

chcp 65001 >$null 2>&1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   bili一键部署" -ForegroundColor Cyan
Write-Host "   支持 MP3 封面嵌入 + 环境检测" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$PYTHON_SCRIPT_URL = "https://cnb.cool/mengzhiruling/lanzoul/-/releases/download/lanzoul/CMD.txt"
$FFMPEG_URL = "https://cnb.cool/mengzhiruling/lanzoul/-/releases/download/lanzoul/ffmpeg-8.1-full_build.zip"
$DOWNLOAD_DIR = "D:\termux"
$SCRIPT_PATH = "$DOWNLOAD_DIR\bili.py"

Write-Host ""
Write-Host "[1/7] 设置执行策略..." -ForegroundColor Yellow
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

Write-Host ""
Write-Host "[2/7] 创建下载目录..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $DOWNLOAD_DIR | Out-Null
Write-Host "      目录: $DOWNLOAD_DIR" -ForegroundColor Green

Write-Host ""
Write-Host "[3/7] 检查并安装 Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "      Python 已安装: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "      正在安装 Python 3.12..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements
    Write-Host "      Python 安装完成" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4/7] 安装 Python 依赖包..." -ForegroundColor Yellow
python -m pip install --upgrade pip -q
Write-Host "      - 安装 requests..." -ForegroundColor Cyan
pip install requests -q
Write-Host "      - 安装 Pillow (图片处理)..." -ForegroundColor Cyan
pip install pillow -q
Write-Host "      - 安装 mutagen (MP3封面嵌入)..." -ForegroundColor Cyan
pip install mutagen -q
Write-Host "      所有 Python 依赖已安装" -ForegroundColor Green

Write-Host ""
Write-Host "[5/7] 检查并安装 ffmpeg..." -ForegroundColor Yellow
try {
    ffmpeg -version 2>&1 | Out-Null
    Write-Host "      ffmpeg 已安装" -ForegroundColor Green
} catch {
    Write-Host "      正在下载 ffmpeg..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $FFMPEG_URL -OutFile "$env:TEMP\ffmpeg.zip" -UseBasicParsing
    Write-Host "      正在解压..." -ForegroundColor Cyan
    Expand-Archive -Path "$env:TEMP\ffmpeg.zip" -DestinationPath "$env:TEMP\ffmpeg" -Force
    $ffmpegExe = Get-ChildItem -Path "$env:TEMP\ffmpeg" -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    Copy-Item "$($ffmpegExe.DirectoryName)\ffmpeg.exe" "C:\Windows\System32\" -Force
    Copy-Item "$($ffmpegExe.DirectoryName)\ffplay.exe" "C:\Windows\System32\" -Force -ErrorAction SilentlyContinue
    Copy-Item "$($ffmpegExe.DirectoryName)\ffprobe.exe" "C:\Windows\System32\" -Force -ErrorAction SilentlyContinue
    Remove-Item "$env:TEMP\ffmpeg.zip" -Force
    Remove-Item "$env:TEMP\ffmpeg" -Recurse -Force
    Write-Host "      ffmpeg 安装完成" -ForegroundColor Green
}

Write-Host ""
Write-Host "[6/7] 下载主程序脚本..." -ForegroundColor Yellow
try {
    $scriptContent = Invoke-WebRequest -Uri $PYTHON_SCRIPT_URL -UseBasicParsing
    $scriptContent.Content | Out-File -FilePath $SCRIPT_PATH -Encoding UTF8
    Write-Host "      脚本已保存到: $SCRIPT_PATH" -ForegroundColor Green
} catch {
    Write-Host "      下载失败，请检查网络连接" -ForegroundColor Red
    pause
    exit
}

Write-Host ""
Write-Host "[7/7] 创建 PowerShell 快捷命令..." -ForegroundColor Yellow
$PROFILE_DIR = "$env:USERPROFILE\Documents\WindowsPowerShell"
New-Item -ItemType Directory -Force -Path $PROFILE_DIR | Out-Null

$profileContent = @"
# bili一键部署快捷命令
function run { 
    python D:\termux\bili.py 
}
function bili { 
    python D:\termux\bili.py 
}
# 自动检测并提示缺失的依赖
function Check-BiliEnv {
    Write-Host "正在检测环境..." -ForegroundColor Cyan
    `$missing = @()
    try { python --version 2>&1 | Out-Null } catch { `$missing += "Python" }
    try { ffmpeg -version 2>&1 | Out-Null } catch { `$missing += "ffmpeg" }
    try { python -c "import requests" 2>&1 | Out-Null } catch { `$missing += "requests" }
    try { python -c "import PIL" 2>&1 | Out-Null } catch { `$missing += "Pillow" }
    try { python -c "import mutagen" 2>&1 | Out-Null } catch { `$missing += "mutagen" }
    if (`$missing.Count -gt 0) {
        Write-Host "缺少组件: `$missing" -ForegroundColor Yellow
        `$choice = Read-Host "是否安装缺失组件? (y/n)"
        if (`$choice -eq 'y') {
            python -m pip install `$missing -q
            Write-Host "安装完成" -ForegroundColor Green
        }
    } else {
        Write-Host "环境检测通过" -ForegroundColor Green
    }
}
"@
$profileContent | Out-File -FilePath "$PROFILE_DIR\Microsoft.PowerShell_profile.ps1" -Encoding UTF8 -Force
Write-Host "      快捷命令已创建: run / bili" -ForegroundColor Green
Write-Host "      环境检测函数已创建: Check-BiliEnv" -ForegroundColor Green

Write-Host ""
Write-Host "创建桌面快捷方式..." -ForegroundColor Yellow
$desktopShortcut = "$env:USERPROFILE\Desktop\B站下载器.bat"
@"
@echo off
chcp 65001 >nul
cd /d D:\termux
python bili.py
pause
"@ | Out-File -FilePath $desktopShortcut -Encoding Default
Write-Host "      桌面快捷方式已创建" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "           部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  已安装组件:" -ForegroundColor Cyan
Write-Host "     Python 3.x" -ForegroundColor White
Write-Host "     requests (网络请求)" -ForegroundColor White
Write-Host "     Pillow (图片裁剪)" -ForegroundColor White
Write-Host "     mutagen (MP3封面)" -ForegroundColor White
Write-Host "     ffmpeg (音视频转换)" -ForegroundColor White
Write-Host ""
Write-Host "  启动方式:" -ForegroundColor Cyan
Write-Host "     1. 输入: run 或 bili" -ForegroundColor White
Write-Host "     2. 双击桌面: B站下载器.bat" -ForegroundColor White
Write-Host "     3. 环境检测: Check-BiliEnv" -ForegroundColor White
Write-Host ""
Write-Host "  重要提示:" -ForegroundColor Yellow
Write-Host "     更新完成后，请执行: . `$PROFILE" -ForegroundColor White
Write-Host "     否则 run 命令无法识别！" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "按任意键启动下载器..." -ForegroundColor Yellow
pause > $null

. $PROFILE
python D:\termux\bili.py
```