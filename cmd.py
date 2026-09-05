# -*- coding: utf-8 -*-
"""
多平台视频下载器 for Windows v10.70
支持B站/抖音/快手等平台视频下载、MP3转换、MP3封面嵌入
新增：B站分P支持、全局模式优化、歌单粘贴增强、搜索翻页配置
"""

import requests
import re
import os
import sys
import time
import json
import subprocess
import shutil
import uuid
import platform
import socket
import hashlib
import threading
import io
from typing import List, Dict, Optional
from PIL import Image
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error

VERSION = "10.70"

DOWNLOAD_PATH = "D:/termux/"
API_URL = "https://api.yuafeng.cn/API/spjx/api.php"
STATS_API_URL = "http://mzrl.xn--4gqq11cba.xn--czrs0t/%E7%9B%B4%E9%93%BE%E8%A7%A3%E6%9E%90/zljx.php"
UPDATE_URL = "http://mzrl.xn--4gqq11cba.xn--czrs0t/%E7%9B%B4%E9%93%BE%E8%A7%A3%E6%9E%90/zljx.php?api=get_content&download=1&file=CMD.txt"

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), ".downloader_config.json")

def load_config():
    """加载配置文件"""
    default_config = {
        "shortcut_command": "run",
        "key_next": "d",
        "key_prev": "a"
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
    except:
        pass
    return default_config

def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def get_device_id():
    try:
        hostname = socket.gethostname()
        if sys.platform == 'win32':
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                product_id = winreg.QueryValueEx(key, "ProductId")[0]
                winreg.CloseKey(key)
                device_str = f"{hostname}_{product_id}"
            except:
                device_str = hostname
        else:
            device_str = hostname
        return hashlib.md5(device_str.encode()).hexdigest()[:16]
    except:
        return hashlib.md5(platform.node().encode()).hexdigest()[:16]

def get_public_ip():
    try:
        r = requests.get('https://api.ipify.org', timeout=5)
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return 'unknown'

def report_stats(action, data=None):
    def send():
        try:
            payload = {
                "device_id": get_device_id(),
                "action": action,
                "timestamp": int(time.time()),
                "os": platform.system(),
                "os_version": platform.version(),
                "python_version": sys.version[:10],
                "public_ip": get_public_ip(),
                "data": data or {}
            }
            requests.post(STATS_API_URL, json=payload, timeout=5)
        except:
            pass
    threading.Thread(target=send, daemon=True).start()

if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

def p(text, color='white'):
    colors = {'r': '\033[91m', 'g': '\033[92m', 'y': '\033[93m', 'c': '\033[96m', 'm': '\033[95m', 'w': '\033[0m'}
    print(f"{colors.get(color, colors['w'])}{text}{colors['w']}")

def check_dependencies():
    """检测并提示安装缺失的依赖"""
    print("\n" + "=" * 50)
    p("       环境检测", 'c')
    print("=" * 50)
    
    missing = []
    
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p('[OK] ffmpeg 已安装', 'g')
    except:
        missing.append('ffmpeg')
        p('[!] ffmpeg 未安装', 'y')
    
    try:
        import requests
        p('[OK] requests 已安装', 'g')
    except:
        missing.append('requests')
        p('[!] requests 未安装', 'y')
    
    try:
        import PIL
        p('[OK] Pillow 已安装', 'g')
    except:
        missing.append('pillow')
        p('[!] Pillow 未安装', 'y')
    
    try:
        import mutagen
        p('[OK] mutagen 已安装', 'g')
    except:
        missing.append('mutagen')
        p('[!] mutagen 未安装', 'y')
    
    if missing:
        print("-" * 50)
        p(f'缺少组件: {", ".join(missing)}', 'y')
        print("[提示] 直接回车 = 安装")
        choice = input('\n是否自动安装缺失组件? (直接回车=是, 输入0=否): ').strip()
        if choice == '' or choice == '1':
            for dep in missing:
                if dep == 'ffmpeg':
                    p(f'[安装] 正在安装 ffmpeg...', 'c')
                    os.system('winget install ffmpeg -s winget --silent')
                else:
                    p(f'[安装] 正在安装 {dep}...', 'c')
                    os.system(f'pip install {dep} -q')
            p('安装完成，请重新运行脚本', 'g')
            input('\n按回车键退出...')
            sys.exit(0)
        else:
            p('跳过安装，部分功能可能不可用', 'y')
    else:
        p('所有依赖检测通过', 'g')
    
    print("=" * 50)

def fetch_server_stats():
    try:
        response = requests.get(STATS_API_URL + "?api=stats", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                return {
                    'total_starts': data.get('total_starts', 0),
                    'total_downloads': data.get('total_downloads', 0),
                    'total_converts': data.get('total_converts', 0),
                    'total_devices': data.get('total_devices', 0),
                    'today_starts': data.get('today_starts', 0),
                    'today_downloads': data.get('today_downloads', 0),
                    'today_converts': data.get('today_converts', 0),
                    'today_devices': data.get('today_devices', 0)
                }
    except:
        pass
    return None

def display_stats():
    stats = fetch_server_stats()
    
    print("\n" + "=" * 50)
    print(f"     多平台视频下载器 for Windows v{VERSION}")
    print("=" * 50)
    
    if stats:
        print(f"  全局统计")
        print(f"     总启动:    {stats['total_starts']:4d}次    总下载:    {stats['total_downloads']:4d}次")
        print(f"     总设备:    {stats['total_devices']:4d}台    MP3转换:   {stats['total_converts']:4d}次")
        print(f"  今日统计")
        print(f"     今日启动:  {stats['today_starts']:4d}次    今日下载:  {stats['today_downloads']:4d}次")
        print(f"     今日设备:  {stats['today_devices']:4d}台    MP3转换:  {stats['today_converts']:4d}次")
    else:
        print(f"  无法获取统计数据，请检查网络")
    
    print("=" * 50)
    print(f"     支持B站/抖音/快手 / 全局模式 / 部分选择 / MP3封面 / 酷狗歌单粘贴 / MP3封面批量管理")
    print("=" * 50)

def extract_urls_from_input(user_input):
    urls = []
    text = user_input
    
    text = re.sub(r'(https://)', r' \1', text)
    
    patterns = [
        r'https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9]+',
        r'https?://b23\.tv/[A-Za-z0-9]+',
        r'https?://v\.douyin\.com/[A-Za-z0-9]+/?',
        r'https?://www\.douyin\.com/video/[0-9]+',
        r'https?://v\.kuaishou\.com/[A-Za-z0-9]+/?',
        r'https?://www\.kuaishou\.com/short-video/[A-Za-z0-9]+',
    ]
    
    for pattern in patterns:
        found = re.findall(pattern, text, re.IGNORECASE)
        urls.extend(found)
    
    for bv in re.findall(r'(?:bv|BV)([0-9A-Za-z]{10})', user_input):
        urls.append(f'https://www.bilibili.com/video/BV{bv}/')
    
    seen = set()
    unique_urls = []
    for url in urls:
        normalized = url.rstrip('/').split('?')[0]
        if normalized not in seen:
            seen.add(normalized)
            unique_urls.append(normalized)
    
    return unique_urls

def get_bilibili_cover(bv_id):
    try:
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        resp = requests.get(api_url, headers=headers, timeout=10)
        data = resp.json()
        if data.get('code') == 0:
            pic = data['data'].get('pic', '')
            if pic:
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif not pic.startswith(('http://', 'https://')):
                    pic = 'https://' + pic
                return pic
    except Exception as e:
        p(f'[B站封面获取失败] {e}', 'y')
    return None

def get_bilibili_video_pages(bv_id):
    """获取B站视频的分P信息"""
    try:
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        resp = requests.get(api_url, headers=headers, timeout=10)
        data = resp.json()
        
        if data.get('code') == 0:
            video_data = data.get('data', {})
            pages = video_data.get('pages', [])
            
            if pages and len(pages) > 1:
                page_list = []
                for idx, page in enumerate(pages, 1):
                    page_list.append({
                        'cid': page.get('cid'),
                        'page': page.get('page', idx),
                        'part': page.get('part', f'P{idx}'),
                        'duration': page.get('duration', 0)
                    })
                return page_list
            elif pages:
                return [{
                    'cid': pages[0].get('cid'),
                    'page': 1,
                    'part': video_data.get('title', '视频'),
                    'duration': pages[0].get('duration', 0)
                }]
    except Exception as e:
        p(f'[获取分P信息失败] {e}', 'y')
    return None

def parse_video(url):
    retry = 0
    while True:
        try:
            p(f'[解析] {url}', 'c')
            
            is_bilibili = 'bilibili.com' in url or 'b23.tv' in url
            pages = None
            bv_id = None
            
            if is_bilibili:
                bv_match = re.search(r'BV([0-9A-Za-z]{10})', url, re.IGNORECASE)
                if bv_match:
                    bv_id = f'BV{bv_match.group(1)}'
                    p(f'[B站] 检测到BV号: {bv_id}', 'c')
                    pages = get_bilibili_video_pages(bv_id)
                    if pages and len(pages) > 1:
                        p(f'[B站] 检测到 {len(pages)} 个分P', 'g')
                    elif pages:
                        p(f'[B站] 单个视频', 'c')
                elif 'b23.tv' in url:
                    try:
                        resp = requests.head(url, timeout=10, allow_redirects=True)
                        final_url = resp.url
                        bv_match = re.search(r'BV([0-9A-Za-z]{10})', final_url, re.IGNORECASE)
                        if bv_match:
                            bv_id = f'BV{bv_match.group(1)}'
                            pages = get_bilibili_video_pages(bv_id)
                            if pages and len(pages) > 1:
                                p(f'[B站] 检测到 {len(pages)} 个分P', 'g')
                    except:
                        pass
            
            r = requests.get(API_URL, params={'url': url}, timeout=30)
            try:
                data = r.json()
            except:
                m = re.search(r'\{.*\}', r.text, re.DOTALL)
                data = json.loads(m.group(0)) if m else {}
            
            if data.get('code') in [0, 200]:
                d = data.get('data', {})
                title = d.get('title', 'video')
                vurl = d.get('url', '') or d.get('video', '')
                cover = d.get('cover', '') or d.get('pic', '')
                
                if is_bilibili and (not cover or 'transparent.png' in cover) and bv_id:
                    real_cover = get_bilibili_cover(bv_id)
                    if real_cover:
                        cover = real_cover
                        p(f'[B站] 获取到真实封面', 'g')
                
                if vurl and title:
                    title = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', title)
                    p(f'[成功] {title}', 'g')
                    return title, vurl, cover, pages
            
            retry += 1
            p(f'[重试 {retry}] {data.get("msg", "解析失败")}', 'y')
        except Exception as e:
            retry += 1
            p(f'[重试 {retry}] {e}', 'y')
        time.sleep(2)

def format_time(seconds):
    """格式化时间显示"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}分{secs}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}小时{minutes}分"

def download_file(url, title):
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    name = re.sub(r'[\\/:*?"<>|]', '_', title)
    vpath = os.path.join(DOWNLOAD_PATH, f'{name}.mp4')
    
    c = 1
    while os.path.exists(vpath):
        vpath = os.path.join(DOWNLOAD_PATH, f'{name}_{c}.mp4')
        c += 1
    
    tmp_path = vpath + '.tmp'
    resume_pos = 0
    
    if '.m3u8' in url:
        p(f'[下载] 正在下载...', 'c')
        
        for attempt in range(3):
            try:
                cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-stats',
                       '-i', url, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-y', vpath]
                
                process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
                process.wait()
                
                if process.returncode == 0 and os.path.exists(vpath):
                    size = os.path.getsize(vpath) / 1024 / 1024
                    if size > 0.5:
                        p(f'[完成] {size:.1f}MB', 'g')
                        report_stats("download", {"title": title, "size": round(size, 2)})
                        return vpath
                    else:
                        p(f'[警告] 文件过小({size:.1f}MB)，可能下载失败', 'y')
                        os.remove(vpath)
                        return None
                else:
                    p(f'[重试] ffmpeg返回码:{process.returncode}', 'y')
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        p(f'[错误] ffmpeg下载失败', 'r')
                        return None
            except Exception as e:
                p(f'[异常] 第{attempt+1}次: {e}', 'y')
                if attempt < 2:
                    time.sleep(2)
                else:
                    return None
        return None
    
    if os.path.exists(tmp_path):
        resume_pos = os.path.getsize(tmp_path)
        p(f'[续传] 从 {resume_pos/1024/1024:.1f}MB 继续', 'y')
    
    p(f'[下载] {os.path.basename(vpath)}', 'c')
    
    for attempt in range(5):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            if resume_pos > 0:
                headers['Range'] = f'bytes={resume_pos}-'
            
            r = requests.get(url, stream=True, timeout=(30, 300), headers=headers)
            
            if resume_pos > 0 and r.status_code == 206:
                mode = 'ab'
            else:
                mode = 'wb'
                resume_pos = 0
            
            total = int(r.headers.get('content-length', 0)) + resume_pos
            done = resume_pos
            last_percent = -1
            start_time = time.time()
            last_time = start_time
            last_done = done
            speed = 0
            
            with open(tmp_path, mode) as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if total > 0:
                            percent = done * 100 // total
                            if percent != last_percent:
                                last_percent = percent
                                
                                now = time.time()
                                time_diff = now - last_time
                                if time_diff >= 0.3:
                                    bytes_diff = done - last_done
                                    speed = bytes_diff / time_diff / 1024 / 1024
                                    last_time = now
                                    last_done = done
                                
                                remaining_bytes = total - done
                                if speed > 0:
                                    remaining_seconds = remaining_bytes / speed / 1024 / 1024
                                    eta = format_time(remaining_seconds)
                                else:
                                    eta = "计算中..."
                                
                                bar_length = 30
                                filled = int(bar_length * percent // 100)
                                bar = '█' * filled + '░' * (bar_length - filled)
                                
                                sys.stdout.write(f'\r[{bar}] {percent}% ({done//1024//1024}MB/{total//1024//1024}MB) {speed:.1f}MB/s 剩余{eta}')
                                sys.stdout.flush()
            
            print()
            os.rename(tmp_path, vpath)
            size = os.path.getsize(vpath) / 1024 / 1024
            p(f'[完成] {size:.1f}MB', 'g')
            report_stats("download", {"title": title, "size": round(size, 2)})
            return vpath
            
        except Exception as e:
            p(f'\n[中断] 第{attempt+1}次: {str(e)[:80]}', 'y')
            if attempt < 4:
                if os.path.exists(tmp_path):
                    resume_pos = os.path.getsize(tmp_path)
                wait = (attempt + 1) * 2
                p(f'[等待] {wait}秒后重试...', 'y')
                time.sleep(wait)
            else:
                p('[错误] 下载失败', 'r')
                return None

def convert_to_mp3(mp4_path):
    if not os.path.exists(mp4_path):
        return None
    
    mp3_path = mp4_path.replace('.mp4', '.mp3')
    c = 1
    while os.path.exists(mp3_path):
        mp3_path = mp4_path.replace('.mp4', f'_{c}.mp3')
        c += 1
    
    p(f'[转换] {os.path.basename(mp4_path)} -> MP3', 'c')
    
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', mp4_path, '-vn', '-acodec', 'libmp3lame', '-ab', '192k', '-y', mp3_path],
            capture_output=True, text=True, timeout=600
        )
        
        if result.returncode == 0 and os.path.exists(mp3_path):
            m_size = os.path.getsize(mp3_path) / 1024 / 1024
            p(f'[成功] MP3: {m_size:.1f}MB', 'g')
            report_stats("convert", {"title": os.path.basename(mp4_path).replace('.mp4', '')})
            return mp3_path
        else:
            p(f'[失败] 转换失败', 'r')
            return None
    except FileNotFoundError:
        p('[错误] ffmpeg 未安装，请运行: winget install ffmpeg', 'r')
        return None
    except Exception as e:
        p(f'[错误] {e}', 'r')
        return None

def download_and_crop_cover(cover_url, output_path):
    try:
        if cover_url.startswith('//'):
            cover_url = 'https:' + cover_url
        elif not cover_url.startswith(('http://', 'https://')):
            cover_url = 'https://' + cover_url
        
        resp = requests.get(cover_url, timeout=10)
        if resp.status_code != 200:
            return False
        img = Image.open(io.BytesIO(resp.content))
        w, h = img.size
        size = min(w, h)
        left = (w - size) // 2
        top = (h - size) // 2
        cropped = img.crop((left, top, left + size, top + size))
        cropped.save(output_path, 'JPEG', quality=90)
        return True
    except Exception as e:
        p(f'[封面处理失败] {e}', 'y')
        return False

def extract_cover_from_video(mp4_path, output_path):
    try:
        cmd = ['ffmpeg', '-i', mp4_path, '-vframes', '1', '-an', '-y', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
    except Exception as e:
        p(f'[提取封面失败] {e}', 'y')
    return False

def add_cover_to_mp3(mp3_path, cover_image_path):
    try:
        audio = MP3(mp3_path, ID3=ID3)
    except error:
        audio = MP3(mp3_path)
        audio.add_tags()
    
    with open(cover_image_path, 'rb') as f:
        image_data = f.read()
    
    apic = APIC(
        encoding=3,
        mime='image/jpeg',
        type=3,
        desc='Cover',
        data=image_data
    )
    audio.tags.delall('APIC')
    audio.tags.add(apic)
    audio.save()
    return True

def process_cover_for_mp3(mp3_path, mp4_path, cover_url):
    """处理MP3封面：API封面 → 视频提取第一帧（兜底）"""
    cover_added = False
    cover_tmp = mp3_path.replace('.mp3', '_cover.jpg')
    
    if cover_url and 'transparent.png' not in cover_url:
        p('[封面] 尝试使用API封面...', 'c')
        if download_and_crop_cover(cover_url, cover_tmp):
            p('[封面] API封面下载成功', 'g')
            cover_added = True
        else:
            p('[封面] API封面下载失败', 'y')
    
    if not cover_added:
        p('[封面] 尝试从视频提取封面...', 'c')
        if extract_cover_from_video(mp4_path, cover_tmp):
            try:
                img = Image.open(cover_tmp)
                w, h = img.size
                size = min(w, h)
                left = (w - size) // 2
                top = (h - size) // 2
                cropped = img.crop((left, top, left + size, top + size))
                cropped.save(cover_tmp, 'JPEG', quality=90)
                p('[封面] 从视频提取并裁剪成功', 'g')
                cover_added = True
            except Exception as e:
                p(f'[封面] 裁剪失败: {e}', 'y')
                cover_added = True
        else:
            p('[封面] 无法从视频提取封面', 'y')
    
    if cover_added:
        p('[封面] 嵌入 MP3...', 'c')
        if add_cover_to_mp3(mp3_path, cover_tmp):
            p('[封面] 封面已嵌入', 'g')
        else:
            p('[封面] 嵌入失败', 'y')
        try:
            os.remove(cover_tmp)
        except:
            pass
    else:
        p('[封面] 无封面，MP3无封面', 'y')

def show_page_selection_menu(pages_info, title):
    """显示分P选择菜单"""
    print("\n" + "=" * 60)
    p(f"       【分P选择】{title}", 'c')
    print("=" * 60)
    print("说明：")
    print("  - 输入数字选择单个分P（如：1）")
    print("  - 输入多个数字用逗号分隔（如：1,3,5）")
    print("  - 输入范围（如：1-5）")
    print("  - 输入 'all' 选择所有分P")
    print("  - 输入 0 跳过此视频")
    print("=" * 60)
    
    for i, page in enumerate(pages_info, 1):
        duration_str = format_time(page['duration']) if page['duration'] else '未知时长'
        print(f"  [{i}] P{page['page']}: {page['part'][:50]} ({duration_str})")
    
    print("=" * 60)
    
    while True:
        choice = input("\n请选择要下载的分P: ").strip().lower()
        
        if choice == '0':
            return None
        elif choice == 'all':
            return list(range(1, len(pages_info) + 1))
        elif ',' in choice or '-' in choice:
            selected = parse_selection_input(choice, len(pages_info))
            if selected:
                return [i + 1 for i in selected]
            else:
                p("无效的选择格式，请重新输入", 'y')
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(pages_info):
                return [idx]
            else:
                p(f"请输入 1-{len(pages_info)} 之间的数字", 'y')
        else:
            p("无效输入，请重新输入", 'y')

def show_page_mode_menu():
    """显示分P处理模式菜单"""
    print("\n" + "=" * 50)
    p("       分P处理模式", 'c')
    print("=" * 50)
    print("  [3] 都要（MP4+MP3，MP3带封面）")
    print("  [2] 仅MP3（下载音频，自动添加封面）")
    print("  [1] 仅MP4（只下载视频）")
    print("=" * 50)
    
    while True:
        choice = input("\n请选择处理模式 [1-3]: ").strip()
        if choice in ['1', '2', '3']:
            return int(choice)
        p('无效选项，请重新输入', 'y')

def download_single_page(page_url, title, mode, cover_url=None):
    """下载单个分P"""
    retry = 0
    while retry < 3:
        try:
            r = requests.get(API_URL, params={'url': page_url}, timeout=30)
            data = r.json()
            if data.get('code') in [0, 200]:
                video_url = data.get('data', {}).get('url', '') or data.get('data', {}).get('video', '')
                if video_url:
                    mp4_path = download_file(video_url, title)
                    if mp4_path:
                        if mode in (2, 3):
                            mp3_path = convert_to_mp3(mp4_path)
                            if mp3_path:
                                process_cover_for_mp3(mp3_path, mp4_path, cover_url)
                            if mode == 2:
                                os.remove(mp4_path)
                                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                            elif mode == 3:
                                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                        else:
                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                        return True
            retry += 1
            time.sleep(2)
        except Exception as e:
            retry += 1
            time.sleep(2)
    return False

def process_single_video(url, mode):
    """处理单个视频（支持B站分P）"""
    p(f'\n{"="*50}', 'm')
    
    is_bilibili = 'bilibili.com' in url or 'b23.tv' in url
    pages = None
    bv_id = None
    
    if is_bilibili:
        bv_match = re.search(r'BV([0-9A-Za-z]{10})', url, re.IGNORECASE)
        if bv_match:
            bv_id = f'BV{bv_match.group(1)}'
            p(f'[B站] 检查分P信息...', 'c')
            pages = get_bilibili_video_pages(bv_id)
    
    if pages and len(pages) > 1:
        title = pages[0].get('part', '视频')
        p(f'[B站] 检测到 {len(pages)} 个分P', 'g')
        
        selected_pages = show_page_selection_menu(pages, f"视频 (共{len(pages)}P)")
        
        if selected_pages is None:
            p('[跳过] 用户选择跳过此视频', 'y')
            return False
        
        page_mode = show_page_mode_menu()
        
        p(f'\n[开始] 准备下载 {len(selected_pages)} 个分P...', 'c')
        
        success_count = 0
        
        for page_num in selected_pages:
            page = pages[page_num - 1]
            page_url = f"https://www.bilibili.com/video/{bv_id}?p={page['page']}"
            page_title = f"{page['part'][:50]}"
            p(f'\n>>> 下载第 {page_num} 个分P: {page["part"]}', 'c')
            
            retry = 0
            while retry < 3:
                try:
                    r = requests.get(API_URL, params={'url': page_url}, timeout=30)
                    data = r.json()
                    if data.get('code') in [0, 200]:
                        video_url = data.get('data', {}).get('url', '') or data.get('data', {}).get('video', '')
                        if video_url:
                            mp4_path = download_file(video_url, page_title)
                            if mp4_path:
                                if page_mode in (2, 3):
                                    mp3_path = convert_to_mp3(mp4_path)
                                    if mp3_path:
                                        cover_url = None
                                        if bv_id:
                                            cover_url = get_bilibili_cover(bv_id)
                                        process_cover_for_mp3(mp3_path, mp4_path, cover_url)
                                    if page_mode == 2:
                                        os.remove(mp4_path)
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                    elif page_mode == 3:
                                        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                else:
                                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                success_count += 1
                                break
                    retry += 1
                    time.sleep(2)
                except Exception as e:
                    retry += 1
                    time.sleep(2)
            else:
                p(f'[失败] 第 {page_num} 个分P下载失败', 'r')
        
        p(f'\n[完成] 成功下载 {success_count}/{len(selected_pages)} 个分P', 'g')
        return success_count > 0
    
    result = parse_video(url)
    if len(result) == 4:
        title, video_url, cover_url, pages = result
    else:
        title, video_url, cover_url = result
        pages = None
    
    if not video_url:
        p('[错误] 解析失败', 'r')
        return False
    
    mp4_path = download_file(video_url, title)
    if not mp4_path:
        p('[错误] 下载失败', 'r')
        return False
    
    if mode in (2, 3):
        mp3_path = convert_to_mp3(mp4_path)
        if mp3_path:
            process_cover_for_mp3(mp3_path, mp4_path, cover_url)
            
            if mode == 2:
                os.remove(mp4_path)
                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
            elif mode == 3:
                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
            return True
        else:
            p(f'[保留] 转换失败，保留MP4', 'y')
            if mode == 2:
                return False
            else:
                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                return True
    else:
        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
        return True

def parse_selection_input(selection_str, total_count):
    selected = set()
    parts = selection_str.replace(' ', '').split(',')
    for part in parts:
        if '-' in part:
            try:
                start, end = part.split('-')
                for i in range(int(start)-1, int(end)):
                    if 0 <= i < total_count:
                        selected.add(i)
            except:
                continue
        else:
            try:
                idx = int(part) - 1
                if 0 <= idx < total_count:
                    selected.add(idx)
            except:
                continue
    return sorted(list(selected))

def process_multiple_videos(urls, global_mode):
    """处理多个视频"""
    videos_info = []
    
    for url in urls:
        p(f'\n[预解析] {url}', 'c')
        result = parse_video(url)
        if len(result) == 4:
            title, video_url, cover_url, pages = result
        else:
            title, video_url, cover_url = result
            pages = None
        
        if video_url:
            videos_info.append({
                'url': url,
                'title': title,
                'video_url': video_url,
                'cover_url': cover_url,
                'pages': pages
            })
        else:
            p(f'[警告] 解析失败: {url}', 'r')
    
    if not videos_info:
        p('[错误] 没有可下载的视频', 'r')
        return 0, 0
    
    success = 0
    fail = 0
    
    for idx, info in enumerate(videos_info):
        p(f'\n{"="*50}', 'm')
        p(f'处理第 {idx+1}/{len(videos_info)} 个视频', 'c')
        
        if info['pages'] and len(info['pages']) > 1:
            if process_single_video(info['url'], global_mode):
                success += 1
            else:
                fail += 1
        else:
            mp4_path = download_file(info['video_url'], info['title'])
            if mp4_path:
                if global_mode in (2, 3):
                    mp3_path = convert_to_mp3(mp4_path)
                    if mp3_path:
                        process_cover_for_mp3(mp3_path, mp4_path, info['cover_url'])
                        if global_mode == 2:
                            os.remove(mp4_path)
                            p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                        elif global_mode == 3:
                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                            p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                    else:
                        if global_mode == 2:
                            fail += 1
                            continue
                        else:
                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                else:
                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                success += 1
            else:
                fail += 1
    
    return success, fail

def show_global_menu():
    p('\n' + '=' * 50, 'm')
    p('       请选择处理模式', 'm')
    p('=' * 50, 'm')
    p('  [3] 全部都要（MP4+MP3，MP3带封面）', 'c')
    p('  [2] 全部转 MP3（删除MP4，自动添加封面）', 'c')
    p('  [1] 全部转 MP4（只下载视频）', 'c')
    p('  [4] 选择部分（手动选择每个视频的处理方式）', 'c')
    p('=' * 50, 'm')
    
    while True:
        choice = input('\n请输入选项 [1/2/3/4]: ').strip()
        if choice in ['1', '2', '3', '4']:
            return int(choice)
        p('无效选项，请重新输入', 'y')

def show_video_mode_menu():
    print('=' * 50)
    print('  [1] 仅MP4（下载视频）')
    print('  [2] 仅MP3（下载音频，自动添加封面）')
    print('  [3] 都要（MP4+MP3，MP3带封面）')
    print('  [q] 返回主菜单')
    print('=' * 50)
    
    while True:
        choice = input('\n请选择处理模式 [1/2/3/q]: ').strip().lower()
        if choice == 'q':
            return None
        elif choice in ['1', '2', '3']:
            return int(choice)
        else:
            p('无效选项，请输入 1、2、3 或 q(返回)', 'y')

def show_uninstall_menu():
    print('\n' + '=' * 50)
    p('       卸载选项', 'c')
    print('=' * 50)
    print('  [1] 仅删除下载的视频文件')
    print('  [2] 卸载下载器（删除脚本，保留视频）')
    print('  [3] 完全清理（删除所有，包括ffmpeg）')
    print('  [4] 返回主菜单')
    print('=' * 50)

def uninstall_videos():
    print(f'\n正在删除视频文件: {DOWNLOAD_PATH}')
    try:
        deleted = 0
        for file in os.listdir(DOWNLOAD_PATH):
            if file.endswith(('.mp4', '.mp3', '.tmp')):
                os.remove(os.path.join(DOWNLOAD_PATH, file))
                deleted += 1
        print(f'[完成] 已删除 {deleted} 个视频/音频文件')
    except Exception as e:
        print(f'[错误] {e}')
    input('\n按回车键返回...')

def uninstall_tool_only():
    print('\n[卸载] 正在移除下载器...')
    
    try:
        os.remove(sys.argv[0])
        print('  已删除脚本文件')
    except Exception as e:
        print(f'  删除脚本失败: {e}')
    
    try:
        config_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), ".downloader_config.json")
        if os.path.exists(config_file):
            os.remove(config_file)
            print('  已删除配置文件')
    except:
        pass
    
    print('\n[完成] 下载器已卸载！')
    input('\n按回车键退出...')
    sys.exit(0)

def uninstall_everything():
    print('\n[警告] 这将删除 ffmpeg 及所有相关文件！')
    print("[提示] 直接回车 = 取消")
    confirm = input('确认完全卸载？(输入 yes 确认, 直接回车取消): ').strip().lower()
    if confirm != 'yes':
        print('[取消] 卸载已取消')
        input('\n按回车键返回...')
        return
    
    try:
        os.remove(sys.argv[0])
        print('  已删除脚本文件')
    except:
        pass
    
    try:
        shutil.rmtree(DOWNLOAD_PATH)
        print('  已删除 D:\\termux 目录')
    except Exception as e:
        print(f'  删除目录失败: {e}')
    
    ffmpeg_paths = [
        'C:\\Windows\\System32\\ffmpeg.exe',
        'C:\\Windows\\System32\\ffplay.exe', 
        'C:\\Windows\\System32\\ffprobe.exe'
    ]
    for path in ffmpeg_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f'  已删除 {os.path.basename(path)}')
        except:
            print(f'  无法删除 {os.path.basename(path)}，需要管理员权限')
    
    print('\n[完成] 完全清理完成！')
    input('\n按回车键退出...')
    sys.exit(0)

def check_for_updates():
    print('\n' + '=' * 50)
    p('       检查更新', 'c')
    print('=' * 50)
    
    try:
        p('[检查] 正在获取最新版本...', 'y')
        response = requests.get(UPDATE_URL, timeout=10)
        
        if response.status_code == 200:
            new_content = response.text
            
            current_file = sys.argv[0]
            with open(current_file, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            new_version_match = re.search(r'VERSION\s*=\s*["\']([0-9.]+)["\']', new_content)
            current_version_match = re.search(r'VERSION\s*=\s*["\']([0-9.]+)["\']', current_content)
            
            new_version = new_version_match.group(1) if new_version_match else '0'
            current_version = current_version_match.group(1) if current_version_match else VERSION
            
            if new_version != current_version:
                p(f'[发现] 检测到新版本！', 'g')
                print(f'  当前版本: v{current_version}')
                print(f'  最新版本: v{new_version}')
                
                print("[提示] 直接回车 = 更新")
                choice = input('\n是否立即更新？(直接回车=是, 输入0=否): ').strip()
                if choice == '' or choice == '1':
                    backup_path = current_file + '.bak'
                    with open(current_file, 'r', encoding='utf-8') as f:
                        with open(backup_path, 'w', encoding='utf-8') as bf:
                            bf.write(f.read())
                    
                    with open(current_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    p('  更新完成！', 'g')
                    print('\n' + '=' * 50)
                    p('       请手动重新启动', 'c')
                    print('=' * 50)
                    input('\n按回车键退出...')
                    sys.exit(0)
                else:
                    p('[跳过] 本次不更新', 'y')
            else:
                p('[完成] 已是最新版本', 'g')
        else:
            p(f'[错误] 获取更新失败', 'r')
    except Exception as e:
        p(f'[错误] {e}', 'r')
    input('\n按回车键返回...')

def check_for_updates_auto():
    try:
        response = requests.get(UPDATE_URL, timeout=10)
        
        if response.status_code == 200:
            new_content = response.text
            
            current_file = sys.argv[0]
            with open(current_file, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            new_version_match = re.search(r'VERSION\s*=\s*["\']([0-9.]+)["\']', new_content)
            current_version_match = re.search(r'VERSION\s*=\s*["\']([0-9.]+)["\']', current_content)
            
            new_version = new_version_match.group(1) if new_version_match else '0'
            current_version = current_version_match.group(1) if current_version_match else VERSION
            
            if new_version != current_version:
                p(f'\n{"="*50}', 'y')
                p(f'发现新版本 v{new_version} (当前 v{current_version})', 'y')
                print('=' * 50)
                print("[提示] 直接回车 = 更新")
                choice = input('是否立即更新？(直接回车=是, 输入0=否): ').strip()
                if choice == '' or choice == '1':
                    backup_path = current_file + '.bak'
                    with open(current_file, 'r', encoding='utf-8') as f:
                        with open(backup_path, 'w', encoding='utf-8') as bf:
                            bf.write(f.read())
                    
                    with open(current_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    p('更新完成！', 'g')
                    print('\n' + '=' * 50)
                    p('   请手动重新启动脚本', 'c')
                    print('=' * 50)
                    input('\n按回车键退出...')
                    sys.exit(0)
                else:
                    p('[跳过] 本次不更新，继续使用当前版本', 'y')
                    print('=' * 50)
    except Exception as e:
        pass

# ==================== 歌名提取函数 ====================

def get_multiline_input_ctrl_d(prompt):
    """使用 Ctrl+Z 结束的多行输入（Windows）"""
    print(prompt)
    print("提示：粘贴完成后按 Ctrl+Z 再按回车结束输入")
    lines = []
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            lines.append(line.rstrip('\n'))
    except KeyboardInterrupt:
        pass
    return '\n'.join(lines)

def extract_song_names_from_text(raw_text):
    """
    从用户复制的酷狗歌单文本中提取歌曲名称
    基于位置特征：找到包含"首歌曲"的行，之后的内容就是歌名
    """
    print("\n[解析] 正在从文本中提取歌名...")
    
    lines = raw_text.strip().split('\n')
    
    playlist_info = {
        'title': '',
        'author': '',
        'description': '',
        'song_count': 0
    }
    
    separator_index = -1
    for i, line in enumerate(lines):
        line = line.strip()
        if line == '分隔线':
            separator_index = i
            break
    
    if separator_index > 0:
        for i in range(separator_index):
            line = lines[i].strip()
            if not line:
                continue
            if line in ['全曲库免费听', '每天可领VIP，新人再领6个月VIP', '封面', '头像', '￼', '□', '■', '●', '◆', '▶']:
                continue
            if '|' in line and not playlist_info['title']:
                playlist_info['title'] = line
            elif not playlist_info['author'] and len(line) <= 20 and not any(x in line for x in ['|', '，', '、', '。']):
                if line not in ['分割线', '播放按钮', '歌曲封面', '收藏歌单']:
                    playlist_info['author'] = line
            elif not playlist_info['description'] and len(line) > 20:
                playlist_info['description'] = line
    
    if playlist_info['title']:
        print(f"[歌单标题] {playlist_info['title']}")
    if playlist_info['author']:
        print(f"[歌单作者] {playlist_info['author']}")
    if playlist_info['description']:
        print(f"[歌单简介] {playlist_info['description']}")
    
    total_count = 0
    for line in lines:
        line = line.strip()
        if '播放按钮' in line and '首歌曲' in line:
            match = re.search(r'(\d+)首歌曲', line)
            if match:
                total_count = int(match.group(1))
                print(f"[信息] 检测到歌单共 {total_count} 首歌曲")
                break
    
    songs = []
    start_index = separator_index + 1 if separator_index != -1 else 0
    
    i = start_index
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        
        if not line or line in ['￼', '□', '■', '●', '◆', '▶']:
            continue
        
        if '收藏歌单' in line:
            break
        
        if line == '歌曲封面':
            if i < len(lines):
                song_name_line = lines[i].strip()
                i += 1
                
                while i < len(lines) and (not song_name_line or song_name_line in ['￼', '□', '■', '●', '◆', '▶']):
                    song_name_line = lines[i].strip()
                    i += 1
                
                if song_name_line and song_name_line not in ['播放按钮', '歌曲封面', '收藏歌单']:
                    song_name = song_name_line
                    artist = ""
                    if i < len(lines):
                        artist_line = lines[i].strip()
                        while i < len(lines) and artist_line in ['￼', '□', '■', '●', '◆', '▶']:
                            i += 1
                            artist_line = lines[i].strip() if i < len(lines) else ""
                        
                        if artist_line and artist_line not in ['播放按钮', '歌曲封面']:
                            artist = artist_line
                            i += 1
                    
                    if len(song_name) < 3 and artist:
                        search_term = f"{song_name} {artist}"
                    elif artist:
                        search_term = song_name
                    else:
                        search_term = song_name
                    
                    songs.append({
                        'name': song_name,
                        'artist': artist,
                        'search_term': search_term
                    })
        
        elif line == '播放按钮':
            continue
    
    if not songs:
        print("[提示] 未找到标准格式，尝试备用方法...")
        i = start_index
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            
            if not line or line in ['￼', '□', '■', '●', '◆', '▶']:
                continue
            
            if '收藏歌单' in line:
                break
            
            if line not in ['播放按钮', '歌曲封面']:
                song_name = line
                artist = ""
                
                if i < len(lines):
                    next_line = lines[i].strip()
                    if next_line and next_line not in ['播放按钮', '歌曲封面', '￼', '□', '■', '●', '◆', '▶']:
                        if re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ffa-zA-Z]', next_line):
                            artist = next_line
                            i += 1
                
                if len(song_name) < 3 and artist:
                    search_term = f"{song_name} {artist}"
                elif artist:
                    search_term = song_name
                else:
                    search_term = song_name
                
                songs.append({
                    'name': song_name,
                    'artist': artist,
                    'search_term': search_term
                })
    
    seen = set()
    unique_songs = []
    for s in songs:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique_songs.append(s)
    
    if total_count > 0 and len(unique_songs) != total_count:
        print(f"\n[警告] 提取数量({len(unique_songs)})与预期({total_count})不符")
        print("可能原因：网页未完全加载，请尝试以下方法：")
        print("  1. 在浏览器中打开歌单网页")
        print("  2. 向下滚动到页面底部，让所有歌曲都加载出来")
        print("  3. 再次全选复制所有内容")
        print("  4. 重新粘贴")
        
        print("[提示] 直接回车 = 重新粘贴")
        choice = input("\n是否重新粘贴？(直接回车=是, 输入0=否): ").strip()
        if choice == '' or choice == '1':
            return None
    
    print(f"\n[成功] 提取到 {len(unique_songs)} 首歌曲")
    
    if unique_songs:
        print("\n提取结果预览（前30首）：")
        for i, s in enumerate(unique_songs[:30], 1):
            display_name = s['name'][:40] + '...' if len(s['name']) > 40 else s['name']
            if s['artist']:
                print(f"  {i}. {display_name} - {s['artist'][:30]}")
            else:
                print(f"  {i}. {display_name}")
        if len(unique_songs) > 30:
            print(f"  ... 共 {len(unique_songs)} 首")
    
    return unique_songs

# ==================== 酷狗歌单处理 ====================

def smart_search_bilibili_for_song(song_name, max_retries=3):
    """智能搜索B站视频 - 自动选择最佳匹配"""
    retry_count = 0
    
    while retry_count <= max_retries:
        if retry_count > 0:
            print(f"\n[重试 {retry_count}/{max_retries}] 重新搜索: {song_name}")
            time.sleep(2)
        
        print(f"\n[智能搜索] {song_name}")
        
        def calculate_title_match_score(query: str, title: str) -> float:
            query_lower = query.lower()
            title_lower = title.lower()
            
            score = 0.0
            if query_lower == title_lower:
                score = 1.0
            elif query_lower in title_lower:
                score = 0.9
            elif title_lower in query_lower:
                score = 0.8
            
            def extract_keywords(text):
                chinese = re.findall(r'[\u4e00-\u9fff]+', text)
                japanese = re.findall(r'[\u3040-\u309f\u30a0-\u30ff]+', text)
                english = re.findall(r'[a-zA-Z]{3,}', text)
                return set(chinese + japanese + [w.lower() for w in english])
            
            query_keywords = extract_keywords(query_lower)
            title_keywords = extract_keywords(title_lower)
            
            if query_keywords:
                matched = len(query_keywords & title_keywords)
                total = len(query_keywords)
                keyword_score = matched / total if total > 0 else 0
                score += keyword_score * 0.5
            
            return min(score, 1.0)
        
        orders = ['totalrank', 'click']
        all_results = []
        
        for order in orders:
            try:
                params = {
                    'keyword': song_name[:30],
                    'page': 1,
                    'pagesize': 10,
                    'search_type': 'video',
                    'order': order
                }
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.bilibili.com/',
                    'Accept': 'application/json, text/plain, */*',
                }
                search_url = "https://api.bilibili.com/x/web-interface/search/type"
                resp = requests.get(search_url, params=params, headers=headers, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('code') == 0:
                        videos = data.get('data', {}).get('result', [])
                        for item in videos:
                            title = item.get('title', '')
                            title = re.sub(r'<em class="keyword">', '', title)
                            title = re.sub(r'</em>', '', title)
                            title = title.replace('&amp;', '&')
                            
                            all_results.append({
                                'bvid': item.get('bvid', ''),
                                'title': title,
                                'author': item.get('author', ''),
                                'play': item.get('play', 0),
                                'duration': item.get('duration', ''),
                                'score': calculate_title_match_score(song_name, title)
                            })
            except Exception as e:
                continue
            time.sleep(0.5)
        
        if all_results:
            break
        
        retry_count += 1
    
    if not all_results:
        print(f"[错误] 搜索失败: {song_name}")
        print("  可能原因：网络问题或B站接口限制")
        print("  选项：")
        print("  [1] 重试")
        print("  [2] 跳过此歌曲")
        print("  [0] 取消整个任务")
        print("[提示] 直接回车 = 重试")
        
        while True:
            choice = input("\n请选择 [0-2] 或直接回车: ").strip()
            if choice == '' or choice == '1':
                return smart_search_bilibili_for_song(song_name, max_retries)
            elif choice == '2':
                return None
            elif choice == '0':
                raise KeyboardInterrupt("用户取消")
            else:
                p("无效选项", 'y')
    
    unique_results = {}
    for video in all_results:
        bvid = video['bvid']
        if bvid not in unique_results or video['score'] > unique_results[bvid]['score']:
            unique_results[bvid] = video
    
    sorted_results = sorted(unique_results.values(), key=lambda x: x['score'], reverse=True)
    
    best = sorted_results[0]
    if best['score'] >= 0.6:
        p(f"[自动选择] 匹配度 {best['score']:.0%} - {best['title'][:50]}", 'g')
    else:
        p(f"[自动选择] 匹配度 {best['score']:.0%} - {best['title'][:50]}", 'y')
    
    return best

def process_copied_playlist():
    """处理用户复制的歌单文本"""
    print("\n" + "=" * 50)
    p("       粘贴歌单模式", 'c')
    print("=" * 50)
    print("使用说明：")
    print("  1. 在浏览器中打开酷狗歌单网页")
    print("  2. 向下滚动到页面底部，让所有歌曲都加载出来")
    print("  3. 按 Ctrl+A 全选 -> 复制")
    print("  4. 粘贴到下方（支持多行粘贴，按 Ctrl+Z 结束）")
    print("=" * 50)
    
    while True:
        raw_text = get_multiline_input_ctrl_d("\n请粘贴网页内容（粘贴后按 Ctrl+Z 再按回车结束）:")
        
        if not raw_text.strip():
            p("未输入任何内容", 'y')
            continue
        
        song_list = extract_song_names_from_text(raw_text)
        
        if song_list is None:
            continue
        
        if not song_list:
            p("未能从文本中提取到歌名", 'r')
            print("[提示] 直接回车 = 重新粘贴")
            choice = input("\n是否重新粘贴？(直接回车=是, 输入0=否): ").strip()
            if choice == '' or choice == '1':
                continue
            else:
                return
        
        break
    
    print("\n" + "=" * 50)
    print("请选择下载模式：")
    print("  [3] 两者都要（MP4+MP3，MP3带封面）")
    print("  [2] 仅MP3（下载音频，自动添加封面）")
    print("  [1] 仅MP4（下载视频）")
    print("  [0] 返回主菜单")
    print("=" * 50)
    
    mode_choice = input("\n请输入选项 [0-3]: ").strip()
    if mode_choice == '0':
        p("已取消", 'y')
        return
    if mode_choice not in ['1', '2', '3']:
        p("无效选项，使用模式2（仅MP3）", 'y')
        mode_choice = '2'
    
    current_mode = int(mode_choice)
    mode_text = {1: 'MP4', 2: 'MP3', 3: 'MP4+MP3'}.get(current_mode, 'MP3')
    p(f"\n[设置] 下载模式: {mode_text}", 'c')
    
    print(f"\n开始处理 {len(song_list)} 首歌曲...")
    print("提示：按 Ctrl+C 可中断处理")
    success_count = 0
    fail_count = 0
    
    for idx, song_info in enumerate(song_list, 1):
        print(f"\n{'=' * 50}")
        print(f"[{idx}/{len(song_list)}] 歌曲: {song_info['name']}")
        if song_info['artist']:
            print(f"     歌手: {song_info['artist']}")
        print("=" * 50)
        
        search_term = song_info['search_term']
        
        selected = smart_search_bilibili_for_song(search_term)
        if not selected:
            p(f"跳过: {song_info['name']}", 'y')
            fail_count += 1
            continue
        
        video_url = f"https://www.bilibili.com/video/{selected['bvid']}"
        p(f"[下载] 开始处理...", 'c')
        
        if process_single_video(video_url, current_mode):
            success_count += 1
            p(f"处理成功: {song_info['name']}", 'g')
        else:
            fail_count += 1
            p(f"处理失败: {song_info['name']}", 'r')
    
    print("\n" + "=" * 50)
    p("       处理完成", 'c')
    print("=" * 50)
    p(f"成功: {success_count} 首", 'g')
    p(f"失败: {fail_count} 首", 'r' if fail_count > 0 else 'g')
    print("=" * 50)
    p(f"保存位置: {DOWNLOAD_PATH}", 'c')
    input("\n按回车键返回主菜单...")

# ==================== MP3封面管理功能 ====================

def get_mp3_duration(mp3_path: str) -> int:
    try:
        audio = MP3(mp3_path)
        return int(audio.info.length)
    except:
        return 0

def has_mp3_cover(mp3_path):
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags and audio.tags.getall('APIC'):
            return True
        return False
    except:
        return False

def get_mp3_files_with_cover_info(folder_path):
    if not os.path.exists(folder_path):
        return [], []
    
    mp3_with_cover = []
    mp3_without_cover = []
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.mp3'):
                mp3_path = os.path.join(root, file)
                if has_mp3_cover(mp3_path):
                    mp3_with_cover.append(mp3_path)
                else:
                    mp3_without_cover.append(mp3_path)
    
    return mp3_with_cover, mp3_without_cover

def get_mp3_cover_info(mp3_path):
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags and audio.tags.getall('APIC'):
            apic = audio.tags.getall('APIC')[0]
            return {
                'has_cover': True,
                'mime': apic.mime,
                'size': len(apic.data),
                'desc': apic.desc if apic.desc else '无描述'
            }
    except:
        pass
    return {'has_cover': False}

def display_mp3_list_with_status(mp3_files, base_folder, title="MP3文件列表"):
    for i, mp3_path in enumerate(mp3_files, 1):
        rel_path = os.path.relpath(mp3_path, base_folder)
        base_name = os.path.basename(mp3_path)
        
        if os.path.dirname(rel_path) != '.':
            display_name = f"{rel_path}"
        else:
            display_name = base_name
        
        has_cover = has_mp3_cover(mp3_path)
        
        duration = get_mp3_duration(mp3_path)
        if duration > 0:
            minutes = duration // 60
            seconds = duration % 60
            duration_str = f" [{minutes}:{seconds:02d}]"
        else:
            duration_str = ""
        
        if has_cover:
            try:
                audio = MP3(mp3_path, ID3=ID3)
                if audio.tags and audio.tags.getall('APIC'):
                    apic = audio.tags.getall('APIC')[0]
                    size_kb = len(apic.data) / 1024
                    status = f'有封面 ({size_kb:.0f}KB){duration_str}'
                    color = 'g'
                else:
                    status = f'无封面{duration_str}'
                    color = 'y'
            except:
                status = f'无封面{duration_str}'
                color = 'y'
        else:
            status = f'无封面{duration_str}'
            color = 'y'
        
        print(f"  {i}. {display_name}")
        p(f"     状态: {status}", color)
    
    print(f"\n{'='*60}")
    p(f"       {title}", 'c')
    print(f"{'='*60}")

def check_network():
    try:
        requests.get('https://api.bilibili.com', timeout=5)
        return True
    except:
        return False

def get_bilibili_cover_by_bvid(bvid):
    try:
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(api_url, headers=headers, timeout=10)
        data = resp.json()
        if data.get('code') == 0:
            pic = data['data'].get('pic', '')
            if pic:
                if pic.startswith('//'):
                    pic = 'https:' + pic
                return pic
    except:
        pass
    return None

def download_and_crop_cover_for_mp3(cover_url, output_path):
    try:
        if cover_url.startswith('//'):
            cover_url = 'https:' + cover_url
        
        resp = requests.get(cover_url, timeout=15)
        if resp.status_code != 200:
            return False
        
        img = Image.open(io.BytesIO(resp.content))
        
        if img.mode == 'RGBA':
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
            img = rgb_img
        elif img.mode == 'P':
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        w, h = img.size
        size = min(w, h)
        left = (w - size) // 2
        top = (h - size) // 2
        cropped = img.crop((left, top, left + size, top + size))
        cropped.save(output_path, 'JPEG', quality=90)
        return True
    except:
        return False

def add_cover_to_mp3_file(mp3_path, cover_image_path):
    try:
        try:
            audio = MP3(mp3_path, ID3=ID3)
        except:
            audio = MP3(mp3_path)
            audio.add_tags()
        
        if audio.tags is None:
            audio.add_tags()
        
        with open(cover_image_path, 'rb') as f:
            image_data = f.read()
        
        apic = APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc='Cover',
            data=image_data
        )
        
        if audio.tags is not None:
            audio.tags.delall('APIC')
        audio.tags.add(apic)
        audio.save(v2_version=3)
        return True
    except:
        return False

def calculate_title_match_score(song_name: str, video_title: str) -> float:
    score = 0.0
    song_lower = song_name.lower()
    title_lower = video_title.lower()
    
    if song_lower == title_lower:
        score += 1.0
    elif song_lower in title_lower:
        score += 0.9
    elif title_lower in song_lower:
        score += 0.8
    
    def extract_keywords(text: str) -> set:
        japanese = re.findall(r'[\u3040-\u309f\u30a0-\u30ff]+', text)
        chinese = re.findall(r'[\u4e00-\u9fff]+', text)
        english = re.findall(r'[a-zA-Z]{3,}', text)
        
        keywords = set()
        keywords.update(japanese)
        keywords.update(chinese)
        keywords.update([w.lower() for w in english])
        
        return keywords
    
    song_keywords = extract_keywords(song_lower)
    title_keywords = extract_keywords(title_lower)
    
    if song_keywords:
        matched = len(song_keywords & title_keywords)
        total = len(song_keywords)
        keyword_score = matched / total if total > 0 else 0
        score += keyword_score * 0.6
        
        japanese_song = [w for w in song_keywords if re.match(r'[\u3040-\u309f\u30a0-\u30ff]', w)]
        japanese_title = [w for w in title_keywords if re.match(r'[\u3040-\u309f\u30a0-\u30ff]', w)]
        if japanese_song and any(w in japanese_title for w in japanese_song):
            score += 0.2
    
    len_ratio = min(len(song_name), len(video_title)) / max(len(song_name), len(video_title))
    score += len_ratio * 0.1
    
    return min(score, 1.0)

def calculate_duration_score(mp3_duration: int, video_duration: int) -> float:
    if mp3_duration == 0 or video_duration == 0:
        return 0.5
    
    diff = abs(mp3_duration - video_duration)
    if diff <= 30:
        return 1.0
    elif diff <= 60:
        return 0.8
    elif diff <= 120:
        return 0.5
    elif diff <= 240:
        return 0.3
    else:
        return 0.1

def search_with_order(keyword: str, order: str) -> List[Dict]:
    if not check_network():
        p(f'  [网络错误] 无法连接B站服务器', 'r')
        return []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }
    
    search_keyword = keyword[:30] if len(keyword) > 30 else keyword
    
    params = {
        'keyword': search_keyword,
        'page': 1,
        'pagesize': 20,
        'search_type': 'video',
        'order': order
    }
    
    try:
        search_url = "https://api.bilibili.com/x/web-interface/search/type"
        
        for retry in range(2):
            try:
                resp = requests.get(search_url, params=params, headers=headers, timeout=10)
                
                if resp.status_code == 200:
                    break
                elif resp.status_code == 412:
                    p(f'  [请求被拒绝] 等待后重试...', 'y')
                    time.sleep(2)
                    continue
                else:
                    p(f'  [HTTP {resp.status_code}]', 'y')
                    return []
            except requests.exceptions.Timeout:
                p(f'  [超时] 第{retry+1}次重试...', 'y')
                time.sleep(1)
                continue
            except requests.exceptions.ConnectionError as e:
                p(f'  [连接错误] 请检查网络', 'y')
                return []
            except Exception as e:
                p(f'  [请求错误] {str(e)[:50]}', 'y')
                return []
        
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        if data.get('code') != 0:
            return []
        
        result = data.get('data', {})
        videos = result.get('result', [])
        
        if not videos:
            return []
        
        results = []
        for item in videos:
            title = item.get('title', '')
            title = re.sub(r'<em class="keyword">', '', title)
            title = re.sub(r'</em>', '', title)
            title = title.replace('&amp;', '&')
            title = title.replace('&#39;', "'")
            title = title.replace('&quot;', '"')
            
            pic = item.get('pic', '')
            if pic and pic.startswith('//'):
                pic = 'https:' + pic
            elif pic and not pic.startswith(('http://', 'https://')):
                pic = 'https://' + pic
            
            duration = item.get('duration', 0)
            if isinstance(duration, str):
                if ':' in duration:
                    parts = duration.split(':')
                    if len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    else:
                        duration = 0
                else:
                    try:
                        duration = int(duration)
                    except:
                        duration = 0
            elif not isinstance(duration, (int, float)):
                duration = 0
            
            results.append({
                'bvid': item.get('bvid', ''),
                'title': title,
                'author': item.get('author', ''),
                'play': item.get('play', 0),
                'duration': duration,
                'pic': pic,
            })
        return results
    except Exception as e:
        p(f'[搜索错误] {str(e)[:50]}', 'y')
        return []

def smart_search_bilibili_with_duration(song_name: str, mp3_duration: int = 0) -> Optional[Dict]:
    def extract_core_info(name: str) -> List[str]:
        candidates = []
        
        if len(name) <= 30:
            candidates.append(name)
        else:
            candidates.append(name[:30])
        
        bracket_patterns = [
            r'[（(]([^）)]+)[）)]',
            r'[【\[](.*?)[】\]]',
        ]
        for pattern in bracket_patterns:
            matches = re.findall(pattern, name)
            for m in matches:
                if len(m) <= 30 and len(m) >= 2:
                    candidates.append(m)
        
        clean_name = re.sub(r'[（(][^）)]*[）)]', '', name)
        clean_name = re.sub(r'[【\[](.*?)[】\]]', '', clean_name)
        clean_name = clean_name.strip()
        if clean_name and clean_name != name and len(clean_name) <= 30:
            candidates.append(clean_name)
        
        japanese = re.findall(r'[\u3040-\u309f\u30a0-\u30ff]{2,}', clean_name)
        if japanese:
            for jp in japanese[:2]:
                if len(jp) >= 2:
                    candidates.append(jp)
        
        chinese = re.findall(r'[\u4e00-\u9fff]{2,}', clean_name)
        if chinese:
            for cn in chinese[:2]:
                if len(cn) >= 2:
                    candidates.append(cn)
        
        english_words = re.findall(r'[a-zA-Z]{3,}', clean_name)
        for word in english_words[:2]:
            if word.lower() not in ['the', 'and', 'for', 'with', 'feat']:
                candidates.append(word)
        
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c not in seen and len(c) >= 2:
                seen.add(c)
                unique_candidates.append(c)
        
        return unique_candidates[:3]
    
    max_retries = 3
    for retry in range(max_retries):
        if retry > 0:
            print(f"\n[重试 {retry}/{max_retries-1}] 重新搜索: {song_name[:50]}")
            time.sleep(2)
        
        candidates = extract_core_info(song_name)
        
        if candidates:
            print(f"[分析] 提取到 {len(candidates)} 个搜索候选:")
            for i, cand in enumerate(candidates, 1):
                print(f"  {i}. {cand}")
        else:
            print(f"[分析] 使用原始搜索词")
            candidates = [song_name[:30]] if len(song_name) > 30 else [song_name]
        
        all_results = []
        orders = ['totalrank', 'click']
        
        for keyword in candidates:
            p(f'\n[搜索] 关键词: "{keyword}"', 'c')
            
            for order in orders:
                results = search_with_order(keyword, order)
                if results:
                    p(f'  [{order}] 找到 {len(results)} 个结果', 'g')
                    for video in results:
                        video['search_keyword'] = keyword
                        video['title_score'] = calculate_title_match_score(song_name, video['title'])
                        video['duration_score'] = calculate_duration_score(mp3_duration, video['duration'])
                        video['total_score'] = video['title_score'] * 0.7 + video['duration_score'] * 0.3
                        all_results.append(video)
                else:
                    p(f'  [{order}] 无结果', 'y')
                time.sleep(0.5)
        
        if all_results:
            break
        
        if retry == max_retries - 1:
            print(f"[失败] 未找到任何结果: {song_name}")
            print("  选项：")
            print("  [1] 重试")
            print("  [2] 跳过此文件")
            print("  [0] 取消整个任务")
            print("[提示] 直接回车 = 重试")
            
            while True:
                choice = input("\n请选择 [0-2] 或直接回车: ").strip()
                if choice == '' or choice == '1':
                    continue
                elif choice == '2':
                    return None
                elif choice == '0':
                    raise KeyboardInterrupt("用户取消")
                else:
                    p("无效选项", 'y')
    
    if not all_results:
        return None
    
    unique_results = {}
    for video in all_results:
        bvid = video['bvid']
        if bvid not in unique_results or video['total_score'] > unique_results[bvid]['total_score']:
            unique_results[bvid] = video
    
    all_results = list(unique_results.values())
    all_results.sort(key=lambda x: x['total_score'], reverse=True)
    
    for i, video in enumerate(all_results[:10], 1):
        total_score = video['total_score']
        title_score = video['title_score']
        duration_score = video['duration_score']
        play = video.get('play', 0)
        title = video['title'][:55] + '...' if len(video['title']) > 55 else video['title']
        
        vid_duration = video.get('duration', 0)
        if vid_duration > 0:
            vid_min = vid_duration // 60
            vid_sec = vid_duration % 60
            duration_str = f"{vid_min}:{vid_sec:02d}"
        else:
            duration_str = "未知"
        
        if mp3_duration > 0:
            mp3_min = mp3_duration // 60
            mp3_sec = mp3_duration % 60
            mp3_duration_str = f"{mp3_min}:{mp3_sec:02d}"
        else:
            mp3_duration_str = "未知"
        
        if total_score >= 0.8:
            color = 'g'
            mark = '★★★'
        elif total_score >= 0.6:
            color = 'c'
            mark = '★★☆'
        elif total_score >= 0.4:
            color = 'y'
            mark = '★☆☆'
        else:
            color = 'r'
            mark = '☆☆☆'
        
        p(f'  {i}. [{mark}] 综合: {total_score:.1%} (标题:{title_score:.1%} 时长:{duration_score:.1%})', color)
        print(f'     标题: {title}')
        print(f'     播放: {play:,} | MP3时长: {mp3_duration_str} | 视频时长: {duration_str}')
    
    print(f"\n{'='*60}")
    p(f"  找到 {len(all_results)} 个结果，按综合匹配度排序", 'c')
    print(f"{'='*60}")
    
    high_title_videos = [v for v in all_results if v['title_score'] >= 0.5]
    if high_title_videos:
        high_title_videos.sort(key=lambda x: x['total_score'], reverse=True)
        best_video = high_title_videos[0]
        p(f'\n[自动选择] 高标题匹配度视频 (标题:{best_video["title_score"]:.1%} 综合:{best_video["total_score"]:.1%})', 'g')
    else:
        if all_results:
            best_video = all_results[0]
            p(f'\n[自动选择] 最佳匹配视频 (综合: {best_video["total_score"]:.1%})', 'y')
    
    if best_video:
        vid_duration = best_video.get('duration', 0)
        if vid_duration > 0:
            vid_min = vid_duration // 60
            vid_sec = vid_duration % 60
            duration_str = f"{vid_min}:{vid_sec:02d}"
        else:
            duration_str = "未知"
        
        if mp3_duration > 0:
            mp3_min = mp3_duration // 60
            mp3_sec = mp3_duration % 60
            mp3_duration_str = f"{mp3_min}:{mp3_sec:02d}"
        else:
            mp3_duration_str = "未知"
        
        p(f'\n[最终选择]', 'c')
        p(f'  标题: {best_video["title"][:70]}', 'c')
        p(f'  播放: {best_video["play"]:,}', 'g')
        p(f'  MP3时长: {mp3_duration_str} | 视频时长: {duration_str}', 'g')
        p(f'  综合匹配度: {best_video["total_score"]:.1%} (标题:{best_video["title_score"]:.1%} 时长:{best_video["duration_score"]:.1%})', 'g')
        
        print("\n选项：")
        print("  [1] 使用此视频的封面")
        print("  [2] 重新搜索（手动选择）")
        print("  [3] 跳过此文件")
        print("[提示] 直接回车 = 使用此视频的封面")
        
        while True:
            choice = input("\n请选择 [1-3] 或直接回车: ").strip()
            if choice == '' or choice == '1':
                return best_video
            elif choice == '2':
                print("\n请手动选择：")
                for i, video in enumerate(all_results[:10], 1):
                    print(f"  [{i}] {video['title'][:60]}")
                print(f"  [0] 跳过")
                while True:
                    manual_choice = input("\n请输入序号 [0-10]: ").strip()
                    if manual_choice == '0':
                        return None
                    try:
                        idx = int(manual_choice) - 1
                        if 0 <= idx < len(all_results[:10]):
                            return all_results[idx]
                        else:
                            p(f"请输入 0-{min(10, len(all_results))}", 'y')
                    except:
                        p("无效输入", 'y')
            elif choice == '3':
                return None
            else:
                p("无效选项，请输入 1-3 或直接回车", 'y')
    
    return None

def process_mp3_cover(mp3_path):
    try:
        base_name = os.path.basename(mp3_path)
        song_name = os.path.splitext(base_name)[0]
        
        song_name = re.sub(r'[_\-\d]+$', '', song_name)
        song_name = song_name.strip()
        
        mp3_duration = get_mp3_duration(mp3_path)
        
        p(f'\n{"="*50}', 'm')
        p(f'[处理] {base_name}', 'c')
        p(f'[搜索词] {song_name}', 'y')
        if mp3_duration > 0:
            minutes = mp3_duration // 60
            seconds = mp3_duration % 60
            p(f'[MP3时长] {minutes}:{seconds:02d}', 'c')
        
        search_result = smart_search_bilibili_with_duration(song_name, mp3_duration)
        
        if not search_result:
            p(f'[失败] 无法找到相关视频: {song_name}', 'r')
            return False
        
        cover_url = search_result.get('pic', '')
        if not cover_url:
            bvid = search_result.get('bvid', '')
            if bvid:
                cover_url = get_bilibili_cover_by_bvid(bvid)
        
        if not cover_url:
            p(f'[失败] 无法获取封面', 'r')
            return False
        
        cover_tmp = mp3_path.replace('.mp3', '_temp_cover.jpg')
        
        if not download_and_crop_cover_for_mp3(cover_url, cover_tmp):
            p(f'[失败] 下载封面失败', 'r')
            return False
        
        if add_cover_to_mp3_file(mp3_path, cover_tmp):
            p(f'[成功] 封面已添加', 'g')
            try:
                os.remove(cover_tmp)
            except:
                pass
            return True
        else:
            p(f'[失败] 添加封面失败', 'r')
            p(f'[尝试] 尝试修复MP3文件...', 'y')
            
            backup_path = mp3_path + '.bak'
            try:
                shutil.copy2(mp3_path, backup_path)
                p(f'[备份] 已创建备份: {os.path.basename(backup_path)}', 'c')
                
                try:
                    audio = MP3(mp3_path)
                    try:
                        audio.delete()
                    except:
                        pass
                    audio.add_tags()
                    with open(cover_tmp, 'rb') as f:
                        image_data = f.read()
                    apic = APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,
                        desc='Cover',
                        data=image_data
                    )
                    audio.tags.add(apic)
                    audio.save()
                    p(f'[修复成功] 封面已添加', 'g')
                    try:
                        os.remove(cover_tmp)
                        os.remove(backup_path)
                    except:
                        pass
                    return True
                except Exception as e2:
                    p(f'[修复失败] {e2}', 'r')
                    try:
                        shutil.copy2(backup_path, mp3_path)
                        p(f'[恢复] 已恢复原文件', 'g')
                    except:
                        pass
            except Exception as e:
                p(f'[备份失败] {e}', 'y')
            
            try:
                os.remove(cover_tmp)
            except:
                pass
            return False
            
    except Exception as e:
        p(f'[异常] 处理失败: {e}', 'r')
        return False

def manual_replace_mp3_cover():
    print("\n" + "=" * 60)
    p("       手动替换MP3封面", 'c')
    print("=" * 60)
    
    while True:
        mp3_path = input("\n请输入MP3文件完整路径: ").strip()
        
        if mp3_path.startswith('~'):
            mp3_path = os.path.expanduser(mp3_path)
        
        mp3_path = os.path.abspath(mp3_path)
        
        if os.path.exists(mp3_path) and mp3_path.lower().endswith('.mp3'):
            break
        else:
            p(f'[错误] 文件不存在或不是MP3文件: {mp3_path}', 'r')
            print("[提示] 直接回车 = 重新输入")
            choice = input("是否重新输入？(直接回车=是, 输入0=否): ").strip()
            if choice == '' or choice == '1':
                continue
            else:
                return
    
    cover_info = get_mp3_cover_info(mp3_path)
    base_name = os.path.basename(mp3_path)
    
    duration = get_mp3_duration(mp3_path)
    if duration > 0:
        minutes = duration // 60
        seconds = duration % 60
        duration_str = f" ({minutes}:{seconds:02d})"
    else:
        duration_str = ""
    
    print(f"\n{'='*50}")
    p(f"文件: {base_name}{duration_str}", 'c')
    if cover_info['has_cover']:
        p(f"当前状态: 有封面 ({cover_info['mime']}, {cover_info['size']/1024:.0f}KB)", 'g')
    else:
        p(f"当前状态: 无封面", 'y')
    print(f"{'='*50}")
    
    print("[提示] 直接回车 = 确认")
    confirm = input("\n确认要为此文件添加/替换封面？(直接回车=是, 输入0=否): ").strip()
    if confirm == '' or confirm == '1':
        p(f'\n开始处理...', 'c')
        
        if process_mp3_cover(mp3_path):
            p(f'\n[成功] 封面已添加/替换: {base_name}', 'g')
        else:
            p(f'\n[失败] 处理失败: {base_name}', 'r')
    else:
        p('[取消]', 'y')
    
    input("\n按回车键返回...")

def batch_add_mp3_covers():
    print("\n" + "=" * 60)
    p("       MP3封面智能管理工具 v4.5", 'c')
    print("=" * 60)
    print("功能说明:")
    print("  1. 递归扫描指定文件夹及所有子文件夹中的MP3文件")
    print("  2. 显示每个MP3的封面状态、时长和所在位置")
    print("  3. 可选择处理无封面的文件")
    print("  4. 也可选择替换已有封面的文件")
    print("  5. 支持手动选择单个或多个文件")
    print("  6. 智能搜索算法：")
    print("     - 正则表达式提取核心信息（支持日文）")
    print("     - 多种排序方式搜索")
    print("     - 标题匹配度 + 时长匹配度综合评分")
    print("     - 优先选择标题匹配度高的视频")
    print("  7. 自动备份和修复损坏的MP3文件")
    print("  8. 支持PNG透明背景转换")
    print("  9. 单行进度条显示")
    print("=" * 60)
    
    print("\n[网络] 检查网络连接...")
    if not check_network():
        p('[网络] 无法连接B站服务器！', 'r')
        p('[建议] 1. 检查WiFi/移动网络是否正常', 'y')
        p('[建议] 2. 尝试切换网络', 'y')
        p('[建议] 3. 检查是否开启了代理/VPN', 'y')
        p('[建议] 4. 稍后重试', 'y')
        input("\n按回车键返回...")
        return
    p('[网络] 连接正常', 'g')
    
    while True:
        folder_path = input("\n请输入MP3文件夹路径: ").strip()
        
        if folder_path.startswith('~'):
            folder_path = os.path.expanduser(folder_path)
        
        folder_path = os.path.abspath(folder_path)
        
        if os.path.exists(folder_path):
            break
        else:
            p(f'[错误] 文件夹不存在: {folder_path}', 'r')
            print("[提示] 直接回车 = 重新输入")
            choice = input("是否重新输入？(直接回车=是, 输入0=否): ").strip()
            if choice == '' or choice == '1':
                continue
            else:
                return
    
    p(f'\n[扫描] 文件夹: {folder_path}', 'c')
    p(f'[提示] 正在递归扫描所有子文件夹...', 'y')
    
    mp3_with_cover, mp3_without_cover = get_mp3_files_with_cover_info(folder_path)
    
    all_mp3_files = mp3_with_cover + mp3_without_cover
    
    if not all_mp3_files:
        p('[提示] 文件夹及子文件夹中没有找到MP3文件', 'y')
        input("\n按回车键返回...")
        return
    
    folders_found = set()
    for mp3 in all_mp3_files:
        folders_found.add(os.path.dirname(mp3))
    
    print(f"\n{'='*50}")
    p(f'  扫描文件夹: {folder_path}', 'c')
    p(f'  发现子文件夹: {len(folders_found)} 个', 'c')
    p(f'  总MP3文件: {len(all_mp3_files)} 个', 'c')
    p(f'  有封面: {len(mp3_with_cover)} 个', 'g')
    p(f'  无封面: {len(mp3_without_cover)} 个', 'y' if mp3_without_cover else 'g')
    
    if mp3_without_cover:
        for i, mp3_path in enumerate(mp3_without_cover, 1):
            rel_path = os.path.relpath(mp3_path, folder_path)
            base_name = os.path.basename(mp3_path)
            
            if os.path.dirname(rel_path) != '.':
                display_name = f"{rel_path}"
            else:
                display_name = base_name
            
            has_cover = has_mp3_cover(mp3_path)
            
            duration = get_mp3_duration(mp3_path)
            if duration > 0:
                minutes = duration // 60
                seconds = duration % 60
                duration_str = f" [{minutes}:{seconds:02d}]"
            else:
                duration_str = ""
            
            if has_cover:
                try:
                    audio = MP3(mp3_path, ID3=ID3)
                    if audio.tags and audio.tags.getall('APIC'):
                        apic = audio.tags.getall('APIC')[0]
                        size_kb = len(apic.data) / 1024
                        status = f'有封面 ({size_kb:.0f}KB){duration_str}'
                        color = 'g'
                    else:
                        status = f'无封面{duration_str}'
                        color = 'y'
                except:
                    status = f'无封面{duration_str}'
                    color = 'y'
            else:
                status = f'无封面{duration_str}'
                color = 'y'
            
            print(f"  {i}. {display_name}")
            p(f"     状态: {status}", color)
    
    print(f"\n{'='*50}")
    p("       扫描结果统计", 'c')
    print(f"{'='*50}")
    
    if mp3_with_cover:
        print("\n选项:")
        print("  [1] 仅处理无封面的文件")
        print("  [2] 处理所有文件（包括替换已有封面）")
        print("  [3] 手动选择要处理的文件（支持多选）")
        print("  [0] 返回主菜单")
        
        choice = input("\n请选择 [0-3]: ").strip()
        
        if choice == '0':
            return
        elif choice == '1':
            selected_files = mp3_without_cover
            if not selected_files:
                p('[提示] 没有无封面的文件需要处理', 'g')
                input("\n按回车键返回...")
                return
        elif choice == '2':
            selected_files = all_mp3_files
            p('[提示] 将处理所有文件，已有封面的将被替换', 'y')
            print("[提示] 直接回车 = 确认")
            confirm = input("确认继续？(直接回车=是, 输入0=否): ").strip()
            if confirm == '' or confirm == '1':
                pass
            else:
                return
        elif choice == '3':
            display_mp3_list_with_status(all_mp3_files, folder_path, "所有MP3文件")
            
            print(f"\n请输入要处理的文件序号 (1-{len(all_mp3_files)})")
            print("格式示例:")
            print("  - 单个: 1")
            print("  - 多个: 1,3,5")
            print("  - 范围: 1-5")
            print("  - 混合: 1,3-5,7")
            print("  - 全部: 0")
            
            selection = input("\n请输入: ").strip()
            
            if not selection:
                p('[取消] 未选择任何文件', 'y')
                return
            
            if selection == '0':
                selected_files = all_mp3_files
            else:
                selected_indices = parse_selection_input(selection, len(all_mp3_files))
                if selected_indices:
                    selected_files = [all_mp3_files[i] for i in selected_indices]
                else:
                    p('[错误] 无效的选择', 'r')
                    return
        else:
            p('[错误] 无效选项', 'r')
            return
    else:
        selected_files = mp3_without_cover
        if not selected_files:
            p('[提示] 没有需要处理的文件', 'g')
            input("\n按回车键返回...")
            return
        
        print("\n选项:")
        print("  [1] 开始处理所有无封面文件")
        print("  [2] 手动选择要处理的文件")
        print("  [0] 返回主菜单")
        
        choice = input("\n请选择 [0-2]: ").strip()
        
        if choice == '0':
            return
        elif choice == '2':
            display_mp3_list_with_status(selected_files, folder_path, "无封面的MP3文件")
            
            print(f"\n请输入要处理的文件序号 (1-{len(selected_files)})")
            print("格式示例: 1,3,5 或 1-3 或 0(全部)")
            selection = input("请输入: ").strip()
            
            if selection == '0':
                pass
            else:
                selected_indices = parse_selection_input(selection, len(selected_files))
                if selected_indices:
                    selected_files = [selected_files[i] for i in selected_indices]
                else:
                    p('[错误] 无效的选择', 'r')
                    return
        elif choice != '1':
            p('[错误] 无效选项', 'r')
            return
    
    if not selected_files:
        p('[取消] 没有选择任何文件', 'y')
        return
    
    print(f"\n{'='*50}")
    p(f"       将要处理 {len(selected_files)} 个文件", 'c')
    print(f"{'='*50}")
    for i, mp3_path in enumerate(selected_files, 1):
        rel_path = os.path.relpath(mp3_path, folder_path)
        base_name = os.path.basename(mp3_path)
        if os.path.dirname(rel_path) != '.':
            display_name = f"{rel_path}"
        else:
            display_name = base_name
        
        has_cover = has_mp3_cover(mp3_path)
        status = "(已有封面，将替换)" if has_cover else "(无封面)"
        print(f"  {i}. {display_name} {status}")
    print(f"{'='*50}")
    
    print("[提示] 直接回车 = 确认")
    confirm = input("\n确认开始处理？(直接回车=是, 输入0=否): ").strip()
    if confirm != '' and confirm != '1':
        p('[取消] 已取消处理', 'y')
        return
    
    p(f'\n开始处理 {len(selected_files)} 个文件...', 'c')
    p('[提示] 将使用智能搜索算法（标题匹配+时长匹配，优先标题匹配度）', 'y')
    p('[提示] 如果遇到网络问题，请检查网络连接后重试', 'y')
    
    success_count = 0
    fail_count = 0
    replace_count = 0
    
    for i, mp3_path in enumerate(selected_files, 1):
        if i % 10 == 0 and not check_network():
            p(f'\n[网络] 网络连接已断开！', 'r')
            p(f'[提示] 已处理 {i-1}/{len(selected_files)} 个文件', 'y')
            print("[提示] 直接回车 = 重试")
            retry_network = input("是否重试？(直接回车=是, 输入0=否): ").strip()
            if retry_network == '' or retry_network == '1':
                time.sleep(5)
                continue
            else:
                break
        
        rel_path = os.path.relpath(mp3_path, folder_path)
        p(f'\n[{i}/{len(selected_files)}] {rel_path}', 'm')
        
        had_cover = has_mp3_cover(mp3_path)
        if had_cover:
            replace_count += 1
        
        max_retries = 2
        success = False
        
        for retry in range(max_retries):
            if process_mp3_cover(mp3_path):
                success = True
                success_count += 1
                if had_cover:
                    p(f'[替换] 已成功替换封面', 'g')
                break
            else:
                if retry < max_retries - 1:
                    p(f'[重试] 第{retry+1}次重试该文件...', 'y')
                    time.sleep(2)
        
        if not success:
            fail_count += 1
            p(f'[跳过] 处理失败，跳过该文件', 'r')
    
    print("\n" + "=" * 50)
    p("       处理完成", 'c')
    print("=" * 50)
    p(f'成功: {success_count} 个', 'g')
    p(f'失败: {fail_count} 个', 'r' if fail_count > 0 else 'g')
    if replace_count > 0:
        p(f'其中替换封面: {replace_count} 个', 'c')
    print("=" * 50)
    
    input("\n按回车键返回...")

# ==================== B站搜索功能 ====================

def search_platform_menu():
    print("\n" + "=" * 50)
    p("       搜索平台", 'c')
    print("=" * 50)
    print("  [1] 哔哩哔哩 (Bilibili)")
    print("  [0] 返回主菜单")
    print("=" * 50)
    print("[提示] 直接按回车返回主菜单")
    
    while True:
        choice = input("\n请选择 [0-1] 或直接回车: ").strip()
        if choice == '' or choice == '0':
            return None  # 返回主菜单
        elif choice == '1':
            return 'bilibili'
        else:
            p('无效选项，请重新输入', 'y')

def bili_search(keyword, page=1, page_size=20, max_retries=3):
    """搜索B站视频 - 带重试机制和反爬处理"""
    retry_count = 0
    
    while retry_count < max_retries:
        if retry_count > 0:
            p(f'\n[重试 {retry_count}/{max_retries-1}] 等待 {retry_count * 2} 秒后重试...', 'y')
            time.sleep(retry_count * 2)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
            }
            params = {
                'keyword': keyword,
                'page': page,
                'pagesize': page_size,
                'search_type': 'video'
            }
            
            search_url = "https://api.bilibili.com/x/web-interface/search/type"
            
            session = requests.Session()
            resp = session.get(search_url, params=params, headers=headers, timeout=15)
            
            if resp.status_code == 412:
                p(f'[请求被拒绝] 触发反爬机制，等待后重试...', 'y')
                retry_count += 1
                continue
            elif resp.status_code != 200:
                p(f'[搜索失败] HTTP {resp.status_code}', 'r')
                retry_count += 1
                continue
            
            try:
                data = resp.json()
            except json.JSONDecodeError as e:
                p(f'[JSON解析错误] {e}', 'r')
                retry_count += 1
                continue
            
            if data.get('code') != 0:
                p(f'[搜索失败] {data.get("message", "未知错误")}', 'r')
                retry_count += 1
                continue
            
            result = data.get('data', {})
            videos = result.get('result', [])
            
            if not videos:
                return {'results': [], 'page': page, 'num_results': 0, 'num_pages': 0}
            
            search_results = []
            for item in videos:
                title = item.get('title', '')
                title = re.sub(r'<em class="keyword">', '', title)
                title = re.sub(r'</em>', '', title)
                title = title.replace('&amp;', '&')
                
                pic = item.get('pic', '')
                if pic and pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic and not pic.startswith(('http://', 'https://')):
                    pic = 'https://' + pic
                
                bvid = item.get('bvid', '')
                pages_count = 1
                if bvid:
                    pages_info = get_bilibili_video_pages(bvid)
                    pages_count = len(pages_info) if pages_info else 1
                
                search_results.append({
                    'bvid': bvid,
                    'title': title,
                    'author': item.get('author', ''),
                    'play': item.get('play', 0),
                    'duration': item.get('duration', ''),
                    'pic': pic,
                    'pages': pages_count
                })
            
            num_results = result.get('numResults', 0)
            num_pages = (num_results + page_size - 1) // page_size if num_results > 0 else 0
            
            return {
                'results': search_results,
                'page': page,
                'num_results': num_results,
                'num_pages': num_pages
            }
            
        except requests.exceptions.Timeout:
            p(f'[超时] 连接超时，第 {retry_count + 1} 次重试', 'y')
            retry_count += 1
            continue
        except requests.exceptions.ConnectionError:
            p(f'[连接错误] 无法连接到服务器，第 {retry_count + 1} 次重试', 'y')
            retry_count += 1
            continue
        except Exception as e:
            p(f'[搜索异常] {e}', 'r')
            retry_count += 1
            continue
    
    p('[错误] 多次重试失败，请检查网络连接', 'r')
    return None

def display_search_results(results, page, total_pages):
    config = load_config()
    key_prev = config.get('key_prev', 'a')
    key_next = config.get('key_next', 'd')
    
    total = len(results)
    for i in range(total - 1, -1, -1):
        video = results[i]
        display_num = i + 1
        title = video['title'][:55] + '...' if len(video['title']) > 55 else video['title']
        play = video['play']
        if play >= 10000:
            play_str = f"{play/10000:.1f}万"
        else:
            play_str = str(play)
        
        duration = video['duration'] if video['duration'] else '未知'
        pages_info = f" [{video.get('pages', 1)}P]" if video.get('pages', 1) > 1 else ""
        
        print(f"  {display_num}. {title}{pages_info}")
        print(f"     UP主: {video['author']}  |  播放: {play_str}  |  时长: {duration}")
        print("-" * 56)
    
    print("\n" + "=" * 60)
    p(f"       搜索结果 (第 {page}/{total_pages} 页)", 'c')
    print("=" * 60)
    result_count = len(results)
    print(f"操作说明:")
    print(f"  输入数字 [1-{result_count}] 选择单个视频")
    print(f"  输入 'm' 进入多选模式")
    print(f"  输入 'c' 确认并开始解析")
    print(f"  输入 '0' 返回平台选择")
    print(f"  输入 'q' 返回主菜单")
    print(f"  输入 {key_prev} 上一页  |  输入 {key_next} 下一页")

def search_videos():
    """搜索视频并让用户选择，支持累积多选"""
    platform = search_platform_menu()
    if platform is None:
        return
    
    if platform == 'bilibili':
        print("\n" + "=" * 50)
        p("       搜索视频 - 哔哩哔哩", 'c')
        print("=" * 50)
        
        keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
        while not keyword:
            p("搜索内容不能为空！", 'y')
            print("\n选项:")
            print("  [回车] 重新输入搜索内容")
            print("  [0] 返回平台选择")
            print("  [q] 返回主菜单")
            choice = input("\n请选择: ").strip().lower()
            if choice == '0':
                return  # 返回平台选择
            elif choice == 'q':
                return None  # 返回主菜单
            else:
                keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
        
        page = 1
        page_size = 20
        selected_videos = []
        config = load_config()
        key_prev = config.get('key_prev', 'a')
        key_next = config.get('key_next', 'd')
        
        # 主搜索循环
        while True:
            p(f'\n[搜索] "{keyword}" 第 {page} 页...', 'c')
            result = bili_search(keyword, page, page_size)
            
            # 搜索失败 - 提供友好的重试选项
            if not result:
                p("[错误] 搜索失败，请检查网络后重试", 'r')
                print("\n操作选项:")
                print("  [1] 重新搜索（重试）")
                print("  [2] 修改搜索关键词")
                print("  [0] 返回平台选择")
                print("  [q] 返回主菜单")
                if selected_videos:
                    print(f"  [4] 保留已选 {len(selected_videos)} 个视频，继续处理")
                print("[提示] 直接回车 = 重新搜索（重试）")
                choice = input("\n请选择: ").strip().lower()
                
                if choice == '' or choice == '1':
                    continue  # 重试当前搜索
                elif choice == '2':
                    keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                    while not keyword:
                        p("搜索内容不能为空！", 'y')
                        print("\n选项:")
                        print("  [回车] 重新输入搜索内容")
                        print("  [0] 返回平台选择")
                        print("  [q] 返回主菜单")
                        choice2 = input("\n请选择: ").strip().lower()
                        if choice2 == '0':
                            return
                        elif choice2 == 'q':
                            return None
                        else:
                            keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                    if keyword:
                        page = 1
                        continue
                    else:
                        break
                elif choice == '0':
                    return  # 返回平台选择
                elif choice == 'q':
                    return None  # 返回主菜单
                elif choice == '4' and selected_videos:
                    break
                else:
                    p("无效选项，重新尝试", 'y')
                    continue
            
            if not result['results']:
                p("[提示] 没有找到相关视频", 'y')
                print("\n操作选项:")
                print("  [1] 重新搜索（换关键词）")
                print("  [0] 返回平台选择")
                print("  [q] 返回主菜单")
                if selected_videos:
                    print(f"  [3] 保留已选 {len(selected_videos)} 个视频，继续处理")
                print("[提示] 直接回车 = 重新搜索（换关键词）")
                choice = input("\n请选择: ").strip().lower()
                
                if choice == '' or choice == '1':
                    keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                    while not keyword:
                        p("搜索内容不能为空！", 'y')
                        print("\n选项:")
                        print("  [回车] 重新输入搜索内容")
                        print("  [0] 返回平台选择")
                        print("  [q] 返回主菜单")
                        choice2 = input("\n请选择: ").strip().lower()
                        if choice2 == '0':
                            return
                        elif choice2 == 'q':
                            return None
                        else:
                            keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                    if keyword:
                        page = 1
                        continue
                    else:
                        break
                elif choice == '0':
                    return  # 返回平台选择
                elif choice == 'q':
                    return None  # 返回主菜单
                elif choice == '3' and selected_videos:
                    break
                else:
                    continue
            
            results = result['results']
            results.sort(key=lambda x: -x['play'])
            
            display_search_results(results, page, result['num_pages'])
            
            if selected_videos:
                p(f"\n[提示] 当前已选中 {len(selected_videos)} 个视频", 'c')
                print("  - 输入数字选择视频添加到列表")
                print("  - 输入 'm' 批量添加")
                print("  - 输入 'c' 确认并开始解析")
                print("  - 输入 '0' 返回平台选择")
                print("  - 输入 'q' 返回主菜单")
                print("  - 直接按回车显示操作菜单")
            else:
                print("  - 输入数字选择视频")
                print("  - 输入 'm' 批量添加")
                print("  - 输入 '0' 返回平台选择")
                print("  - 输入 'q' 返回主菜单")
                print("  - 直接按回车显示操作菜单")
            
            # 获取用户输入
            user_choice = input("\n请选择: ").strip().lower()
            
            # 处理返回平台选择
            if user_choice == '0':
                return  # 返回平台选择
            
            # 处理返回主菜单
            if user_choice == 'q':
                if selected_videos:
                    p(f"\n当前已选中 {len(selected_videos)} 个视频，确认退出？", 'y')
                    print("[提示] 直接回车 = 退出")
                    confirm = input("(直接回车退出，输入0取消): ").strip()
                    if confirm == '' or confirm == '1':
                        return None
                    else:
                        continue
                else:
                    return None
            
            # 处理空输入（直接回车）
            if user_choice == '':
                if selected_videos:
                    print("\n" + "=" * 50)
                    p("       操作菜单", 'c')
                    print("=" * 50)
                    print(f"  当前已选中 {len(selected_videos)} 个视频")
                    print("  [1] 继续搜索添加更多视频")
                    print("  [2] 确认并开始解析")
                    print("  [3] 清空所有选择")
                    print("  [0] 返回平台选择")
                    print("  [q] 返回主菜单")
                    print("[提示] 直接回车 = 继续搜索添加更多视频")
                    print("=" * 50)
                    
                    while True:
                        action = input("\n请选择: ").strip().lower()
                        if action == '':
                            action = '1'  # 默认继续搜索
                        elif action == '0':
                            return  # 返回平台选择
                        elif action == 'q':
                            return None  # 返回主菜单
                        elif action == '1':
                            # 继续搜索添加更多视频
                            print("\n" + "=" * 50)
                            p("       继续搜索", 'c')
                            print("=" * 50)
                            print(f"  当前已选中 {len(selected_videos)} 个视频")
                            print("  [1] 使用新关键词搜索")
                            print("  [2] 返回操作菜单（保留已选视频）")
                            print("  [0] 返回平台选择")
                            print("  [q] 返回主菜单")
                            print("[提示] 直接回车 = 使用新关键词搜索")
                            
                            sub_choice = input("\n请选择: ").strip().lower()
                            
                            if sub_choice == '' or sub_choice == '1':
                                keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                                while not keyword:
                                    p("搜索内容不能为空！", 'y')
                                    print("\n选项:")
                                    print("  [回车] 重新输入搜索内容")
                                    print("  [0] 返回平台选择")
                                    print("  [q] 返回主菜单")
                                    print("  [2] 返回操作菜单（保留已选视频）")
                                    choice2 = input("\n请选择: ").strip().lower()
                                    if choice2 == '0':
                                        return
                                    elif choice2 == 'q':
                                        return None
                                    elif choice2 == '2':
                                        # 返回操作菜单，保留已选视频
                                        break
                                    else:
                                        keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                                        if keyword:
                                            break
                                if keyword:
                                    page = 1
                                    break  # 跳出操作菜单循环，开始新搜索
                                else:
                                    # 用户选择返回操作菜单，继续循环
                                    continue
                            elif sub_choice == '2':
                                # 返回操作菜单（保留已选视频）
                                continue
                            elif sub_choice == '0':
                                return
                            elif sub_choice == 'q':
                                return None
                            else:
                                p("无效选项", 'y')
                                continue
                        elif action == '2':
                            # 确认并开始解析
                            break
                        elif action == '3':
                            selected_videos = []
                            p("已清空所有选择", 'y')
                            keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                            while not keyword:
                                p("搜索内容不能为空！", 'y')
                                print("\n选项:")
                                print("  [回车] 重新输入搜索内容")
                                print("  [0] 返回平台选择")
                                print("  [q] 返回主菜单")
                                choice2 = input("\n请选择: ").strip().lower()
                                if choice2 == '0':
                                    return
                                elif choice2 == 'q':
                                    return None
                                else:
                                    keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                            page = 1
                            break
                        else:
                            p("无效选项，请重新输入", 'y')
                            continue
                    
                    # 如果用户选择了确认（action == '2'），跳出外层循环
                    if action == '2':
                        break
                    else:
                        continue
                else:
                    # 没有选中任何视频时，直接回车显示选项
                    p("[提示] 未选择任何视频", 'y')
                    print("\n操作选项:")
                    print("  [1] 重新搜索（输入新关键词）")
                    print("  [0] 返回平台选择")
                    print("  [q] 返回主菜单")
                    print("[提示] 直接回车 = 重新搜索")
                    choice = input("\n请选择: ").strip().lower()
                    
                    if choice == '' or choice == '1':
                        keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                        while not keyword:
                            p("搜索内容不能为空！", 'y')
                            print("\n选项:")
                            print("  [回车] 重新输入搜索内容")
                            print("  [0] 返回平台选择")
                            print("  [q] 返回主菜单")
                            choice2 = input("\n请选择: ").strip().lower()
                            if choice2 == '0':
                                return
                            elif choice2 == 'q':
                                return None
                            else:
                                keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                        page = 1
                        continue
                    elif choice == '0':
                        return
                    elif choice == 'q':
                        return None
                    else:
                        p("无效选项", 'y')
                        continue
            
            if user_choice == 'c':
                if selected_videos:
                    break
                else:
                    p("没有选中任何视频", 'y')
                    continue
            
            elif user_choice == 'm':
                result_count = len(results)
                print(f"\n{'='*50}")
                p("       批量添加视频", 'c')
                print(f"{'='*50}")
                print(f"当前页有 {result_count} 个视频")
                print("输入格式示例:")
                print("  - 单个: 1 3 5")
                print("  - 范围: 1-5")
                print("  - 混合: 1 3-5 7")
                print("  - 全部: all")
                print(f"{'='*50}")
                
                multi_choice = input("\n请输入要选择的视频编号: ").strip()
                if not multi_choice:
                    p("[取消] 已退出", 'y')
                    continue
                
                if multi_choice.lower() == 'all':
                    selected_indices = list(range(result_count))
                else:
                    selected_indices = parse_selection_input(multi_choice, result_count)
                
                if not selected_indices:
                    p("[错误] 没有有效的选择", 'y')
                    continue
                
                new_count = 0
                for idx in selected_indices:
                    video = results[idx]
                    already_selected = False
                    for v in selected_videos:
                        if v['bvid'] == video['bvid']:
                            already_selected = True
                            break
                    if not already_selected:
                        selected_videos.append({
                            'bvid': video['bvid'],
                            'title': video['title']
                        })
                        new_count += 1
                
                p(f"\n已添加 {new_count} 个视频，当前共选中 {len(selected_videos)} 个视频", 'g')
                
                if selected_videos:
                    print("\n当前选中的视频列表:")
                    for i, v in enumerate(selected_videos, 1):
                        title = v['title'][:50] + '...' if len(v['title']) > 50 else v['title']
                        print(f"  {i}. {title}")
                
                print("\n操作选项:")
                print("  [1] 继续搜索添加更多视频")
                print("  [2] 确认并开始解析")
                print("  [3] 清空所有选择并重新开始")
                print("  [0] 返回平台选择")
                print("  [q] 返回主菜单")
                print("[提示] 直接回车 = 继续搜索添加更多视频")
                
                action = input("\n请选择: ").strip().lower()
                
                if action == '' or action == '1':
                    keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                    while not keyword:
                        p("搜索内容不能为空！", 'y')
                        print("\n选项:")
                        print("  [回车] 重新输入搜索内容")
                        print("  [0] 返回平台选择")
                        print("  [q] 返回主菜单")
                        print("  [2] 返回操作菜单（保留已选视频）")
                        choice2 = input("\n请选择: ").strip().lower()
                        if choice2 == '0':
                            return
                        elif choice2 == 'q':
                            return None
                        elif choice2 == '2':
                            break
                        else:
                            keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                            if keyword:
                                break
                    if keyword:
                        page = 1
                        continue
                    else:
                        continue
                elif action == '2':
                    if selected_videos:
                        break
                    else:
                        p("没有选中任何视频", 'y')
                        continue
                elif action == '3':
                    selected_videos = []
                    keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                    while not keyword:
                        p("搜索内容不能为空！", 'y')
                        print("\n选项:")
                        print("  [回车] 重新输入搜索内容")
                        print("  [0] 返回平台选择")
                        print("  [q] 返回主菜单")
                        choice2 = input("\n请选择: ").strip().lower()
                        if choice2 == '0':
                            return
                        elif choice2 == 'q':
                            return None
                        else:
                            keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                    page = 1
                    continue
                elif action == '0':
                    return
                elif action == 'q':
                    return None
                else:
                    p("[错误] 无效选项", 'y')
                    continue
                    
            elif user_choice == key_next:
                if page < result['num_pages']:
                    page += 1
                    continue
                else:
                    p("[提示] 已经是最后一页了", 'y')
                    continue
            elif user_choice == key_prev:
                if page > 1:
                    page -= 1
                    continue
                else:
                    p("[提示] 已经是第一页了", 'y')
                    continue
            
            # 处理数字选择
            elif user_choice.isdigit():
                idx = int(user_choice) - 1
                if 0 <= idx < len(results):
                    selected = results[idx]
                    p(f'\n[选中] {selected["title"]}', 'g')
                    
                    already = False
                    for v in selected_videos:
                        if v['bvid'] == selected['bvid']:
                            already = True
                            break
                    
                    if already:
                        p("该视频已经在选择列表中", 'y')
                        if selected_videos:
                            print(f"\n当前已选中 {len(selected_videos)} 个视频")
                            print("  [1] 继续搜索添加更多")
                            print("  [2] 确认并开始解析")
                            print("  [0] 返回平台选择")
                            print("  [q] 返回主菜单")
                            print("[提示] 直接回车 = 继续搜索添加更多")
                            choice = input("\n请选择: ").strip().lower()
                            if choice == '' or choice == '1':
                                keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                                while not keyword:
                                    p("搜索内容不能为空！", 'y')
                                    print("\n选项:")
                                    print("  [回车] 重新输入搜索内容")
                                    print("  [0] 返回平台选择")
                                    print("  [q] 返回主菜单")
                                    print("  [2] 返回操作菜单（保留已选视频）")
                                    choice2 = input("\n请选择: ").strip().lower()
                                    if choice2 == '0':
                                        return
                                    elif choice2 == 'q':
                                        return None
                                    elif choice2 == '2':
                                        break
                                    else:
                                        keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                                        if keyword:
                                            break
                                if keyword:
                                    page = 1
                                    continue
                                else:
                                    continue
                            elif choice == '2':
                                break
                            elif choice == '0':
                                return
                            elif choice == 'q':
                                return None
                            else:
                                continue
                        else:
                            continue
                    else:
                        selected_videos.append({'bvid': selected['bvid'], 'title': selected['title']})
                        p(f"已添加，当前共选中 {len(selected_videos)} 个视频", 'g')
                        
                        print("\n当前选中的视频列表:")
                        for i, v in enumerate(selected_videos, 1):
                            title = v['title'][:50] + '...' if len(v['title']) > 50 else v['title']
                            print(f"  {i}. {title}")
                        
                        print("\n操作选项:")
                        print("  [1] 继续搜索添加更多视频")
                        print("  [2] 确认并开始解析")
                        print("  [3] 取消(返回搜索结果)")
                        print("  [0] 返回平台选择")
                        print("  [q] 返回主菜单")
                        print("[提示] 直接回车 = 继续搜索添加更多视频")
                        
                        action = input("\n请选择: ").strip().lower()
                        
                        if action == '' or action == '1':
                            keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                            while not keyword:
                                p("搜索内容不能为空！", 'y')
                                print("\n选项:")
                                print("  [回车] 重新输入搜索内容")
                                print("  [0] 返回平台选择")
                                print("  [q] 返回主菜单")
                                print("  [2] 返回操作菜单（保留已选视频）")
                                choice2 = input("\n请选择: ").strip().lower()
                                if choice2 == '0':
                                    return
                                elif choice2 == 'q':
                                    return None
                                elif choice2 == '2':
                                    break
                                else:
                                    keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                                    if keyword:
                                        break
                            if keyword:
                                page = 1
                                continue
                            else:
                                continue
                        elif action == '2':
                            break
                        elif action == '3':
                            continue
                        elif action == '0':
                            return
                        elif action == 'q':
                            return None
                        else:
                            continue
                else:
                    p(f"[错误] 请输入 1-{len(results)} 之间的数字", 'y')
                    continue
            else:
                if selected_videos:
                    p("[提示] 无效输入，请输入数字、'm'(多选)、'c'(确认)、'0'(返回平台选择)、'q'(返回主菜单)或按回车", 'y')
                else:
                    p("[提示] 无效输入，请输入数字、'm'(多选)、'0'(返回平台选择)、'q'(返回主菜单)或按回车", 'y')
                continue
        
        # 跳出搜索循环后，如果没有选中视频则返回
        if not selected_videos:
            p('[取消] 未选择视频', 'y')
            return
        
        # 显示已选中的视频列表并选择处理模式
        while True:
            p(f'\n{"="*50}', 'm')
            p(f'       已选中 {len(selected_videos)} 个视频', 'g')
            print('=' * 50)
            for i, video in enumerate(selected_videos, 1):
                title = video['title'][:50] + '...' if len(video['title']) > 50 else video['title']
                print(f'  {i}. {title}')
            print('=' * 50)
            
            mode = show_video_mode_menu()
            
            if mode is None:
                p('[取消] 已返回主菜单', 'y')
                return
            
            print("\n[提示] 直接回车 = 开始处理")
            if input('\n开始处理? (直接回车=是, 输入0取消): ').strip() in ['', '1', '是', 'yes', 'y']:
                success = 0
                fail = 0
                for video in selected_videos:
                    video_url = f"https://www.bilibili.com/video/{video['bvid']}"
                    if process_single_video(video_url, mode):
                        success += 1
                    else:
                        fail += 1
                p(f'\n[完成] 成功: {success}  失败: {fail}', 'g')
                p(f'保存位置: {DOWNLOAD_PATH}', 'c')
                input("\n按回车键返回主菜单...")
                return
            else:
                p('[取消] 已取消处理', 'y')
                continue

# ==================== 设置功能 ====================

def settings_menu():
    """设置菜单"""
    config = load_config()
    
    while True:
        print("\n" + "=" * 50)
        p("       设置", 'c')
        print("=" * 50)
        print("  [1] 设置启动快捷命令")
        print("  [2] 设置翻页快捷键")
        print("  [0] 返回主菜单")
        print("[提示] 直接回车返回主菜单")
        print("=" * 50)
        
        choice = input("\n请选择 [0-2] 或直接回车: ").strip()
        
        # 处理直接回车
        if choice == '':
            return
        
        if choice == '0':
            return
        elif choice == '1':
            print("\n" + "=" * 50)
            p("       设置启动快捷命令", 'c')
            print("=" * 50)
            print(f"当前快捷命令: {config.get('shortcut_command', 'run')}")
            print("\n说明：在命令行中输入此命令即可直接启动脚本")
            print("示例：run、start、dl、下载器、mydl 等")
            print("注意：")
            print("  - 必须使用字母开头，不能是纯数字")
            print("  - 不能包含空格")
            print("  - 推荐使用简短易记的名称")
            print("=" * 50)
            
            print("\n操作选项:")
            print("  [1] 设置新的快捷命令")
            print("  [2] 删除当前快捷命令")
            print("  [0] 返回")
            sub_choice = input("\n请选择 [0-2] 或直接回车返回: ").strip()
            
            if sub_choice == '' or sub_choice == '0':
                continue
            elif sub_choice == '2':
                # 删除快捷命令
                old_cmd = config.get('shortcut_command', 'run')
                if old_cmd:
                    # 删除批处理文件
                    bat_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), f"{old_cmd}.bat")
                    if os.path.exists(bat_path):
                        try:
                            os.remove(bat_path)
                            p(f"已删除快捷方式: {old_cmd}.bat", 'g')
                        except:
                            p(f"无法删除快捷方式: {old_cmd}.bat", 'y')
                    
                    config['shortcut_command'] = 'run'
                    save_config(config)
                    p(f"快捷命令已重置为: run", 'g')
                else:
                    p("没有可删除的快捷命令", 'y')
                input("\n按回车键继续...")
                continue
            elif sub_choice == '1':
                new_cmd = input("\n请输入新的快捷命令 (直接回车保持不变): ").strip()
                if not new_cmd:
                    p("未作修改", 'y')
                    input("\n按回车键继续...")
                    continue
                
                if ' ' in new_cmd:
                    p("快捷命令不能包含空格！", 'r')
                    input("\n按回车键继续...")
                    continue
                
                # 检查是否为纯数字
                if new_cmd.isdigit():
                    p("错误：不能使用纯数字作为命令！", 'r')
                    p("Windows 命令提示符无法识别纯数字命令", 'y')
                    p("请使用字母开头的命令，如：dl、mydl、video 等", 'y')
                    input("\n按回车键继续...")
                    continue
                
                # 检查是否以数字开头
                if new_cmd[0].isdigit():
                    p("警告：命令以数字开头，可能无法正常工作", 'y')
                    p("建议使用字母开头，如：dl、mydl、video 等", 'y')
                    confirm = input("仍要继续使用？(输入 yes 确认): ").strip().lower()
                    if confirm != 'yes':
                        p("已取消设置", 'y')
                        input("\n按回车键继续...")
                        continue
                
                # 删除旧的快捷命令文件
                old_cmd = config.get('shortcut_command', 'run')
                if old_cmd:
                    old_bat = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), f"{old_cmd}.bat")
                    if os.path.exists(old_bat) and old_cmd != new_cmd:
                        try:
                            os.remove(old_bat)
                        except:
                            pass
                
                config['shortcut_command'] = new_cmd
                if save_config(config):
                    p(f"快捷命令已设置为: {new_cmd}", 'g')
                    print(f"\n使用方法：在命令行中输入 {new_cmd} 即可启动脚本")
                    
                    # 创建批处理文件
                    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                    bat_path = os.path.join(script_dir, f"{new_cmd}.bat")
                    with open(bat_path, 'w', encoding='utf-8') as f:
                        f.write(f'@echo off\npython "{sys.argv[0]}" %*\n')
                    
                    p(f"已创建快捷方式: {bat_path}", 'g')
                    
                    # 自动添加到 PATH
                    try:
                        import winreg
                        # 获取当前用户 PATH
                        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
                        try:
                            current_path, _ = winreg.QueryValueEx(key, "Path")
                        except:
                            current_path = ""
                        
                        # 检查是否已存在
                        if script_dir not in current_path:
                            # 添加到 PATH
                            new_path = f"{current_path};{script_dir}" if current_path else script_dir
                            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                            winreg.CloseKey(key)
                            
                            # 广播环境变量更新
                            HWND_BROADCAST = 0xFFFF
                            WM_SETTINGCHANGE = 0x001A
                            import ctypes
                            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")
                            
                            p("\n✅ 已自动将 D:\\termux 添加到系统 PATH！", 'g')
                            p("现在可以直接在命令行中输入命令名启动脚本了", 'g')
                            print("提示：如果当前命令行窗口无法识别，请重新打开命令行窗口")
                        else:
                            p("\n[提示] 当前目录已在 PATH 中，可以直接使用命令", 'g')
                    except Exception as e:
                        p(f"\n[提示] 自动添加到 PATH 失败: {e}", 'y')
                        print("请手动添加以下路径到系统环境变量：")
                        print(f"  {script_dir}")
                        print("或直接运行 bat 文件")
                else:
                    p("保存配置失败", 'r')
                
                input("\n按回车键继续...")
            else:
                p("无效选项", 'y')
                continue
        elif choice == '2':
            print("\n" + "=" * 50)
            p("       设置翻页快捷键", 'c')
            print("=" * 50)
            print(f"当前上一页键: {config.get('key_prev', 'a')}")
            print(f"当前下一页键: {config.get('key_next', 'd')}")
            print("\n说明：在搜索视频结果页面使用这些键进行翻页")
            print("示例：w/s、up/down、j/k 等")
            print("=" * 50)
            
            new_prev = input("\n请输入新的上一页键 (直接回车保持不变): ").strip()
            if new_prev:
                if len(new_prev) > 1:
                    p("快捷键只能是单个字符！", 'r')
                else:
                    config['key_prev'] = new_prev.lower()
                    p(f"上一页键已设置为: {new_prev}", 'g')
            
            new_next = input("请输入新的下一页键 (直接回车保持不变): ").strip()
            if new_next:
                if len(new_next) > 1:
                    p("快捷键只能是单个字符！", 'r')
                else:
                    config['key_next'] = new_next.lower()
                    p(f"下一页键已设置为: {new_next}", 'g')
            
            if new_prev or new_next:
                if save_config(config):
                    p("快捷键设置已保存", 'g')
                else:
                    p("保存配置失败", 'r')
            
            input("\n按回车键继续...")
        else:
            p("无效选项，请重新输入", 'y')

# ==================== 主菜单 ====================

def show_main_menu():
    print('\n' + '=' * 50)
    p('       主菜单', 'c')
    print('=' * 50)
    print('  [1] 开始下载视频')
    print('  [2] 搜索视频')
    print('  [3] MP3封面批量管理')
    print('  [4] 手动替换单个MP3封面')
    print('  [5] 粘贴歌单网页内容（自动提取歌名并批量下载）')
    print('  [6] 检查更新')
    print('  [7] 卸载工具')
    print('  [8] 退出')
    print('  [9] 设置')
    print('=' * 50)

def main():
    check_for_updates_auto()
    check_dependencies()
    
    report_stats("start")
    display_stats()
    
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    p(f'[路径] 保存目录: {DOWNLOAD_PATH}', 'c')
    
    while True:
        show_main_menu()
        
        main_choice = input('\n请选择 [1-9]: ').strip()
        
        if main_choice == '8':
            p('再见!', 'm')
            break
        
        if main_choice == '9':
            settings_menu()
            continue
        
        if main_choice == '5':
            process_copied_playlist()
            continue
        
        if main_choice == '3':
            batch_add_mp3_covers()
            continue
        
        if main_choice == '4':
            manual_replace_mp3_cover()
            continue
        
        if main_choice == '6':
            check_for_updates()
            continue
        
        if main_choice == '7':
            show_uninstall_menu()
            uninstall_choice = input('\n请选择 [1/2/3/4]: ').strip()
            if uninstall_choice == '1':
                uninstall_videos()
            elif uninstall_choice == '2':
                uninstall_tool_only()
            elif uninstall_choice == '3':
                uninstall_everything()
            continue
        
        if main_choice == '2':
            search_videos()
            continue
        
        if main_choice != '1':
            p('无效选项，请重新选择', 'y')
            continue
        
        print()
        inp = input('输入视频链接 (多个空格分隔，支持B站/抖音/快手等): ').strip()
        
        if not inp:
            p('未输入链接!', 'y')
            continue
        
        urls = extract_urls_from_input(inp)
        
        if not urls:
            p('未检测到有效链接!', 'y')
            continue
        
        p(f'\n找到 {len(urls)} 个视频（已自动去重）:', 'c')
        for i, u in enumerate(urls, 1):
            display_url = u if len(u) <= 60 else u[:57] + '...'
            print(f'  {i}. {display_url}')
        
        global_mode = show_global_menu()
        
        if global_mode == 4:
            print('\n[选择部分模式]')
            print('  - 输入 "1,3,4" 处理第1、3、4个')
            print('  - 输入 "1-3" 处理第1到3个')
            print('  - 输入 "all" 处理全部')
            
            selection = input(f'\n请输入要处理的序号 (1-{len(urls)}): ').strip()
            
            if not selection:
                p('[取消]', 'y')
                continue
            
            if selection.lower() == 'all':
                selected_indices = list(range(len(urls)))
            else:
                selected_indices = parse_selection_input(selection, len(urls))
                if not selected_indices:
                    p('[错误] 无效格式', 'y')
                    continue
            
            p(f'\n已选择 {len(selected_indices)} 个视频', 'c')
            print("[提示] 直接回车 = 开始处理")
            if input('\n开始处理? (直接回车=是, 输入0=否): ').strip() in ['', '1']:
                success = fail = 0
                for idx in selected_indices:
                    url = urls[idx]
                    p(f'\n>>> 处理第 {idx+1} 个:', 'c')
                    print('  [1] 仅MP4  [2] 仅MP3(带封面)  [3] 都要(MP3带封面)')
                    video_mode = input('请选择 [1/2/3]: ').strip()
                    while video_mode not in ['1', '2', '3']:
                        video_mode = input('请选择 [1/2/3]: ').strip()
                    
                    if process_single_video(url, int(video_mode)):
                        success += 1
                    else:
                        fail += 1
                
                p(f'\n完成! 成功: {success}  失败: {fail}', 'm')
            else:
                p('[取消]', 'y')
                continue
            
        else:
            print("[提示] 直接回车 = 开始处理")
            if input('\n开始处理? (直接回车=是, 输入0=否): ').strip() in ['', '1']:
                success, fail = process_multiple_videos(urls, global_mode)
                
                p(f'\n{"="*50}', 'm')
                p(f'完成! 成功: {success}  失败: {fail}', 'm')
                mode_text = {1: 'MP4', 2: 'MP3(带封面)', 3: 'MP4+MP3(MP3带封面)'}.get(global_mode, '')
                p(f'处理模式: {mode_text}', 'c')
            else:
                p('[取消]', 'y')
                continue
        
        p(f'保存位置: {DOWNLOAD_PATH}', 'c')
        print('=' * 50)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        p('\n[已取消] 用户中断', 'y')
    except Exception as e:
        p(f'\n[错误] {e}', 'r')
        input('\n按回车键退出...')