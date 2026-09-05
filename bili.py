#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import os
import sys
import time
import json
import subprocess
import threading
import platform
import socket
import hashlib
import io
import shutil
import urllib.parse
import base64
from typing import List, Dict, Optional
from PIL import Image
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error

os.environ['LANG'] = 'zh_CN.UTF-8'
os.environ['LC_ALL'] = 'zh_CN.UTF-8'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

VERSION = "11.01"

SCRIPT_PATH = os.path.abspath(sys.argv[0])

# 默认下载路径
DEFAULT_DOWNLOAD_PATH = "/storage/emulated/0/Download/termux/"
DOWNLOAD_PATH = DEFAULT_DOWNLOAD_PATH
API_URL = "https://api.yuafeng.cn/API/spjx/api.php"
STATS_API_URL = "http://mzrl.xn--4gqq11cba.xn--czrs0t/%E7%9B%B4%E9%93%BE%E8%A7%A3%E6%9E%90/zljx.php"
UPDATE_URL = "http://mzrl.xn--4gqq11cba.xn--czrs0t/%E7%9B%B4%E9%93%BE%E8%A7%A3%E6%9E%90/zljx.php?api=get_content&download=1&file=termux.txt"

CONFIG_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), ".downloader_config.json")
PROGRESS_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), ".download_progress.json")
FAILED_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), ".failed_downloads.json")
UNFINISHED_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), ".unfinished_tasks.json")

# ==================== 配置加载 ====================

