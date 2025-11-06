# 版权所有 (C) 2025 Muttix 保留所有权利
# 项目名称: UU_Search_TGBot (Telegram文件代码搜索器机器人)
# 文件名称: main.py
# Email: sunmutian88@gmail.com

# 引入库
import os
import telebot
import json
import gzip
import base64
import datetime
import time
import sys
import random
import re
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from dotenv import load_dotenv
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# ------------------ 全局变量 ------------------ #

# 日志文件路径
LOG_FILEPATH = None

# 数据目录路径
DATA_DIR = "./data/appdata"
LOG_DIR = "./log"
TEMP_DIR = "./temp"

# 用户请求频率限制
USER_REQUEST_LIMITS = {}  # 存储用户请求时间戳
USER_SEARCH_PATTERNS = {}  # 存储用户搜索模式

# 频率限制配置
REQUEST_LIMIT_WINDOW = 30  # 时间窗口(秒)
MAX_REQUESTS_PER_WINDOW = 20  # 每个窗口内最大请求数
SAME_CONTENT_LIMIT = 3  # 相同内容限制次数
BUFFER_TIME = 15  # 缓冲时间（秒）
MAX_RANDOM_LIMIT = 20  # 单个窗口时间内最大随机次数


# 随机次数限制
MAX_RANDOM_PER_DAY_NON_VIP = 10  # 非VIP用户每天最多随机次数

# ------------------ 工具函数 ------------------ #

# 将毫秒级时间戳转换为datetime对象
def timestamp_to_datetime(timestamp_ms):
    # 将毫秒转换为秒
    timestamp_sec = timestamp_ms / 1000.0
    return datetime.datetime.fromtimestamp(timestamp_sec)

# 获取当前时间戳（字符串格式）
def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 确保数据目录存在
def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

# 确保日志目录存在
def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

# 确保TEMP目录存在
def ensure_temp_dir():
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR, exist_ok=True)

# 初始化日志系统
def init_log_system():
    global LOG_FILEPATH
    try:
        # 确保日志目录存在
        ensure_log_dir()
        
        # 创建日志文件名（使用启动时间戳）
        startup_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"LOG_{startup_time}.log"
        LOG_FILEPATH = os.path.join(LOG_DIR, log_filename)
        
        # 创建日志文件并写入启动信息
        with open(LOG_FILEPATH, "w", encoding="utf-8") as f:
            f.write(f"=== UU Search Bot 启动于 {get_current_time()} ===\n\n")
        
        print(f"[{get_current_time()}] [INIT] 日志系统初始化完成: {LOG_FILEPATH}")
        return True
        
    except Exception as e:
        print(f"[{get_current_time()}] [ERROR] 初始化日志系统失败: {e}")
        return False

