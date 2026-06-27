import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import logging
import threading
import re
import sys
import atexit
import requests
import random
import string
from flask import Flask
from threading import Thread
import hashlib
import platform
import socket
import json
import signal
import traceback
from functools import wraps
import cachetools
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

# ============================================
# FLASK KEEP ALIVE
# ============================================

app = Flask('')

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>☁️ MrlDi CLOUD - Premium Free Hosting</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
                .container { max-width: 800px; margin: 0 auto; padding: 20px; background: rgba(255,255,255,0.1); border-radius: 10px; }
                h1 { font-size: 3em; }
                .status { display: inline-block; padding: 10px 20px; background: #4CAF50; border-radius: 5px; }
                .stats { margin-top: 20px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
                .stat { padding: 15px; background: rgba(255,255,255,0.2); border-radius: 5px; text-align: center; }
                .stat-value { font-size: 2em; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>☁️ MrlDi CLOUD</h1>
                <p>Premium Free Hosting Environment</p>
                <div class="status">🟢 ONLINE</div>
                <div class="stats">
                    <div class="stat"><div class="stat-value" id="users">-</div><div>Users</div></div>
                    <div class="stat"><div class="stat-value" id="files">-</div><div>Files</div></div>
                    <div class="stat"><div class="stat-value" id="uptime">-</div><div>Uptime</div></div>
                </div>
            </div>
            <script>
                setInterval(() => {
                    fetch('/stats').then(r => r.json()).then(data => {
                        document.getElementById('users').textContent = data.users;
                        document.getElementById('files').textContent = data.files;
                        document.getElementById('uptime').textContent = data.uptime;
                    });
                }, 5000);
            </script>
        </body>
    </html>
    """

@app.route('/stats')
def stats():
    try:
        return {
            'users': len(active_users),
            'files': sum(len(files) for files in user_files.values()),
            'uptime': str(timedelta(seconds=int(time.time() - start_time)))
        }
    except:
        return {'users': 0, 'files': 0, 'uptime': '0:00:00'}

@app.route('/health')
def health():
    return {'status': 'healthy', 'timestamp': time.time()}

def run_flask():
    try:
        app.run(host='0.0.0.0', port=8081, threaded=True)
    except Exception as e:
        logger.error(f"Flask error: {e}")

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("☁️ Cloud Keep-Alive started on port 8081")

# ============================================
# CONFIGURATION
# ============================================

BOT_TOKEN = "8959475720:AAFGEfM68752iZik6Qxza4qAO08owpLeRnQ"
OWNER_ID = 8915316853
ADMIN_ID = 8915316853
YOUR_USERNAME = "@MrlDi"

FORCE_CHANNEL_ID = -1003958551428
FORCE_GROUP_ID = -1003728099410
FORCE_CHANNEL_LINK = 'https://t.me/+zYo2ub7wsR02YmVl'
FORCE_GROUP_LINK = 'https://t.me/+O_idrjacT2M2Nl'

try:
    OWNER_ID = int(OWNER_ID)
    ADMIN_ID = int(ADMIN_ID)
    FORCE_CHANNEL_ID = int(FORCE_CHANNEL_ID)
    FORCE_GROUP_ID = int(FORCE_GROUP_ID)
except ValueError:
    raise ValueError("❌ IDs must be numbers!")

# Directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'MrlDi_uploads')
MrlDi_DIR = os.path.join(BASE_DIR, 'MrlDi_data')
DATABASE_PATH = os.path.join(MrlDi_DIR, 'MrlDi_host.db')
BACKUP_DIR = os.path.join(MrlDi_DIR, 'backups')
LOGS_DIR = os.path.join(MrlDi_DIR, 'logs')
TEMP_DIR = os.path.join(MrlDi_DIR, 'temp')
CACHE_DIR = os.path.join(MrlDi_DIR, 'cache')

for dir_path in [UPLOAD_BOTS_DIR, MrlDi_DIR, BACKUP_DIR, LOGS_DIR, TEMP_DIR, CACHE_DIR]:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except:
        pass

# Limits
FREE_USER_LIMIT = 10
ADMIN_LIMIT = 999
OWNER_LIMIT = float('inf')
MAX_WARNINGS = 3
MAX_FILE_SIZE = 100 * 1024 * 1024

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Data structures
bot_scripts = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
user_warnings = {}
user_ratelimit = {}
bot_locked = False
force_join_enabled = True
start_time = time.time()

# ============================================
# PENDING FILES SYSTEM
# ============================================

pending_files = {}
approved_files = set()

# ============================================
# BAN SYSTEM
# ============================================

banned_users = set()
banned_users_info = {}

# Thread pools
executor = ThreadPoolExecutor(max_workers=20)
cleanup_queue = Queue()

# Cache
cache = cachetools.TTLCache(maxsize=200, ttl=600)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Stats
stats = {
    'total_scans': 0,
    'approved_files': 0,
    'declined_files': 0,
    'warnings_given': 0,
    'banned_users': 0,
    'total_uploads': 0,
    'total_running': 0,
    'auto_installs': 0
}

# Supported extensions
SUPPORTED_EXTENSIONS = {
    '.py': 'Python', '.java': 'Java', '.html': 'HTML', '.htm': 'HTML',
    '.js': 'JavaScript', '.css': 'CSS', '.txt': 'Text', '.json': 'JSON',
    '.xml': 'XML', '.php': 'PHP', '.c': 'C', '.cpp': 'C++', '.cs': 'C#',
    '.rb': 'Ruby', '.go': 'Go', '.rs': 'Rust', '.md': 'Markdown',
    '.yaml': 'YAML', '.yml': 'YAML', '.sql': 'SQL', '.sh': 'Shell',
    '.bat': 'Batch', '.ps1': 'PowerShell', '.r': 'R', '.swift': 'Swift',
    '.kt': 'Kotlin', '.scala': 'Scala', '.pl': 'Perl', '.lua': 'Lua',
    '.ts': 'TypeScript', '.jsx': 'React JSX', '.tsx': 'React TSX',
    '.vue': 'Vue', '.svelte': 'Svelte', '.dart': 'Dart',
    '.dockerfile': 'Dockerfile', '.tf': 'Terraform'
}

# ============================================
# NODE.JS AUTO INSTALL
# ============================================

def check_node_installed():
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def get_node_version():
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None

def install_nodejs():
    try:
        logger.info("🔄 Attempting to install Node.js...")
        system = platform.system().lower()
        
        if system == 'linux':
            try:
                subprocess.run(['curl', '-fsSL', 'https://deb.nodesource.com/setup_18.x', '-o', '/tmp/node_setup.sh'], 
                              capture_output=True, timeout=30)
                subprocess.run(['bash', '/tmp/node_setup.sh'], capture_output=True, timeout=60)
                subprocess.run(['apt-get', 'install', '-y', 'nodejs'], capture_output=True, timeout=120)
                os.remove('/tmp/node_setup.sh')
                logger.info("✅ Node.js installed via NodeSource")
                return True
            except:
                pass
            try:
                subprocess.run(['snap', 'install', 'node', '--classic'], capture_output=True, timeout=120)
                logger.info("✅ Node.js installed via snap")
                return True
            except:
                pass
            try:
                subprocess.run(['curl', '-o-', 'https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh', '|', 'bash'], 
                              shell=True, capture_output=True, timeout=60)
                subprocess.run(['bash', '-c', 'source ~/.nvm/nvm.sh && nvm install 18 && nvm use 18'], 
                              shell=True, capture_output=True, timeout=120)
                logger.info("✅ Node.js installed via nvm")
                return True
            except:
                pass
        elif system == 'darwin':
            try:
                subprocess.run(['brew', 'install', 'node'], capture_output=True, timeout=120)
                logger.info("✅ Node.js installed via Homebrew")
                return True
            except:
                pass
        elif system == 'windows':
            try:
                subprocess.run(['winget', 'install', 'OpenJS.NodeJS'], capture_output=True, timeout=120)
                logger.info("✅ Node.js installed via winget")
                return True
            except:
                pass
            try:
                subprocess.run(['choco', 'install', 'nodejs', '-y'], capture_output=True, timeout=120)
                logger.info("✅ Node.js installed via Chocolatey")
                return True
            except:
                pass
        
        logger.warning("⚠️ Node.js installation failed")
        return False
    except Exception as e:
        logger.error(f"❌ Node.js installation error: {e}")
        return False

def ensure_nodejs():
    if not check_node_installed():
        logger.info("📦 Node.js not found, installing...")
        success = install_nodejs()
        if success:
            stats['auto_installs'] += 1
            return True
        return False
    node_version = get_node_version()
    logger.info(f"✅ Node.js installed: {node_version}")
    return True

# ============================================
# DATABASE FUNCTIONS
# ============================================

DB_LOCK = threading.Lock()

def init_db():
    """Initialize database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP,
            total_uploads INTEGER DEFAULT 0,
            storage_used INTEGER DEFAULT 0,
            language TEXT DEFAULT 'en'
        )''')
        
        # Active users table
        c.execute('''CREATE TABLE IF NOT EXISTS active_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Files table
        c.execute('''CREATE TABLE IF NOT EXISTS user_files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            chat_id INTEGER,
            file_name TEXT,
            file_type TEXT,
            file_path TEXT,
            original_filename TEXT,
            file_size INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            is_pending INTEGER DEFAULT 0,
            downloads INTEGER DEFAULT 0,
            checksum TEXT,
            version INTEGER DEFAULT 1
        )''')
        
        # Admins table
        c.execute('''CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'admin',
            added_by INTEGER,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Banned users table
        c.execute('''CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            banned_by INTEGER,
            ban_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT
        )''')
        
        # Pending files table
        c.execute('''CREATE TABLE IF NOT EXISTS pending_files (
            file_id TEXT PRIMARY KEY,
            user_id INTEGER,
            file_name TEXT,
            file_type TEXT,
            file_path TEXT,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )''')
        
        # Security logs table
        c.execute('''CREATE TABLE IF NOT EXISTS security_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            file_name TEXT,
            action TEXT,
            log_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            ip_address TEXT
        )''')
        
        # Settings table
        c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT,
            updated_by INTEGER,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Insert default settings
        default_settings = [
            ('free_user_limit', str(FREE_USER_LIMIT)),
            ('force_join_enabled', '1'),
            ('bot_version', '4.0.0'),
            ('maintenance_mode', '0')
        ]
        
        for key, value in default_settings:
            c.execute('INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)',
                     (key, value))
        
        # Insert owner/admin
        c.execute('INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, ?)', (OWNER_ID, 'owner'))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, ?)', (ADMIN_ID, 'admin'))
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return False

def upgrade_database():
    """Upgrade existing database with new columns"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Check if active_users table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='active_users'")
        if not c.fetchone():
            c.execute('''CREATE TABLE active_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            logger.info("✅ Created active_users table")
        
        # Check if checksum column exists in user_files
        c.execute("PRAGMA table_info(user_files)")
        columns = [col[1] for col in c.fetchall()]
        if 'checksum' not in columns:
            c.execute('ALTER TABLE user_files ADD COLUMN checksum TEXT')
            logger.info("✅ Added checksum column to user_files")
        
        # Check if ip_address column exists in security_logs
        c.execute("PRAGMA table_info(security_logs)")
        columns = [col[1] for col in c.fetchall()]
        if 'ip_address' not in columns:
            c.execute('ALTER TABLE security_logs ADD COLUMN ip_address TEXT')
            logger.info("✅ Added ip_address column to security_logs")
        
        conn.commit()
        conn.close()
        logger.info("✅ Database upgrade completed")
        return True
    except Exception as e:
        logger.error(f"❌ Database upgrade error: {e}")
        return False

def load_data():
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Load files
        c.execute('SELECT user_id, file_name, file_type, file_path FROM user_files WHERE is_pending = 0')
        for user_id, file_name, file_type, file_path in c.fetchall():
            try:
                if user_id not in user_files:
                    user_files[user_id] = []
                user_files[user_id].append((file_name, file_type, file_path))
            except:
                pass
        
        # Load active users
        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())
        
        # Load banned users
        c.execute('SELECT user_id, username, first_name, banned_by, ban_time, reason FROM banned_users')
        for user_id, username, first_name, banned_by, ban_time, reason in c.fetchall():
            banned_users.add(user_id)
            banned_users_info[user_id] = {
                'username': username,
                'first_name': first_name,
                'banned_by': banned_by,
                'ban_time': datetime.fromisoformat(ban_time) if ban_time else datetime.now(),
                'reason': reason
            }
        
        # Load pending files
        c.execute('SELECT file_id, user_id, file_name, file_type, file_path, upload_time FROM pending_files WHERE status = "pending"')
        for file_id, user_id, file_name, file_type, file_path, upload_time in c.fetchall():
            pending_files[file_id] = {
                'user_id': user_id,
                'file_name': file_name,
                'file_type': file_type,
                'file_path': file_path,
                'upload_time': datetime.fromisoformat(upload_time) if upload_time else datetime.now()
            }
        
        c.execute('SELECT COUNT(*) FROM banned_users')
        stats['banned_users'] = c.fetchone()[0] or 0
        
        c.execute('SELECT setting_key, setting_value FROM bot_settings')
        for key, value in c.fetchall():
            try:
                if key == 'free_user_limit':
                    global FREE_USER_LIMIT
                    FREE_USER_LIMIT = int(value)
                elif key == 'force_join_enabled':
                    global force_join_enabled
                    force_join_enabled = value == '1'
            except:
                pass
        
        conn.close()
        logger.info(f"📊 Data loaded: {len(active_users)} users, {sum(len(files) for files in user_files.values())} files, {len(pending_files)} pending")
        return True
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")
        return False

