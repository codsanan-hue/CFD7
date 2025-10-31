import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
    
    # تنظیمات دیتابیس
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')
    
    # تنظیمات بازی
    GAME_ENTRY_FEE = 1
    GAME_WIN_REWARD = 2
    GAME_WAIT_TIME = 30
    GAME_CHOICE_TIME = 7
    
    # تنظیمات VIP
    VIP_MONTHLY_PRICE = 20000
    VIP_YEARLY_PRICE = 200000
    VIP_WEEKLY_PRICE = 10000

# ایجاد نمونه کانفیگ
config = Config()