def load_config():
    default_config = {
        "shortcut_command": "run",
        "key_next": "d",
        "key_prev": "a",
        "key_goto": "g",
        "debug_mode": False,
        "download_path": DEFAULT_DOWNLOAD_PATH,
        "skip_existing": True,
        "cover_mode": "api",
        "cover_crop": "center",
        "mp3_cover_enabled": True,
        "mp3_lyric_enabled": True,
        "mp3_lyric_source": "netease",
        "mp3_cover_source": "api",
        "progress_bar_style": "modern",
        "max_parse_retries": 5,  # 新增：最大解析重试次数，默认5次
        "lrc_apis": {
            'netease': {'enabled': True, 'priority': 1},
            'bilibili': {'enabled': True, 'priority': 2},
            'qqmusic': {'enabled': True, 'priority': 3},
            'musixmatch': {'enabled': True, 'priority': 4},
            'lrclib': {'enabled': True, 'priority': 5}
        },
        "lyric_enhance": {
            'enabled': True,
            'romaji': True,
            'translation': True
        }
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                if 'lrc_apis' not in config:
                    config['lrc_apis'] = default_config['lrc_apis']
                else:
                    for key, val in default_config['lrc_apis'].items():
                        if key not in config['lrc_apis']:
                            config['lrc_apis'][key] = val
                        if 'enabled' not in config['lrc_apis'][key]:
                            config['lrc_apis'][key]['enabled'] = val['enabled']
                        if 'priority' not in config['lrc_apis'][key]:
                            config['lrc_apis'][key]['priority'] = val['priority']
                if 'lyric_enhance' not in config:
                    config['lyric_enhance'] = default_config['lyric_enhance']
                else:
                    for key, val in default_config['lyric_enhance'].items():
                        if key not in config['lyric_enhance']:
                            config['lyric_enhance'][key] = val
                if 'progress_bar_style' not in config:
                    config['progress_bar_style'] = default_config['progress_bar_style']
                if 'max_parse_retries' not in config:  # 新增：兼容旧配置
                    config['max_parse_retries'] = default_config['max_parse_retries']
                return config
    except:
        pass
    return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

# ==================== 未完成任务管理（完整版） ====================

import time
import json
import os
from datetime import datetime

def load_unfinished_tasks():
    """加载未完成的任务"""
    try:
        if os.path.exists(UNFINISHED_FILE):
            with open(UNFINISHED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'tasks': []}

def save_unfinished_task(task_data):
    """保存未完成的任务"""
    try:
        data = load_unfinished_tasks()
        # 检查是否已存在相同ID的任务
        for i, task in enumerate(data['tasks']):
            if task.get('id') == task_data.get('id'):
                data['tasks'][i] = task_data
                with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
        data['tasks'].append(task_data)
        with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def remove_unfinished_task(task_id):
    """移除已完成的任务"""
    try:
        data = load_unfinished_tasks()
        data['tasks'] = [t for t in data['tasks'] if t.get('id') != task_id]
        with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def get_unfinished_tasks():
    """获取所有未完成的任务"""
    data = load_unfinished_tasks()
    return data.get('tasks', [])

def create_task_id():
    """创建任务ID"""
    return f"task_{int(time.time())}_{os.urandom(4).hex()}"

def create_unfinished_task(urls, mode, url_info, task_name=None):
    """创建未完成任务记录"""
    if task_name is None:
        task_name = f"下载任务_{len(urls)}个视频"
    
    task_data = {
        'id': create_task_id(),
        'name': task_name,
        'type': '视频下载',
        'urls': urls,
        'mode': mode,
        'url_info': url_info,
        'completed': 0,
        'total': len(urls),
        'current_index': 0,
        'current_file': '',
        'current_progress': '0%',
        'remaining': len(urls),
        'status': 'downloading',  # downloading, paused, completed
        'start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'last_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'failed_count': 0
    }
    save_unfinished_task(task_data)
    return task_data

def update_unfinished_task_progress(task_id, completed, total, current_file='', current_progress='', status='downloading'):
    """更新任务进度"""
    try:
        data = load_unfinished_tasks()
        for i, task in enumerate(data['tasks']):
            if task.get('id') == task_id:
                task['completed'] = completed
                task['total'] = total
                task['remaining'] = total - completed
                if current_file:
                    task['current_file'] = current_file
                if current_progress:
                    task['current_progress'] = current_progress
                task['status'] = status
                task['last_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
                with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
    except:
        pass
    return False

def mark_task_completed(task_id):
    """标记任务为已完成"""
    try:
        data = load_unfinished_tasks()
        for i, task in enumerate(data['tasks']):
            if task.get('id') == task_id:
                task['status'] = 'completed'
                task['completed'] = task['total']
                task['remaining'] = 0
                task['last_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
                with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                # 自动删除已完成的任务
                remove_unfinished_task(task_id)
                return True
    except:
        pass
    return False


def show_scan_progress(message, current, total):
    """显示扫描进度"""
    if total <= 0:
        return
    bar_length = 20
    percent = current / total * 100
    filled = int(bar_length * percent // 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    sys.stderr.write("\r[扫描] {} {} {:.0f}%".format(message, bar, percent))
    sys.stderr.flush()
def scan_tmp_files():
    """扫描下载目录中的.tmp文件，生成未完成任务（带进度）"""
    download_path = get_download_path()
    tmp_files = []
    
    if not os.path.exists(download_path):
        return []
    
    # 先统计总文件数
    total_files = 0
    for root, dirs, files in os.walk(download_path):
        total_files += len(files)
    
    if total_files == 0:
        return []
    
    scanned = 0
    for root, dirs, files in os.walk(download_path):
        for file in files:
            scanned += 1
            # 每扫描50个文件显示一次进度
            if scanned % 50 == 0:
                show_scan_progress(f"扫描文件 ({scanned}/{total_files})", scanned, total_files)
            
            if file.endswith('.tmp'):
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path) / 1024 / 1024
                mtime = os.path.getmtime(file_path)
                mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
                original_name = file.replace('.tmp', '')
                
                # 检查是否有对应的元数据文件
                meta_path = file_path.replace('.tmp', '.meta')
                has_meta = os.path.exists(meta_path)
                meta_info = None
                if has_meta:
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta_info = json.load(f)
                    except:
                        pass
                
                tmp_files.append({
                    'file': file_path,
                    'name': original_name,
                    'size_mb': round(size, 2),
                    'mtime': mtime_str,
                    'folder': os.path.dirname(file_path),
                    'has_meta': has_meta,
                    'meta_info': meta_info
                })
    
    # 清除进度行
    sys.stderr.write('\r' + ' ' * 80 + '\r')
    sys.stderr.flush()
    
    return tmp_files

def detect_unfinished_tasks():
    """检测所有未完成的任务（包括.tmp文件）"""
    tasks = []
    
    # 1. 从JSON文件加载任务
    json_tasks = get_unfinished_tasks()
    tasks.extend(json_tasks)
    
    # 2. 扫描.tmp文件
    tmp_files = scan_tmp_files()
    if tmp_files:
        # 检查是否已有对应的任务
        existing_tmp_task = False
        for task in tasks:
            if task.get('is_tmp_task', False):
                existing_tmp_task = True
                # 更新tmp文件列表
                task['tmp_files'] = tmp_files
                task['total'] = len(tmp_files)
                task['remaining'] = len(tmp_files)
                task['last_time'] = tmp_files[0]['mtime'] if tmp_files else time.strftime('%Y-%m-%d %H:%M:%S')
                task['current_file'] = tmp_files[0]['name'] if tmp_files else ''
                task['current_progress'] = f"{tmp_files[0]['size_mb']}MB" if tmp_files else '0%'
                # 检查是否有元数据
                has_meta = any(tf.get('has_meta', False) for tf in tmp_files)
                task['has_meta'] = has_meta
                break
        
        if not existing_tmp_task:
            # 检查是否有元数据
            has_meta = any(tf.get('has_meta', False) for tf in tmp_files)
            
            tmp_task = {
                'id': f'tmp_task_{int(time.time())}',
                'name': f'未完成的下载文件 ({len(tmp_files)}个)',
                'type': '临时文件',
                'tmp_files': tmp_files,
                'is_tmp_task': True,
                'urls': [],
                'mode': 2,
                'url_info': {},
                'completed': 0,
                'total': len(tmp_files),
                'current_index': 0,
                'current_file': tmp_files[0]['name'] if tmp_files else '',
                'current_progress': f"{tmp_files[0]['size_mb']}MB" if tmp_files else '0%',
                'remaining': len(tmp_files),
                'status': 'paused',
                'start_time': tmp_files[0]['mtime'] if tmp_files else time.strftime('%Y-%m-%d %H:%M:%S'),
                'last_time': tmp_files[0]['mtime'] if tmp_files else time.strftime('%Y-%m-%d %H:%M:%S'),
                'failed_count': 0,
                'folder': tmp_files[0]['folder'] if tmp_files else '',
                'has_meta': has_meta
            }
            tasks.append(tmp_task)
    
    return tasks

def get_unfinished_tasks_enhanced():
    """获取所有未完成的任务（增强版）"""
    return detect_unfinished_tasks()

def show_unfinished_tasks_menu():
    """显示未完成任务菜单（带扫描进度）"""
    p("[扫描] 正在扫描未完成的任务...", "c")
    
    print("\n" + "=" * 50)
    p("       扫描进度", "c")
    print("=" * 50)
    
    p("[1/2] 正在检查已保存的任务...", "y")
    json_tasks = get_unfinished_tasks()
    if json_tasks:
        p(f"      ✓ 发现 {len(json_tasks)} 个已保存的任务", "g")
    else:
        p("      ✓ 没有已保存的任务", "y")
    time.sleep(0.3)
    
    p("[2/2] 正在扫描临时文件...", "y")
    tmp_files = scan_tmp_files()
    if tmp_files:
        p(f"      ✓ 发现 {len(tmp_files)} 个临时文件", "g")
    else:
        p("      ✓ 没有临时文件", "y")
    time.sleep(0.3)
    
    tasks = get_unfinished_tasks_enhanced()
    
    print("=" * 50)
    p("       扫描完成", "g")
    print("=" * 50)
    
    if not tasks:
        p("[信息] 没有未完成的任务", "y")
        input("\n按回车键返回...")
        return
    
    print("\n" + "=" * 60)
    p("       未完成的任务", "c")
    print("=" * 60)
    
    for i, task in enumerate(tasks, 1):
        task_id = task.get("id", f"task_{i}")
        task_name = task.get("name", "未知任务")
        task_type = task.get("type", "未知类型")
        current_file = task.get("current_file", "无")
        current_progress = task.get("current_progress", "0%")
        remaining = task.get("remaining", "未知")
        last_time = task.get("last_time", "未知")
        url_count = task.get("total", 0)
        completed = task.get("completed", 0)
        status = task.get("status", "unknown")
        
        is_tmp = task.get("is_tmp_task", False)
        tmp_files = task.get("tmp_files", [])
        
        status_text = {"downloading": "⏳ 下载中", "paused": "⏸ 已暂停", "completed": "✅ 已完成", "unknown": "❓ 未知"}.get(status, "❓ 未知")
        
        print(f"  [{i}] {task_name}")
        if is_tmp:
            print(f"     类型: 【临时文件】 | 状态: {status_text}")
            print(f"     文件数量: {len(tmp_files)} 个")
            print(f"     下载进度: {current_progress}")
            print(f"     文件位置: {task.get('folder', '未知')}")
            # 检查是否有元数据
            has_meta = task.get('has_meta', False)
            if has_meta:
                p(f"     📦 可续传: 是 (有元数据)", 'g')
                # 显示原始URL（截断显示）
                for tf in tmp_files:
                    if tf.get('has_meta', False) and tf.get('meta_info'):
                        url = tf['meta_info'].get('url', '')
                        if url:
                            p(f"     🔗 原始URL: {url[:60]}...", 'c')
                            break
            else:
                p(f"     ❌ 可续传: 否 (无元数据)", 'y')
            print(f"     最后更新: {last_time}")
        else:
            print(f"     类型: {task_type} | 状态: {status_text} | 总进度: {completed}/{url_count}")
            print(f"     当前文件: {current_file}")
            print(f"     下载进度: {current_progress}")
            print(f"     剩余: {remaining} 个文件")
            print(f"     最后更新: {last_time}")
        print("-" * 56)
    
    print("=" * 60)
    print("操作说明:")
    print("  输入数字选择单个任务继续")
    print("  输入 'm' 进入多选模式")
    print("  输入 'a' 继续所有任务")
    print("  输入 'd' 删除所有已完成的任务")
    print("  输入 't' 清理所有.tmp临时文件")
    print("  输入 'q' 返回主菜单")
    print("=" * 60)
    
    choice = input("\n请选择: ").strip().lower()
    
    if choice in ("q", "0"):
        return
    elif choice == "a":
        for task in tasks:
            continue_unfinished_task_enhanced(task)
        input("\n按回车键返回...")
    elif choice == "d":
        completed_tasks = [t for t in tasks if t.get("status") == "completed" or (t.get("completed", 0) >= t.get("total", 0) and not t.get("is_tmp_task", False))]
        if completed_tasks:
            for task in completed_tasks:
                remove_unfinished_task(task.get("id"))
            p(f"已删除 {len(completed_tasks)} 个已完成的任务", "g")
        else:
            p("没有已完成的任务", "y")
        input("\n按回车键返回...")
    elif choice == "t":
        tmp_files = scan_tmp_files()
        if tmp_files:
            print(f"\n发现 {len(tmp_files)} 个临时文件:")
            for f in tmp_files:
                has_meta = f.get('has_meta', False)
                meta_status = "📦 有元数据" if has_meta else "❌ 无元数据"
                print(f"  - {f['file']} ({f['size_mb']}MB) {meta_status}")
            confirm = input("\n确认删除所有.tmp文件？(直接回车=是, 输入0=否): ").strip()
            if confirm == "" or confirm == "1":
                deleted = 0
                for f in tmp_files:
                    try:
                        os.remove(f["file"])
                        # 同时删除对应的元数据文件
                        meta_path = f["file"] + '.meta'
                        if os.path.exists(meta_path):
                            os.remove(meta_path)
                        deleted += 1
                    except:
                        pass
                p(f"已删除 {deleted} 个临时文件", "g")
            else:
                p("[取消]", "y")
        else:
            p("没有临时文件", "y")
        input("\n按回车键返回...")
    elif choice == "m":
        print("\n请输入要选择的任务序号，用空格分隔")
        print("格式示例: 1 3 5 或 1-3")
        multi_choice = input("请输入: ").strip()
        if not multi_choice:
            p("[取消] 已退出", "y")
            return
        selected_indices = parse_selection_input(multi_choice, len(tasks))
        if not selected_indices:
            p("[错误] 没有有效的选择", "r")
            return
        for idx in selected_indices:
            if 0 <= idx < len(tasks):
                continue_unfinished_task_enhanced(tasks[idx])
        input("\n按回车键返回...")
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(tasks):
            continue_unfinished_task_enhanced(tasks[idx])
        else:
            p("无效选择", "y")
        input("\n按回车键返回...")
    else:
        p("无效选项", "y")
        input("\n按回车键返回...")
def continue_unfinished_task_enhanced(task):
    """继续未完成的任务（增强版）"""
    # 检查是否是tmp任务
    if task.get('is_tmp_task', False):
        continue_tmp_files(task)
        return
    
    task_id = task.get('id')
    task_name = task.get('name', '未知任务')
    urls = task.get('urls', [])
    mode = task.get('mode', 2)
    url_info = task.get('url_info', {})
    completed = task.get('completed', 0)
    
    p(f'\n[继续任务] {task_name}', 'c')
    p(f'[信息] 已完成 {completed}/{len(urls)} 个，继续下载剩余...', 'c')
    
    # 检查是否保存了 video_url
    has_video_url = False
    for url in urls[completed:]:
        if url in url_info and url_info[url].get('video_url'):
            has_video_url = True
            break
    
    if has_video_url:
        p('[信息] 找到已保存的视频地址，直接续传', 'g')
    else:
        p('[信息] 未找到视频地址，需要重新解析', 'y')
    
    # 从当前进度继续
    remaining_urls = urls[completed:]
    success, fail = process_selected_videos(remaining_urls, mode, url_info, task_id)
    
    total_processed = completed + success + fail
    if total_processed >= len(urls):
        mark_task_completed(task_id)
        p(f'[完成] 任务 {task_name} 已完成', 'g')
    else:
        task['completed'] = completed + success
        task['remaining'] = len(urls) - task['completed']
        task['last_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_unfinished_task(task)
        p(f'[更新] 任务进度更新: {task["completed"]}/{len(urls)}', 'y')

def continue_tmp_files(task):
    """继续下载.tmp文件（支持真正续传）"""
    tmp_files = task.get('tmp_files', [])
    
    if not tmp_files:
        p('[信息] 没有临时文件需要处理', 'y')
        return
    
    p(f'\n[继续] 处理 {len(tmp_files)} 个临时文件...', 'c')
    
    success_count = 0
    fail_count = 0
    
    for tmp_file_info in tmp_files:
        tmp_path = tmp_file_info['file']
        original_name = tmp_file_info['name']
        
        # 修复文件名中可能包含的换行符
        original_name = original_name.replace('\n', '').replace('\r', '')
        
        # ★★★ 修复：正确处理文件名，去除多余的 .mp4 后缀 ★★★
        if original_name.endswith('.mp4.mp4'):
            original_name = original_name[:-4]  # 去掉一个 .mp4
        elif original_name.endswith('.mp4.mp4.mp4'):
            original_name = original_name[:-8]  # 去掉两个 .mp4
        
        base_name = os.path.splitext(original_name)[0]
        folder = os.path.dirname(tmp_path)
        
        # ★★★ 修复：如果 base_name 为空，使用 original_name ★★★
        if not base_name:
            base_name = original_name
        
        mp4_path = os.path.join(folder, f'{base_name}.mp4')
        mp3_path = os.path.join(folder, f'{base_name}.mp3')
        
        # 检查是否已完成
        if os.path.exists(mp4_path) or os.path.exists(mp3_path):
            p(f'\n[跳过] 文件已存在: {original_name}', 'y')
            try:
                os.remove(tmp_path)
                meta_path = tmp_path.replace('.tmp', '.meta')
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                p(f'[清理] 已删除临时文件', 'y')
            except:
                pass
            success_count += 1
            continue
        
        # ★★★ 修复：元数据路径使用 replace ★★★
        meta_path = tmp_path.replace('.tmp', '.meta')
        video_url = None
        title_from_meta = None
        
        p(f'\n[检查] 查找元数据: {os.path.basename(meta_path)}', 'c')
        
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    video_url = meta.get('url')
                    title_from_meta = meta.get('title', original_name)
                    p(f'\n[恢复] ✅ 找到下载元数据', 'g')
                    p(f'[信息] 文件: {title_from_meta}', 'y')
                    if video_url:
                        p(f'[信息] 原始URL: {video_url[:60]}...', 'c')
            except Exception as e:
                p(f'[警告] 读取元数据失败: {e}', 'y')
        else:
            p(f'[信息] 未找到元数据文件', 'y')
        
        if video_url:
            p(f'\n[续传] {original_name} ({tmp_file_info["size_mb"]}MB)', 'c')
            
            # ★★★ 使用 original_name 作为标题，避免重复添加 .mp4 ★★★
            result = download_file(video_url, original_name, folder)
            
            if result:
                p(f'[完成] ✅ 下载成功: {original_name}', 'g')
                success_count += 1
                try:
                    if os.path.exists(meta_path):
                        os.remove(meta_path)
                except:
                    pass
            else:
                p(f'[失败] ❌ 续传失败: {original_name}', 'r')
                fail_count += 1
        else:
            # 没有元数据，无法恢复
            p(f'\n[错误] 无法恢复下载: {original_name}', 'r')
            p(f'[提示] 元数据文件不存在，无法获取原始URL', 'y')
            p(f'[建议] 删除临时文件: {tmp_path}', 'y')
            
            choice = input(f'\n是否删除此临时文件？(直接回车=是, 输入0=否): ').strip()
            if choice == '' or choice == '1':
                try:
                    os.remove(tmp_path)
                    meta_path = tmp_path.replace('.tmp', '.meta')
                    if os.path.exists(meta_path):
                        os.remove(meta_path)
                    p(f'[已删除] {tmp_path}', 'y')
                except:
                    pass
            fail_count += 1
    
    p(f'\n[完成] 成功: {success_count} 个, 失败: {fail_count} 个', 'g')
    
    if success_count >= len(tmp_files):
        remove_unfinished_task(task.get('id'))
        p('[信息] 任务已完成', 'g')

# ==================== 中断管理 ====================

class InterruptManager:
    def __init__(self):
        self.interrupted = False
        self.last_result = None  # 记录上次中断菜单结果，供外层检查
        self.current_task = None
        self.task_type = None
        self.task_data = {}
        # 保存当前下载任务信息
        self.current_urls = None
        self.current_mode = None
        self.current_url_info = None
        self.current_task_id = None
        self.current_global_mode = None
    
    def set_task(self, task_type, data=None):
        self.current_task = task_type
        self.task_type = task_type
        self.task_data = data or {}
    
    def set_download_task(self, urls, mode, url_info, task_id=None, global_mode=None):
        """设置当前下载任务"""
        self.current_urls = urls
        self.current_mode = mode
        self.current_url_info = url_info
        self.current_task_id = task_id
        self.current_global_mode = global_mode
    
    def clear_task(self):
        self.current_task = None
        self.task_type = None
        self.task_data = {}
        self.current_urls = None
        self.current_mode = None
        self.current_url_info = None
        self.current_task_id = None
        self.current_global_mode = None
    
    def check_interrupt(self):
        return self.interrupted
    
    def trigger_interrupt(self):
        self.interrupted = True
    
    def reset(self):
        self.interrupted = False
        self.last_result = None
        # 不清除任务信息，以便继续使用
    
    def clear(self):
        """完全清除所有状态"""
        self.interrupted = False
        self.clear_task()
    
    def get_interrupt_menu(self):
        # 重置中断标志，防止在菜单中再次触发
        self.interrupted = False
        print("\n" + "=" * 50)
        p("       中断菜单", 'c')
        print("=" * 50)
        print(f"  当前任务: {self.task_type if self.task_type else '下载中'}")
        if self.task_data:
            print(f"  任务信息: {self.task_data}")
        if self.current_urls:
            print(f"  剩余文件: {len(self.current_urls)} 个")
        print("=" * 50)
        print("  [直接回车] 继续当前下载")
        print("  [q] 返回主菜单（任务已保存）")
        print("  [1] 重新选择下载的解析视频")
        print("  [2] 跳过当前正在进行的任务")
        print("=" * 50)
        
        while True:
            try:
                choice = input("\n请选择: ").strip().lower()
                if choice == '':
                    self.reset()
                    self.last_result = 'continue'
                    return 'continue'
                elif choice in ('q', '0'):
                    self.clear()
                    self.last_result = 'main_menu'
                    return 'main_menu'
                elif choice == '1':
                    self.clear()
                    self.last_result = 'reselect'
                    return 'reselect'
                elif choice == '2':
                    self.clear()
                    self.last_result = 'skip'
                    return 'skip'
                else:
                    p("无效选项，请重新输入", 'y')
            except KeyboardInterrupt:
                p('\n[提示] 请选择菜单选项', 'y')
                continue

interrupt_manager = InterruptManager()

# 自定义中断异常类
class InterruptException(Exception):
    pass

def check_interrupt():
    """检查中断，如果触发了则抛出异常"""
    if interrupt_manager.check_interrupt():
        # 重置中断标志，避免重复触发
        interrupt_manager.interrupted = False
        return interrupt_manager.get_interrupt_menu()
    return None

def setup_interrupt_handler():
    def signal_handler(signum, frame):
        # 使用 sys.stderr.write 避免被缓冲
        sys.stderr.write('\n[中断] 检测到 Ctrl+C，正在中断...\n')
        sys.stderr.flush()
        interrupt_manager.trigger_interrupt()
        
        # 尝试中断可能的阻塞操作
        try:
            # 尝试关闭所有活跃的 requests 会话
            import requests
            if hasattr(requests, 'sessions'):
                for session in requests.sessions:
                    try:
                        session.close()
                    except:
                        pass
        except:
            pass
        
        # 不立即抛出异常，让下载循环自己检查
        # 但如果是在阻塞的 I/O 中，需要强制抛出
        # 这里我们依靠下载循环中的频繁检查
    
    try:
        import signal
        signal.signal(signal.SIGINT, signal_handler)
    except:
        pass

# ==================== 未完成任务管理 ====================

def load_unfinished_tasks():
    try:
        if os.path.exists(UNFINISHED_FILE):
            with open(UNFINISHED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'tasks': []}

def save_unfinished_task(task_data):
    try:
        data = load_unfinished_tasks()
        for i, task in enumerate(data['tasks']):
            if task.get('id') == task_data.get('id'):
                data['tasks'][i] = task_data
                with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
        data['tasks'].append(task_data)
        with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def remove_unfinished_task(task_id):
    try:
        data = load_unfinished_tasks()
        data['tasks'] = [t for t in data['tasks'] if t.get('id') != task_id]
        with open(UNFINISHED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def get_unfinished_tasks():
    data = load_unfinished_tasks()
    return data.get('tasks', [])

def show_unfinished_tasks_menu():
    """显示未完成任务菜单（带扫描进度）"""
    p("[扫描] 正在扫描未完成的任务...", "c")
    
    print("\n" + "=" * 50)
    p("       扫描进度", "c")
    print("=" * 50)
    
    p("[1/2] 正在检查已保存的任务...", "y")
    json_tasks = get_unfinished_tasks()
    if json_tasks:
        p(f"      ✓ 发现 {len(json_tasks)} 个已保存的任务", "g")
    else:
        p("      ✓ 没有已保存的任务", "y")
    time.sleep(0.3)
    
    p("[2/2] 正在扫描临时文件...", "y")
    tmp_files = scan_tmp_files()
    if tmp_files:
        p(f"      ✓ 发现 {len(tmp_files)} 个临时文件", "g")
    else:
        p("      ✓ 没有临时文件", "y")
    time.sleep(0.3)
    
    tasks = get_unfinished_tasks_enhanced()
    
    print("=" * 50)
    p("       扫描完成", "g")
    print("=" * 50)
    
    if not tasks:
        p("[信息] 没有未完成的任务", "y")
        input("\n按回车键返回...")
        return
    
    # ★★★ 使用 while 循环，让用户重新输入而不是返回菜单 ★★★
    while True:
        print("\n" + "=" * 60)
        p("       未完成的任务", "c")
        print("=" * 60)
        
        for i, task in enumerate(tasks, 1):
            task_id = task.get("id", f"task_{i}")
            task_name = task.get("name", "未知任务")
            task_type = task.get("type", "未知类型")
            current_file = task.get("current_file", "无")
            current_progress = task.get("current_progress", "0%")
            remaining = task.get("remaining", "未知")
            last_time = task.get("last_time", "未知")
            url_count = task.get("total", 0)
            completed = task.get("completed", 0)
            status = task.get("status", "unknown")
            
            is_tmp = task.get("is_tmp_task", False)
            tmp_files = task.get("tmp_files", [])
            
            status_text = {"downloading": "⏳ 下载中", "paused": "⏸ 已暂停", "completed": "✅ 已完成", "unknown": "❓ 未知"}.get(status, "❓ 未知")
            
            print(f"  [{i}] {task_name}")
            if is_tmp:
                print(f"     类型: 【临时文件】 | 状态: {status_text}")
                print(f"     文件数量: {len(tmp_files)} 个")
                print(f"     下载进度: {current_progress}")
                print(f"     文件位置: {task.get('folder', '未知')}")
                has_meta = task.get('has_meta', False)
                if has_meta:
                    p(f"     📦 可续传: 是 (有元数据)", 'g')
                    for tf in tmp_files:
                        if tf.get('has_meta', False) and tf.get('meta_info'):
                            url = tf['meta_info'].get('url', '')
                            if url:
                                p(f"     🔗 原始URL: {url[:60]}...", 'c')
                                break
                else:
                    p(f"     ❌ 可续传: 否 (无元数据)", 'y')
                print(f"     最后更新: {last_time}")
            else:
                print(f"     类型: {task_type} | 状态: {status_text} | 总进度: {completed}/{url_count}")
                print(f"     当前文件: {current_file}")
                print(f"     下载进度: {current_progress}")
                print(f"     剩余: {remaining} 个文件")
                print(f"     最后更新: {last_time}")
            print("-" * 56)
        
        print("=" * 60)
        print("操作说明:")
        print("  输入数字选择单个任务继续")
        print("  输入 'm' 进入多选模式")
        print("  输入 'a' 继续所有任务")
        print("  输入 'd' 删除所有已完成的任务")
        print("  输入 't' 清理所有.tmp临时文件")
        print("  输入 'q' 返回主菜单")
        print("=" * 60)
        
        choice = input("\n请选择: ").strip().lower()
        
        if choice in ("q", "0"):
            return
        elif choice == "a":
            for task in tasks:
                continue_unfinished_task_enhanced(task)
            input("\n按回车键返回...")
            return
        elif choice == "d":
            completed_tasks = [t for t in tasks if t.get("status") == "completed" or (t.get("completed", 0) >= t.get("total", 0) and not t.get("is_tmp_task", False))]
            if completed_tasks:
                for task in completed_tasks:
                    remove_unfinished_task(task.get("id"))
                p(f"已删除 {len(completed_tasks)} 个已完成的任务", "g")
            else:
                p("没有已完成的任务", "y")
            input("\n按回车键继续...")
            continue
        elif choice == "t":
            tmp_files = scan_tmp_files()
            if tmp_files:
                print(f"\n发现 {len(tmp_files)} 个临时文件:")
                for f in tmp_files:
                    has_meta = f.get('has_meta', False)
                    meta_status = "📦 有元数据" if has_meta else "❌ 无元数据"
                    print(f"  - {f['file']} ({f['size_mb']}MB) {meta_status}")
                confirm = input("\n确认删除所有.tmp文件？(直接回车=是, 输入0=否): ").strip()
                if confirm == "" or confirm == "1":
                    deleted = 0
                    for f in tmp_files:
                        try:
                            os.remove(f["file"])
                            meta_path = f["file"] + '.meta'
                            if os.path.exists(meta_path):
                                os.remove(meta_path)
                            deleted += 1
                        except:
                            pass
                    p(f"已删除 {deleted} 个临时文件", "g")
                else:
                    p("[取消]", "y")
            else:
                p("没有临时文件", "y")
            input("\n按回车键继续...")
            continue
        elif choice == "m":
            print("\n请输入要选择的任务序号，用空格分隔")
            print("格式示例: 1 3 5 或 1-3")
            multi_choice = input("请输入: ").strip()
            if not multi_choice:
                p("[取消] 已退出", "y")
                continue
            selected_indices = parse_selection_input(multi_choice, len(tasks))
            if not selected_indices:
                p("[错误] 没有有效的选择，请重新输入", "y")
                input("\n按回车键继续...")
                continue
            for idx in selected_indices:
                if 0 <= idx < len(tasks):
                    continue_unfinished_task_enhanced(tasks[idx])
            input("\n按回车键返回...")
            return
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(tasks):
                continue_unfinished_task_enhanced(tasks[idx])
                input("\n按回车键返回...")
                return
            else:
                p(f"无效选择，请输入 1-{len(tasks)} 之间的数字", "y")
                input("\n按回车键继续...")
                continue
        else:
            p("无效选项，请重新输入", "y")
            input("\n按回车键继续...")
            continue
def continue_unfinished_task(task):
    task_id = task.get('id')
    task_name = task.get('name', '未知任务')
    urls = task.get('urls', [])
    mode = task.get('mode', 2)
    url_info = task.get('url_info', {})
    completed = task.get('completed', 0)
    
    p(f'\n[继续任务] {task_name}', 'c')
    p(f'[信息] 已完成 {completed}/{len(urls)} 个，继续下载剩余...', 'c')
    
    remaining_urls = urls[completed:]
    
    success, fail = process_selected_videos(remaining_urls, mode, url_info)
    
    if success + fail >= len(remaining_urls):
        remove_unfinished_task(task_id)
        p(f'[完成] 任务 {task_name} 已完成', 'g')
    else:
        task['completed'] = completed + success
        task['remaining'] = len(urls) - task['completed']
        task['last_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_unfinished_task(task)
        p(f'[更新] 任务进度更新: {task["completed"]}/{len(urls)}', 'y')

# ==================== 失败记录管理 ====================

def load_failed_downloads():
    try:
        if os.path.exists(FAILED_FILE):
            with open(FAILED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'failed_items': [], 'failed_urls': []}

def save_failed_download(failed_info):
    try:
        data = load_failed_downloads()
        for item in data['failed_items']:
            if item.get('url') == failed_info.get('url'):
                return
        
        # ★★★ 提取 BV 号 ★★★
        url = failed_info.get('url', '')
        title = failed_info.get('title', '')
        bvid = None
        
        # 1. 从 URL 中提取
        bv_match = re.search(r'BV([0-9A-Za-z]{10})', url, re.IGNORECASE)
        if bv_match:
            bvid = f'BV{bv_match.group(1)}'
        
        # 2. 从标题中提取
        if not bvid:
            bv_match = re.search(r'BV([0-9A-Za-z]{10})', title, re.IGNORECASE)
            if bv_match:
                bvid = f'BV{bv_match.group(1)}'
        
        # 3. 如果是 B站临时链接但没有 BV 号，尝试从解析结果中获取
        if not bvid and ('bilivideo.com' in url or 'upos' in url):
            # 尝试从已保存的元数据中查找
            download_path = get_download_path()
            for root, dirs, files in os.walk(download_path):
                for file in files:
                    if file.endswith('.meta'):
                        meta_path = os.path.join(root, file)
                        try:
                            with open(meta_path, 'r', encoding='utf-8') as f:
                                meta = json.load(f)
                                if meta.get('url') == url:
                                    meta_title = meta.get('title', '')
                                    bv_match = re.search(r'BV([0-9A-Za-z]{10})', meta_title, re.IGNORECASE)
                                    if bv_match:
                                        bvid = f'BV{bv_match.group(1)}'
                                        break
                        except:
                            pass
                if bvid:
                    break
        
        failed_info['bvid'] = bvid
        data['failed_items'].append(failed_info)
        if failed_info.get('url') and failed_info.get('url') not in data['failed_urls']:
            data['failed_urls'].append(failed_info.get('url'))
        with open(FAILED_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def clear_failed_downloads():
    try:
        if os.path.exists(FAILED_FILE):
            os.remove(FAILED_FILE)
        return True
    except:
        return False

def get_failed_urls():
    data = load_failed_downloads()
    return data.get('failed_urls', [])

def get_failed_items():
    data = load_failed_downloads()
    return data.get('failed_items', [])

# ==================== 视频标题提取和文件检测 ====================

def extract_video_title_from_url(url):
    try:
        result = parse_video(url)
        if result:
            if len(result) >= 3:
                title = result[0]
                if title:
                    return title
    except:
        pass
    return None

def check_file_exists_by_title(title, folder_path=None):
    if not title:
        return False, None
    
    if folder_path is None:
        folder_path = get_download_path()
    
    if not os.path.exists(folder_path):
        return False, None
    
    clean_name = re.sub(r'[\\/:*?"<>|]', '_', title)
    
    extensions = ['.mp4', '.mp3', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4a', '.aac', '.wav']
    
    for ext in extensions:
        file_path = os.path.join(folder_path, f'{clean_name}{ext}')
        if os.path.exists(file_path):
            size = os.path.getsize(file_path) / 1024 / 1024
            if size > 0.5:
                return True, file_path
        
        if os.path.isdir(folder_path):
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    name_without_ext = os.path.splitext(file)[0]
                    clean_file_name = re.sub(r'[\\/:*?"<>|]', '_', name_without_ext)
                    if clean_file_name == clean_name:
                        file_path = os.path.join(root, file)
                        size = os.path.getsize(file_path) / 1024 / 1024
                        if size > 0.5:
                            return True, file_path
    
    return False, None

def get_download_path():
    config = load_config()
    path = config.get('download_path', DEFAULT_DOWNLOAD_PATH)
    os.makedirs(path, exist_ok=True)
    return path

def should_skip_existing():
    config = load_config()
    return config.get('skip_existing', True)

def get_cover_mode():
    config = load_config()
    return config.get('cover_mode', 'api')

def get_cover_crop():
    config = load_config()
    return config.get('cover_crop', 'center')

def get_progress_bar_style():
    config = load_config()
    return config.get('progress_bar_style', 'modern')

# ==================== MP3下载设置功能 ====================

def get_mp3_settings():
    config = load_config()
    return {
        'cover_enabled': config.get('mp3_cover_enabled', True),
        'lyric_enabled': config.get('mp3_lyric_enabled', True),
        'lyric_source': config.get('mp3_lyric_source', 'netease'),
        'cover_source': config.get('mp3_cover_source', 'api')
    }

def save_mp3_settings(cover_enabled=None, lyric_enabled=None, lyric_source=None, cover_source=None):
    config = load_config()
    if cover_enabled is not None:
        config['mp3_cover_enabled'] = cover_enabled
    if lyric_enabled is not None:
        config['mp3_lyric_enabled'] = lyric_enabled
    if lyric_source is not None:
        config['mp3_lyric_source'] = lyric_source
    if cover_source is not None:
        config['mp3_cover_source'] = cover_source
    return save_config(config)

def mp3_settings_menu():
    settings = get_mp3_settings()
    
    source_names = {
        'bilibili': 'B站字幕 (需视频有字幕)',
        'netease': '网易云音乐 (推荐)',
        'qqmusic': 'QQ音乐',
        'musixmatch': 'Musixmatch',
        'lrclib': 'LRCLIB'
    }
    
    while True:
        print("\n" + "=" * 60)
        p("       📥 MP3下载设置", 'c')
        print("=" * 60)
        print(f"  [1] MP3封面下载: {'✅ 开启' if settings['cover_enabled'] else '❌ 关闭'}")
        print(f"  [2] MP3歌词下载: {'✅ 开启' if settings['lyric_enabled'] else '❌ 关闭'}")
        print(f"  [3] 歌词来源: {source_names.get(settings['lyric_source'], settings['lyric_source'])}")
        print("  [q] 返回")
        print("=" * 60)
        print("歌词来源说明：")
        print("  - netease: 网易云音乐（日文/东方/术力口 覆盖率最高）")
        print("  - bilibili: 从B站视频字幕获取（需视频有字幕）")
        print("  - qqmusic: QQ音乐（中文流行）")
        print("  - musixmatch: Musixmatch（英文/国际）")
        print("  - lrclib: LRCLIB（开源/国际）")
        print("=" * 60)
        
        choice = input("\n请选择 [1-3/q]: ").strip().lower()
        
        if choice in ('q', '0'):
            return
        elif choice == '1':
            new_val = not settings['cover_enabled']
            settings['cover_enabled'] = new_val
            save_mp3_settings(cover_enabled=new_val)
            p(f"封面下载已{'开启' if new_val else '关闭'}", 'g')
            input("\n按回车键继续...")
        elif choice == '2':
            new_val = not settings['lyric_enabled']
            settings['lyric_enabled'] = new_val
            save_mp3_settings(lyric_enabled=new_val)
            p(f"歌词下载已{'开启' if new_val else '关闭'}", 'g')
            input("\n按回车键继续...")
        elif choice == '3':
            print("\n" + "=" * 50)
            p("       选择歌词来源", 'c')
            print("=" * 50)
            sources = ['netease', 'bilibili', 'qqmusic', 'musixmatch', 'lrclib']
            for i, src in enumerate(sources, 1):
                status = "✅ 当前" if settings['lyric_source'] == src else "  "
                print(f"  [{i}] {status} {source_names.get(src, src)}")
            print("  [q] 取消")
            print("=" * 50)
            
            src_choice = input("\n请选择 [1-5/q]: ").strip().lower()
            if src_choice in ('q', '0'):
                continue
            if src_choice.isdigit() and 1 <= int(src_choice) <= len(sources):
                selected = sources[int(src_choice) - 1]
                settings['lyric_source'] = selected
                save_mp3_settings(lyric_source=selected)
                p(f"歌词来源已设置为: {source_names.get(selected, selected)}", 'g')
                input("\n按回车键继续...")
            else:
                p("无效选项", 'y')
                input("\n按回车键继续...")
        else:
            p("无效选项", 'y')
            input("\n按回车键继续...")

# ==================== LRC 歌词API设置 ====================

def get_lrc_api_settings():
    config = load_config()
    default_apis = {
        'netease': {'enabled': True, 'priority': 1},
        'bilibili': {'enabled': True, 'priority': 2},
        'qqmusic': {'enabled': True, 'priority': 3},
        'musixmatch': {'enabled': True, 'priority': 4},
        'lrclib': {'enabled': True, 'priority': 5}
    }
    
    saved_apis = config.get('lrc_apis', {})
    apis = {}
    for key, default in default_apis.items():
        if key in saved_apis:
            apis[key] = saved_apis[key]
        else:
            apis[key] = default
    
    for key, default in default_apis.items():
        if key not in apis:
            apis[key] = default
        if 'enabled' not in apis[key]:
            apis[key]['enabled'] = default['enabled']
        if 'priority' not in apis[key]:
            apis[key]['priority'] = default['priority']
    
    return apis

def save_lrc_api_settings(apis):
    config = load_config()
    config['lrc_apis'] = apis
    return save_config(config)

def get_enabled_apis_sorted():
    apis = get_lrc_api_settings()
    enabled = [(key, info['priority']) for key, info in apis.items() if info.get('enabled', True)]
    enabled.sort(key=lambda x: x[1])
    return [key for key, _ in enabled]

def lrc_api_settings_menu():
    apis = get_lrc_api_settings()
    api_names = {
        'bilibili': 'B站搜索 (从视频字幕获取)',
        'netease': '网易云音乐 (推荐日文/东方)',
        'qqmusic': 'QQ音乐',
        'musixmatch': 'Musixmatch',
        'lrclib': 'LRCLIB'
    }
    
    api_tips = {
        'bilibili': '⚠️ 需要视频有字幕，东方老歌通常没有',
        'netease': '✅ 日文歌/东方同人曲覆盖率最高',
        'qqmusic': '中文流行歌较好',
        'musixmatch': '英文歌为主',
        'lrclib': '开源歌词库'
    }
    
    while True:
        print("\n" + "=" * 60)
        p("       🔧 LRC歌词API设置", 'c')
        print("=" * 60)
        print("说明：按优先级顺序尝试，找到歌词即停止")
        print("-" * 60)
        
        sorted_apis = sorted(apis.items(), key=lambda x: x[1].get('priority', 99))
        for i, (key, info) in enumerate(sorted_apis, 1):
            status = '✅' if info.get('enabled', True) else '❌'
            name = api_names.get(key, key)
            tip = api_tips.get(key, '')
            print(f"  {i}. {status} {name} (优先级: {info.get('priority', i)})")
            if tip:
                print(f"      {tip}")
        
        print("-" * 60)
        print("操作说明：")
        print("  [数字] 切换启用/禁用")
        print("  [u] 上移优先级")
        print("  [d] 下移优先级")
        print("  [r] 重置为默认（网易云优先）")
        print("  [q] 返回")
        print("=" * 60)
        
        choice = input("\n请选择: ").strip().lower()
        
        if choice in ('q', '0'):
            return
        elif choice == 'r':
            default_apis = {
                'netease': {'enabled': True, 'priority': 1},
                'bilibili': {'enabled': True, 'priority': 2},
                'qqmusic': {'enabled': True, 'priority': 3},
                'musixmatch': {'enabled': True, 'priority': 4},
                'lrclib': {'enabled': True, 'priority': 5}
            }
            save_lrc_api_settings(default_apis)
            apis = default_apis
            p('已重置为默认设置（网易云优先）', 'g')
            input("\n按回车键继续...")
        elif choice == 'u':
            print("\n选择要上移的API序号:")
            sorted_items = sorted(apis.items(), key=lambda x: x[1].get('priority', 99))
            for i, (key, info) in enumerate(sorted_items, 1):
                status = '✅' if info.get('enabled', True) else '❌'
                name = api_names.get(key, key)
                print(f"  {i}. {status} {name}")
            sub = input("\n请输入序号: ").strip()
            if sub.isdigit():
                idx = int(sub) - 1
                sorted_items = sorted(apis.items(), key=lambda x: x[1].get('priority', 99))
                if 0 <= idx < len(sorted_items) and idx > 0:
                    key1 = sorted_items[idx][0]
                    key2 = sorted_items[idx-1][0]
                    pri1 = apis[key1].get('priority', idx+1)
                    pri2 = apis[key2].get('priority', idx)
                    apis[key1]['priority'] = pri2
                    apis[key2]['priority'] = pri1
                    save_lrc_api_settings(apis)
                    p(f'已上移: {api_names.get(key1, key1)}', 'g')
                else:
                    p('无效选择或已在顶部', 'y')
            input("\n按回车键继续...")
        elif choice == 'd':
            print("\n选择要下移的API序号:")
            sorted_items = sorted(apis.items(), key=lambda x: x[1].get('priority', 99))
            for i, (key, info) in enumerate(sorted_items, 1):
                status = '✅' if info.get('enabled', True) else '❌'
                name = api_names.get(key, key)
                print(f"  {i}. {status} {name}")
            sub = input("\n请输入序号: ").strip()
            if sub.isdigit():
                idx = int(sub) - 1
                sorted_items = sorted(apis.items(), key=lambda x: x[1].get('priority', 99))
                if 0 <= idx < len(sorted_items) and idx < len(sorted_items) - 1:
                    key1 = sorted_items[idx][0]
                    key2 = sorted_items[idx+1][0]
                    pri1 = apis[key1].get('priority', idx+1)
                    pri2 = apis[key2].get('priority', idx+2)
                    apis[key1]['priority'] = pri2
                    apis[key2]['priority'] = pri1
                    save_lrc_api_settings(apis)
                    p(f'已下移: {api_names.get(key1, key1)}', 'g')
                else:
                    p('无效选择或已在底部', 'y')
            input("\n按回车键继续...")
        elif choice.isdigit():
            idx = int(choice) - 1
            sorted_items = sorted(apis.items(), key=lambda x: x[1].get('priority', 99))
            if 0 <= idx < len(sorted_items):
                key = sorted_items[idx][0]
                current = apis[key].get('enabled', True)
                apis[key]['enabled'] = not current
                save_lrc_api_settings(apis)
                p(f"{api_names.get(key, key)} 已{'启用' if not current else '禁用'}", 'g')
                input("\n按回车键继续...")
            else:
                p('无效选择', 'y')
                input("\n按回车键继续...")
        else:
            p('无效选项', 'y')
            input("\n按回车键继续...")

# ==================== 进度管理功能 ====================

def load_progress(bv_id):
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(bv_id, {})
    except:
        pass
    return {}

def save_progress(bv_id, progress_data):
    try:
        data = {}
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data[bv_id] = progress_data
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def get_downloaded_pages(bv_id):
    progress = load_progress(bv_id)
    return set(progress.get('downloaded_pages', []))

def mark_page_downloaded(bv_id, page_num, page_title):
    progress = load_progress(bv_id)
    if 'downloaded_pages' not in progress:
        progress['downloaded_pages'] = []
    if page_num not in progress['downloaded_pages']:
        progress['downloaded_pages'].append(page_num)
    progress['last_page'] = page_num
    progress['last_title'] = page_title
    progress['total_downloaded'] = len(progress['downloaded_pages'])
    save_progress(bv_id, progress)

def clear_progress(bv_id):
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if bv_id in data:
                del data[bv_id]
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
    except:
        pass
    return False

# ==================== 文件检测功能 ====================

def check_file_in_folder(filename, folder_path):
    if not folder_path or not os.path.exists(folder_path):
        return False, None
    
    clean_name = re.sub(r'[\\/:*?"<>|]', '_', filename)
    
    for ext in ['.mp4', '.mp3']:
        file_path = os.path.join(folder_path, f'{clean_name}{ext}')
        if os.path.exists(file_path):
            size = os.path.getsize(file_path) / 1024 / 1024
            if size > 0.5:
                return True, file_path
    return False, None

def get_existing_files_count(folder_path=None):
    if folder_path:
        save_dir = folder_path
    else:
        save_dir = get_download_path()
    
    if not os.path.exists(save_dir):
        return 0
    
    count = 0
    for root, dirs, files in os.walk(save_dir):
        for file in files:
            if file.endswith(('.mp4', '.mp3')):
                if os.path.getsize(os.path.join(root, file)) > 1024:
                    count += 1
    return count

def get_device_id():
    try:
        hostname = socket.gethostname()
        return hashlib.md5(hostname.encode()).hexdigest()[:16]
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
                "os": "Android/Termux",
                "os_version": platform.version(),
                "python_version": sys.version[:10],
                "public_ip": get_public_ip(),
                "data": data or {}
            }
            requests.post(STATS_API_URL, json=payload, timeout=5)
        except:
            pass
    threading.Thread(target=send, daemon=True).start()

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

ANNOUNCEMENT_URL = "https://mzrl.xn--4gqq11cba.xn--czrs0t/%E7%9B%B4%E9%93%BE%E8%A7%A3%E6%9E%90/zljx.php?api=get_content&file=%E5%85%AC%E5%91%8A.txt"

def show_announcement():
    """从远程服务器获取公告内容并显示"""
    print('\n' + '=' * 50)
    p('       公告', 'c')
    print('=' * 50)
    
    try:
        response = requests.get(ANNOUNCEMENT_URL, timeout=10)
        if response.status_code == 200:
            content = response.text.strip()
            if content:
                # 尝试解析JSON响应
                try:
                    import json
                    data = json.loads(content)
                    if data.get('status') == 'ok' and data.get('content'):
                        content = data['content'].strip()
                except (json.JSONDecodeError, ValueError):
                    pass  # 非JSON格式，直接当文本用
                if content:
                    for line in content.split('\n'):
                        print(f"  {line}")
                else:
                    p('  暂无公告', 'y')
            else:
                p('  暂无公告', 'y')
        else:
            p(f'  [获取公告失败] HTTP {response.status_code}', 'y')
    except Exception as e:
        p(f'  [获取公告失败] {e}', 'y')
    
    print('=' * 50)
    input('\n按回车键继续...')
    
def display_stats():
    stats = fetch_server_stats()
    download_path = get_download_path()
    existing_count = get_existing_files_count()
    skip = should_skip_existing()
    cover_mode = get_cover_mode()
    cover_mode_text = "API封面" if cover_mode == "api" else "视频截图"
    cover_crop = get_cover_crop()
    crop_text = {"center": "居中", "top": "上部", "bottom": "下部", "left": "左侧", "right": "右侧"}.get(cover_crop, "居中")
    
    mp3_settings = get_mp3_settings()
    source_names = {
        'bilibili': 'B站字幕',
        'netease': '网易云',
        'qqmusic': 'QQ音乐',
        'musixmatch': 'Musixmatch',
        'lrclib': 'LRCLIB'
    }
    
    print("\n" + "=" * 50)
    print(f"     多平台视频下载器 for Termux v{VERSION}")
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
    print(f"     支持B站/抖音/快手/YouTube / 全局模式 / 部分选择 / MP3封面+歌词智能匹配")
    print(f"     下载路径: {download_path}")
    print(f"     已存在文件: {existing_count} 个  |  跳过已存在: {'开启' if skip else '关闭'}")
    print(f"     MP3封面: {'开启' if mp3_settings['cover_enabled'] else '关闭'}  |  歌词: {'开启' if mp3_settings['lyric_enabled'] else '关闭'}")
    print(f"     歌词来源: {source_names.get(mp3_settings['lyric_source'], mp3_settings['lyric_source'])}")
    print("=" * 50)

def p(text, color='white'):
    colors = {
        'r': '\033[91m', 'g': '\033[92m', 'y': '\033[93m',
        'c': '\033[96m', 'm': '\033[95m', 'w': '\033[0m'
    }
    print(f"{colors.get(color, colors['w'])}{text}{colors['w']}")

def debug_print(text, color='c'):
    config = load_config()
    if config.get('debug_mode', False):
        p(f'[DEBUG] {text}', color)

def _pip_install_with_retry(packages, pip_extra=''):
    """安装pip包，支持多源自动回退重试（清华源→官方PyPI→阿里云源）"""
    sources = [
        ('当前源', ''),  # 使用pip当前配置的源（可能是清华源）
        ('官方PyPI', ' -i https://pypi.org/simple'),
        ('阿里云源', ' -i https://mirrors.aliyun.com/pypi/simple/'),
    ]
    for name, src in sources:
        p(f'  [尝试] 使用{name}安装 {packages}...', 'y')
        ret = os.system(f'pip install{pip_extra}{src} {packages}')
        if ret == 0:
            p(f'  [成功] 使用{name}安装完成', 'g')
            return True
        p(f'  [失败] {name}安装失败，尝试其他源...', 'r')
    p(f'  [错误] 所有源均安装失败: {packages}', 'r')
    return False

def check_dependencies():
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
    try:
        import pykakasi
        p('[OK] pykakasi 已安装（歌词罗马音）', 'g')
    except:
        missing.append('pykakasi')
        p('[!] pykakasi 未安装（歌词罗马音功能）', 'y')
    
    try:
        import qrcode
        p('[OK] qrcode 已安装（终端二维码）', 'g')
    except:
        missing.append('qrcode')
        p('[!] qrcode 未安装（B站扫码登录二维码）', 'y')
    
    
    try:
        subprocess.run(['yt-dlp', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p('[OK] yt-dlp 已安装', 'g')
    except:
        missing.append('yt-dlp')
        p('[!] yt-dlp 未安装', 'y')
    
    # 检测 nano 编辑器 (用于大量链接粘贴输入)
    try:
        subprocess.run(['nano', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p('[OK] nano 已安装', 'g')
    except:
        missing.append('nano')
        p('[!] nano 未安装 (大量链接输入需要)', 'y')
    
    if missing:
        print("-" * 50)
        p(f'缺少组件: {", ".join(missing)}', 'y')
        print("[提示] 直接回车 = 安装")
        choice = input('\n是否自动安装缺失组件? (直接回车=是, 输入0=否): ').strip()
        if choice == '' or choice == '1':
            # ★★★ 修复：检测PEP 668环境，pip安装需加 --break-system-packages ★★★
            pip_extra = ''
            try:
                # 检查是否受PEP 668保护（Debian/Ubuntu 23.04+ 系统Python）
                _test = subprocess.run(
                    ['pip', 'install', '--dry-run', 'nonexistent-pkg'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
                )
                if b'externally-managed' in _test.stderr:
                    pip_extra = ' --break-system-packages'
                    p('[提示] 检测到PEP 668环境，pip安装将使用 --break-system-packages', 'y')
            except:
                pass
            
            for dep in missing:
                if dep == 'ffmpeg':
                    p(f'[安装] 正在安装 ffmpeg...', 'c')
                    os.system('pkg install ffmpeg -y')
                elif dep == 'nano':
                    p(f'[安装] 正在安装 nano...', 'c')
                    os.system('pkg install nano -y')
                elif dep == 'yt-dlp':
                    p(f'[安装] 正在安装 yt-dlp...', 'c')
                    _pip_install_with_retry(f'yt-dlp', pip_extra)
                elif dep == 'qrcode':
                    p(f'[安装] 正在安装 qrcode + pillow...', 'c')
                    _pip_install_with_retry('qrcode pillow', pip_extra)
                else:
                    p(f'[安装] 正在安装 {dep}...', 'c')
                    _pip_install_with_retry(dep, pip_extra)
            p('安装完成，请重新运行脚本', 'g')
            input('\n按回车键退出...')
            sys.exit(0)
        else:
            p('跳过安装，部分功能可能不可用', 'y')
    else:
        p('所有依赖检测通过', 'g')
    
    print("=" * 50)

def extract_urls_from_input(user_input):
    urls = []
    text = user_input
    
    text = re.sub(r'(https://)', r' \1', text)
    
    patterns = [
        r'https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9]+',
        r'https?://b23\.tv/[A-Za-z0-9]+',
        r'https?://(?:www\.)?bilibili\.com/medialist/play/[0-9]+',
        r'https?://(?:www\.)?bilibili\.com/list/[0-9]+',
        r'https?://v\.douyin\.com/[A-Za-z0-9]+/?',
        r'https?://www\.douyin\.com/video/[0-9]+',
        r'https?://v\.kuaishou\.com/[A-Za-z0-9]+/?',
        r'https?://www\.kuaishou\.com/short-video/[A-Za-z0-9]+',
        r'https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+',
        r'https?://youtu\.be/[A-Za-z0-9_-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[A-Za-z0-9_-]+',
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
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
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
    try:
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        resp = requests.get(api_url, headers=headers, timeout=10)
        data = resp.json()
        
        if data.get('code') == 0:
            video_data = data.get('data', {})
            pages = video_data.get('pages', [])
            
            debug_print(f'获取到视频信息: {video_data.get("title", "未知标题")}')
            debug_print(f'分P数量: {len(pages) if pages else 0}')
            
            if pages and len(pages) > 1:
                page_list = []
                for idx, page in enumerate(pages, 1):
                    page_list.append({
                        'cid': page.get('cid'),
                        'page': page.get('page', idx),
                        'part': page.get('part', f'P{idx}'),
                        'duration': page.get('duration', 0),
                        'index': idx
                    })
                    debug_print(f'  P{idx}: cid={page.get("cid")}, 标题={page.get("part", f"P{idx}")[:30]}...')
                return page_list
            elif pages:
                return [{
                    'cid': pages[0].get('cid'),
                    'page': 1,
                    'part': video_data.get('title', '视频'),
                    'duration': pages[0].get('duration', 0),
                    'index': 1
                }]
    except Exception as e:
        p(f'[获取分P信息失败] {e}', 'y')
    return None

# ==================== B站合集解析功能 ====================

def extract_medialist_id(url):
    patterns = [
        r'medialist/play/(\d+)',
        r'list/(\d+)',
        r'ml(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    if 'b23.tv' in url:
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            final_url = resp.url
            for pattern in patterns:
                match = re.search(pattern, final_url)
                if match:
                    return match.group(1)
        except:
            pass
    return None

def get_bilibili_medialist(ml_id):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        
        info_url = f"https://api.bilibili.com/x/v1/medialist/info?type=4&biz_id={ml_id}"
        resp = requests.get(info_url, headers=headers, timeout=10)
        data = resp.json()
        
        if data.get('code') != 0:
            debug_print(f'获取合集信息失败: {data.get("message", "未知错误")}')
            return None
        
        medialist = data.get('data', {})
        title = medialist.get('title', '合集')
        debug_print(f'合集标题: {title}')
        
        all_videos = []
        page = 1
        page_size = 50
        
        while True:
            content_url = f"https://api.bilibili.com/x/v1/medialist/contents?type=4&biz_id={ml_id}&page={page}&pagesize={page_size}"
            resp2 = requests.get(content_url, headers=headers, timeout=10)
            data2 = resp2.json()
            
            if data2.get('code') != 0:
                break
            
            contents = data2.get('data', {}).get('contents', [])
            if not contents:
                break
            
            for item in contents:
                video = item.get('content', {})
                bvid = video.get('bvid', '')
                title = video.get('title', '未知标题')
                pic = video.get('pic', '')
                if pic and pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic and not pic.startswith(('http://', 'https://')):
                    pic = 'https://' + pic
                
                if bvid:
                    all_videos.append({
                        'bvid': bvid,
                        'title': title,
                        'pic': pic,
                        'url': f"https://www.bilibili.com/video/{bvid}"
                    })
                    debug_print(f'  视频: {title[:40]}... (BV:{bvid})')
            
            if len(contents) < page_size:
                break
            page += 1
        
        if all_videos:
            return {
                'title': title,
                'videos': all_videos,
                'total': len(all_videos)
            }
        else:
            debug_print('合集为空或获取失败')
            return None
            
    except Exception as e:
        p(f'[获取合集信息失败] {e}', 'y')
        debug_print(f'合集解析异常: {e}')
    return None
# ==================== YouTube Cookies 检测功能 ====================

def check_youtube_cookies():
    cookie_paths = [
        os.path.join(os.path.dirname(SCRIPT_PATH), 'cookies.txt'),
        os.path.join(os.path.dirname(SCRIPT_PATH), 'cookies'),
        '/storage/emulated/0/Download/cookies.txt',
        '/sdcard/Download/cookies.txt',
        os.path.expanduser('~/cookies.txt'),
        os.path.expanduser('~/cookies'),
    ]
    
    for path in cookie_paths:
        if os.path.exists(path) and os.path.getsize(path) > 100:
            debug_print(f'找到cookies文件: {path}')
            return path
    
    return None

def show_youtube_cookies_guide():
    print("\n" + "=" * 60)
    p("       ⚠️ YouTube 需要 Cookies 认证", 'r')
    print("=" * 60)
    print()
    print("由于 YouTube 的反爬虫机制，下载需要登录认证。")
    print()
    p("【解决方法】在电脑上导出 cookies.txt 文件", 'c')
    print("=" * 60)
    print()
    print("步骤 1: 安装浏览器扩展")
    print("   Chrome/Edge: Get cookies.txt LOCALLY")
    print("   Firefox: cookies.txt")
    print()
    print("步骤 2: 登录 YouTube")
    print("   打开 https://www.youtube.com 并登录账号")
    print()
    print("步骤 3: 导出 Cookies")
    print("   点击扩展图标 → Export → 保存为 cookies.txt")
    print()
    print("步骤 4: 传到手机并放到以下位置之一：")
    print(f"   1. {os.path.join(os.path.dirname(SCRIPT_PATH), 'cookies.txt')}")
    print(f"   2. /storage/emulated/0/Download/cookies.txt")
    print(f"   3. ~/cookies.txt")
    print()
    print("步骤 5: 重新运行脚本")
    print("=" * 60)
    print()
    print("[提示] 按回车键继续（请先完成以上步骤）")
    print("  [q] 返回上一级")
    print("  [x] 退出")
    print("=" * 60)

def check_and_prompt_youtube_cookies(show_guide=True):
    cookie_path = check_youtube_cookies()
    
    if cookie_path:
        debug_print(f'cookies已就绪: {cookie_path}')
        try:
            test_cmd = [
                'yt-dlp',
                '--cookies', cookie_path,
                '--simulate',
                '--no-warnings',
                'https://youtu.be/DeKLpgzh-qQ'
            ]
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                p('[OK] YouTube cookies 有效', 'g')
                return True
            else:
                p('[警告] cookies 可能已过期，请重新导出', 'y')
                if show_guide:
                    show_youtube_cookies_guide()
                return False
        except:
            p('[警告] cookies 测试失败', 'y')
            return False
    else:
        p('[!] 未找到 YouTube cookies 文件', 'y')
        if show_guide:
            show_youtube_cookies_guide()
            choice = input('\n请选择 [回车继续 / q返回 / x退出]: ').strip().lower()
            if choice in ('q', '0'):
                return False
            elif choice == 'x':
                sys.exit(0)
            else:
                return check_and_prompt_youtube_cookies(show_guide=False)
        return False

def get_cookies_path():
    cookie_paths = [
        os.path.join(os.path.dirname(SCRIPT_PATH), 'cookies.txt'),
        os.path.join(os.path.dirname(SCRIPT_PATH), 'cookies'),
        '/storage/emulated/0/Download/cookies.txt',
        '/sdcard/Download/cookies.txt',
        os.path.expanduser('~/cookies.txt'),
        os.path.expanduser('~/cookies'),
    ]
    
    for path in cookie_paths:
        if os.path.exists(path) and os.path.getsize(path) > 100:
            return path
    
    script_dir = os.path.dirname(SCRIPT_PATH)
    for path in ['/storage/emulated/0/Download/cookies.txt', '/sdcard/Download/cookies.txt']:
        if os.path.exists(path) and os.path.getsize(path) > 100:
            try:
                link_path = os.path.join(script_dir, 'cookies.txt')
                if not os.path.exists(link_path):
                    os.symlink(path, link_path)
                    return link_path
            except:
                pass
    
    return None

def get_bilibili_video_url(bv_id):
    """通过B站API获取视频URL"""
    try:
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        resp = requests.get(api_url, headers=headers, timeout=10)
        data = resp.json()
        if data.get('code') == 0:
            video_data = data.get('data', {})
            # 获取视频的播放地址
            cid = video_data.get('cid')
            if cid:
                play_url = f"https://api.bilibili.com/x/player/playurl?bvid={bv_id}&cid={cid}&qn=80&type=&otype=json"
                play_resp = requests.get(play_url, headers=headers, timeout=10)
                play_data = play_resp.json()
                if play_data.get('code') == 0:
                    durl = play_data.get('data', {}).get('durl', [])
                    if durl:
                        return durl[0].get('url', '')
        return None
    except Exception as e:
        debug_print(f'获取B站视频URL失败: {e}')
        return None

# ==================== 解析视频功能 ====================

def parse_video(url):
    retry = 0
    pages = None
    bv_id = None
    # 从配置读取最大重试次数
    config = load_config()
    MAX_RETRIES = config.get('max_parse_retries', 5)
    
    # YouTube 处理代码保持不变...
    if 'youtube.com' in url or 'youtu.be' in url:
        # ... 保持原有 YouTube 处理代码 ...
        pass
    
    while retry < MAX_RETRIES:
        try:
            # 检查中断
            if interrupt_manager.check_interrupt():
                interrupt_result = interrupt_manager.get_interrupt_menu()
                if interrupt_result == 'main_menu':
                    return None, None, None, None
                elif interrupt_result == 'skip':
                    return None, None, None, None
                elif interrupt_result == 'reselect':
                    return None, None, None, None
                elif interrupt_result == 'continue':
                    interrupt_manager.reset()
                    continue
            
            p(f'[解析] {url}', 'c')
            debug_print(f'开始解析URL: {url}')
            
            is_bilibili = 'bilibili.com' in url or 'b23.tv' in url
            is_medialist = False
            medialist_info = None
            
            # ★★★ 新增：用于存储修正后的URL ★★★
            actual_url = url
            
            if is_bilibili:
                medialist_id = extract_medialist_id(url)
                if medialist_id:
                    is_medialist = True
                    p(f'[B站合集] 检测到合集ID: {medialist_id}', 'c')
                    debug_print(f'合集ID: {medialist_id}')
                    
                    medialist_info = get_bilibili_medialist(medialist_id)
                    if medialist_info and medialist_info['videos']:
                        p(f'[B站合集] 包含 {medialist_info["total"]} 个视频', 'g')
                        debug_print(f'合集视频数量: {medialist_info["total"]}')
                        return None, None, None, None, medialist_info
                    else:
                        p(f'[B站合集] 获取视频列表失败，尝试作为普通链接处理', 'y')
                
                bv_match = re.search(r'BV([0-9A-Za-z]{10})', url, re.IGNORECASE)
                if bv_match:
                    bv_id = f'BV{bv_match.group(1)}'
                    p(f'[B站] 检测到BV号: {bv_id}', 'c')
                    debug_print(f'BV号: {bv_id}')
                    pages = get_bilibili_video_pages(bv_id)
                    if pages and len(pages) > 1:
                        p(f'[B站] 检测到 {len(pages)} 个分P', 'g')
                        debug_print(f'分P数量: {len(pages)}')
                    elif pages:
                        p(f'[B站] 单个视频', 'c')
                elif 'b23.tv' in url:
                    try:
                        resp = requests.head(url, timeout=10, allow_redirects=True)
                        final_url = resp.url
                        debug_print(f'短链接重定向到: {final_url}')
                        
                        # ★★★ 修复：检测并修正 p 参数，默认使用 P1 ★★★
                        p_match = re.search(r'[?&]p=(\d+)', final_url)
                        if p_match:
                            p_value = int(p_match.group(1))
                            if p_value != 1:
                                p(f'[提示] 短链接跳转到P{p_value}，自动修正为P1...', 'y')
                                # 将 p=数字 改为 p=1
                                actual_url = re.sub(r'[?&]p=\d+', '&p=1', final_url)
                                # 如果URL中没有?，将第一个&改为?
                                if '?' not in actual_url and 'p=1' in actual_url:
                                    actual_url = actual_url.replace('&p=1', '?p=1')
                                debug_print(f'修正后URL: {actual_url}')
                            else:
                                actual_url = final_url
                        else:
                            # 如果没有p参数，添加p=1确保进入P1
                            if '?' in final_url:
                                actual_url = final_url + '&p=1'
                            else:
                                actual_url = final_url + '?p=1'
                            debug_print(f'添加p=1参数: {actual_url}')
                        
                        # ★★★ 重要：用修正后的URL继续处理 ★★★
                        medialist_id = extract_medialist_id(actual_url)
                        if medialist_id:
                            is_medialist = True
                            p(f'[B站合集] 检测到合集ID: {medialist_id}', 'c')
                            medialist_info = get_bilibili_medialist(medialist_id)
                            if medialist_info and medialist_info['videos']:
                                p(f'[B站合集] 包含 {medialist_info["total"]} 个视频', 'g')
                                return None, None, None, None, medialist_info
                        
                        bv_match = re.search(r'BV([0-9A-Za-z]{10})', actual_url, re.IGNORECASE)
                        if bv_match:
                            bv_id = f'BV{bv_match.group(1)}'
                            pages = get_bilibili_video_pages(bv_id)
                            if pages and len(pages) > 1:
                                p(f'[B站] 检测到 {len(pages)} 个分P', 'g')
                                debug_print(f'分P数量: {len(pages)}')
                    except Exception as e:
                        debug_print(f'短链接解析异常: {e}')
                        pass
            
            # ★★★ 重要：使用修正后的URL进行API请求 ★★★
            # 如果是B站短链接且已修正，使用 actual_url；否则使用原始url
            api_url = actual_url if 'b23.tv' not in url else actual_url
            debug_print(f'API请求URL: {api_url}')
            
            r = requests.get(API_URL, params={'url': api_url}, timeout=30)
            debug_print(f'API响应状态码: {r.status_code}')
            
            data = None
            try:
                data = r.json()
                debug_print(f'API响应code: {data.get("code")}')
            except:
                m = re.search(r'\{.*\}', r.text, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(0))
                    except:
                        data = {}
                else:
                    data = {}
                debug_print(f'API响应(JSON解析): {data}')
            
            if data is None:
                retry += 1
                if retry >= MAX_RETRIES:
                    p(f'[错误] 解析失败，已达到最大重试次数 {MAX_RETRIES}', 'r')
                    return None, None, None, None
                p(f'[重试 {retry}/{MAX_RETRIES}] 解析失败（数据为空）', 'y')
                time.sleep(2)
                continue
            
            if data.get('code') in [0, 200]:
                d = data.get('data', {})
                title = d.get('title', '')
                vurl = d.get('url', '') or d.get('video', '')
                cover = d.get('cover', '') or d.get('pic', '')
                
                debug_print(f'解析结果: 标题="{title}", 视频URL={vurl[:80]}..., 封面={cover[:80]}...')
                
                # 修复：如果 title 是 None 或空字符串，尝试从其他地方获取
                if not title or title == 'None':
                    if is_bilibili and bv_id:
                        title_from_api = get_video_title(bv_id)
                        if title_from_api:
                            title = title_from_api
                            debug_print(f'从B站API获取标题: {title}')
                    if not title or title == 'None':
                        title = 'video'
                        debug_print(f'使用默认标题: {title}')
                
                if is_bilibili and (not cover or 'transparent.png' in cover) and bv_id:
                    real_cover = get_bilibili_cover(bv_id)
                    if real_cover:
                        cover = real_cover
                        p(f'[B站] 获取到真实封面', 'g')
                        debug_print(f'真实封面: {cover}')
                
                # 修复：如果 vurl 为空，尝试从其他来源获取
                if not vurl:
                    if is_bilibili and bv_id:
                        vurl_from_api = get_bilibili_video_url(bv_id)
                        if vurl_from_api:
                            vurl = vurl_from_api
                            debug_print(f'从备用API获取视频URL: {vurl[:80]}...')
                
                if vurl and title:
                    title = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', title)
                    p(f'[成功] {title}', 'g')
                    debug_print(f'最终视频URL: {vurl}')
                    # ★★★ 返回 pages 信息，让主循环显示分P菜单 ★★★
                    return title, vurl, cover, pages
                else:
                    retry += 1
                    if retry >= MAX_RETRIES:
                        p(f'[错误] 解析失败，已达到最大重试次数 {MAX_RETRIES}', 'r')
                        debug_print(f'解析结果不完整: title={title}, vurl={vurl}')
                        return None, None, None, None
                    p(f'[重试 {retry}/{MAX_RETRIES}] 解析结果不完整（vurl或title为空）', 'y')
                    debug_print(f'解析结果不完整: title={title}, vurl={vurl}')
                    time.sleep(2)
                    continue
            
            retry += 1
            if retry >= MAX_RETRIES:
                p(f'[错误] 解析失败，已达到最大重试次数 {MAX_RETRIES}', 'r')
                return None, None, None, None
            
            msg = data.get('msg', '解析失败') if data else '解析失败'
            p(f'[重试 {retry}/{MAX_RETRIES}] {msg}', 'y')
            debug_print(f'解析失败: {msg}')
            
        except Exception as e:
            if interrupt_manager.check_interrupt():
                interrupt_result = interrupt_manager.get_interrupt_menu()
                if interrupt_result == 'main_menu':
                    return None, None, None, None
                elif interrupt_result == 'skip':
                    return None, None, None, None
                elif interrupt_result == 'reselect':
                    return None, None, None, None
                elif interrupt_result == 'continue':
                    interrupt_manager.reset()
                    continue
            
            retry += 1
            if retry >= MAX_RETRIES:
                p(f'[错误] 解析失败，已达到最大重试次数 {MAX_RETRIES}', 'r')
                debug_print(f'解析异常: {e}')
                return None, None, None, None
            p(f'[重试 {retry}/{MAX_RETRIES}] {e}', 'y')
            debug_print(f'解析异常: {e}')
        time.sleep(2)
    
    return None, None, None, None

def format_time(seconds):
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

# ==================== 下载功能 ====================

def download_with_ytdlp(url, output_path, title):
    p(f'[下载] 使用 yt-dlp 下载...', 'c')
    debug_print(f'使用 yt-dlp 下载: {url}')
    
    cookies_path = get_cookies_path()
    
    if not cookies_path:
        p('[提示] 未找到 YouTube cookies', 'y')
        show_youtube_cookies_guide()
        return None
    
    try:
        cmd = [
            'yt-dlp',
            '-f', 'best[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '-o', output_path,
            '--no-warnings',
            '--no-playlist',
            '--no-check-certificates',
            '--geo-bypass',
            '--sleep-requests', '1',
            '--sleep-interval', '1',
            '--max-sleep-interval', '3',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        ]
        
        if cookies_path and os.path.exists(cookies_path):
            cmd.extend(['--cookies', cookies_path])
            debug_print(f'使用cookies文件: {cookies_path}')
        else:
            p('[错误] 未找到有效的cookies文件', 'r')
            show_youtube_cookies_guide()
            return None
        
        cmd.append(url)
        
        debug_print(f'执行命令: {" ".join(cmd[:10])} ...')
        
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
        last_percent = 0
        error_lines = []
        
        for line in process.stderr:
            if '%' in line:
                match = re.search(r'(\d+\.?\d*%)', line)
                if match:
                    percent = match.group(1)
                    if percent != last_percent:
                        sys.stderr.write(f'\r[进度] {percent}')
                        sys.stderr.flush()
                        last_percent = percent
            elif 'ERROR' in line:
                error_lines.append(line.strip())
                debug_print(f'yt-dlp错误: {line.strip()}')
            elif 'WARNING' in line:
                debug_print(f'警告: {line.strip()}')
        
        process.wait()
        sys.stderr.write('\n')
        
        if process.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path) / 1024 / 1024
            if size > 0.5:
                p(f'[完成] {size:.1f}MB', 'g')
                report_stats("download", {"title": title, "size": round(size, 2)})
                debug_print(f'下载完成: {output_path}, 大小: {size:.2f}MB')
                return output_path
            else:
                p(f'[警告] 文件过小({size:.1f}MB)，可能下载失败', 'y')
                if os.path.exists(output_path):
                    os.remove(output_path)
                return None
        else:
            p(f'[错误] yt-dlp返回码: {process.returncode}', 'r')
            for err in error_lines[:3]:
                debug_print(f'错误详情: {err}')
            
            if 'expired' in str(error_lines) or 'invalid' in str(error_lines):
                p('[提示] cookies可能已过期，请重新导出', 'y')
                show_youtube_cookies_guide()
            return None
            
    except subprocess.TimeoutExpired:
        p('[超时] 下载超时', 'y')
        return None
    except Exception as e:
        p(f'[错误] {e}', 'r')
        debug_print(f'yt-dlp下载异常: {e}')
        return None

def download_file(url, title, folder_path=None):
    if folder_path:
        save_dir = folder_path
    else:
        save_dir = get_download_path()
    
    os.makedirs(save_dir, exist_ok=True)
    name = re.sub(r'[\\/:*?"<>|]', '_', title)
    
    # ★★★ 修复：检查 title 是否已经包含扩展名 ★★★
    if name.endswith('.mp4') or name.endswith('.mp3'):
        base_name = name
    else:
        base_name = name
    
    if should_skip_existing():
        exists, existing_path = check_file_exists_by_title(title, save_dir)
        if exists:
            size = os.path.getsize(existing_path) / 1024 / 1024
            p(f'[跳过] 文件已存在: {os.path.basename(existing_path)} ({size:.1f}MB)', 'y')
            debug_print(f'跳过已存在文件: {existing_path}')
            return existing_path
    
    # ★★★ 修复：正确处理文件名，避免重复添加 .mp4 ★★★
    if base_name.endswith('.mp4'):
        vpath = os.path.join(save_dir, base_name)
    else:
        vpath = os.path.join(save_dir, f'{base_name}.mp4')
    
    # 如果文件已存在，添加序号
    c = 1
    while os.path.exists(vpath):
        if base_name.endswith('.mp4'):
            vpath = os.path.join(save_dir, f'{base_name.replace(".mp4", "")}_{c}.mp4')
        else:
            vpath = os.path.join(save_dir, f'{base_name}_{c}.mp4')
        c += 1
    
    if 'googlevideo.com' in url:
        p(f'[下载] 检测到YouTube临时链接，使用原始链接重试...', 'c')
        video_id_match = re.search(r'id=o-([A-Za-z0-9_-]+)', url)
        if video_id_match:
            original_url = f"https://youtu.be/{video_id_match.group(1)}"
            debug_print(f'提取到原始链接: {original_url}')
            return download_with_ytdlp(original_url, vpath, title)
        else:
            video_id_match2 = re.search(r'id=([A-Za-z0-9_-]+)', url)
            if video_id_match2:
                original_url = f"https://youtu.be/{video_id_match2.group(1)}"
                debug_print(f'提取到原始链接: {original_url}')
                return download_with_ytdlp(original_url, vpath, title)
            return download_with_ytdlp(url, vpath, title)
    
    if 'youtube.com' in url or 'youtu.be' in url:
        return download_with_ytdlp(url, vpath, title)
    
    tmp_path = vpath + '.tmp'
    meta_path = vpath + '.meta'
    resume_pos = 0
    
    debug_print(f'下载路径: {vpath}')
    debug_print(f'下载URL: {url[:100]}...')
    
    # 保存元数据
    try:
        meta_data = {
            'url': url,
            'title': title,
            'folder': save_dir,
            'filename': name,
            'timestamp': time.time()
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        debug_print(f'元数据已保存: {meta_path}')
    except Exception as e:
        debug_print(f'保存元数据失败: {e}')
    
    if '.m3u8' in url:
        p(f'[下载] 正在下载...', 'c')
        debug_print('检测到m3u8流，使用ffmpeg下载')
        
        for attempt in range(3):
            # ★★★ 检查中断 ★★★
            if interrupt_manager.check_interrupt():
                p('\n[中断] 用户中断下载', 'y')
                return None
            
            try:
                cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-stats',
                       '-i', url, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-y', vpath]
                
                process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
                
                while True:
                    # ★★★ 检查中断 ★★★
                    if interrupt_manager.check_interrupt():
                        process.terminate()
                        p('\n[中断] 用户中断下载', 'y')
                        return None
                    
                    line = process.stderr.readline()
                    if not line and process.poll() is not None:
                        break
                
                process.wait()
                
                if process.returncode == 0 and os.path.exists(vpath):
                    size = os.path.getsize(vpath) / 1024 / 1024
                    if size > 0.5:
                        p(f'[完成] {size:.1f}MB', 'g')
                        report_stats("download", {"title": title, "size": round(size, 2)})
                        debug_print(f'下载完成: {vpath}, 大小: {size:.2f}MB')
                        try:
                            if os.path.exists(meta_path):
                                os.remove(meta_path)
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                        except:
                            pass
                        return vpath
                    else:
                        p(f'[警告] 文件过小({size:.1f}MB)，可能下载失败', 'y')
                        os.remove(vpath)
                        save_failed_download({'url': url, 'title': title, 'reason': '文件过小'})
                        return None
                else:
                    p(f'[重试] ffmpeg返回码:{process.returncode}', 'y')
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        p(f'[错误] ffmpeg下载失败', 'r')
                        save_failed_download({'url': url, 'title': title, 'reason': f'ffmpeg返回码{process.returncode}'})
                        return None
            except Exception as e:
                if interrupt_manager.check_interrupt():
                    p('\n[中断] 用户中断下载', 'y')
                    return None
                p(f'[异常] 第{attempt+1}次: {e}', 'y')
                if attempt < 2:
                    time.sleep(2)
                else:
                    save_failed_download({'url': url, 'title': title, 'reason': str(e)})
                    return None
        return None
    
    # 检查是否存在临时文件（续传）
    if os.path.exists(tmp_path):
        resume_pos = os.path.getsize(tmp_path)
        p(f'[续传] 从 {resume_pos/1024/1024:.1f}MB 继续', 'y')
        debug_print(f'续传位置: {resume_pos} bytes')
    else:
        debug_print('首次下载')
    
    progress_style = get_progress_bar_style()
    
    p(f'[下载] {os.path.basename(vpath)}', 'c')
    
    for attempt in range(5):
        # ★★★ 检查中断 ★★★
        if interrupt_manager.check_interrupt():
            p('\n[中断] 用户中断下载', 'y')
            return None
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'}
            if resume_pos > 0:
                headers['Range'] = f'bytes={resume_pos}-'
            
            # ★★★ 使用更短的超时时间 ★★★
            r = requests.get(url, stream=True, timeout=(10, 30), headers=headers)
            
            if resume_pos > 0 and r.status_code == 206:
                mode = 'ab'
                p(f'[续传] 服务器支持断点续传', 'g')
            else:
                mode = 'wb'
                resume_pos = 0
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            total = int(r.headers.get('content-length', 0)) + resume_pos
            done = resume_pos
            last_percent = -1
            start_time = time.time()
            last_time = start_time
            last_done = done
            speed = 0
            
            debug_print(f'下载开始: 总大小={total} bytes, 已下载={done} bytes')
            
            filename = os.path.basename(vpath)
            chunk_count = 0
            
            with open(tmp_path, mode) as f:
                for chunk in r.iter_content(8192):
                    chunk_count += 1
                    
                    # ★★★ 问题2修复：每5个块检查一次中断（更快响应） ★★★
                    if chunk_count % 5 == 0 and interrupt_manager.check_interrupt():
                        p('\n[中断] 用户中断下载', 'y')
                        if os.path.exists(tmp_path):
                            p(f'[提示] 已下载 {os.path.getsize(tmp_path)/1024/1024:.1f}MB，临时文件已保留', 'y')
                        return None
                    
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        
                        # ★★★ 每500KB检查一次中断 ★★★
                        if done % (512 * 1024) < 8192:
                            if interrupt_manager.check_interrupt():
                                p('\n[中断] 用户中断下载', 'y')
                                if os.path.exists(tmp_path):
                                    p(f'[提示] 已下载 {os.path.getsize(tmp_path)/1024/1024:.1f}MB，临时文件已保留', 'y')
                                return None
                        
                        if total > 0:
                            percent = done * 100 // total
                            
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
                            
                            bar_length = 20
                            
                            if progress_style == 'modern':
                                filled = int(bar_length * percent // 100)
                                if percent >= 100:
                                    bar = '━' * bar_length
                                elif filled < bar_length:
                                    if percent > 0:
                                        bar = '━' * filled + '╸' + ' ' * (bar_length - filled - 1)
                                    else:
                                        bar = ' ' * bar_length
                                else:
                                    bar = '━' * bar_length
                            else:
                                filled = int(bar_length * percent // 100)
                                empty = bar_length - filled
                                bar = '█' * filled + '░' * empty
                            
                            done_mb = done / 1024 / 1024
                            total_mb = total / 1024 / 1024
                            
                            if total_mb < 10:
                                done_str = f"{done_mb:.2f}"
                                total_str = f"{total_mb:.2f}"
                            elif total_mb < 100:
                                done_str = f"{done_mb:.1f}"
                                total_str = f"{total_mb:.1f}"
                            else:
                                done_str = f"{done_mb:.0f}"
                                total_str = f"{total_mb:.0f}"
                            
                            filename_display = filename
                            if len(filename_display) > 30:
                                filename_display = filename_display[:27] + '...'
                            
                            line = f"\r{filename_display}  {bar}  {done_str}/{total_str} MB  {speed:.1f} MB/s  eta {eta}"
                            
                            if len(line) > 80:
                                filename_display = filename_display[:20] + '...'
                                line = f"\r{filename_display}  {bar}  {done_str}/{total_str} MB  {speed:.1f} MB/s  eta {eta}"
                            
                            sys.stderr.write(line)
                            sys.stderr.flush()
                            
                            last_percent = percent
            
            sys.stderr.write('\n')
            os.rename(tmp_path, vpath)
            size = os.path.getsize(vpath) / 1024 / 1024
            
            if size < 0.5:
                p(f'[警告] 文件过小({size:.1f}MB)，下载可能不完整', 'y')
                os.remove(vpath)
                save_failed_download({'url': url, 'title': title, 'reason': '文件过小'})
                return None
            
            p(f'[完成] {size:.1f}MB', 'g')
            report_stats("download", {"title": title, "size": round(size, 2)})
            debug_print(f'下载完成: {vpath}, 大小: {size:.2f}MB')
            
            try:
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except:
                pass
            
            return vpath
            
        except Exception as e:
            # ★★★ 检查是否是因为中断导致的异常 ★★★
            if interrupt_manager.check_interrupt():
                p('\n[中断] 用户中断下载', 'y')
                if os.path.exists(tmp_path):
                    p(f'[提示] 已下载 {os.path.getsize(tmp_path)/1024/1024:.1f}MB，临时文件已保留', 'y')
                return None
            
            p(f'\n[中断] 第{attempt+1}次: {str(e)[:80]}', 'y')
            debug_print(f'下载异常: {e}')
            if attempt < 4:
                if os.path.exists(tmp_path):
                    resume_pos = os.path.getsize(tmp_path)
                    debug_print(f'更新续传位置: {resume_pos} bytes')
                wait = (attempt + 1) * 2
                p(f'[等待] {wait}秒后重试...', 'y')
                time.sleep(wait)
            else:
                p('[错误] 下载失败', 'r')
                save_failed_download({'url': url, 'title': title, 'reason': str(e)})
                if os.path.exists(tmp_path):
                    p(f'[提示] 临时文件已保留: {tmp_path}', 'y')
                    p(f'[提示] 元数据已保留: {meta_path}', 'y')
                return None

# ==================== 封面处理功能 ====================

def crop_image_with_position(img, crop_position="center"):
    w, h = img.size
    size = min(w, h)
    
    if crop_position == "center":
        left = (w - size) // 2
        top = (h - size) // 2
    elif crop_position == "top":
        left = (w - size) // 2
        top = 0
    elif crop_position == "bottom":
        left = (w - size) // 2
        top = h - size
    elif crop_position == "left":
        left = 0
        top = (h - size) // 2
    elif crop_position == "right":
        left = w - size
        top = (h - size) // 2
    else:
        left = (w - size) // 2
        top = (h - size) // 2
    
    return img.crop((left, top, left + size, top + size))

def download_and_crop_cover(cover_url, output_path):
    try:
        if cover_url.startswith('//'):
            cover_url = 'https:' + cover_url
        elif not cover_url.startswith(('http://', 'https://')):
            cover_url = 'https://' + cover_url
        
        debug_print(f'封面下载URL: {cover_url}')
        resp = requests.get(cover_url, timeout=10)
        if resp.status_code != 200:
            debug_print(f'封面下载失败: HTTP {resp.status_code}')
            return False
        
        img = Image.open(io.BytesIO(resp.content))
        crop_position = get_cover_crop()
        cropped = crop_image_with_position(img, crop_position)
        cropped.save(output_path, 'JPEG', quality=90)
        debug_print(f'封面保存成功: {output_path} (裁剪位置: {crop_position})')
        return True
    except Exception as e:
        p(f'[封面处理失败] {e}', 'y')
        debug_print(f'封面处理异常: {e}')
        return False

def extract_cover_from_video(mp4_path, output_path):
    try:
        cmd = ['ffmpeg', '-i', mp4_path, '-vframes', '1', '-an', '-y', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            try:
                img = Image.open(output_path)
                crop_position = get_cover_crop()
                cropped = crop_image_with_position(img, crop_position)
                cropped.save(output_path, 'JPEG', quality=90)
                debug_print(f'从视频提取并裁剪封面成功: {output_path} (裁剪位置: {crop_position})')
            except Exception as e:
                debug_print(f'裁剪封面失败: {e}')
            return True
    except Exception as e:
        p(f'[提取封面失败] {e}', 'y')
        debug_print(f'提取封面异常: {e}')
    return False

def add_cover_to_mp3(mp3_path, cover_image_path):
    try:
        try:
            audio = MP3(mp3_path, ID3=ID3)
        except error:
            audio = MP3(mp3_path)
            audio.add_tags()
        
        # 读取封面图片
        with open(cover_image_path, 'rb') as f:
            image_data = f.read()
        
        apic = APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc='Cover',
            data=image_data
        )
        
        # 删除已有的封面
        try:
            if audio.tags is not None:
                audio.tags.delall('APIC')
        except:
            try:
                audio.tags = ID3()
            except:
                pass
        
        # 添加新封面
        try:
            if audio.tags is None:
                audio.add_tags()
            audio.tags.add(apic)
        except:
            audio = MP3(mp3_path)
            audio.add_tags()
            audio.tags.add(apic)
        
        audio.save(v2_version=3)
        debug_print(f'封面已嵌入MP3: {mp3_path}')
        return True
    except Exception as e:
        p(f'[添加封面失败] {e}', 'r')
        debug_print(f'封面添加异常: {e}')
        return False

def process_cover_for_mp3(mp3_path, mp4_path, cover_url, force=False):
    """为MP3添加封面，如果force=True则强制重新添加"""
    cover_added = False
    cover_tmp = mp3_path.replace('.mp3', '_cover.jpg')
    
    # 如果force=True，先检查封面是否存在，如果存在则先移除
    if force:
        try:
            audio = MP3(mp3_path, ID3=ID3)
            if audio.tags and audio.tags.getall('APIC'):
                audio.tags.delall('APIC')
                audio.save()
                debug_print(f'已移除旧封面: {mp3_path}')
        except:
            pass
    
    cover_mode = get_cover_mode()
    
    if cover_mode == "api" and cover_url and 'transparent.png' not in cover_url:
        if download_and_crop_cover(cover_url, cover_tmp):
            p('[封面] API封面下载成功', 'g')
            cover_added = True
    
    if not cover_added and cover_mode == "video":
        if extract_cover_from_video(mp4_path, cover_tmp):
            p('[封面] 视频截图成功', 'g')
            cover_added = True
    
    if cover_added:
        if add_cover_to_mp3(mp3_path, cover_tmp):
            p('[封面] 封面已嵌入', 'g')
        else:
            p('[封面] 嵌入失败', 'y')
        try:
            os.remove(cover_tmp)
        except:
            pass
    else:
        p('[封面] 无封面', 'y')

# ==================== MP3转换（含封面和歌词） ====================

def convert_to_mp3(mp4_path, cover_url=None, force_cover=False):
    if not os.path.exists(mp4_path):
        return None
    
    mp3_path = mp4_path.replace('.mp4', '.mp3')
    
    # 检查MP3是否存在，如果存在则跳过转换，但仍然尝试添加封面和歌词
    mp3_exists = False
    if should_skip_existing() and os.path.exists(mp3_path):
        size = os.path.getsize(mp3_path) / 1024 / 1024
        if size > 0.5:
            p(f'[跳过] MP3已存在: {os.path.basename(mp3_path)} ({size:.1f}MB)', 'y')
            mp3_exists = True
            # 即使MP3存在，仍然尝试添加封面
            settings = get_mp3_settings()
            if settings.get('cover_enabled', True) and cover_url:
                p('[封面] 检查并添加封面...', 'c')
                process_cover_for_mp3(mp3_path, mp4_path, cover_url)
            return mp3_path
    
    # 如果MP3不存在，进行转换
    c = 1
    while os.path.exists(mp3_path):
        mp3_path = mp4_path.replace('.mp4', f'_{c}.mp3')
        c += 1
    
    p(f'[转换] {os.path.basename(mp4_path)} -> MP3', 'c')
    debug_print(f'MP3输出路径: {mp3_path}')
    
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', mp4_path, '-vn', '-acodec', 'libmp3lame', '-ab', '192k', '-y', mp3_path],
            capture_output=True, text=True, timeout=600
        )
        
        if result.returncode == 0 and os.path.exists(mp3_path):
            m_size = os.path.getsize(mp3_path) / 1024 / 1024
            p(f'[成功] MP3: {m_size:.1f}MB', 'g')
            report_stats("convert", {"title": os.path.basename(mp4_path).replace('.mp4', '')})
            debug_print(f'MP3转换完成: {mp3_path}, 大小: {m_size:.2f}MB')
            
            settings = get_mp3_settings()
            if settings.get('cover_enabled', True) and cover_url:
                p('[封面] 正在添加...', 'c')
                process_cover_for_mp3(mp3_path, mp4_path, cover_url)
            
            return mp3_path
        else:
            p(f'[失败] 转换失败', 'r')
            debug_print(f'ffmpeg转换失败: {result.stderr}')
            return None
    except FileNotFoundError:
        p('[错误] ffmpeg 未安装，请运行: pkg install ffmpeg', 'r')
        return None
    except Exception as e:
        p(f'[错误] {e}', 'r')
        debug_print(f'转换异常: {e}')
        return None
# ==================== B站字幕相关功能 ====================

def get_bvid_from_input(user_input):
    bv_match = re.search(r'BV([0-9A-Za-z]{10})', user_input, re.IGNORECASE)
    if bv_match:
        return f'BV{bv_match.group(1)}'
    if re.match(r'^[0-9A-Za-z]{10}$', user_input):
        return f'BV{user_input}'
    return None

def get_cid_from_bvid(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get('code') != 0:
            return None
        return data.get('data', {}).get('cid')
    except:
        return None

def get_video_title(bvid):
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get('code') != 0:
            return None
        return data.get('data', {}).get('title', '未知标题')
    except:
        return None

def get_subtitle_list(bvid, cid):
    url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
        'Referer': 'https://www.bilibili.com/'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get('code') != 0:
            return None
        subtitles = data.get('data', {}).get('subtitle', {}).get('subtitles', [])
        return subtitles
    except:
        return None

def download_subtitle_json(subtitle_url):
    if subtitle_url.startswith('//'):
        subtitle_url = 'https:' + subtitle_url
    try:
        resp = requests.get(subtitle_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()
    except:
        return None

def convert_subtitle_to_lrc(subtitle_json):
    body = subtitle_json.get('body', [])
    if not body:
        return None
    lrc_lines = []
    for item in body:
        start = item.get('from', 0)
        text = item.get('content', '').strip()
        if not text:
            continue
        minutes = int(start // 60)
        seconds = int(start % 60)
        centiseconds = int((start % 1) * 100)
        timestamp = f"[{minutes:02d}:{seconds:02d}.{centiseconds:02d}]"
        lrc_lines.append(f"{timestamp}{text}")
    return '\n'.join(lrc_lines)

def get_bilibili_subtitle_lyrics(bvid, cid=None):
    try:
        if not cid:
            cid = get_cid_from_bvid(bvid)
            if not cid:
                return None
        
        subtitles = get_subtitle_list(bvid, cid)
        if not subtitles:
            return None
        
        preferred_langs = ['zh-CN', 'zh', 'ja', 'en']
        selected_sub = None
        
        for lang in preferred_langs:
            for sub in subtitles:
                if sub.get('lan', '').startswith(lang):
                    selected_sub = sub
                    break
            if selected_sub:
                break
        
        if not selected_sub:
            selected_sub = subtitles[0]
        
        subtitle_url = selected_sub.get('subtitle_url')
        if not subtitle_url:
            return None
        
        subtitle_json = download_subtitle_json(subtitle_url)
        if not subtitle_json:
            return None
        
        lrc_content = convert_subtitle_to_lrc(subtitle_json)
        return lrc_content
        
    except Exception as e:
        debug_print(f'获取B站字幕失败: {e}')
        return None

# ==================== B站搜索歌词（增强版） ====================

def clean_search_query(song_name, artist_name=None):
    special_chars = r'【】「」『』（）()〈〉《》［］﹁﹂『』〝〞'
    clean = song_name
    for char in special_chars:
        clean = clean.replace(char, ' ')
    
    clean = re.sub(r'feat\..*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'feat\..*?$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\(feat\..*?\)', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'【feat\..*?】', '', clean, flags=re.IGNORECASE)
    
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    if not clean:
        clean = re.sub(r'[【】「」『』（）()]', ' ', song_name)
        clean = re.sub(r'\s+', ' ', clean).strip()
    
    if artist_name:
        clean_artist = re.sub(r'[【】「」『』（）()]', ' ', artist_name)
        clean_artist = re.sub(r'\s+', ' ', clean_artist).strip()
        clean_artist = re.sub(r'feat\..*$', '', clean_artist, flags=re.IGNORECASE)
        
        if len(clean) < 3:
            return f"{clean_artist} {clean}"
    
    return clean

def search_bilibili_video_by_song(song_name, artist_name=None):
    try:
        clean_name = clean_search_query(song_name, artist_name)
        
        if len(clean_name) < 2:
            clean_name = song_name
        
        search_queries = [
            clean_name,
            re.sub(r'feat\..*$', '', clean_name, flags=re.IGNORECASE).strip(),
            clean_name.split('『')[0].strip(),
            clean_name.split('「')[0].strip(),
            clean_name.split('（')[0].strip(),
        ]
        
        search_queries = [q for q in dict.fromkeys(search_queries) if q and len(q) > 1]
        
        if re.search(r'[\u3040-\u30ff]', clean_name):
            jp_parts = re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]+', clean_name)
            if jp_parts:
                jp_query = ' '.join(jp_parts[:3])
                if jp_query and len(jp_query) > 1 and jp_query not in search_queries:
                    search_queries.append(jp_query)
        
        debug_print(f'B站搜索策略: {search_queries[:3]}')
        
        for query in search_queries[:3]:
            if len(query) > 30:
                query = query[:30]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
            }
            params = {
                'keyword': query,
                'page': 1,
                'pagesize': 10,
                'search_type': 'video'
            }
            
            search_url = "https://api.bilibili.com/x/web-interface/search/type"
            resp = requests.get(search_url, params=params, headers=headers, timeout=15)
            
            if resp.status_code != 200:
                continue
            
            data = resp.json()
            if data.get('code') != 0:
                continue
            
            videos = data.get('data', {}).get('result', [])
            if not videos:
                continue
            
            results = []
            for item in videos:
                bvid = item.get('bvid', '')
                title = item.get('title', '')
                title = re.sub(r'<em class="keyword">', '', title)
                title = re.sub(r'</em>', '', title)
                title = title.replace('&amp;', '&')
                
                score = 0
                song_clean = re.sub(r'[【】「」『』（）()]', ' ', song_name)
                song_clean = re.sub(r'\s+', ' ', song_clean).strip()
                if song_clean and song_clean.lower() in title.lower():
                    score += 50
                
                if artist_name:
                    artist_clean = re.sub(r'[【】「」『』（）()]', ' ', artist_name)
                    artist_clean = re.sub(r'\s+', ' ', artist_clean).strip()
                    if artist_clean and artist_clean.lower() in title.lower():
                        score += 30
                
                music_keywords = ['歌', '曲', 'music', 'song', '演唱', '翻唱', 'MV', '官方', 'OP', 'ED', 'PV', 'cover']
                for kw in music_keywords:
                    if kw in title:
                        score += 5
                
                if bvid:
                    results.append({
                        'bvid': bvid,
                        'title': title,
                        'score': score,
                        'author': item.get('author', ''),
                        'duration': item.get('duration', 0)
                    })
            
            if results:
                results.sort(key=lambda x: x['score'], reverse=True)
                if results[0]['score'] > 10:
                    return results
        
        return None
        
    except Exception as e:
        debug_print(f'B站搜索异常: {e}')
        return None

def search_lrc_bilibili(song_name, artist_name=None):
    try:
        debug_print(f'B站搜索: {song_name}')
        
        results = search_bilibili_video_by_song(song_name, artist_name)
        
        if not results:
            clean_song = re.sub(r'[【】「」『』（）()]', ' ', song_name)
            clean_song = re.sub(r'\s+', ' ', clean_song).strip()
            clean_song = re.sub(r'feat\..*$', '', clean_song, flags=re.IGNORECASE)
            clean_song = clean_song.strip()
            
            if clean_song and clean_song != song_name and len(clean_song) > 1:
                debug_print(f'尝试简化搜索: {clean_song}')
                results = search_bilibili_video_by_song(clean_song, None)
        
        if not results:
            jp_match = re.search(r'[\u3040-\u30ff\u4e00-\u9fff]+', song_name)
            if jp_match:
                jp_keyword = jp_match.group(0)
                if len(jp_keyword) > 1:
                    debug_print(f'尝试日文关键词: {jp_keyword}')
                    results = search_bilibili_video_by_song(jp_keyword, None)
        
        if not results:
            return None
        
        for item in results[:5]:
            bvid = item.get('bvid')
            if not bvid:
                continue
            
            debug_print(f'尝试BV: {bvid} - {item["title"][:30]}...')
            lrc = get_bilibili_subtitle_lyrics(bvid)
            if lrc:
                debug_print(f'✓ B站找到歌词: {item["title"][:30]}')
                return lrc
        
        return None
        
    except Exception as e:
        debug_print(f'B站搜索歌词异常: {e}')
        return None

# ==================== LRC 歌词搜索功能（多源） ====================

def convert_lrc_time_format(lrc_content):
    if not lrc_content:
        return lrc_content
    
    def convert_time(match):
        mm = match.group(1)
        ss = match.group(2)
        cc = match.group(3)
        return f"[{mm}:{ss}.{cc}]"
    
    pattern = r'\[(\d{2}):(\d{2}):(\d{2})\]'
    converted = re.sub(pattern, convert_time, lrc_content)
    
    pattern2 = r'\[(\d{1,2}):(\d{2}):(\d{2})\]'
    converted2 = re.sub(pattern2, convert_time, converted)
    
    if converted2 == lrc_content:
        if re.search(r'\[\d{2}:\d{2}\.\d{2}\]', lrc_content):
            return lrc_content
    
    return converted2

def fix_lrc_format(lrc_content):
    if not lrc_content:
        return lrc_content
    
    lines = lrc_content.split('\n')
    fixed_lines = []
    
    for line in lines:
        if re.search(r'\[\d{2}:\d{2}:\d{2}\]', line):
            def fix_time1(match):
                mm = match.group(1)
                ss = match.group(2)
                cc = match.group(3)
                return f"[{mm}:{ss}.{cc}]"
            line = re.sub(r'\[(\d{2}):(\d{2}):(\d{2})\]', fix_time1, line)
            line = re.sub(r'\[(\d{1,2}):(\d{2}):(\d{2})\]', fix_time1, line)
        elif re.search(r'\[\d{2}:\d{2},\d{2}\]', line):
            def fix_comma(match):
                mm = match.group(1)
                ss = match.group(2)
                cc = match.group(3)
                return f"[{mm}:{ss}.{cc}]"
            line = re.sub(r'\[(\d{2}):(\d{2}),(\d{2})\]', fix_comma, line)
            line = re.sub(r'\[(\d{1,2}):(\d{2}),(\d{2})\]', fix_comma, line)
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

# ==================== 歌词增强功能（罗马音+翻译）====================

def is_japanese_text(text):
    if not text:
        return False
    jp_pattern = r'[\u3040-\u309f\u30a0-\u30ff]'
    jp_chars = re.findall(jp_pattern, text)
    if len(jp_chars) > 0:
        return True
    return False

def is_japanese_lyrics(lrc_content):
    if not lrc_content:
        return False
    
    lines = lrc_content.split('\n')
    all_text = ''
    for line in lines:
        match = re.match(r'^\[\d{2}:\d{2}\.\d{2,3}\](.*)$', line)
        if match:
            lyric = match.group(1).strip()
            if lyric and not re.match(r'^(作词|作曲|编曲|演唱|歌手|album|artist|title)', lyric, re.IGNORECASE):
                all_text += lyric
    
    return is_japanese_text(all_text)

def is_english_text(text):
    if not text:
        return False
    en_pattern = r'[a-zA-Z]'
    en_chars = re.findall(en_pattern, text)
    if len(en_chars) == 0:
        return False
    total_chars = len([c for c in text if c.strip() and not c in '.,!?;:\'"-()[]{}'])
    if total_chars == 0:
        return False
    return len(en_chars) / total_chars > 0.5

def detect_lyrics_language(lrc_content):
    if not lrc_content:
        return 'zh'
    
    lines = lrc_content.split('\n')
    all_text = ''
    for line in lines:
        match = re.match(r'^\[\d{2}:\d{2}\.\d{2,3}\](.*)$', line)
        if match:
            lyric = match.group(1).strip()
            if lyric and not re.match(r'^(作词|作曲|编曲|演唱|歌手|album|artist|title)', lyric, re.IGNORECASE):
                all_text += lyric
    
    if is_japanese_text(all_text):
        return 'ja'
    
    if is_english_text(all_text):
        return 'en'
    
    return 'zh'

def is_foreign_lyrics(lrc_content):
    lang = detect_lyrics_language(lrc_content)
    return lang in ['ja', 'en']

def japanese_to_romaji(text):
    if not text or not text.strip():
        return text
    try:
        import pykakasi
        kks = pykakasi.kakasi()
        
        hira_result = kks.convert(text)
        hira_text = ''
        for item in hira_result:
            hira_text += item.get('hira', item.get('orig', ''))
        
        if not hira_text:
            return text
        
        syllables = []
        i = 0
        sokuon = False
        
        while i < len(hira_text):
            ch = hira_text[i]
            
            if ch == 'っ':
                sokuon = True
                i += 1
                continue
            
            if ch == 'ー':
                if syllables:
                    last = syllables[-1]
                    if last and last[-1] in 'aeiou':
                        syllables.append(last[-1])
                    else:
                        syllables.append('ー')
                else:
                    syllables.append('ー')
                i += 1
                continue
            
            syllable_chars = ch
            i += 1
            
            if i < len(hira_text) and hira_text[i] in 'ゃゅょぁぃぅぇぉ':
                syllable_chars += hira_text[i]
                i += 1
            
            if sokuon:
                syllable_chars = 'っ' + syllable_chars
                sokuon = False
            
            syl_result = kks.convert(syllable_chars)
            hepburn = ''
            for item in syl_result:
                hepburn += item.get('hepburn', '')
            if hepburn:
                syllables.append(hepburn)
        
        romaji = ' '.join(syllables)
        romaji = re.sub(r'\s+', ' ', romaji).strip()
        return romaji
        
    except ImportError:
        debug_print('pykakasi未安装，无法转换罗马音')
        return None
    except Exception as e:
        debug_print(f'罗马音转换失败: {e}')
        return None

def translate_to_chinese(text, source_lang='auto'):
    if not text or not text.strip():
        return text
    
    lang_map = {
        'ja': 'ja',
        'en': 'en',
        'auto': 'auto'
    }
    source = lang_map.get(source_lang, 'auto')
    
    youdao_type_map = {
        'ja': 'JA2ZH_CN',
        'en': 'EN2ZH_CN',
        'auto': 'AUTO'
    }
    youdao_type = youdao_type_map.get(source_lang, 'AUTO')
    
    try:
        langpair = f"{source}|zh-CN" if source != 'auto' else "autodetect|zh-CN"
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair={langpair}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            translation = data.get('responseData', {}).get('translatedText', '')
            if translation and translation != text:
                return translation
    except Exception as e:
        debug_print(f'MyMemory翻译失败: {e}')
    
    try:
        url = "https://fanyi.youdao.com/translate"
        params = {
            'type': youdao_type,
            'i': text,
            'doctype': 'json',
            'version': '2.1',
            'keyfrom': 'fanyi.web',
            'ue': 'UTF-8',
            'action': 'FY_BY_CLICKBUTTION',
            'typoResult': 'false'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Referer': 'https://fanyi.youdao.com/'
        }
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('errorCode') == 0:
                translation = data.get('translateResult', [])
                if translation and len(translation) > 0:
                    result = ''
                    for line in translation:
                        for item in line:
                            result += item.get('tgt', '')
                    if result and result != text:
                        return result
    except Exception as e:
        debug_print(f'有道翻译失败: {e}')
    
    return None

def get_lyric_enhance_settings():
    config = load_config()
    enhance = config.get('lyric_enhance', {})
    return {
        'enabled': enhance.get('enabled', True),
        'romaji': enhance.get('romaji', True),
        'translation': enhance.get('translation', True)
    }

def save_lyric_enhance_settings(enabled=None, romaji=None, translation=None):
    config = load_config()
    if 'lyric_enhance' not in config:
        config['lyric_enhance'] = {
            'enabled': True,
            'romaji': True,
            'translation': True
        }
    if enabled is not None:
        config['lyric_enhance']['enabled'] = enabled
    if romaji is not None:
        config['lyric_enhance']['romaji'] = romaji
    if translation is not None:
        config['lyric_enhance']['translation'] = translation
    save_config(config)

def lyric_enhance_settings_menu():
    while True:
        settings = get_lyric_enhance_settings()
        
        print("\n" + "=" * 50)
        p("       🎵 歌词增强设置", 'c')
        print("=" * 50)
        print(f"  歌词增强功能: {'✅ 开启' if settings['enabled'] else '❌ 关闭'}")
        print(f"  罗马音显示:   {'✅ 开启' if settings['romaji'] else '❌ 关闭'}")
        print(f"  中文翻译:     {'✅ 开启' if settings['translation'] else '❌ 关闭'}")
        print("-" * 50)
        print("说明：自动检测日文/英文歌词，添加中文翻译")
        print("  - 日文歌词：罗马音 + 原文 + 中文翻译")
        print("  - 英文歌词：原文 + 中文翻译")
        print("  - 罗马音需要安装 pykakasi 库（仅日文需要）")
        print("  - 翻译使用在线API，需要网络连接")
        print("  - 中文歌词不受影响")
        print("-" * 50)
        print("  [1] 开关歌词增强功能")
        print("  [2] 开关罗马音显示")
        print("  [3] 开关中文翻译")
        print("  [q] 返回")
        print("=" * 50)
        
        choice = input("\n请选择 [1-3/q]: ").strip().lower()
        
        if choice in ('q', '0'):
            return
        elif choice == '1':
            new_enabled = not settings['enabled']
            save_lyric_enhance_settings(enabled=new_enabled)
            if new_enabled:
                p("歌词增强功能已开启", 'g')
                try:
                    import pykakasi
                    p("pykakasi 库已安装，罗马音功能可用", 'g')
                except ImportError:
                    p("⚠️  pykakasi 未安装，罗马音功能将不可用", 'y')
                    print("   可运行: pip install pykakasi")
            else:
                p("歌词增强功能已关闭", 'g')
        elif choice == '2':
            new_romaji = not settings['romaji']
            save_lyric_enhance_settings(romaji=new_romaji)
            if new_romaji:
                p("罗马音显示已开启", 'g')
            else:
                p("罗马音显示已关闭", 'g')
        elif choice == '3':
            new_translation = not settings['translation']
            save_lyric_enhance_settings(translation=new_translation)
            if new_translation:
                p("中文翻译已开启", 'g')
            else:
                p("中文翻译已关闭", 'g')
        else:
            p("无效选项", 'y')
        
        input("\n按回车键继续...")

def enhance_lrc_with_romaji_and_translation(lrc_content):
    if not lrc_content:
        return lrc_content
    
    settings = get_lyric_enhance_settings()
    if not settings['enabled']:
        return lrc_content
    
    lang = detect_lyrics_language(lrc_content)
    if lang == 'zh':
        return lrc_content
    
    lang_names = {
        'ja': '日文',
        'en': '英文'
    }
    lang_name = lang_names.get(lang, '外文')
    
    p(f'[增强] 检测到{lang_name}歌词，正在添加翻译...', 'c')
    
    lines = lrc_content.split('\n')
    enhanced_lines = []
    processed_count = 0
    
    for line in lines:
        match = re.match(r'^(\[\d{2}:\d{2}\.\d{2,3}\])(.*)$', line)
        if match:
            timestamp = match.group(1)
            lyric = match.group(2).strip()
            
            if not lyric:
                enhanced_lines.append(line)
                continue
            
            if re.match(r'^(作词|作曲|编曲|演唱|歌手|album|artist|title)', lyric, re.IGNORECASE):
                enhanced_lines.append(line)
                continue
            
            added = False
            
            if lang == 'ja':
                if settings['romaji']:
                    romaji = japanese_to_romaji(lyric)
                    if romaji:
                        enhanced_lines.append(f"{timestamp}{romaji}")
                        added = True
                
                enhanced_lines.append(line)
                
                if settings['translation']:
                    translation = translate_to_chinese(lyric, source_lang='ja')
                    if translation:
                        enhanced_lines.append(f"{timestamp}{translation}")
                        added = True
                
                if added:
                    processed_count += 1
                    
            elif lang == 'en':
                enhanced_lines.append(line)
                
                if settings['translation']:
                    translation = translate_to_chinese(lyric, source_lang='en')
                    if translation:
                        enhanced_lines.append(f"{timestamp}{translation}")
                        added = True
                
                if added:
                    processed_count += 1
                    
            else:
                enhanced_lines.append(line)
        else:
            enhanced_lines.append(line)
    
    if processed_count > 0:
        p(f'[增强] 已处理 {processed_count} 行歌词', 'g')
    
    return '\n'.join(enhanced_lines)

def search_lrc_lrclib(song_name, artist_name=None):
    try:
        query = song_name
        if artist_name:
            query = f"{artist_name} {song_name}"
        
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://lrclib.net/api/search?q={encoded_query}"
        
        response = requests.get(search_url, timeout=15)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if not data or len(data) == 0:
            return None
        
        if artist_name:
            for item in data:
                if artist_name.lower() in item.get('artistName', '').lower():
                    lrc_content = get_lrc_by_id(item.get('id'))
                    if lrc_content:
                        return lrc_content
        
        first_result = data[0]
        lrc_content = get_lrc_by_id(first_result.get('id'))
        return lrc_content
        
    except Exception as e:
        debug_print(f'LRCLIB异常: {e}')
        return None

def get_lrc_by_id(lrc_id):
    try:
        if not lrc_id:
            return None
        
        url = f"https://lrclib.net/api/get/{lrc_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        lrc_content = data.get('syncedLyrics')
        
        if not lrc_content:
            lrc_content = data.get('plainLyrics')
        
        if lrc_content and len(lrc_content.strip()) > 10:
            return lrc_content.strip()
        
        return None
        
    except Exception as e:
        debug_print(f'获取歌词异常: {e}')
        return None

def search_lrc_netease(song_name, artist_name=None):
    try:
        query = song_name
        if artist_name:
            query = f"{artist_name} {song_name}"
        
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://music.163.com/api/search/get/web?csrf_token=&hlpretag=&hlposttag=&s={encoded_query}&type=1&offset=0&total=true&limit=10"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://music.163.com/',
            'Cookie': 'appver=2.0.2'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        songs = data.get('result', {}).get('songs', [])
        
        if not songs:
            return None
        
        best_song = None
        if artist_name:
            for song in songs:
                artists = song.get('artists', [])
                for artist in artists:
                    if artist_name.lower() in artist.get('name', '').lower():
                        best_song = song
                        break
                if best_song:
                    break
        
        if not best_song:
            best_song = songs[0]
        
        song_id = best_song.get('id')
        if not song_id:
            return None
        
        lyric_url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
        lyric_resp = requests.get(lyric_url, headers=headers, timeout=10)
        
        if lyric_resp.status_code != 200:
            return None
        
        lyric_data = lyric_resp.json()
        lrc_content = lyric_data.get('lrc', {}).get('lyric', '')
        
        if lrc_content and len(lrc_content.strip()) > 10:
            converted = convert_lrc_time_format(lrc_content.strip())
            return converted
        
        return None
        
    except Exception as e:
        debug_print(f'网易云搜索异常: {e}')
        return None

def search_lrc_qqmusic(song_name, artist_name=None):
    try:
        query = song_name
        if artist_name:
            query = f"{artist_name} {song_name}"
        
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?ct=24&qqmusic_ver=1298&new_json=1&remoteplace=txt.yqq.song&searchid=1&t=0&aggr=1&cr=1&catZhida=1&lossless=0&flag_qc=0&p=1&n=10&w={encoded_query}&g_tk=5381&loginUin=0&hostUin=0&format=json&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq.json&needNewCode=0"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://y.qq.com/',
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        songs = data.get('data', {}).get('song', {}).get('list', [])
        
        if not songs:
            return None
        
        best_song = None
        if artist_name:
            for song in songs:
                singers = song.get('singer', [])
                for singer in singers:
                    if artist_name.lower() in singer.get('name', '').lower():
                        best_song = song
                        break
                if best_song:
                    break
        
        if not best_song:
            best_song = songs[0]
        
        song_mid = best_song.get('mid')
        if not song_mid:
            return None
        
        lyric_url = f"https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg?songmid={song_mid}&g_tk=5381&loginUin=0&hostUin=0&format=json&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq.json&needNewCode=0"
        
        lyric_resp = requests.get(lyric_url, headers=headers, timeout=10)
        
        if lyric_resp.status_code != 200:
            return None
        
        lyric_data = lyric_resp.json()
        lrc_content = lyric_data.get('lyric', '')
        
        if lrc_content:
            try:
                decoded = base64.b64decode(lrc_content).decode('utf-8')
                if decoded and len(decoded.strip()) > 10:
                    return decoded.strip()
            except:
                pass
        
        return None
        
    except Exception as e:
        debug_print(f'QQ音乐搜索异常: {e}')
        return None

def search_lrc_musixmatch(song_name, artist_name=None):
    try:
        query = song_name
        if artist_name:
            query = f"{artist_name} {song_name}"
        
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://api.musixmatch.com/ws/1.1/track.search?q={encoded_query}&page_size=5&page=1&s_track_rating=desc&apikey=0e3c3f7b7b4d8e9f7a6b5c4d3e2f1a0b"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
        except requests.exceptions.Timeout:
            debug_print('Musixmatch超时，跳过')
            return None
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if data.get('message', {}).get('header', {}).get('status_code') != 200:
            return None
        
        tracks = data.get('message', {}).get('body', {}).get('track_list', [])
        
        if not tracks:
            return None
        
        best_track = None
        if artist_name:
            for track_info in tracks:
                track = track_info.get('track', {})
                track_artist = track.get('artist_name', '')
                if artist_name.lower() in track_artist.lower():
                    best_track = track
                    break
        
        if not best_track:
            best_track = tracks[0].get('track', {})
        
        track_id = best_track.get('track_id')
        if not track_id:
            return None
        
        lyric_url = f"https://api.musixmatch.com/ws/1.1/track.lyrics.get?track_id={track_id}&apikey=0e3c3f7b7b4d8e9f7a6b5c4d3e2f1a0b"
        
        try:
            lyric_resp = requests.get(lyric_url, headers=headers, timeout=10)
        except requests.exceptions.Timeout:
            debug_print('Musixmatch超时，跳过')
            return None
        
        if lyric_resp.status_code != 200:
            return None
        
        lyric_data = lyric_resp.json()
        
        if lyric_data.get('message', {}).get('header', {}).get('status_code') != 200:
            return None
        
        lyrics_body = lyric_data.get('message', {}).get('body', {}).get('lyrics', {})
        lrc_content = lyrics_body.get('lyrics_body', '')
        
        if lrc_content and len(lrc_content.strip()) > 10:
            return lrc_content.strip()
        
        return None
        
    except Exception as e:
        debug_print(f'Musixmatch搜索异常: {e}')
        return None

def search_lrc_by_priority(song_name, artist_name=None, priority_apis=None):
    if priority_apis is None:
        priority_apis = get_enabled_apis_sorted()
    
    api_functions = {
        'netease': ('网易云音乐', lambda: search_lrc_netease(song_name, artist_name)),
        'bilibili': ('B站搜索', lambda: search_lrc_bilibili(song_name, artist_name)),
        'qqmusic': ('QQ音乐', lambda: search_lrc_qqmusic(song_name, artist_name)),
        'musixmatch': ('Musixmatch', lambda: search_lrc_musixmatch(song_name, artist_name)),
        'lrclib': ('LRCLIB', lambda: search_lrc_lrclib(song_name, artist_name)),
    }
    
    for api_key in priority_apis:
        if api_key in api_functions:
            name, func = api_functions[api_key]
            try:
                debug_print(f'尝试 {name}...')
                result = func()
                if result:
                    debug_print(f'✓ {name} 找到歌词')
                    return result
            except Exception as e:
                debug_print(f'{name} 失败: {e}')
                continue
            time.sleep(0.3)
    
    return None

def extract_artist_from_filename(filename):
    name = os.path.splitext(filename)[0]
    
    separators = [' - ', ' — ', ' – ', '·', '|', '，', '、', '/']
    
    for sep in separators:
        if sep in name:
            parts = name.split(sep, 1)
            if len(parts) == 2:
                artist = parts[0].strip()
                song = parts[1].strip()
                if len(artist) < 30 and len(song) > 1:
                    return artist, song
    
    match = re.search(r'^(.+?)\s+[-—]\s+(.+)$', name)
    if match:
        artist = match.group(1).strip()
        song = match.group(2).strip()
        if len(artist) < 30 and len(song) > 1:
            return artist, song
    
    match = re.search(r'\((.+?)\)', name)
    if match:
        artist = match.group(1)
        song = name.replace(f'({artist})', '').strip()
        if len(artist) < 30 and len(song) > 1:
            return artist, song
    
    match = re.search(r'feat\.\s*(.+?)$', name, re.IGNORECASE)
    if match:
        artist = match.group(1).strip()
        song = name[:match.start()].strip()
        if len(artist) < 30 and len(song) > 1:
            return artist, song
    
    match = re.search(r'【(.+?)】', name)
    if match:
        artist = match.group(1).strip()
        song = name.replace(f'【{artist}】', '').strip()
        if len(artist) < 30 and len(song) > 1:
            return artist, song
    
    match = re.search(r'［(.+?)］', name)
    if match:
        artist = match.group(1).strip()
        song = name.replace(f'［{artist}］', '').strip()
        if len(artist) < 30 and len(song) > 1:
            return artist, song
    
    return None, name

def download_lrc_for_mp3(mp3_path, force=False):
    try:
        if not os.path.exists(mp3_path):
            return False, "文件不存在"
        
        if mp3_path.lower().endswith('.lrc'):
            return False, "已是LRC文件"
        
        dir_path = os.path.dirname(mp3_path)
        filename = os.path.basename(mp3_path)
        name_without_ext = os.path.splitext(filename)[0]
        lrc_path = os.path.join(dir_path, f"{name_without_ext}.lrc")
        
        if os.path.exists(lrc_path) and not force:
            return True, "已存在"
        
        artist = None
        song_title = name_without_ext
        
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, TPE1, TIT2
            
            audio = MP3(mp3_path, ID3=ID3)
            
            if 'TPE1' in audio.tags:
                artist = str(audio.tags['TPE1'])
            if 'TIT2' in audio.tags:
                title = str(audio.tags['TIT2'])
                if title and len(title) > 1:
                    song_title = title
                    
        except Exception as e:
            debug_print(f'读取MP3标签失败: {e}')
        
        if not artist or artist == song_title:
            extracted_artist, extracted_song = extract_artist_from_filename(name_without_ext)
            if extracted_artist and extracted_song:
                artist = extracted_artist
                song_title = extracted_song
        
        display_title = song_title[:40] + '...' if len(song_title) > 40 else song_title
        p(f'[歌词搜索] {display_title}', 'c')
        
        priority_apis = get_enabled_apis_sorted()
        lrc_content = None
        
        if artist:
            lrc_content = search_lrc_by_priority(song_title, artist, priority_apis)
        
        if not lrc_content:
            clean_title = re.sub(r'[【】「」『』（）()]', ' ', song_title)
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            clean_title = re.sub(r'feat\..*$', '', clean_title, flags=re.IGNORECASE)
            clean_title = clean_title.strip()
            
            if clean_title and clean_title != song_title and len(clean_title) > 1:
                debug_print(f'尝试清理后搜索: {clean_title}')
                lrc_content = search_lrc_by_priority(clean_title, None, priority_apis)
        
        if not lrc_content:
            jp_match = re.search(r'[\u3040-\u30ff\u4e00-\u9fff]+', song_title)
            if jp_match:
                jp_keyword = jp_match.group(0)
                if len(jp_keyword) > 1:
                    debug_print(f'尝试关键词搜索: {jp_keyword}')
                    lrc_content = search_lrc_by_priority(jp_keyword, None, priority_apis)
        
        if not lrc_content:
            raw_name = os.path.splitext(os.path.basename(mp3_path))[0]
            raw_name = re.sub(r'[【】「」『』（）()]', ' ', raw_name)
            raw_name = re.sub(r'\s+', ' ', raw_name).strip()
            raw_name = re.sub(r'feat\..*$', '', raw_name, flags=re.IGNORECASE)
            raw_name = raw_name.strip()
            
            if raw_name and raw_name != song_title and raw_name != clean_title and len(raw_name) > 1:
                debug_print(f'尝试原始文件名: {raw_name}')
                lrc_content = search_lrc_by_priority(raw_name, None, priority_apis)
        
        if not lrc_content:
            first_word = song_title.split()[0] if song_title.split() else None
            if first_word and len(first_word) > 1:
                debug_print(f'尝试首词搜索: {first_word}')
                lrc_content = search_lrc_by_priority(first_word, None, priority_apis)
        
        if not lrc_content:
            return False, "未找到歌词"
        
        lrc_content = fix_lrc_format(lrc_content)
        
        lrc_content = enhance_lrc_with_romaji_and_translation(lrc_content)
        
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(lrc_content)
        
        return True, "下载成功"
        
    except Exception as e:
        debug_print(f'下载LRC异常: {e}')
        return False, str(e)

def batch_download_lrc(folder_path, force=False):
    if not os.path.exists(folder_path):
        return 0, 0, 0, "文件夹不存在"
    
    mp3_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.mp3'):
                mp3_files.append(os.path.join(root, file))
    
    if not mp3_files:
        return 0, 0, 0, "未找到MP3文件"
    
    p(f'\n[开始] 找到 {len(mp3_files)} 个MP3文件', 'c')
    
    success = 0
    exists = 0
    failed = 0
    failed_list = []
    
    for idx, mp3_path in enumerate(mp3_files, 1):
        filename = os.path.basename(mp3_path)
        p(f'\n[{idx}/{len(mp3_files)}] {filename}', 'c')
        
        result, message = download_lrc_for_mp3(mp3_path, force)
        
        if result and message == "已存在":
            p(f'  [跳过] LRC已存在', 'y')
            exists += 1
        elif result:
            p(f'  [成功] {message}', 'g')
            success += 1
        else:
            p(f'  [失败] {message}', 'r')
            failed += 1
            failed_list.append(filename)
        
        if idx % 5 == 0:
            time.sleep(1)
    
    return success, exists, failed, failed_list

def process_lrc_download():
    print("\n" + "=" * 60)
    p("       🎵 LRC 歌词批量下载工具", 'c')
    print("=" * 60)
    print("功能说明：")
    print("  1. 扫描指定文件夹中的所有 MP3 文件")
    print("  2. 从多个音乐库搜索歌词：")
    
    enabled_apis = get_enabled_apis_sorted()
    api_names = {
        'bilibili': 'B站搜索',
        'netease': '网易云音乐',
        'qqmusic': 'QQ音乐',
        'musixmatch': 'Musixmatch',
        'lrclib': 'LRCLIB'
    }
    for api in enabled_apis:
        print(f"     - {api_names.get(api, api)}")
    
    print("  3. 自动下载并保存为 .lrc 文件")
    print("  4. 自动转换时间格式 [mm:ss:cc] → [mm:ss.cc]")
    print("  5. 歌词文件与 MP3 文件同名，Poweramp 可自动识别")
    print("=" * 60)
    print()
    print("提示：输入 'm' 进入API设置，自定义搜索源")
    print("=" * 60)
    
    while True:
        folder_input = input("\n请输入要检测的文件夹路径 (直接回车使用默认下载目录, m=API设置): ").strip()
        
        if folder_input.lower() == 'm':
            lrc_api_settings_menu()
            continue
        
        if not folder_input:
            folder_path = get_download_path()
            p(f'使用默认目录: {folder_path}', 'y')
        else:
            if folder_input.startswith('~'):
                folder_path = os.path.expanduser(folder_input)
            else:
                folder_path = folder_input
        
        if os.path.exists(folder_path):
            break
        else:
            p(f'[错误] 文件夹不存在: {folder_path}', 'r')
            print("\n选项:")
            print("  [回车] 重新输入路径")
            print("  [m] 进入API设置")
            print("  [q] 返回主菜单")
            choice = input("\n请选择: ").strip().lower()
            if choice in ('q', '0'):
                return
            elif choice == 'm':
                lrc_api_settings_menu()
                continue
    
    mp3_count = 0
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.mp3'):
                mp3_count += 1
    
    if mp3_count == 0:
        p('[提示] 该文件夹中没有找到MP3文件', 'y')
        input("\n按回车键返回主菜单...")
        return
    
    p(f'\n[检测] 找到 {mp3_count} 个MP3文件', 'g')
    
    print("\n" + "=" * 50)
    p("       下载模式", 'c')
    print("=" * 50)
    print("  [1] 仅下载缺失的歌词 (跳过已存在的)")
    print("  [2] 强制重新下载所有歌词 (覆盖已存在的)")
    print("  [q] 返回主菜单")
    print("=" * 50)
    
    mode_choice = input("\n请选择 [1-2/q]: ").strip().lower()
    
    if mode_choice in ('q', '0'):
        return
    elif mode_choice == '2':
        force = True
        p('[模式] 强制重新下载', 'y')
    else:
        force = False
        p('[模式] 仅下载缺失的歌词', 'g')
    
    print("\n[提示] 直接回车 = 开始处理")
    confirm = input('\n开始下载歌词？(直接回车=是, 输入0=否): ').strip()
    if confirm == '0':
        p('[取消]', 'y')
        return
    
    print("\n" + "=" * 50)
    p("       开始下载歌词", 'c')
    print("=" * 50)
    print("提示：按 Ctrl+C 可中断处理")
    print("=" * 50)
    
    start_time = time.time()
    
    try:
        success, exists, failed, failed_list = batch_download_lrc(folder_path, force)
    except KeyboardInterrupt:
        p('\n[中断] 用户取消', 'y')
        input("\n按回车键返回主菜单...")
        return
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    p("       下载完成", 'c')
    print("=" * 60)
    print(f"  处理时间: {elapsed_time:.1f} 秒")
    print(f"  新下载:   {success} 个")
    print(f"  已存在:   {exists} 个")
    print(f"  失败:     {failed} 个")
    
    if failed_list:
        print("\n失败的歌曲:")
        for f in failed_list[:20]:
            print(f"  - {f}")
        if len(failed_list) > 20:
            print(f"  ... 共 {len(failed_list)} 个失败")
    
    print("=" * 60)
    p(f'[位置] {folder_path}', 'c')
    
    print("\n提示：")
    print("  - LRC 文件与 MP3 文件在同一个文件夹")
    print("  - 文件名相同，Poweramp 可自动识别")
    print("  - 输入 'm' 可调整API优先级")
    
    input("\n按回车键返回主菜单...")

def process_bilibili_subtitle_to_lrc():
    print("\n" + "=" * 60)
    p("       🎵 从B站视频生成LRC歌词", 'c')
    print("=" * 60)
    print("功能说明：")
    print("  1. 输入B站视频链接或BV号")
    print("  2. 自动获取视频的字幕（如有多个可选择）")
    print("  3. 转换为标准LRC格式，与MP3配套使用")
    print("=" * 60)

    user_input = input("\n请输入B站视频链接或BV号: ").strip()
    if not user_input:
        p('未输入内容', 'y')
        return

    bvid = get_bvid_from_input(user_input)
    if not bvid:
        p('无法识别BV号，请检查输入（需包含BV或10位字符）', 'r')
        return

    p(f'[检测] BV号: {bvid}', 'c')

    cid = get_cid_from_bvid(bvid)
    if not cid:
        p('获取视频信息失败，请检查网络或视频是否存在', 'r')
        return

    title = get_video_title(bvid)
    if title:
        p(f'[标题] {title}', 'g')
    else:
        title = 'bilibili_video'

    subtitles = get_subtitle_list(bvid, cid)
    if not subtitles:
        p('该视频没有字幕，无法生成LRC', 'y')
        input("\n按回车键返回...")
        return

    print("\n找到以下字幕：")
    for idx, sub in enumerate(subtitles, 1):
        lang = sub.get('lan', '未知语言')
        desc = sub.get('subtitle', {}).get('description', '')
        print(f"  {idx}. 语言: {lang}  {desc}")

    if len(subtitles) == 1:
        choice = 1
    else:
        choice_input = input("\n请选择要使用的字幕序号: ").strip()
        if not choice_input.isdigit():
            p('无效输入', 'y')
            return
        choice = int(choice_input)
        if choice < 1 or choice > len(subtitles):
            p('序号超出范围', 'y')
            return

    selected = subtitles[choice - 1]
    subtitle_url = selected.get('subtitle_url')
    if not subtitle_url:
        p('字幕URL无效', 'r')
        return

    p('[下载字幕] 正在获取字幕内容...', 'c')
    subtitle_json = download_subtitle_json(subtitle_url)
    if not subtitle_json:
        p('下载字幕失败，请检查网络', 'r')
        return

    lrc_content = convert_subtitle_to_lrc(subtitle_json)
    if not lrc_content:
        p('字幕内容为空，无法生成LRC', 'y')
        return

    print("\n保存选项：")
    print("  [1] 保存到下载目录（自动命名）")
    print("  [2] 指定MP3文件所在目录（同名）")
    print("  [3] 手动指定保存路径")
    save_choice = input("\n请选择 [1-3]: ").strip()

    save_path = None
    if save_choice == '1':
        save_dir = get_download_path()
        filename = re.sub(r'[\\/:*?"<>|]', '_', title) + '.lrc'
        save_path = os.path.join(save_dir, filename)
    elif save_choice == '2':
        mp3_path = input("请输入MP3文件的完整路径: ").strip()
        if not mp3_path or not os.path.exists(mp3_path):
            p('MP3文件不存在', 'r')
            return
        dir_path = os.path.dirname(mp3_path)
        base = os.path.splitext(os.path.basename(mp3_path))[0]
        save_path = os.path.join(dir_path, base + '.lrc')
        if os.path.exists(save_path):
            overwrite = input("LRC文件已存在，是否覆盖？(y/n): ").strip().lower()
            if overwrite != 'y':
                p('取消保存', 'y')
                return
    elif save_choice == '3':
        save_path = input("请输入完整保存路径（含文件名，建议.lrc结尾）: ").strip()
        if not save_path:
            p('未输入路径', 'y')
            return
        if not save_path.endswith('.lrc'):
            save_path += '.lrc'
        dir_path = os.path.dirname(save_path)
        if dir_path and not os.path.exists(dir_path):
            p('目录不存在，请先创建', 'r')
            return
    else:
        p('无效选项', 'y')
        return

    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(lrc_content)
        p(f'[完成] LRC文件已保存: {save_path}', 'g')
        print("\n提示：将LRC文件与MP3放在同一目录且同名，Poweramp可自动识别滚动歌词。")
    except Exception as e:
        p(f'[错误] 保存失败: {e}', 'r')

    input("\n按回车键返回主菜单...")

def download_mp3_with_settings(mp4_path, cover_url=None, bvid=None, cid=None, title=None, artist=None, force=False):
    """下载MP3，如果force=True则强制重新处理封面和歌词"""
    settings = get_mp3_settings()
    
    mp3_path = convert_to_mp3(mp4_path, cover_url if settings.get('cover_enabled', True) else None)
    if not mp3_path:
        return None
    
    # 检查是否需要强制处理歌词
    if force:
        # 删除旧的lrc文件
        lrc_path = mp3_path.replace('.mp3', '.lrc')
        if os.path.exists(lrc_path):
            try:
                os.remove(lrc_path)
                debug_print(f'已删除旧歌词: {lrc_path}')
            except:
                pass
    
    if settings.get('lyric_enabled', True):
        lrc_path = mp3_path.replace('.mp3', '.lrc')
        
        if os.path.exists(lrc_path) and not force:
            p('[歌词] 已存在', 'y')
            return mp3_path
        
        song_title = title
        if not song_title:
            song_title = os.path.splitext(os.path.basename(mp4_path))[0]
        
        if not artist:
            extracted_artist, _ = extract_artist_from_filename(os.path.basename(mp4_path))
            artist = extracted_artist
        
        p('[歌词] 正在获取...', 'c')
        
        priority_apis = get_enabled_apis_sorted()
        lrc_content = search_lrc_by_priority(song_title, artist, priority_apis)
        
        if not lrc_content and artist:
            debug_print('带歌手搜索失败，尝试仅搜索歌名')
            lrc_content = search_lrc_by_priority(song_title, None, priority_apis)
        
        if lrc_content:
            try:
                lrc_content = enhance_lrc_with_romaji_and_translation(lrc_content)
                with open(lrc_path, 'w', encoding='utf-8') as f:
                    f.write(lrc_content)
                p('[歌词] 下载成功', 'g')
            except Exception as e:
                p(f'[歌词] 保存失败: {e}', 'r')
        else:
            p('[歌词] 未找到', 'y')
    
    return mp3_path
# ==================== 进度条样式设置菜单 ====================

def progress_bar_style_menu():
    print("\n" + "=" * 50)
    p("       进度条样式设置", 'c')
    print("=" * 50)
    
    current_style = get_progress_bar_style()
    print(f"当前样式: {'现代样式 (╸━━━)' if current_style == 'modern' else '经典样式 (█░)'}")
    print("\n选择进度条样式：")
    print("  [1] 现代样式 (╸━━━) - 类似pip的圆角进度条")
    print("  [2] 经典样式 (█░) - 传统的方块进度条")
    print("  [q] 返回")
    print("=" * 50)
    
    choice = input("\n请选择 [1-2/q]: ").strip().lower()
    
    config = load_config()
    if choice == '1':
        config['progress_bar_style'] = 'modern'
        if save_config(config):
            p("已切换为现代样式", 'g')
        else:
            p("保存配置失败", 'r')
    elif choice == '2':
        config['progress_bar_style'] = 'classic'
        if save_config(config):
            p("已切换为经典样式", 'g')
        else:
            p("保存配置失败", 'r')
    elif choice in ('q', '0'):
        return
    else:
        p("无效选项", 'y')
    
    input("\n按回车键继续...")

# ==================== 分P选择功能（带翻页和跳转） ====================

def show_page_selection_menu(pages_info, title):
    """显示分P选择菜单（带翻页和跳转功能）"""
    config = load_config()
    key_prev = config.get('key_prev', 'a')
    key_next = config.get('key_next', 'd')
    key_goto = config.get('key_goto', 'g')
    
    current_page = 0
    page_size = 20
    total_pages = (len(pages_info) + page_size - 1) // page_size
    selected_pages = []
    
    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(pages_info))
        current_results = pages_info[start_idx:end_idx]
        
        print("\n" + "=" * 60)
        p(f"       【分P选择】{title}", 'c')
        print("=" * 60)
        print(f"共 {len(pages_info)} 个分P (第 {current_page + 1}/{total_pages} 页)")
        print("-" * 60)
        
        # 倒序显示
        reversed_results = list(reversed(current_results))
        
        for i, page in enumerate(reversed_results, 1):
            display_num = len(current_results) - i + 1
            actual_page_num = end_idx - i + 1
            duration_str = format_time(page['duration']) if page['duration'] else '未知时长'
            part_title = page['part'][:55] + '...' if len(page['part']) > 55 else page['part']
            selected_mark = '✅' if actual_page_num in selected_pages else '  '
            print(f"  {selected_mark} {display_num}. {part_title}")
            print(f"     时长: {duration_str}  |  P{page['page']} (P{actual_page_num})")
            print("-" * 56)
        
        print("\n" + "=" * 60)
        p(f"       分P列表 (第 {current_page + 1}/{total_pages} 页)", 'c')
        print("=" * 60)
        print(f"操作说明:")
        print(f"  输入数字 [1-{len(current_results)}] 选择对应序号的分P")
        print(f"  输入 'm' 进入多选模式 (输入序号，用空格分隔)")
        print(f"  输入 'all' 选择所有 {len(pages_info)} 个分P")
        print(f"  输入 'c' 确认并开始解析")
        if selected_pages:
            print(f"  [提示] 当前已选中 {len(selected_pages)} 个分P")
        print(f"  输入 '0' 跳过此视频")
        print(f"  输入 'q' 返回主菜单")
        print(f"  输入 {key_prev} 上一页  |  输入 {key_next} 下一页")
        print(f"  输入 {key_goto} + 页码 跳转到指定页 (如: {key_goto} 5)")
        print("=" * 60)
        
        # ★★★ 修复：分P菜单中也检查中断，Ctrl+C时退出菜单由外层处理 ★★★
        if interrupt_manager.interrupted:
            p('\n[中断] 检测到中断，退出分P选择', 'y')
            interrupt_manager.get_interrupt_menu()
            return None
        
        user_choice = input("\n请选择: ").strip().lower()
        
        if user_choice == '0':
            return None
        elif user_choice == 'q':
            p('[取消] 已返回', 'y')
            return None
        elif user_choice == 'all':
            selected_pages = list(range(1, len(pages_info) + 1))
            p(f'\n已选择全部 {len(pages_info)} 个分P', 'g')
            break
        elif user_choice == 'c':
            if selected_pages:
                break
            else:
                p("没有选中任何分P", 'y')
                continue
        elif user_choice == key_next:
            if current_page < total_pages - 1:
                current_page += 1
                continue
            else:
                p("[提示] 已经是最后一页了", 'y')
                continue
        elif user_choice == key_prev:
            if current_page > 0:
                current_page -= 1
                continue
            else:
                p("[提示] 已经是第一页了", 'y')
                continue
        elif user_choice.startswith(key_goto):
            parts = user_choice.split()
            if len(parts) >= 2 and parts[1].isdigit():
                target_page = int(parts[1]) - 1
                if 0 <= target_page < total_pages:
                    current_page = target_page
                    continue
                else:
                    p(f"页码范围: 1-{total_pages}", 'y')
                    continue
            else:
                p(f"格式错误，请输入: {key_goto} 页码 (如: {key_goto} 5)", 'y')
                continue
        elif user_choice == 'm':
            result_count = len(current_results)
            print(f"\n当前页有 {result_count} 个分P")
            print("输入格式示例:")
            print("  - 单个: 1 3 5")
            print("  - 范围: 1-5")
            print("  - 混合: 1 3-5 7")
            print("  - 全部: all")
            print("=" * 60)
            
            multi_choice = input("\n请输入要选择的分P序号: ").strip()
            if not multi_choice:
                p("[取消] 已退出", 'y')
                continue
            
            if multi_choice.lower() == 'all':
                for display_idx in range(1, result_count + 1):
                    actual_page_num = end_idx - (result_count - display_idx + 1) + 1
                    if actual_page_num not in selected_pages:
                        selected_pages.append(actual_page_num)
            else:
                selected_indices = parse_selection_input(multi_choice, result_count)
                if not selected_indices:
                    p("[错误] 没有有效的选择", 'y')
                    continue
                for idx in selected_indices:
                    display_num = idx + 1
                    actual_page_num = end_idx - (result_count - display_num + 1) + 1
                    if 1 <= actual_page_num <= len(pages_info) and actual_page_num not in selected_pages:
                        selected_pages.append(actual_page_num)
            
            p(f"\n已添加，当前共选中 {len(selected_pages)} 个分P", 'g')
            
            if selected_pages:
                print("\n当前选中的分P列表:")
                for i, page_num in enumerate(sorted(selected_pages)[:20], 1):
                    page = pages_info[page_num - 1]
                    title_text = page['part'][:40] + '...' if len(page['part']) > 40 else page['part']
                    print(f"  {i}. P{page['page']}: {title_text}")
                if len(selected_pages) > 20:
                    print(f"  ... 共 {len(selected_pages)} 个分P")
            
            print("\n操作选项:")
            print("  [1] 继续选择")
            print("  [2] 确认并开始解析")
            print("  [3] 清空所有选择")
            print("  [q] 返回")
            
            action = input("\n请选择 [1-3/q]: ").strip().lower()
            if action == '2':
                if selected_pages:
                    break
                else:
                    p("没有选中任何分P", 'y')
                    continue
            elif action == '3':
                selected_pages = []
                p("已清空所有选择", 'y')
                continue
            elif action in ('q', '0'):
                continue
            else:
                continue
        elif user_choice.isdigit():
            user_num = int(user_choice)
            result_count = len(current_results)
            if 1 <= user_num <= result_count:
                actual_page_num = end_idx - (result_count - user_num + 1) + 1
                
                p(f'\n[选中] 序号 {user_num} → P{actual_page_num}: {pages_info[actual_page_num - 1]["part"]}', 'g')
                
                if actual_page_num in selected_pages:
                    p("该分P已经在选择列表中", 'y')
                    if selected_pages:
                        print(f"\n当前已选中 {len(selected_pages)} 个分P")
                        print("  [1] 继续选择")
                        print("  [2] 确认并开始解析")
                        choice = input("\n请选择 [1/2]: ").strip()
                        if choice == '2':
                            break
                        else:
                            continue
                    else:
                        continue
                else:
                    selected_pages.append(actual_page_num)
                    p(f"已添加，当前共选中 {len(selected_pages)} 个分P", 'g')
                    
                    print("\n当前选中的分P列表:")
                    for i, p_num in enumerate(sorted(selected_pages)[:20], 1):
                        page = pages_info[p_num - 1]
                        title_text = page['part'][:40] + '...' if len(page['part']) > 40 else page['part']
                        print(f"  {i}. P{page['page']}: {title_text}")
                    if len(selected_pages) > 20:
                        print(f"  ... 共 {len(selected_pages)} 个分P")
                    
                    print("\n操作选项:")
                    print("  [1] 继续选择")
                    print("  [2] 确认并开始解析")
                    print("  [q] 取消")
                    
                    action = input("\n请选择 [1/2/q]: ").strip().lower()
                    if action == '2':
                        break
                    elif action in ('q', '3'):
                        selected_pages.remove(actual_page_num)
                        continue
                    else:
                        continue
            else:
                p(f"[错误] 请输入 1-{result_count} 之间的数字", 'y')
                continue
        else:
            p("无效输入，请重新输入", 'y')
            continue
    
    return sorted(selected_pages) if selected_pages else None

def show_page_mode_menu():
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

def bv_id_from_url(url):
    match = re.search(r'BV([0-9A-Za-z]{10})', url, re.IGNORECASE)
    if match:
        return f'BV{match.group(1)}'
    return None

def get_bvid_from_url(url):
    bv_match = re.search(r'BV([0-9A-Za-z]{10})', url, re.IGNORECASE)
    if bv_match:
        return f'BV{bv_match.group(1)}'
    
    if 'b23.tv' in url:
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            final_url = resp.url
            bv_match = re.search(r'BV([0-9A-Za-z]{10})', final_url, re.IGNORECASE)
            if bv_match:
                return f'BV{bv_match.group(1)}'
        except:
            pass
    
    return None

def ask_for_folder():
    print("\n" + "=" * 50)
    p("       文件夹选项", 'c')
    print("=" * 50)
    print("是否将所有分P下载到同一个文件夹？")
    print("  [直接回车] 不创建文件夹，文件直接保存在下载目录")
    print("  [输入名称] 创建指定名称的文件夹")
    print("=" * 50)
    
    folder_name = input("\n请输入文件夹名称 (直接回车跳过): ").strip()
    
    if not folder_name:
        return None
    
    folder_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name)
    return folder_name

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

# ==================== 核心处理函数 ====================

def process_single_video(url, mode, pages_info=None):
    p(f'\n{"="*50}', 'm')
    debug_print(f'处理视频: {url}')
    debug_print(f'模式: {mode}')
    
    is_youtube = 'youtube.com' in url or 'youtu.be' in url or 'googlevideo.com' in url
    if is_youtube and not get_cookies_path():
        p('[提示] YouTube 需要 cookies 认证', 'y')
        show_youtube_cookies_guide()
        return False
    
    is_bilibili = 'bilibili.com' in url or 'b23.tv' in url
    pages = pages_info
    bv_id = None
    
    if is_bilibili:
        bv_id = get_bvid_from_url(url)
        if bv_id:
            debug_print(f'提取到BV号: {bv_id}')
        else:
            debug_print('未能提取到BV号')
    
    if pages is None and is_bilibili and bv_id:
        p(f'[B站] 检查分P信息...', 'c')
        pages = get_bilibili_video_pages(bv_id)
        if pages and len(pages) > 1:
            p(f'[B站] 检测到 {len(pages)} 个分P', 'g')
            debug_print(f'分P数量: {len(pages)}')
    
    if pages and len(pages) > 1:
        selected_pages = show_page_selection_menu(pages, title if 'title' in locals() else '视频')
        if selected_pages is None:
            p('[取消] 用户取消选择', 'y')
            return False
        
        p(f'\n已选中 {len(selected_pages)} 个分P', 'g')
        print("=" * 60)
        for i, page_num in enumerate(selected_pages, 1):
            page = pages[page_num - 1]
            title_text = page['part'][:50] + '...' if len(page['part']) > 50 else page['part']
            print(f"  {i}. P{page['page']}: {title_text}")
            debug_print(f'  P{page["page"]}: cid={page["cid"]}')
        print("=" * 60)
        
        folder_name = ask_for_folder()
        if folder_name:
            base_path = get_download_path()
            save_folder = os.path.join(base_path, folder_name)
            os.makedirs(save_folder, exist_ok=True)
            p(f'[文件夹] 文件将保存到: {save_folder}', 'g')
        else:
            save_folder = None
            p('[提示] 文件将直接保存在下载目录', 'y')
        
        page_mode = show_page_mode_menu()
        
        p(f'\n[开始] 准备下载 {len(selected_pages)} 个分P...', 'c')
        debug_print(f'开始下载 {len(selected_pages)} 个分P, 模式: {page_mode}')
        
        success_count = 0
        skipped_count = 0
        failed_pages = []
        
        cover_url = None
        bvid = None
        cid = None
        
        if is_bilibili and bv_id:
            bvid = bv_id
            cover_url = get_bilibili_cover(bv_id)
            try:
                cid = get_cid_from_bvid(bvid)
            except:
                pass
        
        for page_num in selected_pages:
            # 检查中断
            if interrupt_manager.check_interrupt():
                p('\n[中断] 用户中断，停止下载当前分P', 'y')
                break
            
            page = pages[page_num - 1]
            page_title = page['part'][:50]
            display_num = page_num
            
            if save_folder:
                exists, existing_path = check_file_exists_by_title(page_title, save_folder)
            else:
                exists, existing_path = check_file_exists_by_title(page_title)
            
            if exists:
                p(f'\n[跳过] 文件夹中已存在: {os.path.basename(existing_path)}', 'y')
                skipped_count += 1
                success_count += 1
                continue
            
            p(f'\n>>> 下载第 {display_num} 个分P: {page["part"]}', 'c')
            debug_print(f'下载 P{page["page"]}: cid={page["cid"]}, 标题={page["part"]}')
            
            attempt = 1
            downloaded = False
            while not downloaded and attempt <= 10:
                # 检查中断
                if interrupt_manager.check_interrupt():
                    p('\n[中断] 用户中断下载', 'y')
                    break
                
                try:
                    cid_page = page.get('cid')
                    if not cid_page:
                        p(f'[错误] 无法获取分P的cid', 'r')
                        debug_print(f'错误: 无法获取cid (P{page["page"]})')
                        break
                    
                    if not bvid:
                        bvid = get_bvid_from_url(url)
                        if not bvid:
                            p(f'[错误] 无法提取BV号', 'r')
                            debug_print('BV号为空')
                            attempt += 1
                            continue
                    
                    page_url = f"https://www.bilibili.com/video/{bvid}?p={page['page']}"
                    debug_print(f'使用备用API: {page_url}')
                    
                    result = parse_video(page_url)
                    
                    # 检查解析是否被中断
                    if result is None or (len(result) >= 1 and result[0] is None):
                        p('\n[中断] 解析被中断', 'y')
                        break
                    
                    if result and len(result) >= 2:
                        video_url = result[1]
                        if video_url:
                            p(f'[解析成功] 获取到视频流', 'g')
                            mp4_path = download_file(video_url, page_title, save_folder)
                            
                            # 检查下载是否被中断
                            if interrupt_manager.check_interrupt():
                                p('\n[中断] 用户中断下载', 'y')
                                break
                            
                            if mp4_path:
                                size = os.path.getsize(mp4_path) / 1024 / 1024
                                if size < 0.5:
                                    p(f'[警告] 文件过小({size:.1f}MB)，可能下载失败', 'y')
                                    os.remove(mp4_path)
                                    attempt += 1
                                    continue
                                
                                # 检查MP3是否存在但可能没有封面
                                mp3_path = mp4_path.replace('.mp4', '.mp3')
                                if os.path.exists(mp3_path) and page_mode in (2, 3):
                                    # MP3已存在，强制重新处理封面和歌词
                                    mp3_path_final = download_mp3_with_settings(
                                        mp4_path, 
                                        cover_url, 
                                        bvid, 
                                        cid, 
                                        page_title,
                                        force=True
                                    )
                                    if mp3_path_final:
                                        if page_mode == 2:
                                            if os.path.exists(mp4_path):
                                                os.remove(mp4_path)
                                                debug_print(f'已删除MP4: {mp4_path}')
                                            p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                                        elif page_mode == 3:
                                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                            p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                                    else:
                                        p('[失败] MP3处理失败', 'r')
                                        attempt += 1
                                        continue
                                elif page_mode in (2, 3):
                                    # 正常处理
                                    mp3_path_final = download_mp3_with_settings(
                                        mp4_path, 
                                        cover_url, 
                                        bvid, 
                                        cid, 
                                        page_title
                                    )
                                    if mp3_path_final:
                                        if page_mode == 2:
                                            if os.path.exists(mp4_path):
                                                os.remove(mp4_path)
                                                debug_print(f'已删除MP4: {mp4_path}')
                                            p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                                        elif page_mode == 3:
                                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                            p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                                    else:
                                        p('[失败] MP3处理失败', 'r')
                                        attempt += 1
                                        continue
                                else:
                                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                
                                success_count += 1
                                downloaded = True
                                debug_print(f'P{page["page"]} 下载成功')
                                break
                    else:
                        p(f'[重试 {attempt}] 备用API解析失败，等待后重试...', 'y')
                        debug_print('备用API解析失败')
                        time.sleep(2)
                        attempt += 1
                        
                except Exception as e:
                    if interrupt_manager.check_interrupt():
                        p('\n[中断] 用户中断下载', 'y')
                        break
                    p(f'[重试 {attempt}] {str(e)[:50]}，等待后重试...', 'y')
                    debug_print(f'异常: {e}')
                    time.sleep(2)
                    attempt += 1
            
            # 如果是因为中断退出循环，记录并停止
            if interrupt_manager.check_interrupt():
                p('\n[中断] 用户中断，停止下载', 'y')
                break
            
            if not downloaded:
                failed_pages.append(display_num)
                save_failed_download({
                    'url': url, 
                    'title': page_title, 
                    'reason': f'分P {display_num} 下载失败'
                })
                p(f'[失败] 第 {display_num} 个分P 下载失败', 'r')
        
        p(f'\n[完成] 成功: {success_count} 个, 跳过: {skipped_count} 个, 失败: {len(failed_pages)} 个', 'g')
        if failed_pages:
            p(f'[失败] 以下分P下载失败: {failed_pages}', 'r')
        if save_folder:
            p(f'[位置] 文件保存在: {save_folder}', 'c')
        debug_print(f'分P下载完成: 成功 {success_count}/{len(selected_pages)}')
        
        # 如果被中断，返回False
        if interrupt_manager.check_interrupt():
            return False
        return success_count > 0
    
    # 单个视频处理
    debug_print('单个视频处理')
    result = parse_video(url)
    
    # 检查解析是否被中断
    if result is None or (len(result) >= 1 and result[0] is None):
        p('\n[中断] 解析被中断', 'y')
        return False
    
    if len(result) == 5:
        title, video_url, cover_url, pages, medialist_info = result
        if medialist_info:
            p(f'[B站合集] 检测到合集: {medialist_info["title"]}, 共 {medialist_info["total"]} 个视频', 'g')
            return process_medialist(medialist_info, mode)
    elif len(result) == 4:
        title, video_url, cover_url, pages = result
    else:
        title, video_url, cover_url = result
        pages = None
    
    if not video_url:
        p('[错误] 解析失败', 'r')
        debug_print('解析失败: 未获取到视频URL')
        save_failed_download({'url': url, 'title': title if title else '未知', 'reason': '解析失败'})
        return False
    
    debug_print(f'视频标题: {title}')
    debug_print(f'视频URL: {video_url[:100]}...')
    debug_print(f'封面URL: {cover_url[:80]}...')
    
    mp4_path = download_file(video_url, title)
    
    # 检查是否被中断
    if interrupt_manager.check_interrupt():
        p('\n[中断] 用户中断下载', 'y')
        return False
    
    if not mp4_path:
        p('[错误] 下载失败', 'r')
        debug_print('下载失败')
        return False
    
    if mode in (2, 3):
        bvid = None
        cid = None
        if is_bilibili and bv_id:
            bvid = bv_id
            try:
                cid = get_cid_from_bvid(bvid)
            except:
                pass
        
        # 检查MP3是否存在，如果存在则强制重新处理
        mp3_path = mp4_path.replace('.mp4', '.mp3')
        if os.path.exists(mp3_path) and mode in (2, 3):
            mp3_path_final = download_mp3_with_settings(
                mp4_path, cover_url, bvid, cid, title, force=True
            )
            if mp3_path_final:
                if mode == 2:
                    if os.path.exists(mp4_path):
                        os.remove(mp4_path)
                        debug_print(f'已删除MP4: {mp4_path}')
                    p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                elif mode == 3:
                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                    p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                debug_print('处理完成（MP3）')
                return True
            else:
                p(f'[保留] 转换失败，保留MP4', 'y')
                debug_print('MP3处理失败')
                if mode == 2:
                    return False
                else:
                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                    return True
        else:
            mp3_path_final = download_mp3_with_settings(mp4_path, cover_url, bvid, cid, title)
            if mp3_path_final:
                if mode == 2:
                    if os.path.exists(mp4_path):
                        os.remove(mp4_path)
                        debug_print(f'已删除MP4: {mp4_path}')
                    p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                elif mode == 3:
                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                    p(f'[完成] 音频: {os.path.basename(mp3_path_final)}', 'g')
                debug_print('处理完成（MP3）')
                return True
            else:
                p(f'[保留] 转换失败，保留MP4', 'y')
                debug_print('MP3转换失败')
                if mode == 2:
                    return False
                else:
                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                    return True
    else:
        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
        debug_print('处理完成（MP4）')
        return True

def process_medialist(medialist_info, mode):
    videos = medialist_info['videos']
    title = medialist_info['title']
    
    p(f'\n{"="*50}', 'm')
    p(f'[B站合集] {title}', 'c')
    p(f'[B站合集] 共 {len(videos)} 个视频', 'g')
    print("=" * 50)
    
    print("\n视频列表：")
    for i, video in enumerate(videos, 1):
        print(f"  {i}. {video['title'][:55]}...")
        print(f"     BV: {video['bvid']}")
        print("-" * 50)
    
    print("\n" + "=" * 50)
    print("操作说明：")
    print("  - 输入 'all' 下载全部视频")
    print("  - 输入数字选择单个视频（如：1）")
    print("  - 输入多个数字用逗号分隔（如：1,3,5）")
    print("  - 输入范围（如：1-5）")
    print("  - 输入 q 跳过此合集")
    print("=" * 50)
    
    while True:
        choice = input("\n请选择: ").strip().lower()
        
        if choice in ('q', '0'):
            p('[跳过] 跳过此合集', 'y')
            return False
        
        if choice == 'all':
            selected_indices = list(range(len(videos)))
            break
        
        if ',' in choice or '-' in choice:
            selected_indices = parse_selection_input(choice, len(videos))
            if selected_indices:
                break
            else:
                p("无效的选择格式，请重新输入", 'y')
                continue
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(videos):
                selected_indices = [idx]
                break
            else:
                p(f"请输入 1-{len(videos)} 之间的数字", 'y')
                continue
        
        p("无效输入，请重新输入", 'y')
    
    if not selected_indices:
        p('[取消] 未选择视频', 'y')
        return False
    
    p(f'\n已选择 {len(selected_indices)} 个视频', 'g')
    
    folder_name = ask_for_folder()
    if folder_name:
        base_path = get_download_path()
        save_folder = os.path.join(base_path, folder_name)
        os.makedirs(save_folder, exist_ok=True)
        p(f'[文件夹] 文件将保存到: {save_folder}', 'g')
    else:
        save_folder = None
        p('[提示] 文件将直接保存在下载目录', 'y')
    
    page_mode = show_page_mode_menu()
    
    p(f'\n[开始] 准备下载 {len(selected_indices)} 个视频...', 'c')
    debug_print(f'开始下载合集视频, 模式: {page_mode}')
    
    success_count = 0
    for idx in selected_indices:
        video = videos[idx]
        video_url = video['url']
        video_title = video['title']
        
        p(f'\n>>> 下载视频: {video_title}', 'c')
        debug_print(f'下载视频: {video_title} ({video_url})')
        
        bvid = video['bvid']
        pages = get_bilibili_video_pages(bvid)
        cover_url = get_bilibili_cover(bvid)
        cid = get_cid_from_bvid(bvid)
        
        if pages and len(pages) > 1:
            p(f'[B站] 检测到 {len(pages)} 个分P', 'g')
            print(f"\n视频 {video_title} 有 {len(pages)} 个分P")
            choice = input("下载全部? (直接回车=全部, 输入数字选择单个): ").strip()
            if choice == '':
                selected_pages = list(range(len(pages)))
            elif choice.isdigit():
                idx_p = int(choice) - 1
                if 0 <= idx_p < len(pages):
                    selected_pages = [idx_p]
                else:
                    p(f"无效选择，跳过此视频", 'y')
                    continue
            else:
                p(f"无效选择，跳过此视频", 'y')
                continue
            
            for page_idx in selected_pages:
                page = pages[page_idx]
                page_title = f"{video_title} - P{page['page']}"
                cid_page = page.get('cid')
                if not cid_page:
                    continue
                
                if save_folder:
                    exists, existing_path = check_file_exists_by_title(page_title, save_folder)
                else:
                    exists, existing_path = check_file_exists_by_title(page_title)
                
                if exists:
                    p(f'[跳过] 文件夹中已存在: {os.path.basename(existing_path)}', 'y')
                    success_count += 1
                    continue
                
                page_url = f"https://www.bilibili.com/video/{bvid}?p={page['page']}"
                result = parse_video(page_url)
                if result and len(result) >= 2:
                    video_url = result[1]
                    if video_url:
                        mp4_path = download_file(video_url, page_title, save_folder)
                        if mp4_path:
                            if page_mode in (2, 3):
                                mp3_path = download_mp3_with_settings(
                                    mp4_path, 
                                    cover_url, 
                                    bvid, 
                                    cid, 
                                    page_title
                                )
                                if mp3_path:
                                    if page_mode == 2:
                                        if os.path.exists(mp4_path):
                                            os.remove(mp4_path)
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                    elif page_mode == 3:
                                        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                else:
                                    p('[失败] MP3转换失败', 'y')
                            else:
                                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                            success_count += 1
        else:
            try:
                result = parse_video(video_url)
                if len(result) >= 2:
                    video_url = result[1]
                    if video_url:
                        mp4_path = download_file(video_url, video_title, save_folder)
                        if mp4_path:
                            if page_mode in (2, 3):
                                mp3_path = download_mp3_with_settings(
                                    mp4_path, 
                                    cover_url, 
                                    bvid, 
                                    cid, 
                                    video_title
                                )
                                if mp3_path:
                                    if page_mode == 2:
                                        if os.path.exists(mp4_path):
                                            os.remove(mp4_path)
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                    elif page_mode == 3:
                                        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                else:
                                    p('[失败] MP3转换失败', 'y')
                            else:
                                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                            success_count += 1
            except Exception as e:
                p(f'[错误] 处理失败: {e}', 'r')
    
    p(f'\n[完成] 成功下载 {success_count} 个视频', 'g')
    if save_folder:
        p(f'[位置] 文件保存在: {save_folder}', 'c')
    return success_count > 0

# ==================== 处理选中的视频（不再重复解析） ====================

def process_selected_videos(urls, global_mode, url_info, task_id=None):
    """处理已经解析好的视频列表（不再重复解析）"""
    if not urls:
        return 0, 0
    
    # 设置中断管理器的当前任务
    interrupt_manager.set_download_task(urls, global_mode, url_info, task_id, global_mode)
    interrupt_manager.set_task('下载视频', {'total': len(urls), 'mode': global_mode})
    
    # 在开始前检查中断
    if interrupt_manager.check_interrupt():
        interrupt_result = interrupt_manager.get_interrupt_menu()
        if interrupt_result == 'main_menu':
            interrupt_manager.clear()
            return 0, 0
        elif interrupt_result == 'skip':
            interrupt_manager.reset()
            return 0, 0
        elif interrupt_result == 'reselect':
            interrupt_manager.clear()
            return 0, 0
        elif interrupt_result == 'continue':
            interrupt_manager.reset()
    
    # 创建或获取任务ID
    if task_id is None:
        p(f'\n[任务] 正在创建任务...', 'c')
        task_data = create_unfinished_task(urls, global_mode, url_info)
        task_id = task_data['id']
        p(f'[任务] 已创建任务: {task_data["name"]}', 'g')
        p(f'[任务] 共 {len(urls)} 个文件待下载', 'c')
        interrupt_manager.current_task_id = task_id
    
    success = 0
    fail = 0
    total = len(urls)
    
    # ★★★ 使用 while 循环，方便中断后继续 ★★★
    idx = 0
    while idx < len(urls):
        
        # ★★★ 检查中断 ★★★
        if interrupt_manager.check_interrupt():
            interrupt_result = interrupt_manager.get_interrupt_menu()
            if interrupt_result == 'main_menu':
                p('\n[中断] 已返回主菜单', 'y')
                interrupt_manager.clear()
                break
            elif interrupt_result == 'skip':
                p('\n[中断] 跳过当前任务', 'y')
                interrupt_manager.reset()
                idx += 1
                continue
            elif interrupt_result == 'reselect':
                p('\n[中断] 重新选择', 'y')
                interrupt_manager.clear()
                break
            elif interrupt_result == 'continue':
                p('\n[继续] 继续当前下载...', 'c')
                interrupt_manager.reset()
                # ★★★ 继续执行：不前进idx，重试当前视频（利用.tmp续传）★★★
                continue
        
        key = urls[idx]
        info = url_info.get(key, {})
        title = info.get('title', '未知标题')
        video_url = info.get('video_url')
        cover_url = info.get('cover_url')
        pages = info.get('pages')
        bvid = info.get('bvid')
        selected_pages = info.get('selected_pages')
        page = info.get('page')
        page_num = info.get('page_num')
        original_url = info.get('url', key)
        
        p(f'\n{"="*50}', 'm')
        p(f'处理第 {idx}/{len(urls)} 个任务', 'c')
        p(f'标题: {title[:50]}...' if len(title) > 50 else f'标题: {title}', 'c')
        debug_print(f'处理任务 {idx}/{len(urls)}: {title}')
        
        # 更新任务进度
        update_unfinished_task_progress(
            task_id, 
            success, 
            total,
            current_file=title[:50] + '...' if len(title) > 50 else title,
            current_progress='准备下载',
            status='downloading'
        )
        
        # ★★★ 如果有保存的 video_url，直接使用 ★★★
        if video_url:
            # 如果有page和page_num（单个分P）- 直接下载
            if page and page_num:
                page_title = page['part'][:50]
                p(f'[分P续传] 正在处理: {page_title}', 'c')
                p(f'[续传] 使用已保存的视频地址直接下载...', 'c')
                
                mp4_path = download_file(video_url, page_title)
                if mp4_path:
                    if global_mode in (2, 3):
                        mp3_path = download_mp3_with_settings(mp4_path, cover_url, bvid, None, page_title)
                        if mp3_path:
                            if global_mode == 2:
                                if os.path.exists(mp4_path):
                                    os.remove(mp4_path)
                                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                            else:
                                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                            success += 1
                        else:
                            p('[失败] MP3转换失败', 'y')
                            fail += 1
                    else:
                        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                        success += 1
                else:
                    fail += 1
                
                update_unfinished_task_progress(
                    task_id, 
                    success, 
                    total,
                    current_file=title[:50] + '...' if len(title) > 50 else title,
                    current_progress=f'{success}/{total}',
                    status='downloading'
                )
                p(f'[进度] 已完成: {success}/{total}', 'c')
                idx += 1
                continue
            
            # 如果有选中的分P列表 - 直接使用
            if selected_pages and pages and len(selected_pages) > 1:
                p(f'[续传] 使用已保存的 {len(selected_pages)} 个分P，直接下载...', 'c')
                if process_selected_pages(original_url, global_mode, pages, selected_pages, title, cover_url, bvid):
                    success += 1
                else:
                    fail += 1
                update_unfinished_task_progress(
                    task_id, 
                    success, 
                    total,
                    current_file=title[:50] + '...' if len(title) > 50 else title,
                    current_progress=f'{success}/{total}',
                    status='downloading'
                )
                p(f'[进度] 已完成: {success}/{total}', 'c')
                idx += 1
                continue
            
            # 普通视频 - 直接下载
            if not page and not selected_pages:
                p(f'[续传] 使用已保存的解析结果，直接下载...', 'c')
                mp4_path = download_file(video_url, title)
                
                if mp4_path:
                    update_unfinished_task_progress(
                        task_id, 
                        success, 
                        total,
                        current_file=title[:50] + '...' if len(title) > 50 else title,
                        current_progress='下载完成',
                        status='downloading'
                    )
                
                if mp4_path:
                    if global_mode in (2, 3):
                        p(f'[转换] 正在转换为MP3...', 'c')
                        cid = None
                        if bvid:
                            try:
                                cid = get_cid_from_bvid(bvid)
                            except:
                                pass
                        
                        mp3_path = download_mp3_with_settings(
                            mp4_path, 
                            cover_url, 
                            bvid, 
                            cid, 
                            title
                        )
                        if mp3_path:
                            if global_mode == 2:
                                if os.path.exists(mp4_path):
                                    os.remove(mp4_path)
                                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                            elif global_mode == 3:
                                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                        else:
                            p('[失败] MP3转换失败', 'y')
                            fail += 1
                            idx += 1
                            continue
                    else:
                        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                    success += 1
                    debug_print(f'下载成功: {title}')
                else:
                    fail += 1
                    debug_print(f'下载失败: {title}')
                
                update_unfinished_task_progress(
                    task_id, 
                    success, 
                    total,
                    current_file=title[:50] + '...' if len(title) > 50 else title,
                    current_progress=f'{success}/{total}',
                    status='downloading'
                )
                p(f'[进度] 已完成: {success}/{total}', 'c')
                idx += 1
                continue
        
        # ===== 备用逻辑（当没有保存的 video_url 时） =====
        
        # 检查文件是否已存在
        p(f'[检查] 正在检查文件是否存在...', 'y')
        exists, existing_path = check_file_exists_by_title(title)
        if exists:
            p(f'[跳过] 文件已存在: {os.path.basename(existing_path)}', 'y')
            success += 1
            update_unfinished_task_progress(
                task_id, 
                success, 
                total,
                current_file='已跳过: ' + (title[:30] + '...' if len(title) > 30 else title),
                current_progress='已存在',
                status='downloading'
            )
            idx += 1
            continue
        
        if page and page_num:
            page_title = page['part'][:50]
            p(f'[分P] 正在处理: {page_title}', 'c')
            if process_single_video(original_url, global_mode, pages):
                success += 1
                p(f'[完成] 分P: {page_title}', 'g')
            else:
                fail += 1
                p(f'[失败] 分P: {page_title}', 'r')
            idx += 1
            continue
        
        if selected_pages and pages and len(selected_pages) > 1:
            p(f'[下载] 使用选中的 {len(selected_pages)} 个分P', 'c')
            if process_selected_pages(original_url, global_mode, pages, selected_pages, title, cover_url, bvid):
                success += 1
            else:
                fail += 1
        elif pages and len(pages) > 1:
            p(f'[下载] 有 {len(pages)} 个分P，传入pages信息', 'c')
            if process_single_video(original_url, global_mode, pages_info=pages):
                success += 1
            else:
                fail += 1
        elif video_url:
            p(f'[下载] 开始下载视频...', 'c')
            mp4_path = download_file(video_url, title)
            
            if mp4_path:
                update_unfinished_task_progress(
                    task_id, 
                    success, 
                    total,
                    current_file=title[:50] + '...' if len(title) > 50 else title,
                    current_progress='下载完成',
                    status='downloading'
                )
            
            if mp4_path:
                if global_mode in (2, 3):
                    p(f'[转换] 正在转换为MP3...', 'c')
                    cid = None
                    if bvid:
                        try:
                            cid = get_cid_from_bvid(bvid)
                        except:
                            pass
                    
                    mp3_path = download_mp3_with_settings(
                        mp4_path, 
                        cover_url, 
                        bvid, 
                        cid, 
                        title
                    )
                    if mp3_path:
                        if global_mode == 2:
                            if os.path.exists(mp4_path):
                                os.remove(mp4_path)
                            p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                        elif global_mode == 3:
                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                            p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                    else:
                        p('[失败] MP3转换失败', 'y')
                        fail += 1
                        idx += 1
                        continue
                else:
                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                success += 1
                debug_print(f'下载成功: {title}')
            else:
                fail += 1
                debug_print(f'下载失败: {title}')
        else:
            p(f'[重试] 未找到保存的视频地址，尝试重新解析...', 'y')
            result = parse_video(original_url)
            if result and len(result) >= 3:
                video_url = result[1]
                if video_url:
                    url_info[key]['video_url'] = video_url
                    save_unfinished_task({'id': task_id, 'url_info': url_info})
                    
                    mp4_path = download_file(video_url, title)
                    if mp4_path:
                        if global_mode in (2, 3):
                            mp3_path = download_mp3_with_settings(mp4_path, cover_url, bvid, None, title)
                            if mp3_path:
                                if global_mode == 2:
                                    if os.path.exists(mp4_path):
                                        os.remove(mp4_path)
                                    p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                else:
                                    p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                    p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                            else:
                                fail += 1
                                idx += 1
                                continue
                        else:
                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                        success += 1
                    else:
                        fail += 1
                else:
                    fail += 1
            else:
                fail += 1
        
        # 更新进度
        update_unfinished_task_progress(
            task_id, 
            success, 
            total,
            current_file=title[:50] + '...' if len(title) > 50 else title,
            current_progress=f'{success}/{total}',
            status='downloading'
        )
        p(f'[进度] 已完成: {success}/{total}', 'c')
        
        # ★★★ 修复：while 循环末尾统一前进到下一个视频 ★★★
        idx += 1
    
    if success >= total:
        mark_task_completed(task_id)
        p(f'\n[任务] 所有任务已完成', 'g')
    else:
        update_unfinished_task_progress(
            task_id, 
            success, 
            total,
            current_file='已结束',
            current_progress=f'{success}/{total}',
            status='paused'
        )
        p(f'\n[任务] 进度已保存: {success}/{total}', 'y')
    
    return success, fail

def process_selected_pages(url, global_mode, pages, selected_pages, title, cover_url, bvid):
    """处理选中的分P"""
    p(f'\n[开始] 下载选中的 {len(selected_pages)} 个分P...', 'c')
    debug_print(f'下载选中的分P: {len(selected_pages)} 个')
    
    success_count = 0
    skipped_count = 0
    failed_pages = []
    
    folder_name = ask_for_folder()
    if folder_name:
        base_path = get_download_path()
        save_folder = os.path.join(base_path, folder_name)
        os.makedirs(save_folder, exist_ok=True)
        p(f'[文件夹] 文件将保存到: {save_folder}', 'g')
    else:
        save_folder = None
        p('[提示] 文件将直接保存在下载目录', 'y')
    
    page_mode = show_page_mode_menu()
    
    cid = None
    if bvid:
        try:
            cid = get_cid_from_bvid(bvid)
        except:
            pass
    
    for page_num in selected_pages:
        page = pages[page_num - 1]
        page_title = page['part'][:50]
        display_num = page_num
        
        if save_folder:
            exists, existing_path = check_file_exists_by_title(page_title, save_folder)
        else:
            exists, existing_path = check_file_exists_by_title(page_title)
        
        if exists:
            p(f'\n[跳过] 分P已存在: {os.path.basename(existing_path)}', 'y')
            skipped_count += 1
            success_count += 1
            continue
        
        p(f'\n>>> 下载第 {display_num} 个分P: {page["part"]}', 'c')
        debug_print(f'下载 P{page["page"]}: cid={page["cid"]}, 标题={page["part"]}')
        
        attempt = 1
        downloaded = False
        while not downloaded and attempt <= 10:
            try:
                cid_page = page.get('cid')
                if not cid_page:
                    p(f'[错误] 无法获取分P的cid', 'r')
                    debug_print(f'错误: 无法获取cid (P{page["page"]})')
                    break
                
                if not bvid:
                    bvid = get_bvid_from_url(url)
                    if not bvid:
                        p(f'[错误] 无法提取BV号', 'r')
                        debug_print('BV号为空')
                        attempt += 1
                        continue
                
                page_url = f"https://www.bilibili.com/video/{bvid}?p={page['page']}"
                debug_print(f'使用备用API: {page_url}')
                
                result = parse_video(page_url)
                if result and len(result) >= 2:
                    video_url = result[1]
                    if video_url:
                        p(f'[解析成功] 获取到视频流', 'g')
                        mp4_path = download_file(video_url, page_title, save_folder)
                        if mp4_path:
                            size = os.path.getsize(mp4_path) / 1024 / 1024
                            if size < 0.5:
                                p(f'[警告] 文件过小({size:.1f}MB)，可能下载失败', 'y')
                                os.remove(mp4_path)
                                attempt += 1
                                continue
                            
                            if page_mode in (2, 3):
                                mp3_path = download_mp3_with_settings(
                                    mp4_path, 
                                    cover_url, 
                                    bvid, 
                                    cid, 
                                    page_title
                                )
                                if mp3_path:
                                    if page_mode == 2:
                                        if os.path.exists(mp4_path):
                                            os.remove(mp4_path)
                                            debug_print(f'已删除MP4: {mp4_path}')
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                    elif page_mode == 3:
                                        p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                else:
                                    p('[失败] MP3转换失败', 'r')
                                    attempt += 1
                                    continue
                            else:
                                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                            
                            success_count += 1
                            downloaded = True
                            debug_print(f'P{page["page"]} 下载成功')
                            break
                else:
                    p(f'[重试 {attempt}] 备用API解析失败，等待后重试...', 'y')
                    debug_print('备用API解析失败')
                    time.sleep(2)
                    attempt += 1
                    
            except Exception as e:
                p(f'[重试 {attempt}] {str(e)[:50]}，等待后重试...', 'y')
                debug_print(f'异常: {e}')
                time.sleep(2)
                attempt += 1
        
        if not downloaded:
            failed_pages.append(display_num)
            save_failed_download({
                'url': url, 
                'title': page_title, 
                'reason': f'分P {display_num} 下载失败'
            })
            p(f'[失败] 第 {display_num} 个分P 下载失败', 'r')
    
    p(f'\n[完成] 成功: {success_count} 个, 跳过: {skipped_count} 个, 失败: {len(failed_pages)} 个', 'g')
    if failed_pages:
        p(f'[失败] 以下分P下载失败: {failed_pages}', 'r')
    if save_folder:
        p(f'[位置] 文件保存在: {save_folder}', 'c')
    debug_print(f'分P下载完成: 成功 {success_count}/{len(selected_pages)}')
    return success_count > 0
# ==================== 重试失败下载功能 ====================

def retry_failed_downloads():
    failed_items = get_failed_items()
    failed_urls = get_failed_urls()
    
    if not failed_items and not failed_urls:
        p('[信息] 没有失败的下载记录', 'y')
        return
    
    print("\n" + "=" * 60)
    p("       重新下载失败的文件", 'c')
    print("=" * 60)
    
    print(f"发现 {len(failed_items)} 个失败的下载记录:")
    for i, item in enumerate(failed_items, 1):
        title = item.get('title', '未知标题')
        reason = item.get('reason', '未知原因')
        url = item.get('url', '')
        bvid = item.get('bvid', '')
        print(f"  {i}. {title[:50]}...")
        print(f"     原因: {reason}")
        print(f"     URL: {url[:60]}...")
        if bvid:
            print(f"     BV号: {bvid}")
        print("-" * 50)
    
    print("=" * 60)
    print("[提示] 直接回车 = 开始重新下载")
    print("  输入 q = 取消并清空失败记录")
    print("  输入 1 = 仅重新下载，保留失败记录")
    
    choice = input("\n请选择: ").strip().lower()
    
    if choice in ('q', '0'):
        clear_failed_downloads()
        p('[已清空] 失败记录已清除', 'y')
        return
    
    if choice == '1':
        p('[模式] 仅重新下载，保留失败记录', 'y')
        keep_record = True
    else:
        keep_record = False
    
    print("\n" + "=" * 50)
    p("       开始重新下载", 'c')
    print("=" * 50)
    
    success_count = 0
    fail_count = 0
    
    for i, item in enumerate(failed_items, 1):
        url = item.get('url')
        title = item.get('title', f'视频_{i}')
        bvid = item.get('bvid', '')
        
        if not url:
            continue
        
        p(f'\n[{i}/{len(failed_items)}] 重新下载: {title[:40]}...', 'c')
        
        exists, existing_path = check_file_exists_by_title(title)
        if exists:
            p(f'[跳过] 文件已存在: {os.path.basename(existing_path)}', 'y')
            success_count += 1
            continue
        
        # ★★★ 修复：检测到 B站临时链接时，使用 BV 号重新获取 ★★★
        if 'bilivideo.com' in url or 'upos' in url:
            p('[信息] 检测到B站临时链接（已过期），尝试通过BV号重新获取...', 'y')
            
            # 如果没有 BV 号，尝试从 URL 中提取
            if not bvid:
                # 尝试从 URL 中提取 BV 号
                bv_match = re.search(r'BV([0-9A-Za-z]{10})', url, re.IGNORECASE)
                if bv_match:
                    bvid = f'BV{bv_match.group(1)}'
                    p(f'[信息] 从URL提取到BV号: {bvid}', 'c')
                else:
                    # 尝试从标题中提取
                    bv_match = re.search(r'BV([0-9A-Za-z]{10})', title, re.IGNORECASE)
                    if bv_match:
                        bvid = f'BV{bv_match.group(1)}'
                        p(f'[信息] 从标题提取到BV号: {bvid}', 'c')
                    else:
                        # ★★★ 如果都没有，尝试从缓存文件中查找 ★★★
                        p('[信息] 未找到BV号，尝试从元数据文件中查找...', 'y')
                        download_path = get_download_path()
                        for root, dirs, files in os.walk(download_path):
                            for file in files:
                                if file.endswith('.meta'):
                                    meta_path = os.path.join(root, file)
                                    try:
                                        with open(meta_path, 'r', encoding='utf-8') as f:
                                            meta = json.load(f)
                                            if meta.get('url') == url:
                                                # 从元数据中提取 BV 号
                                                meta_title = meta.get('title', '')
                                                bv_match = re.search(r'BV([0-9A-Za-z]{10})', meta_title, re.IGNORECASE)
                                                if bv_match:
                                                    bvid = f'BV{bv_match.group(1)}'
                                                    p(f'[信息] 从元数据提取到BV号: {bvid}', 'c')
                                                    break
                                    except:
                                        pass
                            if bvid:
                                break
            
            if bvid:
                # ★★★ 使用 BV 号重新获取视频地址（不是直接解析临时链接） ★★★
                video_url = f"https://www.bilibili.com/video/{bvid}"
                p(f'[信息] 使用BV号重新解析: {video_url}', 'c')
                
                result = parse_video(video_url)
                if result and len(result) >= 3:
                    video_title, video_url_new, cover_url = result[0], result[1], result[2]
                    if video_url_new and video_title:
                        p(f'[信息] 获取到新的视频地址，开始下载...', 'g')
                        # ★★★ 使用视频的实际标题，而不是保存的标题 ★★★
                        mp4_path = download_file(video_url_new, video_title)
                        if mp4_path:
                            success_count += 1
                            p(f'[成功] 重新下载完成', 'g')
                            continue
                    else:
                        p('[失败] 无法获取有效的视频地址', 'r')
                else:
                    p('[失败] 解析失败', 'r')
            else:
                p('[错误] 无法提取BV号，B站临时链接已过期且无法恢复', 'r')
                p('[提示] 建议手动搜索该视频重新下载', 'y')
            fail_count += 1
            continue
        
        # 普通 URL 直接解析
        result = parse_video(url)
        if result:
            if len(result) >= 3:
                video_title, video_url, cover_url = result[0], result[1], result[2]
                if video_url:
                    mp4_path = download_file(video_url, video_title)
                    if mp4_path:
                        success_count += 1
                        p(f'[成功] 重新下载完成', 'g')
                        continue
        
        p(f'[失败] 重新下载失败', 'r')
        fail_count += 1
    
    print("\n" + "=" * 50)
    p("       重新下载完成", 'c')
    print("=" * 50)
    p(f"成功: {success_count} 个", 'g')
    p(f"失败: {fail_count} 个", 'r' if fail_count > 0 else 'g')
    print("=" * 50)
    
    if not keep_record and fail_count == 0:
        clear_failed_downloads()
        p('[已清空] 所有失败记录已清除', 'g')
    elif not keep_record and fail_count > 0:
        p('[保留] 仍有失败记录，已保留', 'y')
    
    input("\n按回车键返回...")

# ==================== 菜单功能 ====================

def show_global_menu():
    p('\n' + '=' * 50, 'm')
    p('       请选择处理模式', 'm')
    p('=' * 50, 'm')
    p('  [5] 从剪贴板读取链接', 'c')
    p('  [4] 选择部分（手动选择每个视频的处理方式）', 'c')
    p('  [3] 全部都要（MP4+MP3，MP3带封面）', 'c')
    p('  [2] 全部转 MP3（删除MP4，自动添加封面）', 'c')
    p('  [1] 全部转 MP4（只下载视频）', 'c')
    p('  [q] 返回主菜单', 'c')
    p('=' * 50, 'm')
    
    while True:
        choice = input('\n请输入选项 [1-5/q]: ').strip().lower()
        if choice in ('q', '0'):
            return 0
        elif choice in ['1', '2', '3', '4', '5']:
            return int(choice)
        p('无效选项，请重新输入', 'y')

def show_video_mode_menu(allow_return=True):
    print('=' * 50)
    print('  [3] 都要（MP4+MP3，MP3带封面）')
    print('  [2] 仅MP3（下载音频，自动添加封面）')
    print('  [1] 仅MP4（下载视频）')
    if allow_return:
        print('  [q] 返回上一页（重新搜索）')
    print('=' * 50)
    print('提示：直接按回车返回主菜单')
    
    while True:
        choice = input('\n请选择处理模式 [1-3] 或按回车返回主菜单: ').strip().lower()
        if choice == '':
            return 'main_menu'
        elif choice in ['1', '2', '3']:
            return int(choice)
        elif allow_return and choice in ('q', '0'):
            return 'reselect'
        else:
            p('无效选项，请输入 1-3 或按回车', 'y')

def show_uninstall_menu():
    print('\n' + '=' * 50)
    p('       卸载选项', 'c')
    print('=' * 50)
    print('  [2] 返回主菜单')
    print('  [1] 仅删除下载的视频文件')
    print('=' * 50)

def uninstall_videos():
    download_path = get_download_path()
    print(f'\n正在删除视频文件: {download_path}')
    try:
        deleted = 0
        for root, dirs, files in os.walk(download_path):
            for file in files:
                if file.endswith(('.mp4', '.mp3', '.tmp')):
                    os.remove(os.path.join(root, file))
                    deleted += 1
        print(f'[完成] 已删除 {deleted} 个视频/音频文件')
    except Exception as e:
        print(f'[错误] {e}')
    input('\n按回车键返回...')

def check_for_updates():
    print('\n' + '=' * 50)
    p('       检查更新', 'c')
    print('=' * 50)
    
    try:
        p('[检查] 正在获取最新版本...', 'y')
        
        temp_file = "/storage/emulated/0/Download/termux.txt"
        download_cmd = f'curl -L -o {temp_file} "{UPDATE_URL}"'
        os.system(download_cmd)
        
        if os.path.exists(temp_file):
            with open(temp_file, 'r', encoding='utf-8') as f:
                new_content = f.read()
            
            new_version_match = re.search(r'VERSION\s*=\s*["\']([0-9.]+)["\']', new_content)
            current_version_match = re.search(r'VERSION\s*=\s*["\']([0-9.]+)["\']', open(SCRIPT_PATH, 'r', encoding='utf-8').read())
            
            new_version = new_version_match.group(1) if new_version_match else '0'
            current_version = current_version_match.group(1) if current_version_match else VERSION
            
            if new_version != current_version:
                p(f'[发现] 检测到新版本！', 'g')
                print(f'  当前版本: v{current_version}')
                print(f'  最新版本: v{new_version}')
                
                print("[提示] 直接回车 = 更新")
                choice = input('\n是否立即更新？(直接回车=是, 输入0=否): ').strip()
                if choice == '' or choice == '1':
                    backup_path = SCRIPT_PATH + '.bak'
                    with open(SCRIPT_PATH, 'r', encoding='utf-8') as f:
                        with open(backup_path, 'w', encoding='utf-8') as bf:
                            bf.write(f.read())
                    
                    os.system(f'cp {temp_file} {SCRIPT_PATH}')
                    os.system(f'chmod +x {SCRIPT_PATH}')
                    
                    p('  更新完成！', 'g')
                    print('\n' + '=' * 50)
                    p('       请手动输入 run 重新启动', 'c')
                    print('=' * 50)
                    input('\n按回车键退出...')
                    sys.exit(0)
                else:
                    p('[跳过] 本次不更新', 'y')
            else:
                p('[完成] 已是最新版本', 'g')
        else:
            p('[错误] 下载失败，请检查网络', 'r')
    except Exception as e:
        p(f'[错误] {e}', 'r')
    
    # ★★★ 新功能：检查更新后支持输入 r 用已下载脚本替换更新 ★★★
    temp_file = "/storage/emulated/0/Download/termux.txt"
    if os.path.exists(temp_file):
        print("\n" + "=" * 50)
        print("[提示] 输入 r = 用已下载的脚本替换更新")
        print("[提示] 直接回车 = 返回主菜单")
        print("=" * 50)
        choice = input('\n请输入 (直接回车=返回主菜单, r=替换更新): ').strip().lower()
        if choice == 'r':
            try:
                backup_path = SCRIPT_PATH + '.bak'
                with open(SCRIPT_PATH, 'r', encoding='utf-8') as f:
                    with open(backup_path, 'w', encoding='utf-8') as bf:
                        bf.write(f.read())
                os.system(f'cp {temp_file} {SCRIPT_PATH}')
                os.system(f'chmod +x {SCRIPT_PATH}')
                p('  替换更新完成！', 'g')
                print('\n' + '=' * 50)
                p('       请手动输入 run 重新启动', 'c')
                print('=' * 50)
                input('\n按回车键退出...')
                sys.exit(0)
            except Exception as e:
                p(f'[错误] 替换更新失败: {e}', 'r')
    else:
        input('\n按回车键返回...')
    
    os.system('rm -f /storage/emulated/0/Download/termux.txt')

def auto_check_for_updates():
    print('\n' + '=' * 50)
    p('       自动检查更新', 'c')
    print('=' * 50)
    
    try:
        p('[检查] 正在获取最新版本...', 'y')
        
        temp_file = "/storage/emulated/0/Download/termux_check.txt"
        download_cmd = f'curl -s -L -o {temp_file} "{UPDATE_URL}"'
        os.system(download_cmd)
        
        if os.path.exists(temp_file):
            with open(temp_file, 'r', encoding='utf-8', errors='ignore') as f:
                new_content = f.read()
            
            new_version_match = re.search(r'VERSION\s*=\s*["\']([0-9.]+)["\']', new_content)
            
            if new_version_match:
                new_version = new_version_match.group(1)
                current_version = VERSION
                
                if new_version != current_version:
                    p(f'[发现] 检测到新版本！', 'g')
                    print(f'  当前版本: v{current_version}')
                    print(f'  最新版本: v{new_version}')
                    
                    print("[提示] 直接回车 = 更新")
                    choice = input('\n是否立即更新？(直接回车=是, 输入0=否): ').strip()
                    if choice == '' or choice == '1':
                        update_temp = "/storage/emulated/0/Download/termux_update.txt"
                        os.system(f'curl -L -o {update_temp} "{UPDATE_URL}"')
                        if os.path.exists(update_temp):
                            backup_path = SCRIPT_PATH + '.bak'
                            with open(SCRIPT_PATH, 'r', encoding='utf-8') as f:
                                with open(backup_path, 'w', encoding='utf-8') as bf:
                                    bf.write(f.read())
                            
                            os.system(f'cp {update_temp} {SCRIPT_PATH}')
                            os.system(f'chmod +x {SCRIPT_PATH}')
                            
                            p('  更新完成！', 'g')
                            print('\n' + '=' * 50)
                            p('       请重新运行脚本', 'c')
                            print('=' * 50)
                            input('\n按回车键退出...')
                            sys.exit(0)
                        else:
                            p('[错误] 下载更新文件失败', 'r')
                    else:
                        p('[跳过] 本次不更新，继续使用当前版本', 'y')
                else:
                    p('[完成] 已是最新版本', 'g')
            else:
                p('[信息] 无法获取版本信息，跳过检查', 'y')
        else:
            p('[信息] 无法连接更新服务器，跳过检查', 'y')
    except Exception as e:
        p(f'[信息] 自动更新检查失败: {e}', 'y')
    
    os.system('rm -f /storage/emulated/0/Download/termux_check.txt')
    os.system('rm -f /storage/emulated/0/Download/termux_update.txt')
    print("=" * 50)

# ==================== 设置功能 ====================

def settings_menu():
    config = load_config()
    
    while True:
        print("\n" + "=" * 50)
        p("       设置", 'c')
        print("=" * 50)
        print("  [1] 设置启动快捷命令")
        print("  [2] 设置翻页快捷键")
        print("  [3] 切换调试模式")
        print("  [4] 设置下载路径")
        print("  [5] 切换跳过已存在文件")
        print("  [6] MP3封面设置")
        print("  [7] MP3下载设置 (封面/歌词)")
        print("  [8] LRC歌词API设置")
        print("  [9] 歌词增强设置（罗马音+翻译）")
        print("  [10] 进度条样式设置")
        print("  [11] 设置最大解析重试次数")  # 新增
        print("  [q] 返回主菜单")
        print("=" * 50)
        
        choice = input("\n请选择 [1-11/q]: ").strip().lower()
        
        if choice in ('q', '0'):
            return
        elif choice == '1':
            print("\n" + "=" * 50)
            p("       设置启动快捷命令", 'c')
            print("=" * 50)
            print(f"当前快捷命令: {config.get('shortcut_command', 'run')}")
            print("\n说明：在Termux中输入此命令即可直接启动脚本")
            print("示例：run、start、dl、下载器等")
            print("=" * 50)
            
            new_cmd = input("\n请输入新的快捷命令 (直接回车保持不变): ").strip()
            if new_cmd:
                if ' ' in new_cmd:
                    p("快捷命令不能包含空格！", 'r')
                    input("\n按回车键继续...")
                    continue
                
                config['shortcut_command'] = new_cmd
                if save_config(config):
                    p(f"快捷命令已设置为: {new_cmd}", 'g')
                    print(f"\n使用方法：在Termux中输入 {new_cmd} 即可启动脚本")
                    
                    bashrc_path = os.path.expanduser("~/.bashrc")
                    alias_line = f"alias {new_cmd}='python {SCRIPT_PATH}'"
                    
                    try:
                        if os.path.exists(bashrc_path):
                            with open(bashrc_path, 'r') as f:
                                content = f.read()
                        else:
                            content = ""
                        
                        old_pattern = r'^alias (run|start|dl|下载器)=.*$'
                        new_content = re.sub(old_pattern, '', content, flags=re.MULTILINE)
                        
                        if alias_line not in new_content:
                            new_content += f"\n{alias_line}\n"
                        
                        with open(bashrc_path, 'w') as f:
                            f.write(new_content)
                        
                        p("别名已添加到.bashrc", 'g')
                        print("请运行 'source ~/.bashrc' 使配置生效")
                    except Exception as e:
                        p(f"自动配置别名失败: {e}", 'y')
                        print(f"请手动添加以下内容到 ~/.bashrc：")
                        print(f"  alias {new_cmd}='python {SCRIPT_PATH}'")
                else:
                    p("保存配置失败", 'r')
            else:
                p("未作修改", 'y')
            
            input("\n按回车键继续...")
        elif choice == '2':
            print("\n" + "=" * 50)
            p("       设置翻页快捷键", 'c')
            print("=" * 50)
            print(f"当前上一页键: {config.get('key_prev', 'a')}")
            print(f"当前下一页键: {config.get('key_next', 'd')}")
            print(f"当前跳转键: {config.get('key_goto', 'g')}")
            print("\n说明：在分P列表页面使用这些键进行翻页和跳转")
            print("示例：w/s、up/down、j/k 等")
            print("跳转键用法: 按跳转键 + 页码 (如: g 5)")
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
            
            new_goto = input("请输入新的跳转键 (直接回车保持不变): ").strip()
            if new_goto:
                if len(new_goto) > 1:
                    p("快捷键只能是单个字符！", 'r')
                else:
                    config['key_goto'] = new_goto.lower()
                    p(f"跳转键已设置为: {new_goto}", 'g')
            
            if new_prev or new_next or new_goto:
                if save_config(config):
                    p("快捷键设置已保存", 'g')
                else:
                    p("保存配置失败", 'r')
            
            input("\n按回车键继续...")
        elif choice == '3':
            print("\n" + "=" * 50)
            p("       调试模式", 'c')
            print("=" * 50)
            current_debug = config.get('debug_mode', False)
            print(f"当前调试模式: {'开启' if current_debug else '关闭'}")
            print("\n开启后将在解析和下载时显示详细信息：")
            print("  - 视频解析详情（API响应、BV号、分P信息）")
            print("  - 每个分P的cid和下载链接")
            print("  - 封面下载和MP3嵌入详情")
            print("  - 下载进度和错误详情")
            print("=" * 50)
            
            print("\n[1] 开启调试模式")
            print("[2] 关闭调试模式")
            print("[q] 返回")
            
            sub_choice = input("\n请选择 [1-2/q]: ").strip().lower()
            if sub_choice in ('q', '0'):
                input("\n按回车键继续...")
                continue
            elif sub_choice == '1':
                config['debug_mode'] = True
                if save_config(config):
                    p("调试模式已开启", 'g')
                else:
                    p("保存配置失败", 'r')
            elif sub_choice == '2':
                config['debug_mode'] = False
                if save_config(config):
                    p("调试模式已关闭", 'g')
                else:
                    p("保存配置失败", 'r')
            
            input("\n按回车键继续...")
        elif choice == '4':
            print("\n" + "=" * 50)
            p("       设置下载路径", 'c')
            print("=" * 50)
            current_path = config.get('download_path', DEFAULT_DOWNLOAD_PATH)
            print(f"当前下载路径: {current_path}")
            print("\n说明：所有下载的视频和音频将保存到该目录")
            print("示例：/sdcard/Download/、/storage/emulated/0/Music/ 等")
            print("=" * 50)
            
            new_path = input("\n请输入新的下载路径 (直接回车保持不变): ").strip()
            if new_path:
                if new_path.startswith('~'):
                    new_path = os.path.expanduser(new_path)
                
                try:
                    os.makedirs(new_path, exist_ok=True)
                    config['download_path'] = new_path
                    if save_config(config):
                        p(f"下载路径已设置为: {new_path}", 'g')
                        global DOWNLOAD_PATH
                        DOWNLOAD_PATH = new_path
                    else:
                        p("保存配置失败", 'r')
                except Exception as e:
                    p(f"创建目录失败: {e}", 'r')
            else:
                p("未作修改", 'y')
            
            input("\n按回车键继续...")
        elif choice == '5':
            print("\n" + "=" * 50)
            p("       切换跳过已存在文件", 'c')
            print("=" * 50)
            current_skip = config.get('skip_existing', True)
            print(f"当前状态: {'开启' if current_skip else '关闭'}")
            print("\n开启后，如果下载目录已存在同名文件，将自动跳过下载")
            print("关闭后，将重新下载并覆盖已存在的文件")
            print("=" * 50)
            
            print("\n[1] 开启跳过")
            print("[2] 关闭跳过")
            print("[q] 返回")
            
            sub_choice = input("\n请选择 [1-2/q]: ").strip().lower()
            if sub_choice in ('q', '0'):
                input("\n按回车键继续...")
                continue
            elif sub_choice == '1':
                config['skip_existing'] = True
                if save_config(config):
                    p("已开启跳过已存在文件", 'g')
                else:
                    p("保存配置失败", 'r')
            elif sub_choice == '2':
                config['skip_existing'] = False
                if save_config(config):
                    p("已关闭跳过已存在文件（将覆盖下载）", 'g')
                else:
                    p("保存配置失败", 'r')
            
            input("\n按回车键继续...")
        elif choice == '6':
            print("\n" + "=" * 50)
            p("       MP3封面设置", 'c')
            print("=" * 50)
            current_mode = config.get('cover_mode', 'api')
            current_crop = config.get('cover_crop', 'center')
            crop_text = {"center": "居中", "top": "上部", "bottom": "下部", "left": "左侧", "right": "右侧"}.get(current_crop, "居中")
            
            print(f"当前封面模式: {'API封面' if current_mode == 'api' else '视频截图'}")
            print(f"当前裁剪位置: {crop_text}")
            print("\n选择MP3封面设置：")
            print("  [1] 封面来源 - API封面（从B站API获取视频封面）")
            print("  [2] 封面来源 - 视频截图（截取MP4第一帧作为封面）")
            print("  [3] 裁剪位置调整")
            print("  [q] 返回")
            print("=" * 50)
            
            sub_choice = input("\n请选择 [1-3/q]: ").strip().lower()
            if sub_choice in ('q', '0'):
                input("\n按回车键继续...")
                continue
            elif sub_choice == '1':
                config['cover_mode'] = 'api'
                if save_config(config):
                    p("已切换为API封面模式", 'g')
                else:
                    p("保存配置失败", 'r')
            elif sub_choice == '2':
                config['cover_mode'] = 'video'
                if save_config(config):
                    p("已切换为视频截图封面模式", 'g')
                else:
                    p("保存配置失败", 'r')
            elif sub_choice == '3':
                print("\n" + "=" * 50)
                p("       封面裁剪位置调整", 'c')
                print("=" * 50)
                print("选择裁剪位置：")
                print("  [1] 居中（默认）")
                print("  [2] 上部")
                print("  [3] 下部")
                print("  [4] 左侧")
                print("  [5] 右侧")
                print("  [q] 返回")
                print("=" * 50)
                
                crop_choice = input("\n请选择 [1-5/q]: ").strip().lower()
                if crop_choice in ('q', '0'):
                    input("\n按回车键继续...")
                    continue
                crop_map = {
                    '1': 'center',
                    '2': 'top',
                    '3': 'bottom',
                    '4': 'left',
                    '5': 'right'
                }
                if crop_choice in crop_map:
                    config['cover_crop'] = crop_map[crop_choice]
                    if save_config(config):
                        crop_name = {"center": "居中", "top": "上部", "bottom": "下部", "left": "左侧", "right": "右侧"}.get(crop_map[crop_choice], "居中")
                        p(f"裁剪位置已设置为: {crop_name}", 'g')
                    else:
                        p("保存配置失败", 'r')
            
            input("\n按回车键继续...")
        elif choice == '7':
            mp3_settings_menu()
            continue
        elif choice == '8':
            lrc_api_settings_menu()
            continue
        elif choice == '9':
            lyric_enhance_settings_menu()
            continue
        elif choice == '10':
            progress_bar_style_menu()
            continue
        elif choice == '11':
            # 新增：设置最大解析重试次数
            print("\n" + "=" * 50)
            p("       设置最大解析重试次数", 'c')
            print("=" * 50)
            current_max = config.get('max_parse_retries', 5)
            print(f"当前最大解析重试次数: {current_max}")
            print("\n说明：当解析视频失败时，脚本会自动重试")
            print("  建议值：3-10 次")
            print("  设置太大会增加等待时间，太小可能解析失败")
            print("  当前默认值：5次")
            print("=" * 50)
            
            new_max = input("\n请输入新的最大重试次数 (1-20，直接回车保持不变): ").strip()
            if new_max:
                try:
                    new_max_int = int(new_max)
                    if 1 <= new_max_int <= 20:
                        config['max_parse_retries'] = new_max_int
                        if save_config(config):
                            p(f"最大解析重试次数已设置为: {new_max_int}", 'g')
                        else:
                            p("保存配置失败", 'r')
                    else:
                        p("请输入 1-20 之间的数字", 'y')
                except ValueError:
                    p("请输入有效的数字", 'y')
            else:
                p("未作修改", 'y')
            
            input("\n按回车键继续...")
        else:
            p("无效选项", 'y')
            input("\n按回车键继续...")
# ==================== 搜索视频功能 ====================

def search_platform_menu():
    print("\n" + "=" * 50)
    p("       搜索平台", 'c')
    print("=" * 50)
    print("  [1] 哔哩哔哩 (Bilibili)")
    print("  [2] YouTube")
    print("  [q] 返回主菜单")
    print("=" * 50)
    print("[提示] 直接按回车返回主菜单")
    
    while True:
        choice = input("\n请选择 [1-2/q] 或直接回车: ").strip().lower()
        if choice == '' or choice in ('q', '0'):
            return None
        elif choice == '1':
            return 'bilibili'
        elif choice == '2':
            return 'youtube'
        else:
            p('无效选项，请重新输入', 'y')

# ==================== YouTube 搜索功能 ====================

def youtube_search(keyword, max_results=20):
    if not get_cookies_path():
        show_youtube_cookies_guide()
        return None
    
    try:
        debug_print(f'YouTube搜索关键词: {keyword}, 最大结果: {max_results}')
        
        cmd = [
            'yt-dlp',
            f'ytsearch{max_results}:{keyword}',
            '--flat-playlist',
            '--dump-json',
            '--no-warnings',
            '--no-playlist',
            '--no-check-certificates',
            '--geo-bypass',
            '--socket-timeout', '30',
        ]
        
        cookies_path = get_cookies_path()
        if cookies_path:
            cmd.extend(['--cookies', cookies_path])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            debug_print(f'yt-dlp搜索失败: {result.stderr}')
            return youtube_search_alternative(keyword, max_results)
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get('_type') == 'url' or data.get('_type') == 'playlist':
                    continue
                
                video_id = data.get('id', '')
                if not video_id:
                    continue
                
                duration = data.get('duration', 0)
                if duration:
                    minutes = duration // 60
                    seconds = duration % 60
                    duration_str = f"{minutes}:{seconds:02d}"
                else:
                    duration_str = "未知"
                
                videos.append({
                    'id': video_id,
                    'title': data.get('title', '未知标题'),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'duration': duration_str,
                    'duration_seconds': duration,
                    'uploader': data.get('uploader', '未知'),
                    'view_count': data.get('view_count', 0),
                    'thumbnail': data.get('thumbnail', '')
                })
                debug_print(f'  {data.get("title", "")[:40]}... (ID:{video_id})')
            except json.JSONDecodeError:
                continue
        
        if videos:
            return videos
        else:
            return youtube_search_alternative(keyword, max_results)
        
    except subprocess.TimeoutExpired:
        p('[超时] YouTube搜索超时，尝试备用方法...', 'y')
        return youtube_search_alternative(keyword, max_results)
    except Exception as e:
        p(f'[YouTube搜索错误] {e}', 'r')
        debug_print(f'YouTube搜索异常: {e}')
        return youtube_search_alternative(keyword, max_results)

def youtube_search_alternative(keyword, max_results=20):
    if not get_cookies_path():
        return None
    
    try:
        debug_print(f'使用备用YouTube搜索: {keyword}')
        
        cmd = [
            'yt-dlp',
            f'ytsearch{max_results}:{keyword}',
            '-j',
            '--no-warnings',
            '--no-playlist',
            '--ignore-errors',
            '--socket-timeout', '30',
        ]
        
        cookies_path = get_cookies_path()
        if cookies_path:
            cmd.extend(['--cookies', cookies_path])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            debug_print(f'备用搜索失败: {result.stderr}')
            return None
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                video_id = data.get('id', '')
                if not video_id:
                    continue
                
                duration = data.get('duration', 0)
                if duration:
                    minutes = duration // 60
                    seconds = duration % 60
                    duration_str = f"{minutes}:{seconds:02d}"
                else:
                    duration_str = "未知"
                
                videos.append({
                    'id': video_id,
                    'title': data.get('title', '未知标题'),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'duration': duration_str,
                    'duration_seconds': duration,
                    'uploader': data.get('uploader', '未知'),
                    'view_count': data.get('view_count', 0),
                    'thumbnail': data.get('thumbnail', '')
                })
            except json.JSONDecodeError:
                continue
        
        return videos if videos else None
        
    except Exception as e:
        debug_print(f'备用搜索异常: {e}')
        return None

def process_youtube_search():
    print("\n" + "=" * 50)
    p("       搜索视频 - YouTube", 'c')
    print("=" * 50)
    
    if not check_and_prompt_youtube_cookies(show_guide=True):
        p('[取消] YouTube 需要 cookies 认证', 'y')
        return
    
    keyword = input("\n请输入搜索内容(YouTube): ").strip()
    while not keyword:
        p("搜索内容不能为空！", 'y')
        print("\n选项:")
        print("  [回车] 重新输入搜索内容")
        print("  [0] 返回平台选择")
        print("  [q] 返回主菜单")
        choice = input("\n请选择: ").strip().lower()
        if choice == '0':
            return
        elif choice == 'q':
            return None
        else:
            keyword = input("\n请输入搜索内容(YouTube): ").strip()
    
    max_results = 20
    selected_videos = []
    current_page = 0
    page_size = 10
    search_attempts = 0
    
    while True:
        videos = None
        while search_attempts < 3 and not videos:
            if search_attempts > 0:
                p(f'\n[重试 {search_attempts}/3] 重新搜索...', 'y')
                time.sleep(2)
            
            p(f'\n[搜索] "{keyword}" ...', 'c')
            videos = youtube_search(keyword, max_results)
            search_attempts += 1
        
        if not videos:
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
                search_attempts = 0
                continue
            elif choice == '2':
                keyword = input("\n请输入搜索内容(YouTube): ").strip()
                if keyword:
                    search_attempts = 0
                    continue
            elif choice == '0':
                return
            elif choice == 'q':
                return None
            elif choice == '4' and selected_videos:
                break
            else:
                p("无效选项", 'y')
                continue
        
        total_pages = (len(videos) + page_size - 1) // page_size
        
        start = current_page * page_size
        end = min(start + page_size, len(videos))
        page_videos = videos[start:end]
        
        print("\n" + "=" * 60)
        p(f"       YouTube搜索结果 (第 {current_page+1}/{total_pages} 页)", 'c')
        print("=" * 60)
        
        for i, video in enumerate(page_videos, 1):
            display_num = start + i
            title = video['title'][:55] + '...' if len(video['title']) > 55 else video['title']
            duration = video['duration']
            uploader = video['uploader'][:20]
            views = video['view_count']
            if views >= 10000:
                views_str = f"{views/10000:.1f}万"
            else:
                views_str = str(views)
            
            print(f"  {display_num}. {title}")
            print(f"     UP主: {uploader}  |  播放: {views_str}  |  时长: {duration}")
            print("-" * 56)
        
        print("\n" + "=" * 60)
        p(f"       搜索结果 (第 {current_page+1}/{total_pages} 页)", 'c')
        print("=" * 60)
        config = load_config()
        key_prev = config.get('key_prev', 'a')
        key_next = config.get('key_next', 'd')
        key_goto = config.get('key_goto', 'g')
        print(f"操作说明:")
        print(f"  输入数字 [1-{len(page_videos)}] 选择视频（按当前页顺序）")
        print(f"  输入 'm' 进入多选模式")
        print(f"  输入 'c' 确认并开始解析")
        print(f"  输入 '0' 返回平台选择")
        print(f"  输入 'q' 返回主菜单")
        print(f"  输入 {key_next} 下一页  |  输入 {key_prev} 上一页")
        print(f"  输入 {key_goto} + 页码 跳转到指定页 (如: {key_goto} 5)")
        if selected_videos:
            print(f"  [提示] 当前已选中 {len(selected_videos)} 个视频")
        print("=" * 60)
        
        user_choice = input("\n请选择: ").strip().lower()
        
        if user_choice == '0':
            return
        elif user_choice == 'q':
            if selected_videos:
                confirm = input("确认退出？(直接回车退出，输入0取消): ").strip()
                if confirm == '' or confirm == '1':
                    return None
                else:
                    continue
            else:
                return None
        
        elif user_choice == key_next:
            if current_page < total_pages - 1:
                current_page += 1
                continue
            else:
                p("[提示] 已经是最后一页了", 'y')
                continue
        elif user_choice == key_prev:
            if current_page > 0:
                current_page -= 1
                continue
            else:
                p("[提示] 已经是第一页了", 'y')
                continue
        elif user_choice.startswith(key_goto):
            parts = user_choice.split()
            if len(parts) >= 2 and parts[1].isdigit():
                target_page = int(parts[1]) - 1
                if 0 <= target_page < total_pages:
                    current_page = target_page
                    continue
                else:
                    p(f"页码范围: 1-{total_pages}", 'y')
                    continue
            else:
                p(f"格式错误，请输入: {key_goto} 页码 (如: {key_goto} 5)", 'y')
                continue
        
        elif user_choice == 'c':
            if selected_videos:
                break
            else:
                p("没有选中任何视频", 'y')
                continue
        
        elif user_choice == 'm':
            result_count = len(page_videos)
            print(f"\n当前页有 {result_count} 个视频")
            print("输入格式示例:")
            print("  - 单个: 1 3 5")
            print("  - 范围: 1-5")
            print("  - 混合: 1 3-5 7")
            print("  - 全部: all")
            
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
                video = page_videos[idx]
                already_selected = False
                for v in selected_videos:
                    if v['id'] == video['id']:
                        already_selected = True
                        break
                if not already_selected:
                    selected_videos.append(video)
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
            print("  [0] 返回平台选择")
            print("  [q] 返回主菜单")
            action = input("\n请选择: ").strip().lower()
            if action == '1':
                keyword = input("\n请输入搜索内容(YouTube): ").strip()
                if keyword:
                    current_page = 0
                    search_attempts = 0
                    continue
                else:
                    continue
            elif action == '2':
                if selected_videos:
                    break
                else:
                    p("没有选中任何视频", 'y')
                    continue
            elif action == '0':
                return
            elif action == 'q':
                return None
            else:
                continue
        
        elif user_choice.isdigit():
            idx = int(user_choice) - 1
            if 0 <= idx < len(page_videos):
                selected = page_videos[idx]
                p(f'\n[选中] {selected["title"]}', 'g')
                
                already = False
                for v in selected_videos:
                    if v['id'] == selected['id']:
                        already = True
                        break
                
                if already:
                    p("该视频已经在选择列表中", 'y')
                else:
                    selected_videos.append(selected)
                    p(f"已添加，当前共选中 {len(selected_videos)} 个视频", 'g')
                    
                    print("\n操作选项:")
                    print("  [1] 继续搜索添加更多视频")
                    print("  [2] 确认并开始解析")
                    print("  [0] 返回平台选择")
                    print("  [q] 返回主菜单")
                    action = input("\n请选择: ").strip().lower()
                    if action == '1':
                        keyword = input("\n请输入搜索内容(YouTube): ").strip()
                        if keyword:
                            current_page = 0
                            search_attempts = 0
                            continue
                    elif action == '2':
                        if selected_videos:
                            break
                    elif action == '0':
                        return
                    elif action == 'q':
                        return None
            else:
                p(f"[错误] 请输入 1-{len(page_videos)} 之间的数字", 'y')
                continue
        else:
            p("无效输入，请重新输入", 'y')
            continue
    
    if not selected_videos:
        p('[取消] 未选择视频', 'y')
        return
    
    print("\n" + "=" * 50)
    p(f'       已选中 {len(selected_videos)} 个视频', 'g')
    print('=' * 50)
    for i, video in enumerate(selected_videos, 1):
        title = video['title'][:50] + '...' if len(video['title']) > 50 else video['title']
        print(f'  {i}. {title}')
    print('=' * 50)
    
    print("请选择下载模式：")
    print("  [3] 两者都要（MP4+MP3）")
    print("  [2] 仅MP3（下载音频）")
    print("  [1] 仅MP4（下载视频）")
    print("  [q] 取消")
    print("=" * 50)
    
    mode_choice = input("\n请选择 [1-3/q]: ").strip().lower()
    if mode_choice in ('q', '0'):
        p("已取消", 'y')
        return
    if mode_choice not in ['1', '2', '3']:
        p("无效选项，使用模式2（仅MP3）", 'y')
        mode_choice = '2'
    
    mode = int(mode_choice)
    mode_text = {1: 'MP4', 2: 'MP3', 3: 'MP4+MP3'}.get(mode, 'MP3')
    p(f"\n[设置] 下载模式: {mode_text}", 'c')
    
    print(f"\n开始处理 {len(selected_videos)} 个视频...")
    print("提示：按 Ctrl+C 可中断处理")
    
    success_count = 0
    fail_count = 0
    
    for idx, video in enumerate(selected_videos, 1):
        print(f"\n{'=' * 50}")
        print(f"[{idx}/{len(selected_videos)}] {video['title'][:60]}")
        print("=" * 50)
        
        mp4_path = download_file(video['url'], video['title'])
        if mp4_path:
            if mode == 1:
                p(f"[完成] 视频: {os.path.basename(mp4_path)}", 'g')
                success_count += 1
            elif mode in (2, 3):
                mp3_path = download_mp3_with_settings(
                    mp4_path, 
                    video.get('thumbnail', ''), 
                    None, 
                    None, 
                    video['title']
                )
                if mp3_path:
                    if mode == 2:
                        if os.path.exists(mp4_path):
                            os.remove(mp4_path)
                        p(f"[完成] 音频: {os.path.basename(mp3_path)}", 'g')
                    else:
                        p(f"[完成] 视频: {os.path.basename(mp4_path)}", 'g')
                        p(f"[完成] 音频: {os.path.basename(mp3_path)}", 'g')
                    success_count += 1
                else:
                    fail_count += 1
        else:
            fail_count += 1
    
    print("\n" + "=" * 50)
    p("       处理完成", 'c')
    print("=" * 50)
    p(f"成功: {success_count} 个", 'g')
    p(f"失败: {fail_count} 个", 'r' if fail_count > 0 else 'g')
    print("=" * 50)
    p(f"保存位置: {get_download_path()}", 'c')
    input("\n按回车键返回主菜单...")

# ==================== B站搜索功能（带翻页和跳转） ====================

def bili_search(keyword, page=1, page_size=20, max_retries=3):
    retry_count = 0
    
    while retry_count < max_retries:
        if retry_count > 0:
            p(f'\n[重试 {retry_count}/{max_retries-1}] 等待 {retry_count * 2} 秒后重试...', 'y')
            time.sleep(retry_count * 2)
        
        try:
            debug_print(f'搜索关键词: {keyword}, 页码: {page}')
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
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
                debug_print('HTTP 412 反爬拒绝')
                retry_count += 1
                continue
            elif resp.status_code != 200:
                p(f'[搜索失败] HTTP {resp.status_code}', 'r')
                debug_print(f'HTTP错误: {resp.status_code}')
                retry_count += 1
                continue
            
            try:
                data = resp.json()
                debug_print(f'搜索API响应code: {data.get("code")}')
            except json.JSONDecodeError as e:
                p(f'[JSON解析错误] {e}', 'r')
                debug_print(f'JSON解析错误: {e}')
                retry_count += 1
                continue
            
            if data.get('code') != 0:
                p(f'[搜索失败] {data.get("message", "未知错误")}', 'r')
                debug_print(f'搜索失败: {data.get("message")}')
                retry_count += 1
                continue
            
            result = data.get('data', {})
            videos = result.get('result', [])
            debug_print(f'搜索结果数量: {len(videos)}')
            
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
                debug_print(f'  {title[:40]}... (BV:{bvid}, 播放:{item.get("play",0)})')
            
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
            debug_print('请求超时')
            retry_count += 1
            continue
        except requests.exceptions.ConnectionError:
            p(f'[连接错误] 无法连接到服务器，第 {retry_count + 1} 次重试', 'y')
            debug_print('连接错误')
            retry_count += 1
            continue
        except Exception as e:
            p(f'[搜索异常] {e}', 'r')
            debug_print(f'搜索异常: {e}')
            retry_count += 1
            continue
    
    p('[错误] 多次重试失败，请检查网络连接', 'r')
    return None

def display_search_results(results, page, total_pages, selected_videos=None):
    """显示搜索结果（带翻页和跳转功能）"""
    config = load_config()
    key_prev = config.get('key_prev', 'a')
    key_next = config.get('key_next', 'd')
    key_goto = config.get('key_goto', 'g')
    
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
    print(f"  输入 {key_goto} + 页码 跳转到指定页 (如: {key_goto} 5)")
    if selected_videos:
        print(f"  [提示] 当前已选中 {len(selected_videos)} 个视频")
    print("=" * 60)

def search_videos():
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
                return
            elif choice == 'q':
                return None
            else:
                keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
        
        page = 1
        page_size = 20
        selected_videos = []
        config = load_config()
        key_prev = config.get('key_prev', 'a')
        key_next = config.get('key_next', 'd')
        key_goto = config.get('key_goto', 'g')
        
        while True:
            p(f'\n[搜索] "{keyword}" 第 {page} 页...', 'c')
            result = bili_search(keyword, page, page_size)
            
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
                    continue
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
                    return
                elif choice == 'q':
                    return None
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
                    return
                elif choice == 'q':
                    return None
                elif choice == '3' and selected_videos:
                    break
                else:
                    continue
            
            results = result['results']
            results.sort(key=lambda x: -x['play'])
            
            display_search_results(results, page, result['num_pages'], selected_videos)
            
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
            
            user_choice = input("\n请选择: ").strip().lower()
            
            if user_choice == '0':
                return
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
                            action = '1'
                        elif action == '0':
                            return
                        elif action == 'q':
                            return None
                        elif action == '1':
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
                                        break
                                    else:
                                        keyword = input("\n请输入搜索内容(哔哩哔哩): ").strip()
                                        if keyword:
                                            break
                                if keyword:
                                    page = 1
                                    break
                                else:
                                    continue
                            elif sub_choice == '2':
                                continue
                            elif sub_choice == '0':
                                return
                            elif sub_choice == 'q':
                                return None
                            else:
                                p("无效选项", 'y')
                                continue
                        elif action == '2':
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
                    
                    if action == '2':
                        break
                    else:
                        continue
                else:
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
            elif user_choice.startswith(key_goto):
                parts = user_choice.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    target_page = int(parts[1])
                    if 1 <= target_page <= result['num_pages']:
                        page = target_page
                        continue
                    else:
                        p(f"页码范围: 1-{result['num_pages']}", 'y')
                        continue
                else:
                    p(f"格式错误，请输入: {key_goto} 页码 (如: {key_goto} 5)", 'y')
                    continue
            elif user_choice.isdigit():
                idx = int(user_choice) - 1
                if 0 <= idx < len(results):
                    selected = results[idx]
                    p(f'\n[选中] {selected["title"]}', 'g')
                    debug_print(f'选中视频: {selected["title"]}, BV: {selected["bvid"]}')
                    
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
                        debug_print(f'已添加视频: {selected["title"]}')
                        
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
        
        if not selected_videos:
            p('[取消] 未选择视频', 'y')
            return
        
        while True:
            p(f'\n{"="*50}', 'm')
            p(f'       已选中 {len(selected_videos)} 个视频', 'g')
            print('=' * 50)
            for i, video in enumerate(selected_videos, 1):
                title = video['title'][:50] + '...' if len(video['title']) > 50 else video['title']
                print(f'  {i}. {title}')
            print('=' * 50)
            
            mode = show_video_mode_menu(allow_return=True)
            
            if mode == 'main_menu':
                p('[取消] 已返回主菜单', 'y')
                return
            elif mode == 'reselect':
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
                    break
                else:
                    continue
            else:
                print("\n[提示] 直接回车 = 开始处理")
                if input('\n开始处理? (直接回车=是, 输入0取消): ').strip() in ['', '1', '是', 'yes', 'y']:
                    success = 0
                    fail = 0
                    for video in selected_videos:
                        video_url = f"https://www.bilibili.com/video/{video['bvid']}"
                        debug_print(f'处理选中的视频: {video["title"]} ({video_url})')
                        if process_single_video(video_url, mode):
                            success += 1
                        else:
                            fail += 1
                    p(f'\n[完成] 成功: {success}  失败: {fail}', 'g')
                    p(f'保存位置: {get_download_path()}', 'c')
                    input("\n按回车键返回主菜单...")
                    return
                else:
                    p('[取消] 已取消处理，返回选择菜单', 'y')
                    continue
    
    elif platform == 'youtube':
        process_youtube_search()

# ==================== 智能搜索功能 ====================

def smart_search_bilibili_for_song(song_name, max_retries=3):
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
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
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
                            
                            pic = item.get('pic', '')
                            if pic and pic.startswith('//'):
                                pic = 'https:' + pic
                            elif pic and not pic.startswith(('http://', 'https://')):
                                pic = 'https://' + pic
                            
                            all_results.append({
                                'bvid': item.get('bvid', ''),
                                'title': title,
                                'author': item.get('author', ''),
                                'play': item.get('play', 0),
                                'duration': item.get('duration', ''),
                                'pic': pic,
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
        print("  [q] 取消整个任务")
        print("[提示] 直接回车 = 重试")
        
        while True:
            choice = input("\n请选择 [1-2/q] 或直接回车: ").strip().lower()
            if choice == '' or choice == '1':
                return smart_search_bilibili_for_song(song_name, max_retries)
            elif choice == '2':
                return None
            elif choice in ('q', '0'):
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

# ==================== 粘贴歌单处理 ====================

def get_multiline_input_ctrl_d(prompt):
    print(prompt)
    print("提示：粘贴完成后按 Ctrl+D 结束输入")
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

def process_copied_playlist():
    print("\n" + "=" * 50)
    p("       粘贴歌单模式", 'c')
    print("=" * 50)
    print("使用说明：")
    print("  1. 在浏览器中打开酷狗歌单网页")
    print("  2. 向下滚动到页面底部，让所有歌曲都加载出来")
    print("  3. 长按页面 -> 全选 -> 复制")
    print("  4. 粘贴到下方（支持多行粘贴，按 Ctrl+D 结束）")
    print("=" * 50)
    
    while True:
        raw_text = get_multiline_input_ctrl_d("\n请粘贴网页内容（粘贴后按 Ctrl+D 结束）:")
        
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
    print("  [q] 返回主菜单")
    print("=" * 50)
    
    mode_choice = input("\n请输入选项 [1-3/q]: ").strip().lower()
    if mode_choice in ('q', '0'):
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
    p(f"保存位置: {get_download_path()}", 'c')
    input("\n按回车键返回主菜单...")
# ==================== MP3封面管理功能（完整版）====================

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

def has_mp3_cover(mp3_path):
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags and audio.tags.getall('APIC'):
            return True
        return False
    except:
        return False

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

def batch_add_mp3_covers():
    print("\n" + "=" * 60)
    p("       MP3封面智能管理工具", 'c')
    print("=" * 60)
    
    cover_mode = get_cover_mode()
    cover_mode_text = "API封面" if cover_mode == "api" else "视频截图"
    cover_crop = get_cover_crop()
    crop_text = {"center": "居中", "top": "上部", "bottom": "下部", "left": "左侧", "right": "右侧"}.get(cover_crop, "居中")
    print(f"当前封面模式: {cover_mode_text}")
    print(f"当前裁剪位置: {crop_text}")
    print("=" * 60)
    
    while True:
        folder_path = input("\n请输入MP3文件夹路径 (直接回车使用下载目录): ").strip()
        if not folder_path:
            folder_path = get_download_path()
            print(f"使用下载目录: {folder_path}")
            break
        if folder_path.startswith('~'):
            folder_path = os.path.expanduser(folder_path)
        folder_path = os.path.abspath(folder_path)
        if os.path.exists(folder_path):
            break
        else:
            p(f'[错误] 文件夹不存在: {folder_path}', 'r')
            print("[提示] 直接回车 = 重新输入")
    
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
    print(f"{'='*50}")
    
    if mp3_without_cover:
        print("\n无封面的MP3文件：")
        for i, mp3_path in enumerate(mp3_without_cover, 1):
            rel_path = os.path.relpath(mp3_path, folder_path)
            print(f"  {i}. {rel_path}")
    
    print("\n选项:")
    print("  [1] 仅处理无封面的文件")
    if mp3_with_cover:
        print("  [2] 处理所有文件（包括替换已有封面）")
    print("  [3] 手动选择要处理的文件")
    print("  [q] 返回主菜单")
    
    choice = input("\n请选择 [1-3/q]: ").strip().lower()
    
    if choice in ('q', '0'):
        return
    elif choice == '1':
        selected_files = mp3_without_cover
        if not selected_files:
            p('[提示] 没有无封面的文件需要处理', 'g')
            input("\n按回车键返回...")
            return
    elif choice == '2' and mp3_with_cover:
        selected_files = all_mp3_files
        p('[提示] 将处理所有文件，已有封面的将被替换', 'y')
        confirm = input("确认继续？(直接回车=是, 输入0=否): ").strip()
        if confirm == '' or confirm == '1':
            pass
        else:
            return
    elif choice == '3':
        display_mp3_list_with_status(all_mp3_files, folder_path, "所有MP3文件")
        print(f"\n请输入要处理的文件序号 (1-{len(all_mp3_files)})")
        print("格式示例: 1,3,5 或 1-3 或 0(全部)")
        selection = input("请输入: ").strip()
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
    
    if not selected_files:
        p('[取消] 没有选择任何文件', 'y')
        return
    
    print(f"\n将要处理 {len(selected_files)} 个文件")
    confirm = input("\n确认开始处理？(直接回车=是, 输入0=否): ").strip()
    if confirm != '' and confirm != '1':
        p('[取消] 已取消处理', 'y')
        return
    
    p(f'\n开始处理 {len(selected_files)} 个文件...', 'c')
    
    success_count = 0
    fail_count = 0
    
    for i, mp3_path in enumerate(selected_files, 1):
        rel_path = os.path.relpath(mp3_path, folder_path)
        p(f'\n[{i}/{len(selected_files)}] {rel_path}', 'm')
        
        if process_mp3_cover(mp3_path):
            success_count += 1
            p(f'[成功] 封面已添加/更新', 'g')
        else:
            fail_count += 1
            p(f'[失败] 处理失败', 'r')
    
    print("\n" + "=" * 50)
    p("       处理完成", 'c')
    print("=" * 50)
    p(f'成功: {success_count} 个', 'g')
    p(f'失败: {fail_count} 个', 'r' if fail_count > 0 else 'g')
    print("=" * 50)
    input("\n按回车键返回...")

def manual_replace_mp3_cover():
    print("\n" + "=" * 60)
    p("       手动替换MP3封面", 'c')
    print("=" * 60)
    
    cover_mode = get_cover_mode()
    cover_mode_text = "API封面" if cover_mode == "api" else "视频截图"
    cover_crop = get_cover_crop()
    crop_text = {"center": "居中", "top": "上部", "bottom": "下部", "left": "左侧", "right": "右侧"}.get(cover_crop, "居中")
    print(f"当前封面模式: {cover_mode_text}")
    print(f"当前裁剪位置: {crop_text}")
    print("=" * 60)
    
    while True:
        mp3_path = input("\n请输入MP3文件完整路径: ").strip()
        if not mp3_path:
            p('[取消] 未输入路径', 'y')
            return
        if mp3_path.startswith('~'):
            mp3_path = os.path.expanduser(mp3_path)
        mp3_path = os.path.abspath(mp3_path)
        if os.path.exists(mp3_path) and mp3_path.lower().endswith('.mp3'):
            break
        else:
            p(f'[错误] 文件不存在或不是MP3文件: {mp3_path}', 'r')
            print("[提示] 直接回车 = 重新输入, 输入0 = 返回")
            choice = input("是否重新输入？(直接回车=是, 输入0=否): ").strip()
            if choice == '0':
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

def get_mp3_duration(mp3_path):
    try:
        audio = MP3(mp3_path)
        return int(audio.info.length)
    except:
        return 0

def process_mp3_cover(mp3_path):
    try:
        base_name = os.path.basename(mp3_path)
        song_name = os.path.splitext(base_name)[0]
        song_name = re.sub(r'[_\-\d]+$', '', song_name)
        song_name = song_name.strip()
        
        cover_tmp = mp3_path.replace('.mp3', '_temp_cover.jpg')
        cover_added = False
        
        cover_mode = get_cover_mode()
        
        if cover_mode == "api":
            p(f'[搜索] 正在搜索: {song_name}', 'y')
            search_result = smart_search_bilibili_for_song(song_name)
            if search_result:
                cover_url = search_result.get('pic', '')
                if not cover_url and search_result.get('bvid'):
                    p(f'[获取] 通过BV号获取封面...', 'c')
                    cover_url = get_bilibili_cover(search_result['bvid'])
                if cover_url:
                    p(f'[下载] 下载API封面...', 'c')
                    if download_and_crop_cover(cover_url, cover_tmp):
                        p('[封面] API封面下载成功', 'g')
                        cover_added = True
        elif cover_mode == "video":
            mp4_path = mp3_path.replace('.mp3', '.mp4')
            if os.path.exists(mp4_path):
                p(f'[提取] 从视频提取封面...', 'c')
                if extract_cover_from_video(mp4_path, cover_tmp):
                    p('[封面] 视频截图成功', 'g')
                    cover_added = True
            else:
                p(f'[警告] 找不到对应的MP4文件: {os.path.basename(mp4_path)}', 'y')
                p(f'[备用] 尝试搜索B站封面...', 'y')
                search_result = smart_search_bilibili_for_song(song_name)
                if search_result:
                    cover_url = search_result.get('pic', '')
                    if not cover_url and search_result.get('bvid'):
                        p(f'[获取] 通过BV号获取封面...', 'c')
                        cover_url = get_bilibili_cover(search_result['bvid'])
                    if cover_url:
                        if download_and_crop_cover(cover_url, cover_tmp):
                            p('[封面] 备用封面下载成功', 'g')
                            cover_added = True
        
        if cover_added:
            if add_cover_to_mp3_file(mp3_path, cover_tmp):
                try:
                    os.remove(cover_tmp)
                except:
                    pass
                return True
        
        return False
        
    except Exception as e:
        p(f'[异常] 处理失败: {e}', 'r')
        return False

def add_cover_to_mp3_file(mp3_path, cover_image_path):
    try:
        try:
            audio = MP3(mp3_path, ID3=ID3)
        except Exception as e:
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
        
        try:
            if audio.tags is not None:
                audio.tags.delall('APIC')
        except:
            try:
                audio.tags = ID3()
            except:
                pass
        
        try:
            audio.tags.add(apic)
        except:
            audio = MP3(mp3_path)
            audio.add_tags()
            audio.tags.add(apic)
        
        audio.save(v2_version=3)
        return True
        
    except Exception as e:
        p(f'[添加封面失败] {e}', 'r')
        return False

# ==================== 主菜单 ====================

def show_main_menu():
    print('\n' + '=' * 50)
    p('       主菜单', 'c')
    print('=' * 50)
    
    # 始终显示未完成任务选项
    print('  [l] 未完成的任务')
    
    # ★★★ B站功能选项 ★★★
    print('  [b] B站收藏夹批量下载')
    print('  [h] B站历史记录')
    print('  [a] B站账号管理(登录/退出/记录)')
    
    print('  [1] 开始下载视频')
    print('  [2] 搜索视频 (B站/YouTube)')
    print('  [3] MP3封面批量管理')
    print('  [4] 手动替换单个MP3封面')
    print('  [5] 粘贴歌单网页内容（自动提取歌名并批量下载）')
    print('  [6] 检查更新')
    print('  [7] LRC歌词批量下载')
    print('  [8] 从B站视频生成LRC歌词')
    print('  [9] 卸载工具')
    print('  [0] 设置')
    print('  [r] 重新下载失败的文件')
    print('  [q] 退出')
    print('=' * 50)
    
    failed_count = len(get_failed_items())
    if failed_count > 0:
        p(f'[提示] 有 {failed_count} 个失败的下载记录，输入 r 重新下载', 'r')




# ==================== B站登录 & 收藏夹 & 历史记录 功能 ====================

import urllib.request

BILI_COOKIES_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), ".bili_cookies.json")
BILI_LOGIN_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), ".bili_login.json")
BILI_DOWNLOAD_RECORD_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), ".bili_download_record.json")

# B站API请求头
BILI_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Origin': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

def bili_get_headers():
    """获取带cookies的请求头"""
    headers = dict(BILI_HEADERS)
    cookies = load_bili_cookies()
    if cookies:
        cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
        headers['Cookie'] = cookie_str
    return headers

# ==================== Cookies 管理 ====================

def load_bili_cookies():
    """加载B站cookies"""
    try:
        if os.path.exists(BILI_COOKIES_FILE):
            with open(BILI_COOKIES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_bili_cookies(cookies):
    """保存B站cookies"""
    try:
        with open(BILI_COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def load_bili_login():
    """加载B站登录信息"""
    try:
        if os.path.exists(BILI_LOGIN_FILE):
            with open(BILI_LOGIN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_bili_login(login_info):
    """保存B站登录信息"""
    try:
        with open(BILI_LOGIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(login_info, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def get_bili_login_status():
    """检查B站登录状态，返回 (是否登录, 用户名)"""
    cookies = load_bili_cookies()
    if not cookies:
        return False, None
    has_sessdata = any('SESSDATA' in k for k in cookies.keys())
    if not has_sessdata:
        return False, None
    try:
        resp = requests.get('https://api.bilibili.com/x/web-interface/nav',
                           headers=bili_get_headers(), timeout=10)
        data = resp.json()
        if data.get('code') == 0:
            user_info = data.get('data', {})
            if user_info.get('isLogin', False):
                return True, user_info.get('uname', '未知用户')
            else:
                return False, None
        else:
            return False, None
    except Exception as e:
        debug_print(f'检查登录状态失败: {e}')
        return False, None

# ==================== B站扫码登录功能 ====================

def bili_qrcode_login():
    """B站扫码登录：生成二维码 -> 用户扫码 -> 自动检测 -> 保存cookies"""
    p("\n" + "=" * 60, 'c')
    p("       B站扫码登录", 'c')
    print("=" * 60)
    
    # 检查是否已登录
    logged_in, username = get_bili_login_status()
    if logged_in:
        p(f'\n[已登录] 当前账号: {username}', 'g')
        print("\n  [1] 重新登录")
        print("  [2] 退出登录")
        print("  [q] 返回")
        choice = input("\n请选择 [1-2/q]: ").strip().lower()
        if choice in ('q', '0'):
            return True
        elif choice == '1':
            pass
        elif choice == '2':
            logout_bili()
            return False
    
    try:
        # 步骤1: 获取二维码 (B站接口只支持GET)
        p('\n[1/4] 正在获取登录二维码...', 'c')
        resp = requests.get('https://passport.bilibili.com/x/passport-login/web/qrcode/generate',
                            headers=BILI_HEADERS, timeout=15)
        try:
            data = resp.json()
        except Exception:
            p(f'[警告] 接口返回异常: HTTP {resp.status_code}, 内容: {resp.text[:100]}', 'y')
            p('[提示] 尝试重新请求...', 'y')
            resp = requests.get('https://passport.bilibili.com/x/passport-login/web/qrcode/generate',
                                headers=BILI_HEADERS, timeout=15)
            data = resp.json()
        if data.get('code') != 0:
            p(f'[错误] 获取二维码失败: {data.get("message", "未知错误")}', 'r')
            input("\n按回车键返回...")
            return False
        
        qrcode_key = data['data']['qrcode_key']
        qrcode_url = data['data']['url']
        p('[成功] 二维码已生成', 'g')
        
        # 步骤2: 显示二维码
        p('\n[2/4] 请使用B站App或手机浏览器扫码登录', 'c')
        p('        (打开B站App -> 我的 -> 扫一扫)', 'y')
        print("\n" + "=" * 60)
        print("       【扫码区域】")
        print("=" * 60)
        print("  [提示] 请在手机B站App中扫描以下内容:")
        print(f"  二维码链接: {qrcode_url}")
        print("=" * 60)
        
        # 尝试显示二维码字符画（需要qrcode库，可选）
        try:
            import qrcode
            qr = qrcode.QRCode(border=1)
            qr.add_data(qrcode_url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
            print("=" * 60)
        except ImportError:
            p('[提示] 未安装qrcode库，无法显示终端二维码', 'y')
            p('请手动打开链接扫码: ', 'c')
            print(f"  {qrcode_url}")
            print()
            p('[提示] 也可以安装qrcode库获得更好的体验:', 'y')
            p('  pip install qrcode pillow', 'y')
        
        # 步骤3: 轮询检测登录状态
        p('\n[3/4] 等待扫码... (最长等待120秒, 按Ctrl+C可取消)', 'c')
        poll_url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < 120:
            try:
                # B站poll接口只支持GET
                resp = requests.get(poll_url,
                                    params={'qrcode_key': qrcode_key},
                                    headers=BILI_HEADERS, timeout=15)
                data = resp.json()
                if data.get('code') != 0:
                    time.sleep(2)
                    continue
                
                status = data['data'].get('code')
                # 86101: 未扫码  86090: 已扫码未确认  0: 登录成功  86038: 二维码失效
                if status == 86101:
                    if last_status != status:
                        p('[状态] 等待扫码...', 'y')
                        last_status = status
                elif status == 86090:
                    p('[状态] 已扫码，请在手机上确认登录!', 'g')
                    last_status = status
                elif status == 0:
                    p('\n[成功] 扫码登录成功!', 'g')
                    # 兼容新版(cookie_info.cookies)和旧版(cookies)返回格式
                    cookies = data['data'].get('cookies', [])
                    if not cookies:
                        cookie_info = data['data'].get('cookie_info', {}) or {}
                        cookies = cookie_info.get('cookies', [])
                    # 备用: 从HTTP响应头Set-Cookie提取
                    if not cookies and resp.cookies:
                        try:
                            cookie_dict = {k: v for k, v in resp.cookies.items()}
                            if cookie_dict:
                                save_bili_cookies(cookie_dict)
                                p('[已保存] cookies已保存到本地文件(从响应头提取)', 'g')
                                p('[提示] 现在可以使用收藏夹/历史记录功能了', 'c')
                                input("\n按回车键继续...")
                                return True
                        except Exception:
                            pass
                    if not cookies:
                        p('[错误] 未获取到cookies数据', 'r')
                        input("\n按回车键返回...")
                        return False
                    
                    cookie_dict = {}
                    for c in cookies:
                        cookie_dict[c['name']] = c['value']
                    
                    save_bili_cookies(cookie_dict)
                    
                    login_info = {'login_time': time.strftime('%Y-%m-%d %H:%M:%S')}
                    try:
                        nav_resp = requests.get('https://api.bilibili.com/x/web-interface/nav',
                                               headers=bili_get_headers(), timeout=10)
                        nav_data = nav_resp.json()
                        if nav_data.get('code') == 0:
                            user = nav_data.get('data', {})
                            login_info['uname'] = user.get('uname', '')
                            login_info['mid'] = user.get('mid', 0)
                    except:
                        pass
                    save_bili_login(login_info)
                    
                    username = login_info.get('uname', '未知用户')
                    p(f'[登录成功] 欢迎: {username}', 'g')
                    p('[已保存] cookies已保存到本地文件', 'g')
                    p('[提示] 现在可以使用收藏夹/历史记录功能了', 'c')
                    input("\n按回车键继续...")
                    return True
                elif status == 86038:
                    p('[错误] 二维码已失效，请重新登录', 'r')
                    input("\n按回车键返回...")
                    return False
            except Exception as e:
                debug_print(f'轮询异常: {e}')
            time.sleep(2)
        
        p('\n[超时] 等待扫码超时(120秒)', 'y')
        input("\n按回车键返回...")
        return False
        
    except Exception as e:
        p(f'[错误] 扫码登录失败: {e}', 'r')
        input("\n按回车键返回...")
        return False

def logout_bili():
    """退出B站登录"""
    try:
        if os.path.exists(BILI_COOKIES_FILE):
            os.remove(BILI_COOKIES_FILE)
        if os.path.exists(BILI_LOGIN_FILE):
            os.remove(BILI_LOGIN_FILE)
        p('[退出] 已清除B站登录信息', 'g')
    except Exception as e:
        p(f'[错误] 退出失败: {e}', 'r')

# ==================== B站收藏夹功能 ====================

def get_bili_favorites_list():
    """获取用户的收藏夹列表"""
    cookies = load_bili_cookies()
    if not cookies:
        return None
    
    try:
        # 先获取mid
        mid = None
        nav_resp = requests.get('https://api.bilibili.com/x/web-interface/nav',
                               headers=bili_get_headers(), timeout=10)
        nav_data = nav_resp.json()
        if nav_data.get('code') == 0:
            mid = nav_data['data'].get('mid')
        
        if not mid:
            login_info = load_bili_login()
            mid = login_info.get('mid')
        
        if not mid:
            p('[错误] 无法获取用户ID', 'r')
            return None
        
        all_folders = []
        # 获取创建的收藏夹
        url = f'https://api.bilibili.com/x/v3/fav/folder/created/list-all?up_mid={mid}'
        resp = requests.get(url, headers=bili_get_headers(), timeout=15)
        data = resp.json()
        
        if data.get('code') == 0:
            folders = data.get('data', {}).get('list', [])
            for f in folders:
                all_folders.append({
                    'id': f.get('id'),
                    'title': f.get('title', '未命名'),
                    'media_count': f.get('media_count', 0),
                    'type': 'created'
                })
        else:
            debug_print(f'获取收藏夹列表失败: {data.get("message", "")}')
        
        # 获取收藏的收藏夹（其他人的收藏夹）
        url2 = f'https://api.bilibili.com/x/v3/fav/folder/collected/list?up_mid={mid}'
        resp2 = requests.get(url2, headers=bili_get_headers(), timeout=15)
        data2 = resp2.json()
        
        if data2.get('code') == 0:
            folders2 = data2.get('data', {}).get('list', [])
            for f in folders2:
                all_folders.append({
                    'id': f.get('id'),
                    'title': f.get('title', '未命名'),
                    'media_count': f.get('media_count', 0),
                    'type': 'collected'
                })
        
        return all_folders
    except Exception as e:
        p(f'[错误] 获取收藏夹失败: {e}', 'r')
        debug_print(f'获取收藏夹异常: {e}')
        return None

def get_bili_favorites_detail(folder_id, page=1, page_size=20):
    """获取收藏夹内的视频列表"""
    try:
        url = 'https://api.bilibili.com/x/v3/fav/resource/list'
        params = {
            'media_id': folder_id,
            'pn': page,
            'ps': page_size,
            'keyword': '',
            'order': 'mtime',
            'type': 0,
            'tid': 0,
            'platform': 'web'
        }
        resp = requests.get(url, params=params, headers=bili_get_headers(), timeout=15)
        data = resp.json()
        
        if data.get('code') != 0:
            debug_print(f'获取收藏夹内容失败: {data.get("message", "")}')
            return None
        
        info = data.get('data', {})
        medias = info.get('medias', [])
        total = info.get('info', {}).get('media_count', 0)
        
        video_list = []
        for m in medias:
            if m.get('type') != 2:
                continue
            bvid = m.get('bvid', '')
            title = m.get('title', '未知标题')
            cover = m.get('cover', '')
            if cover and cover.startswith('//'):
                cover = 'https:' + cover
            upper = m.get('upper', {})
            upper_name = upper.get('name', '未知UP主')
            duration = m.get('duration', 0)
            fav_time = m.get('fav_time', 0)
            
            video_list.append({
                'bvid': bvid,
                'title': title,
                'cover': cover,
                'upper': upper_name,
                'duration': duration,
                'fav_time': fav_time,
                'url': f'https://www.bilibili.com/video/{bvid}' if bvid else ''
            })
        
        return {
            'videos': video_list,
            'total': total,
            'page': page,
            'page_size': page_size
        }
    except Exception as e:
        p(f'[错误] 获取收藏夹内容失败: {e}', 'r')
        debug_print(f'获取收藏夹内容异常: {e}')
        return None

# ==================== B站历史记录功能 ====================

def get_bili_history(max_count=50):
    """获取B站观看历史记录"""
    try:
        url = 'https://api.bilibili.com/x/web-interface/history/cursor'
        params = {
            'max': 0,
            'view_at': 0,
            'business': 'archive',
            'ps': max_count
        }
        resp = requests.get(url, params=params, headers=bili_get_headers(), timeout=15)
        data = resp.json()
        
        if data.get('code') != 0:
            debug_print(f'获取历史记录失败: {data.get("message", "")}')
            return None
        
        items = data.get('data', {}).get('list', [])
        video_list = []
        for item in items:
            history = item.get('history', {})
            if history.get('business') != 'archive':
                continue
            bvid = history.get('bvid', '')
            title = item.get('title', '未知标题')
            cover = item.get('cover', '')
            if cover and cover.startswith('//'):
                cover = 'https:' + cover
            author = item.get('author_name', '未知UP主')
            view_at = item.get('view_at', 0)
            
            video_list.append({
                'bvid': bvid,
                'title': title,
                'cover': cover,
                'upper': author,
                'view_at': view_at,
                'url': f'https://www.bilibili.com/video/{bvid}' if bvid else ''
            })
        
        return video_list
    except Exception as e:
        p(f'[错误] 获取历史记录失败: {e}', 'r')
        debug_print(f'获取历史记录异常: {e}')
        return None

# ==================== 下载记录管理（增量下载） ====================

def load_bili_download_record():
    """加载下载记录"""
    try:
        if os.path.exists(BILI_DOWNLOAD_RECORD_FILE):
            with open(BILI_DOWNLOAD_RECORD_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'records': {}}

def save_bili_download_record(record):
    """保存下载记录"""
    try:
        with open(BILI_DOWNLOAD_RECORD_FILE, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def record_bili_download(bvid, title, folder_key='default'):
    """记录已下载的视频"""
    record = load_bili_download_record()
    if 'records' not in record:
        record['records'] = {}
    if folder_key not in record['records']:
        record['records'][folder_key] = {}
    record['records'][folder_key][bvid] = {
        'title': title,
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'bvid': bvid
    }
    save_bili_download_record(record)

def is_bili_downloaded(bvid, folder_key='default'):
    """检查视频是否已下载过"""
    record = load_bili_download_record()
    records = record.get('records', {}).get(folder_key, {})
    return bvid in records

def get_bili_downloaded_list(folder_key='default'):
    """获取已下载的视频列表"""
    record = load_bili_download_record()
    return record.get('records', {}).get(folder_key, {})

def clear_bili_download_record(folder_key=None):
    """清除下载记录"""
    record = load_bili_download_record()
    if folder_key is None:
        record['records'] = {}
    else:
        if folder_key in record.get('records', {}):
            del record['records'][folder_key]
    save_bili_download_record(record)
    p('[记录] 下载记录已清除', 'g')

def show_bili_download_records():
    """显示下载记录"""
    record = load_bili_download_record()
    records = record.get('records', {})
    
    if not records:
        p('[信息] 暂无下载记录', 'y')
        input("\n按回车键返回...")
        return
    
    print("\n" + "=" * 60)
    p("       下载记录", 'c')
    print("=" * 60)
    
    total = 0
    for folder_key, items in records.items():
        print(f"\n  📁 {folder_key} ({len(items)}个视频)")
        total += len(items)
        for bvid, info in list(items.items())[:10]:
            title = info.get('title', '未知')
            time_str = info.get('time', '')
            print(f"     - {title[:50]}... [{bvid}] ({time_str})")
        if len(items) > 10:
            print(f"     ... 共 {len(items)} 个")
    
    print(f"\n[总计] {total} 条下载记录")
    print("=" * 60)
    
    choice = input("\n是否清除所有记录？(输入 y 清除, 直接回车返回): ").strip().lower()
    if choice == 'y':
        clear_bili_download_record()
    input("\n按回车键返回...")

# ==================== 收藏夹视频选择与下载 ====================

def format_bili_duration(seconds):
    """格式化视频时长"""
    try:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        else:
            return f"{m}:{s:02d}"
    except:
        return "未知"

def select_favorites_folder():
    """选择收藏夹"""
    p('\n正在获取收藏夹列表...', 'c')
    folders = get_bili_favorites_list()
    
    if folders is None:
        p('[错误] 无法获取收藏夹列表，请确认已登录', 'r')
        return None
    
    if not folders:
        p('[信息] 没有找到收藏夹', 'y')
        return None
    
    print("\n" + "=" * 60)
    p("       我的收藏夹", 'c')
    print("=" * 60)
    
    for i, folder in enumerate(folders, 1):
        type_text = "创建的" if folder['type'] == 'created' else "收藏的"
        print(f"  [{i}] {folder['title']}  ({type_text} | {folder['media_count']}个视频)")
    
    print("  [q] 返回")
    print("=" * 60)
    
    while True:
        choice = input("\n请选择收藏夹 [1-{}] (q 返回): ".format(len(folders))).strip().lower()
        if choice in ('q', '0'):
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(folders):
            return folders[int(choice) - 1]
        p("无效选择，请重新输入 (数字选收藏夹, q 返回)", 'y')

def show_favorites_videos(folder):
    """显示收藏夹中的视频列表，支持翻页选择（按键风格与主脚本一致）"""
    config = load_config()
    key_prev = config.get('key_prev', 'a')
    key_next = config.get('key_next', 'd')
    key_goto = config.get('key_goto', 'g')
    
    folder_id = folder['id']
    folder_title = folder['title']
    page = 1
    page_size = 20
    all_selected = []
    last_page = 0
    all_mode = False           # 全部列出模式
    all_videos = []            # 全部列出模式下的视频缓存
    all_list_rendered = False  # 全部模式下列表是否已渲染
    
    print("\n" + "=" * 60)
    p(f"       收藏夹: {folder_title}", 'c')
    print("=" * 60)
    
    while True:
        # ============ 全部列出模式（s 进入，r 退出） ============
        if all_mode:
            videos = all_videos
            if not videos:
                p('[信息] 收藏夹是空的', 'y')
                return None
            
            # 只在第一次进入时渲染，避免刷屏
            if not all_list_rendered:
                print(f"\n共 {len(videos)} 个视频 (全部列出模式)")
                print("-" * 60)
                for i, video in enumerate(videos, 1):
                    duration_str = format_bili_duration(video['duration'])
                    downloaded_mark = "✅" if is_bili_downloaded(video['bvid'], folder_title) else "  "
                    print(f"  {downloaded_mark} {i}. {video['title'][:55]}")
                    print(f"      UP主: {video['upper']} | 时长: {duration_str} | BV: {video['bvid']}")
                    print("-" * 56)
                all_list_rendered = True
            
            print("\n" + "=" * 60)
            print("操作说明 (全部列出模式):")
            print(f"  输入数字 [1-{len(videos)}] 选择视频 (如: 1 3 5 或 1-5)")
            print(f"  输入 'm' 进入多选模式")
            print(f"  输入 'all' 选择全部视频")
            print(f"  输入 'c' 确认并开始下载")
            print(f"  输入 'r' 恢复分页模式")
            print(f"  输入 'q' 返回收藏夹列表")
            if all_selected:
                print(f"  [提示] 当前已选中 {len(all_selected)} 个视频")
            print("=" * 60)
            
            choice = input("\n请选择: ").strip().lower()
            
            if choice == 'r':
                all_mode = False
                all_list_rendered = False
                last_page = 0
                p('[提示] 已恢复分页模式', 'c')
                continue
            elif choice in ('0', 'q'):
                return 'back_to_folder_list'
            elif choice == 'all':
                for video in videos:
                    if video not in all_selected:
                        all_selected.append(video)
                p(f"[已选] 全部 {len(videos)} 个视频已加入选择 (当前共 {len(all_selected)} 个)", 'g')
            elif choice == 'm':
                print(f"\n共 {len(videos)} 个视频")
                print("输入序号选择（用空格或逗号分隔，支持范围如 1-5）")
                print("输入 'all' 选择全部")
                print("输入 'q' 取消多选")
                multi_input = input("请输入: ").strip().lower()
                if multi_input == 'all':
                    for video in videos:
                        if video not in all_selected:
                            all_selected.append(video)
                    p(f"[已选] 全部 {len(videos)} 个视频已加入选择 (当前共 {len(all_selected)} 个)", 'g')
                elif multi_input in ('q', '0'):
                    p('[取消] 已退出多选模式', 'y')
                else:
                    selected_indices = parse_selection_input(multi_input, len(videos))
                    if selected_indices:
                        for idx in selected_indices:
                            if 0 <= idx < len(videos) and videos[idx] not in all_selected:
                                all_selected.append(videos[idx])
                        p(f"[已选] 当前共 {len(all_selected)} 个视频", 'g')
                    else:
                        p("没有有效的选择", 'y')
            elif choice == 'c':
                if all_selected:
                    break
                else:
                    p("还没有选择任何视频", 'y')
            else:
                selected_indices = parse_selection_input(choice, len(videos))
                if selected_indices:
                    for idx in selected_indices:
                        if 0 <= idx < len(videos) and videos[idx] not in all_selected:
                            all_selected.append(videos[idx])
                    p(f"[已选] 当前共 {len(all_selected)} 个视频", 'g')
                else:
                    p("无效输入，请重新输入", 'y')
            continue
        
        # ============ 分页模式（原逻辑） ============
        result = get_bili_favorites_detail(folder_id, page, page_size)
        if not result:
            p('[错误] 获取收藏夹内容失败', 'r')
            return None
        
        videos = result['videos']
        total = result['total']
        total_pages = max(1, (total + page_size - 1) // page_size)
        
        if not videos and page == 1:
            p('[信息] 收藏夹是空的', 'y')
            return None
        
        # 翻页时重新渲染列表
        if page != last_page:
            print(f"\n共 {total} 个视频 (第 {page}/{total_pages} 页)")
            print("-" * 60)
            for i, video in enumerate(videos, 1):
                duration_str = format_bili_duration(video['duration'])
                downloaded_mark = "✅" if is_bili_downloaded(video['bvid'], folder_title) else "  "
                print(f"  {downloaded_mark} {i}. {video['title'][:55]}")
                print(f"      UP主: {video['upper']} | 时长: {duration_str} | BV: {video['bvid']}")
                print("-" * 56)
            last_page = page
        
        print("\n" + "=" * 60)
        print("操作说明:")
        print(f"  输入数字 [1-{len(videos)}] 选择视频 (如: 1 3 5 或 1-5)")
        print(f"  输入 'm' 进入多选模式")
        print(f"  输入 'all' 选择本页全部视频")
        print(f"  输入 's' 列出收藏夹全部视频 (不分页)")
        print(f"  输入 'c' 确认并开始下载")
        print(f"  输入 'q' 返回收藏夹列表")
        print(f"  输入 {key_prev} 上一页  |  输入 {key_next} 下一页")
        print(f"  输入 {key_goto} + 页码 跳转到指定页 (如: {key_goto} 5)")
        if all_selected:
            print(f"  [提示] 当前已选中 {len(all_selected)} 个视频")
        print("=" * 60)
        
        choice = input("\n请选择: ").strip().lower()
        
        if choice in ('0', 'q'):
            return 'back_to_folder_list'
        elif choice == 's':
            # 进入全部列出模式：一次性拉取所有视频
            p('[提示] 正在获取全部视频列表...', 'c')
            all_videos = []
            for pg in range(1, total_pages + 1):
                r = get_bili_favorites_detail(folder_id, pg, page_size)
                if r and r['videos']:
                    all_videos.extend(r['videos'])
            all_mode = True
            all_list_rendered = False
            continue
        elif choice == key_next:
            if page < total_pages:
                page += 1
                continue
            else:
                p("[提示] 已经是最后一页了", 'y')
        elif choice == key_prev:
            if page > 1:
                page -= 1
                continue
            else:
                p("[提示] 已经是第一页了", 'y')
        elif choice.startswith(key_goto):
            parts = choice.split()
            if len(parts) >= 2 and parts[1].isdigit():
                target_page = int(parts[1])
                if 1 <= target_page <= total_pages:
                    page = target_page
                    continue
                else:
                    p(f"页码范围: 1-{total_pages}", 'y')
            else:
                p(f"格式错误，请输入: {key_goto} 页码 (如: {key_goto} 5)", 'y')
        elif choice == 'all':
            for video in videos:
                if video not in all_selected:
                    all_selected.append(video)
            p(f"[已选] 本页 {len(videos)} 个视频已加入选择 (当前共 {len(all_selected)} 个)", 'g')
        elif choice == 'm':
            print(f"\n当前页有 {len(videos)} 个视频")
            print("输入序号选择（用空格或逗号分隔，支持范围如 1-5）")
            print("输入 'all' 选择本页全部")
            print("输入 'q' 取消多选")
            multi_input = input("请输入: ").strip().lower()
            if multi_input == 'all':
                for video in videos:
                    if video not in all_selected:
                        all_selected.append(video)
                p(f"[已选] 本页 {len(videos)} 个视频已加入选择 (当前共 {len(all_selected)} 个)", 'g')
            elif multi_input in ('q', '0'):
                p('[取消] 已退出多选模式', 'y')
            else:
                selected_indices = parse_selection_input(multi_input, len(videos))
                if selected_indices:
                    for idx in selected_indices:
                        if 0 <= idx < len(videos) and videos[idx] not in all_selected:
                            all_selected.append(videos[idx])
                    p(f"[已选] 当前共 {len(all_selected)} 个视频", 'g')
                else:
                    p("没有有效的选择", 'y')
        elif choice == 'c':
            if all_selected:
                break
            else:
                p("还没有选择任何视频", 'y')
        else:
            selected_indices = parse_selection_input(choice, len(videos))
            if selected_indices:
                for idx in selected_indices:
                    if 0 <= idx < len(videos) and videos[idx] not in all_selected:
                        all_selected.append(videos[idx])
                p(f"[已选] 当前共 {len(all_selected)} 个视频", 'g')
            else:
                p("无效输入，请重新输入", 'y')
    
    return all_selected

def choose_download_mode():
    """选择下载模式（mp3/mp4/都要）"""
    print("\n" + "=" * 50)
    p("       下载格式", 'c')
    print("=" * 50)
    print("  [1] 仅MP4 (视频)")
    print("  [2] 仅MP3 (音频)")
    print("  [3] MP4 + MP3 (都要)")
    print("=" * 50)
    
    while True:
        choice = input("\n请选择 [1-3]: ").strip()
        if choice in ['1', '2', '3']:
            return int(choice)
        p("无效选项，请重新输入", 'y')

# ==================== 收藏夹/历史记录 菜单主入口 ====================

def ensure_bili_login():
    """确保已登录B站，未登录则引导扫码"""
    logged_in, username = get_bili_login_status()
    if logged_in:
        p(f'\n[已登录] {username}', 'g')
        return True
    p('\n[提示] 请先登录B站账号', 'y')
    choice = input("是否现在扫码登录？(直接回车=是, 输入q=否): ").strip().lower()
    if choice in ('q', '0'):
        return False
    success = bili_qrcode_login()
    if not success:
        return False
    return True

def download_bili_video_list(videos, folder_key, mode, save_folder=None):
    """批量下载B站视频列表（带增量记录）"""
    if not videos:
        p('[信息] 没有要下载的视频', 'y')
        return 0, 0
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    abort_download = False  # 中断返回主菜单时置True，退出整个循环
    
    # ★★★ 修复：改为 while 循环，使中断后"继续"能重试当前视频 ★★★
    idx = 1
    while idx <= len(videos):
        video = videos[idx - 1]
        if abort_download:
            break
        # ★★★ 每次循环开始时检查中断 ★★★
        _ir = check_interrupt()
        if _ir is not None:
            if _ir == 'main_menu':
                p('\n[中断] 已返回主菜单', 'y')
                interrupt_manager.reset()
                break
            elif _ir == 'skip':
                p('\n[中断] 跳过当前任务', 'y')
                interrupt_manager.reset()
                idx += 1
                continue
            elif _ir == 'reselect':
                p('\n[中断] 重新选择', 'y')
                interrupt_manager.reset()
                break
            elif _ir == 'continue':
                # ★★★ 继续当前下载：不前进 idx，重试当前视频（利用.tmp续传）★★★
                interrupt_manager.reset()
                continue
        
        bvid = video.get('bvid', '')
        title = video.get('title', '未知标题')
        video_url = video.get('url', '')
        
        p(f'\n[{idx}/{len(videos)}] 正在处理: {title}', 'c')
        
        if not bvid or not video_url:
            p('[跳过] 无效的视频链接', 'y')
            skip_count += 1
            idx += 1
            continue
        
        # 检查是否已下载过（增量）
        if is_bili_downloaded(bvid, folder_key):
            p(f'[增量] 已下载过，跳过: {title}', 'y')
            skip_count += 1
            idx += 1
            continue
        
        try:
            # 检查分P
            pages = get_bilibili_video_pages(bvid)
            has_multi_pages = pages and len(pages) > 1
            
            if has_multi_pages:
                # 多P视频，使用完整的分P选择菜单（支持翻页/多选/跳转）
                p(f'[提示] 该视频有 {len(pages)} 个分P', 'y')
                p('[提示] 按 q 可跳过此视频', 'y')
                selected_pages = show_page_selection_menu(pages, title)
                if selected_pages is None:
                    # 用户取消/跳过
                    if interrupt_manager.last_result is not None:
                        _ir_tmp = interrupt_manager.last_result
                        interrupt_manager.last_result = None
                        if _ir_tmp == 'main_menu':
                            p('\n[中断] 已返回主菜单', 'y')
                            interrupt_manager.reset()
                            abort_download = True
                            break
                        elif _ir_tmp == 'skip':
                            p('\n[中断] 跳过当前任务', 'y')
                            interrupt_manager.reset()
                            idx += 1
                            continue
                        elif _ir_tmp == 'reselect':
                            p('\n[中断] 重新选择', 'y')
                            interrupt_manager.reset()
                            abort_download = True
                            break
                        elif _ir_tmp == 'continue':
                            # ★★★ 继续：重新进入分P选择菜单 ★★★
                            p('\n[继续] 重新选择分P...', 'c')
                            interrupt_manager.reset()
                            continue
                    p('[跳过] 未选择任何分P，跳过此视频', 'y')
                    skip_count += 1
                    idx += 1
                    continue
                
                video_ok = True
                # ★★★ 修复：内层分P循环改为 while，支持中断后"继续"重试当前分P ★★★
                _page_idx = 0
                while _page_idx < len(selected_pages):
                    page_num = selected_pages[_page_idx]
                    page = pages[page_num - 1]
                    page_title = f"{title} - P{page['page']}"
                    
                    if save_folder:
                        exists, existing_path = check_file_exists_by_title(page_title, save_folder)
                    else:
                        exists, existing_path = check_file_exists_by_title(page_title)
                    
                    if exists:
                        p(f'[跳过] 文件已存在: {os.path.basename(existing_path)}', 'y')
                        _page_idx += 1
                        continue
                    
                    page_url = f"https://www.bilibili.com/video/{bvid}?p={page['page']}"
                    result = parse_video(page_url)
                    # ★★★ 检查parse_video内部是否已处理了中断菜单 ★★★
                    if interrupt_manager.last_result is not None:
                        _ir = interrupt_manager.last_result
                        interrupt_manager.last_result = None
                        if _ir == 'main_menu':
                            p('\n[中断] 已返回主菜单', 'y')
                            video_ok = False
                            abort_download = True
                            break
                        elif _ir == 'skip':
                            p('\n[中断] 跳过当前任务', 'y')
                            interrupt_manager.reset()
                            video_ok = False
                            break
                        elif _ir == 'reselect':
                            p('\n[中断] 重新选择', 'y')
                            interrupt_manager.reset()
                            abort_download = True
                            break
                        elif _ir == 'continue':
                            # ★★★ 继续当前下载：不前进_page_idx，重试当前分P ★★★
                            p('\n[继续] 重新解析当前分P...', 'c')
                            interrupt_manager.reset()
                            continue
                    if result and len(result) >= 2 and result[1]:
                        mp4_path = download_file(result[1], page_title, save_folder)
                        if mp4_path:
                            cover_url = get_bilibili_cover(bvid)
                            if mode in (2, 3):
                                cid = page.get('cid')
                                mp3_path = download_mp3_with_settings(mp4_path, cover_url, bvid, cid, page_title)
                                if mp3_path:
                                    if mode == 2:
                                        if os.path.exists(mp4_path):
                                            os.remove(mp4_path)
                                        p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                    else:
                                        p(f'[完成] 视频+音频', 'g')
                                else:
                                    p('[失败] MP3转换失败', 'y')
                                    video_ok = False
                            else:
                                p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                        else:
                            p('[失败] 下载失败', 'r')
                            # ★★★ 修复：分P下载失败时若因中断导致，显示中断菜单 ★★★
                            if interrupt_manager.interrupted:
                                _ir2 = interrupt_manager.get_interrupt_menu()
                                if _ir2 == 'main_menu':
                                    p('\n[中断] 已返回主菜单', 'y')
                                    interrupt_manager.reset()
                                    abort_download = True
                                    break
                                elif _ir2 == 'skip':
                                    p('\n[中断] 跳过当前任务', 'y')
                                    interrupt_manager.reset()
                                    video_ok = False
                                    break
                                elif _ir2 == 'reselect':
                                    p('\n[中断] 重新选择', 'y')
                                    interrupt_manager.reset()
                                    abort_download = True
                                    break
                                elif _ir2 == 'continue':
                                    # ★★★ 继续：重试当前分P（利用.tmp续传）★★★
                                    p('\n[继续] 重新下载当前分P（断点续传）...', 'c')
                                    interrupt_manager.reset()
                                    continue
                            video_ok = False
                    else:
                        p('[失败] 解析失败', 'r')
                        video_ok = False
                    _page_idx += 1
                
                if video_ok:
                    record_bili_download(bvid, title, folder_key)
                    success_count += 1
                elif not abort_download:
                    # ★★★ 修复：多P下载失败时，若因中断导致则显示中断菜单 ★★★
                    if interrupt_manager.interrupted:
                        _ir = interrupt_manager.get_interrupt_menu()
                        if _ir == 'main_menu':
                            p('\n[中断] 已返回主菜单', 'y')
                            interrupt_manager.reset()
                            abort_download = True
                            break
                        elif _ir == 'skip':
                            p('\n[中断] 跳过当前任务', 'y')
                            interrupt_manager.reset()
                            idx += 1
                            continue
                        elif _ir == 'reselect':
                            p('\n[中断] 重新选择', 'y')
                            interrupt_manager.reset()
                            abort_download = True
                            break
                        elif _ir == 'continue':
                            # ★★★ 继续当前下载：不前进idx，重试当前视频 ★★★
                            p('\n[继续] 重新下载当前视频（断点续传）...', 'c')
                            interrupt_manager.reset()
                            continue
                    fail_count += 1
            else:
                # 单个视频
                if save_folder:
                    exists, existing_path = check_file_exists_by_title(title, save_folder)
                else:
                    exists, existing_path = check_file_exists_by_title(title)
                
                if exists:
                    p(f'[跳过] 文件已存在: {os.path.basename(existing_path)}', 'y')
                    record_bili_download(bvid, title, folder_key)
                    success_count += 1
                    idx += 1
                    continue
                
                result = parse_video(video_url)
                # ★★★ 检查parse_video内部是否已处理了中断菜单 ★★★
                if interrupt_manager.last_result is not None:
                    _ir = interrupt_manager.last_result
                    interrupt_manager.last_result = None
                    if _ir == 'main_menu':
                        p('\n[中断] 已返回主菜单', 'y')
                        interrupt_manager.reset()
                        abort_download = True
                        break
                    elif _ir == 'skip':
                        p('\n[中断] 跳过当前任务', 'y')
                        interrupt_manager.reset()
                        idx += 1
                        continue
                    elif _ir == 'reselect':
                        p('\n[中断] 重新选择', 'y')
                        interrupt_manager.reset()
                        abort_download = True
                        break
                    elif _ir == 'continue':
                        # ★★★ 继续当前下载：不前进idx，重试当前视频（重新解析）★★★
                        p('\n[继续] 重新解析当前视频...', 'c')
                        interrupt_manager.reset()
                        continue
                if result and len(result) >= 2 and result[1]:
                    mp4_path = download_file(result[1], title, save_folder)
                    if mp4_path:
                        cover_url = get_bilibili_cover(bvid)
                        if mode in (2, 3):
                            cid = None
                            try:
                                cid = get_cid_from_bvid(bvid)
                            except:
                                pass
                            mp3_path = download_mp3_with_settings(mp4_path, cover_url, bvid, cid, title)
                            if mp3_path:
                                if mode == 2:
                                    if os.path.exists(mp4_path):
                                        os.remove(mp4_path)
                                    p(f'[完成] 音频: {os.path.basename(mp3_path)}', 'g')
                                else:
                                    p(f'[完成] 视频+音频', 'g')
                            else:
                                p('[失败] MP3转换失败', 'y')
                        else:
                            p(f'[完成] 视频: {os.path.basename(mp4_path)}', 'g')
                        record_bili_download(bvid, title, folder_key)
                        success_count += 1
                    else:
                        p('[失败] 下载失败', 'r')
                        # ★★★ 修复：下载失败时检查是否因中断导致，若是则显示中断菜单 ★★★
                        if interrupt_manager.interrupted:
                            _ir = interrupt_manager.get_interrupt_menu()
                            if _ir == 'main_menu':
                                p('\n[中断] 已返回主菜单', 'y')
                                interrupt_manager.reset()
                                abort_download = True
                                break
                            elif _ir == 'skip':
                                p('\n[中断] 跳过当前任务', 'y')
                                interrupt_manager.reset()
                                idx += 1
                                continue
                            elif _ir == 'reselect':
                                p('\n[中断] 重新选择', 'y')
                                interrupt_manager.reset()
                                abort_download = True
                                break
                            elif _ir == 'continue':
                                # ★★★ 继续当前下载：不前进idx，重试当前视频（利用.tmp续传）★★★
                                p('\n[继续] 重新下载当前视频（断点续传）...', 'c')
                                interrupt_manager.reset()
                                continue
                        fail_count += 1
                else:
                    p('[失败] 解析失败', 'r')
                    fail_count += 1
        except Exception as e:
            p(f'[错误] 处理失败: {e}', 'r')
            fail_count += 1
        
        # ★★★ 修复：while 循环末尾统一前进到下一个视频 ★★★
        idx += 1
    
    return success_count, fail_count

def bili_favorites_menu():
    """B站收藏夹批量下载主入口"""
    if not ensure_bili_login():
        return
    
    # 外层循环：支持 0 返回收藏夹列表（重新选择）
    while True:
        folder = select_favorites_folder()
        if not folder:
            return
        
        folder_title = folder['title']
        folder_key = folder_title
        
        p('\n[信息] 正在加载收藏夹内容...', 'c')
        videos = show_favorites_videos(folder)
        if videos == 'back_to_folder_list':
            # 用户按 0，返回收藏夹列表
            continue
        if not videos:
            # 用户按 q 或其他，返回主菜单
            return
        
        # 过滤已下载的（增量下载）
        new_videos = []
        already_downloaded = []
        for v in videos:
            if is_bili_downloaded(v['bvid'], folder_key):
                already_downloaded.append(v)
            else:
                new_videos.append(v)
        
        if already_downloaded:
            p(f'\n[增量] 已下载过的视频: {len(already_downloaded)} 个 (将跳过)', 'y')
            for v in already_downloaded[:5]:
                p(f'  - 已下载: {v["title"][:50]}', 'y')
            if len(already_downloaded) > 5:
                p(f'  ... 共 {len(already_downloaded)} 个', 'y')
        
        if not new_videos:
            p('\n[完成] 所有选中的视频都已下载过，无需重复下载', 'g')
            input("\n按回车键返回...")
            return
        
        p(f'\n[待下载] {len(new_videos)} 个新视频', 'c')
        
        # 询问是否只下载新的还是全部重新下载
        print("\n" + "=" * 50)
        p("       下载选项", 'c')
        print("=" * 50)
        print(f"  [1] 仅下载新增的 {len(new_videos)} 个视频 (推荐)")
        print(f"  [2] 全部重新下载 ({len(videos)} 个)")
        print("  [q] 取消")
        print("=" * 50)
        
        choice = input("\n请选择: ").strip().lower()
        if choice in ('q', '0'):
            return
        elif choice == '2':
            new_videos = videos
            p('[模式] 全部重新下载', 'y')
        else:
            p(f'[模式] 仅下载新增 {len(new_videos)} 个视频', 'g')
        
        # 选择下载格式
        mode = choose_download_mode()
        mode_text = {1: '仅MP4', 2: '仅MP3', 3: 'MP4+MP3'}[mode]
        p(f'\n[格式] {mode_text}', 'c')
        
        # 询问是否下载到子文件夹
        print("\n" + "=" * 50)
        p("       保存位置", 'c')
        print("=" * 50)
        print(f"  下载目录: {get_download_path()}")
        print("  是否在下载目录下创建子文件夹？")
        print("  [直接回车] 不创建，直接保存到下载目录")
        print("  [输入名称] 创建子文件夹")
        print("=" * 50)
        
        sub_folder = input("\n请输入文件夹名称 (直接回车跳过): ").strip()
        save_folder = None
        if sub_folder:
            sub_folder = re.sub(r'[\\/:*?"<>|]', '_', sub_folder)
            save_folder = os.path.join(get_download_path(), sub_folder)
            os.makedirs(save_folder, exist_ok=True)
            p(f'[文件夹] 文件将保存到: {save_folder}', 'g')
        
        # 开始批量下载
        p(f'\n[开始] 准备下载 {len(new_videos)} 个视频...', 'c')
        
        success, fail = download_bili_video_list(new_videos, folder_key, mode, save_folder)
        
        p(f'\n[完成] 成功: {success} 个, 失败: {fail} 个', 'g')
        input("\n按回车键返回...")
        # 下载完成后返回收藏夹列表，方便继续操作其他收藏夹
        continue

def bili_history_menu():
    """B站历史记录查看与下载"""
    if not ensure_bili_login():
        return
    
    p('\n[信息] 正在获取历史记录...', 'c')
    videos = get_bili_history(50)
    
    if not videos:
        p('[信息] 没有获取到历史记录', 'y')
        input("\n按回车键返回...")
        return
    
    print("\n" + "=" * 60)
    p("       观看历史记录", 'c')
    print("=" * 60)
    
    for i, video in enumerate(videos, 1):
        downloaded_mark = "✅" if is_bili_downloaded(video['bvid'], 'history') else "  "
        print(f"  {downloaded_mark} {i}. {video['title'][:55]}")
        print(f"      UP主: {video['upper']} | BV: {video['bvid']}")
        print("-" * 56)
    
    print("\n" + "=" * 60)
    print("操作说明:")
    print("  [数字] 选择视频 (如: 1 3 5)")
    print("  [范围] 选择范围 (如: 1-10)")
    print("  [all] 选择全部")
    print("  [q] 返回")
    print("=" * 60)
    
    choice = input("\n请选择: ").strip().lower()
    
    if choice in ('q', '0'):
        return
    
    if choice == 'all':
        selected_videos = videos
    else:
        selected_indices = parse_selection_input(choice, len(videos))
        if not selected_indices:
            p("[错误] 没有有效的选择", 'y')
            input("\n按回车键返回...")
            return
        selected_videos = [videos[idx] for idx in selected_indices]
    
    # 过滤已下载的
    new_videos = [v for v in selected_videos if not is_bili_downloaded(v['bvid'], 'history')]
    already_downloaded = [v for v in selected_videos if is_bili_downloaded(v['bvid'], 'history')]
    
    if already_downloaded:
        p(f'\n[增量] 已下载过的视频: {len(already_downloaded)} 个 (将跳过)', 'y')
    
    if not new_videos:
        p('\n[完成] 所有选中的视频都已下载过', 'g')
        input("\n按回车键返回...")
        return
    
    p(f'\n[待下载] {len(new_videos)} 个新视频', 'c')
    
    # 下载选项
    print("\n" + "=" * 50)
    p("       下载选项", 'c')
    print("=" * 50)
    print(f"  [1] 仅下载新增的 {len(new_videos)} 个视频 (推荐)")
    print(f"  [2] 全部重新下载 ({len(selected_videos)} 个)")
    print("  [q] 取消")
    print("=" * 50)
    
    d_choice = input("\n请选择: ").strip().lower()
    if d_choice in ('q', '0'):
        return
    elif d_choice == '2':
        new_videos = selected_videos
    
    mode = choose_download_mode()
    mode_text = {1: '仅MP4', 2: '仅MP3', 3: 'MP4+MP3'}[mode]
    p(f'\n[格式] {mode_text}', 'c')
    
    sub_folder = input("\n请输入文件夹名称 (直接回车保存到下载目录): ").strip()
    save_folder = None
    if sub_folder:
        sub_folder = re.sub(r'[\\/:*?"<>|]', '_', sub_folder)
        save_folder = os.path.join(get_download_path(), sub_folder)
        os.makedirs(save_folder, exist_ok=True)
        p(f'[文件夹] 文件将保存到: {save_folder}', 'g')
    
    p(f'\n[开始] 准备下载 {len(new_videos)} 个视频...', 'c')
    
    success, fail = download_bili_video_list(new_videos, 'history', mode, save_folder)
    
    p(f'\n[完成] 成功: {success} 个, 失败: {fail} 个', 'g')
    input("\n按回车键返回...")

def bili_account_menu():
    """B站账号菜单（登录/退出/记录）"""
    print("\n" + "=" * 50)
    p("       B站账号管理", 'c')
    print("=" * 50)
    
    logged_in, username = get_bili_login_status()
    if logged_in:
        p(f'[状态] 已登录: {username}', 'g')
    else:
        p('[状态] 未登录', 'y')
    
    print("\n  [1] 扫码登录")
    print("  [2] 退出登录")
    print("  [3] 查看下载记录")
    print("  [4] 清除下载记录")
    print("  [q] 返回")
    print("=" * 50)
    
    choice = input("\n请选择 [1-4/q]: ").strip().lower()
    
    if choice in ('q', '0'):
        return
    elif choice == '1':
        bili_qrcode_login()
    elif choice == '2':
        logout_bili()
        input("\n按回车键返回...")
    elif choice == '3':
        show_bili_download_records()
    elif choice == '4':
        choice2 = input("确认清除所有下载记录？(输入 y 确认): ").strip().lower()
        if choice2 == 'y':
            clear_bili_download_record()
            input("\n按回车键返回...")
    else:
        return

def main():
    global DOWNLOAD_PATH
    
    config = load_config()
    DOWNLOAD_PATH = config.get('download_path', DEFAULT_DOWNLOAD_PATH)
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    
    setup_interrupt_handler()
    
    check_dependencies()
    auto_check_for_updates()
    show_announcement()
    
    report_stats("start")
    display_stats()
    
    p(f'[路径] 保存目录: {DOWNLOAD_PATH}', 'c')
    
    if config.get('debug_mode', False):
        p('[调试模式] 已开启', 'c')
    
    skip_status = '开启' if config.get('skip_existing', True) else '关闭'
    cover_mode = config.get('cover_mode', 'api')
    cover_text = 'API封面' if cover_mode == 'api' else '视频截图'
    cover_crop = config.get('cover_crop', 'center')
    crop_text = {"center": "居中", "top": "上部", "bottom": "下部", "left": "左侧", "right": "右侧"}.get(cover_crop, "居中")
    p(f'[跳过已存在] {skip_status}  |  [封面模式] {cover_text}  |  [裁剪位置] {crop_text}', 'c')
    
    while True:
        try:
            show_main_menu()
            
            main_choice = input('\n请选择 [0-9] 或 q 退出: ').strip().lower()

            if main_choice == 'q':
                failed_count = len(get_failed_items())
                if failed_count > 0:
                    print("\n" + "=" * 50)
                    p(f'[提示] 有 {failed_count} 个失败的下载记录', 'y')
                    print("  输入 r 重新下载失败的文件")
                    print("  直接回车退出")
                    print("=" * 50)
                    choice = input("\n请选择: ").strip().lower()
                    if choice == 'r':
                        retry_failed_downloads()
                        continue
                p('再见!', 'm')
                break

            if main_choice == 'l':
                show_unfinished_tasks_menu()
                continue

            # ★★★ B站功能选项 ★★★
            if main_choice == 'b':
                try:
                    bili_favorites_menu()
                except Exception as e:
                    p(f'[错误] 收藏夹功能异常: {e}', 'r')
                    import traceback
                    traceback.print_exc()
                    input("\n按回车键继续...")
                continue

            if main_choice == 'h':
                try:
                    bili_history_menu()
                except Exception as e:
                    p(f'[错误] 历史记录功能异常: {e}', 'r')
                    import traceback
                    traceback.print_exc()
                    input("\n按回车键继续...")
                continue

            if main_choice == 'a':
                try:
                    bili_account_menu()
                except Exception as e:
                    p(f'[错误] 账号管理异常: {e}', 'r')
                    import traceback
                    traceback.print_exc()
                    input("\n按回车键继续...")
                continue

            if main_choice == 'r':
                retry_failed_downloads()
                continue

            if main_choice == '9':
                show_uninstall_menu()
                uninstall_choice = input('\n请选择 [1-2]: ').strip()
                if uninstall_choice == '1':
                    uninstall_videos()
                continue

            if main_choice == '0':
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
                process_lrc_download()
                continue

            if main_choice == '8':
                process_bilibili_subtitle_to_lrc()
                continue

            if main_choice == '2':
                search_videos()
                continue

            if main_choice != '1':
                p('无效选项，请重新选择', 'y')
                continue

            print()
            inp = ''
            temp_input_file = os.path.join(os.path.dirname(SCRIPT_PATH), '_temp_links.txt')
            # 先创建空文件
            with open(temp_input_file, 'w', encoding='utf-8') as f:
                f.write('')
            
            # 检查可用的编辑器 (直接调用检测, 不依赖 which)
            editor = None
            for ed in ['nano', 'vim', 'vi']:
                try:
                    _r = subprocess.run([ed, '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                    if _r.returncode == 0 or _r.returncode == 1:
                        editor = ed
                        break
                except:
                    try:
                        _r = subprocess.run([ed, '--help'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                        if _r.returncode == 0 or _r.returncode == 1:
                            editor = ed
                            break
                    except:
                        pass
            
            if editor:
                p('即将打开文本编辑器, 请在编辑器中粘贴链接', 'c')
                p('粘贴完成后: Ctrl+O 保存 (回车确认文件名) -> Ctrl+X 退出', 'c')
                p('如果使用 vim: i 进入插入模式粘贴 -> Esc -> :wq 保存退出', 'c')
                input('\n按回车键打开编辑器...')
                # 用编辑器打开临时文件, 用户在里面粘贴
                subprocess.run([editor, temp_input_file])
                # 读取文件
                try:
                    with open(temp_input_file, 'r', encoding='utf-8') as f:
                        inp = f.read().strip()
                except Exception as e:
                    p(f'读取文件失败: {e}', 'r')
                    continue
                finally:
                    try:
                        os.remove(temp_input_file)
                    except:
                        pass
                if inp:
                    p(f'[已读取] {len(inp)} 字节', 'g')
            else:
                # 无编辑器: 回退到分批粘贴
                p('未检测到文本编辑器 (nano/vim)', 'y')
                p('建议安装: pkg install nano', 'c')
                p('当前使用分批粘贴模式', 'c')
                p('每次粘贴部分链接后按 Ctrl+D, 最后空批结束', 'c')
                batch = 0
                while True:
                    batch += 1
                    chunk = get_multiline_input_ctrl_d(f'\n[第{batch}批] 请粘贴链接 (直接 Ctrl+D 结束输入):')
                    if not chunk.strip():
                        break
                    with open(temp_input_file, 'a', encoding='utf-8') as f:
                        f.write(chunk + '\n')
                    p(f'[暂存] 第{batch}批已保存, 继续粘贴或按 Ctrl+D 结束', 'g')
                try:
                    with open(temp_input_file, 'r', encoding='utf-8') as f:
                        inp = f.read().strip()
                except Exception as e:
                    p(f'读取临时文件失败: {e}', 'r')
                    continue
                finally:
                    try:
                        os.remove(temp_input_file)
                    except:
                        pass
            
            if not inp:
                p('未输入链接', 'y')
                continue
            
            urls = extract_urls_from_input(inp)
            
            if not urls:
                p('未检测到有效链接', 'y')
                continue
            
            # ===== 直接解析并检测重名 =====
            p(f'\n[解析] 正在解析 {len(urls)} 个链接...', 'c')
            
            valid_urls = []
            skipped_urls = []
            url_info = {}
            interrupt_occurred = False
            
            try:
                for idx, url in enumerate(urls):
                    # 每次循环开始时检查中断
                    _ir = check_interrupt()
                    if _ir is not None:
                        interrupt_occurred = True
                        if _ir == 'main_menu':
                            p('\n[中断] 已返回主菜单', 'y')
                            break
                        elif _ir == 'skip':
                            p('\n[中断] 跳过当前任务', 'y')
                            interrupt_manager.reset()
                            continue
                        elif _ir == 'reselect':
                            p('\n[中断] 重新选择', 'y')
                            interrupt_occurred = True
                            break
                        elif _ir == 'continue':
                            interrupt_manager.reset()
                            continue
                    
                    p(f'\n[{idx+1}/{len(urls)}] [解析] {url}', 'c')
                    result = parse_video(url)
                    
                    # ★★★ 检查parse_video内部是否已处理了中断菜单 ★★★
                    if interrupt_manager.last_result is not None:
                        _ir = interrupt_manager.last_result
                        interrupt_manager.last_result = None
                        if _ir == 'main_menu':
                            p('\n[中断] 已返回主菜单', 'y')
                            interrupt_occurred = True
                            break
                        elif _ir == 'skip':
                            p('\n[中断] 跳过当前任务', 'y')
                            interrupt_manager.reset()
                            continue
                        elif _ir == 'reselect':
                            p('\n[中断] 重新选择', 'y')
                            interrupt_occurred = True
                            break
                    
                    title = None
                    video_url = None
                    cover_url = None
                    pages = None
                    medialist_info = None
                    bvid = None
                    
                    is_bilibili = 'bilibili.com' in url or 'b23.tv' in url
                    if is_bilibili:
                        bvid = get_bvid_from_url(url)
                    
                    if result and len(result) == 5:
                        title, video_url, cover_url, pages, medialist_info = result
                        if medialist_info:
                            p(f'[B站合集] 检测到合集: {medialist_info["title"]}, 共 {medialist_info["total"]} 个视频', 'g')
                            for video in medialist_info['videos']:
                                _ir = check_interrupt()
                                if _ir is not None:
                                    interrupt_occurred = True
                                    if _ir == 'continue':
                                        interrupt_manager.reset()
                                        interrupt_occurred = False
                                        continue
                                    break
                                
                                exists, existing_path = check_file_exists_by_title(video['title'])
                                if exists:
                                    p(f'[跳过] 文件已存在: {os.path.basename(existing_path)}', 'y')
                                    skipped_urls.append(video['url'])
                                else:
                                    valid_urls.append(video['url'])
                                    url_info[video['url']] = {
                                        'title': video['title'],
                                        'video_url': None,
                                        'cover_url': video.get('pic', ''),
                                        'bvid': video['bvid']
                                    }
                            
                            if interrupt_occurred:
                                break
                            continue
                    elif result and len(result) == 4:
                        title, video_url, cover_url, pages = result
                    elif result and len(result) >= 3:
                        title, video_url, cover_url = result[0], result[1], result[2]
                        pages = None
                    else:
                        p(f'[警告] 解析失败: {url}', 'r')
                        continue
                    
                    if title and video_url:
                        if pages and len(pages) > 1:
                            p(f'[B站] 检测到 {len(pages)} 个分P，进入分P选择...', 'c')
                            selected_pages = show_page_selection_menu(pages, title)
                            if selected_pages is None:
                                p('[跳过] 用户取消选择', 'y')
                                continue
                            
                            for page_num in selected_pages:
                                _ir = check_interrupt()
                                if _ir is not None:
                                    interrupt_occurred = True
                                    if _ir == 'continue':
                                        interrupt_manager.reset()
                                        interrupt_occurred = False
                                        continue
                                    break
                                
                                page = pages[page_num - 1]
                                page_title = page['part'][:50]
                                
                                exists, existing_path = check_file_exists_by_title(page_title)
                                if exists:
                                    p(f'[跳过] 分P已存在: {os.path.basename(existing_path)}', 'y')
                                    continue
                                
                                unique_key = f"{url}_p{page_num}"
                                valid_urls.append(unique_key)
                                url_info[unique_key] = {
                                    'url': url,
                                    'title': f"{title} - P{page['page']}: {page['part']}",
                                    'video_url': video_url,
                                    'cover_url': cover_url,
                                    'pages': pages,
                                    'bvid': bvid,
                                    'selected_pages': [page_num],
                                    'page': page,
                                    'page_num': page_num
                                }
                            
                            if interrupt_occurred:
                                break
                        else:
                            exists, existing_path = check_file_exists_by_title(title)
                            if exists:
                                p(f'[跳过] 文件已存在: {os.path.basename(existing_path)}', 'y')
                                skipped_urls.append(url)
                            else:
                                valid_urls.append(url)
                                url_info[url] = {
                                    'title': title,
                                    'video_url': video_url,
                                    'cover_url': cover_url,
                                    'pages': pages,
                                    'bvid': bvid
                                }
                    else:
                        p(f'[警告] 解析失败: {url}', 'r')
                
                if interrupt_occurred:
                    interrupt_manager.reset()
                    continue
                    
            except InterruptException:
                interrupt_occurred = True
                interrupt_result = interrupt_manager.get_interrupt_menu()
                if interrupt_result == 'main_menu':
                    p('\n[中断] 已返回主菜单', 'y')
                elif interrupt_result == 'skip':
                    p('\n[中断] 跳过当前任务', 'y')
                elif interrupt_result == 'reselect':
                    p('\n[中断] 重新选择', 'y')
                interrupt_manager.reset()
                continue
            
            if not valid_urls:
                if skipped_urls:
                    p(f'\n[信息] 所有 {len(skipped_urls)} 个视频都已存在，无需下载', 'g')
                else:
                    p('[错误] 没有可下载的视频', 'r')
                input("\n按回车键继续...")
                continue
            
            p(f'\n[信息] 跳过已存在: {len(skipped_urls)} 个，待下载: {len(valid_urls)} 个', 'c')
            for i, key in enumerate(valid_urls, 1):
                info = url_info.get(key, {})
                title = info.get('title', '未知标题')
                display_title = title[:50] + '...' if len(title) > 50 else title
                print(f'  {i}. {display_title}')
            
            global_mode = show_global_menu()
            
            if global_mode == 0:
                continue
            
            if global_mode == 5:
                p('剪贴板功能已移除，请直接输入链接', 'y')
                continue
            
            if global_mode == 4:
                print('\n[选择部分模式]')
                selection = input(f'请输入要处理的序号 (1-{len(valid_urls)}), 输入0返回: ').strip()
                
                if not selection or selection == '0':
                    p('[取消]', 'y')
                    continue
                
                if selection.lower() == 'all':
                    selected_indices = list(range(len(valid_urls)))
                else:
                    selected_indices = parse_selection_input(selection, len(valid_urls))
                    if not selected_indices:
                        p('[错误] 无效格式', 'y')
                        continue
                
                p(f'\n已选择 {len(selected_indices)} 个任务', 'c')
                
                print('\n' + '=' * 50)
                print('  [3] 都要（MP4+MP3，MP3带封面）')
                print('  [2] 仅MP3（下载音频，自动添加封面）')
                print('  [1] 仅MP4（下载视频）')
                print('  [q] 返回主菜单')
                print('=' * 50)
                video_mode = input('请选择 [1-3/q]: ').strip().lower()
                if video_mode in ('q', '0'):
                    continue
                if video_mode not in ['1', '2', '3']:
                    p('无效选项，使用模式2', 'y')
                    video_mode = '2'
                
                print("[提示] 直接回车 = 开始处理")
                confirm = input('\n开始处理？(直接回车=是, 输入0=否): ').strip()
                if confirm == '' or confirm == '1':
                    selected_urls = [valid_urls[idx] for idx in selected_indices]
                    try:
                        success, fail = process_selected_videos(selected_urls, int(video_mode), url_info)
                    except InterruptException:
                        p('\n[中断] 用户中断了下载过程', 'y')
                        interrupt_result = interrupt_manager.get_interrupt_menu()
                        if interrupt_result == 'main_menu':
                            p('\n[中断] 已返回主菜单', 'y')
                            interrupt_manager.clear()
                        elif interrupt_result == 'skip':
                            p('\n[中断] 跳过当前任务', 'y')
                            interrupt_manager.reset()
                        elif interrupt_result == 'reselect':
                            p('\n[中断] 重新选择', 'y')
                            interrupt_manager.clear()
                        elif interrupt_result == 'continue':
                            p('\n[继续] 继续当前下载...', 'c')
                            interrupt_manager.reset()
                            if interrupt_manager.current_urls:
                                p(f'[信息] 继续下载剩余 {len(interrupt_manager.current_urls)} 个文件...', 'c')
                                try:
                                    success, fail = process_selected_videos(
                                        interrupt_manager.current_urls,
                                        interrupt_manager.current_global_mode or interrupt_manager.current_mode,
                                        interrupt_manager.current_url_info,
                                        interrupt_manager.current_task_id
                                    )
                                    p(f'[完成] 成功: {success}  失败: {fail}', 'm')
                                except Exception as e:
                                    p(f'[错误] 继续下载失败: {e}', 'r')
                        continue
                    p(f'\n完成! 成功: {success}  失败: {fail}', 'm')
                else:
                    p('[取消]', 'y')
                    continue
                
            else:
                print("[提示] 直接回车 = 开始处理")
                confirm = input('\n开始处理？(直接回车=是, 输入0=否): ').strip()
                if confirm == '' or confirm == '1':
                    try:
                        success, fail = process_selected_videos(valid_urls, global_mode, url_info)
                    except InterruptException:
                        p('\n[中断] 用户中断了下载过程', 'y')
                        interrupt_result = interrupt_manager.get_interrupt_menu()
                        if interrupt_result == 'main_menu':
                            p('\n[中断] 已返回主菜单', 'y')
                            interrupt_manager.clear()
                        elif interrupt_result == 'skip':
                            p('\n[中断] 跳过当前任务', 'y')
                            interrupt_manager.reset()
                        elif interrupt_result == 'reselect':
                            p('\n[中断] 重新选择', 'y')
                            interrupt_manager.clear()
                        elif interrupt_result == 'continue':
                            p('\n[继续] 继续当前下载...', 'c')
                            interrupt_manager.reset()
                            if interrupt_manager.current_urls:
                                p(f'[信息] 继续下载剩余 {len(interrupt_manager.current_urls)} 个文件...', 'c')
                                try:
                                    success, fail = process_selected_videos(
                                        interrupt_manager.current_urls,
                                        interrupt_manager.current_global_mode or interrupt_manager.current_mode,
                                        interrupt_manager.current_url_info,
                                        interrupt_manager.current_task_id
                                    )
                                    p(f'[完成] 成功: {success}  失败: {fail}', 'm')
                                except Exception as e:
                                    p(f'[错误] 继续下载失败: {e}', 'r')
                        continue
                    
                    p(f'\n{"="*50}', 'm')
                    p(f'完成! 成功: {success}  失败: {fail}', 'm')
                    mode_text = {1: 'MP4', 2: 'MP3', 3: 'MP4+MP3'}.get(global_mode, '')
                    p(f'处理模式: {mode_text}', 'c')
                    
                    failed_count = len(get_failed_items())
                    if failed_count > 0:
                        p(f'\n[提示] 有 {failed_count} 个下载失败', 'y')
                        print("  输入 r 重新下载失败的文件")
                        print("  按回车继续")
                        choice = input("\n请选择: ").strip().lower()
                        if choice == 'r':
                            retry_failed_downloads()
                else:
                    p('[取消]', 'y')
                    continue
            
            p(f'保存位置: {DOWNLOAD_PATH}', 'c')
            print('=' * 50)
            
        except InterruptException:
            p('\n[中断] 用户中断了当前操作', 'y')
            interrupt_result = interrupt_manager.get_interrupt_menu()
            
            if interrupt_result == 'main_menu':
                p('\n[中断] 已返回主菜单', 'y')
                interrupt_manager.clear()
            elif interrupt_result == 'skip':
                p('\n[中断] 跳过当前任务', 'y')
                interrupt_manager.reset()
            elif interrupt_result == 'reselect':
                p('\n[中断] 重新选择', 'y')
                interrupt_manager.clear()
            elif interrupt_result == 'continue':
                p('\n[继续] 继续当前下载...', 'c')
                interrupt_manager.reset()
                if interrupt_manager.current_urls:
                    p(f'[信息] 继续下载剩余 {len(interrupt_manager.current_urls)} 个文件...', 'c')
                    try:
                        success, fail = process_selected_videos(
                            interrupt_manager.current_urls,
                            interrupt_manager.current_global_mode or interrupt_manager.current_mode,
                            interrupt_manager.current_url_info,
                            interrupt_manager.current_task_id
                        )
                        p(f'[完成] 成功: {success}  失败: {fail}', 'm')
                    except Exception as e:
                        p(f'[错误] 继续下载失败: {e}', 'r')
                else:
                    p('[信息] 没有可继续的任务', 'y')
            continue
            
        except KeyboardInterrupt:
            p('\n[中断] 检测到 Ctrl+C，正在中断...', 'y')
            interrupt_manager.trigger_interrupt()
            interrupt_result = interrupt_manager.get_interrupt_menu()
            
            if interrupt_result == 'main_menu':
                p('\n[中断] 已返回主菜单', 'y')
                interrupt_manager.clear()
            elif interrupt_result == 'skip':
                p('\n[中断] 跳过当前任务', 'y')
                interrupt_manager.reset()
            elif interrupt_result == 'reselect':
                p('\n[中断] 重新选择', 'y')
                interrupt_manager.clear()
            elif interrupt_result == 'continue':
                p('\n[继续] 继续当前下载...', 'c')
                interrupt_manager.reset()
                if interrupt_manager.current_urls:
                    p(f'[信息] 继续下载剩余 {len(interrupt_manager.current_urls)} 个文件...', 'c')
                    try:
                        success, fail = process_selected_videos(
                            interrupt_manager.current_urls,
                            interrupt_manager.current_global_mode or interrupt_manager.current_mode,
                            interrupt_manager.current_url_info,
                            interrupt_manager.current_task_id
                        )
                        p(f'[完成] 成功: {success}  失败: {fail}', 'm')
                    except Exception as e:
                        p(f'[错误] 继续下载失败: {e}', 'r')
                else:
                    p('[信息] 没有可继续的任务', 'y')
            continue
            
        except Exception as e:
            p(f'\n[错误] {e}', 'r')
            import traceback
            traceback.print_exc()
            input("\n按回车键继续...")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        p('\n[已取消] 用户中断', 'y')
    except Exception as e:
        p(f'\n[错误] {e}', 'r')