def save_user(user_id, username, first_name, last_name):
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO users 
                        (user_id, username, first_name, last_name, last_active)
                        VALUES (?, ?, ?, ?, ?)''',
                      (user_id, username or '', first_name or '', last_name or '', datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error saving user: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def save_user_file(user_id, file_name, file_type, file_path, pending=False):
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            checksum = hashlib.sha256(open(file_path, 'rb').read()).hexdigest() if os.path.exists(file_path) else ''
            
            c.execute('''INSERT OR REPLACE INTO user_files 
                        (user_id, chat_id, file_name, file_type, file_path, 
                         original_filename, file_size, is_pending, checksum)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (user_id, user_id, file_name, file_type, file_path,
                      file_name, file_size, 1 if pending else 0, checksum))
            
            c.execute('UPDATE users SET total_uploads = total_uploads + 1, storage_used = storage_used + ? WHERE user_id = ?',
                     (file_size, user_id))
            
            conn.commit()
            
            if not pending:
                if user_id not in user_files:
                    user_files[user_id] = []
                user_files[user_id] = [(fn, ft, fp) for fn, ft, fp in user_files[user_id] if fn != file_name]
                user_files[user_id].append((file_name, file_type, file_path))
                logger.info(f"✅ Added to user_files: {file_name} for user {user_id}")
            
            stats['total_uploads'] += 1
            logger.info(f"✅ File saved: {file_name} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving file: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            
            c.execute('SELECT file_size, file_path FROM user_files WHERE user_id = ? AND file_name = ?',
                     (user_id, file_name))
            result = c.fetchone()
            file_size = result[0] if result else 0
            
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            
            if file_size > 0:
                c.execute('UPDATE users SET storage_used = storage_used - ? WHERE user_id = ?',
                         (file_size, user_id))
            
            conn.commit()
            
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]:
                    del user_files[user_id]
            
            return True
        except Exception as e:
            logger.error(f"❌ Error removing file: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def add_active_user(user_id):
    active_users.add(user_id)
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
            return True
        except:
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def log_security_event(user_id, username, file_name, action, details=None, ip=None):
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''INSERT INTO security_logs 
                     (user_id, username, file_name, action, details, ip_address)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user_id, username or '', file_name or '', action, details or '', ip or ''))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Error logging security event: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def refresh_user_files_from_db(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        c.execute('SELECT file_name, file_type, file_path FROM user_files WHERE user_id = ? AND is_pending = 0', (user_id,))
        files = c.fetchall()
        
        if user_id in user_files:
            del user_files[user_id]
        
        if files:
            user_files[user_id] = [(fn, ft, fp) for fn, ft, fp in files]
        
        conn.close()
        logger.info(f"🔄 Refreshed files for user {user_id}: {len(files)} files")
        return True
    except Exception as e:
        logger.error(f"❌ Error refreshing files: {e}")
        return False

# ============================================
# PENDING FILE FUNCTIONS
# ============================================

def save_pending_file(file_id, user_id, file_name, file_type, file_path):
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            upload_time = datetime.now()
            c.execute('''INSERT INTO pending_files 
                        (file_id, user_id, file_name, file_type, file_path, upload_time, status) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (file_id, user_id, file_name, file_type, file_path, upload_time.isoformat(), 'pending'))
            conn.commit()
            
            pending_files[file_id] = {
                'user_id': user_id,
                'file_name': file_name,
                'file_path': file_path,
                'file_type': file_type,
                'upload_time': upload_time
            }
            
            return True
        except Exception as e:
            logger.error(f"Error saving pending file: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def update_pending_file_status(file_id, status):
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('UPDATE pending_files SET status = ? WHERE file_id = ?', (status, file_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating pending file: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def get_pending_files_count():
    return len(pending_files)

def get_all_pending_files():
    return pending_files.copy()

def notify_admins_about_pending_file(user_id, file_name, file_type, file_id):
    user_info = f"User ID: {user_id}"
    try:
        chat = bot.get_chat(user_id)
        if chat.username:
            user_info += f"\nUsername: @{chat.username}"
        if chat.first_name:
            user_info += f"\nName: {chat.first_name}"
    except:
        pass
    
    message = (f"🔔 New File Pending Approval\n\n"
               f"📁 File: {file_name}\n"
               f"📊 Type: {file_type}\n"
               f"👤 {user_info}\n\n"
               f"Please review and approve/reject.")
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_file_{file_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_file_{file_id}")
    )
    markup.add(types.InlineKeyboardButton("👤 User Info", callback_data=f"user_info_{user_id}"))
    
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, message, reply_markup=markup)
        except:
            pass

# ============================================
# APPROVE FILE FUNCTION
# ============================================

def approve_file(file_id, admin_id):
    if file_id not in pending_files:
        return False, "File not found"
    
    file_info = pending_files[file_id]
    user_id = file_info['user_id']
    file_name = file_info['file_name']
    file_type = file_info['file_type']
    pending_path = file_info['file_path']
    
    try:
        user_folder = get_user_folder(user_id)
        final_path = os.path.join(user_folder, file_name)
        
        if os.path.exists(pending_path):
            shutil.move(pending_path, final_path)
        else:
            return False, "File missing"
        
        save_user_file(user_id, file_name, file_type, final_path, pending=False)
        
        if file_id in pending_files:
            del pending_files[file_id]
        update_pending_file_status(file_id, 'approved')
        stats['approved_files'] += 1
        
        refresh_user_files_from_db(user_id)
        
        if file_type == 'py' or file_name.endswith('.py'):
            threading.Thread(target=run_script,
                           args=(final_path, user_id, user_folder, file_name, None), daemon=True).start()
        else:
            threading.Thread(target=run_js_script,
                           args=(final_path, user_id, user_folder, file_name, None), daemon=True).start()
        
        try:
            bot.send_message(user_id, f"✅ Your file '{file_name}' has been approved and is now running!")
        except:
            pass
        
        log_security_event(user_id, None, file_name, 'approved', f"Approved by admin {admin_id}")
        
        logger.info(f"✅ File approved: {file_name} for user {user_id}")
        logger.info(f"📂 User {user_id} files after approval: {user_files.get(user_id, [])}")
        
        return True, "File approved and started"
        
    except Exception as e:
        logger.error(f"Error approving file: {e}")
        return False, str(e)

def reject_file(file_id, admin_id, reason=None):
    if file_id not in pending_files:
        return False, "File not found"
    
    file_info = pending_files[file_id]
    user_id = file_info['user_id']
    file_name = file_info['file_name']
    pending_path = file_info['file_path']
    
    try:
        if os.path.exists(pending_path):
            os.remove(pending_path)
        
        if file_id in pending_files:
            del pending_files[file_id]
        update_pending_file_status(file_id, 'rejected')
        stats['declined_files'] += 1
        
        reason_text = f"\nReason: {reason}" if reason else ""
        try:
            bot.send_message(user_id, f"❌ Your file '{file_name}' was rejected.{reason_text}")
        except:
            pass
        
        log_security_event(user_id, None, file_name, 'rejected', f"Rejected by admin {admin_id}. Reason: {reason}")
        
        return True, "File rejected"
        
    except Exception as e:
        logger.error(f"Error rejecting file: {e}")
        return False, str(e)

# ============================================
# BAN SYSTEM FUNCTIONS
# ============================================

def is_user_banned(user_id):
    return user_id in banned_users

def ban_user(admin_id, target_id, username=None, first_name=None, reason=None):
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            ban_time = datetime.now()
            
            if username is None or first_name is None:
                try:
                    chat = bot.get_chat(target_id)
                    username = chat.username
                    first_name = chat.first_name
                except:
                    pass
            
            c.execute('''INSERT OR REPLACE INTO banned_users 
                        (user_id, username, first_name, banned_by, ban_time, reason) 
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (target_id, username, first_name, admin_id, ban_time.isoformat(), reason))
            conn.commit()
            
            banned_users.add(target_id)
            banned_users_info[target_id] = {
                'username': username,
                'first_name': first_name,
                'banned_by': admin_id,
                'ban_time': ban_time,
                'reason': reason
            }
            
            active_users.discard(target_id)
            stats['banned_users'] += 1
            
            cleanup_user_processes(target_id)
            
            logger.info(f"User {target_id} banned by {admin_id}")
            return True
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def unban_user(admin_id, target_id):
    with DB_LOCK:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('DELETE FROM banned_users WHERE user_id = ?', (target_id,))
            conn.commit()
            removed = c.rowcount > 0
            
            if removed:
                banned_users.discard(target_id)
                if target_id in banned_users_info:
                    del banned_users_info[target_id]
                stats['banned_users'] -= 1
                logger.info(f"User {target_id} unbanned by {admin_id}")
            
            return removed
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def get_banned_users():
    return banned_users_info.copy()

# ============================================
# UTILITY FUNCTIONS
# ============================================

def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {size_names[i]}"

def get_user_file_limit(user_id):
    if user_id == OWNER_ID:
        return OWNER_LIMIT
    if user_id in admin_ids:
        return ADMIN_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def get_user_status(user_id):
    if user_id == OWNER_ID:
        return "👑 System Owner"
    if user_id in admin_ids:
        return "🛡️ Administrator"
    return "👤 Free User"

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    try:
        os.makedirs(user_folder, exist_ok=True)
    except:
        pass
    return user_folder

def check_force_join(user_id):
    if user_id in admin_ids:
        return True
    if not force_join_enabled:
        return True
    if is_user_banned(user_id):
        return False
    try:
        member = bot.get_chat_member(FORCE_GROUP_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def is_rate_limited(user_id):
    now = time.time()
    if user_id not in user_ratelimit:
        user_ratelimit[user_id] = []
    
    user_ratelimit[user_id] = [t for t in user_ratelimit[user_id] if now - t < 10]
    
    if len(user_ratelimit[user_id]) >= 5:
        return True
    
    user_ratelimit[user_id].append(now)
    return False

# ============================================
# PROCESS MANAGEMENT
# ============================================

def is_bot_running(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
    return False

def kill_process_tree(process_info):
    try:
        process = process_info.get('process')
        if process and hasattr(process, 'pid'):
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except:
                        pass
                time.sleep(1)
                for child in children:
                    try:
                        if child.is_running():
                            child.kill()
                    except:
                        pass
                parent.terminate()
                parent.wait(timeout=5)
                if parent.is_running():
                    parent.kill()
            except:
                pass
            if process.poll() is None:
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
        return True
    except Exception as e:
        logger.error(f"❌ Error killing process: {e}")
        return False

def force_cleanup_process(process_info):
    try:
        kill_process_tree(process_info)
        return True
    except:
        return False

def cleanup_user_processes(user_id):
    keys_to_remove = []
    for script_key, process_info in list(bot_scripts.items()):
        if script_key.startswith(f"{user_id}_"):
            force_cleanup_process(process_info)
            keys_to_remove.append(script_key)
    for key in keys_to_remove:
        if key in bot_scripts:
            del bot_scripts[key]
    return len(keys_to_remove)

def cleanup_zombie_processes():
    for script_key in list(bot_scripts.keys()):
        try:
            script_info = bot_scripts.get(script_key)
            if script_info and script_info.get('process'):
                try:
                    proc = psutil.Process(script_info['process'].pid)
                    if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                        if script_key in bot_scripts:
                            del bot_scripts[script_key]
                except psutil.NoSuchProcess:
                    if script_key in bot_scripts:
                        del bot_scripts[script_key]
        except:
            pass

# ============================================
# SCRIPT EXECUTION
# ============================================

def auto_install_pip_packages(script_path, user_folder):
    try:
        if not os.path.exists(script_path):
            return False
        
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        import_pattern = re.compile(r'^(?:from|import)\s+([a-zA-Z0-9_]+)', re.MULTILINE)
        imports = import_pattern.findall(content)
        
        builtins = {'os', 'sys', 'time', 'datetime', 're', 'json', 'random', 'string', 
                   'math', 'collections', 'itertools', 'functools', 'typing', 'logging',
                   'threading', 'subprocess', 'socket', 'ssl', 'hashlib', 'base64',
                   'urllib', 'http', 'email', 'pathlib', 'tempfile', 'shutil', 'zipfile',
                   'tarfile', 'io', 'pickle', 'sqlite3', 'xml', 'csv', 'argparse',
                   'ast', 'inspect', 'pdb', 'traceback', 'warnings', 'contextlib',
                   'abc', 'enum', 'dataclasses', 'asyncio', 'unittest', 'doctest'}
        
        missing = []
        for imp in set(imports):
            if imp in builtins:
                continue
            try:
                __import__(imp)
            except ImportError:
                missing.append(imp)
        
        if not missing:
            return True
        
        logger.info(f"📦 Installing missing packages: {missing}")
        for package in missing:
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package, '--quiet', '--timeout', '60'],
                    capture_output=True,
                    timeout=120
                )
                stats['auto_installs'] += 1
                logger.info(f"✅ Installed: {package}")
            except Exception as e:
                logger.error(f"❌ Failed to install {package}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Auto install error: {e}")
        return False

def run_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply):
    script_key = f"{script_owner_id}_{file_name}"
    
    try:
        if not os.path.exists(script_path):
            try:
                bot.send_message(script_owner_id, f"❌ File `{file_name}` not found", parse_mode='Markdown')
            except:
                pass
            return
        
        auto_install_pip_packages(script_path, user_folder)
        
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = None
        
        try:
            log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"❌ Failed to open log file: {e}")
            return
        
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.Popen(
                [sys.executable, script_path],
                cwd=user_folder,
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.PIPE,
                startupinfo=startupinfo,
                encoding='utf-8',
                errors='ignore',
                bufsize=1
            )
            
            bot_scripts[script_key] = {
                'process': process,
                'log_file': log_file,
                'file_name': file_name,
                'chat_id': script_owner_id,
                'script_owner_id': script_owner_id,
                'start_time': datetime.now(),
                'user_folder': user_folder,
                'type': 'py',
                'pid': process.pid
            }
            
            stats['total_running'] = len(bot_scripts)
            
            try:
                bot.send_message(script_owner_id, 
                               f"✅ `{file_name}` Running (PID: {process.pid})",
                               parse_mode='Markdown')
            except:
                pass
            
            try:
                if message_obj_for_reply:
                    bot.delete_message(message_obj_for_reply.chat.id, message_obj_for_reply.message_id)
            except:
                pass
                
        except Exception as e:
            if log_file and not log_file.closed:
                log_file.close()
            logger.error(f"❌ Error starting script: {e}")
            try:
                bot.send_message(script_owner_id, f"❌ Error starting `{file_name}`", parse_mode='Markdown')
            except:
                pass
            if script_key in bot_scripts:
                del bot_scripts[script_key]
                
    except Exception as e:
        logger.error(f"❌ Error: {e}")

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj_for_reply):
    script_key = f"{script_owner_id}_{file_name}"
    
    try:
        if not os.path.exists(script_path):
            try:
                bot.send_message(script_owner_id, f"❌ File `{file_name}` not found", parse_mode='Markdown')
            except:
                pass
            return
        
        if not ensure_nodejs():
            try:
                bot.send_message(script_owner_id, 
                               f"❌ Node.js installation failed. Please install Node.js manually.\n\n"
                               f"Installation guide: https://nodejs.org",
                               parse_mode='Markdown')
            except:
                pass
            return
        
        auto_install_npm_packages(user_folder, script_path)
        
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = None
        
        try:
            log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"❌ Failed to open log file: {e}")
            return
        
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.Popen(
                ['node', script_path],
                cwd=user_folder,
                stdout=log_file,
                stderr=log_file,
                stdin=subprocess.PIPE,
                startupinfo=startupinfo,
                encoding='utf-8',
                errors='ignore',
                bufsize=1
            )
            
            bot_scripts[script_key] = {
                'process': process,
                'log_file': log_file,
                'file_name': file_name,
                'chat_id': script_owner_id,
                'script_owner_id': script_owner_id,
                'start_time': datetime.now(),
                'user_folder': user_folder,
                'type': 'js',
                'pid': process.pid
            }
            
            stats['total_running'] = len(bot_scripts)
            
            try:
                bot.send_message(script_owner_id, 
                               f"✅ `{file_name}` Running (PID: {process.pid})",
                               parse_mode='Markdown')
            except:
                pass
            
            try:
                if message_obj_for_reply:
                    bot.delete_message(message_obj_for_reply.chat.id, message_obj_for_reply.message_id)
            except:
                pass
                
        except Exception as e:
            if log_file and not log_file.closed:
                log_file.close()
            logger.error(f"❌ Error starting JS: {e}")
            try:
                bot.send_message(script_owner_id, f"❌ Error starting `{file_name}`", parse_mode='Markdown')
            except:
                pass
            if script_key in bot_scripts:
                del bot_scripts[script_key]
                
    except Exception as e:
        logger.error(f"❌ Error: {e}")