# 日志记录函数
def log_message(message, log_type="INFO"):
    timestamp = get_current_time()
    log_entry = f"[{timestamp}] [{log_type}] {message}"
    
    # 打印到控制台
    print(log_entry)
    
    # 写入日志文件
    if LOG_FILEPATH:
        try:
            with open(LOG_FILEPATH, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            print(f"[{get_current_time()}] [ERROR] 写入日志文件失败: {e}")

# 读取文本文件
def read_text_file(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
        else:
            log_message(f"文件不存在: {filepath}", "ERROR")
            return None
    except Exception as e:
        log_message(f"读取文件失败 {filepath}: {e}", "ERROR")
        return None

# 搜索函数
def search_in_descriptions(database, keyword):
    # 在代码介绍中搜索关键词
    if not database or "db_data" not in database:
        return []
    
    results = []
    for item in database["db_data"]:
        if len(item) >= 3:  # 确保有代码介绍字段
            code, code_type, description = item
            if keyword.lower() in description.lower():
                results.append(item)
    
    return results

# 获取用户显示名称
def get_user_display_name(user):
    # 如果有 first_name 和 last_name
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    # 如果只有 first_name
    elif user.first_name:
        return user.first_name
    # 如果只有 last_name（这种情况很少见）
    elif user.last_name:
        return user.last_name
    # 如果有 username
    elif user.username:
        return f"@{user.username}"
    # 如果什么都没有，使用用户ID
    else:
        return f"用户{user.id}"

# 检查内容是否包含广告
def contains_advertisement(text):
    """
    检查文本是否包含广告内容
    包括：@用户名、http链接、t.me链接、.com等
    """
    if not text:
        return False
    
    # 广告检测规则
    ad_patterns = [
        r'@\w+',  # @用户名
        r'http[s]?://',  # http链接
        r't\.me/',  # t.me链接
        r'\.com',  # .com域名
        r'\.net',  # .net域名
        r'\.org',  # .org域名
        r'[\w]+@[A-Za-z]+(\.[A-Za-z0-9]+){1,2}',  # 邮箱
        r'^(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,}$', # 泛域名
        r'购买', '付费', '充值', '代理', '联系', '低价', "口碑老店", "值得信赖", "安全靠谱", "博彩","社工库", "开户", "面付"  # 中文广告词
    ]
    
    text_lower = text.lower()
    for pattern in ad_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False

# 加载热搜榜单数据
def load_hot_searches():
    try:
        ensure_data_dir()
        hot_searches_path = os.path.join(DATA_DIR, "hot_searches.json")
        if os.path.exists(hot_searches_path):
            with open(hot_searches_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # 初始化为空的热搜数据
            default_hot_searches = {
                "last_updated": datetime.datetime.now().isoformat(),
                "search_counts": {}
            }
            # 保存默认数据
            with open(hot_searches_path, "w", encoding="utf-8") as f:
                json.dump(default_hot_searches, f, ensure_ascii=False, indent=2)
            return default_hot_searches
    except Exception as e:
        log_message(f"加载热搜榜单失败: {e}", "ERROR")
        return None

# 保存热搜榜单数据
def save_hot_searches(hot_searches_data):
    try:
        ensure_data_dir()
        hot_searches_path = os.path.join(DATA_DIR, "hot_searches.json")
        with open(hot_searches_path, "w", encoding="utf-8") as f:
            json.dump(hot_searches_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_message(f"保存热搜榜单失败: {e}", "ERROR")
        return False

# 更新热搜关键词计数
def update_hot_search_count(keyword):
    try:
        # 检查关键词是否包含广告内容
        if contains_advertisement(keyword):
            log_message(f"跳过广告关键词计数: {keyword}", "AD_DETECT")
            return False
            
        hot_searches_data = load_hot_searches()
        if not hot_searches_data:
            return False
        
        # 初始化search_counts如果不存在
        if "search_counts" not in hot_searches_data:
            hot_searches_data["search_counts"] = {}
        
        # 更新搜索计数
        if keyword in hot_searches_data["search_counts"]:
            hot_searches_data["search_counts"][keyword] += 1
        else:
            hot_searches_data["search_counts"][keyword] = 1
        
        # 更新最后修改时间
        hot_searches_data["last_updated"] = datetime.datetime.now().isoformat()
        
        return save_hot_searches(hot_searches_data)
        
    except Exception as e:
        log_message(f"更新热搜计数失败: {e}", "ERROR")
        return False

# 获取热搜榜单前10名（过滤广告内容）
def get_top_hot_searches(limit=10):
    try:
        hot_searches_data = load_hot_searches()
        if not hot_searches_data or "search_counts" not in hot_searches_data:
            return []
        
        # 过滤包含广告内容的关键词
        filtered_searches = {}
        for keyword, count in hot_searches_data["search_counts"].items():
            # 检查是否包含禁止内容
            if not contains_advertisement(keyword):
                filtered_searches[keyword] = count
        
        # 按搜索次数排序并取前limit名
        sorted_searches = sorted(
            filtered_searches.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return sorted_searches
    except Exception as e:
        log_message(f"获取热搜榜单失败: {e}", "ERROR")
        return []

# 加载用户使用记录
def load_user_usage_stats():
    try:
        ensure_data_dir()
        user_stats_path = os.path.join(DATA_DIR, "user_usage_stats.json")
        if os.path.exists(user_stats_path):
            with open(user_stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        log_message(f"加载用户使用记录失败: {e}", "ERROR")
        return {}

# 保存用户使用记录
def save_user_usage_stats(user_stats):
    try:
        ensure_data_dir()
        user_stats_path = os.path.join(DATA_DIR, "user_usage_stats.json")
        with open(user_stats_path, "w", encoding="utf-8") as f:
            json.dump(user_stats, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_message(f"保存用户使用记录失败: {e}", "ERROR")
        return False

# 更新用户使用记录
def update_user_usage_stats(user_id, action="search", keyword=None):
    try:
        user_stats = load_user_usage_stats()
        user_id_str = str(user_id)
        current_time = datetime.datetime.now().isoformat()
        
        if user_id_str not in user_stats:
            user_stats[user_id_str] = {
                "first_seen": current_time,
                "last_active": current_time,
                "total_searches": 0,
                "vip_status": False,
                "search_keywords": [],
                "actions": []
            }
        
        user_stats[user_id_str]["last_active"] = current_time
        
        if action == "search":
            user_stats[user_id_str]["total_searches"] = user_stats[user_id_str].get("total_searches", 0) + 1
            if keyword:
                user_stats[user_id_str]["search_keywords"].append({
                    "keyword": keyword,
                    "time": current_time
                })
                # 只保留最近50个搜索关键词
                user_stats[user_id_str]["search_keywords"] = user_stats[user_id_str]["search_keywords"][-50:]
        
        user_stats[user_id_str]["actions"].append({
            "action": action,
            "time": current_time,
            "keyword": keyword if action == "search" else None
        })
        
        # 只保留最近100个操作记录
        user_stats[user_id_str]["actions"] = user_stats[user_id_str]["actions"][-100:]
        
        return save_user_usage_stats(user_stats)
        
    except Exception as e:
        log_message(f"更新用户使用记录失败: {e}", "ERROR")
        return False

# 加载封禁用户列表
def load_banned_users():
    try:
        ensure_data_dir()
        banned_users_path = os.path.join(DATA_DIR, "banned_users.json")
        if os.path.exists(banned_users_path):
            with open(banned_users_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        log_message(f"加载封禁用户列表失败: {e}", "ERROR")
        return {}

# 保存封禁用户列表
def save_banned_users(banned_users):
    try:
        ensure_data_dir()
        banned_users_path = os.path.join(DATA_DIR, "banned_users.json")
        with open(banned_users_path, "w", encoding="utf-8") as f:
            json.dump(banned_users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_message(f"保存封禁用户列表失败: {e}", "ERROR")
        return False

# 检查用户是否被封禁
def is_user_banned(user_id):
    try:
        banned_users = load_banned_users()
        return str(user_id) in banned_users
    except Exception as e:
        log_message(f"检查用户封禁状态失败: {e}", "ERROR")
        return False

# 封禁用户
def ban_user(user_id, reason="违反使用规则", admin_id=None):
    try:
        banned_users = load_banned_users()
        user_id_str = str(user_id)
        
        banned_users[user_id_str] = {
            "banned_time": datetime.datetime.now().isoformat(),
            "reason": reason,
            "banned_by": admin_id
        }
        
        if save_banned_users(banned_users):
            log_message(f"用户 {user_id} 已被封禁，原因: {reason}", "BAN")
            return True
        return False
    except Exception as e:
        log_message(f"封禁用户失败: {e}", "ERROR")
        return False

# 解封用户
def unban_user(user_id):
    try:
        banned_users = load_banned_users()
        user_id_str = str(user_id)
        
        if user_id_str in banned_users:
            del banned_users[user_id_str]
            if save_banned_users(banned_users):
                log_message(f"用户 {user_id} 已解封", "UNBAN")
                return True
        return False
    except Exception as e:
        log_message(f"解封用户失败: {e}", "ERROR")
        return False

# 加载VIP用户数据
def load_vip_users():
    try:
        ensure_data_dir()
        vip_users_path = os.path.join(DATA_DIR, "vip_users.json")
        if os.path.exists(vip_users_path):
            with open(vip_users_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        log_message(f"加载VIP用户数据失败: {e}", "ERROR")
        return {}

# 保存VIP用户数据
def save_vip_users(vip_users):
    try:
        ensure_data_dir()
        vip_users_path = os.path.join(DATA_DIR, "vip_users.json")
        with open(vip_users_path, "w", encoding="utf-8") as f:
            json.dump(vip_users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_message(f"保存VIP用户数据失败: {e}", "ERROR")
        return False

# 加载用户搜索次数
def load_user_search_counts():
    try:
        ensure_data_dir()
        search_counts_path = os.path.join(DATA_DIR, "user_search_counts.json")
        if os.path.exists(search_counts_path):
            with open(search_counts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 检查日期，如果是新的一天则重置计数
                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                if data.get('date') != current_date:
                    return {}
                else:
                    return data.get('counts', {})
        else:
            return {}
    except Exception as e:
        log_message(f"加载用户搜索次数失败: {e}", "ERROR")
        return {}

# 保存用户搜索次数
def save_user_search_counts(user_search_counts):
    try:
        ensure_data_dir()
        search_counts_path = os.path.join(DATA_DIR, "user_search_counts.json")
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        data = {
            'date': current_date,
            'counts': user_search_counts
        }
        with open(search_counts_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_message(f"保存用户搜索次数失败: {e}", "ERROR")
        return False
    
# 加载用户随机次数
def load_user_random_counts():
    try:
        ensure_data_dir()
        random_counts_path = os.path.join(DATA_DIR, "user_random_counts.json")
        if os.path.exists(random_counts_path):
            with open(random_counts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 检查日期，如果是新的一天则重置计数
                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                if data.get('date') != current_date:
                    return {}
                else:
                    return data.get('counts', {})
        else:
            return {}
    except Exception as e:
        log_message(f"加载用户随机次数失败: {e}", "ERROR")
        return {}

# 保存用户随机次数
def save_user_random_counts(user_random_counts):
    try:
        ensure_data_dir()
        random_counts_path = os.path.join(DATA_DIR, "user_random_counts.json")
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        data = {
            'date': current_date,
            'counts': user_random_counts
        }
        with open(random_counts_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_message(f"保存用户随机次数失败: {e}", "ERROR")
        return False
    
# 检查用户请求频率（智能版）
def check_request_frequency(user_id, content=None):
    current_time = time.time()
    user_id_str = str(user_id)
    
    # 初始化用户记录
    if user_id_str not in USER_REQUEST_LIMITS:
        USER_REQUEST_LIMITS[user_id_str] = {
            'timestamps': [],
            'last_buffer_time': 0
        }
    
    if user_id_str not in USER_SEARCH_PATTERNS:
        USER_SEARCH_PATTERNS[user_id_str] = {}
    
    user_limits = USER_REQUEST_LIMITS[user_id_str]
    user_patterns = USER_SEARCH_PATTERNS[user_id_str]
    
    # 检查是否在缓冲期内
    if current_time - user_limits['last_buffer_time'] < BUFFER_TIME:
        return False, "缓冲期"
    
    # 清理过期的请求记录
    user_limits['timestamps'] = [
        timestamp for timestamp in user_limits['timestamps']
        if current_time - timestamp < REQUEST_LIMIT_WINDOW
    ]
    
    # 检查相同内容限制
    if content and content.strip():
        content_key = content.strip().lower()
        if content_key not in user_patterns:
            user_patterns[content_key] = []
        
        # 清理过期的相同内容记录
        user_patterns[content_key] = [
            timestamp for timestamp in user_patterns[content_key]
            if current_time - timestamp < REQUEST_LIMIT_WINDOW
        ]
        
        # 检查相同内容次数
        if content_key != "🎲 全库随机":
            # 如果不是全库随机搜索
            if len(user_patterns[content_key]) >= SAME_CONTENT_LIMIT:
                user_limits['last_buffer_time'] = current_time
                return False, "相同内容"
        elif len(user_patterns[content_key]) >= MAX_RANDOM_LIMIT:
            # 如果是全库随机搜索
            user_limits['last_buffer_time'] = current_time
            return False, "频繁请求"
        
        # 记录当前相同内容请求
        user_patterns[content_key].append(current_time)
    
    # 检查总请求次数限制
    if len(user_limits['timestamps']) >= MAX_REQUESTS_PER_WINDOW:
        user_limits['last_buffer_time'] = current_time
        return False, "频繁请求"
    
    # 记录当前请求
    user_limits['timestamps'].append(current_time)
    return True, None

# 清理过期的频率记录
def cleanup_old_frequency_records():
    current_time = time.time()
    expired_users = []
    
    for user_id_str, user_limits in USER_REQUEST_LIMITS.items():
        # 清理过期的请求记录
        user_limits['timestamps'] = [
            timestamp for timestamp in user_limits['timestamps']
            if current_time - timestamp < REQUEST_LIMIT_WINDOW * 2
        ]
        
        # 如果用户没有有效记录且不在缓冲期，标记为待删除
        if (not user_limits['timestamps'] and 
            current_time - user_limits['last_buffer_time'] > BUFFER_TIME * 2):
            expired_users.append(user_id_str)
    
    # 清理搜索模式记录
    for user_id_str, user_patterns in USER_SEARCH_PATTERNS.items():
        for content_key, timestamps in list(user_patterns.items()):
            # 清理过期的相同内容记录
            user_patterns[content_key] = [
                timestamp for timestamp in timestamps
                if current_time - timestamp < REQUEST_LIMIT_WINDOW * 2
            ]
            
            # 如果内容记录为空，删除该内容键
            if not user_patterns[content_key]:
                del user_patterns[content_key]
        
        # 如果用户没有搜索模式记录，标记为待删除
        if not user_patterns and user_id_str not in expired_users:
            expired_users.append(user_id_str)
    
    # 删除过期用户记录
    for user_id_str in expired_users:
        if user_id_str in USER_REQUEST_LIMITS:
            del USER_REQUEST_LIMITS[user_id_str]
        if user_id_str in USER_SEARCH_PATTERNS:
            del USER_SEARCH_PATTERNS[user_id_str]


# ------------------ Telegram 机器人主类 ------------------ #
class TelegramBot:
    # 从文件加载欢迎消息
    def load_welcome_message(self):
        content = read_text_file(self.WELCOME_MESSAGE_PATH)
        if content:
            log_message(f"已加载欢迎消息，长度: {len(content)} 字符", "INFO")
            return content
        else:
            log_message("欢迎消息文件不存在或读取失败", "ERROR")
            return "欢迎消息加载失败，请联系管理员。"

    # 从文件加载用户协议
    def load_user_agreement(self):
        content = read_text_file(self.USER_AGREEMENT_PATH)
        if content:
            log_message(f"已加载用户协议，长度: {len(content)} 字符", "INFO")
            return content
        else:
            log_message("用户协议文件不存在或读取失败", "ERROR")
            return "用户协议加载失败，请联系管理员。"

    # 从文件加载帮助信息
    def load_help_message(self):
        content = read_text_file(self.HELP_MESSAGE_PATH)
        if content:
            log_message(f"已加载帮助信息，长度: {len(content)} 字符", "INFO")
            return content
        else:
            log_message("帮助信息文件不存在或读取失败", "ERROR")
            return "帮助信息加载失败，请联系管理员。"

    # 初始化机器人配置
    def __init__(self):
        # 初始化日志系统
        if not init_log_system():
            print("日志系统初始化失败，程序退出")
            exit(1)

        # 加载.env文件中的环境变量
        load_dotenv()
        # 从环境变量获取机器人Token
        self.BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        # 从环境变量获取文件路径
        self.WELCOME_MESSAGE_PATH = os.getenv("WELCOME_MESSAGE_PATH", "./data/welcome_message.txt")
        self.USER_AGREEMENT_PATH = os.getenv("USER_AGREEMENT_PATH", "./data/user_agreement.txt")
        self.HELP_MESSAGE_PATH = os.getenv("HELP_MESSAGE_PATH", "./data/help_message.txt")
        self.DEFAULT_DATABASE_PATH = os.getenv("DEFAULT_DATABASE_PATH")
        # 管理员ID列表
        self.ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
        
        # LOG
        log_message(f"TELEGRAM_BOT_TOKEN = {self.BOT_TOKEN}", "ENV")
        log_message(f"WELCOME_MESSAGE_PATH = {self.WELCOME_MESSAGE_PATH}", "ENV")
        log_message(f"USER_AGREEMENT_PATH = {self.USER_AGREEMENT_PATH}", "ENV")
        log_message(f"HELP_MESSAGE_PATH = {self.HELP_MESSAGE_PATH}", "ENV")
        log_message(f"DEFAULT_DATABASE_PATH = {self.DEFAULT_DATABASE_PATH}", "ENV")
        log_message(f"ADMIN_IDS = {self.ADMIN_IDS}", "ENV")
        
        # 初始化机器人实例
        self.bot = None
        # 初始化数据库
        self.o_database = None
        # 用户搜索状态存储
        self.user_search_sessions = {}
        # VIP用户数据
        self.vip_users = load_vip_users()
        # 用户搜索次数记录
        self.user_search_counts = load_user_search_counts()
        # 用户随机次数记录
        self.user_random_counts = load_user_random_counts()
        # 用户使用统计
        self.user_usage_stats = load_user_usage_stats()
        # 封禁用户列表
        self.banned_users = load_banned_users()
        
        # 从文件读取欢迎消息
        self.WelcomeMessage = self.load_welcome_message()
        # 从文件读取用户协议
        self.UserAgreement = self.load_user_agreement()
        # 从文件读取帮助信息
        self.HelpMessage = self.load_help_message()

    # 检查用户VIP状态
    def is_vip_user(self, user_id):
        # 管理员自动拥有VIP权限（无限制）
        if user_id in self.ADMIN_IDS:
            return True
        
        user_id_str = str(user_id)
        if user_id_str in self.vip_users:
            expiry_time = datetime.datetime.fromisoformat(self.vip_users[user_id_str]['expiry_time'])
            if expiry_time > datetime.datetime.now():
                return True
            else:
                # VIP已过期，删除记录
                del self.vip_users[user_id_str]
                save_vip_users(self.vip_users)
        return False

    # 获取VIP剩余时间
    def get_vip_remaining_time(self, user_id):
        # 管理员显示无限制
        if user_id in self.ADMIN_IDS:
            return "永久"
        
        user_id_str = str(user_id)
        if user_id_str in self.vip_users:
            expiry_time = datetime.datetime.fromisoformat(self.vip_users[user_id_str]['expiry_time'])
            remaining = expiry_time - datetime.datetime.now()
            if remaining.total_seconds() > 0:
                days = remaining.days
                hours = remaining.seconds // 3600
                return f"{days}天{hours}小时"
        return "无"

    # 检查用户搜索限制
    def check_search_limit(self, user_id):
        # 检查用户是否被封禁
        if is_user_banned(user_id):
            return False, "❌ 无权限"
        
        if self.is_vip_user(user_id):
            return True, None  # VIP用户无限制
        
        user_id_str = str(user_id)
        today_searches = self.user_search_counts.get(user_id_str, 0)
        
        if today_searches >= 10:  # 非VIP用户每天最多10次搜索
            return False, "❌ 今日搜索次数已达上限（10次）\n\n⭐ 升级VIP可享受无限制搜索！"
        
        # 更新搜索次数
        self.user_search_counts[user_id_str] = today_searches + 1
        save_user_search_counts(self.user_search_counts)
        
        remaining_searches = 10 - (today_searches + 1)
        if remaining_searches <= 3:
            return True, f"💡 今日剩余搜索次数：{remaining_searches}次\n⭐ 升级VIP享受无限制搜索！"
        
        return True, None

    # 检查用户随机限制
    def check_random_limit(self, user_id):
        # 检查用户是否被封禁
        if is_user_banned(user_id):
            return False, "❌ 无权限"
        
        if self.is_vip_user(user_id):
            return True, None  # VIP用户无限制
        
        user_id_str = str(user_id)
        today_randoms = self.user_random_counts.get(user_id_str, 0)
        
        if today_randoms >= MAX_RANDOM_PER_DAY_NON_VIP:
            return False, f"❌ 今日随机次数已达上限（{MAX_RANDOM_PER_DAY_NON_VIP}次）\n\n⭐ 升级VIP可享受无限制随机推荐！"
        
        # 更新随机次数
        self.user_random_counts[user_id_str] = today_randoms + 1
        save_user_random_counts(self.user_random_counts)
        
        remaining_randoms = MAX_RANDOM_PER_DAY_NON_VIP - (today_randoms + 1)
        if remaining_randoms <= 1:
            return True, f"💡 今日剩余随机次数：{remaining_randoms}次\n⭐ 升级VIP享受无限制随机推荐！"
        
        return True, None

    # 添加VIP用户
    def add_vip_user(self, user_id, days=30):
        user_id_str = str(user_id)
        expiry_time = datetime.datetime.now() + datetime.timedelta(days=days)
        self.vip_users[user_id_str] = {
            'expiry_time': expiry_time.isoformat(),
            'added_time': datetime.datetime.now().isoformat(),
            'days': days
        }
        save_vip_users(self.vip_users)
        log_message(f"用户 {user_id} 已添加VIP，有效期{days}天", "VIP")

    # 检查翻页限制（非VIP用户最多6页）
    def check_page_limit(self, user_id, page_number):
        if self.is_vip_user(user_id):
            return True  # VIP用户无限制
        
        if page_number > 6:  # 非VIP用户最多查看6页
            return False
        
        return True

    # 创建主菜单底部键盘
    def create_main_keyboard(self):
        markup = ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=False
        )
        
        # 根据VIP状态显示不同按钮
        markup.row("📜 使用协议", "ℹ️ 帮助信息")
        markup.row("👤 我的信息", "⭐ VIP服务")
        markup.row("🎲 全库随机", "🔥 热搜榜单")
        
        return markup

    # 创建VIP服务键盘
    def create_vip_keyboard(self):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("💰 购买VIP", callback_data="vip_buy"),
            InlineKeyboardButton("📊 VIP状态", callback_data="vip_status")
        )
        markup.row(InlineKeyboardButton("🏠 返回主页", callback_data="back_to_main"))
        return markup

    # 创建分页内联键盘（带跳转功能）
    def create_pagination_keyboard(self, current_page, total_pages, search_id):
        markup = InlineKeyboardMarkup()
        
        # 页码信息
        page_info = f"{current_page}/{total_pages}"
        
        # 翻页按钮
        row_buttons = []
        if current_page > 1:
            row_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"page_{search_id}_{current_page-1}"))
        
        row_buttons.append(InlineKeyboardButton(f"📄 {page_info}", callback_data="page_info"))
        
        if current_page < total_pages:
            row_buttons.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"page_{search_id}_{current_page+1}"))
        
        markup.row(*row_buttons)
        
        # 跳转页面按钮（仅VIP用户显示）
        if self.check_page_limit(999999, current_page + 1):  # 临时检查
            markup.row(InlineKeyboardButton("🔢 跳转到页面", callback_data=f"jump_{search_id}"))
        
        # 操作按钮
        markup.row(
            InlineKeyboardButton("🔄 重新搜索", callback_data="new_search"),
            InlineKeyboardButton("🏠 返回主页", callback_data="back_to_main")
        )
        
        return markup

    # 创建管理员键盘
    def create_admin_keyboard(self):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📊 统计信息", "👥 用户管理")
        markup.row("⭐ VIP管理", "📁 日志管理")
        markup.row("🔄 重置限制", "📢 广播消息")
        markup.row("🚫 封禁管理", "🔥 热搜榜单管理")
        markup.row("📤 数据导出", "💬 用户私信")
        markup.row("🏠 返回主菜单")
        return markup
    
    # 创建内容导出键盘
    def create_export_keyboard(self):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("👥 用户数据", callback_data="export_users"),
            InlineKeyboardButton("⭐ VIP数据", callback_data="export_vip")
        )
        markup.row(
            InlineKeyboardButton("🔥 热搜数据", callback_data="export_hot_searches"),
            InlineKeyboardButton("📊 搜索统计", callback_data="export_search_stats")
        )
        markup.row(
            InlineKeyboardButton("🚫 封禁列表", callback_data="export_banned"),
            InlineKeyboardButton("📋 完整备份", callback_data="export_full")
        )
        markup.row(InlineKeyboardButton("⬅️ 返回管理员", callback_data="back_to_admin"))
        return markup

    # 创建热搜管理键盘
    def create_hot_search_keyboard(self):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("📋 查看热搜", callback_data="hot_search_view"),
            InlineKeyboardButton("✏️ 修改热搜", callback_data="hot_search_edit")
        )
        markup.row(
            InlineKeyboardButton("🗑️ 清空热搜", callback_data="hot_search_clear"),
            InlineKeyboardButton("🔄 重置计数", callback_data="hot_search_reset")
        )
        markup.row(InlineKeyboardButton("⬅️ 返回管理员", callback_data="back_to_admin"))
        return markup

    # 创建用户私信键盘
    def create_private_message_keyboard(self):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("📝 发送私信", callback_data="pm_send"),
            InlineKeyboardButton("📋 用户列表", callback_data="pm_user_list")
        )
        markup.row(InlineKeyboardButton("⬅️ 返回管理员", callback_data="back_to_admin"))
        return markup

    # 创建日志管理键盘
    def create_log_keyboard(self):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("📋 列出所有日志", callback_data="log_list"),
            InlineKeyboardButton("📊 当前日志", callback_data="log_current")
        )
        markup.row(InlineKeyboardButton("⬅️ 返回管理员", callback_data="back_to_admin"))
        return markup

    # 创建用户管理键盘
    def create_user_management_keyboard(self):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("📈 用户统计", callback_data="user_stats"),
            InlineKeyboardButton("👤 用户列表", callback_data="user_list")
        )
        markup.row(InlineKeyboardButton("⬅️ 返回管理员", callback_data="back_to_admin"))
        return markup

    # 创建封禁管理键盘
    def create_ban_management_keyboard(self):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("🚫 封禁用户", callback_data="ban_user"),
            InlineKeyboardButton("✅ 解封用户", callback_data="unban_user")
        )
        markup.row(InlineKeyboardButton("📋 封禁列表", callback_data="banned_list"))
        markup.row(InlineKeyboardButton("⬅️ 返回管理员", callback_data="back_to_admin"))
        return markup

    # 移除键盘
    def remove_keyboard(self):
        return ReplyKeyboardRemove()

    # 获取数据库信息
    def get_database_info(self):
        if not self.o_database:
            return "❌ 数据库未加载"
        
        db_name = self.o_database.get('name', '未知数据库')
        db_time = self.o_database.get('time', 0)
        db_notes = self.o_database.get('notes', '无备注')
        data_count = len(self.o_database.get('db_data', []))
        
        # 格式化时间
        if db_time:
            formatted_time = timestamp_to_datetime(db_time).strftime('%Y-%m-%d %H:%M:%S')
        else:
            formatted_time = '未知时间'
        
        info = f"""
<b>📊 数据库信息</b>

📁 数据库名称: {db_name}
📅 创建时间: {formatted_time}
📝 数据库备注: {db_notes}
📋 数据条目: {data_count} 条
"""
        return info

    # 初始化代码数据库
    def initDataBase(self):
        try:
            # 读取数据库文件
            with gzip.open(self.DEFAULT_DATABASE_PATH, 'rb') as f:
                final_encrypted_base64 = f.read()
            # 第一步：base64解码
            encrypted_data = base64.b64decode(final_encrypted_base64)
            # 第二步：AES解密
            key = b"vq1ljMB0hRWRKnRDDraM8fE0fLssjWhM"
            cipher = AES.new(key, AES.MODE_ECB)
            # 解密数据
            decrypted_padded_data = cipher.decrypt(encrypted_data)
            # 第三步：去除填充
            try:
                decrypted_data = unpad(decrypted_padded_data, AES.block_size)
            except ValueError as e:
                log_message(f"去除填充时出错: {e}", "ERROR")
                # 如果标准unpad失败，尝试手动处理
                decrypted_data = decrypted_padded_data.rstrip(b'\x00')
            # 第四步：解码base64字符串
            base64_decoded_str = decrypted_data.decode('utf-8')
            json_bytes = base64.b64decode(base64_decoded_str)
            json_str = json_bytes.decode('utf-8')
            # 第五步：解析JSON
            self.o_database = json.loads(json_str)
            # LOG
            log_message(f"已从数据库({self.o_database['name']})中导入了 {len(self.o_database['db_data'])} 条内容。该数据库的创建日期为:{timestamp_to_datetime(self.o_database['time']).strftime('%Y-%m-%d %H:%M:%S')} ({self.o_database['time']}),该数据库的注意事项为:{self.o_database['notes']}", "INFO")
        except Exception as e:
            log_message(f"数据库初始化失败: {e}", "ERROR")
            self.o_database = {"name": "空数据库", "time": 0, "notes": "数据库加载失败", "db_data": []}

    # 生成搜索会话ID
    def generate_search_id(self, user_id, keyword):
        import hashlib
        import time
        unique_str = f"{user_id}_{keyword}_{time.time()}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:8]

    # 处理 /start 命令
    def start_(self, message):
        # 检查用户是否被封禁
        if is_user_banned(message.from_user.id):
            self.bot.send_message(message.chat.id, "❌ 无权限")
            return
        
        log_message(f"用户 {get_user_display_name(message.from_user)}({message.from_user.id}) 发送了 /start 命令", "INFO")
        
        # 更新用户使用记录
        update_user_usage_stats(message.from_user.id, "start")
        
        # 构建完整的欢迎消息（包含数据库信息）
        full_welcome_message = self.WelcomeMessage
        
        # 发送欢迎消息和按钮
        self.bot.send_message(
            message.chat.id, 
            full_welcome_message, 
            parse_mode="HTML",
            reply_markup=self.create_main_keyboard()
        )

    # 显示用户协议
    def ShowUserAgreement_(self, message):
        # 检查用户是否被封禁
        if is_user_banned(message.from_user.id):
            self.bot.send_message(message.chat.id, "❌ 无权限")
            return
        
        self.bot.send_message(
            message.chat.id, 
            self.UserAgreement, 
            parse_mode="HTML",
            reply_markup=self.create_main_keyboard()
        )
    
    # 搜索功能 - 带分页
    def handle_search(self, message, keyword=None):
        # 检查用户是否被封禁
        if is_user_banned(message.from_user.id):
            self.bot.send_message(message.chat.id, "❌ 无权限")
            return
        
        if not self.o_database or not self.o_database.get("db_data"):
            self.bot.reply_to(message, "❌ 数据库未加载或为空")
            return
        
        user_id = message.from_user.id
        
        # 检查搜索限制
        can_search, limit_message = self.check_search_limit(user_id)
        if not can_search:
            self.bot.reply_to(message, limit_message)
            return
        
        # 如果没有提供关键词，从消息中提取
        if keyword is None:
            if message.text.startswith("搜索 "):
                keyword = message.text[3:].strip()
            else:
                keyword = message.text.strip()
        
        if not keyword:
            self.bot.send_message(
                message.chat.id,
                "🔍 请输入搜索关键词\n\n格式：<code>搜索 关键词</code>\n或直接发送关键词",
                parse_mode="HTML",
                reply_markup=self.create_main_keyboard()
            )
            return
        
        # 检查关键词是否包含广告内容
        contains_ad = contains_advertisement(keyword)
        
        if contains_ad:
            # 发送警告给所有管理员
            user_nickname = get_user_display_name(message.from_user)
            warning_msg = f"🚨 广告链接检测\n用户ID: {message.from_user.id}\n昵称: {user_nickname}\n搜索内容: {keyword}"
            
            # 发送警告给所有管理员
            for admin_id in self.ADMIN_IDS:
                try:
                    self.bot.send_message(admin_id, warning_msg)
                except Exception as e:
                    log_message(f"向管理员 {admin_id} 发送警告失败: {e}", "ERROR")
            
            # 不更新热搜计数（广告内容不计入热搜）
            log_message(f"用户 {user_id} 搜索广告内容: {keyword}，不计入热搜", "AD_DETECT")
        else:
            # 只有非广告内容才更新热搜计数
            update_hot_search_count(keyword)
        
        # 更新用户使用记录（无论是否广告都记录）
        update_user_usage_stats(user_id, "search", keyword)
        
        # 执行搜索（无论是否广告都返回结果）
        results = search_in_descriptions(self.o_database, keyword)
        
        if not results:
            self.bot.send_message(
                message.chat.id,
                f"🔍 没有找到包含「{keyword}」的代码介绍",
                parse_mode='HTML',
                reply_markup=self.create_main_keyboard()
            )
            return
        
        # 生成搜索会话ID
        search_id = self.generate_search_id(user_id, keyword)
        
        # 存储搜索会话
        self.user_search_sessions[search_id] = {
            'user_id': user_id,
            'keyword': keyword,
            'results': results,
            'current_page': 1,
            'total_pages': len(results),
            'created_time': datetime.datetime.now(),
            'contains_ad': contains_ad  # 标记是否包含广告
        }
        
        # LOG
        if contains_ad:
            log_message(f"用户 {get_user_display_name(message.from_user)}({user_id}) 搜索广告关键词: {keyword}, 找到 {len(results)} 条结果（不计入热搜）", "INFO")
        else:
            log_message(f"用户 {get_user_display_name(message.from_user)}({user_id}) 搜索关键词: {keyword}, 找到 {len(results)} 条结果", "INFO")
        
        # 显示第一页
        self.show_search_page(message.chat.id, search_id, 1, message.message_id)
        
        # 显示限制提示信息
        if limit_message:
            self.bot.send_message(message.chat.id, limit_message)

    # 显示搜索结果的指定页面
    def show_search_page(self, chat_id, search_id, page_number, reply_to_message_id=None):
        if search_id not in self.user_search_sessions:
            self.bot.send_message(chat_id, "❌ 搜索会话已过期，请重新搜索")
            return
        
        session = self.user_search_sessions[search_id]
        results = session['results']
        total_pages = len(results)
        user_id = session['user_id']
        contains_ad = session.get('contains_ad', False)
        
        # 检查翻页限制（非VIP用户最多6页）
        if not self.check_page_limit(user_id, page_number):
            self.bot.send_message(chat_id, "❌ 非VIP用户最多查看6页内容\n\n⭐ 升级VIP可查看全部结果！")
            page_number = 6  # 限制在6页
        
        # 确保页码在有效范围内
        page_number = max(1, min(page_number, total_pages))
        session['current_page'] = page_number
        
        # 获取当前页的数据
        current_item = results[page_number - 1]
        code, code_type, description = current_item
        
        # 代码种类映射
        type_names = {
            1: "推荐使用 @ShowFilesBot 必要时使用 @FilesPan1Bot (FilesDriveBLGA与旧密文)",
            2: "@ShowFilesBot 或 @MediaBKbot", 
            3: "@ShowFilesBot",
            4: "@ShowFilesBot (DataPanBot)",
            5: "@ShowFilesBot (FilesPan1Bot)",
            6: "南天门解码器( @ntmjmqbot )"
        }
        type_name = type_names.get(code_type)
        
        # 构建消息内容
        response = f"🔍 <b>搜索「{session['keyword']}」</b>\n"
        
        # 如果是广告内容，添加提示
        if contains_ad:
            response += "⚠️ <i>检测到广告内容，本次搜索不计入热搜榜单</i>\n"
        
        response += f"📄 <i>第 {page_number}/{total_pages} 页</i>\n"
        
        # 显示翻页限制提示
        if not self.is_vip_user(user_id) and total_pages > 6:
            response += f"<i>💡 非VIP用户最多查看6页内容</i>\n\n"
        else:
            response += "\n"
        
        response += f"<b>📁 代码适用解码器:</b> {type_name}\n"
        response += f"<b>🔤 代码内容:</b>\n<code>{code}</code>\n\n"
        response += f"<b>📝 代码介绍:</b>\n<i>{description}</i>\n\n"
        
        # 添加底部标识
        response += f"<i>UU搜索 - UUSearchBot</i>"
        
        # 创建分页键盘
        markup = self.create_pagination_keyboard(page_number, total_pages, search_id)
        
        # 发送或编辑消息
        if reply_to_message_id:
            # 编辑现有消息
            try:
                self.bot.edit_message_text(
                    response,
                    chat_id,
                    reply_to_message_id,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except Exception as e:
                # 如果编辑失败，发送新消息
                log_message(f"编辑消息失败: {e}", "ERROR")
                self.bot.send_message(
                    chat_id,
                    response,
                    parse_mode='HTML',
                    reply_markup=markup
                )
        else:
            # 发送新消息
            self.bot.send_message(
                chat_id,
                response,
                parse_mode='HTML',
                reply_markup=markup
            )
    
    # 处理分页回调
    def handle_pagination_callback(self, call):
        try:
            data = call.data
            message = call.message
            
            if data.startswith("page_"):
                # 解析页码信息
                parts = data.split("_")
                if len(parts) >= 3:
                    search_id = parts[1]
                    page_number = int(parts[2])
                    
                    # 编辑现有消息显示指定页面
                    self.show_search_page(call.message.chat.id, search_id, page_number, call.message.message_id)
                    
                    # 回答回调查询
                    self.bot.answer_callback_query(call.id, f"切换到第 {page_number} 页")
            
            elif data.startswith("jump_"):
                # 跳转到指定页面
                search_id = data.split("_")[1]
                # 请求用户输入页码
                msg = self.bot.send_message(
                    call.message.chat.id,
                    "🔢 请输入要跳转的页码：",
                    reply_to_message_id=call.message.message_id
                )
                # 注册下一步处理器
                self.bot.register_next_step_handler(msg, self.handle_jump_page, search_id)
                self.bot.answer_callback_query(call.id, "请输入页码")
            
            elif data == "new_search":
                # 重新搜索
                self.bot.delete_message(call.message.chat.id, call.message.message_id)
                self.bot.send_message(
                    call.message.chat.id,
                    "🔍 请输入新的搜索关键词：",
                    parse_mode="HTML",
                    reply_markup=self.create_main_keyboard()
                )
                self.bot.answer_callback_query(call.id, "开始新的搜索")
            
            elif data == "back_to_main":
                # 返回主页
                self.bot.delete_message(call.message.chat.id, call.message.message_id)
                # 创建临时消息对象用于start_函数
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.start_(temp_message)
                self.bot.answer_callback_query(call.id, "返回主页")
            
            elif data == "page_info":
                self.bot.answer_callback_query(call.id, "当前页面信息")
            
            # VIP相关回调 - 修改这里
            elif data == "vip_buy":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat,
                    'message_id': call.message.message_id
                })()
                self.show_vip_purchase_options(temp_message)
                self.bot.answer_callback_query(call.id, "VIP购买选项")
                
            elif data == "vip_status":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat,
                    'message_id': call.message.message_id
                })()
                self.show_vip_status(temp_message)
                self.bot.answer_callback_query(call.id, "VIP状态")
                
            elif data == "vip_back":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat,
                    'message_id': call.message.message_id
                })()
                self.handle_vip_service(temp_message)
                self.bot.answer_callback_query(call.id, "返回VIP服务")
            
            # 日志管理回调
            elif data == "log_list":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.list_log_files(temp_message)
                self.bot.answer_callback_query(call.id, "列出日志文件")
                
            elif data == "log_current":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.send_current_log(temp_message)
                self.bot.answer_callback_query(call.id, "发送当前日志")
                
            elif data == "back_to_admin":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.handle_admin_command(temp_message)
                self.bot.answer_callback_query(call.id, "返回管理员")
            
            # 用户管理回调
            elif data == "user_stats":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.show_user_statistics(temp_message)
                self.bot.answer_callback_query(call.id, "用户统计")
                
            elif data == "user_list":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.show_user_list(temp_message)
                self.bot.answer_callback_query(call.id, "用户列表")
            
            # 封禁管理回调
            elif data == "ban_user":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.request_ban_user(temp_message)
                self.bot.answer_callback_query(call.id, "封禁用户")
                
            elif data == "unban_user":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.request_unban_user(temp_message)
                self.bot.answer_callback_query(call.id, "解封用户")
                
            elif data == "banned_list":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.show_banned_users(temp_message)
                self.bot.answer_callback_query(call.id, "封禁列表")
            
            # 热搜榜单管理回调
            elif data == "hot_search_view":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.show_hot_search_list(temp_message)
                self.bot.answer_callback_query(call.id, "查看热搜榜单")
                
            elif data == "hot_search_edit":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.request_edit_hot_search(temp_message)
                self.bot.answer_callback_query(call.id, "修改热搜榜单")
                
            elif data == "hot_search_clear":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.clear_hot_searches(temp_message)
                self.bot.answer_callback_query(call.id, "清空热搜榜单")
                
            elif data == "hot_search_reset":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.reset_hot_search_counts(temp_message)
                self.bot.answer_callback_query(call.id, "重置搜索计数")
            
            # 数据导出回调
            elif data == "export_users":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.export_user_data(temp_message)
                self.bot.answer_callback_query(call.id, "导出用户数据")
                
            elif data == "export_vip":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.export_vip_data(temp_message)
                self.bot.answer_callback_query(call.id, "导出VIP数据")
                
            elif data == "export_hot_searches":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.export_hot_searches_data(temp_message)
                self.bot.answer_callback_query(call.id, "导出热搜数据")
                
            elif data == "export_search_stats":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.export_search_stats(temp_message)
                self.bot.answer_callback_query(call.id, "导出搜索统计")
                
            elif data == "export_banned":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.export_banned_users(temp_message)
                self.bot.answer_callback_query(call.id, "导出封禁列表")
                
            elif data == "export_full":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.export_full_backup(temp_message)
                self.bot.answer_callback_query(call.id, "导出完整备份")
            
            # 用户私信回调
            elif data == "pm_send":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.request_private_message(temp_message)
                self.bot.answer_callback_query(call.id, "发送私信")
                
            elif data == "pm_user_list":
                # 创建临时消息对象，包含正确的用户信息
                temp_message = type('obj', (object,), {
                    'from_user': call.from_user,
                    'chat': call.message.chat
                })()
                self.show_pm_user_list(temp_message)
                self.bot.answer_callback_query(call.id, "用户列表")
                    
        except Exception as e:
            log_message(f"处理分页回调时出错: {e}", "ERROR")
            self.bot.answer_callback_query(call.id, "操作失败，请重试")
    
    # 处理跳转页面输入
    def handle_jump_page(self, message, search_id):
        try:
            page_number = int(message.text.strip())
            # 删除用户输入的消息
            self.bot.delete_message(message.chat.id, message.message_id)
            # 跳转到指定页面，使用当前消息的ID
            self.show_search_page(message.chat.id, search_id, page_number, message.message_id)
        except ValueError:
            self.bot.send_message(message.chat.id, "❌ 请输入有效的页码数字")
        except Exception as e:
            log_message(f"处理跳转页面失败: {e}", "ERROR")
            self.bot.send_message(message.chat.id, "❌ 跳转失败，请重试")

    # 显示VIP购买选项
    def handle_vip_service(self, message):
        # 显示VIP购买选项
        vip_options = f"""
    <b>⭐ VIP会员服务</b>

    🎁 <b>VIP特权：</b>
    • 无限制搜索次数
    • 查看全部搜索结果（无6页限制）
    • 优先技术支持

    💰 <b>价格方案：</b>
    • 1个月 VIP - 15元
    • 3个月 VIP - 40元 (省5元)
    • 6个月 VIP - 75元 (省15元)
    • 12个月 VIP - 140元 (省40元)

    💳 <b>购买方式：</b>
    联系TG @JLmn7

    🆔 <b>您的用户ID是：</b><code>{message.from_user.id}</code>
    开通VIP需要告诉我你的ID
    """
        
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("📊 VIP状态", callback_data="vip_status"),
            InlineKeyboardButton("⬅️ 返回上一页", callback_data="vip_back")
        )
        
        try:
            # 检查是否有message_id（来自回调）
            if hasattr(message, 'message_id'):
                self.bot.edit_message_text(
                    vip_options,
                    message.chat.id,
                    message.message_id,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            else:
                # 来自普通消息
                self.bot.send_message(
                    message.chat.id,
                    vip_options,
                    parse_mode='HTML',
                    reply_markup=markup
                )
        except Exception as e:
            log_message(f"显示VIP购买选项失败: {e}", "ERROR")
            # 如果编辑失败，发送新消息
            self.bot.send_message(
                message.chat.id,
                vip_options,
                parse_mode='HTML',
                reply_markup=markup
            )

    def show_vip_status(self, message):
        # 显示VIP状态
        user_id = message.from_user.id
        is_vip = self.is_vip_user(user_id)
        remaining_time = self.get_vip_remaining_time(user_id)
        
        if is_vip:
            status_text = f"""
    <b>⭐ 您的VIP状态</b>

    ✅ <b>状态：</b> VIP会员
    ⏰ <b>剩余时间：</b> {remaining_time}
    🎉 <b>享受所有VIP特权！</b>
    """
        else:
            status_text = f"""
    <b>⭐ 您的VIP状态</b>

    ❌ <b>状态：</b> 非VIP会员
    🆔 <b>您的用户ID：</b> <code>{user_id}</code>

    📊 <b>当前限制：</b>
    • 每天最多搜索10次
    • 最多查看6页结果

    💡 <b>升级VIP享受：</b>
    • 无限制搜索次数
    • 查看全部搜索结果
    • 优先技术支持
    """
        
        markup = InlineKeyboardMarkup()
        if not is_vip:
            markup.row(InlineKeyboardButton("💰 购买VIP", callback_data="vip_buy"))
        markup.row(InlineKeyboardButton("⬅️ 返回上一页", callback_data="vip_back"))
        
        try:
            # 检查是否有message_id（来自回调）
            if hasattr(message, 'message_id'):
                self.bot.edit_message_text(
                    status_text,
                    message.chat.id,
                    message.message_id,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            else:
                # 来自普通消息
                self.bot.send_message(
                    message.chat.id,
                    status_text,
                    parse_mode='HTML',
                    reply_markup=markup
                )
        except Exception as e:
            log_message(f"显示VIP状态失败: {e}", "ERROR")
            self.bot.send_message(
                message.chat.id,
                status_text,
                parse_mode='HTML',
                reply_markup=markup
            )
    
    # 全库随机功能
    def handle_random_search(self, message):
        # 检查用户是否被封禁
        if is_user_banned(message.from_user.id):
            self.bot.send_message(message.chat.id, "❌ 无权限")
            return
        
        if not self.o_database or not self.o_database.get("db_data"):
            self.bot.reply_to(message, "❌ 数据库未加载或为空")
            return
        
        user_id = message.from_user.id
        
        # 检查随机限制
        can_random, limit_message = self.check_random_limit(user_id)
        if not can_random:
            self.bot.reply_to(message, limit_message)
            return
        
        # 从数据库中随机选择一条记录
        random_item = random.choice(self.o_database["db_data"])
        code, code_type, description = random_item
        
        # 代码种类映射
        type_names = {
            1: "推荐使用 @ShowFilesBot 必要时使用 @FilesPan1Bot (FilesDriveBLGA与旧密文)",
            2: "@ShowFilesBot 或 @MediaBKbot", 
            3: "@ShowFilesBot",
            4: "@ShowFilesBot (DataPanBot)",
            5: "@ShowFilesBot (FilesPan1Bot)",
            6: "南天门解码器( @ntmjmqbot )"
        }
        type_name = type_names.get(code_type)
        
        # 构建消息内容
        response = f"🎲 <b>全库随机推荐</b>\n\n"
        
        # 显示随机次数提示
        user_id_str = str(user_id)
        today_randoms = self.user_random_counts.get(user_id_str, 0)
        remaining_randoms = MAX_RANDOM_PER_DAY_NON_VIP - today_randoms
        
        if not self.is_vip_user(user_id):
            response += f"<i>💡 今日剩余随机次数：{remaining_randoms}/{MAX_RANDOM_PER_DAY_NON_VIP}</i>\n\n"
        
        response += f"<b>📁 代码适用解码器:</b> {type_name}\n"
        response += f"<b>🔤 代码内容:</b>\n<code>{code}</code>\n\n"
        response += f"<b>📝 代码介绍:</b>\n<i>{description}</i>\n\n"
        response += f"<i>UU搜索 - UUSearchBot</i>"
        
        # 更新用户使用记录
        update_user_usage_stats(user_id, "random_search")
        
        # 发送随机结果
        self.bot.send_message(
            message.chat.id,
            response,
            parse_mode='HTML',
            reply_markup=self.create_main_keyboard()
        )
        
        # 显示限制提示信息
        if limit_message:
            self.bot.send_message(message.chat.id, limit_message)
    
    # 显示热搜榜单
    def handle_hot_searches(self, message):
        # 检查用户是否被封禁
        if is_user_banned(message.from_user.id):
            self.bot.send_message(message.chat.id, "❌ 无权限")
            return
        
        top_searches = get_top_hot_searches(10)
        
        if not top_searches:
            self.bot.send_message(
                message.chat.id,
                "🔥 <b>热搜榜单</b>\n\n暂无搜索数据",
                parse_mode='HTML',
                reply_markup=self.create_main_keyboard()
            )
            return
        
        # 构建热搜榜单消息
        hot_searches_text = "🔥 <b>热搜榜单 TOP 10</b>\n\n"
        
        for i, (keyword, count) in enumerate(top_searches, 1):
            hot_searches_text += f"{i}. <code>{keyword}</code> - {count}次\n"
        
        hot_searches_text += f"\n💡 点击热搜关键词可直接搜索"
        
        self.bot.send_message(
            message.chat.id,
            hot_searches_text,
            parse_mode='HTML',
            reply_markup=self.create_main_keyboard()
        )
    
    # 管理员命令处理
    def handle_admin_command(self, message):
        if message.from_user.id not in self.ADMIN_IDS:
            self.bot.reply_to(message, "❌ 无权访问管理员功能")
            return
        
        admin_menu = """
    <b>⚙️ 管理员面板</b>

    选择要管理的功能：
    """
        admin_menu = admin_menu + "\n\n" + self.get_database_info()
        
        try:
            self.bot.send_message(
                message.chat.id,
                admin_menu,
                parse_mode='HTML',
                reply_markup=self.create_admin_keyboard()
            )
            print("DEBUG: 管理员面板发送成功")
        except Exception as e:
            print(f"DEBUG: 发送管理员面板失败: {e}")
            self.bot.reply_to(message, f"❌ 发送管理员面板失败: {e}")
    
    # 处理管理员功能
    def handle_admin_functions(self, message):
        if message.from_user.id not in self.ADMIN_IDS:
            return
        
        if message.text == "📊 统计信息":
            self.show_admin_stats(message)
        elif message.text == "👥 用户管理":
            self.show_user_management(message)
        elif message.text == "⭐ VIP管理":
            self.show_vip_management(message)
        elif message.text == "📁 日志管理":
            self.show_log_management(message)
        elif message.text == "🔄 重置限制":
            self.reset_user_limits(message)
        elif message.text == "📢 广播消息":
            self.request_broadcast_message(message)
        elif message.text == "🚫 封禁管理":
            self.show_ban_management(message)
        elif message.text == "🔥 热搜榜单管理":
            self.show_hot_search_management(message)
        elif message.text == "📤 数据导出":
            self.show_data_export_options(message)
        elif message.text == "💬 用户私信":
            self.show_private_message_options(message)
        elif message.text == "🏠 返回主菜单":
            self.start_(message)

    # 显示热搜管理
    def show_hot_search_management(self, message):
        hot_search_management = """
<b>🔥 热搜榜单管理</b>

选择热搜管理操作：
"""
        self.bot.send_message(
            message.chat.id,
            hot_search_management,
            parse_mode='HTML',
            reply_markup=self.create_hot_search_keyboard()
        )
    
    # 显示用户私信选项
    def show_private_message_options(self, message):
        private_message_menu = """
<b>💬 用户私信</b>

选择私信操作：
"""
        self.bot.send_message(
            message.chat.id,
            private_message_menu,
            parse_mode='HTML',
            reply_markup=self.create_private_message_keyboard()
        )
    
    # 显示数据导出选项
    def show_data_export_options(self, message):
        export_menu = """
<b>📤 数据导出</b>

选择要导出的数据类型：
"""
        self.bot.send_message(
            message.chat.id,
            export_menu,
            parse_mode='HTML',
            reply_markup=self.create_export_keyboard()
        )
    
    # 显示管理员统计信息
    def show_admin_stats(self, message):
        total_vip = len(self.vip_users)
        today_searches = sum(self.user_search_counts.values())
        active_sessions = len(self.user_search_sessions)
        user_stats = load_user_usage_stats()
        total_users = len(user_stats)
        banned_users = load_banned_users()
        total_banned = len(banned_users)
        
        stats_text = f"""
<b>📊 系统统计信息</b>

⭐ VIP用户数: {total_vip}
🔍 今日搜索次数: {today_searches}
💬 活跃会话数: {active_sessions}
👥 总用户数: {total_users}
🚫 封禁用户: {total_banned}
📁 数据库条目: {len(self.o_database.get('db_data', []))}
"""
        self.bot.send_message(message.chat.id, stats_text, parse_mode='HTML')
    
    # 显示用户管理
    def show_user_management(self, message):
        user_management = """
<b>👥 用户管理</b>

选择用户管理操作：
"""
        self.bot.send_message(
            message.chat.id,
            user_management,
            parse_mode='HTML',
            reply_markup=self.create_user_management_keyboard()
        )
    
    # 显示用户统计信息
    def show_user_statistics(self, message):
        user_stats = load_user_usage_stats()
        total_users = len(user_stats)
        
        # 计算活跃用户（最近7天有活动的）
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        active_users = 0
        total_searches = 0
        
        for user_id, stats in user_stats.items():
            total_searches += stats.get('total_searches', 0)
            last_active = datetime.datetime.fromisoformat(stats.get('last_active', '2000-01-01'))
            if last_active > seven_days_ago:
                active_users += 1
        
        # 获取搜索最多的用户
        top_searchers = sorted(
            [(uid, stats.get('total_searches', 0)) for uid, stats in user_stats.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        stats_text = f"""
<b>📈 用户统计信息</b>

👥 总用户数: {total_users}
🔍 总搜索次数: {total_searches}
📊 活跃用户(7天): {active_users}
⭐ VIP用户: {len(self.vip_users)}

🏆 <b>搜索排行榜 TOP 5:</b>
"""
        
        for i, (user_id, searches) in enumerate(top_searchers, 1):
            stats_text += f"{i}. 用户 {user_id} - {searches}次\n"
        
        self.bot.send_message(message.chat.id, stats_text, parse_mode='HTML')
    
    # 显示用户列表
    def show_user_list(self, message):
        user_stats = load_user_usage_stats()
        total_users = len(user_stats)
        
        # 按最后活跃时间排序
        sorted_users = sorted(
            user_stats.items(),
            key=lambda x: datetime.datetime.fromisoformat(x[1].get('last_active', '2000-01-01')),
            reverse=True
        )[:20]  # 只显示前20个用户
        
        user_list_text = f"""
<b>👤 用户列表 (最近活跃的前20个)</b>

总用户数: {total_users}

"""
        
        for i, (user_id, stats) in enumerate(sorted_users, 1):
            last_active = datetime.datetime.fromisoformat(stats.get('last_active', '2000-01-01'))
            days_ago = (datetime.datetime.now() - last_active).days
            vip_status = "⭐" if self.is_vip_user(int(user_id)) else "🔹"
            banned_status = "🚫" if is_user_banned(int(user_id)) else "✅"
            
            user_list_text += f"{i}. {vip_status}{banned_status} 用户 {user_id}\n"
            user_list_text += f"   搜索: {stats.get('total_searches', 0)}次 | {days_ago}天前活跃\n"
        
        if total_users > 20:
            user_list_text += f"\n... 还有 {total_users - 20} 个用户未显示"
        
        self.bot.send_message(message.chat.id, user_list_text, parse_mode='HTML')
    
    # 显示VIP管理
    def show_vip_management(self, message):
        vip_count = len(self.vip_users)
        vip_list = "\n".join([f"• {user_id}" for user_id in list(self.vip_users.keys())[:10]])
        if len(self.vip_users) > 10:
            vip_list += f"\n• ... 还有 {len(self.vip_users) - 10} 个用户"
        
        vip_management = f"""
<b>⭐ VIP用户管理</b>

当前VIP用户数: {vip_count}

{vip_list if vip_list else "暂无VIP用户"}

发送 <code>/vip 用户ID 天数</code> 添加VIP
发送 <code>/unvip 用户ID</code> 移除VIP
"""
        self.bot.send_message(message.chat.id, vip_management, parse_mode='HTML')
    
    # 显示日志管理
    def show_log_management(self, message):
        log_management = """
<b>📁 日志管理</b>

选择日志管理操作：
"""
        self.bot.send_message(
            message.chat.id,
            log_management,
            parse_mode='HTML',
            reply_markup=self.create_log_keyboard()
        )
    
    # 显示封禁管理
    def show_ban_management(self, message):
        ban_management = """
<b>🚫 封禁管理</b>

选择封禁管理操作：
"""
        self.bot.send_message(
            message.chat.id,
            ban_management,
            parse_mode='HTML',
            reply_markup=self.create_ban_management_keyboard()
        )
    
    # 请求封禁用户
    def request_ban_user(self, message):
        msg = self.bot.send_message(
            message.chat.id,
            "🚫 请输入要封禁的用户ID和原因（用空格分隔）：\n\n示例：<code>123456789 发布违规内容</code>",
            parse_mode='HTML'
        )
        self.bot.register_next_step_handler(msg, self.handle_ban_user)
    
    # 处理封禁用户
    def handle_ban_user(self, message):
        try:
            parts = message.text.split(' ', 1)
            if len(parts) < 2:
                self.bot.reply_to(message, "❌ 格式错误，请提供用户ID和原因")
                return
            
            user_id = int(parts[0])
            reason = parts[1]
            
            if ban_user(user_id, reason, message.from_user.id):
                self.bot.reply_to(message, f"✅ 用户 {user_id} 已被封禁\n原因: {reason}")
            else:
                self.bot.reply_to(message, f"❌ 封禁用户 {user_id} 失败")
                
        except ValueError:
            self.bot.reply_to(message, "❌ 用户ID必须是数字")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 封禁用户失败: {e}")
    
    # 请求解封用户
    def request_unban_user(self, message):
        msg = self.bot.send_message(
            message.chat.id,
            "✅ 请输入要解封的用户ID：\n\n示例：<code>123456789</code>",
            parse_mode='HTML'
        )
        self.bot.register_next_step_handler(msg, self.handle_unban_user)
    
    # 处理解封用户
    def handle_unban_user(self, message):
        try:
            user_id = int(message.text.strip())
            
            if unban_user(user_id):
                self.bot.reply_to(message, f"✅ 用户 {user_id} 已解封")
            else:
                self.bot.reply_to(message, f"❌ 解封用户 {user_id} 失败或用户未被封禁")
                
        except ValueError:
            self.bot.reply_to(message, "❌ 用户ID必须是数字")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 解封用户失败: {e}")
    
    # 显示封禁用户列表
    def show_banned_users(self, message):
        banned_users = load_banned_users()
        total_banned = len(banned_users)
        
        if total_banned == 0:
            self.bot.send_message(message.chat.id, "📋 当前没有封禁用户")
            return
        
        banned_list_text = f"""
<b>🚫 封禁用户列表</b>

总封禁用户: {total_banned}

"""
        
        for i, (user_id, ban_info) in enumerate(list(banned_users.items())[:20], 1):
            banned_time = datetime.datetime.fromisoformat(ban_info.get('banned_time', '2000-01-01'))
            reason = ban_info.get('reason', '未知原因')
            banned_by = ban_info.get('banned_by', '未知管理员')
            
            banned_list_text += f"{i}. 用户 {user_id}\n"
            banned_list_text += f"   原因: {reason}\n"
            banned_list_text += f"   封禁时间: {banned_time.strftime('%Y-%m-%d %H:%M')}\n"
            banned_list_text += f"   操作员: {banned_by}\n\n"
        
        if total_banned > 20:
            banned_list_text += f"... 还有 {total_banned - 20} 个封禁用户未显示"
        
        self.bot.send_message(message.chat.id, banned_list_text, parse_mode='HTML')

    # 请求广播消息
    def request_broadcast_message(self, message):
        msg = self.bot.send_message(
            message.chat.id,
            "📢 请输入要广播的消息内容：",
            parse_mode='HTML'
        )
        self.bot.register_next_step_handler(msg, self.handle_broadcast_message)
    
    # 处理广播消息
    def handle_broadcast_message(self, message):
        broadcast_content = message.text
        user_stats = load_user_usage_stats()
        total_users = len(user_stats)
        
        # 发送广播开始消息
        progress_msg = self.bot.send_message(
            message.chat.id,
            f"📢 开始广播消息...\n目标用户数: {total_users}\n\n发送中...",
            parse_mode='HTML'
        )
        
        success_count = 0
        fail_count = 0
        processed = 0
        
        for user_id_str in user_stats.keys():
            try:
                user_id = int(user_id_str)
                # 跳过被封禁的用户
                if is_user_banned(user_id):
                    fail_count += 1
                    processed += 1
                    continue
                
                self.bot.send_message(
                    user_id,
                    f"📢 <b>系统广播</b>\n\n{broadcast_content}",
                    parse_mode='HTML'
                )
                success_count += 1
                
                # 每发送10个用户更新一次进度
                processed += 1
                if processed % 10 == 0:
                    try:
                        self.bot.edit_message_text(
                            f"📢 广播消息发送中...\n目标用户数: {total_users}\n已处理: {processed}/{total_users}\n成功: {success_count} | 失败: {fail_count}",
                            message.chat.id,
                            progress_msg.message_id,
                            parse_mode='HTML'
                        )
                    except:
                        pass
                
                # 短暂延迟避免频繁发送
                time.sleep(0.1)
                
            except Exception as e:
                fail_count += 1
                processed += 1
                log_message(f"向用户 {user_id_str} 发送广播失败: {e}", "ERROR")
        
        # 发送广播完成消息
        result_text = f"""
📢 <b>广播完成</b>

✅ 成功发送: {success_count} 个用户
❌ 发送失败: {fail_count} 个用户
📊 成功率: {success_count/total_users*100:.1f}%

💡 失败原因可能是用户已封禁或已阻止机器人
"""
        self.bot.edit_message_text(
            result_text,
            message.chat.id,
            progress_msg.message_id,
            parse_mode='HTML'
        )
        
        log_message(f"管理员 {message.from_user.id} 发送广播消息，成功: {success_count}, 失败: {fail_count}", "BROADCAST")
    
    # 热搜管理相关功能
    def show_hot_search_list(self, message):
        top_searches = get_top_hot_searches(20)  # 显示前20名
        
        if not top_searches:
            self.bot.send_message(message.chat.id, "📋 当前热搜榜单为空")
            return
        
        hot_searches_text = "🔥 <b>热搜榜单 TOP 20</b>\n\n"
        
        for i, (keyword, count) in enumerate(top_searches, 1):
            hot_searches_text += f"{i}. <code>{keyword}</code> - {count}次\n"
        
        self.bot.send_message(message.chat.id, hot_searches_text, parse_mode='HTML')

    def request_edit_hot_search(self, message):
        msg = self.bot.send_message(
            message.chat.id,
            "✏️ 请输入要添加或修改的热搜关键词和次数（用空格分隔）：\n\n"
            "示例：<code>电影 100</code>\n"
            "⚠️ 注意：禁止包含 @ 信息和链接广告\n"
            "如需删除关键词，请将次数设为0",
            parse_mode='HTML'
        )
        self.bot.register_next_step_handler(msg, self.handle_edit_hot_search)

    def handle_edit_hot_search(self, message):
        try:
            parts = message.text.split(' ', 1)
            if len(parts) < 2:
                self.bot.reply_to(message, "❌ 格式错误，请提供关键词和次数")
                return
            
            keyword = parts[0].strip()
            count = int(parts[1])
            
            # 检查是否包含禁止内容
            if contains_advertisement(keyword):
                self.bot.reply_to(message, "❌ 热搜关键词不能包含 @ 信息、链接或广告内容")
                return
            
            hot_searches_data = load_hot_searches()
            if not hot_searches_data:
                self.bot.reply_to(message, "❌ 加载热搜数据失败")
                return
            
            if "search_counts" not in hot_searches_data:
                hot_searches_data["search_counts"] = {}
            
            if count <= 0:
                # 删除关键词
                if keyword in hot_searches_data["search_counts"]:
                    del hot_searches_data["search_counts"][keyword]
                    action = "删除"
                else:
                    self.bot.reply_to(message, f"❌ 关键词 '{keyword}' 不存在")
                    return
            else:
                # 添加或修改关键词
                hot_searches_data["search_counts"][keyword] = count
                action = "添加" if keyword not in hot_searches_data["search_counts"] else "修改"
            
            hot_searches_data["last_updated"] = datetime.datetime.now().isoformat()
            
            if save_hot_searches(hot_searches_data):
                self.bot.reply_to(message, f"✅ 已{action}热搜关键词：{keyword} - {count}次")
            else:
                self.bot.reply_to(message, "❌ 保存热搜数据失败")
                
        except ValueError:
            self.bot.reply_to(message, "❌ 次数必须是数字")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 修改热搜失败: {e}")

    def clear_hot_searches(self, message):
        try:
            hot_searches_data = {
                "last_updated": datetime.datetime.now().isoformat(),
                "search_counts": {}
            }
            
            if save_hot_searches(hot_searches_data):
                self.bot.reply_to(message, "✅ 已清空热搜榜单")
            else:
                self.bot.reply_to(message, "❌ 清空热搜榜单失败")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 清空热搜榜单失败: {e}")

    def reset_hot_search_counts(self, message):
        try:
            hot_searches_data = load_hot_searches()
            if not hot_searches_data:
                self.bot.reply_to(message, "❌ 加载热搜数据失败")
                return
            
            # 将所有关键词的计数设为1
            for keyword in hot_searches_data.get("search_counts", {}):
                hot_searches_data["search_counts"][keyword] = 1
            
            hot_searches_data["last_updated"] = datetime.datetime.now().isoformat()
            
            if save_hot_searches(hot_searches_data):
                self.bot.reply_to(message, "✅ 已重置所有热搜关键词计数为1")
            else:
                self.bot.reply_to(message, "❌ 重置热搜计数失败")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 重置热搜计数失败: {e}")

    # 数据导出功能
    def export_user_data(self, message):
        try:
            ensure_temp_dir()
            user_stats = load_user_usage_stats()
            # 直接导出源数据，不额外包装
            export_data = user_stats
            
            filename = f"user_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(TEMP_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            with open(filepath, 'rb') as f:
                self.bot.send_document(
                    message.chat.id,
                    f,
                    caption=f"📤 用户数据导出\n用户数量: {len(user_stats)}"
                )
            
            os.remove(filepath)
            
        except Exception as e:
            self.bot.reply_to(message, f"❌ 导出用户数据失败: {e}")

    def export_vip_data(self, message):
        try:
            ensure_temp_dir()
            vip_users = load_vip_users()
            # 直接导出源数据
            export_data = vip_users
            
            filename = f"vip_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(TEMP_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            with open(filepath, 'rb') as f:
                self.bot.send_document(
                    message.chat.id,
                    f,
                    caption=f"⭐ VIP数据导出\nVIP用户数量: {len(vip_users)}"
                )
            
            os.remove(filepath)
            
        except Exception as e:
            self.bot.reply_to(message, f"❌ 导出VIP数据失败: {e}")

    def export_hot_searches_data(self, message):
        try:
            ensure_temp_dir()
            hot_searches = load_hot_searches()
            # 直接导出源数据
            export_data = hot_searches
            
            filename = f"hot_searches_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(TEMP_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            with open(filepath, 'rb') as f:
                self.bot.send_document(
                    message.chat.id,
                    f,
                    caption="🔥 热搜数据导出"
                )
            
            os.remove(filepath)
            
        except Exception as e:
            self.bot.reply_to(message, f"❌ 导出热搜数据失败: {e}")

    def export_banned_users(self, message):
        try:
            ensure_temp_dir()
            banned_users = load_banned_users()
            # 直接导出源数据
            export_data = banned_users
            
            filename = f"banned_users_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(TEMP_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            with open(filepath, 'rb') as f:
                self.bot.send_document(
                    message.chat.id,
                    f,
                    caption=f"🚫 封禁列表导出\n封禁用户: {len(banned_users)}个"
                )
            
            os.remove(filepath)
            
        except Exception as e:
            self.bot.reply_to(message, f"❌ 导出封禁列表失败: {e}")
    # 用户私信功能
    def request_private_message(self, message):
        msg = self.bot.send_message(
            message.chat.id,
            "💬 请输入要发送私信的用户ID和消息内容（用空格分隔）：\n\n"
            "示例：<code>123456789 您好，这是管理员发送的私信</code>",
            parse_mode='HTML'
        )
        self.bot.register_next_step_handler(msg, self.handle_private_message)

    def handle_private_message(self, message):
        try:
            parts = message.text.split(' ', 1)
            if len(parts) < 2:
                self.bot.reply_to(message, "❌ 格式错误，请提供用户ID和消息内容")
                return
            
            user_id = int(parts[0])
            pm_content = parts[1]
            
            try:
                self.bot.send_message(
                    user_id,
                    f"💌 <b>管理员私信</b>\n\n{pm_content}",
                    parse_mode='HTML'
                )
                self.bot.reply_to(message, f"✅ 私信已发送给用户 {user_id}")
                log_message(f"管理员 {message.from_user.id} 向用户 {user_id} 发送私信", "PM")
            except Exception as e:
                self.bot.reply_to(message, f"❌ 发送私信失败: 用户可能已阻止机器人或不存在")
                
        except ValueError:
            self.bot.reply_to(message, "❌ 用户ID必须是数字")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 发送私信失败: {e}")

    def show_pm_user_list(self, message):
        user_stats = load_user_usage_stats()
        total_users = len(user_stats)
        
        # 按最后活跃时间排序
        sorted_users = sorted(
            user_stats.items(),
            key=lambda x: datetime.datetime.fromisoformat(x[1].get('last_active', '2000-01-01')),
            reverse=True
        )[:15]  # 只显示前15个用户
        
        user_list_text = f"""
<b>👤 可私信用户列表 (最近活跃的前15个)</b>

总用户数: {total_users}

"""
        
        for i, (user_id, stats) in enumerate(sorted_users, 1):
            last_active = datetime.datetime.fromisoformat(stats.get('last_active', '2000-01-01'))
            days_ago = (datetime.datetime.now() - last_active).days
            
            user_list_text += f"{i}. 用户 <code>{user_id}</code>\n"
            user_list_text += f"   最后活跃: {days_ago}天前 | 搜索: {stats.get('total_searches', 0)}次\n"
        
        user_list_text += f"\n💡 复制用户ID用于私信功能"
        
        self.bot.send_message(message.chat.id, user_list_text, parse_mode='HTML')

    # 列出所有日志文件
    def list_log_files(self, message):
        try:
            if not os.path.exists(LOG_DIR):
                self.bot.send_message(message.chat.id, "❌ 日志目录不存在")
                return
            
            log_files = [f for f in os.listdir(LOG_DIR) if f.endswith('.log')]
            log_files.sort(reverse=True)  # 按时间倒序排列
            
            if not log_files:
                self.bot.send_message(message.chat.id, "📁 暂无日志文件")
                return
            
            # 构建日志文件列表
            log_list = "<b>📋 日志文件列表</b>\n\n"
            for i, log_file in enumerate(log_files[:20], 1):  # 最多显示20个
                file_path = os.path.join(LOG_DIR, log_file)
                file_size = os.path.getsize(file_path)
                log_list += f"{i}. <code>{log_file}</code> ({file_size} bytes)\n"
            
            if len(log_files) > 20:
                log_list += f"\n... 还有 {len(log_files) - 20} 个文件未显示"
            
            log_list += "\n\n发送 <code>/log 文件名</code> 获取具体日志文件\n示例: <code>/log LOG_20241201_120000.log</code>"
            
            self.bot.send_message(message.chat.id, log_list, parse_mode='HTML')
            
        except Exception as e:
            log_message(f"列出日志文件失败: {e}", "ERROR")
            self.bot.send_message(message.chat.id, f"❌ 列出日志文件失败: {e}")
    
    # 发送当前日志文件
    def send_current_log(self, message):
        try:
            if LOG_FILEPATH and os.path.exists(LOG_FILEPATH):
                with open(LOG_FILEPATH, 'rb') as f:
                    self.bot.send_document(
                        message.chat.id,
                        f,
                        caption=f"📄 当前日志文件: {os.path.basename(LOG_FILEPATH)}"
                    )
            else:
                self.bot.send_message(message.chat.id, "❌ 当前日志文件不存在")
        except Exception as e:
            log_message(f"发送当前日志失败: {e}", "ERROR")
            self.bot.send_message(message.chat.id, f"❌ 发送日志文件失败: {e}")
    
    # 发送指定日志文件
    def send_specific_log(self, message, log_filename):
        try:
            log_path = os.path.join(LOG_DIR, log_filename)
            
            if not os.path.exists(log_path):
                self.bot.send_message(message.chat.id, f"❌ 日志文件不存在: {log_filename}")
                return
            
            # 检查文件大小，如果太大则分割发送
            file_size = os.path.getsize(log_path)
            max_size = 50 * 1024 * 1024  # 50MB Telegram限制
            
            if file_size > max_size:
                self.bot.send_message(message.chat.id, f"📁 文件过大 ({file_size} bytes)，正在分割发送...")
                self.send_large_log_file(message, log_path)
            else:
                with open(log_path, 'rb') as f:
                    self.bot.send_document(
                        message.chat.id,
                        f,
                        caption=f"📄 日志文件: {log_filename}"
                    )
                
        except Exception as e:
            log_message(f"发送指定日志失败: {e}", "ERROR")
            self.bot.send_message(message.chat.id, f"❌ 发送日志文件失败: {e}")
    
    # 发送大日志文件（分割发送）
    def send_large_log_file(self, message, log_path):
        try:
            ensure_temp_dir()
            chunk_size = 45 * 1024 * 1024
            part_num = 1
            
            with open(log_path, 'r', encoding='utf-8') as f:
                while True:
                    chunk = f.read(10 * 1024 * 1024)
                    if not chunk:
                        break
                    
                    temp_filename = f"{os.path.basename(log_path)}.part{part_num}"
                    temp_filepath = os.path.join(TEMP_DIR, temp_filename)
                    
                    with open(temp_filepath, 'w', encoding='utf-8') as temp_file:
                        temp_file.write(chunk)
                    
                    with open(temp_filepath, 'rb') as temp_file:
                        self.bot.send_document(
                            message.chat.id,
                            temp_file,
                            caption=f"📄 {os.path.basename(log_path)} 第{part_num}部分"
                        )
                    
                    os.remove(temp_filepath)
                    part_num += 1
                    
                    time.sleep(1)
            
            self.bot.send_message(message.chat.id, f"✅ 日志文件已分割为 {part_num-1} 部分发送完成")
            
        except Exception as e:
            log_message(f"发送大日志文件失败: {e}", "ERROR")
            self.bot.send_message(message.chat.id, f"❌ 发送大日志文件失败: {e}")
    
    # 重置用户限制
    def reset_user_limits(self, message):
        self.user_search_counts = {}
        save_user_search_counts(self.user_search_counts)
        self.user_random_counts = {}
        save_user_random_counts(self.user_random_counts)
        
        # 重置请求频率限制
        global USER_REQUEST_LIMITS, USER_SEARCH_PATTERNS
        USER_REQUEST_LIMITS = {}
        USER_SEARCH_PATTERNS = {}
        
        self.bot.reply_to(message, "✅ 已重置所有用户搜索、随机次数和请求频率限制")
    
    # 处理管理员文本命令
    def handle_admin_text_commands(self, message):
        if message.from_user.id not in self.ADMIN_IDS:
            return
        
        text = message.text.strip()
        
        if text.startswith("/vip "):
            self.handle_add_vip_command(message)
        elif text.startswith("/unvip "):
            self.handle_remove_vip_command(message)
        elif text.startswith("/user "):
            self.handle_user_info_command(message)
        elif text.startswith("/log "):
            self.handle_log_command(message)
    
    # 处理添加VIP命令
    def handle_add_vip_command(self, message):
        try:
            parts = message.text.split()
            if len(parts) >= 3:
                user_id = int(parts[1])
                days = int(parts[2])
                self.add_vip_user(user_id, days)
                self.bot.reply_to(message, f"✅ 已为用户 {user_id} 添加 {days} 天VIP")
            else:
                self.bot.reply_to(message, "❌ 格式错误，使用: /vip 用户ID 天数")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 添加VIP失败: {e}")
    
    # 处理移除VIP命令
    def handle_remove_vip_command(self, message):
        try:
            user_id = int(message.text.split()[1])
            user_id_str = str(user_id)
            if user_id_str in self.vip_users:
                del self.vip_users[user_id_str]
                save_vip_users(self.vip_users)
                self.bot.reply_to(message, f"✅ 已移除用户 {user_id} 的VIP权限")
            else:
                self.bot.reply_to(message, f"❌ 用户 {user_id} 不是VIP")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 移除VIP失败: {e}")
    
    # 处理用户信息命令
    def handle_user_info_command(self, message):
        try:
            user_id = int(message.text.split()[1])
            user_id_str = str(user_id)
            user_stats = load_user_usage_stats()
            
            if user_id_str not in user_stats:
                self.bot.reply_to(message, f"❌ 用户 {user_id} 不存在或未使用过机器人")
                return
            
            stats = user_stats[user_id_str]
            is_vip = self.is_vip_user(user_id)
            is_banned = is_user_banned(user_id)
            search_count = stats.get('total_searches', 0)
            first_seen = datetime.datetime.fromisoformat(stats.get('first_seen', '2000-01-01'))
            last_active = datetime.datetime.fromisoformat(stats.get('last_active', '2000-01-01'))
            
            user_info = f"""
<b>👤 用户详细信息</b>

🆔 ID: <code>{user_id}</code>
⭐ VIP状态: {'✅ 是' if is_vip else '❌ 否'}
🚫 封禁状态: {'✅ 是' if is_banned else '❌ 否'}
🔍 总搜索次数: {search_count} 次
📅 首次使用: {first_seen.strftime('%Y-%m-%d %H:%M')}
🕒 最后活跃: {last_active.strftime('%Y-%m-%d %H:%M')}
"""
            
            # 添加最近搜索关键词（最多5个）
            recent_keywords = stats.get('search_keywords', [])[-5:]
            if recent_keywords:
                user_info += "\n<b>最近搜索关键词:</b>\n"
                for keyword_data in reversed(recent_keywords):
                    keyword = keyword_data.get('keyword', '未知')
                    time_str = datetime.datetime.fromisoformat(keyword_data.get('time', '2000-01-01')).strftime('%m-%d %H:%M')
                    user_info += f"• {keyword} ({time_str})\n"
            
            self.bot.reply_to(message, user_info, parse_mode='HTML')
        except Exception as e:
            self.bot.reply_to(message, f"❌ 获取用户信息失败: {e}")
    
    # 处理日志命令
    def handle_log_command(self, message):
        try:
            parts = message.text.split()
            if len(parts) >= 2:
                log_filename = parts[1]
                self.send_specific_log(message, log_filename)
            else:
                self.bot.reply_to(message, "❌ 格式错误，使用: /log 文件名")
        except Exception as e:
            self.bot.reply_to(message, f"❌ 获取日志文件失败: {e}")
    
    # 显示帮助信息
    def show_help(self, message):
        # 检查用户是否被封禁
        if is_user_banned(message.from_user.id):
            self.bot.send_message(message.chat.id, "❌ 无权限")
            return
        
        self.bot.send_message(
            message.chat.id,
            self.HelpMessage,
            parse_mode='HTML',
            reply_markup=self.create_main_keyboard()
        )
    
    # 显示用户信息
    def show_user_info(self, message):
        # 检查用户是否被封禁
        if is_user_banned(message.from_user.id):
            self.bot.send_message(message.chat.id, "❌ 无权限")
            return
        
        user = message.from_user
        is_vip = self.is_vip_user(user.id)
        vip_status = "✅ VIP会员" if is_vip else "❌ 非VIP会员"
        remaining_time = self.get_vip_remaining_time(user.id) if is_vip else "无"
        search_count = self.user_search_counts.get(str(user.id), 0)
        remaining_searches = 10 - search_count if not is_vip else "无限制"
        
        user_info = f"""
<b>👤 用户信息</b>

🆔 ID: <code>{user.id}</code>
👤 姓名: {user.first_name or '未设置'}
📛 用户名: @{user.username or '未设置'}
⭐ VIP状态: {vip_status}
⏰ VIP剩余: {remaining_time}
🔍 今日搜索: {search_count} 次
📄 剩余搜索: {remaining_searches} 次
"""
        self.bot.send_message(
            message.chat.id,
            user_info,
            parse_mode='HTML',
            reply_markup=self.create_main_keyboard()
        )
    
    # 清理过期的搜索会话
    def cleanup_old_sessions(self):
        current_time = datetime.datetime.now()
        expired_sessions = []
        
        for search_id, session in self.user_search_sessions.items():
            # 如果会话创建时间超过1小时，则标记为过期
            if (current_time - session['created_time']).total_seconds() > 3600:
                expired_sessions.append(search_id)
        
        for search_id in expired_sessions:
            del self.user_search_sessions[search_id]
        
        if expired_sessions:
            log_message(f"清理了 {len(expired_sessions)} 个过期搜索会话", "CLEANUP")
        
        # 清理过期的频率记录
        cleanup_old_frequency_records()
    
    # 安全的处理器装饰器
    def safe_handler(self, handler_func):
        def wrapper(message):
            try:
                # 检查请求频率（传入消息内容）
                can_request, reason = check_request_frequency(
                    message.from_user.id, 
                    message.text
                )
                
                if not can_request:
                    # 发送频繁请求警告给管理员
                    user_nickname = get_user_display_name(message.from_user)
                    warning_msg = f"🚨 频繁请求警告\n用户ID: {message.from_user.id}\n昵称: {user_nickname}\n请求内容: {message.text}\n限制原因: {reason}\n时间: {get_current_time()}"
                    
                    # 发送警告给所有管理员
                    for admin_id in self.ADMIN_IDS:
                        try:
                            self.bot.send_message(admin_id, warning_msg)
                        except Exception as e:
                            log_message(f"向管理员 {admin_id} 发送频繁请求警告失败: {e}", "ERROR")
                    
                    log_message(f"用户 {message.from_user.id} 频繁请求被限制，原因: {reason}, 内容: {message.text}", "FREQUENCY_LIMIT")
                    
                    # 根据原因返回不同的提示信息
                    if reason == "相同内容":
                        self.bot.reply_to(message, f"⏳ 相同内容搜索过于频繁，请等待 {BUFFER_TIME} 秒后再试")
                    elif reason == "频繁请求":
                        self.bot.reply_to(message, f"⏳ 请求过于频繁，请等待 {BUFFER_TIME} 秒后再试")
                    else:
                        self.bot.reply_to(message, f"⏳ 系统繁忙，请等待 {BUFFER_TIME} 秒后再试")
                    return
                
                return handler_func(message)
            except Exception as e:
                log_message(f"处理消息时出错 (用户: {message.from_user.id}, 内容: {message.text}): {e}", "ERROR")
                try:
                    self.bot.reply_to(message, "❌ 处理消息时出现错误，请稍后重试")
                except:
                    pass
        return wrapper
    
    # 安全回调处理器装饰器
    def safe_callback_handler(self, handler_func):
        def wrapper(call):
            try:
                # 检查请求频率（传入回调数据）
                can_request, reason = check_request_frequency(
                    call.from_user.id, 
                    call.data
                )
                
                if not can_request:
                    # 发送频繁请求警告给管理员
                    user_nickname = get_user_display_name(call.from_user)
                    warning_msg = f"🚨 频繁请求警告\n用户ID: {call.from_user.id}\n昵称: {user_nickname}\n回调数据: {call.data}\n限制原因: {reason}\n时间: {get_current_time()}"
                    
                    # 发送警告给所有管理员
                    for admin_id in self.ADMIN_IDS:
                        try:
                            self.bot.send_message(admin_id, warning_msg)
                        except Exception as e:
                            log_message(f"向管理员 {admin_id} 发送频繁请求警告失败: {e}", "ERROR")
                    
                    log_message(f"用户 {call.from_user.id} 频繁回调请求被限制，原因: {reason}, 数据: {call.data}", "FREQUENCY_LIMIT")
                    self.bot.answer_callback_query(call.id, f"⏳ 请求过于频繁，请等待 {BUFFER_TIME} 秒")
                    return
                
                return handler_func(call)
            except Exception as e:
                log_message(f"处理回调时出错 (用户: {call.from_user.id}, 数据: {call.data}): {e}", "ERROR")
                try:
                    self.bot.answer_callback_query(call.id, "❌ 操作失败，请重试")
                except:
                    pass
        return wrapper
    
    # 设置消息处理器
    def setup_handlers(self):
        # 处理 /start 命令
        @self.bot.message_handler(commands=["start"])
        @self.safe_handler
        def start(message):
            self.start_(message)
        
        # 处理 /admin 命令 - 放在安全检测之前
        @self.bot.message_handler(commands=["admin"])
        @self.safe_handler
        def admin(message):
            self.handle_admin_command(message)
        
        # 处理"使用协议"关键词
        @self.bot.message_handler(regexp=r"^使用协议$")
        @self.safe_handler
        def ShowUserAgreement(message):
            self.ShowUserAgreement_(message)
        
        # 处理搜索命令
        @self.bot.message_handler(regexp=r'^搜索\s+.+')
        @self.safe_handler
        def handle_search_command(message):
            self.handle_search(message)
        
        # 处理主菜单按钮
        @self.bot.message_handler(func=lambda message: message.text in [
            "📜 使用协议", "ℹ️ 帮助信息", "👤 我的信息", "⭐ VIP服务", "🎲 全库随机", "🔥 热搜榜单"
        ])
        @self.safe_handler
        def handle_main_menu(message):
            if message.text == "📜 使用协议":
                self.ShowUserAgreement_(message)
            elif message.text == "ℹ️ 帮助信息":
                self.show_help(message)
            elif message.text == "👤 我的信息":
                self.show_user_info(message)
            elif message.text == "⭐ VIP服务":
                self.handle_vip_service(message)
            elif message.text == "🎲 全库随机":
                self.handle_random_search(message)
            elif message.text == "🔥 热搜榜单":
                self.handle_hot_searches(message)
        
        # 处理管理员功能按钮
        @self.bot.message_handler(func=lambda message: message.text in [
            "📊 统计信息", "👥 用户管理", "⭐ VIP管理", "📁 日志管理", "🔄 重置限制", 
            "📢 广播消息", "🚫 封禁管理", "🔥 热搜榜单管理", "📤 数据导出", "💬 用户私信", "🏠 返回主菜单"
        ])
        @self.safe_handler
        def handle_admin_buttons(message):
            self.handle_admin_functions(message)
        
        # 处理管理员文本命令
        @self.bot.message_handler(func=lambda message: message.text.startswith(('/vip ', '/unvip ', '/user ', '/log ')))
        @self.safe_handler
        def handle_admin_text(message):
            self.handle_admin_text_commands(message)
        
        # 安全检测：监控非管理员用户尝试使用管理员命令
        @self.bot.message_handler(func=lambda message: any(message.text.startswith(cmd) for cmd in ['/vip', '/user', '/log']))
        @self.safe_handler
        def handle_admin_commands_security(message):
            """
            安全检测：监控非管理员用户尝试使用管理员命令
            当普通用户尝试使用管理员专属命令时，立即向所有管理员发送安全警报
            """
            # 检查用户身份，如果是管理员则放行
            if message.from_user.id in self.ADMIN_IDS:
                return  # 管理员正常使用命令，不触发警报
            
            # 获取用户昵称用于识别
            user_nickname = get_user_display_name(message.from_user)
            
            # 构建安全警报消息
            security_alert = f"""
    🚨 <b>安全警报 - 管理员命令尝试</b>

    🆔 <b>用户ID:</b> <code>{message.from_user.id}</code>
    👤 <b>用户昵称:</b> {user_nickname}
    📝 <b>尝试命令:</b> <code>{message.text}</code>
    ⏰ <b>时间:</b> {get_current_time()}

    ⚠️ <b>警报:</b> 该用户正在尝试使用管理员命令！
    """
            
            # 向所有管理员发送安全警报
            for admin_id in self.ADMIN_IDS:
                try:
                    self.bot.send_message(admin_id, security_alert, parse_mode='HTML')
                    log_message(f"向管理员 {admin_id} 发送安全警报: 用户 {message.from_user.id} 尝试使用命令 {message.text}", "SECURITY")
                except Exception as e:
                    log_message(f"向管理员 {admin_id} 发送安全警报失败: {e}", "ERROR")
            
            # 记录安全事件到日志
            log_message(f"非管理员用户 {message.from_user.id} ({user_nickname}) 尝试使用管理员命令: {message.text}", "SECURITY")
            
            # 给用户回复无权限消息
            self.bot.reply_to(message, "❌ 无权限执行此命令")
        
        # 处理分页回调
        @self.bot.callback_query_handler(func=lambda call: True)
        @self.safe_callback_handler
        def handle_callback(call):
            self.handle_pagination_callback(call)
        
        # 处理所有其他消息
        @self.bot.message_handler(func=lambda message: True)
        @self.safe_handler
        def search(message):
            self.handle_search(message)
    
    # 运行机器人主循环
    def run(self):
        # 检查Token是否有效
        if not self.BOT_TOKEN:
            log_message("未找到 TELEGRAM_BOT_TOKEN 环境变量", "ERROR")
            return
        
        # 无限重试机制
        retry_delay = 30  # 初始重试延迟（秒）
        max_retry_delay = 300  # 最大重试延迟（5分钟）
        
        while True:
            try:
                # 创建Telegram机器人实例
                self.bot = telebot.TeleBot(self.BOT_TOKEN)
                log_message("机器人初始化成功", "OK")
                
                # 设置消息处理器
                self.setup_handlers()
                
                # 开始机器人轮询
                log_message("机器人开始运行...", "START")
                
                # 设置更宽松的异常处理
                self.bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
                
                # 如果polling正常返回，重置重试延迟
                retry_delay = 30
                log_message("机器人轮询正常结束，重新启动...", "RESTART")
                
            except KeyboardInterrupt:
                log_message("程序被用户中断", "INFO")
                break
            except Exception as e:
                log_message(f"机器人运行出错: {e}", "ERROR")
                log_message(f"{retry_delay}秒后重试...", "RETRY")
                
                try:
                    time.sleep(retry_delay)
                    
                    # 指数退避策略，但设置上限
                    retry_delay = min(retry_delay * 1.5, max_retry_delay)
                    
                except KeyboardInterrupt:
                    log_message("程序被用户中断", "INFO")
                    break
                except Exception as sleep_error:
                    log_message(f"重试等待时出错: {sleep_error}", "ERROR")
                    
            # 定期清理会话（即使在运行中也执行）
            try:
                self.cleanup_old_sessions()
            except Exception as e:
                log_message(f"清理会话时出错: {e}", "ERROR")

# MAIN 程序入口点
if __name__ == "__main__":
    try:
        # 确保数据目录存在
        ensure_data_dir()
        ensure_log_dir()
        ensure_temp_dir()
        
        # 创建机器人实例
        bot_instance = TelegramBot()
        # 初始化数据库
        bot_instance.initDataBase()
        # 启动机器人（内部已包含无限重试）
        bot_instance.run()
    except KeyboardInterrupt:
        log_message("程序被用户中断", "INFO")
    except Exception as e:
        log_message(f"程序启动时发生致命错误: {e}", "FATAL")
        # 即使启动失败也尝试重新启动
        time.sleep(60)
        # 重新启动程序
        os.execv(sys.executable, [sys.executable] + sys.argv)