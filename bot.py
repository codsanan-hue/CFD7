import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    ConversationHandler
)
from config import config

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالت‌های گفتگو
ADD_PRODUCT_PHOTO, ADD_PRODUCT_NAME, ADD_PRODUCT_DESC, ADD_PRODUCT_PRICE, ADD_PRODUCT_QUANTITY, ADD_PRODUCT_DISCOUNT = range(6)

class TelegramBot:
    def __init__(self):
        self.db_connection = sqlite3.connect('bot_database.db', check_same_thread=False)
        self.create_tables()
        self.active_games = {}
    
    def create_tables(self):
        """ایجاد جداول دیتابیس"""
        cursor = self.db_connection.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                invite_count INTEGER DEFAULT 0,
                balance INTEGER DEFAULT 0,
                is_vip BOOLEAN DEFAULT FALSE,
                vip_expiry DATE,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                channel_username TEXT,
                channel_title TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                price INTEGER,
                quantity INTEGER,
                discount_vip INTEGER DEFAULT 0,
                media_type TEXT,
                media_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER,
                user2_id INTEGER,
                user1_choice TEXT,
                user2_choice TEXT,
                status TEXT DEFAULT 'waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.db_connection.commit()

    async def check_channel_membership(self, user_id: int) -> tuple:
        """چک کردن عضویت کاربر در کانال‌ها"""
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT channel_id, channel_username FROM channels")
        channels = cursor.fetchall()
        
        if not channels:
            return True, []
        
        bot = await self.application.bot.get_me()
        not_joined = []
        
        for channel_id, channel_username in channels:
            try:
                member = await self.application.bot.get_chat_member(channel_id, user_id)
                if member.status in ['left', 'kicked']:
                    not_joined.append((channel_id, channel_username))
            except Exception as e:
                logger.error(f"Error checking membership: {e}")
                continue
        
        return len(not_joined) == 0, not_joined

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور start"""
        user = update.effective_user
        user_id = user.id
        
        # ذخیره کاربر در دیتابیس
        cursor = self.db_connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name) 
            VALUES (?, ?, ?)
        ''', (user_id, user.username, user.first_name))
        self.db_connection.commit()
        
        # چک عضویت در کانال
        is_member, not_joined = await self.check_channel_membership(user_id)
        
        if not is_member:
            # نمایش کانال‌هایی که کاربر عضو نیست
            keyboard = []
            for channel_id, channel_username in not_joined:
                keyboard.append([InlineKeyboardButton(
                    f"عضویت در {channel_username}", 
                    url=f"https://t.me/{channel_username[1:]}"
                )])
            
            keyboard.append([InlineKeyboardButton("✅ تأیید عضویت", callback_data="verify_membership")])
            
            await update.message.reply_text(
                "📢 لطفاً در کانال‌های زیر عضو شوید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # نمایش منوی اصلی
        await self.show_main_menu(update, context)

    async def verify_membership(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تأیید عضویت"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        is_member, not_joined = await self.check_channel_membership(user_id)
        
        if is_member:
            await query.message.delete()
            await self.show_main_menu_from_query(query, context)
        else:
            await query.answer("❌ هنوز در برخی کانال‌ها عضو نشدید!", show_alert=True)

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش منوی اصلی"""
        keyboard = [
            [InlineKeyboardButton("🛍️ فروشگاه", callback_data="shop")],
            [InlineKeyboardButton("👥 دعوت دوست", callback_data="invite")],
            [InlineKeyboardButton("💰 موجودی", callback_data="balance")],
            [InlineKeyboardButton("🎮 بازی", callback_data="games")],
            [InlineKeyboardButton("⭐ VIP", callback_data="vip")],
            [InlineKeyboardButton("📜 قوانین", callback_data="rules")],
        ]
        
        if update.effective_user.id in config.ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ ادمین", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(
                "🎯 به ربات خوش آمدید! لطفاً یک گزینه انتخاب کنید:",
                reply_markup=reply_markup
            )
        else:
            await update.callback_query.edit_message_text(
                "🎯 به ربات خوش آمدید! لطفاً یک گزینه انتخاب کنید:",
                reply_markup=reply_markup
            )

    async def show_main_menu_from_query(self, query, context: ContextTypes.DEFAULT_TYPE):
        """نمایش منوی اصلی از callback"""
        keyboard = [
            [InlineKeyboardButton("🛍️ فروشگاه", callback_data="shop")],
            [InlineKeyboardButton("👥 دعوت دوست", callback_data="invite")],
            [InlineKeyboardButton("💰 موجودی", callback_data="balance")],
            [InlineKeyboardButton("🎮 بازی", callback_data="games")],
            [InlineKeyboardButton("⭐ VIP", callback_data="vip")],
            [InlineKeyboardButton("📜 قوانین", callback_data="rules")],
        ]
        
        if query.from_user.id in config.ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ ادمین", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 به ربات خوش آمدید! لطفاً یک گزینه انتخاب کنید:",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت کلیک روی دکمه‌ها"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "verify_membership":
            await self.verify_membership(update, context)
        elif data == "shop":
            await self.show_shop(update, context)
        elif data == "invite":
            await self.show_invite(update, context)
        elif data == "balance":
            await self.show_balance(update, context)
        elif data == "games":
            await self.show_games(update, context)
        elif data == "vip":
            await self.show_vip(update, context)
        elif data == "rules":
            await self.show_rules(update, context)
        elif data == "admin":
            await self.show_admin_panel(update, context)
        elif data == "back_to_menu":
            await self.show_main_menu(update, context)

    async def show_shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش فروشگاه"""
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT product_id, name, price FROM products WHERE quantity > 0")
        products = cursor.fetchall()
        
        if not products:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]]
            await update.callback_query.edit_message_text(
                "🛍️ فروشگاه\n\n❌ هیچ محصولی موجود نیست!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        keyboard = []
        for product_id, name, price in products:
            keyboard.append([InlineKeyboardButton(
                f"{name} - {price} تومن", 
                callback_data=f"product_{product_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")])
        
        await update.callback_query.edit_message_text(
            "🛍️ فروشگاه\n\nلطفاً یک محصول انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش بخش دعوت دوستان"""
        user_id = update.effective_user.id
        invite_link = f"https://t.me/{(await self.application.bot.get_me()).username}?start={user_id}"
        
        text = f"""
        👥 دعوت از دوستان

        🔗 لینک دعوت شما:
        `{invite_link}`

        📊 هر دوست که با لینک شما وارد شود:
        • شما: {1.5 if await self.is_vip(user_id) else 1} امتیاز
        • دوست شما: 1 امتیاز

        💡 لینک را برای دوستان خود ارسال کنید!
        """
        
        keyboard = [
            [InlineKeyboardButton("🔗 کپی لینک", callback_data="copy_link")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def is_vip(self, user_id: int) -> bool:
        """چک کردن وضعیت VIP کاربر"""
        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT is_vip, vip_expiry FROM users WHERE user_id = ?", 
            (user_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            return False
        
        is_vip, vip_expiry = result
        if is_vip and vip_expiry:
            return datetime.strptime(vip_expiry, '%Y-%m-%d') > datetime.now()
        
        return False

    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش موجودی"""
        user_id = update.effective_user.id
        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT balance, invite_count FROM users WHERE user_id = ?", 
            (user_id,)
        )
        result = cursor.fetchone()
        
        if result:
            balance, invite_count = result
        else:
            balance, invite_count = 0, 0
        
        vip_status = "✅ فعال" if await self.is_vip(user_id) else "❌ غیرفعال"
        
        text = f"""
        💰 موجودی شما:

        💵 اعتبار: {balance} امتیاز
        👥 تعداد دعوت: {invite_count}
        ⭐ وضعیت VIP: {vip_status}
        """
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_games(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش بخش بازی‌ها"""
        text = """
        🎮 بخش بازی‌ها

        🪨📄✂️ بازی سنگ کاغذ قیچی:
        • ورودی: 1 امتیاز
        • برنده: 2 امتیاز
        • بازنده: 0 امتیاز
        • مساوی: 1 امتیاز

        ⏰ زمان بازی: 30 ثانیه برای یافتن حریف
        ⏳ زمان انتخاب: 7 ثانیه
        """
        
        keyboard = [
            [InlineKeyboardButton("🪨📄✂️ شروع بازی", callback_data="start_rps")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش بخش VIP"""
        text = f"""
        ⭐ مزایای VIP:

        • 🛍️ تخفیف در خرید محصولات
        • 💰 بازگشت ۱۰٪ موجودی در case باخت
        • 👥 دعوت هر دوست {1.5} امتیاز
        • 🎮 امتیازات ویژه در بازی‌ها

        💎 قیمت‌ها:
        • هفته‌ای: {config.VIP_WEEKLY_PRICE} تومن
        • ماهانه: {config.VIP_MONTHLY_PRICE} تومن  
        • سالانه: {config.VIP_YEARLY_PRICE} تومن
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 خرید VIP", callback_data="buy_vip")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]
        ]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_rules(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش قوانین"""
        text = """
        📜 قوانین ربات:

        🛍️ فروشگاه:
        • خرید محصولات با امتیاز
        • تحویل فوری پس از خرید

        👥 دعوت دوستان:
        • دریافت امتیاز برای هر دعوت
        • امتیاز بیشتر برای کاربران VIP

        🎮 بازی‌ها:
        • هزینه ورود 1 امتیاز
        • برنده 2 امتیاز دریافت می‌کند
        • رعایت نوبت در بازی

        ⭐ VIP:
        • مزایای ویژه برای کاربران ویژه
        • تخفیف در خریدها
        • امتیاز بیشتر در دعوت

        ⚠️ توجه:
        • هرگونه تقلب منجر به مسدودی می‌شود
        • قوانین قابل تغییر هستند
        """
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]]
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل ادمین"""
        keyboard = [
            [InlineKeyboardButton("➕ افزودن محصول", callback_data="admin_add_product")],
            [InlineKeyboardButton("🗑️ حذف محصول", callback_data="admin_remove_product")],
            [InlineKeyboardButton("➕ افزودن کانال", callback_data="admin_add_channel")],
            [InlineKeyboardButton("🗑️ حذف کانال", callback_data="admin_remove_channel")],
            [InlineKeyboardButton("⭐ مدیریت VIP", callback_data="admin_manage_vip")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]
        ]
        
        await update.callback_query.edit_message_text(
            "⚙️ پنل مدیریت ادمین\n\nلطفاً یک گزینه انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def run(self):
        """اجرای ربات"""
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        
        # اضافه کردن handlerها
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        logger.info("ربات در حال اجراست...")
        self.application.run_polling()

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