def auto_install_npm_packages(user_folder, script_path):
    try:
        if not os.path.exists(script_path):
            return False
        
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        require_pattern = re.compile(r"require\(['\"]([^'\"]+)['\"]\)", re.IGNORECASE)
        imports = require_pattern.findall(content)
        
        import_pattern = re.compile(r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]", re.IGNORECASE)
        imports.extend(import_pattern.findall(content))
        
        builtins = {'fs', 'path', 'http', 'https', 'url', 'util', 'events', 'stream', 
                   'crypto', 'zlib', 'os', 'child_process', 'buffer', 'timers', 
                   'worker_threads', 'perf_hooks', 'dns', 'net', 'tls', 'readline',
                   'querystring', 'string_decoder', 'punycode', 'assert', 'console',
                   'cluster', 'domain', 'module', 'process', 'vm', 'v8', 'inspector'}
        
        node_modules_path = os.path.join(user_folder, 'node_modules')
        missing = []
        
        for package in set(imports):
            package_name = package.split('/')[0]
            if package_name.startswith('@'):
                package_name = package.split('/')[0] + '/' + package.split('/')[1]
            
            if package_name in builtins:
                continue
            
            package_path = os.path.join(node_modules_path, package_name)
            if not os.path.exists(package_path):
                missing.append(package_name)
        
        if not missing:
            return True
        
        logger.info(f"📦 Installing npm packages: {missing}")
        
        for package in missing[:5]:
            try:
                subprocess.run(
                    ['npm', 'install', package, '--save', '--no-audit', '--no-fund', '--quiet'],
                    cwd=user_folder,
                    capture_output=True,
                    timeout=120
                )
                stats['auto_installs'] += 1
                logger.info(f"✅ Installed npm: {package}")
            except Exception as e:
                logger.error(f"❌ Failed to install npm {package}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"❌ npm auto install error: {e}")
        return False

# ============================================
# FILE HANDLING FUNCTIONS
# ============================================

def handle_zip_file(downloaded_file_content, file_name_zip, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    
    try:
        if len(downloaded_file_content) == 0:
            bot.reply_to(message, "❌ Error: ZIP file is empty.")
            return
            
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        zip_path = os.path.join(temp_dir, file_name_zip)
        
        with open(zip_path, 'wb') as new_file:
            new_file.write(downloaded_file_content)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        py_files = []
        js_files = []
        
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.py'):
                    py_files.append(os.path.join(root, file))
                elif file.endswith('.js'):
                    js_files.append(os.path.join(root, file))
        
        main_file = None
        file_type = None
        
        if py_files:
            for preferred in ['main.py', 'bot.py', 'app.py', 'start.py']:
                for f in py_files:
                    if os.path.basename(f) == preferred:
                        main_file = f
                        file_type = 'py'
                        break
                if main_file:
                    break
            if not main_file:
                main_file = py_files[0]
                file_type = 'py'
        
        elif js_files:
            for preferred in ['index.js', 'main.js', 'bot.js', 'app.js']:
                for f in js_files:
                    if os.path.basename(f) == preferred:
                        main_file = f
                        file_type = 'js'
                        break
                if main_file:
                    break
            if not main_file:
                main_file = js_files[0]
                file_type = 'js'
        
        if not main_file:
            bot.reply_to(message, "❌ No Python or JavaScript files found in ZIP!")
            return
        
        file_id = f"zip_{user_id}_{int(time.time())}"
        main_file_name = os.path.basename(main_file)
        
        pending_folder = os.path.join(user_folder, 'pending')
        os.makedirs(pending_folder, exist_ok=True)
        dest_path = os.path.join(pending_folder, main_file_name)
        
        shutil.copy2(main_file, dest_path)
        
        save_pending_file(file_id, user_id, main_file_name, file_type, dest_path)
        
        bot.reply_to(message, f"📤 File '{main_file_name}' uploaded and waiting for admin approval.")
        
        notify_admins_about_pending_file(user_id, main_file_name, file_type, file_id)
        
    except Exception as e:
        logger.error(f"Error processing ZIP: {e}")
        bot.reply_to(message, f"❌ Error processing ZIP: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

def handle_js_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        if is_user_banned(script_owner_id):
            bot.reply_to(message, "🚫 You are banned from using this bot.")
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        
        file_limit = get_user_file_limit(script_owner_id)
        current_files = get_user_file_count(script_owner_id)
        if current_files >= file_limit:
            limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
            bot.reply_to(message, f"⚠️ File limit ({current_files}/{limit_str}) reached. Delete files first.")
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        
        file_id = f"js_{script_owner_id}_{int(time.time())}"
        
        pending_folder = os.path.join(user_folder, 'pending')
        os.makedirs(pending_folder, exist_ok=True)
        pending_path = os.path.join(pending_folder, file_name)
        
        if os.path.exists(file_path):
            shutil.move(file_path, pending_path)
        
        save_pending_file(file_id, script_owner_id, file_name, 'js', pending_path)
        
        bot.reply_to(message, f"📤 File '{file_name}' uploaded and waiting for admin approval.")
        
        notify_admins_about_pending_file(script_owner_id, file_name, 'js', file_id)
        
    except Exception as e:
        logger.error(f"Error processing JS file: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

def handle_py_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        if is_user_banned(script_owner_id):
            bot.reply_to(message, "🚫 You are banned from using this bot.")
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        
        file_limit = get_user_file_limit(script_owner_id)
        current_files = get_user_file_count(script_owner_id)
        if current_files >= file_limit:
            limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
            bot.reply_to(message, f"⚠️ File limit ({current_files}/{limit_str}) reached. Delete files first.")
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        
        file_id = f"py_{script_owner_id}_{int(time.time())}"
        
        pending_folder = os.path.join(user_folder, 'pending')
        os.makedirs(pending_folder, exist_ok=True)
        pending_path = os.path.join(pending_folder, file_name)
        
        if os.path.exists(file_path):
            shutil.move(file_path, pending_path)
        
        save_pending_file(file_id, script_owner_id, file_name, 'py', pending_path)
        
        bot.reply_to(message, f"📤 File '{file_name}' uploaded and waiting for admin approval.")
        
        notify_admins_about_pending_file(script_owner_id, file_name, 'py', file_id)
        
    except Exception as e:
        logger.error(f"Error processing Python file: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ============================================
# KEYBOARD FUNCTIONS
# ============================================

def create_main_menu_keyboard(user_id):
    """Create main menu keyboard - NO PROFILE BUTTON"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        '📤 Upload File',
        '📂 My Files',
        '📊 Statistics'
    ]
    if user_id in admin_ids:
        pending_count = get_pending_files_count()
        pending_text = f"⏳ Pending Files ({pending_count})" if pending_count > 0 else "⏳ Pending Files"
        buttons.append('⚙️ Admin Dashboard')
        buttons.append(pending_text)
        buttons.append('🚫 Banned Users')
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i+1])
        else:
            markup.row(buttons[i])
    
    return markup

def create_manage_files_keyboard(user_id):
    user_files_list = user_files.get(user_id, [])
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if not user_files_list:
        markup.add(types.InlineKeyboardButton("📭 No Files", callback_data='no_files'))
    else:
        for file_name, file_type, file_path in user_files_list:
            is_running = is_bot_running(user_id, file_name)
            status_emoji = "🟢" if is_running else "🔴"
            markup.add(types.InlineKeyboardButton(f"{status_emoji} {file_name}", 
                                                 callback_data=f'file_{user_id}_{file_name}'))
    
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data='back_to_main'))
    return markup

def create_file_management_buttons(user_id, file_name, is_running):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("⏸️ Stop", callback_data=f'stop_{user_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{user_id}_{file_name}')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("▶️ Start", callback_data=f'start_{user_id}_{file_name}')
        )
    markup.row(
        types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{user_id}_{file_name}'),
        types.InlineKeyboardButton("📋 Logs", callback_data=f'logs_{user_id}_{file_name}')
    )
    markup.row(
        types.InlineKeyboardButton("📥 Download", callback_data=f'download_{user_id}_{file_name}'),
        types.InlineKeyboardButton("⬅️ Back", callback_data='manage_files')
    )
    return markup

def create_force_join_message():
    return f"""
🔒 *ACCESS RESTRICTED* 🔒

👋 Welcome to MrlDi Cloud Hosting!

To access our services, please join:

🌐 **Channel:** [Join Channel]({FORCE_CHANNEL_LINK})
👥 **Group:** [Join Group]({FORCE_GROUP_LINK})

Tap "✅ Verify Access" after joining."""

def create_force_join_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🌐 Join Channel", url=FORCE_CHANNEL_LINK))
    markup.add(types.InlineKeyboardButton("👥 Join Group", url=FORCE_GROUP_LINK))
    markup.add(types.InlineKeyboardButton("✅ Verify Access", callback_data='check_membership'))
    return markup

def create_admin_panel_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        '📊 Users Stats',
        '📢 Broadcast'
    ]
    
    if user_id == OWNER_ID:
        owner_buttons = [
            '➕ Add Admin',
            '➖ Remove Admin',
            '🚫 Ban User',
            '✅ Unban User',
            '📋 Banned List',
            '🔧 System Info',
            '📈 System Stats',
            '🔄 Restart Bot'
        ]
        buttons = owner_buttons + buttons
    
    buttons.append('⬅️ Back')
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(buttons[i], buttons[i+1])
        else:
            markup.row(buttons[i])
    
    return markup

# ============================================
# CALLBACK HANDLERS
# ============================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.message.chat.type in ['group', 'supergroup']:
        bot.answer_callback_query(call.id, "❌ Private chat only", show_alert=True)
        return
    
    if is_user_banned(user_id) and user_id not in admin_ids:
        bot.answer_callback_query(call.id, "🚫 You are banned!", show_alert=True)
        return
    
    if is_rate_limited(user_id) and user_id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Slow down!", show_alert=True)
        return
    
    data = call.data
    
    try:
        # ✅ FIXED: Handle start_ callback properly
        if data.startswith('start_'):
            handle_start_file(call)
        elif data.startswith('stop_'):
            handle_stop_file(call)
        elif data.startswith('restart_'):
            handle_restart_file(call)
        elif data.startswith('delete_'):
            handle_delete_file(call)
        elif data.startswith('logs_'):
            handle_logs_file(call)
        elif data.startswith('download_'):
            handle_download_file(call)
        elif data.startswith('file_'):
            handle_file_click(call)
        elif data.startswith('approve_file_'):
            handle_approve_file(call)
        elif data.startswith('reject_file_'):
            handle_reject_file(call)
        elif data.startswith('user_info_'):
            handle_user_info(call)
        elif data.startswith('ban_user_id_'):
            handle_ban_user_from_callback(call)
        elif data == 'check_membership':
            handle_check_membership(call)
        elif data == 'manage_files':
            handle_manage_files(call)
        elif data == 'start_hosting':
            handle_start_hosting(call)
        elif data == 'back_to_main':
            handle_back_to_main(call)
        elif data == 'pending_files':
            handle_pending_files(call)
        elif data == 'banned_users_list':
            handle_banned_users_list(call)
        elif data.startswith('unban_user_'):
            handle_unban_user(call)
        else:
            bot.answer_callback_query(call.id, "❌ Unknown action", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

# ============================================
# START FILE FUNCTION - FIXED
# ============================================

def handle_start_file(call):
    """Handle start file - FIXED"""
    try:
        parts = call.data.split('_', 2)
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "❌ Invalid request", show_alert=True)
            return
            
        user_id_str, file_name = parts[1], parts[2]
        user_id = int(user_id_str)
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "❌ Access Denied", show_alert=True)
            return
        
        # Find file path
        file_path = None
        for fn, ft, fp in user_files.get(user_id, []):
            if fn == file_name:
                file_path = fp
                break
        
        if not file_path or not os.path.exists(file_path):
            bot.answer_callback_query(call.id, "❌ File not found", show_alert=True)
            return
        
        if is_bot_running(user_id, file_name):
            bot.answer_callback_query(call.id, "⚠️ Already running", show_alert=True)
            return
        
        user_folder = get_user_folder(user_id)
        
        # Start based on file extension
        if file_name.endswith('.py'):
            threading.Thread(target=run_script,
                           args=(file_path, user_id, user_folder, file_name, call.message), daemon=True).start()
            bot.answer_callback_query(call.id, "🚀 Starting Python...")
        elif file_name.endswith('.js'):
            threading.Thread(target=run_js_script,
                           args=(file_path, user_id, user_folder, file_name, call.message), daemon=True).start()
            bot.answer_callback_query(call.id, "🚀 Starting JavaScript...")
        else:
            bot.answer_callback_query(call.id, f"❌ Unsupported file", show_alert=True)
            return
        
        time.sleep(1)
        handle_file_click(call)
        
    except Exception as e:
        logger.error(f"❌ Start error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

# ============================================
# OTHER CALLBACKS
# ============================================

def handle_approve_file(call):
    file_id = call.data.replace('approve_file_', '')
    
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    success, message = approve_file(file_id, call.from_user.id)
    bot.answer_callback_query(call.id, message, show_alert=True)
    
    if success:
        handle_pending_files(call)

def handle_reject_file(call):
    file_id = call.data.replace('reject_file_', '')
    
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    msg = bot.send_message(call.message.chat.id, 
                          "Enter reason for rejection (or send /skip to reject without reason):")
    bot.register_next_step_handler(msg, process_reject_reason, file_id, call)

def process_reject_reason(message, file_id, original_call):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Not authorized.")
        return
    
    reason = None if message.text == '/skip' else message.text
    
    success, result = reject_file(file_id, message.from_user.id, reason)
    bot.reply_to(message, result)
    
    if success:
        handle_pending_files(original_call)

def handle_user_info(call):
    user_id = int(call.data.replace('user_info_', ''))
    
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    user_info_text = f"👤 User ID: {user_id}"
    try:
        chat = bot.get_chat(user_id)
        if chat.username:
            user_info_text += f"\nUsername: @{chat.username}"
        if chat.first_name:
            user_info_text += f"\nName: {chat.first_name}"
    except:
        pass
    
    file_count = get_user_file_count(user_id)
    is_banned = is_user_banned(user_id)
    
    user_info_text += f"\n\n📁 Files: {file_count}"
    user_info_text += f"\n🚫 Banned: {'Yes' if is_banned else 'No'}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    if not is_banned:
        markup.add(types.InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_user_id_{user_id}"))
    else:
        markup.add(types.InlineKeyboardButton("✅ Unban User", callback_data=f"unban_user_{user_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="pending_files"))
    
    try:
        bot.edit_message_text(user_info_text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, user_info_text, reply_markup=markup)

def handle_ban_user_from_callback(call):
    user_id = int(call.data.replace('ban_user_id_', ''))
    
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "User already banned.", show_alert=True)
        return
    
    msg = bot.send_message(call.message.chat.id, 
                          f"Enter ban reason for user {user_id} (or /skip):")
    bot.register_next_step_handler(msg, process_ban_reason_from_callback, user_id, call)

def process_ban_reason_from_callback(message, user_id, original_call):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Not authorized.")
        return
    
    reason = None if message.text == '/skip' else message.text
    
    success = ban_user(message.from_user.id, user_id, reason=reason)
    
    if success:
        bot.reply_to(message, f"✅ User {user_id} banned.")
        handle_user_info(original_call)
    else:
        bot.reply_to(message, f"❌ Failed to ban user.")

def handle_pending_files(call):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    pending = get_all_pending_files()
    
    if not pending:
        try:
            bot.edit_message_text("📂 No pending files.",
                                call.message.chat.id, call.message.message_id,
                                reply_markup=types.InlineKeyboardMarkup().add(
                                    types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main")
                                ))
        except:
            bot.send_message(call.message.chat.id, "📂 No pending files.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_id, info in pending.items():
        user_id = info['user_id']
        file_name = info['file_name']
        file_type = info['file_type']
        upload_time = info['upload_time'].strftime('%H:%M %d/%m')
        
        user_display = f"User {user_id}"
        try:
            chat = bot.get_chat(user_id)
            if chat.username:
                user_display = f"@{chat.username}"
            elif chat.first_name:
                user_display = chat.first_name
        except:
            pass
        
        btn_text = f"{file_name} ({file_type}) - {user_display} [{upload_time}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"review_file_{file_id}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
    try:
        bot.edit_message_text("⏳ Pending Files:",
                             call.message.chat.id, call.message.message_id,
                             reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, "⏳ Pending Files:", reply_markup=markup)

def handle_banned_users_list(call):
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    banned = get_banned_users()
    
    if not banned:
        try:
            bot.edit_message_text("🚫 No banned users.",
                                call.message.chat.id, call.message.message_id,
                                reply_markup=types.InlineKeyboardMarkup().add(
                                    types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main")
                                ))
        except:
            bot.send_message(call.message.chat.id, "🚫 No banned users.")
        return
    
    msg = "🚫 Banned Users:\n\n"
    for user_id, info in list(banned.items())[:15]:
        name = info.get('first_name', 'Unknown')
        username = info.get('username', '')
        ban_time = info.get('ban_time', datetime.now()).strftime('%d/%m/%Y')
        reason = info.get('reason', 'No reason')
        
        display = f"• {name}"
        if username:
            display += f" (@{username})"
        display += f"\n  ID: {user_id}\n  Banned: {ban_time}\n  Reason: {reason}\n"
        msg += display + "\n"
    
    if len(msg) > 3500:
        msg = msg[:3500] + "...\n(Truncated)"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for user_id in list(banned.keys())[:10]:
        info = banned[user_id]
        name = info.get('first_name', 'Unknown')
        markup.add(types.InlineKeyboardButton(f"✅ Unban {name}", callback_data=f"unban_user_{user_id}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
    
    try:
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                             reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, msg, reply_markup=markup)

def handle_unban_user(call):
    user_id = int(call.data.replace('unban_user_', ''))
    
    if call.from_user.id not in admin_ids:
        bot.answer_callback_query(call.id, "⚠️ Admin permissions required.", show_alert=True)
        return
    
    success = unban_user(call.from_user.id, user_id)
    
    if success:
        bot.answer_callback_query(call.id, f"✅ User {user_id} unbanned.")
        try:
            bot.send_message(user_id, "✅ You have been unbanned and can now use the bot.")
        except:
            pass
        handle_banned_users_list(call)
    else:
        bot.answer_callback_query(call.id, "❌ Failed to unban.", show_alert=True)

def handle_check_membership(call):
    user_id = call.from_user.id
    
    if check_force_join(user_id):
        bot.answer_callback_query(call.id, "✅ Verified", show_alert=True)
        add_active_user(user_id)
        save_user(user_id, call.from_user.username, call.from_user.first_name, call.from_user.last_name)
        
        welcome_text = f"""
☁️ **MrlDi CLOUD HOSTING** ☁️

✨ *Welcome, {call.from_user.first_name}!*

✅ **MEMBERSHIP VERIFIED**

📊 **Status:** {get_user_status(user_id)}
📁 **Files:** {get_user_file_count(user_id)}/{get_user_file_limit(user_id) if get_user_file_limit(user_id) != float('inf') else '∞'}

Tap buttons to start hosting."""
        
        markup = create_main_menu_keyboard(user_id)
        try:
            bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id,
                                 reply_markup=markup, parse_mode='Markdown')
        except:
            bot.send_message(call.message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, "❌ Please join the group and channel first", show_alert=True)

def handle_file_click(call):
    try:
        parts = call.data.split('_', 2)
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "❌ Invalid request", show_alert=True)
            return
            
        user_id_str, file_name = parts[1], parts[2]
        user_id = int(user_id_str)
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "❌ Access Denied", show_alert=True)
            return
        
        is_running = is_bot_running(user_id, file_name)
        
        file_path = None
        file_type = None
        file_size = 0
        for fn, ft, fp in user_files.get(user_id, []):
            if fn == file_name:
                file_type = ft
                file_path = fp
                if os.path.exists(fp):
                    file_size = os.path.getsize(fp)
                break
        
        file_text = f"""
📄 **FILE DETAILS**

━━━━━━━━━━━━━━━━━━━━━
📌 **Name:** `{file_name}`
📦 **Type:** {file_type or 'Unknown'}
📊 **Size:** {format_file_size(file_size)}
🔧 **Status:** {'🟢 Running' if is_running else '🔴 Stopped'}
━━━━━━━━━━━━━━━━━━━━━

Select an action below:"""
        
        markup = create_file_management_buttons(user_id, file_name, is_running)
        try:
            bot.edit_message_text(file_text, call.message.chat.id, call.message.message_id,
                                 reply_markup=markup, parse_mode='Markdown')
        except:
            bot.send_message(call.message.chat.id, file_text, reply_markup=markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ File click error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

def handle_manage_files(call):
    user_id = call.from_user.id
    
    refresh_user_files_from_db(user_id)
    
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.answer_callback_query(call.id, "📭 No Files", show_alert=True)
        return
    
    files_text = f"📂 **MY FILES:**\n\n"
    for file_name, file_type, file_path in user_files_list:
        is_running = is_bot_running(user_id, file_name)
        status = "🟢 Running" if is_running else "🔴 Stopped"
        files_text += f"• `{file_name}`\n  ├─ {status}\n\n"
    
    markup = create_manage_files_keyboard(user_id)
    try:
        bot.edit_message_text(files_text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, files_text, reply_markup=markup, parse_mode='Markdown')

def handle_start_hosting(call):
    user_id = call.from_user.id
    
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.answer_callback_query(call.id, "❌ No Files to Deploy", show_alert=True)
        return
    
    started_count = 0
    for file_name, file_type, file_path in user_files_list:
        if not is_bot_running(user_id, file_name):
            user_folder = get_user_folder(user_id)
            if os.path.exists(file_path):
                file_ext = os.path.splitext(file_name)[1].lower()
                if file_ext == '.py':
                    threading.Thread(target=run_script, 
                                   args=(file_path, user_id, user_folder, file_name, call.message), daemon=True).start()
                    started_count += 1
                elif file_ext == '.js':
                    threading.Thread(target=run_js_script,
                                   args=(file_path, user_id, user_folder, file_name, call.message), daemon=True).start()
                    started_count += 1
                time.sleep(0.5)
    
    bot.answer_callback_query(call.id, f"🚀 Deployed {started_count} files")

def handle_back_to_main(call):
    user_id = call.from_user.id
    
    main_menu_text = f"""
☁️ **MrlDi CLOUD HOSTING**

👋 *{call.from_user.first_name}*

━━━━━━━━━━━━━━━━━━━━━
📊 **ACCOUNT INFO**
━━━━━━━━━━━━━━━━━━━━━
├─ ID: `{user_id}`
├─ Status: {get_user_status(user_id)}
├─ Files: {get_user_file_count(user_id)} / {get_user_file_limit(user_id) if get_user_file_limit(user_id) != float('inf') else '∞'}
└─ Running: {sum(1 for fn, _, _ in user_files.get(user_id, []) if is_bot_running(user_id, fn))}

Select an option below."""
    
    markup = create_main_menu_keyboard(user_id)
    try:
        bot.edit_message_text(main_menu_text, call.message.chat.id, call.message.message_id,
                             reply_markup=markup, parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, main_menu_text, reply_markup=markup, parse_mode='Markdown')

def handle_stop_file(call):
    try:
        parts = call.data.split('_', 2)
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "❌ Invalid request", show_alert=True)
            return
            
        user_id_str, file_name = parts[1], parts[2]
        user_id = int(user_id_str)
        script_key = f"{user_id}_{file_name}"
        
        process_info = bot_scripts.get(script_key)
        if process_info:
            force_cleanup_process(process_info)
            if script_key in bot_scripts:
                del bot_scripts[script_key]
            stats['total_running'] = len(bot_scripts)
            bot.answer_callback_query(call.id, f"⏸️ Stopped successfully")
        else:
            bot.answer_callback_query(call.id, f"ℹ️ Not running")
        
        time.sleep(0.5)
        handle_file_click(call)
            
    except Exception as e:
        logger.error(f"❌ Stop error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

def handle_restart_file(call):
    try:
        parts = call.data.split('_', 2)
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "❌ Invalid request", show_alert=True)
            return
            
        user_id_str, file_name = parts[1], parts[2]
        user_id = int(user_id_str)
        
        script_key = f"{user_id}_{file_name}"
        process_info = bot_scripts.get(script_key)
        if process_info:
            force_cleanup_process(process_info)
            if script_key in bot_scripts:
                del bot_scripts[script_key]
            time.sleep(1)
        
        file_path = None
        for fn, ft, fp in user_files.get(user_id, []):
            if fn == file_name:
                file_path = fp
                break
        
        if file_path and os.path.exists(file_path):
            user_folder = get_user_folder(user_id)
            file_ext = os.path.splitext(file_name)[1].lower()
            if file_ext == '.py':
                threading.Thread(target=run_script, 
                               args=(file_path, user_id, user_folder, file_name, call.message), daemon=True).start()
            elif file_ext == '.js':
                threading.Thread(target=run_js_script,
                               args=(file_path, user_id, user_folder, file_name, call.message), daemon=True).start()
            bot.answer_callback_query(call.id, f"🔄 Restarting...")
        else:
            bot.answer_callback_query(call.id, "❌ File Not Found", show_alert=True)
        
        time.sleep(0.5)
        handle_file_click(call)
            
    except Exception as e:
        logger.error(f"❌ Restart error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

def handle_delete_file(call):
    try:
        parts = call.data.split('_', 2)
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "❌ Invalid request", show_alert=True)
            return
            
        user_id_str, file_name = parts[1], parts[2]
        user_id = int(user_id_str)
        
        script_key = f"{user_id}_{file_name}"
        process_info = bot_scripts.get(script_key)
        if process_info:
            force_cleanup_process(process_info)
            if script_key in bot_scripts:
                del bot_scripts[script_key]
        
        remove_user_file_db(user_id, file_name)
        
        user_folder = get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        log_file = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
            except:
                pass
        
        stats['total_running'] = len(bot_scripts)
        bot.answer_callback_query(call.id, f"🗑️ Deleted {file_name}")
        
        try:
            bot.edit_message_text(
                f"🗑️ **{file_name}** Deleted",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        except:
            pass
        
        time.sleep(1)
        handle_manage_files(call)
        
    except Exception as e:
        logger.error(f"❌ Delete error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

def handle_logs_file(call):
    try:
        parts = call.data.split('_', 2)
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "❌ Invalid request", show_alert=True)
            return
            
        user_id_str, file_name = parts[1], parts[2]
        user_id = int(user_id_str)
        
        user_folder = get_user_folder(user_id)
        log_file = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                logs = f.read()
            
            if len(logs) > 4000:
                logs = logs[:4000] + "\n\n... (Truncated)"
            
            log_text = f"📋 **{file_name} Logs:**\n\n```\n{logs}\n```"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data=f'file_{user_id}_{file_name}'))
            
            try:
                bot.edit_message_text(log_text, call.message.chat.id, call.message.message_id,
                                     reply_markup=markup, parse_mode='Markdown')
            except:
                bot.send_message(call.message.chat.id, log_text, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "📭 No Logs Found", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ Logs error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

def handle_download_file(call):
    try:
        parts = call.data.split('_', 2)
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "❌ Invalid request", show_alert=True)
            return
            
        user_id_str, file_name = parts[1], parts[2]
        user_id = int(user_id_str)
        
        if call.from_user.id != user_id and call.from_user.id not in admin_ids:
            bot.answer_callback_query(call.id, "❌ Access Denied", show_alert=True)
            return
        
        file_path = None
        for fn, ft, fp in user_files.get(user_id, []):
            if fn == file_name:
                file_path = fp
                break
        
        if not file_path or not os.path.exists(file_path):
            bot.answer_callback_query(call.id, "❌ File not found", show_alert=True)
            return
        
        with open(file_path, 'rb') as f:
            bot.send_document(
                call.message.chat.id,
                f,
                caption=f"📄 {file_name}"
            )
        
        bot.answer_callback_query(call.id, "✅ Download started")
        
    except Exception as e:
        logger.error(f"❌ Download error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error", show_alert=True)
        except:
            pass

# ============================================
# MESSAGE HANDLERS
# ============================================

@bot.message_handler(commands=['start', 'help'])
def command_send_welcome(message):
    user_id = message.from_user.id
    
    if message.chat.type in ['group', 'supergroup']:
        return
    
    if is_user_banned(user_id) and user_id not in admin_ids:
        bot.send_message(message.chat.id,
                        f"""🚫 *YOU ARE BANNED*

👑 **Contact Admin:** {YOUR_USERNAME}""",
                        parse_mode='Markdown')
        return
    
    if force_join_enabled and user_id not in admin_ids and not check_force_join(user_id):
        force_message = create_force_join_message()
        force_markup = create_force_join_keyboard()
        bot.send_message(message.chat.id, force_message, reply_markup=force_markup, parse_mode='Markdown')
        return
    
    add_active_user(user_id)
    save_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    
    welcome_text = f"""
☁️ **MrlDi CLOUD HOSTING** ☁️

✨ *Welcome, {message.from_user.first_name}!*

━━━━━━━━━━━━━━━━━━━━━
👤 **ACCOUNT STATUS**
━━━━━━━━━━━━━━━━━━━━━
├─ Plan: {get_user_status(user_id)}
├─ Files: {get_user_file_count(user_id)}/{get_user_file_limit(user_id) if get_user_file_limit(user_id) != float('inf') else '∞'}
└─ Running: {sum(1 for fn, _, _ in user_files.get(user_id, []) if is_bot_running(user_id, fn))}

Select an option below."""
    
    markup = create_main_menu_keyboard(user_id)
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')

# ============================================
# DOCUMENT HANDLER
# ============================================

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    doc = message.document
    
    if is_user_banned(user_id):
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return
    
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Bot is locked, cannot accept files.")
        return

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        limit_str = str(file_limit) if file_limit != float('inf') else "Unlimited"
        bot.reply_to(message, f"⚠️ File limit ({current_files}/{limit_str}) reached. Delete files first.")
        return

    file_name = doc.file_name
    if not file_name:
        bot.reply_to(message, "⚠️ No file name.")
        return
    
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "⚠️ Only `.py`, `.js`, or `.zip` files are allowed.")
        return
    
    if doc.file_size > 20 * 1024 * 1024:
        bot.reply_to(message, "⚠️ File too large! Max 20 MB.")
        return

    try:
        # Forward to owner
        try:
            bot.forward_message(OWNER_ID, chat_id, message.message_id)
            logger.info(f"✅ File forwarded to owner: {file_name} from user {user_id}")
            
            user_info = f"⬆️ Uploader: {message.from_user.first_name}\n"
            user_info += f"🆔 ID: {user_id}\n"
            if message.from_user.username:
                user_info += f"✳️ Username: @{message.from_user.username}\n"
            user_info += f"📁 File: {file_name}\n"
            user_info += f"📊 Size: {doc.file_size / 1024:.1f} KB\n"
            user_info += f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            bot.send_message(OWNER_ID, user_info, parse_mode=None)
            logger.info(f"✅ User info sent to owner for file: {file_name}")
        except Exception as e:
            logger.error(f"❌ Failed to forward file to OWNER_ID {OWNER_ID}: {e}")

        # Download file
        download_msg = bot.reply_to(message, f"⏳ Downloading `{file_name}`...")
        file_info = bot.get_file(doc.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        bot.edit_message_text(f"✅ Downloaded `{file_name}`. Processing...", chat_id, download_msg.message_id)
        
        user_folder = get_user_folder(user_id)

        if file_ext == '.zip':
            handle_zip_file(downloaded_file, file_name, message)
        else:
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f:
                f.write(downloaded_file)
            
            if file_ext == '.js':
                handle_js_file(file_path, user_id, user_folder, file_name, message)
            elif file_ext == '.py':
                handle_py_file(file_path, user_id, user_folder, file_name, message)
                
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Telegram API Error: {e}")
        if "file is too big" in str(e).lower():
            bot.reply_to(message, "❌ Telegram API Error: File too large to download (~20MB limit).")
        else:
            bot.reply_to(message, f"❌ Telegram API Error: {str(e)}")
    except Exception as e:
        logger.error(f"Error handling file: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ============================================
# TEXT MESSAGE HANDLER
# ============================================

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    
    if message.chat.type in ['group', 'supergroup']:
        return
    
    if is_rate_limited(user_id) and user_id not in admin_ids:
        bot.send_message(message.chat.id, "⚠️ Too many requests. Please wait.")
        return
    
    if is_user_banned(user_id) and user_id not in admin_ids:
        bot.send_message(message.chat.id, "🚫 You are banned!")
        return
    
    if force_join_enabled and user_id not in admin_ids and not check_force_join(user_id):
        force_message = create_force_join_message()
        force_markup = create_force_join_keyboard()
        bot.send_message(message.chat.id, force_message, reply_markup=force_markup, parse_mode='Markdown')
        return
    
    text = message.text
    
    # Admin commands
    if text == '⚙️ Admin Dashboard' and user_id in admin_ids:
        handle_admin_panel(message)
    elif text == '📊 Users Stats' and user_id in admin_ids:
        handle_users_stats(message)
    elif text == '📢 Broadcast' and user_id in admin_ids:
        handle_broadcast(message)
    elif text == '⏳ Pending Files' and user_id in admin_ids:
        handle_pending_files_text(message)
    elif text == '🚫 Banned Users' and user_id in admin_ids:
        handle_banned_users_text(message)
    elif text == '➕ Add Admin' and user_id == OWNER_ID:
        handle_add_admin(message)
    elif text == '➖ Remove Admin' and user_id == OWNER_ID:
        handle_remove_admin(message)
    elif text == '🚫 Ban User' and user_id == OWNER_ID:
        handle_ban_user(message)
    elif text == '✅ Unban User' and user_id == OWNER_ID:
        handle_unban_user(message)
    elif text == '📋 Banned List' and user_id == OWNER_ID:
        handle_banned_list(message)
    elif text == '🔧 System Info' and user_id == OWNER_ID:
        handle_system_info(message)
    elif text == '📈 System Stats' and user_id == OWNER_ID:
        handle_system_stats(message)
    elif text == '🔄 Restart Bot' and user_id == OWNER_ID:
        handle_restart_bot(message)
    
    # User commands
    elif text == '⬅️ Back':
        handle_back_to_main_text(message)
    elif text == '📤 Upload File':
        handle_upload_file_text(message)
    elif text == '📂 My Files':
        handle_my_files_text(message)
    elif text == '📊 Statistics':
        handle_statistics(message)
    else:
        bot.send_message(message.chat.id, "❌ Invalid command. Use the menu buttons.")

# ============================================
# ADMIN TEXT HANDLERS
# ============================================

def handle_admin_panel(message):
    markup = create_admin_panel_keyboard(message.from_user.id)
    
    pending_count = get_pending_files_count()
    banned_count = len(get_banned_users())
    
    admin_text = f"""
🛡️ **ADMIN DASHBOARD**

👤 **Admin:** {message.from_user.first_name}
🆔 **ID:** `{message.from_user.id}`

━━━━━━━━━━━━━━━━━━━━━
📊 **QUICK STATS**
━━━━━━━━━━━━━━━━━━━━━
├─ Users: {len(active_users)}
├─ Files: {sum(len(files) for files in user_files.values())}
├─ Running: {len(bot_scripts)}
├─ Admins: {len(admin_ids)}
├─ Pending: {pending_count}
└─ Banned: {banned_count}

━━━━━━━━━━━━━━━━━━━━━
🛡️ **SECURITY**
━━━━━━━━━━━━━━━━━━━━━
├─ Scans: {stats['total_scans']}
├─ Approved: {stats['approved_files']}
├─ Declined: {stats['declined_files']}
├─ Warnings: {stats['warnings_given']}
└─ Banned: {stats['banned_users']}

━━━━━━━━━━━━━━━━━━━━━
⚡ **SYSTEM**
━━━━━━━━━━━━━━━━━━━━━
├─ Node.js: {'✅' if check_node_installed() else '❌'}
├─ Auto Installs: {stats['auto_installs']}
└─ Uptime: {str(timedelta(seconds=int(time.time() - start_time)))}

Select an option below."""
    
    bot.send_message(message.chat.id, admin_text, reply_markup=markup, parse_mode='Markdown')

def handle_users_stats(message):
    banned_users_list = get_banned_users()
    total_files = sum(len(files) for files in user_files.values())
    running_files = len(bot_scripts)
    pending_count = get_pending_files_count()
    
    stats_text = f"""
📊 **USER STATISTICS**

━━━━━━━━━━━━━━━━━━━━━
👥 **USERS**
━━━━━━━━━━━━━━━━━━━━━
├─ Total Users: {len(active_users)}
├─ Banned Users: {len(banned_users_list)}
└─ Admins: {len(admin_ids)}

━━━━━━━━━━━━━━━━━━━━━
📁 **FILES**
━━━━━━━━━━━━━━━━━━━━━
├─ Total Files: {total_files}
├─ Running: {running_files}
├─ Pending: {pending_count}
└─ Avg per User: {total_files / len(active_users) if active_users else 0:.1f}

━━━━━━━━━━━━━━━━━━━━━
🛡️ **SECURITY**
━━━━━━━━━━━━━━━━━━━━━
├─ Total Scans: {stats['total_scans']}
├─ Approved: {stats['approved_files']}
├─ Declined: {stats['declined_files']}
├─ Warnings: {stats['warnings_given']}
└─ Banned: {stats['banned_users']}

━━━━━━━━━━━━━━━━━━━━━
⚡ **SYSTEM**
━━━━━━━━━━━━━━━━━━━━━
├─ Running Scripts: {len(bot_scripts)}
├─ Auto Installs: {stats['auto_installs']}
└─ Uptime: {str(timedelta(seconds=int(time.time() - start_time)))}"""
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

def handle_broadcast(message):
    msg = bot.send_message(message.chat.id, "📢 Enter message to broadcast:")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    broadcast_text = message.text
    success = 0
    fail = 0
    
    status_msg = bot.send_message(message.chat.id, "📢 Broadcasting...")
    
    for user_id in list(active_users):
        if is_user_banned(user_id):
            continue
        try:
            bot.send_message(user_id, broadcast_text)
            success += 1
        except:
            fail += 1
        
        if (success + fail) % 10 == 0:
            try:
                bot.edit_message_text(f"📢 Broadcasting... {success+fail}/{len(active_users)}",
                                     status_msg.chat.id, status_msg.message_id)
            except:
                pass
    
    bot.edit_message_text(f"📢 **Broadcast Complete**\n\n✅ Success: {success}\n❌ Failed: {fail}",
                         status_msg.chat.id, status_msg.message_id, parse_mode='Markdown')

def handle_pending_files_text(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    
    pending = get_all_pending_files()
    
    if not pending:
        bot.reply_to(message, "📂 No pending files.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_id, info in pending.items():
        user_id = info['user_id']
        file_name = info['file_name']
        file_type = info['file_type']
        
        user_display = f"User {user_id}"
        try:
            chat = bot.get_chat(user_id)
            if chat.username:
                user_display = f"@{chat.username}"
            elif chat.first_name:
                user_display = chat.first_name
        except:
            pass
        
        btn_text = f"{file_name} ({file_type}) - {user_display}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"review_file_{file_id}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
    bot.reply_to(message, "⏳ Pending Files:", reply_markup=markup)

def handle_banned_users_text(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin permissions required.")
        return
    
    banned = get_banned_users()
    
    if not banned:
        bot.reply_to(message, "🚫 No banned users.")
        return
    
    msg = "🚫 Banned Users:\n\n"
    for user_id, info in list(banned.items())[:15]:
        name = info.get('first_name', 'Unknown')
        username = info.get('username', '')
        reason = info.get('reason', 'No reason')
        
        display = f"• {name}"
        if username:
            display += f" (@{username})"
        display += f"\n  ID: {user_id}\n  Reason: {reason}\n"
        msg += display + "\n"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for user_id in list(banned.keys())[:10]:
        info = banned[user_id]
        name = info.get('first_name', 'Unknown')
        markup.add(types.InlineKeyboardButton(f"✅ Unban {name}", callback_data=f"unban_user_{user_id}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
    
    bot.reply_to(message, msg, reply_markup=markup)

def handle_add_admin(message):
    msg = bot.send_message(message.chat.id, "🆔 Enter user ID to add as admin:")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    try:
        admin_id = int(message.text.strip())
        if admin_id == OWNER_ID:
            bot.send_message(message.chat.id, "❌ Already owner")
            return
        
        try:
            user_chat = bot.get_chat(admin_id)
            user_name = user_chat.first_name
        except:
            bot.send_message(message.chat.id, "❌ User not found")
            return
        
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO admins (user_id, role, added_by) VALUES (?, ?, ?)',
                 (admin_id, 'admin', message.from_user.id))
        conn.commit()
        conn.close()
        
        admin_ids.add(admin_id)
        bot.send_message(message.chat.id, f"✅ Admin added: `{admin_id}`\n👤 {user_name}", parse_mode='Markdown')
        
        try:
            bot.send_message(admin_id, f"🛡️ You have been promoted to admin by {message.from_user.first_name}")
        except:
            pass
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid ID")

def handle_remove_admin(message):
    msg = bot.send_message(message.chat.id, "🆔 Enter admin ID to remove:")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    try:
        admin_id = int(message.text.strip())
        if admin_id == OWNER_ID:
            bot.send_message(message.chat.id, "❌ Cannot remove owner")
            return
        
        if admin_id not in admin_ids:
            bot.send_message(message.chat.id, "❌ Not an admin")
            return
        
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()
        conn.close()
        
        admin_ids.discard(admin_id)
        bot.send_message(message.chat.id, f"✅ Admin removed: `{admin_id}`", parse_mode='Markdown')
        
        try:
            bot.send_message(admin_id, f"⚠️ You have been removed from admin by {message.from_user.first_name}")
        except:
            pass
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid ID")

def handle_ban_user(message):
    msg = bot.send_message(message.chat.id, "🆔 Enter user ID to ban:")
    bot.register_next_step_handler(msg, process_ban_user)

def process_ban_user(message):
    try:
        user_id = int(message.text.strip())
        if user_id in admin_ids or user_id == OWNER_ID:
            bot.send_message(message.chat.id, "❌ Cannot ban admin/owner")
            return
        
        success = ban_user(message.from_user.id, user_id, reason=f"Banned by {message.from_user.first_name}")
        if success:
            bot.send_message(message.chat.id, f"✅ User `{user_id}` banned", parse_mode='Markdown')
            try:
                bot.send_message(user_id, f"🚫 You have been banned by {message.from_user.first_name}")
            except:
                pass
        else:
            bot.send_message(message.chat.id, f"❌ Failed to ban user")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid ID")

def handle_unban_user(message):
    msg = bot.send_message(message.chat.id, "🆔 Enter user ID to unban:")
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    try:
        user_id = int(message.text.strip())
        success = unban_user(message.from_user.id, user_id)
        if success:
            bot.send_message(message.chat.id, f"✅ User `{user_id}` unbanned", parse_mode='Markdown')
            try:
                bot.send_message(user_id, f"✅ You have been unbanned by {message.from_user.first_name}")
            except:
                pass
        else:
            bot.send_message(message.chat.id, f"❌ Failed to unban user")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid ID")

def handle_banned_list(message):
    banned = get_banned_users()
    if not banned:
        bot.send_message(message.chat.id, "📭 No banned users")
        return
    
    text = "🚫 **BANNED USERS**\n\n"
    for user_id, info in list(banned.items())[:20]:
        name = info.get('first_name', 'Unknown')
        username = info.get('username', '')
        reason = info.get('reason', 'No reason')
        ban_time = info.get('ban_time', datetime.now()).strftime('%Y-%m-%d %H:%M')
        
        display = f"• {name}"
        if username:
            display += f" (@{username})"
        display += f"\n  ID: {user_id}\n  Banned: {ban_time}\n  Reason: {reason}\n"
        text += display + "\n"
    
    if len(banned) > 20:
        text += f"\n... {len(banned) - 20} more"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def handle_system_info(message):
    node_status = "✅ Installed" if check_node_installed() else "❌ Not Installed"
    node_version = get_node_version() or "N/A"
    
    info_text = f"""
🔧 **SYSTEM INFORMATION**

━━━━━━━━━━━━━━━━━━━━━
💻 **SYSTEM**
━━━━━━━━━━━━━━━━━━━━━
├─ OS: {platform.system()} {platform.release()}
├─ Python: {platform.python_version()}
├─ Hostname: {socket.gethostname()}
└─ Uptime: {str(timedelta(seconds=int(time.time() - start_time)))}

━━━━━━━━━━━━━━━━━━━━━
📦 **NODE.JS**
━━━━━━━━━━━━━━━━━━━━━
├─ Status: {node_status}
├─ Version: {node_version}
└─ Auto Installs: {stats['auto_installs']}

━━━━━━━━━━━━━━━━━━━━━
📊 **BOT STATS**
━━━━━━━━━━━━━━━━━━━━━
├─ Users: {len(active_users)}
├─ Admins: {len(admin_ids)}
├─ Files: {sum(len(files) for files in user_files.values())}
├─ Running: {len(bot_scripts)}
├─ Pending: {get_pending_files_count()}
└─ Total Uploads: {stats['total_uploads']}

━━━━━━━━━━━━━━━━━━━━━
🛡️ **SECURITY**
━━━━━━━━━━━━━━━━━━━━━
├─ Scans: {stats['total_scans']}
├─ Approved: {stats['approved_files']}
├─ Declined: {stats['declined_files']}
├─ Warnings: {stats['warnings_given']}
└─ Banned: {stats['banned_users']}"""
    
    bot.send_message(message.chat.id, info_text, parse_mode='Markdown')

def handle_system_stats(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Owner Only")
        return
    
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    stats_text = f"""
📈 **SYSTEM STATISTICS**

━━━━━━━━━━━━━━━━━━━━━
💻 **CPU**
━━━━━━━━━━━━━━━━━━━━━
├─ Usage: {cpu_percent}%
├─ Cores: {psutil.cpu_count()}
└─ {'█' * int(cpu_percent/5)}{'░' * (20 - int(cpu_percent/5))}

━━━━━━━━━━━━━━━━━━━━━
🧠 **MEMORY**
━━━━━━━━━━━━━━━━━━━━━
├─ Usage: {memory.percent}%
├─ Used: {format_file_size(memory.used)}
├─ Total: {format_file_size(memory.total)}
└─ {'█' * int(memory.percent/5)}{'░' * (20 - int(memory.percent/5))}

━━━━━━━━━━━━━━━━━━━━━
💾 **DISK**
━━━━━━━━━━━━━━━━━━━━━
├─ Usage: {disk.percent}%
├─ Used: {format_file_size(disk.used)}
├─ Total: {format_file_size(disk.total)}
└─ {'█' * int(disk.percent/5)}{'░' * (20 - int(disk.percent/5))}

━━━━━━━━━━━━━━━━━━━━━
📊 **BOT**
━━━━━━━━━━━━━━━━━━━━━
├─ Active Users: {len(active_users)}
├─ Running Scripts: {len(bot_scripts)}
├─ Total Files: {sum(len(files) for files in user_files.values())}
├─ Pending Files: {get_pending_files_count()}
└─ Uptime: {str(timedelta(seconds=int(time.time() - start_time)))}"""
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

def handle_restart_bot(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "❌ Owner Only")
        return
    
    bot.send_message(message.chat.id, "🔄 Restarting bot...")
    logger.info("🔄 Bot restart initiated by owner")
    
    cleanup()
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ============================================
# USER TEXT HANDLERS
# ============================================

def handle_back_to_main_text(message):
    user_id = message.from_user.id
    markup = create_main_menu_keyboard(user_id)
    bot.send_message(message.chat.id, "⬅️ Back to Main Menu", reply_markup=markup)

def handle_upload_file_text(message):
    user_id = message.from_user.id
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    
    if current_files >= file_limit:
        bot.send_message(message.chat.id, f"❌ Storage limit reached ({file_limit} files)\nContact admin for more space.")
        return
    
    supported = ", ".join(list(SUPPORTED_EXTENSIONS.keys())[:20])
    bot.send_message(message.chat.id,
                    f"""📤 **UPLOAD FILE**

Supported: `{supported}`
Max size: {format_file_size(MAX_FILE_SIZE)}

Upload your file. Admin will review before deployment.

📌 Supported: Python (.py), JavaScript (.js), and many more!""",
                    parse_mode='Markdown')

def handle_my_files_text(message):
    user_id = message.from_user.id
    
    refresh_user_files_from_db(user_id)
    
    user_files_list = user_files.get(user_id, [])
    if not user_files_list:
        bot.send_message(message.chat.id, "📭 No files found")
        return
    
    files_text = "📂 **MY FILES:**\n\n"
    for file_name, file_type, file_path in user_files_list:
        is_running = is_bot_running(user_id, file_name)
        status = "🟢 Running" if is_running else "🔴 Stopped"
        file_size = format_file_size(os.path.getsize(file_path)) if os.path.exists(file_path) else "Unknown"
        files_text += f"• `{file_name}`\n  ├─ {status}\n  └─ Size: {file_size}\n\n"
    
    markup = create_manage_files_keyboard(user_id)
    bot.send_message(message.chat.id, files_text, reply_markup=markup, parse_mode='Markdown')

def handle_statistics(message):
    user_id = message.from_user.id
    
    total_users = len(active_users)
    total_files = sum(len(files) for files in user_files.values())
    running_files = len(bot_scripts)
    pending_count = get_pending_files_count()
    banned_count = len(get_banned_users())
    
    stats_text = f"""
📊 **STATISTICS**

━━━━━━━━━━━━━━━━━━━━━
🌍 **GLOBAL**
━━━━━━━━━━━━━━━━━━━━━
├─ Total Users: {total_users}
├─ Banned Users: {banned_count}
├─ Total Files: {total_files}
├─ Running Files: {running_files}
├─ Pending Files: {pending_count}
└─ Admins: {len(admin_ids)}

━━━━━━━━━━━━━━━━━━━━━
👤 **YOUR STATS**
━━━━━━━━━━━━━━━━━━━━━
├─ Files: {get_user_file_count(user_id)}/{get_user_file_limit(user_id) if get_user_file_limit(user_id) != float('inf') else '∞'}
├─ Running: {sum(1 for fn, _, _ in user_files.get(user_id, []) if is_bot_running(user_id, fn))}
└─ Status: {get_user_status(user_id)}

━━━━━━━━━━━━━━━━━━━━━
🛡️ **SECURITY**
━━━━━━━━━━━━━━━━━━━━━
├─ Total Scans: {stats['total_scans']}
├─ Approved: {stats['approved_files']}
├─ Declined: {stats['declined_files']}
└─ Warnings Given: {stats['warnings_given']}

━━━━━━━━━━━━━━━━━━━━━
⚡ **SYSTEM**
━━━━━━━━━━━━━━━━━━━━━
├─ Auto Installs: {stats['auto_installs']}
├─ Node.js: {'✅' if check_node_installed() else '❌'}
└─ Uptime: {str(timedelta(seconds=int(time.time() - start_time)))}"""
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# ============================================
# CLEANUP
# ============================================

def cleanup():
    logger.warning("🛑 Shutting down...")
    for script_key in list(bot_scripts.keys()):
        if script_key in bot_scripts:
            force_cleanup_process(bot_scripts[script_key])
    logger.info("✅ Cleanup completed")

def schedule_cleanup():
    while True:
        try:
            cleanup_zombie_processes()
            
            now = time.time()
            for file in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, file)
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < now - 86400:
                    try:
                        os.remove(file_path)
                    except:
                        pass
            
            time.sleep(300)
        except:
            time.sleep(60)

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    atexit.register(cleanup)
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, cleaning up...")
        cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    init_db()
    upgrade_database()
    load_data()
    
    cleanup_thread = threading.Thread(target=schedule_cleanup, daemon=True)
    cleanup_thread.start()
    
    if not check_node_installed():
        logger.info("📦 Installing Node.js...")
        threading.Thread(target=install_nodejs, daemon=True).start()
    
    keep_alive()
    
    logger.info("🚀 MrlDi Cloud Bot v4.0 with Approve System starting...")
    logger.info(f"📊 Users: {len(active_users)}, Files: {sum(len(files) for files in user_files.values())}")
    logger.info(f"👥 Admins: {list(admin_ids)}")
    logger.info(f"⏳ Pending Files: {get_pending_files_count()}")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
            time.sleep(5)
            continue
