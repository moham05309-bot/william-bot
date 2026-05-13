"""
╔══════════════════════════════════════════╗
║     🌾 QuizFarm Bot v4.1 🌾              ║
║  نظام مسابقات + مزرعة + بنك متكامل      ║
║  👑 صاحب البوت: @x_m0_7a_m3d            ║
╠══════════════════════════════════════════╣
║  ✅ v4.1 — التحسينات:                   ║
║   • توكن محمي عبر ملف .env              ║
║   • حفظ آمن + نسخ احتياطي تلقائي       ║
║   • تحويل بنكي ذري (anti double-spend)  ║
║   • خلط الأسئلة (لا انحياز لـ B)        ║
║   • إشعارات الحصاد التلقائية            ║
║   • pagination للمتصدرين                ║
║   • تحدي أسبوعي بمكافأة كبيرة          ║
║   • معالج أخطاء عام                     ║
╚══════════════════════════════════════════╝

Requirements:
    pip install python-telegram-bot==20.7

تشغيل:
    python bot_v3.py

ملف .env (اختياري، أنشئه في نفس المجلد):
    BOT_TOKEN=توكنك_هنا
    OWNER_ID=رقمك_هنا
    SECRET_CODE=كودك_السري_هنا
"""

import logging
import random
import asyncio
import json
import os
import math
import threading
import shutil
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
    PreCheckoutQueryHandler
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ الإعدادات — يُقرأ من .env أو من المتغيرات المباشرة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# يمكنك إنشاء ملف .env بجانب البوت بهذا الشكل:
#   BOT_TOKEN=توكنك_هنا
#   OWNER_ID=رقمك_هنا
# أو استبدل القيم الافتراضية أدناه مباشرة

def _load_env():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "ضع_توكنك_هنا")   # ← ضع توكنك في ملف .env
OWNER      = "@x07_wy"
OWNER_ID   = int(os.environ.get("OWNER_ID", "8785789269"))   # ← ضع الـ ID في ملف .env
DB_FILE    = "quizfarm_data.json"
DB_BACKUP  = "quizfarm_data_backup.json"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⭐ حزم الشراء بنجوم تيليغرام
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STARS_PACKAGES = {
    "stars_s": {
        "name": "⭐ الحزمة الصغيرة",
        "stars": 50,
        "coins": 500,
        "farm_money": 300,
        "bank_balance": 1000,
        "desc": "500 🪙 + 300 💵 مزرعة + 1,000 💵 بنك",
    },
    "stars_m": {
        "name": "🌟 الحزمة المتوسطة",
        "stars": 150,
        "coins": 2000,
        "farm_money": 1000,
        "bank_balance": 5000,
        "desc": "2,000 🪙 + 1,000 💵 مزرعة + 5,000 💵 بنك",
    },
    "stars_l": {
        "name": "💎 الحزمة الكبيرة",
        "stars": 350,
        "coins": 6000,
        "farm_money": 3000,
        "bank_balance": 15000,
        "desc": "6,000 🪙 + 3,000 💵 مزرعة + 15,000 💵 بنك",
    },
    "stars_xl": {
        "name": "👑 حزمة البطل",
        "stars": 750,
        "coins": 15000,
        "farm_money": 8000,
        "bank_balance": 40000,
        "desc": "15,000 🪙 + 8,000 💵 مزرعة + 40,000 💵 بنك",
    },
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالات المحادثة للبنك
BANK_TRANSFER_ACCOUNT, BANK_TRANSFER_AMOUNT = range(2)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💾 قاعدة البيانات JSON
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_db_lock = threading.Lock()

def load_db() -> dict:
    for fname in [DB_FILE, DB_BACKUP]:
        if os.path.exists(fname):
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "users" in data:
                        if fname == DB_BACKUP:
                            logger.warning("تم التحميل من النسخة الاحتياطية!")
                        return data
            except Exception as e:
                logger.error(f"خطأ في تحميل {fname}: {e}")
    return {"users": {}, "bank_accounts": {}}

def save_db(db: dict):
    """حفظ آمن مع قفل thread ونسخة احتياطية"""
    with _db_lock:
        tmp_file = DB_FILE + ".tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            if os.path.exists(DB_FILE):
                shutil.copy2(DB_FILE, DB_BACKUP)
            os.replace(tmp_file, DB_FILE)
        except Exception as e:
            logger.error(f"خطأ في حفظ DB: {e}")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass

DB = load_db()

_save_pending = False

def mark_dirty():
    global _save_pending
    _save_pending = True

async def _periodic_save():
    global _save_pending
    while True:
        await asyncio.sleep(60)
        if _save_pending:
            save_db(DB)
            _save_pending = False

# تتبع من أُرسل له إشعار الحصاد (لتجنب الإرسال المتكرر)
_harvest_notified: dict = {}   # {user_id: set of crop planted_at keys}

async def _harvest_notifier(bot):
    """يراقب المحاصيل ويرسل إشعاراً عند النضج"""
    while True:
        await asyncio.sleep(120)   # فحص كل دقيقتين
        try:
            now = datetime.now()
            for uid_str, udata in list(DB["users"].items()):
                uid  = udata.get("id")
                if not uid:
                    continue
                farm = udata.get("farm", {})
                crops = farm.get("crops", [])
                has_gh = "greenhouse" in farm.get("buildings", [])
                notified = _harvest_notified.setdefault(uid, set())
                ready_new = []
                for crop in crops:
                    key = crop.get("planted_at", "")
                    tl  = farm_time_left(key, crop["grow_minutes"], has_gh)
                    if tl <= 0 and key not in notified:
                        sinfo = SEEDS.get(crop.get("seed_type", ""), {})
                        ready_new.append(sinfo.get("emoji", "🌱") + " " + sinfo.get("name", "محصول"))
                        notified.add(key)
                if ready_new:
                    try:
                        crops_text = " | ".join(ready_new[:5])
                        await bot.send_message(
                            chat_id=uid,
                            text=f"🌾 محاصيلك جاهزة للحصاد!\n\n{crops_text}\n\nاكتب: حصاد"
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"harvest notifier error: {e}")

def get_user(user_id: int, username: str = "", first_name: str = "") -> dict:
    uid = str(user_id)
    if uid not in DB["users"]:
        account_number = _generate_account_number()
        DB["users"][uid] = {
            # ━━ أساسيات ━━
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "registered_at": datetime.now().isoformat(),
            # ━━ نظام النقاط/المستوى ━━
            "points": 0,
            "coins": 500,
            "gems": 5,
            "level": 1,
            "exp": 0,
            "total_played": 0,
            "total_correct": 0,
            "total_wrong": 0,
            "best_streak": 0,
            "daily_played": None,
            "achievements": [],
            "challenge_wins": 0,
            "challenge_losses": 0,
            # ━━ المزرعة ━━
            "farm": {
                "level": 1,
                "exp": 0,
                "money": 200,
                "seeds": {},          # {"wheat": 5, "corn": 3, ...}
                "animals": {},        # {"chicken": 2, "cow": 1, ...}
                "crops": [],          # قائمة المحاصيل المزروعة
                "animal_products": [], # قائمة منتجات الحيوانات
                "storage": {},        # المخزن {"wheat_harvested": 10, ...}
                "last_active": datetime.now().isoformat(),
                "status": "active",   # active / neglected
                "total_harvests": 0,
                "total_sales": 0,
                "buildings": [],      # مباني المزرعة
                "workers": 0,
                "water": 100,         # مستوى الماء 0-100
                "soil_quality": 100,  # جودة التربة 0-100
            },
            # ━━ البنك ━━
            "bank": {
                "account_number": account_number,
                "balance": 1000,
                "transactions": [],   # آخر 20 معاملة
                "created_at": datetime.now().isoformat(),
                "loan": 0,
                "loan_due": None,
                "vip": False,
            },
        }
        DB["bank_accounts"][account_number] = user_id
        save_db(DB)
    else:
        # تحديث بيانات موجودة
        u = DB["users"][uid]
        if username:  u["username"]   = username
        if first_name: u["first_name"] = first_name
    return DB["users"][uid]

def save_user(user_id: int):
    """يعلّم DB بأنها تحتاج حفظ (الحفظ الفعلي يحدث كل 60 ثانية)"""
    mark_dirty()

def _generate_account_number() -> str:
    while True:
        num = str(random.randint(1000000000, 9999999999))
        if num not in DB["bank_accounts"]:
            return num

def get_user_by_account(account_number: str):
    uid = DB["bank_accounts"].get(account_number)
    if uid:
        return DB["users"].get(str(uid))
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌾 بيانات المزرعة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEEDS = {
    "wheat":    {"name": "قمح 🌾",    "price": 20,  "grow_minutes": 10,  "sell_price": 50,  "emoji": "🌾", "exp": 5},
    "corn":     {"name": "ذرة 🌽",    "price": 35,  "grow_minutes": 20,  "sell_price": 90,  "emoji": "🌽", "exp": 8},
    "potato":   {"name": "بطاطا 🥔",  "price": 40,  "grow_minutes": 30,  "sell_price": 110, "emoji": "🥔", "exp": 10},
    "tomato":   {"name": "طماطم 🍅",  "price": 50,  "grow_minutes": 45,  "sell_price": 140, "emoji": "🍅", "exp": 12},
    "carrot":   {"name": "جزر 🥕",    "price": 30,  "grow_minutes": 25,  "sell_price": 80,  "emoji": "🥕", "exp": 7},
    "strawberry":{"name":"فراولة 🍓", "price": 80,  "grow_minutes": 60,  "sell_price": 220, "emoji": "🍓", "exp": 18},
    "watermelon":{"name":"بطيخ 🍉",   "price": 100, "grow_minutes": 90,  "sell_price": 300, "emoji": "🍉", "exp": 25},
    "grape":    {"name": "عنب 🍇",    "price": 120, "grow_minutes": 120, "sell_price": 380, "emoji": "🍇", "exp": 30},
    "sunflower":{"name": "عباد شمس 🌻","price": 60, "grow_minutes": 50,  "sell_price": 170, "emoji": "🌻", "exp": 15},
    "rice":     {"name": "أرز 🍚",    "price": 45,  "grow_minutes": 35,  "sell_price": 120, "emoji": "🍚", "exp": 11},
}

ANIMALS = {
    "chicken": {"name": "دجاجة 🐔",  "price": 150, "produce_minutes": 30,  "product": "egg",  "product_name": "بيض 🥚",   "sell_price": 80,  "feed_cost": 15, "exp": 20},
    "cow":     {"name": "بقرة 🐄",   "price": 500, "produce_minutes": 120, "product": "milk", "product_name": "حليب 🥛",  "sell_price": 250, "feed_cost": 50, "exp": 60},
    "sheep":   {"name": "خروف 🐑",   "price": 350, "produce_minutes": 90,  "product": "wool", "product_name": "صوف 🧶",   "sell_price": 180, "feed_cost": 35, "exp": 40},
    "rabbit":  {"name": "أرنب 🐇",   "price": 200, "produce_minutes": 60,  "product": "fur",  "product_name": "فرو 🐰",   "sell_price": 120, "feed_cost": 20, "exp": 28},
    "bee":     {"name": "نحلة 🐝",   "price": 300, "produce_minutes": 240, "product": "honey","product_name": "عسل 🍯",   "sell_price": 400, "feed_cost": 10, "exp": 50},
    "horse":   {"name": "حصان 🐴",   "price": 800, "produce_minutes": 180, "product": "ride", "product_name": "ركوب 🏇",  "sell_price": 450, "feed_cost": 80, "exp": 90},
}

FARM_LEVELS = {
    1:  {"name": "مزرعة صغيرة 🌱",     "exp_needed": 0,    "max_crops": 3,  "max_animals": 2},
    2:  {"name": "مزرعة ناشئة 🌿",     "exp_needed": 100,  "max_crops": 5,  "max_animals": 3},
    3:  {"name": "مزرعة متوسطة 🌳",    "exp_needed": 250,  "max_crops": 8,  "max_animals": 5},
    4:  {"name": "مزرعة كبيرة 🏡",     "exp_needed": 500,  "max_crops": 12, "max_animals": 8},
    5:  {"name": "مزرعة متقدمة 🌾",    "exp_needed": 1000, "max_crops": 16, "max_animals": 12},
    6:  {"name": "مزرعة محترفة 🏆",    "exp_needed": 2000, "max_crops": 20, "max_animals": 15},
    7:  {"name": "مزرعة أسطورية 👑",   "exp_needed": 4000, "max_crops": 25, "max_animals": 20},
}

BUILDINGS = {
    "barn":       {"name": "إسطبل 🏠",      "price": 500,  "desc": "يزيد سعة الحيوانات +3"},
    "greenhouse": {"name": "بيت زجاجي 🏗️", "price": 800,  "desc": "يسرّع نمو المحاصيل 20%"},
    "well":       {"name": "بئر 💧",         "price": 300,  "desc": "يمنع نفاد الماء"},
    "silo":       {"name": "صومعة 🏰",       "price": 600,  "desc": "يضاعف سعة المخزن"},
    "market":     {"name": "سوق خاص 🏪",    "price": 1200, "desc": "يرفع أسعار البيع 15%"},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✨ الحيوانات النادرة — لا تُشترى، تُكتسب فقط
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RARE_ANIMALS = {
    # ━━ 🟢 غير عادي ━━
    "panda": {
        "name":            "الباندا 🐼",
        "rarity":          "غير عادي",
        "rarity_emoji":    "🟢",
        "rarity_stars":    "⭐⭐",
        "produce_minutes": 45,
        "product":         "خيزران_نادر",
        "product_name":    "خيزران نادر 🎋",
        "sell_price":      800,
        "how_to_get":      "وصّل مزرعتك للمستوى 5",
        "condition":       lambda u: u["farm"].get("level", 1) >= 5,
        "progress":        lambda u: f"مزرعتك المستوى {u['farm'].get('level',1)}/5",
    },
    "blue_fox": {
        "name":            "الثعلب الأزرق 🦊",
        "rarity":          "غير عادي",
        "rarity_emoji":    "🟢",
        "rarity_stars":    "⭐⭐",
        "produce_minutes": 60,
        "product":         "فرو_أزرق",
        "product_name":    "فرو أزرق 💙",
        "sell_price":      600,
        "how_to_get":      "العب 50 لعبة مسابقة",
        "condition":       lambda u: u.get("total_played", 0) >= 50,
        "progress":        lambda u: f"لعبت {u.get('total_played',0)}/50",
    },
    # ━━ 🔵 نادر ━━
    "golden_bee": {
        "name":            "النحلة الذهبية 🐝",
        "rarity":          "نادر",
        "rarity_emoji":    "🔵",
        "rarity_stars":    "⭐⭐⭐",
        "produce_minutes": 30,
        "product":         "عسل_ذهبي",
        "product_name":    "عسل ذهبي 🍯",
        "sell_price":      1500,
        "how_to_get":      "اجمع 10,000 عملة في أي وقت",
        "condition":       lambda u: u.get("coins", 0) >= 10000,
        "progress":        lambda u: f"عندك {u.get('coins',0):,}/10,000 عملة",
    },
    "snow_wolf": {
        "name":            "الذئب الثلجي 🐺",
        "rarity":          "نادر",
        "rarity_emoji":    "🔵",
        "rarity_stars":    "⭐⭐⭐",
        "produce_minutes": 90,
        "product":         "ناب_ثلجي",
        "product_name":    "ناب ثلجي ❄️",
        "sell_price":      1200,
        "how_to_get":      "فز بـ 20 تحدي ضد لاعبين",
        "condition":       lambda u: u.get("challenge_wins", 0) >= 20,
        "progress":        lambda u: f"فزت بـ {u.get('challenge_wins',0)}/20 تحدي",
    },
    "royal_octopus": {
        "name":            "الأخطبوط الملكي 🐙",
        "rarity":          "نادر",
        "rarity_emoji":    "🔵",
        "rarity_stars":    "⭐⭐⭐",
        "produce_minutes": 120,
        "product":         "حبر_سحري",
        "product_name":    "حبر سحري 🖤",
        "sell_price":      2000,
        "how_to_get":      "احصد 100 محصول في المزرعة",
        "condition":       lambda u: u["farm"].get("total_harvests", 0) >= 100,
        "progress":        lambda u: f"حصدت {u['farm'].get('total_harvests',0)}/100",
    },
    # ━━ 🟣 أسطوري ━━
    "unicorn": {
        "name":            "اليونيكورن 🦄",
        "rarity":          "أسطوري",
        "rarity_emoji":    "🟣",
        "rarity_stars":    "⭐⭐⭐⭐",
        "produce_minutes": 90,
        "product":         "قرن_سحري",
        "product_name":    "قرن سحري 🌈",
        "sell_price":      3000,
        "how_to_get":      "احصد 300 محصول + امتلك 3 مباني",
        "condition":       lambda u: (
            u["farm"].get("total_harvests", 0) >= 300 and
            len(u["farm"].get("buildings", [])) >= 3
        ),
        "progress":        lambda u: (
            f"حصدت {u['farm'].get('total_harvests',0)}/300 | "
            f"مبانيك {len(u['farm'].get('buildings',[]))}/3"
        ),
    },
    "golden_lion": {
        "name":            "الأسد الذهبي 🦁",
        "rarity":          "أسطوري",
        "rarity_emoji":    "🟣",
        "rarity_stars":    "⭐⭐⭐⭐",
        "produce_minutes": 180,
        "product":         "تاج_ذهبي",
        "product_name":    "تاج ذهبي 👑",
        "sell_price":      4000,
        "how_to_get":      "اجمع 1,000 نقطة مسابقة + فز بـ 30 تحدي",
        "condition":       lambda u: (
            u.get("points", 0) >= 1000 and
            u.get("challenge_wins", 0) >= 30
        ),
        "progress":        lambda u: (
            f"نقاطك {u.get('points',0)}/1,000 | "
            f"انتصاراتك {u.get('challenge_wins',0)}/30"
        ),
    },
    # ━━ 🔴 إلهي ━━
    "phoenix": {
        "name":            "طائر الفينيق 🦅",
        "rarity":          "إلهي",
        "rarity_emoji":    "🔴",
        "rarity_stars":    "⭐⭐⭐⭐⭐",
        "produce_minutes": 60,
        "product":         "ريشة_ذهبية",
        "product_name":    "ريشة ذهبية ✨",
        "sell_price":      2500,
        "how_to_get":      "العب 200 لعبة + حقق سلسلة 10 متتالية",
        "condition":       lambda u: (
            u.get("total_played", 0) >= 200 and
            u.get("best_streak", 0) >= 10
        ),
        "progress":        lambda u: (
            f"لعبت {u.get('total_played',0)}/200 | "
            f"أعلى سلسلة {u.get('best_streak',0)}/10"
        ),
    },
    "dragon": {
        "name":            "التنين 🐉",
        "rarity":          "إلهي",
        "rarity_emoji":    "🔴",
        "rarity_stars":    "⭐⭐⭐⭐⭐",
        "produce_minutes": 240,
        "product":         "حجر_التنين",
        "product_name":    "حجر التنين 💎",
        "sell_price":      8000,
        "how_to_get":      "فز بـ 100 تحدي + بنك 50,000 + مزرعة مستوى 7",
        "condition":       lambda u: (
            u.get("challenge_wins", 0) >= 100 and
            u["bank"].get("balance", 0) >= 50000 and
            u["farm"].get("level", 1) >= 7
        ),
        "progress":        lambda u: (
            f"انتصارات {u.get('challenge_wins',0)}/100 | "
            f"بنكك {u['bank'].get('balance',0):,}/50,000 | "
            f"مزرعتك {u['farm'].get('level',1)}/7"
        ),
    },
    # ━━ ⚫ كوني — يستلزم امتلاك الـ9 السابقة ━━
    "cosmos": {
        "name":            "إله الكون 🌌",
        "rarity":          "كوني",
        "rarity_emoji":    "⚫",
        "rarity_stars":    "⭐⭐⭐⭐⭐⭐",
        "produce_minutes": 360,
        "product":         "شظية_كونية",
        "product_name":    "شظية كونية 💫",
        "sell_price":      15000,
        "how_to_get":      "امتلك الحيوانات النادرة الـ9 السابقة كلها",
        "condition":       lambda u: all(
            a in u["farm"].get("rare_animals", [])
            for a in ["panda","blue_fox","golden_bee","snow_wolf",
                      "royal_octopus","unicorn","golden_lion","phoenix","dragon"]
        ),
        "progress":        lambda u: (
            f"عندك {sum(1 for a in ['panda','blue_fox','golden_bee','snow_wolf','royal_octopus','unicorn','golden_lion','phoenix','dragon'] if a in u['farm'].get('rare_animals',[]))}/9 حيوانات"
        ),
    },
}

RARE_RARITY_ORDER = ["غير عادي", "نادر", "أسطوري", "إلهي", "كوني"]

def check_rare_animals(db_user: dict) -> list:
    """يتحقق إذا المستخدم يستحق حيوان نادر جديد ويضيفه"""
    earned = []
    owned  = db_user["farm"].setdefault("rare_animals", [])
    for animal_id, animal in RARE_ANIMALS.items():
        if animal_id not in owned:
            try:
                if animal["condition"](db_user):
                    owned.append(animal_id)
                    earned.append((animal_id, animal))
            except Exception:
                pass
    return earned

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛠️ دوال مساعدة للمزرعة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_farm_level_info(farm_exp: int) -> tuple[int, dict]:
    lvl = 1
    for l, info in FARM_LEVELS.items():
        if farm_exp >= info["exp_needed"]:
            lvl = l
    return lvl, FARM_LEVELS[lvl]

def farm_time_left(planted_at: str, grow_minutes: int, has_greenhouse: bool = False) -> int:
    """الدقائق المتبقية للحصاد (سالبة = جاهز)"""
    planted = datetime.fromisoformat(planted_at)
    if has_greenhouse:
        grow_minutes = int(grow_minutes * 0.8)
    elapsed = (datetime.now() - planted).total_seconds() / 60
    return grow_minutes - elapsed

def format_time(minutes: float) -> str:
    if minutes <= 0:
        return "✅ جاهز للحصاد!"
    if minutes < 60:
        return f"{int(minutes)} دقيقة"
    hours = int(minutes // 60)
    mins  = int(minutes % 60)
    return f"{hours} ساعة و{mins} دقيقة"

def check_farm_neglect(farm: dict):
    """تحقق من إهمال المزرعة وطبّق العقوبات"""
    messages = []
    now = datetime.now()
    new_crops = []
    for crop in farm.get("crops", []):
        harvest_due = datetime.fromisoformat(crop["planted_at"]) + timedelta(minutes=crop["grow_minutes"])
        overdue_hours = (now - harvest_due).total_seconds() / 3600
        if overdue_hours > 2:  # متأخر أكثر من ساعتين
            decay_chance = min(0.8, 0.1 + overdue_hours * 0.05)
            if random.random() < decay_chance:
                messages.append(f"💀 فسدت محاصيل {SEEDS.get(crop['seed_type'], {}).get('emoji', '🌱')} بسبب الإهمال!")
                continue
        new_crops.append(crop)
    farm["crops"] = new_crops

    new_animals = []
    for animal in farm.get("animal_products", []):
        produce_due = datetime.fromisoformat(animal["started_at"]) + timedelta(minutes=animal["produce_minutes"])
        overdue_hours = (now - produce_due).total_seconds() / 3600
        if overdue_hours > 4:  # متأخر أكثر من 4 ساعات
            death_chance = min(0.6, 0.05 + overdue_hours * 0.03)
            if random.random() < death_chance:
                animal_key = animal.get("animal_type", "")
                aname = ANIMALS.get(animal_key, {}).get("name", "حيوان")
                messages.append(f"🪦 مات {aname} بسبب الإهمال!")
                # أزل الحيوان من قائمة الحيوانات
                if animal_key in farm["animals"] and farm["animals"][animal_key] > 0:
                    farm["animals"][animal_key] -= 1
                    if farm["animals"][animal_key] == 0:
                        del farm["animals"][animal_key]
                continue
        new_animals.append(animal)
    farm["animal_products"] = new_animals
    return messages

def add_farm_exp(farm: dict, exp: int) -> str:
    """أضف خبرة للمزرعة وتحقق من الترقية"""
    farm["exp"] = farm.get("exp", 0) + exp
    old_level = farm.get("level", 1)
    new_level, info = get_farm_level_info(farm["exp"])
    farm["level"] = new_level
    if new_level > old_level:
        farm["money"] += 200  # مكافأة ترقية
        return f"\n\n🎉 ترقية المزرعة! → {info['name']}\n💰 مكافأة: +200 💵"
    return ""

def has_building(farm: dict, building: str) -> bool:
    return building in farm.get("buildings", [])

def sell_price_multiplier(farm: dict) -> float:
    if has_building(farm, "market"):
        return 1.15
    return 1.0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📚 بنك الأسئلة (المحسن والمنقح)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUESTIONS = {
    "geography": [
        {"q": "ما هي عاصمة مصر؟", "options": ["A) الإسكندرية", "B) القاهرة", "C) الأقصر", "D) الجيزة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "من بنى الأهرامات؟", "options": ["A) الرومان", "B) الفراعنة", "C) الإغريق", "D) الفرس"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هي أكبر قارة في العالم؟", "options": ["A) إفريقيا", "B) أوروبا", "C) آسيا", "D) أمريكا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "من هو أول رئيس للولايات المتحدة؟", "options": ["A) أبراهام لنكولن", "B) جورج واشنطن", "C) توماس جيفرسون", "D) روزفلت"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو أطول نهر في العالم؟", "options": ["A) الأمازون", "B) النيل", "C) المسيسيبي", "D) الدانوب"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "في أي قارة تقع فرنسا؟", "options": ["A) آسيا", "B) أوروبا", "C) إفريقيا", "D) أمريكا"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما الحضارة التي قامت في بلاد الرافدين؟", "options": ["A) الفرعونية", "B) الرومانية", "C) السومرية", "D) الإغريقية"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هي عاصمة اليابان؟", "options": ["A) بكين", "B) سيول", "C) طوكيو", "D) بانكوك"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "من هو القائد الذي فتح مصر في الإسلام؟", "options": ["A) خالد بن الوليد", "B) عمرو بن العاص", "C) سعد بن أبي وقاص", "D) صلاح الدين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو أكبر محيط في العالم؟", "options": ["A) الأطلسي", "B) الهندي", "C) الهادئ", "D) المتجمد"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هي عاصمة إيطاليا؟", "options": ["A) ميلانو", "B) روما", "C) نابولي", "D) تورينو"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "في أي سنة اكتشف كولومبوس أمريكا؟", "options": ["A) 1492", "B) 1500", "C) 1480", "D) 1510"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هي أكبر دولة من حيث المساحة؟", "options": ["A) الصين", "B) كندا", "C) روسيا", "D) أمريكا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "من هو القائد المسلم في معركة حطين؟", "options": ["A) عمر بن الخطاب", "B) صلاح الدين الأيوبي", "C) طارق بن زياد", "D) هارون الرشيد"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي عاصمة كندا؟", "options": ["A) تورونتو", "B) أوتاوا", "C) مونتريال", "D) فانكوفر"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي الدولة التي فيها نهر الأمازون؟", "options": ["A) مصر", "B) البرازيل", "C) الهند", "D) الصين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "من هو مؤسس الدولة العباسية؟", "options": ["A) أبو العباس السفاح", "B) هارون الرشيد", "C) المنصور", "D) الأمين"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هي عاصمة أستراليا؟", "options": ["A) سيدني", "B) ملبورن", "C) كانبرا", "D) بيرث"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هي الحرب التي حدثت بين 1914 و1918؟", "options": ["A) العالمية الأولى", "B) العالمية الثانية", "C) الحرب الباردة", "D) حرب الخليج"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هي أكبر صحراء في العالم؟", "options": ["A) الربع الخالي", "B) الصحراء الكبرى", "C) جوبي", "D) القطب الجنوبي"], "answer": "D", "fact": "الإجابة الصحيحة هي D", "difficulty": "medium"},
        {"q": "ما هي عاصمة البرازيل؟", "options": ["A) ريو دي جانيرو", "B) ساو باولو", "C) برازيليا", "D) سالفادور"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "من هو القائد الذي فتح الأندلس؟", "options": ["A) صلاح الدين", "B) طارق بن زياد", "C) موسى بن نصير", "D) عمر بن عبد العزيز"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي أطول سلسلة جبلية في العالم؟", "options": ["A) الهيمالايا", "B) الأنديز", "C) الألب", "D) الأطلس"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "في أي سنة سقطت الأندلس (غرناطة)؟", "options": ["A) 1492", "B) 1453", "C) 1500", "D) 1480"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "hard"},
        {"q": "ما هي عاصمة تركيا؟", "options": ["A) إسطنبول", "B) أنقرة", "C) إزمير", "D) بورصة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو البحر الذي يفصل بين السعودية وإفريقيا؟", "options": ["A) المتوسط", "B) الأحمر", "C) الأسود", "D) قزوين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "من هو الإمبراطور الفرنسي الشهير؟", "options": ["A) لويس الرابع عشر", "B) نابليون بونابرت", "C) شارل ديغول", "D) هنري الرابع"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي الدولة التي تضم جبال الهيمالايا؟", "options": ["A) مصر", "B) الهند", "C) اليابان", "D) إسبانيا"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي المعركة التي انتصر فيها المسلمون على المغول؟", "options": ["A) بدر", "B) حطين", "C) عين جالوت", "D) اليرموك"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هي عاصمة الأرجنتين؟", "options": ["A) ليما", "B) سانتياغو", "C) بوينس آيرس", "D) كراكاس"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هي أقدم حضارة في التاريخ؟", "options": ["A) المصرية", "B) الرومانية", "C) السومرية", "D) الإغريقية"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هي عاصمة كازاخستان؟", "options": ["A) ألماتي", "B) أستانا", "C) طشقند", "D) باكو"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو القائد في معركة اليرموك؟", "options": ["A) خالد بن الوليد", "B) عمرو بن العاص", "C) سعد بن أبي وقاص", "D) علي بن أبي طالب"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "expert"},
        {"q": "ما هي أكبر جزيرة في العالم؟", "options": ["A) مدغشقر", "B) غرينلاند", "C) أستراليا", "D) اليابان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "في أي سنة سقطت القسطنطينية؟", "options": ["A) 1492", "B) 1453", "C) 1400", "D) 1503"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هي الدولة التي يمر بها نهر الدانوب؟", "options": ["A) مصر", "B) ألمانيا", "C) الهند", "D) الصين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو أول خليفة أموي؟", "options": ["A) يزيد بن معاوية", "B) معاوية بن أبي سفيان", "C) عبد الملك بن مروان", "D) الوليد بن عبد الملك"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هي عاصمة النرويج؟", "options": ["A) أوسلو", "B) ستوكهولم", "C) كوبنهاغن", "D) هلسنكي"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "expert"},
        {"q": "ما هو المضيق الذي يفصل آسيا عن أمريكا؟", "options": ["A) هرمز", "B) جبل طارق", "C) بيرينغ", "D) ملقا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هي الدولة التي كانت تسمى بلاد فارس؟", "options": ["A) العراق", "B) تركيا", "C) إيران", "D) سوريا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
    ],
    "science": [
        {"q": "ما هو الكوكب الذي نعيش عليه؟", "options": ["A) المريخ", "B) الأرض", "C) الزهرة", "D) عطارد"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الغاز الذي نتنفسه؟", "options": ["A) النيتروجين", "B) الأكسجين", "C) ثاني أكسيد الكربون", "D) الهيدروجين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم عدد الكواكب في المجموعة الشمسية؟", "options": ["A) 7", "B) 8", "C) 9", "D) 10"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو أقرب نجم إلى الأرض؟", "options": ["A) القمر", "B) الشمس", "C) المريخ", "D) زحل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هي حالة الماء عند درجة 0 مئوية؟", "options": ["A) غاز", "B) سائل", "C) صلب", "D) بلازما"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو العضو المسؤول عن التنفس في الإنسان؟", "options": ["A) القلب", "B) الكبد", "C) الرئتان", "D) المعدة"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو الحيوان الذي يبيض؟", "options": ["A) القط", "B) الكلب", "C) الدجاجة", "D) الحصان"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو مصدر الطاقة الرئيسي للأرض؟", "options": ["A) القمر", "B) الشمس", "C) الرياح", "D) الماء"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو عدد حواس الإنسان؟", "options": ["A) 4", "B) 5", "C) 6", "D) 7"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الكوكب الأحمر؟", "options": ["A) الأرض", "B) المشتري", "C) المريخ", "D) نبتون"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو العنصر الكيميائي الذي رمزه H؟", "options": ["A) هيليوم", "B) هيدروجين", "C) حديد", "D) نحاس"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو أكبر عضو في جسم الإنسان؟", "options": ["A) القلب", "B) الكبد", "C) الجلد", "D) الدماغ"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو الكوكب الأكبر في المجموعة الشمسية؟", "options": ["A) الأرض", "B) المشتري", "C) زحل", "D) نبتون"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو العضو الذي يضخ الدم في الجسم؟", "options": ["A) الرئتان", "B) الدماغ", "C) القلب", "D) المعدة"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو الغاز الذي تستخدمه النباتات في البناء الضوئي؟", "options": ["A) الأكسجين", "B) النيتروجين", "C) ثاني أكسيد الكربون", "D) الهيدروجين"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هي وحدة قياس القوة؟", "options": ["A) جول", "B) واط", "C) نيوتن", "D) متر"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو الكوكب الأقرب إلى الشمس؟", "options": ["A) الأرض", "B) الزهرة", "C) عطارد", "D) المريخ"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو السائل الموجود في جسم الإنسان وينقل الغذاء؟", "options": ["A) الماء", "B) الدم", "C) اللعاب", "D) العصارة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي حاسة الشم مرتبطة بأي عضو؟", "options": ["A) العين", "B) الأنف", "C) الأذن", "D) اللسان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو اسم المجرة التي نعيش فيها؟", "options": ["A) أندروميدا", "B) درب التبانة", "C) الحلزونية", "D) القزمة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو العنصر الأكثر وفرة في الكون؟", "options": ["A) الأكسجين", "B) الهيدروجين", "C) الهيليوم", "D) الكربون"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي العملية التي تقوم بها النباتات لصنع غذائها؟", "options": ["A) التنفس", "B) البناء الضوئي", "C) الهضم", "D) الامتصاص"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي وحدة قياس الطاقة؟", "options": ["A) نيوتن", "B) جول", "C) متر", "D) واط"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "كم عدد عظام جسم الإنسان البالغ؟", "options": ["A) 200", "B) 206", "C) 210", "D) 215"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو الكوكب المعروف بحلقاته؟", "options": ["A) المريخ", "B) زحل", "C) المشتري", "D) أورانوس"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو أسرع حيوان في العالم؟", "options": ["A) الفهد", "B) الصقر الشاهين", "C) الأسد", "D) النمر"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي طبقة الأوزون مسؤولة عن؟", "options": ["A) إنتاج الأكسجين", "B) حجب الأشعة فوق البنفسجية", "C) تكوين السحب", "D) تبريد الأرض"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو اسم العملية التي يتحول فيها السائل إلى غاز؟", "options": ["A) التكثف", "B) التبخر", "C) التجمد", "D) الانصهار"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو العضو المسؤول عن التفكير؟", "options": ["A) القلب", "B) الدماغ", "C) الكبد", "D) الرئتان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو أقسى معدن طبيعي؟", "options": ["A) الحديد", "B) الذهب", "C) الألماس", "D) الفضة"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو عدد الكروموسومات في جسم الإنسان؟", "options": ["A) 44", "B) 45", "C) 46", "D) 48"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هي أسرع سرعة في الكون؟", "options": ["A) سرعة الصوت", "B) سرعة الضوء", "C) سرعة الرياح", "D) سرعة الأرض"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو العنصر الذي عدده الذري 6؟", "options": ["A) أكسجين", "B) كربون", "C) نيتروجين", "D) هيدروجين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو اسم أقرب مجرة إلى درب التبانة؟", "options": ["A) أندروميدا", "B) درب اللبانة", "C) القزمة", "D) الحلزونية"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "expert"},
        {"q": "ما هي وحدة قياس شدة التيار الكهربائي؟", "options": ["A) فولت", "B) أمبير", "C) واط", "D) أوم"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو الغاز الأكثر انتشارًا في الغلاف الجوي؟", "options": ["A) الأكسجين", "B) النيتروجين", "C) الهيدروجين", "D) ثاني أكسيد الكربون"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو اسم العملية التي يتحول فيها الغاز إلى سائل؟", "options": ["A) تبخر", "B) تكثف", "C) تجمد", "D) انصهار"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو اسم أكبر محيط في العالم؟", "options": ["A) الأطلسي", "B) الهندي", "C) الهادئ", "D) المتجمد"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هو الجهاز المسؤول عن نقل الإشارات في الجسم؟", "options": ["A) الهضمي", "B) العصبي", "C) التنفسي", "D) الدوري"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو العنصر الذي رمزه Fe؟", "options": ["A) فضة", "B) ذهب", "C) حديد", "D) نحاس"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
    ],
    "history": [
        {"q": "ما هي عاصمة مصر؟", "options": ["A) الإسكندرية", "B) القاهرة", "C) الأقصر", "D) الجيزة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "من بنى الأهرامات؟", "options": ["A) الرومان", "B) الفراعنة", "C) الإغريق", "D) الفرس"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هي أكبر قارة في العالم؟", "options": ["A) إفريقيا", "B) أوروبا", "C) آسيا", "D) أمريكا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "من هو أول رئيس للولايات المتحدة؟", "options": ["A) أبراهام لنكولن", "B) جورج واشنطن", "C) توماس جيفرسون", "D) روزفلت"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو أطول نهر في العالم؟", "options": ["A) الأمازون", "B) النيل", "C) المسيسيبي", "D) الدانوب"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "في أي قارة تقع فرنسا؟", "options": ["A) آسيا", "B) أوروبا", "C) إفريقيا", "D) أمريكا"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما الحضارة التي قامت في بلاد الرافدين؟", "options": ["A) الفرعونية", "B) الرومانية", "C) السومرية", "D) الإغريقية"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هي عاصمة اليابان؟", "options": ["A) بكين", "B) سيول", "C) طوكيو", "D) بانكوك"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "من هو القائد الذي فتح مصر في الإسلام؟", "options": ["A) خالد بن الوليد", "B) عمرو بن العاص", "C) سعد بن أبي وقاص", "D) صلاح الدين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو أكبر محيط في العالم؟", "options": ["A) الأطلسي", "B) الهندي", "C) الهادئ", "D) المتجمد"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هي عاصمة إيطاليا؟", "options": ["A) ميلانو", "B) روما", "C) نابولي", "D) تورينو"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "في أي سنة اكتشف كولومبوس أمريكا؟", "options": ["A) 1492", "B) 1500", "C) 1480", "D) 1510"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هي أكبر دولة من حيث المساحة؟", "options": ["A) الصين", "B) كندا", "C) روسيا", "D) أمريكا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "من هو القائد المسلم في معركة حطين؟", "options": ["A) عمر بن الخطاب", "B) صلاح الدين الأيوبي", "C) طارق بن زياد", "D) هارون الرشيد"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي عاصمة كندا؟", "options": ["A) تورونتو", "B) أوتاوا", "C) مونتريال", "D) فانكوفر"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي الدولة التي فيها نهر الأمازون؟", "options": ["A) مصر", "B) البرازيل", "C) الهند", "D) الصين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "من هو مؤسس الدولة العباسية؟", "options": ["A) أبو العباس السفاح", "B) هارون الرشيد", "C) المنصور", "D) الأمين"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هي عاصمة أستراليا؟", "options": ["A) سيدني", "B) ملبورن", "C) كانبرا", "D) بيرث"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هي الحرب التي حدثت بين 1914 و1918؟", "options": ["A) العالمية الأولى", "B) العالمية الثانية", "C) الحرب الباردة", "D) حرب الخليج"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هي أكبر صحراء في العالم؟", "options": ["A) الربع الخالي", "B) الصحراء الكبرى", "C) جوبي", "D) القطب الجنوبي"], "answer": "D", "fact": "الإجابة الصحيحة هي D", "difficulty": "medium"},
        {"q": "ما هي عاصمة البرازيل؟", "options": ["A) ريو دي جانيرو", "B) ساو باولو", "C) برازيليا", "D) سالفادور"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "من هو القائد الذي فتح الأندلس؟", "options": ["A) صلاح الدين", "B) طارق بن زياد", "C) موسى بن نصير", "D) عمر بن عبد العزيز"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي أطول سلسلة جبلية في العالم؟", "options": ["A) الهيمالايا", "B) الأنديز", "C) الألب", "D) الأطلس"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "في أي سنة سقطت الأندلس (غرناطة)؟", "options": ["A) 1492", "B) 1453", "C) 1500", "D) 1480"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "hard"},
        {"q": "ما هي عاصمة تركيا؟", "options": ["A) إسطنبول", "B) أنقرة", "C) إزمير", "D) بورصة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو البحر الذي يفصل بين السعودية وإفريقيا؟", "options": ["A) المتوسط", "B) الأحمر", "C) الأسود", "D) قزوين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "من هو الإمبراطور الفرنسي الشهير؟", "options": ["A) لويس الرابع عشر", "B) نابليون بونابرت", "C) شارل ديغول", "D) هنري الرابع"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي الدولة التي تضم جبال الهيمالايا؟", "options": ["A) مصر", "B) الهند", "C) اليابان", "D) إسبانيا"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي المعركة التي انتصر فيها المسلمون على المغول؟", "options": ["A) بدر", "B) حطين", "C) عين جالوت", "D) اليرموك"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هي عاصمة الأرجنتين؟", "options": ["A) ليما", "B) سانتياغو", "C) بوينس آيرس", "D) كراكاس"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هي أقدم حضارة في التاريخ؟", "options": ["A) المصرية", "B) الرومانية", "C) السومرية", "D) الإغريقية"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هي عاصمة كازاخستان؟", "options": ["A) ألماتي", "B) أستانا", "C) طشقند", "D) باكو"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو القائد في معركة اليرموك؟", "options": ["A) خالد بن الوليد", "B) عمرو بن العاص", "C) سعد بن أبي وقاص", "D) علي بن أبي طالب"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "expert"},
        {"q": "ما هي أكبر جزيرة في العالم؟", "options": ["A) مدغشقر", "B) غرينلاند", "C) أستراليا", "D) اليابان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "في أي سنة سقطت القسطنطينية؟", "options": ["A) 1492", "B) 1453", "C) 1400", "D) 1503"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هي الدولة التي يمر بها نهر الدانوب؟", "options": ["A) مصر", "B) ألمانيا", "C) الهند", "D) الصين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو أول خليفة أموي؟", "options": ["A) يزيد بن معاوية", "B) معاوية بن أبي سفيان", "C) عبد الملك بن مروان", "D) الوليد بن عبد الملك"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هي عاصمة النرويج؟", "options": ["A) أوسلو", "B) ستوكهولم", "C) كوبنهاغن", "D) هلسنكي"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "expert"},
        {"q": "ما هو المضيق الذي يفصل آسيا عن أمريكا؟", "options": ["A) هرمز", "B) جبل طارق", "C) بيرينغ", "D) ملقا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هي الدولة التي كانت تسمى بلاد فارس؟", "options": ["A) العراق", "B) تركيا", "C) إيران", "D) سوريا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
    ],
    "sports": [
        {"q": "كم عدد اللاعبين في فريق كرة القدم داخل الملعب؟", "options": ["A) 9", "B) 10", "C) 11", "D) 12"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما اسم البطولة العالمية لكرة القدم؟", "options": ["A) دوري الأبطال", "B) كأس العالم", "C) كأس آسيا", "D) الدوري الأوروبي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم مدة مباراة كرة القدم؟", "options": ["A) 60 دقيقة", "B) 70 دقيقة", "C) 80 دقيقة", "D) 90 دقيقة"], "answer": "D", "fact": "الإجابة الصحيحة هي D", "difficulty": "easy"},
        {"q": "ما هو لون البطاقة التي تعني الطرد؟", "options": ["A) أصفر", "B) أحمر", "C) أخضر", "D) أزرق"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم عدد الأشواط في المباراة؟", "options": ["A) 1", "B) 2", "C) 3", "D) 4"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو مركز اللاعب الذي يحمي المرمى؟", "options": ["A) مدافع", "B) حارس", "C) مهاجم", "D) وسط"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما اسم الجهة المنظمة لكأس العالم؟", "options": ["A) UEFA", "B) FIFA", "C) CAF", "D) AFC"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هي الدولة التي فازت بكأس العالم 2018؟", "options": ["A) ألمانيا", "B) فرنسا", "C) البرازيل", "D) الأرجنتين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم عدد الحكام في المباراة (داخل الملعب)؟", "options": ["A) 1", "B) 2", "C) 3", "D) 4"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "easy"},
        {"q": "ما هو اسم البطولة الأوروبية للأندية؟", "options": ["A) كأس العالم", "B) دوري أبطال أوروبا", "C) كأس آسيا", "D) كوبا أمريكا"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "من هو اللاعب المعروف بلقب \"الدون\"؟", "options": ["A) ميسي", "B) رونالدو", "C) نيمار", "D) مبابي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "كم عدد كؤوس العالم التي فازت بها البرازيل؟", "options": ["A) 3", "B) 4", "C) 5", "D) 6"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "من هو أفضل هداف في تاريخ كأس العالم؟", "options": ["A) بيليه", "B) كلوزه", "C) رونالدو", "D) ميسي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "في أي دولة أقيم كأس العالم 2014؟", "options": ["A) ألمانيا", "B) البرازيل", "C) روسيا", "D) قطر"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما اسم نادي برشلونة ملعبه؟", "options": ["A) سانتياغو برنابيو", "B) كامب نو", "C) أولد ترافورد", "D) أنفيلد"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "من فاز بكأس العالم 2022؟", "options": ["A) فرنسا", "B) البرازيل", "C) الأرجنتين", "D) إسبانيا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "كم عدد بطولات دوري أبطال أوروبا لريال مدريد (تقريبًا)؟", "options": ["A) 10", "B) 12", "C) 14", "D) 16"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما اسم البطولة في أمريكا الجنوبية؟", "options": ["A) يورو", "B) كوبا أمريكا", "C) كأس آسيا", "D) دوري الأبطال"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "من هو اللاعب الأرجنتيني الشهير؟", "options": ["A) رونالدو", "B) ميسي", "C) نيمار", "D) مودريتش"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو اسم الاتحاد الأوروبي لكرة القدم؟", "options": ["A) FIFA", "B) UEFA", "C) CAF", "D) AFC"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "في أي سنة أقيم أول كأس عالم؟", "options": ["A) 1920", "B) 1930", "C) 1940", "D) 1950"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "من فاز بأول كأس عالم؟", "options": ["A) البرازيل", "B) ألمانيا", "C) الأوروغواي", "D) إيطاليا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "من هو أكثر لاعب فاز بالكرة الذهبية (حتى 2023)؟", "options": ["A) رونالدو", "B) ميسي", "C) زيدان", "D) كرويف"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "كم عدد بطولات كأس العالم لألمانيا؟", "options": ["A) 2", "B) 3", "C) 4", "D) 5"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو اسم ملعب ريال مدريد؟", "options": ["A) كامب نو", "B) برنابيو", "C) أنفيلد", "D) الاتحاد"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "من هو هداف ريال مدريد التاريخي؟", "options": ["A) بنزيما", "B) رونالدو", "C) راؤول", "D) بيل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي الدولة التي استضافت كأس العالم 2010؟", "options": ["A) البرازيل", "B) جنوب إفريقيا", "C) ألمانيا", "D) اليابان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "من هو المدرب الذي فاز بكأس العالم 2014؟", "options": ["A) مورينيو", "B) لو", "C) غوارديولا", "D) أنشيلوتي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو عدد بطولات كأس العالم لإيطاليا؟", "options": ["A) 2", "B) 3", "C) 4", "D) 5"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "من هو النادي الأكثر تتويجًا بدوري الأبطال؟", "options": ["A) برشلونة", "B) بايرن", "C) ريال مدريد", "D) ميلان"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "من سجل \"يد الله\" الشهيرة؟", "options": ["A) بيليه", "B) مارادونا", "C) ميسي", "D) رونالدو"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "في أي سنة فازت إسبانيا بكأس العالم؟", "options": ["A) 2006", "B) 2008", "C) 2010", "D) 2012"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "من هو أكثر منتخب وصولًا للنهائي؟", "options": ["A) البرازيل", "B) ألمانيا", "C) الأرجنتين", "D) إيطاليا"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "كم عدد بطولات كأس العالم لفرنسا؟", "options": ["A) 1", "B) 2", "C) 3", "D) 4"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو أول لاعب عربي يسجل في كأس العالم؟", "options": ["A) ماجر", "B) التومي", "C) عبد الرحمن فوزي", "D) صلاح"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هو أكبر فوز في تاريخ كأس العالم؟", "options": ["A) 8-0", "B) 9-0", "C) 10-1", "D) 7-1"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو اللاعب الذي فاز بكأس العالم كلاعب ومدرب؟", "options": ["A) زيدان", "B) بيكنباور", "C) مارادونا", "D) بيليه"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو النادي الذي يُلقب بالريدز؟", "options": ["A) مانشستر", "B) ليفربول", "C) آرسنال", "D) تشيلسي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو هداف كأس العالم 2018؟", "options": ["A) مبابي", "B) كين", "C) لوكاكو", "D) غريزمان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو المنتخب الذي فاز بيورو 2016؟", "options": ["A) فرنسا", "B) ألمانيا", "C) البرتغال", "D) إسبانيا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
    ],
    "technology": [
        {"q": "ما هو الذكاء الاصطناعي؟", "options": ["A) نوع من الأجهزة", "B) قدرة الحاسوب على محاكاة الذكاء البشري", "C) لعبة إلكترونية", "D) لغة برمجة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الهاتف الذكي؟", "options": ["A) جهاز للاتصال فقط", "B) جهاز يحتوي على تطبيقات ونظام تشغيل", "C) تلفاز صغير", "D) كاميرا فقط"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو نظام تشغيل مشهور للهواتف؟", "options": ["A) Windows", "B) Android", "C) Linux", "D) macOS"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الحاسوب المحمول؟", "options": ["A) Desktop", "B) Laptop", "C) Server", "D) Router"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الإنترنت؟", "options": ["A) جهاز", "B) شبكة عالمية", "C) برنامج", "D) لعبة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الروبوت؟", "options": ["A) إنسان آلي", "B) برنامج فقط", "C) جهاز تلفاز", "D) موقع"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "easy"},
        {"q": "ما هي الشركة المطورة لنظام iOS؟", "options": ["A) Google", "B) Apple", "C) Microsoft", "D) Amazon"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو محرك البحث الأشهر؟", "options": ["A) Bing", "B) Yahoo", "C) Google", "D) DuckDuckGo"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو البريد الإلكتروني؟", "options": ["A) رسالة ورقية", "B) رسالة رقمية", "C) مكالمة", "D) فيديو"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو التطبيق؟", "options": ["A) جهاز", "B) برنامج صغير", "C) موقع فقط", "D) لعبة فقط"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو تعلم الآلة؟", "options": ["A) برمجة عادية", "B) تعليم الحاسوب من البيانات", "C) لعبة", "D) نظام تشغيل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي لغة Python؟", "options": ["A) لغة تصميم", "B) لغة برمجة", "C) نظام تشغيل", "D) قاعدة بيانات"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو الـ CPU؟", "options": ["A) وحدة التخزين", "B) وحدة المعالجة", "C) الشاشة", "D) الشبكة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو الـ RAM؟", "options": ["A) تخزين دائم", "B) تخزين مؤقت", "C) معالج", "D) كرت شاشة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو التخزين السحابي؟", "options": ["A) تخزين على القرص", "B) تخزين عبر الإنترنت", "C) تخزين في RAM", "D) تخزين خارجي فقط"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو الذكاء الاصطناعي التوليدي؟", "options": ["A) ذكاء لإصلاح الأجهزة", "B) ذكاء ينشئ محتوى جديد", "C) ذكاء للتحليل فقط", "D) ذكاء للشبكات"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو الـ GPU؟", "options": ["A) معالج الرسوميات", "B) وحدة تخزين", "C) برنامج", "D) نظام تشغيل"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هو ChatGPT؟", "options": ["A) جهاز", "B) نموذج ذكاء اصطناعي", "C) لعبة", "D) نظام تشغيل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو النظام الذي يدير الحاسوب؟", "options": ["A) المتصفح", "B) نظام التشغيل", "C) التطبيق", "D) السيرفر"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي الشبكة المحلية؟", "options": ["A) LAN", "B) WAN", "C) MAN", "D) PAN"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هو Big Data؟", "options": ["A) بيانات صغيرة", "B) بيانات ضخمة ومعقدة", "C) برنامج", "D) جهاز"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو API؟", "options": ["A) برنامج تشغيل", "B) واجهة برمجة التطبيقات", "C) لغة برمجة", "D) نظام تشغيل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو التعلم العميق؟", "options": ["A) نوع من الشبكات", "B) نوع من تعلم الآلة", "C) نظام تشغيل", "D) برنامج عادي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو الخادم (Server)؟", "options": ["A) جهاز شخصي", "B) جهاز يقدم خدمات للأجهزة الأخرى", "C) شاشة", "D) برنامج فقط"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو HTTP؟", "options": ["A) لغة برمجة", "B) بروتوكول نقل", "C) نظام تشغيل", "D) جهاز"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو الذكاء الاصطناعي الضيق؟", "options": ["A) ذكاء عام", "B) ذكاء لمهمة محددة", "C) ذكاء بشري", "D) ذكاء كامل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو SQL؟", "options": ["A) لغة تصميم", "B) لغة قواعد بيانات", "C) نظام تشغيل", "D) بروتوكول"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو IoT؟", "options": ["A) إنترنت الأشياء", "B) نظام تشغيل", "C) جهاز", "D) لغة"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "hard"},
        {"q": "ما هو التعلم غير المراقب؟", "options": ["A) تعلم ببيانات مصنفة", "B) تعلم بدون بيانات مصنفة", "C) تعلم يدوي", "D) تعلم عبر الإنترنت"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو الأمن السيبراني؟", "options": ["A) تصميم مواقع", "B) حماية الأنظمة والبيانات", "C) برمجة ألعاب", "D) تخزين بيانات"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو NLP؟", "options": ["A) معالجة الصور", "B) معالجة اللغة الطبيعية", "C) شبكة", "D) نظام تشغيل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو TensorFlow؟", "options": ["A) جهاز", "B) مكتبة تعلم آلة", "C) نظام تشغيل", "D) لعبة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو Blockchain؟", "options": ["A) قاعدة بيانات موزعة", "B) برنامج", "C) جهاز", "D) نظام تشغيل"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "expert"},
        {"q": "ما هو التدريب (Training) في AI؟", "options": ["A) تشغيل البرنامج", "B) تعليم النموذج من البيانات", "C) تخزين البيانات", "D) حذف البيانات"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو النموذج اللغوي؟", "options": ["A) برنامج تصميم", "B) نموذج يفهم ويولد نصوص", "C) جهاز", "D) شبكة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو Cloud Computing؟", "options": ["A) حوسبة محلية", "B) حوسبة عبر الإنترنت", "C) جهاز", "D) برنامج"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو Prompt في AI؟", "options": ["A) جهاز", "B) أمر أو نص يُعطى للنموذج", "C) برنامج", "D) شبكة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو Neural Network؟", "options": ["A) شبكة إنترنت", "B) شبكة عصبية اصطناعية", "C) جهاز", "D) نظام تشغيل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو Data Mining؟", "options": ["A) حذف البيانات", "B) استخراج المعرفة من البيانات", "C) تخزين البيانات", "D) نقل البيانات"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو Algorithm؟", "options": ["A) جهاز", "B) مجموعة خطوات لحل مشكلة", "C) نظام تشغيل", "D) شبكة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
    ],
    "programming": [
        {"q": "ما هي لغة تستخدم لتصميم صفحات الويب؟", "options": ["A) Python", "B) HTML", "C) C++", "D) Java"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الوسم المستخدم لكتابة عنوان في HTML؟", "options": ["A) <p>", "B) <div>", "C) <h1>", "D) <span>"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هي اللغة المستخدمة لتنسيق صفحات الويب؟", "options": ["A) CSS", "B) HTML", "C) Python", "D) SQL"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "easy"},
        {"q": "ما هو الرمز المستخدم للتعليق في بايثون؟", "options": ["A) //", "B) <!-- -->", "C) #", "D) **"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو ناتج print(2 + 3) في بايثون؟", "options": ["A) 23", "B) 5", "C) 6", "D) خطأ"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو الجهاز المسؤول عن المعالجة في الحاسوب؟", "options": ["A) RAM", "B) CPU", "C) HDD", "D) GPU"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو اختصار RAM؟", "options": ["A) Random Access Memory", "B) Read Access Memory", "C) Run All Memory", "D) Rapid Access Machine"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "easy"},
        {"q": "ما هو الوسم المستخدم لإضافة صورة في HTML؟", "options": ["A) <img>", "B) <pic>", "C) <image>", "D) <src>"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "easy"},
        {"q": "ما هي لغة برمجة مشهورة وسهلة للمبتدئين؟", "options": ["A) Assembly", "B) Python", "C) C", "D) Rust"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو المتصفح؟", "options": ["A) برنامج لكتابة الكود", "B) برنامج لتصفح الإنترنت", "C) برنامج تصميم", "D) نظام تشغيل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو وسم الرابط في HTML؟", "options": ["A) <link>", "B) <a>", "C) <href>", "D) <url>"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ماذا تعني CSS؟", "options": ["A) Computer Style Sheets", "B) Creative Style System", "C) Cascading Style Sheets", "D) Color Style Sheets"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو ناتج print(10 // 3) في بايثون؟", "options": ["A) 3.3", "B) 3", "C) 4", "D) 10"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي وظيفة GPU؟", "options": ["A) تخزين البيانات", "B) معالجة الرسوميات", "C) تشغيل النظام", "D) إدارة الشبكة"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو نوع المتغير الناتج عن 3.14 في بايثون؟", "options": ["A) int", "B) float", "C) str", "D) bool"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو الوسم لإنشاء قائمة غير مرتبة؟", "options": ["A) <ol>", "B) <ul>", "C) <li>", "D) <list>"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو ناتج print(\"Hi\" * 2)؟", "options": ["A) Hi2", "B) HiHi", "C) خطأ", "D) 2Hi"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي وحدة التخزين الدائمة؟", "options": ["A) RAM", "B) Cache", "C) HDD/SSD", "D) CPU"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو الامتداد لملفات بايثون؟", "options": ["A) .py", "B) .js", "C) .html", "D) .exe"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "medium"},
        {"q": "ما هو وسم الفقرة في HTML؟", "options": ["A) <text>", "B) <p>", "C) <para>", "D) <h>"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو ناتج print(2 ** 3)؟", "options": ["A) 6", "B) 8", "C) 9", "D) 5"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هي خاصية CSS لتغيير لون النص؟", "options": ["A) font-color", "B) text-style", "C) color", "D) background"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو نوع البيانات True في بايثون؟", "options": ["A) int", "B) str", "C) bool", "D) float"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو العنصر المسؤول عن تشغيل البرامج؟", "options": ["A) RAM", "B) CPU", "C) GPU", "D) HDD"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو ناتج len(\"Hello\")؟", "options": ["A) 4", "B) 5", "C) 6", "D) خطأ"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو الوسم لإنشاء جدول في HTML؟", "options": ["A) <table>", "B) <tr>", "C) <td>", "D) <tab>"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "hard"},
        {"q": "ما هي خاصية CSS لتغيير حجم الخط؟", "options": ["A) font-size", "B) text-size", "C) size", "D) font-style"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "hard"},
        {"q": "ما هو ناتج print(5 % 2)؟", "options": ["A) 2", "B) 3", "C) 1", "D) 0"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو نوع البيانات للنص في بايثون؟", "options": ["A) int", "B) string", "C) str", "D) text"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو اختصار CPU؟", "options": ["A) Central Process Unit", "B) Central Processing Unit", "C) Computer Processing Unit", "D) Core Processing Unit"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو ناتج print(type(10))؟", "options": ["A) int", "B) <class 'int'>", "C) number", "D) type int"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هي خاصية CSS لتوسيط النص؟", "options": ["A) align", "B) text-align", "C) center-text", "D) align-text"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو ناتج print(bool(0))؟", "options": ["A) True", "B) False", "C) 0", "D) خطأ"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو البروتوكول المستخدم لنقل صفحات الويب؟", "options": ["A) FTP", "B) HTTP", "C) SMTP", "D) TCP"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو ناتج print(3 == \"3\")؟", "options": ["A) True", "B) False", "C) 3", "D) خطأ"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو دور RAM؟", "options": ["A) تخزين دائم", "B) تخزين مؤقت", "C) معالجة البيانات", "D) عرض الصور"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو الوسم لإنشاء نموذج (Form) في HTML؟", "options": ["A) <input>", "B) <form>", "C) <data>", "D) <submit>"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو ناتج print([1,2,3][1])؟", "options": ["A) 1", "B) 2", "C) 3", "D) خطأ"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو نوع البيانات لقيمة None في بايثون؟", "options": ["A) null", "B) NoneType", "C) void", "D) empty"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو نظام التشغيل؟", "options": ["A) برنامج لتصفح الإنترنت", "B) برنامج يدير موارد الحاسوب", "C) لغة برمجة", "D) جهاز مادي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
    ],
    "math": [
        {"q": "كم حاصل 2 + 3؟", "options": ["A) 4", "B) 5", "C) 6", "D) 7"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم حاصل 10 - 4؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم حاصل 3 × 3؟", "options": ["A) 6", "B) 7", "C) 8", "D) 9"], "answer": "D", "fact": "الإجابة الصحيحة هي D", "difficulty": "easy"},
        {"q": "كم حاصل 12 ÷ 4؟", "options": ["A) 2", "B) 3", "C) 4", "D) 5"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو العدد التالي: 2، 4، 6، ؟", "options": ["A) 7", "B) 8", "C) 9", "D) 10"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم عدد أضلاع المثلث؟", "options": ["A) 2", "B) 3", "C) 4", "D) 5"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم حاصل 5 + 5 × 2؟", "options": ["A) 20", "B) 15", "C) 10", "D) 25"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما هو نصف 20؟", "options": ["A) 5", "B) 10", "C) 15", "D) 20"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم حاصل 9 - 3؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم حاصل 7 + 2؟", "options": ["A) 8", "B) 9", "C) 10", "D) 11"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم حاصل 15 × 2؟", "options": ["A) 20", "B) 25", "C) 30", "D) 35"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "كم حاصل 100 ÷ 5؟", "options": ["A) 10", "B) 15", "C) 20", "D) 25"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو مربع العدد 6؟", "options": ["A) 12", "B) 24", "C) 36", "D) 48"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو جذر العدد 49؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "كم حاصل 8 × 7؟", "options": ["A) 54", "B) 56", "C) 58", "D) 60"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "كم حاصل 45 ÷ 9؟", "options": ["A) 4", "B) 5", "C) 6", "D) 7"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو العدد الزوجي؟", "options": ["A) 3", "B) 5", "C) 8", "D) 9"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "كم حاصل 11 + 13؟", "options": ["A) 22", "B) 23", "C) 24", "D) 25"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "كم حاصل 20 - 7؟", "options": ["A) 12", "B) 13", "C) 14", "D) 15"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو محيط مربع طول ضلعه 4؟", "options": ["A) 8", "B) 12", "C) 16", "D) 20"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "كم حاصل 3² + 4²؟", "options": ["A) 12", "B) 25", "C) 20", "D) 24"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو جذر 81؟", "options": ["A) 7", "B) 8", "C) 9", "D) 10"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم حاصل 7 × (5 + 3)؟", "options": ["A) 40", "B) 48", "C) 56", "D) 60"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم حاصل 100 - (20 × 3)؟", "options": ["A) 20", "B) 30", "C) 40", "D) 50"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم حاصل 64 ÷ 8 + 2؟", "options": ["A) 8", "B) 9", "C) 10", "D) 12"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو مربع العدد 9؟", "options": ["A) 18", "B) 72", "C) 81", "D) 90"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم عدد درجات الزاوية القائمة؟", "options": ["A) 45", "B) 60", "C) 90", "D) 180"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم حاصل 5³؟", "options": ["A) 25", "B) 75", "C) 100", "D) 125"], "answer": "D", "fact": "الإجابة الصحيحة هي D", "difficulty": "hard"},
        {"q": "كم حاصل 72 ÷ 9؟", "options": ["A) 6", "B) 7", "C) 8", "D) 9"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم حاصل 14 + 6 × 2؟", "options": ["A) 40", "B) 28", "C) 26", "D) 20"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم حاصل (3 + 5)²؟", "options": ["A) 16", "B) 64", "C) 32", "D) 25"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو جذر 144؟", "options": ["A) 10", "B) 11", "C) 12", "D) 13"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "كم حاصل 2⁵؟", "options": ["A) 16", "B) 24", "C) 32", "D) 64"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "إذا كان x = 3، كم قيمة 2x + 4؟", "options": ["A) 8", "B) 9", "C) 10", "D) 11"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "كم حاصل 81 ÷ 3²؟", "options": ["A) 3", "B) 6", "C) 9", "D) 12"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "كم عدد أضلاع الشكل السداسي؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو ناتج 10² - 50؟", "options": ["A) 25", "B) 50", "C) 75", "D) 100"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "كم حاصل (6 × 6) ÷ 3؟", "options": ["A) 10", "B) 12", "C) 14", "D) 16"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "كم حاصل 7² - 9؟", "options": ["A) 30", "B) 40", "C) 42", "D) 49"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "إذا كان x + 5 = 12، فما قيمة x؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
    ],
    "general": [
        {"q": "ما هي عاصمة فرنسا؟", "options": ["A) مدريد", "B) باريس", "C) روما", "D) برلين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "كم عدد أيام الأسبوع؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو أكبر كوكب في المجموعة الشمسية؟", "options": ["A) الأرض", "B) زحل", "C) المريخ", "D) المشتري"], "answer": "D", "fact": "الإجابة الصحيحة هي D", "difficulty": "easy"},
        {"q": "ما اسم الحيوان الذي يُلقب بملك الغابة؟", "options": ["A) النمر", "B) الأسد", "C) الفيل", "D) الذئب"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما لون السماء في النهار؟", "options": ["A) أخضر", "B) أحمر", "C) أزرق", "D) أصفر"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "كم عدد القارات في العالم؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "ما هو الغاز الذي نتنفسه؟", "options": ["A) الهيدروجين", "B) الأكسجين", "C) النيتروجين", "D) ثاني أكسيد الكربون"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما اسم القارة التي تقع فيها الجزائر؟", "options": ["A) آسيا", "B) أوروبا", "C) إفريقيا", "D) أمريكا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "كم عدد أصابع اليد الواحدة؟", "options": ["A) 4", "B) 5", "C) 6", "D) 7"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "easy"},
        {"q": "ما اسم البحر الذي يفصل بين أوروبا وإفريقيا؟", "options": ["A) البحر الأحمر", "B) البحر الأسود", "C) البحر الأبيض المتوسط", "D) بحر قزوين"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "easy"},
        {"q": "من هو مخترع المصباح الكهربائي؟", "options": ["A) نيوتن", "B) تسلا", "C) إديسون", "D) آينشتاين"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هي عاصمة كندا؟", "options": ["A) تورونتو", "B) أوتاوا", "C) مونتريال", "D) فانكوفر"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هو أطول نهر في العالم؟", "options": ["A) الأمازون", "B) النيل", "C) اليانغتسي", "D) المسيسيبي"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "في أي قارة تقع البرازيل؟", "options": ["A) آسيا", "B) إفريقيا", "C) أمريكا الجنوبية", "D) أوروبا"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "كم عدد كواكب المجموعة الشمسية؟", "options": ["A) 7", "B) 8", "C) 9", "D) 10"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "من هو أول إنسان صعد إلى القمر؟", "options": ["A) يوري غاغارين", "B) نيل أرمسترونغ", "C) باز ألدرين", "D) جون غلين"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي العملة الرسمية لليابان؟", "options": ["A) اليوان", "B) الدولار", "C) الين", "D) الوون"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما اسم أكبر محيط في العالم؟", "options": ["A) الأطلسي", "B) الهندي", "C) المتجمد", "D) الهادئ"], "answer": "D", "fact": "الإجابة الصحيحة هي D", "difficulty": "medium"},
        {"q": "كم عدد ألوان قوس قزح؟", "options": ["A) 5", "B) 6", "C) 7", "D) 8"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "medium"},
        {"q": "ما هو العنصر الكيميائي الذي رمزه O؟", "options": ["A) ذهب", "B) أكسجين", "C) فضة", "D) حديد"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "medium"},
        {"q": "ما هي أصغر دولة في العالم؟", "options": ["A) موناكو", "B) الفاتيكان", "C) سان مارينو", "D) مالطا"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "من هو مؤسس الدولة الأموية؟", "options": ["A) عمر بن الخطاب", "B) معاوية بن أبي سفيان", "C) علي بن أبي طالب", "D) عثمان بن عفان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو العنصر الأكثر وفرة في الكون؟", "options": ["A) الأكسجين", "B) الكربون", "C) الهيدروجين", "D) الهيليوم"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما اسم العملية التي تحول بها النباتات الضوء إلى طاقة؟", "options": ["A) التنفس", "B) البناء الضوئي", "C) التبخر", "D) التحلل"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "في أي سنة اندلعت الحرب العالمية الثانية؟", "options": ["A) 1914", "B) 1920", "C) 1939", "D) 1945"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو أسرع حيوان بري؟", "options": ["A) الأسد", "B) الفهد", "C) الحصان", "D) الذئب"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما اسم أطول سلسلة جبلية في العالم؟", "options": ["A) الهيمالايا", "B) الألب", "C) الأنديز", "D) الأطلس"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "ما هو اسم عاصمة أستراليا؟", "options": ["A) سيدني", "B) ملبورن", "C) كانبرا", "D) بيرث"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "hard"},
        {"q": "كم عدد عظام جسم الإنسان البالغ؟", "options": ["A) 200", "B) 206", "C) 210", "D) 196"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "من هو العالم الذي وضع قوانين الحركة؟", "options": ["A) آينشتاين", "B) نيوتن", "C) غاليليو", "D) كبلر"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "hard"},
        {"q": "ما هو عدد الكروموسومات في جسم الإنسان؟", "options": ["A) 44", "B) 45", "C) 46", "D) 48"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما اسم النظرية التي تفسر نشأة الكون؟", "options": ["A) النسبية", "B) الانفجار العظيم", "C) التطور", "D) الكم"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو الفيلسوف اليوناني الذي كان تلميذ أفلاطون؟", "options": ["A) سقراط", "B) أرسطو", "C) هيراقليطس", "D) فيثاغورس"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما هو العنصر الذي عدده الذري 1؟", "options": ["A) الهيليوم", "B) الهيدروجين", "C) الليثيوم", "D) الكربون"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما اسم أعمق نقطة في المحيطات؟", "options": ["A) خندق الفلبين", "B) خندق ماريانا", "C) خندق تونغا", "D) خندق اليابان"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو مؤلف كتاب \"الأمير\"؟", "options": ["A) أفلاطون", "B) أرسطو", "C) مكيافيلي", "D) ديكارت"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هو أسرع كائن حي في العالم؟", "options": ["A) الفهد", "B) الصقر الشاهين", "C) النسر", "D) الحوت"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "ما اسم المعاهدة التي أنهت الحرب العالمية الأولى؟", "options": ["A) باريس", "B) لندن", "C) فرساي", "D) برلين"], "answer": "C", "fact": "الإجابة الصحيحة هي C", "difficulty": "expert"},
        {"q": "ما هو الغاز الأكثر انتشارًا في الغلاف الجوي للأرض؟", "options": ["A) الأكسجين", "B) النيتروجين", "C) الهيدروجين", "D) ثاني أكسيد الكربون"], "answer": "B", "fact": "الإجابة الصحيحة هي B", "difficulty": "expert"},
        {"q": "من هو مكتشف قانون الجاذبية؟", "options": ["A) نيوتن", "B) آينشتاين", "C) غاليليو", "D) كبلر"], "answer": "A", "fact": "الإجابة الصحيحة هي A", "difficulty": "expert"},
    ],
}

# 🧠 مودات الأسئلة (نظام الكاتيغوري)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUIZ_MODES = {
    "all":         {"name": "🎲 كل الأسئلة",       "cats": None,              "emoji": "🎲"},
    "science":     {"name": "🔬 علوم",              "cats": ["science"],       "emoji": "🔬"},
    "programming": {"name": "💻 برمجة",             "cats": ["programming"],   "emoji": "💻"},
    "math":        {"name": "🔢 رياضيات",           "cats": ["math"],          "emoji": "🔢"},
    "geography":   {"name": "🌍 جغرافيا",          "cats": ["geography"],     "emoji": "🌍"},
    "history":     {"name": "📜 تاريخ",             "cats": ["history"],       "emoji": "📜"},
    "technology":  {"name": "📱 تكنولوجيا",         "cats": ["technology"],    "emoji": "📱"},
    "sports":      {"name": "⚽ رياضة",             "cats": ["sports"],        "emoji": "⚽"},
    "general":     {"name": "🌐 ثقافة عامة",        "cats": ["general"],       "emoji": "🌐"},
    "mixed_sci":   {"name": "🧪 علوم + برمجة",      "cats": ["science", "programming", "math"], "emoji": "🧪"},
}

# تتبع مود كل مستخدم
user_quiz_mode = {}  # {user_id: mode_key}

CATEGORIES_EMOJI = {"geography":"🌍","science":"🔬","history":"📜","sports":"⚽","technology":"💻",
                    "programming":"💻","math":"🔢","general":"🌐"}
DIFFICULTY_POINTS = {"easy": 10, "medium": 20, "hard": 50, "expert": 100}
DIFFICULTY_EMOJI  = {"easy": "🟢", "medium": "🟡", "hard": "🔴", "expert": "⚫"}
LEVEL_THRESHOLDS  = [0, 100, 300, 600, 1000, 1500, 2500, 4000, 6000, 10000]
LEVEL_NAMES = ["مبتدئ 🌱","متعلم 📗","متقدم 🌟","محترف 🏅","خبير 🎯","بطل 🏆","أسطورة 👑","عبقري 🧠","فيلسوف ⚡","إله المعرفة 🔱"]
STREAK_MULTIPLIERS = {3: 1.2, 5: 1.5, 7: 2.0, 10: 3.0}

games_db     = {}
challenges_db = {}
# تتبع حالة تفعيل البوت في المجموعات {chat_id: True}
group_active = {}
# تتبع فهرس الأسئلة لكل مستخدم (لمنع التكرار والترتيب التسلسلي)
# {user_id: {mode_difficulty_key: next_index}}
user_question_indices = {}

def get_streak_multiplier(streak: int) -> float:
    mult = 1.0
    for t, m in sorted(STREAK_MULTIPLIERS.items()):
        if streak >= t:
            mult = m
    return mult

def get_level(points: int) -> tuple[int, str]:
    lvl = 1
    for i, t in enumerate(LEVEL_THRESHOLDS):
        if points >= t:
            lvl = i + 1
    return min(lvl, len(LEVEL_NAMES)), LEVEL_NAMES[min(lvl, len(LEVEL_NAMES)) - 1]

def get_leaderboard() -> list:
    return sorted(DB["users"].values(), key=lambda x: x["points"], reverse=True)

def get_random_question(category=None, difficulty=None, mode_key=None, user_id=None) -> dict:
    """اختر سؤالاً بترتيب ثابت بدون تكرار مع دعم مودات الفئة"""
    all_q = []
    if mode_key and mode_key in QUIZ_MODES and QUIZ_MODES[mode_key]["cats"]:
        cats = QUIZ_MODES[mode_key]["cats"]
    elif category and category in QUESTIONS:
        cats = [category]
    else:
        cats = list(QUESTIONS.keys())

    # جمع الأسئلة حسب الفئة والصعوبة
    for cat in cats:
        for q in QUESTIONS.get(cat, []):
            qc = q.copy(); qc["category"] = cat
            if difficulty is None or qc.get("difficulty") == difficulty:
                all_q.append(qc)

    if not all_q:
        return None

    if user_id is None:
        return shuffle_question_options(all_q[0])

    # مفتاح تتبع الفهرس: يجمع المود والصعوبة والفئات
    track_key = f"{mode_key or 'all'}_{difficulty or 'any'}_{','.join(sorted(cats))}"

    # تهيئة مؤشر المستخدم
    if user_id not in user_question_indices:
        user_question_indices[user_id] = {}

    idx = user_question_indices[user_id].get(track_key, 0)

    # إذا وصلنا للنهاية، نبدأ من الأول (دورة كاملة)
    if idx >= len(all_q):
        idx = 0

    user_question_indices[user_id][track_key] = idx + 1
    return shuffle_question_options(all_q[idx])

def shuffle_question_options(q: dict) -> dict:
    """يخلط خيارات السؤال عشوائياً لإزالة الانحياز نحو إجابة معينة"""
    q = q.copy()
    options = q["options"][:]
    correct_answer_letter = q["answer"]  # A, B, C, or D
    # استخرج نص الإجابة الصحيحة
    correct_text = None
    for opt in options:
        if opt.startswith(correct_answer_letter + ")"):
            correct_text = opt
            break
    if correct_text is None:
        return q  # لا تغيّر لو ما لقينا الإجابة
    # خلط الخيارات
    random.shuffle(options)
    # إعادة تسمية الخيارات A, B, C, D
    letters = ["A", "B", "C", "D"]
    new_options = []
    new_answer = correct_answer_letter
    for i, opt in enumerate(options):
        old_letter = opt[0]
        new_letter = letters[i]
        new_opt = new_letter + opt[1:]  # استبدل الحرف الأول
        new_options.append(new_opt)
        if opt == correct_text:
            new_answer = new_letter
    q["options"] = new_options
    q["answer"] = new_answer
    q["fact"] = f"الإجابة الصحيحة هي {new_answer}"
    return q

MAX_LOAN_MULTIPLIER = 3

def get_max_loan(bank: dict) -> int:
    """الحد الأقصى للقرض"""
    return max(500, bank.get("balance", 0) * MAX_LOAN_MULTIPLIER)

def make_progress_bar(val: int, total: int, width: int = 10) -> str:
    filled = int((val / max(total, 1)) * width)
    return "█" * filled + "░" * (width - filled)

def lives_bar(lives: int, max_lives: int = 3) -> str:
    return "❤️" * lives + "🖤" * (max_lives - lives)

def display_name(u: dict) -> str:
    return u.get("first_name") or u.get("username") or f"لاعب {u['id']}"

ALL_ACHIEVEMENTS = [
    {"id":"first_game",  "name":"🎮 أول لعبة",      "desc":"العب أول لعبة",               "reward_coins":20},
    {"id":"10_correct",  "name":"✅ عشرة صحيحة",     "desc":"أجب على 10 أسئلة صحيحة",      "reward_coins":30},
    {"id":"streak_5",    "name":"🔥 سلسلة ناجحة",    "desc":"سلسلة 5 إجابات صحيحة",        "reward_coins":50},
    {"id":"streak_10",   "name":"⚡ سلسلة أسطورية",  "desc":"سلسلة 10 إجابات",             "reward_coins":100},
    {"id":"100_points",  "name":"⭐ مئة نقطة",       "desc":"اجمع 100 نقطة",               "reward_coins":15},
    {"id":"500_points",  "name":"🌟 خمسمئة نقطة",    "desc":"اجمع 500 نقطة",               "reward_coins":40},
    {"id":"1000_points", "name":"💎 ألف نقطة",       "desc":"اجمع 1000 نقطة",              "reward_coins":80},
    {"id":"first_win",   "name":"🏆 أول انتصار",     "desc":"افوز بأول تحدٍّ",             "reward_coins":60},
    {"id":"first_harvest","name":"🌾 أول حصاد",      "desc":"احصد محصولك الأول",            "reward_coins":50},
    {"id":"farm_lvl3",   "name":"🌳 مزرعة متقدمة",   "desc":"ارقِّ مزرعتك للمستوى 3",      "reward_coins":100},
    {"id":"rich_farmer", "name":"💰 مزارع ثري",      "desc":"اجمع 5000 في مزرعتك",         "reward_coins":150},
    {"id":"bank_1000",   "name":"🏦 مدخّر",          "desc":"اجمع 1000 في البنك",           "reward_coins":30},
    {"id":"transfer_1",  "name":"💸 أول تحويل",      "desc":"أجرِ أول تحويل بنكي",         "reward_coins":20},
]

def check_achievements(db_user: dict) -> list[str]:
    newly = []
    total = db_user["total_correct"] + db_user["total_wrong"]
    conditions = {
        "first_game":   total >= 1,
        "10_correct":   db_user["total_correct"] >= 10,
        "streak_5":     db_user["best_streak"] >= 5,
        "streak_10":    db_user["best_streak"] >= 10,
        "100_points":   db_user["points"] >= 100,
        "500_points":   db_user["points"] >= 500,
        "1000_points":  db_user["points"] >= 1000,
        "first_win":    db_user.get("challenge_wins", 0) >= 1,
        "first_harvest":db_user["farm"].get("total_harvests", 0) >= 1,
        "farm_lvl3":    db_user["farm"].get("level", 1) >= 3,
        "rich_farmer":  db_user["farm"].get("money", 0) >= 5000,
        "bank_1000":    db_user["bank"].get("balance", 0) >= 1000,
        "transfer_1":   len(db_user["bank"].get("transactions", [])) >= 1,
    }
    for ach in ALL_ACHIEVEMENTS:
        if conditions.get(ach["id"]) and ach["id"] not in db_user["achievements"]:
            db_user["achievements"].append(ach["id"])
            db_user["coins"] += ach["reward_coins"]
            newly.append(f"{ach['name']} (+{ach['reward_coins']} 🪙)")
    return newly


# ╔══════════════════════════════════════════╗
# ║          🚀 أوامر البوت الأساسية         ║
# ╚══════════════════════════════════════════╝

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")
    save_user(user.id)
    _, lvl_name = get_level(db_user["points"])
    name = user.first_name or "صديقي"

    text = (
        f"👋 أهلاً يا {name}!\n\n"
        "🌟 مرحباً في QuizFarm\n"
        "مسابقات ذكاء + مزرعة تفاعلية + بنك متكامل في مكان واحد!\n\n"
        "⸻\n"
        "🎯  مسابقات ذكاء من 8 فئات مختلفة\n"
        "🌾  مزرعة تفاعلية مع حيوانات نادرة\n"
        "🏦  بنك متكامل مع تحويلات آمنة\n"
        "⚔️  تحديات مباشرة بين اللاعبين\n"
        "⸻\n\n"
        "📊 ملفك الحالي:\n"
        f"⭐ {db_user['points']:,} نقطة  ·  📈 {lvl_name}\n"
        f"🪙 {db_user['coins']:,} عملة\n"
        f"🌾 مزرعة Lv.{db_user['farm']['level']}  ·  🏦 {db_user['bank']['balance']:,} 💵\n\n"
        f"👑 المالك: {OWNER}"
    )
    keyboard = [
        [
            InlineKeyboardButton("🎮 العب الآن",     callback_data="play_menu"),
            InlineKeyboardButton("🌾 مزرعتي",        callback_data="my_farm"),
        ],
        [
            InlineKeyboardButton("🏦 حسابي البنكي",  callback_data="my_bank"),
            InlineKeyboardButton("🏆 المتصدرون",     callback_data="leaderboard"),
        ],
        [
            InlineKeyboardButton("👤 ملفي",           callback_data="profile"),
            InlineKeyboardButton("📅 مكافأة يومية",  callback_data="daily"),
        ],
        [
            InlineKeyboardButton("🏅 إنجازاتي",      callback_data="achievements_cb"),
            InlineKeyboardButton("🛒 المتجر",         callback_data="shop_menu"),
        ],
        [
            InlineKeyboardButton("📅 التحدي الأسبوعي", callback_data="weekly_cb"),
        ],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 الأوامر الكاملة\n\n"
        "🎮 المسابقات\n"
        "/play · /easy · /medium · /hard · /expert\n"
        "/daily · /leaderboard · /stats · /profile\n"
        "/challenge @user · /accept · /decline\n\n"
        "🧠 فئات الأسئلة — اكتب: مود\n"
        "🔬 علوم  💻 برمجة  🔢 رياضيات  🌍 جغرافيا\n"
        "📜 تاريخ  📱 تكنولوجيا  ⚽ رياضة  🎲 كل شيء\n\n"
        "💰 الاقتصاد\n"
        "استثمار — ربح 1–25% 🪙\n"
        "حظ [مبلغ] — راهن عملاتك 🎲\n"
        "بقشيش — هدية مجانية 200–1500 🪙\n\n"
        "🌾 المزرعة\n"
        "مزرعتي · زرع [نوع] · حصاد · بيع [نوع]\n"
        "مخزني · شراء بذور · شراء حيوانات\n"
        "سقي المحاصيل · اطعام الحيوانات\n"
        "تطوير المزرعة · ترقية [مبنى] · وقتي\n\n"
        "🏦 البنك\n"
        "حسابي البنكي · رصيدي · تحويل\n\n"
        "💡 في المجموعات: نادِ «ويليم» لتفعيل البوت\n\n"
        f"👑 المالك: {OWNER}"
    )
    await update.message.reply_text(text)


# ╔══════════════════════════════════════════╗
# ║            🌾 نظام المزرعة              ║
# ╚══════════════════════════════════════════╝

async def my_farm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مزرعتي - عرض حالة المزرعة كاملة"""
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")
    farm    = db_user["farm"]

    # فحص الإهمال
    neglect_msgs = check_farm_neglect(farm)

    farm_lvl, farm_info = get_farm_level_info(farm.get("exp", 0))
    farm["level"] = farm_lvl

    # محاصيل
    crops_text = ""
    if farm.get("crops"):
        for i, crop in enumerate(farm["crops"], 1):
            seed_info  = SEEDS.get(crop["seed_type"], {})
            has_gh     = has_building(farm, "greenhouse")
            time_left  = farm_time_left(crop["planted_at"], crop["grow_minutes"], has_gh)
            status     = "✅" if time_left <= 0 else "⏳"
            crops_text += f"  {status} {seed_info.get('emoji','🌱')} {seed_info.get('name','؟')} - {format_time(time_left)}\n"
    else:
        crops_text = "  لا توجد محاصيل مزروعة\n"

    # حيوانات
    animals_text = ""
    if farm.get("animals"):
        for atype, count in farm["animals"].items():
            ainfo = ANIMALS.get(atype, {})
            animals_text += f"  {ainfo.get('name','؟')} × {count}\n"
    else:
        animals_text = "  لا توجد حيوانات\n"

    # بذور في المخزن
    seeds_text = ""
    if farm.get("seeds"):
        for stype, count in farm["seeds"].items():
            sinfo = SEEDS.get(stype, {})
            seeds_text += f"  {sinfo.get('emoji','🌱')} {sinfo.get('name','؟')}: {count}\n"
    else:
        seeds_text = "  لا توجد بذور\n"

    next_lvl_info = FARM_LEVELS.get(farm_lvl + 1, {})
    exp_needed    = next_lvl_info.get("exp_needed", farm.get("exp", 0))
    exp_bar       = make_progress_bar(farm.get("exp", 0), max(exp_needed, 1))
    water_bar     = make_progress_bar(farm.get("water", 100), 100, 8)
    soil_bar      = make_progress_bar(farm.get("soil_quality", 100), 100, 8)

    last_active = datetime.fromisoformat(farm.get("last_active", datetime.now().isoformat()))
    idle_hours  = (datetime.now() - last_active).total_seconds() / 3600
    status_icon = "✅ نشطة" if idle_hours < 12 else "⚠️ مهملة"

    text = (
        "╔══════════════════════╗\n"
        f"║  🌾 مزرعة {user.first_name[:10]}  ║\n"
        "╚══════════════════════╝\n\n"
        f"📊 المستوى: {farm_info['name']}\n"
        f"✨ الخبرة: {farm.get('exp',0)} / {exp_needed}\n"
        f"{exp_bar}\n\n"
        f"💵 أموال المزرعة: {farm['money']:,}\n"
        f"💧 الماء: {water_bar} {farm.get('water',100)}%\n"
        f"🌱 جودة التربة: {soil_bar} {farm.get('soil_quality',100)}%\n"
        f"🔧 حالة المزرعة: {status_icon}\n\n"
        f"📦 السعة: {len(farm.get('crops',[]))}/{farm_info['max_crops']} محاصيل\n"
        f"🐾 الحيوانات: {sum(farm.get('animals',{}).values())}/{farm_info['max_animals']}\n\n"
        f"🌱 المحاصيل الحالية:\n{crops_text}\n"
        f"🐄 الحيوانات:\n{animals_text}\n"
        f"🎒 البذور في الجيب:\n{seeds_text}"
    )
    if neglect_msgs:
        text += "\n⚠️ تحذيرات:\n" + "\n".join(neglect_msgs)

    # عرض الحيوانات النادرة إن وُجدت
    rare_owned = farm.get("rare_animals", [])
    if rare_owned:
        text += "\n\n✨ حيواناتك النادرة:\n"
        for aid in rare_owned:
            a = RARE_ANIMALS.get(aid, {})
            text += f"  {a.get('rarity_emoji','')} {a.get('name',aid)}\n"
        text += f"💡 لرؤية التفاصيل: حيوانات نادرة"

    farm["last_active"] = datetime.now().isoformat()
    save_user(user.id)

    keyboard = [
        [
            InlineKeyboardButton("🌱 زرع",          callback_data="farm_plant_menu"),
            InlineKeyboardButton("🌾 حصاد",         callback_data="farm_harvest"),
        ],
        [
            InlineKeyboardButton("🛒 شراء بذور",    callback_data="farm_buy_seeds"),
            InlineKeyboardButton("🐄 شراء حيوانات", callback_data="farm_buy_animals"),
        ],
        [
            InlineKeyboardButton("💧 سقي",           callback_data="farm_water"),
            InlineKeyboardButton("🍖 إطعام",        callback_data="farm_feed"),
        ],
        [
            InlineKeyboardButton("📦 مخزني",         callback_data="farm_storage"),
            InlineKeyboardButton("💰 بيع",           callback_data="farm_sell_menu"),
        ],
        [
            InlineKeyboardButton("🏗️ تطوير",        callback_data="farm_upgrade_menu"),
            InlineKeyboardButton("🏪 السوق",         callback_data="farm_market"),
        ],
        [
            InlineKeyboardButton("✨ حيوانات نادرة", callback_data="rare_animals"),
        ],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def farm_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المزرعة - عرض جميع أوامر المزرعة"""
    text = (
        "╔══════════════════════════════╗\n"
        "║      🌾 دليل المزرعة 🌾       ║\n"
        "╚══════════════════════════════╝\n\n"
        "📌 كيف تبدأ (خطوة بخطوة):\n"
        "1️⃣ اكتب: مزرعتي - لتشاهد مزرعتك\n"
        "2️⃣ اشترِ بذوراً: شراء بذور قمح 5\n"
        "3️⃣ ازرع: زرع قمح\n"
        "4️⃣ انتظر وقت النمو ثم: حصاد\n"
        "5️⃣ بع المحصول: بيع قمح\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌱 أوامر الزراعة:\n"
        "  مزرعتي            - حالة مزرعتك\n"
        "  زرع [نوع]         - ازرع بذوراً\n"
        "  حصاد              - احصد جاهز\n"
        "  سقي المحاصيل      - اسقِ مزرعتك\n\n"
        "🛒 أوامر الشراء:\n"
        "  شراء بذور [نوع] [كمية]\n"
        "  شراء حيوانات [نوع]\n"
        "  سوق المزرعة       - أسعار كل شيء\n\n"
        "🐄 الحيوانات:\n"
        "  اطعام الحيوانات   - أطعم حيواناتك\n"
        "  انتاج الحيوانات   - اجمع المنتجات\n\n"
        "💰 التجارة:\n"
        "  بيع [نوع] [كمية]  - بع من مخزنك\n"
        "  مخزني             - محتويات المخزن\n\n"
        "⬆️ التطوير:\n"
        "  تطوير المزرعة     - اعرف خياراتك\n"
        "  ترقية [مبنى]      - ابنِ مبنى\n"
        "  عمال المزرعة      - استئجار عمال\n\n"
        "📊 الإحصائيات:\n"
        "  احصائيات مزرعتي  - إحصائيات تفصيلية\n"
        "  وقتي              - أوقات الحصاد\n"
        "  مستوى مزرعتي     - تقدم مزرعتك\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌾 أنواع البذور المتاحة:\n"
        "  قمح 🌾 | ذرة 🌽 | بطاطا 🥔\n"
        "  طماطم 🍅 | جزر 🥕 | فراولة 🍓\n"
        "  بطيخ 🍉 | عنب 🍇 | عباد شمس 🌻\n"
        "  أرز 🍚\n\n"
        "🐄 أنواع الحيوانات:\n"
        "  دجاج 🐔 | بقر 🐄 | غنم 🐑\n"
        "  أرانب 🐇 | نحل 🐝 | خيول 🐴\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text)


async def farm_market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سوق المزرعة - عرض أسعار كل شيء"""
    text = (
        "╔══════════════════════════════╗\n"
        "║       🏪 سوق المزرعة 🏪       ║\n"
        "╚══════════════════════════════╝\n\n"
        "🌱 البذور (السعر / وقت النمو / سعر البيع):\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    for key, s in SEEDS.items():
        text += (
            f"{s['emoji']} {s['name']}\n"
            f"  شراء: {s['price']} 💵 | نمو: {format_time(s['grow_minutes'])} | بيع: {s['sell_price']} 💵\n"
        )
    text += "\n🐄 الحيوانات (السعر / الإنتاج / المنتج):\n━━━━━━━━━━━━━━━━━━━━\n"
    for key, a in ANIMALS.items():
        text += (
            f"{a['name']}\n"
            f"  شراء: {a['price']} 💵 | إنتاج كل: {format_time(a['produce_minutes'])} | {a['product_name']}: {a['sell_price']} 💵\n"
        )
    text += "\n🏗️ المباني:\n━━━━━━━━━━━━━━━━━━━━\n"
    for key, b in BUILDINGS.items():
        text += f"{b['name']} - {b['price']} 💵 | {b['desc']}\n"
    text += "\n━━━━━━━━━━━━━━━━━━━━\n💡 استخدم: شراء بذور [نوع] [كمية]"
    await update.message.reply_text(text)


async def buy_seeds_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شراء بذور [نوع] [كمية]"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    args    = context.args

    SEED_ALIASES = {
        "قمح":"wheat","ذرة":"corn","بطاطا":"potato","طماطم":"tomato",
        "جزر":"carrot","فراولة":"strawberry","بطيخ":"watermelon",
        "عنب":"grape","عباد":"sunflower","عبادشمس":"sunflower","ارز":"rice","أرز":"rice",
    }

    if not args:
        text = "🌱 أنواع البذور المتاحة:\n\n"
        for key, s in SEEDS.items():
            text += f"{s['emoji']} {s['name']} - {s['price']} 💵\n"
        text += "\n📝 استخدم: شراء بذور [نوع] [كمية]\nمثال: شراء بذور قمح 5"
        await update.message.reply_text(text)
        return

    seed_key_ar = args[0]
    seed_key    = SEED_ALIASES.get(seed_key_ar, seed_key_ar)
    quantity    = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1

    if seed_key not in SEEDS:
        await update.message.reply_text(f"❌ نوع البذور '{seed_key_ar}' غير موجود!\nاكتب: سوق المزرعة لرؤية الأنواع.")
        return

    seed_info = SEEDS[seed_key]
    total_cost = seed_info["price"] * quantity

    if farm["money"] < total_cost:
        await update.message.reply_text(
            f"❌ لا يكفي المال!\n"
            f"تحتاج: {total_cost} 💵\n"
            f"لديك: {farm['money']} 💵"
        )
        return

    farm["money"] -= total_cost
    farm.setdefault("seeds", {})[seed_key] = farm["seeds"].get(seed_key, 0) + quantity
    save_user(user.id)

    await update.message.reply_text(
        f"✅ تم الشراء!\n\n"
        f"{seed_info['emoji']} {seed_info['name']} × {quantity}\n"
        f"💵 التكلفة: {total_cost}\n"
        f"💰 المتبقي: {farm['money']:,} 💵\n\n"
        f"🌱 الآن اكتب: زرع {seed_key_ar}"
    )


async def buy_animals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شراء حيوانات [نوع]"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    args    = context.args

    ANIMAL_ALIASES = {
        "دجاج":"chicken","دجاجة":"chicken","بقر":"cow","بقرة":"cow",
        "غنم":"sheep","خروف":"sheep","ارانب":"rabbit","أرانب":"rabbit",
        "أرنب":"rabbit","نحل":"bee","نحلة":"bee","خيول":"horse","حصان":"horse",
    }

    if not args:
        text = "🐄 الحيوانات المتاحة:\n\n"
        for key, a in ANIMALS.items():
            text += f"{a['name']} - {a['price']} 💵 | ينتج: {a['product_name']} كل {format_time(a['produce_minutes'])}\n"
        text += "\n📝 استخدم: شراء حيوانات [نوع]\nمثال: شراء حيوانات دجاج"
        await update.message.reply_text(text)
        return

    animal_key_ar = args[0]
    animal_key    = ANIMAL_ALIASES.get(animal_key_ar, animal_key_ar)

    if animal_key not in ANIMALS:
        await update.message.reply_text(f"❌ نوع الحيوان '{animal_key_ar}' غير موجود!")
        return

    _, farm_info = get_farm_level_info(farm.get("exp", 0))
    total_animals = sum(farm.get("animals", {}).values())
    max_animals   = farm_info["max_animals"] + (3 if has_building(farm, "barn") else 0)

    if total_animals >= max_animals:
        await update.message.reply_text(
            f"❌ مزرعتك ممتلئة! ({total_animals}/{max_animals} حيوانات)\n"
            f"💡 ارقِّ مزرعتك أو ابنِ إسطبلاً."
        )
        return

    ainfo = ANIMALS[animal_key]
    if farm["money"] < ainfo["price"]:
        await update.message.reply_text(
            f"❌ لا يكفي المال!\n"
            f"تحتاج: {ainfo['price']} 💵\n"
            f"لديك: {farm['money']} 💵"
        )
        return

    farm["money"] -= ainfo["price"]
    farm.setdefault("animals", {})[animal_key] = farm["animals"].get(animal_key, 0) + 1

    # ابدأ دورة الإنتاج
    farm.setdefault("animal_products", []).append({
        "animal_type":    animal_key,
        "produce_minutes":ainfo["produce_minutes"],
        "started_at":     datetime.now().isoformat(),
    })
    save_user(user.id)

    await update.message.reply_text(
        f"✅ تم شراء {ainfo['name']}! 🎉\n\n"
        f"💵 التكلفة: {ainfo['price']}\n"
        f"💰 المتبقي: {farm['money']:,} 💵\n"
        f"⏱️ ينتج {ainfo['product_name']} كل {format_time(ainfo['produce_minutes'])}\n\n"
        f"🍖 لا تنسَ إطعامه: اطعام الحيوانات"
    )


async def plant_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زرع [نوع]"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    args    = context.args

    SEED_ALIASES = {
        "قمح":"wheat","ذرة":"corn","بطاطا":"potato","طماطم":"tomato",
        "جزر":"carrot","فراولة":"strawberry","بطيخ":"watermelon",
        "عنب":"grape","عباد":"sunflower","ارز":"rice","أرز":"rice",
    }

    if not args:
        seeds_available = farm.get("seeds", {})
        if not seeds_available:
            await update.message.reply_text("❌ لا توجد بذور! اشترِ أولاً: شراء بذور قمح 5")
            return
        text = "🌱 بذورك المتاحة:\n\n"
        for stype, count in seeds_available.items():
            sinfo = SEEDS.get(stype, {})
            text += f"{sinfo.get('emoji','🌱')} {sinfo.get('name','؟')}: {count}\n"
        text += "\n📝 اكتب: زرع [نوع]"
        await update.message.reply_text(text)
        return

    seed_key_ar = args[0]
    seed_key    = SEED_ALIASES.get(seed_key_ar, seed_key_ar)

    if seed_key not in SEEDS:
        await update.message.reply_text(f"❌ نوع البذور '{seed_key_ar}' غير موجود!")
        return

    farm.setdefault("seeds", {})
    if farm["seeds"].get(seed_key, 0) <= 0:
        await update.message.reply_text(f"❌ لا تملك بذور {seed_key_ar}!\nاشترِ: شراء بذور {seed_key_ar} 5")
        return

    _, farm_info = get_farm_level_info(farm.get("exp", 0))
    current_crops = len(farm.get("crops", []))
    if current_crops >= farm_info["max_crops"]:
        await update.message.reply_text(
            f"❌ حقلك ممتلئ! ({current_crops}/{farm_info['max_crops']})\n"
            f"💡 احصد أولاً أو رقِّ مزرعتك."
        )
        return

    if farm.get("water", 100) < 10:
        await update.message.reply_text("❌ الماء ناضب! اكتب: سقي المحاصيل أولاً.")
        return

    sinfo = SEEDS[seed_key]
    farm["seeds"][seed_key] -= 1
    if farm["seeds"][seed_key] <= 0:
        del farm["seeds"][seed_key]

    # احسب عدد بذور نفس النوع الموجودة حالياً في الحقل
    same_type_count = sum(1 for c in farm.get("crops", []) if c.get("seed_type") == seed_key)
    # كل بذرة إضافية تزيد وقت النمو بنسبة 5%
    grow_minutes = round(sinfo["grow_minutes"] * (1.05 ** same_type_count), 2)

    farm.setdefault("crops", []).append({
        "seed_type":   seed_key,
        "grow_minutes":grow_minutes,
        "planted_at":  datetime.now().isoformat(),
    })
    farm["water"] = max(0, farm.get("water", 100) - 10)
    farm["last_active"] = datetime.now().isoformat()

    lvl_up = add_farm_exp(farm, sinfo["exp"] // 2)
    save_user(user.id)

    await update.message.reply_text(
        f"✅ تمت الزراعة! {sinfo['emoji']} {sinfo['name']}\n\n"
        f"⏱️ جاهز للحصاد بعد: {format_time(grow_minutes)}\n"
        f"💧 الماء المتبقي: {farm['water']}%\n"
        f"🌾 المحاصيل: {len(farm['crops'])}/{farm_info['max_crops']}{lvl_up}"
    )


async def harvest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حصاد - احصد كل المحاصيل الجاهزة"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]

    ready_crops   = []
    pending_crops = []
    has_gh = has_building(farm, "greenhouse")

    for crop in farm.get("crops", []):
        time_left = farm_time_left(crop["planted_at"], crop["grow_minutes"], has_gh)
        if time_left <= 0:
            ready_crops.append(crop)
        else:
            pending_crops.append(crop)

    if not ready_crops:
        text = "⏳ لا توجد محاصيل جاهزة للحصاد!\n\n"
        if farm.get("crops"):
            text += "المحاصيل الجارية:\n"
            for crop in farm["crops"]:
                sinfo     = SEEDS.get(crop["seed_type"], {})
                time_left = farm_time_left(crop["planted_at"], crop["grow_minutes"], has_gh)
                text += f"  {sinfo.get('emoji','🌱')} {sinfo.get('name','؟')} - {format_time(time_left)}\n"
        await update.message.reply_text(text)
        return

    total_earned = 0
    harvest_summary = []
    mult = sell_price_multiplier(farm)
    for crop in ready_crops:
        sinfo  = SEEDS.get(crop["seed_type"], {})
        earned = int(sinfo.get("sell_price", 50) * mult)

        # أضف للمخزن بدل البيع المباشر
        storage_key = f"{crop['seed_type']}_harvested"
        farm.setdefault("storage", {})[storage_key] = farm["storage"].get(storage_key, 0) + 1
        harvest_summary.append(f"  {sinfo.get('emoji','🌱')} {sinfo.get('name','؟')} → المخزن")
        lvl_up = add_farm_exp(farm, sinfo.get("exp", 5))

    farm["crops"] = pending_crops
    farm["total_harvests"] = farm.get("total_harvests", 0) + len(ready_crops)
    farm["last_active"]    = datetime.now().isoformat()
    save_user(user.id)

    newly = check_achievements(db_user)
    # تحقق من حيوانات نادرة جديدة بعد كل حصاد
    newly_rare = check_rare_animals(db_user)
    save_user(user.id)

    text = (
        f"🎉 تم الحصاد!\n\n"
        f"{''.join(harvest_summary)}\n\n"
        f"📦 المحاصيل في مخزنك الآن.\n"
        f"💰 لبيعها اكتب: بيع [نوع]\n"
        f"⏳ محاصيل جارية: {len(pending_crops)}"
    )
    if newly:
        text += "\n\n🏅 إنجازات جديدة:\n" + "\n".join(newly)
    if newly_rare:
        for _, rare in newly_rare:
            text += f"\n\n🎊 حيوان نادر جديد: {rare['name']} {rare['rarity_stars']}"
    await update.message.reply_text(text)


async def sell_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بيع [نوع] [كمية]"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    args    = context.args

    SELL_ALIASES = {
        "قمح":"wheat_harvested","ذرة":"corn_harvested","بطاطا":"potato_harvested",
        "طماطم":"tomato_harvested","جزر":"carrot_harvested","فراولة":"strawberry_harvested",
        "بطيخ":"watermelon_harvested","عنب":"grape_harvested","عباد":"sunflower_harvested",
        "ارز":"rice_harvested","أرز":"rice_harvested",
        "بيض":"egg","حليب":"milk","صوف":"wool","فرو":"fur","عسل":"honey","ركوب":"ride",
    }

    storage = farm.get("storage", {})
    if not storage:
        await update.message.reply_text("📦 مخزنك فارغ!\nاحصد أولاً: حصاد")
        return

    if not args:
        text = "📦 مخزنك:\n\n"
        for key, qty in storage.items():
            seed_key = key.replace("_harvested", "")
            sinfo = SEEDS.get(seed_key, {}) or ANIMALS.get(seed_key, {})
            name  = sinfo.get("name", key) if sinfo else key
            price = sinfo.get("sell_price", 50) if sinfo else 50
            text += f"  {sinfo.get('emoji','📦') if sinfo else '📦'} {name}: {qty} (يساوي {price} 💵/وحدة)\n"
        text += "\n📝 اكتب: بيع [نوع] [كمية]\nمثال: بيع قمح 3"
        await update.message.reply_text(text)
        return

    item_ar   = args[0]
    item_key  = SELL_ALIASES.get(item_ar, item_ar + "_harvested")
    quantity  = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1

    # ━━ تحقق إذا كان المنتج من حيوان نادر (بدون لاحقة _harvested) ━━
    rare_products = {ainfo["product"]: ainfo for ainfo in RARE_ANIMALS.values()}
    if item_ar in rare_products:
        item_key = item_ar

    if storage.get(item_key, 0) < quantity:
        # لو ما وجد، جرّب بدون _harvested
        alt_key = item_ar
        if storage.get(alt_key, 0) >= quantity:
            item_key = alt_key
        else:
            await update.message.reply_text(
                f"❌ لا يوجد ما يكفي في مخزنك!\n"
                f"لديك: {storage.get(item_key, 0)} وحدة\n\n"
                f"💡 اكتب مخزني لترى ما عندك وأوامر البيع الصحيحة"
            )
            return

    # ━━ تحديد السعر — عادي أو نادر ━━
    mult = sell_price_multiplier(farm)
    if item_key in rare_products:
        ainfo = rare_products[item_key]
        price = ainfo["sell_price"]
        name  = ainfo["product_name"]
        emoji = ainfo["rarity_emoji"]
    else:
        seed_key = item_key.replace("_harvested", "")
        sinfo    = SEEDS.get(seed_key, {}) or ANIMALS.get(seed_key, {})
        price    = sinfo.get("sell_price", 50) if sinfo else 50
        name     = sinfo.get("name", item_ar) if sinfo else item_ar
        emoji    = sinfo.get("emoji", "📦") if sinfo else "📦"

    total = int(price * mult * quantity)

    farm["storage"][item_key] -= quantity
    if farm["storage"][item_key] <= 0:
        del farm["storage"][item_key]
    farm["money"] += total
    farm["total_sales"] = farm.get("total_sales", 0) + quantity
    save_user(user.id)

    market_bonus = "  🏪 +15% سوق خاص\n" if mult > 1 else ""
    await update.message.reply_text(
        f"💰 تم البيع!\n\n"
        f"{emoji} {name} × {quantity}\n"
        f"{market_bonus}"
        f"💵 الربح: +{total:,}\n"
        f"💰 رصيد المزرعة: {farm['money']:,} 💵"
    )


async def storage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مخزني"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    storage = farm.get("storage", {})

    if not storage:
        await update.message.reply_text("📦 مخزنك فارغ! احصد محاصيلك أولاً: حصاد")
        return

    # ━━ بناء قاموس منتجات الحيوانات النادرة للبحث السريع ━━
    rare_products = {}
    for aid, ainfo in RARE_ANIMALS.items():
        rare_products[ainfo["product"]] = ainfo

    # ━━ فصل المنتجات العادية عن النادرة ━━
    normal_items = {}
    rare_items   = {}
    for key, qty in storage.items():
        if key in rare_products:
            rare_items[key] = qty
        else:
            normal_items[key] = qty

    text        = "📦 مخزن المزرعة:\n\n"
    total_value = 0
    mult        = sell_price_multiplier(farm)

    # ━━ المنتجات العادية ━━
    if normal_items:
        text += "🌾 منتجات المزرعة:\n"
        for key, qty in normal_items.items():
            seed_key = key.replace("_harvested", "")
            sinfo    = SEEDS.get(seed_key, {}) or ANIMALS.get(seed_key, {})
            name     = sinfo.get("name", key) if sinfo else key
            price    = sinfo.get("sell_price", 50) if sinfo else 50
            value    = int(price * mult * qty)
            total_value += value
            emoji = sinfo.get("emoji", "📦") if sinfo else "📦"
            text += f"  {emoji} {name}: {qty} وحدة (≈ {value} 💵)\n"
            text += f"      للبيع: بيع {key.replace('_harvested','')} {qty}\n"

    # ━━ منتجات الحيوانات النادرة ━━
    if rare_items:
        text += "\n✨ منتجات الحيوانات النادرة:\n"
        for key, qty in rare_items.items():
            ainfo  = rare_products[key]
            price  = ainfo["sell_price"]
            value  = int(price * qty)
            total_value += value
            text += (
                f"  {ainfo['rarity_emoji']} {ainfo['product_name']}: {qty} وحدة (≈ {value} 💵)\n"
                f"      من: {ainfo['name']}\n"
                f"      للبيع: بيع {key} {qty}\n"
            )

    text += f"\n💎 القيمة الإجمالية: ≈ {total_value:,} 💵\n"
    if has_building(farm, "silo"):
        text += "🏰 مضاعف الصومعة نشط!\n"
    if has_building(farm, "market"):
        text += "🏪 مضاعف السوق الخاص نشط (+15%)!\n"

    text += "\n💡 للبيع اكتب: بيع [اسم_المنتج] [الكمية]"

    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text)


async def water_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سقي المحاصيل"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]

    if farm.get("water", 100) >= 100:
        await update.message.reply_text("💧 مستوى الماء ممتلئ بالفعل (100%)!")
        return

    has_well = has_building(farm, "well")
    refill   = 100 if has_well else 50
    farm["water"] = min(100, farm.get("water", 0) + refill)
    save_user(user.id)

    await update.message.reply_text(
        f"💧 تم السقي!\n\n"
        f"{'🏗️ البئر تملأ الخزان كاملاً!' if has_well else ''}\n"
        f"💧 مستوى الماء: {farm['water']}%\n"
        f"🌱 محاصيلك ستنمو بشكل أفضل."
    )


async def feed_animals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اطعام الحيوانات"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]

    animals = farm.get("animals", {})
    if not animals:
        await update.message.reply_text("🐾 لا توجد حيوانات في مزرعتك!")
        return

    total_cost = 0
    for atype, count in animals.items():
        ainfo = ANIMALS.get(atype, {})
        total_cost += ainfo.get("feed_cost", 20) * count

    if farm["money"] < total_cost:
        await update.message.reply_text(
            f"❌ لا يكفي المال للإطعام!\n"
            f"تحتاج: {total_cost} 💵 | لديك: {farm['money']} 💵"
        )
        return

    farm["money"] -= total_cost
    # سرّع الإنتاج
    for prod in farm.get("animal_products", []):
        prod["fed"] = True
    save_user(user.id)

    summary = "\n".join([
        f"  {ANIMALS[at]['name']} × {c} - {ANIMALS[at]['feed_cost'] * c} 💵"
        for at, c in animals.items() if at in ANIMALS
    ])
    await update.message.reply_text(
        f"🍖 تم الإطعام!\n\n{summary}\n\n"
        f"💵 الإجمالي: -{total_cost}\n"
        f"💰 المتبقي: {farm['money']:,} 💵\n"
        f"✅ الحيوانات سعيدة وستنتج أكثر!"
    )


async def collect_animal_products_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتاج الحيوانات - اجمع المنتجات"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]

    if not farm.get("animal_products"):
        await update.message.reply_text("🐾 لا توجد منتجات لجمعها الآن.")
        return

    ready   = []
    pending = []
    for prod in farm["animal_products"]:
        time_left = farm_time_left(prod["started_at"], prod["produce_minutes"])
        if time_left <= 0:
            ready.append(prod)
        else:
            pending.append(prod)

    if not ready:
        text = "⏳ لا توجد منتجات جاهزة بعد!\n\n"
        for prod in pending:
            ainfo = ANIMALS.get(prod["animal_type"], {})
            tl    = farm_time_left(prod["started_at"], prod["produce_minutes"])
            text += f"  {ainfo.get('name','؟')} → {ainfo.get('product_name','؟')} بعد {format_time(tl)}\n"
        await update.message.reply_text(text)
        return

    summary = []
    mult    = sell_price_multiplier(farm)
    for prod in ready:
        ainfo   = ANIMALS.get(prod["animal_type"], {})
        product = ainfo.get("product", "item")
        farm.setdefault("storage", {})[product] = farm["storage"].get(product, 0) + 1
        summary.append(f"  {ainfo['name']} → {ainfo['product_name']} (+1)")
        # أعد دورة الإنتاج
        prod["started_at"] = datetime.now().isoformat()
        pending.append(prod)
        add_farm_exp(farm, ainfo.get("exp", 20) // 3)

    farm["animal_products"] = pending
    save_user(user.id)

    await update.message.reply_text(
        f"🎉 تم جمع المنتجات!\n\n"
        + "\n".join(summary) +
        f"\n\n📦 المنتجات في مخزنك.\n"
        f"💰 لبيعها: بيع [نوع المنتج]"
    )


async def farm_upgrade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تطوير المزرعة / ترقية [مبنى]"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    args    = context.args

    BUILDING_ALIASES = {
        "اسطبل":"barn","إسطبل":"barn","بيت زجاجي":"greenhouse","بئر":"well",
        "صومعة":"silo","سوق":"market",
    }

    if not args:
        _, farm_info  = get_farm_level_info(farm.get("exp", 0))
        my_buildings  = farm.get("buildings", [])
        text = (
            "╔══════════════════════╗\n"
            "║  🏗️ تطوير المزرعة   ║\n"
            "╚══════════════════════╝\n\n"
            f"💵 رصيدك: {farm['money']:,}\n\n"
            "🏠 المباني المتاحة:\n"
        )
        for key, b in BUILDINGS.items():
            owned = "✅ مملوك" if key in my_buildings else f"💵 {b['price']}"
            text += f"  {b['name']}\n  {b['desc']}\n  {owned}\n\n"
        text += "📝 لشراء مبنى: ترقية [اسم المبنى]\nمثال: ترقية اسطبل"
        await update.message.reply_text(text)
        return

    building_ar  = " ".join(args)
    building_key = BUILDING_ALIASES.get(building_ar, args[0])

    if building_key not in BUILDINGS:
        await update.message.reply_text(f"❌ مبنى '{building_ar}' غير موجود!")
        return

    if building_key in farm.get("buildings", []):
        await update.message.reply_text(f"✅ هذا المبنى مملوك بالفعل!")
        return

    binfo = BUILDINGS[building_key]
    if farm["money"] < binfo["price"]:
        await update.message.reply_text(
            f"❌ لا يكفي المال!\n"
            f"تحتاج: {binfo['price']} 💵 | لديك: {farm['money']} 💵"
        )
        return

    farm["money"] -= binfo["price"]
    farm.setdefault("buildings", []).append(building_key)
    save_user(user.id)

    await update.message.reply_text(
        f"🎉 تم بناء {binfo['name']}!\n\n"
        f"✨ {binfo['desc']}\n"
        f"💰 المتبقي: {farm['money']:,} 💵"
    )


async def farm_workers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عمال المزرعة"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    workers = farm.get("workers", 0)
    cost    = 100

    text = (
        f"👷 عمال مزرعتك: {workers}\n\n"
        f"💡 كل عامل يسرّع الإنتاج 10%\n"
        f"💵 استئجار عامل: {cost} 💵\n\n"
        f"💰 رصيدك: {farm['money']} 💵\n"
    )
    keyboard = [
        [InlineKeyboardButton(f"👷 استئجار عامل ({cost} 💵)", callback_data="hire_worker")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def farm_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """احصائيات مزرعتي"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    _, info  = get_farm_level_info(farm.get("exp", 0))

    text = (
        "╔══════════════════════╗\n"
        "║  📊 إحصائيات المزرعة ║\n"
        "╚══════════════════════╝\n\n"
        f"🌾 مستوى المزرعة: {info['name']}\n"
        f"✨ الخبرة: {farm.get('exp', 0)}\n"
        f"💵 أموال المزرعة: {farm['money']:,}\n\n"
        f"📈 الإجمالي:\n"
        f"  🌾 مرات الحصاد: {farm.get('total_harvests', 0)}\n"
        f"  💰 مرات البيع: {farm.get('total_sales', 0)}\n\n"
        f"🏗️ المباني: {', '.join([BUILDINGS[b]['name'] for b in farm.get('buildings', [])]) or 'لا شيء'}\n"
        f"👷 العمال: {farm.get('workers', 0)}\n"
        f"💧 الماء: {farm.get('water', 100)}%\n"
        f"🌱 التربة: {farm.get('soil_quality', 100)}%\n"
    )
    await update.message.reply_text(text)


async def harvest_time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتي - أوقات الحصاد"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    has_gh  = has_building(farm, "greenhouse")

    text = "⏱️ أوقات الحصاد:\n\n"
    text += "🌱 المحاصيل:\n"
    if farm.get("crops"):
        for crop in farm["crops"]:
            sinfo = SEEDS.get(crop["seed_type"], {})
            tl    = farm_time_left(crop["planted_at"], crop["grow_minutes"], has_gh)
            status = "✅ جاهز!" if tl <= 0 else format_time(tl)
            text += f"  {sinfo.get('emoji','🌱')} {sinfo.get('name','؟')}: {status}\n"
    else:
        text += "  لا توجد محاصيل\n"

    text += "\n🐄 منتجات الحيوانات:\n"
    if farm.get("animal_products"):
        for prod in farm["animal_products"]:
            ainfo = ANIMALS.get(prod["animal_type"], {})
            tl    = farm_time_left(prod["started_at"], prod["produce_minutes"])
            status = "✅ جاهز!" if tl <= 0 else format_time(tl)
            text += f"  {ainfo.get('name','؟')} → {ainfo.get('product_name','؟')}: {status}\n"
    else:
        text += "  لا توجد حيوانات\n"

    await update.message.reply_text(text)


async def farm_level_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مستوى مزرعتي"""
    user    = update.effective_user
    db_user = get_user(user.id)
    farm    = db_user["farm"]
    lvl, info     = get_farm_level_info(farm.get("exp", 0))
    next_info     = FARM_LEVELS.get(lvl + 1, {})
    next_exp_need = next_info.get("exp_needed", farm.get("exp", 0))
    exp_bar       = make_progress_bar(farm.get("exp", 0), max(next_exp_need, 1))

    text = (
        "╔══════════════════════╗\n"
        "║  🌟 مستوى مزرعتك    ║\n"
        "╚══════════════════════╝\n\n"
        f"🌾 المستوى الحالي: {info['name']}\n"
        f"✨ الخبرة: {farm.get('exp', 0)} / {next_exp_need}\n"
        f"{exp_bar}\n\n"
        f"📦 سعة المحاصيل: {info['max_crops']}\n"
        f"🐾 سعة الحيوانات: {info['max_animals']}\n\n"
    )
    if next_info:
        text += (
            f"⬆️ المستوى التالي: {next_info.get('name','')}\n"
            f"  📦 سعة: {next_info['max_crops']} محاصيل\n"
            f"  🐾 سعة: {next_info['max_animals']} حيوانات\n"
            f"  🎯 تحتاج: {next_exp_need - farm.get('exp', 0)} خبرة\n\n"
            f"💡 للحصول على خبرة: ازرع واحصد وأطعم حيواناتك!"
        )
    await update.message.reply_text(text)


async def rare_animals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حيوانات نادرة — عرض كل الحيوانات النادرة وتقدم المستخدم"""
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")

    # تحقق من حيوانات جديدة مستحقة
    newly_earned = check_rare_animals(db_user)
    if newly_earned:
        save_user(user.id)
        for _, animal in newly_earned:
            notif = (
                f"🎉 مبروك! حصلت على حيوان نادر!\n\n"
                f"{animal['rarity_emoji']} {animal['name']}\n"
                f"✨ الندرة: {animal['rarity']} {animal['rarity_stars']}\n"
                f"📦 ينتج: {animal['product_name']} كل {format_time(animal['produce_minutes'])}\n"
                f"💰 سعر البيع: {animal['sell_price']:,} 💵\n\n"
                f"أنت من بين القلائل الذين يمتلكونه! 👑"
            )
            if update.message:
                await update.message.reply_text(notif)
            elif update.callback_query:
                await update.callback_query.message.reply_text(notif)

    owned = db_user["farm"].get("rare_animals", [])

    # ━━ بناء الرسالة ━━
    text = (
        "╔══════════════════════════════╗\n"
        "║   ✨ الحيوانات النادرة ✨    ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🏆 مجموعتك: {len(owned)}/{len(RARE_ANIMALS)} حيوان\n\n"
    )

    # عرض المملوكة أولاً
    if owned:
        text += "✅ تمتلكها:\n"
        for aid in owned:
            a = RARE_ANIMALS.get(aid, {})
            text += (
                f"  {a.get('rarity_emoji','')} {a.get('name','')}\n"
                f"     {a.get('rarity','')} {a.get('rarity_stars','')}\n"
                f"     📦 {a.get('product_name','')} كل {format_time(a.get('produce_minutes',60))}\n"
                f"     💰 {a.get('sell_price',0):,} 💵\n\n"
            )

    # عرض غير المملوكة مع التقدم
    not_owned = [(aid, a) for aid, a in RARE_ANIMALS.items() if aid not in owned]
    if not_owned:
        text += "🔒 لم تحصل عليها بعد:\n"
        for aid, a in not_owned:
            try:
                progress = a["progress"](db_user)
            except Exception:
                progress = "—"
            text += (
                f"  {a['rarity_emoji']} {a['name']}\n"
                f"     {a['rarity']} {a['rarity_stars']}\n"
                f"     🎯 {a['how_to_get']}\n"
                f"     📊 {progress}\n\n"
            )

    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "💡 الحيوانات النادرة تنتج منتجات قيّمة تلقائياً!"

    keyboard = [[InlineKeyboardButton("🌾 مزرعتي", callback_data="my_farm")]]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ╔══════════════════════════════════════════╗
# ║            🏦 نظام البنك                 ║
# ╚══════════════════════════════════════════╝

async def my_bank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حسابي البنكي"""
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")
    bank    = db_user["bank"]

    vip_badge = "💎 VIP" if bank.get("vip") else "🔵 عادي"
    transactions = bank.get("transactions", [])[-5:]

    text = (
        "╔══════════════════════════════╗\n"
        "║       🏦 حسابك البنكي 🏦      ║\n"
        "╚══════════════════════════════╝\n\n"
        f"👤 الاسم: {user.first_name}\n"
        f"🔢 رقم الحساب: {bank['account_number']}\n"
        f"🏅 نوع الحساب: {vip_badge}\n"
        f"📅 تاريخ الفتح: {bank.get('created_at', '')[:10]}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 الرصيد الحالي: {bank['balance']:,} 💵\n"
    )
    if bank.get("loan", 0) > 0:
        text += f"⚠️ قرض مستحق: {bank['loan']:,} 💵\n"

    text += "\n📋 آخر المعاملات:\n"
    if transactions:
        for t in reversed(transactions):
            icon = "📤" if t["type"] == "sent" else "📥"
            text += f"  {icon} {t['amount']:,} 💵 | {t.get('note','')}\n"
    else:
        text += "  لا توجد معاملات بعد\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━\n📝 الأوامر:\n  تحويل | رصيدي"

    keyboard = [
        [
            InlineKeyboardButton("💸 تحويل",   callback_data="bank_transfer_start"),
            InlineKeyboardButton("💰 رصيدي",   callback_data="bank_balance"),
        ],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def bank_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رصيدي"""
    user    = update.effective_user
    db_user = get_user(user.id)
    bank    = db_user["bank"]

    text = (
        f"💰 رصيدك البنكي\n\n"
        f"🔢 رقم حسابك: {bank['account_number']}\n"
        f"💵 الرصيد: {bank['balance']:,} 💵\n"
        f"🌾 أموال المزرعة: {db_user['farm']['money']:,} 💵\n"
        f"🪙 عملات البوت: {db_user['coins']}\n\n"
        f"💡 لتحويل الأموال: تحويل"
    )
    if update.callback_query:
        await update.callback_query.answer(f"💰 رصيدك: {bank['balance']:,} 💵", show_alert=True)
    else:
        await update.message.reply_text(text)


async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحويل - بداية عملية التحويل"""
    user    = update.effective_user
    db_user = get_user(user.id)
    bank    = db_user["bank"]

    if bank["balance"] <= 0:
        msg = "❌ رصيدك صفر! لا يمكنك التحويل، اكسب عملات أولاً."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return BANK_TRANSFER_ACCOUNT

    text = (
        "╔══════════════════════════════╗\n"
        "║       💸 تحويل بنكي 💸        ║\n"
        "╚══════════════════════════════╝\n\n"
        f"💵 رصيدك الحالي: {bank['balance']:,} 💵\n\n"
        "📝 الخطوة 1/2:\n"
        "أدخل رقم الحساب المستلم (10 أرقام):\n\n"
        "💡 مثال: 1234567890\n\n"
        "⌨️ أرسل رقم الحساب:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)
    return BANK_TRANSFER_ACCOUNT


async def transfer_receive_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_number = update.message.text.strip()

    if not account_number.isdigit() or len(account_number) != 10:
        await update.message.reply_text(
            "❌ رقم حساب غير صحيح!\n"
            "يجب أن يكون 10 أرقام بالضبط.\n\n"
            "أعد الإدخال:"
        )
        return BANK_TRANSFER_ACCOUNT

    user    = update.effective_user
    db_user = get_user(user.id)

    if account_number == db_user["bank"]["account_number"]:
        await update.message.reply_text("❌ لا يمكنك التحويل لنفسك!")
        return ConversationHandler.END

    target = get_user_by_account(account_number)
    if not target:
        await update.message.reply_text(
            "❌ رقم الحساب غير موجود!\n"
            "تحقق من الرقم وأعد المحاولة:"
        )
        return BANK_TRANSFER_ACCOUNT

    context.user_data["transfer_target_account"] = account_number
    context.user_data["transfer_target_name"]    = display_name(target)
    bank = db_user["bank"]

    await update.message.reply_text(
        f"✅ تم التحقق من الحساب!\n\n"
        f"👤 المستلم: {display_name(target)}\n"
        f"🔢 الحساب: {account_number}\n\n"
        f"💵 رصيدك: {bank['balance']:,}\n\n"
        f"📝 الخطوة 2/2:\n"
        f"أدخل المبلغ المراد تحويله:"
    )
    return BANK_TRANSFER_AMOUNT


async def transfer_receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.strip()

    if not amount_text.isdigit():
        await update.message.reply_text("❌ أدخل رقماً صحيحاً فقط!")
        return BANK_TRANSFER_AMOUNT

    amount  = int(amount_text)
    user    = update.effective_user
    db_user = get_user(user.id)
    bank    = db_user["bank"]

    if amount <= 0:
        await update.message.reply_text("❌ يجب أن يكون المبلغ أكبر من صفر!")
        return BANK_TRANSFER_AMOUNT

    if amount > bank["balance"]:
        await update.message.reply_text(
            f"❌ رصيد غير كافٍ!\n"
            f"طلبت: {amount:,} | لديك: {bank['balance']:,}\n\n"
            f"أدخل مبلغاً أقل:"
        )
        return BANK_TRANSFER_AMOUNT

    target_account = context.user_data.get("transfer_target_account")
    target_name    = context.user_data.get("transfer_target_name")
    target         = get_user_by_account(target_account)

    if not target:
        await update.message.reply_text("❌ خطأ: الحساب غير موجود. أعد المحاولة.")
        return ConversationHandler.END

    # تنفيذ التحويل بشكل ذري — نتحقق من الرصيد مرة أخيرة قبل الخصم
    with _db_lock:
        # إعادة قراءة الرصيد من DB مباشرة لتجنب race condition
        fresh_bank = DB["users"].get(str(user.id), {}).get("bank", bank)
        if fresh_bank["balance"] < amount:
            await update.message.reply_text(
                f"❌ رصيد غير كافٍ بعد التحقق!\n"
                f"المتاح الآن: {fresh_bank['balance']:,} 💵"
            )
            return ConversationHandler.END
        bank["balance"] -= amount
        target["bank"]["balance"] += amount

    # سجل المعاملات
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    bank.setdefault("transactions", []).append({
        "type": "sent", "amount": amount,
        "to": target_account, "note": f"تحويل إلى {target_name}",
        "date": now_str,
    })
    if len(bank["transactions"]) > 20:
        bank["transactions"] = bank["transactions"][-20:]

    target["bank"].setdefault("transactions", []).append({
        "type": "received", "amount": amount,
        "from": bank["account_number"], "note": f"تحويل من {display_name(db_user)}",
        "date": now_str,
    })
    if len(target["bank"]["transactions"]) > 20:
        target["bank"]["transactions"] = target["bank"]["transactions"][-20:]

    save_db(DB)

    newly = check_achievements(db_user)
    save_db(DB)

    result_text = (
        "╔══════════════════════════════╗\n"
        "║     ✅ تم التحويل بنجاح!     ║\n"
        "╚══════════════════════════════╝\n\n"
        f"📤 من: {display_name(db_user)}\n"
        f"📥 إلى: {target_name}\n"
        f"🔢 رقم الحساب: {target_account}\n"
        f"💵 المبلغ المحوّل: {amount:,} 💵\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 رصيدك الآن: {bank['balance']:,} 💵\n"
        f"💰 رصيد المستلم: {target['bank']['balance']:,} 💵\n"
        f"📅 التاريخ: {now_str}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    if newly:
        result_text += "\n\n🏅 " + "\n".join(newly)

    await update.message.reply_text(result_text)

    # أعلم المستلم
    try:
        target_id = target["id"]
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "╔══════════════════════════════╗\n"
                "║      📥 وصلك تحويل! 📥       ║\n"
                "╚══════════════════════════════╝\n\n"
                f"💵 المبلغ: +{amount:,} 💵\n"
                f"📤 من: {display_name(db_user)}\n"
                f"💰 رصيدك الآن: {target['bank']['balance']:,} 💵\n"
                f"📅 {now_str}"
            )
        )
    except Exception:
        pass

    context.user_data.clear()
    return ConversationHandler.END


async def transfer_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ تم إلغاء التحويل.")
    return ConversationHandler.END


# ╔══════════════════════════════════════════╗
# ║         🎮 نظام المسابقات               ║
# ╚══════════════════════════════════════════╝

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ اختر الصعوبة\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🟢 سهل    — 10 نقاط/سؤال\n"
        "🟡 متوسط  — 20 نقطة/سؤال\n"
        "🔴 صعب    — 50 نقطة/سؤال\n"
        "⚫ خبير   — 100 نقطة/سؤال\n\n"
        "🔥 السلسلة تضاعف نقاطك:\n"
        "  ×1.2 سلسلة 3 | ×1.5 سلسلة 5\n"
        "  ×2.0 سلسلة 7 | ×3.0 سلسلة 10!\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    keyboard = [
        [
            InlineKeyboardButton("🟢 سهل",    callback_data="start_game_easy"),
            InlineKeyboardButton("🟡 متوسط",  callback_data="start_game_medium"),
        ],
        [
            InlineKeyboardButton("🔴 صعب",    callback_data="start_game_hard"),
            InlineKeyboardButton("⚫ خبير",   callback_data="start_game_expert"),
        ],
        [InlineKeyboardButton("🔙 رجوع",     callback_data="back_start")],
    ]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")
    today   = date.today().isoformat()
    is_cb   = bool(update.callback_query)

    if db_user.get("daily_played") == today:
        msg = "✅ أخذت مكافأتك اليومية! عد غداً 😊"
        if is_cb:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return

    # مكافأة يومية
    coins_reward = random.randint(50, 150)
    farm_money   = random.randint(30, 80)
    bank_reward  = random.randint(100, 300)

    db_user["daily_played"]           = today
    db_user["coins"]                  += coins_reward
    db_user["farm"]["money"]          += farm_money
    db_user["bank"]["balance"]        += bank_reward
    save_user(user.id)

    text = (
        f"🎁 مكافأة يومية!\n\n"
        f"أهلاً {user.first_name} 🎉\n\n"
        f"🪙 +{coins_reward} عملة بوت\n"
        f"🌾 +{farm_money} 💵 مزرعة\n"
        f"🏦 +{bank_reward} 💵 بنك\n\n"
        f"رصيدك الآن:\n"
        f"🪙 {db_user['coins']:,}  ·  💵 {db_user['farm']['money']:,}  ·  🏦 {db_user['bank']['balance']:,}\n\n"
        f"⏰ عد غداً لمكافأة جديدة!"
    )
    keyboard = [
        [InlineKeyboardButton("🎮 العب الآن", callback_data="play_menu")],
        [InlineKeyboardButton("🌾 مزرعتي",   callback_data="my_farm")],
    ]
    if is_cb:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


PAGE_SIZE = 10  # عدد اللاعبين في كل صفحة

def _build_leaderboard_text(board, page, user_id, db_user):
    RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
    total_pages = max(1, math.ceil(len(board) / PAGE_SIZE))
    start = page * PAGE_SIZE
    end   = start + PAGE_SIZE
    text  = f"🏆 المتصدرون — صفحة {page+1}/{total_pages}\n\n"
    for i, u in enumerate(board[start:end], start=start+1):
        prefix = RANK_MEDALS.get(i, f"{i}.")
        _, lvl_name = get_level(u["points"])
        text += f"{prefix} {display_name(u)}  ·  ⭐ {u['points']:,}  ({lvl_name})\n"
    my_rank = next((i+1 for i, u in enumerate(board) if u["id"] == user_id), "؟")
    _, my_lvl = get_level(db_user["points"])
    text += (
        f"\n⸻\n"
        f"📍 أنت: #{my_rank}  ·  ⭐ {db_user['points']:,}  ·  {my_lvl}"
    )
    return text, total_pages

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📅 التحدي الأسبوعي
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def weekly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحدي أسبوعي بمكافأة كبيرة"""
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")
    is_cb   = bool(update.callback_query)

    # حساب أرقام الأسبوع الحالي
    today     = date.today()
    week_num  = today.isocalendar()[1]
    year      = today.isocalendar()[0]
    week_key  = f"weekly_{year}_{week_num}"

    # نهاية الأسبوع (الأحد القادم)
    days_left = 6 - today.weekday() if today.weekday() <= 6 else 0

    if db_user.get(week_key) == "done":
        msg = (
            "✅ أكملت تحدي هذا الأسبوع!\n"
            f"⏳ التحدي الجديد يبدأ بعد {days_left} يوم/أيام.\n"
            "💪 عد الأسبوع القادم لمكافأة أكبر!"
        )
        if is_cb:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return

    # أجب على 30 سؤالاً صحيحة هذا الأسبوع
    weekly_correct = db_user.get(f"weekly_correct_{year}_{week_num}", 0)
    target         = 30
    progress       = min(weekly_correct, target)
    prog_bar       = make_progress_bar(progress, target, 12)

    if progress >= target:
        # منح المكافأة
        coins_r  = 2000
        bank_r   = 5000
        farm_r   = 1500
        db_user["coins"]           += coins_r
        db_user["bank"]["balance"] += bank_r
        db_user["farm"]["money"]   += farm_r
        db_user[week_key]           = "done"
        mark_dirty()
        text = (
            f"🏆 أكملت التحدي الأسبوعي!\n\n"
            f"🎉 أجبت على {target} سؤالاً صحيحاً!\n\n"
            f"🪙 +{coins_r:,} عملة\n"
            f"🏦 +{bank_r:,} 💵 بنك\n"
            f"🌾 +{farm_r:,} 💵 مزرعة\n\n"
            f"⏳ التحدي الجديد بعد {days_left} يوم!"
        )
    else:
        remaining = target - progress
        text = (
            f"📅 التحدي الأسبوعي\n\n"
            f"🎯 الهدف: {target} سؤال صحيح\n\n"
            f"{prog_bar}  {progress}/{target}\n\n"
            f"📌 المتبقي: {remaining} سؤال\n"
            f"⏳ ينتهي بعد: {days_left} يوم\n\n"
            f"🎁 المكافأة عند الإتمام:\n"
            f"🪙 2,000  ·  🏦 5,000  ·  🌾 1,500\n\n"
            f"💡 العب الآن: /play"
        )

    keyboard = [
        [InlineKeyboardButton("🎮 العب الآن", callback_data="play_menu")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_start")],
    ]
    if is_cb:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    user    = update.effective_user
    db_user = get_user(user.id)
    board   = get_leaderboard()
    text, total_pages = _build_leaderboard_text(board, page, user.id, db_user)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"lb_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"lb_page_{page+1}"))
    keyboard = []
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_start")])

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_user = get_user(user.id)
    _, lvl_name = get_level(db_user["points"])
    total   = db_user["total_correct"] + db_user["total_wrong"]
    acc     = round(db_user["total_correct"] / max(total, 1) * 100)
    _, fi   = get_farm_level_info(db_user["farm"].get("exp", 0))

    text = (
        f"👤 {user.first_name}  ·  @{user.username or '—'}\n\n"
        f"🎮 المسابقات\n"
        f"⭐ {db_user['points']:,} نقطة  ·  📈 {lvl_name}\n"
        f"🎯 الدقة: {acc}%  ·  🎮 {db_user['total_played']} مباراة\n"
        f"🔥 أفضل سلسلة: {db_user['best_streak']}\n\n"
        f"🌾 المزرعة\n"
        f"📊 {fi['name']}\n"
        f"💵 {db_user['farm']['money']:,}  ·  🌾 {db_user['farm'].get('total_harvests', 0)} حصادة\n\n"
        f"🏦 البنك\n"
        f"💰 {db_user['bank']['balance']:,} 💵\n"
        f"🔢 رقم الحساب: {db_user['bank']['account_number']}\n\n"
        f"🪙 عملات البوت: {db_user['coins']:,}\n"
        f"🏅 الإنجازات: {len(db_user['achievements'])}/{len(ALL_ACHIEVEMENTS)}"
    )
    keyboard = [[InlineKeyboardButton("🎮 العب الآن", callback_data="play_menu")]]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_user = get_user(user.id)
    total   = db_user["total_correct"] + db_user["total_wrong"]
    acc     = round(db_user["total_correct"] / max(total, 1) * 100)
    bar     = make_progress_bar(db_user["total_correct"], max(total, 1))
    await update.message.reply_text(
        f"📊 إحصائياتك\n\n"
        f"🎯 {bar}  {acc}%\n\n"
        f"✅ صحيح: {db_user['total_correct']}\n"
        f"❌ خطأ: {db_user['total_wrong']}\n"
        f"🔥 أفضل سلسلة: {db_user['best_streak']}\n"
        f"🌟 النقاط: {db_user['points']:,}"
    )


async def achievements_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_user = get_user(user.id)
    total   = db_user["total_correct"] + db_user["total_wrong"]
    conditions = {
        "first_game":   total >= 1,
        "10_correct":   db_user["total_correct"] >= 10,
        "streak_5":     db_user["best_streak"] >= 5,
        "streak_10":    db_user["best_streak"] >= 10,
        "100_points":   db_user["points"] >= 100,
        "500_points":   db_user["points"] >= 500,
        "1000_points":  db_user["points"] >= 1000,
        "first_win":    db_user.get("challenge_wins", 0) >= 1,
        "first_harvest":db_user["farm"].get("total_harvests", 0) >= 1,
        "farm_lvl3":    db_user["farm"].get("level", 1) >= 3,
        "rich_farmer":  db_user["farm"].get("money", 0) >= 5000,
        "bank_1000":    db_user["bank"].get("balance", 0) >= 1000,
        "transfer_1":   len(db_user["bank"].get("transactions", [])) >= 1,
    }
    unlocked = [f"✅ {a['name']} — {a['desc']}" for a in ALL_ACHIEVEMENTS if conditions.get(a["id"])]
    locked   = [f"🔒 {a['name']} — {a['desc']}" for a in ALL_ACHIEVEMENTS if not conditions.get(a["id"])]
    text = (
        f"🏅 الإنجازات  ·  {len(unlocked)}/{len(ALL_ACHIEVEMENTS)} مكتملة\n\n"
        + ("\n".join(unlocked) + "\n\n" if unlocked else "")
        + ("🔒 المقفلة:\n" + "\n".join(locked) if locked else "")
    )
    if update.message:
        await update.message.reply_text(text)
    else:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]]
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_user = get_user(user.id)
    text = (
        f"🛒 المتجر\n\n"
        f"🪙 عملاتك: {db_user['coins']:,}\n\n"
        f"🎮 مساعدات المسابقة\n"
        f"💡 تلميح    —  10 🪙  (يكشف خيار خاطئ)\n"
        f"❤️ حياة    —  20 🪙  (حياة إضافية)\n"
        f"⚡ مضاعفة  —  50 🪙  (ضاعف نقاط السؤال)\n\n"
        f"🌾 مساعدات المزرعة\n"
        f"💧 ماء إضافي  —  15 🪙  (+50% ماء)\n"
        f"🌿 سماد      —  25 🪙  (يسرّع النمو 50%)\n\n"
        f"⭐ شراء بالنجوم\n"
        f"⭐ صغيرة  50  ·  🌟 متوسطة  150\n"
        f"💎 كبيرة  350  ·  👑 بطل  750"
    )
    keyboard = [
        [
            InlineKeyboardButton("💡 تلميح (10🪙)", callback_data="buy_hint"),
            InlineKeyboardButton("❤️ حياة (20🪙)",  callback_data="buy_life"),
        ],
        [
            InlineKeyboardButton("⚡ مضاعفة (50🪙)", callback_data="buy_double"),
            InlineKeyboardButton("💧 ماء (15🪙)",    callback_data="buy_water"),
        ],
        [
            InlineKeyboardButton("🌿 سماد (25🪙)", callback_data="buy_fertilizer"),
        ],
        [InlineKeyboardButton("⭐ شراء بالنجوم", callback_data="stars_shop")],
    ]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⏱️ نظام الكولداون (20 دقيقة)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COOLDOWN_MINUTES = 20
# {user_id: {"invest": datetime, "luck": datetime, "baqshish": datetime}}
cooldowns: dict = {}

def check_cooldown(user_id: int, action: str) -> int:
    """يرجع الدقائق المتبقية (0 = مسموح)"""
    last = cooldowns.get(user_id, {}).get(action)
    if not last:
        return 0
    elapsed = (datetime.now() - last).total_seconds() / 60
    remaining = COOLDOWN_MINUTES - elapsed
    return max(0, remaining)

def set_cooldown(user_id: int, action: str):
    cooldowns.setdefault(user_id, {})[action] = datetime.now()

def fmt_cooldown(minutes: float) -> str:
    m = int(minutes)
    s = int((minutes - m) * 60)
    if m > 0:
        return f"{m} دقيقة و{s} ثانية"
    return f"{s} ثانية"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💰 نظام الاستثمار
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def invest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استثمار - يضاعف عملات المستخدم من 1% إلى 25%"""
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")

    remaining = check_cooldown(user.id, "invest")
    if remaining > 0:
        await update.message.reply_text(
            f"⏳ الاستثمار متاح كل {COOLDOWN_MINUTES} دقيقة!\n"
            f"⏱️ انتظر: {fmt_cooldown(remaining)}"
        )
        return

    coins = db_user["coins"]
    if coins <= 0:
        await update.message.reply_text(
            "❌ ما عندك عملات تستثمرها!\n"
            "💡 اكسب عملات عن طريق الألعاب أو المكافأة اليومية."
        )
        return

    percent = random.uniform(1, 25)
    gained  = max(1, int(coins * percent / 100))
    db_user["coins"] += gained
    set_cooldown(user.id, "invest")
    save_user(user.id)

    stars = "⭐" * min(5, int(percent / 5) + 1)
    await update.message.reply_text(
        f"💹 نتيجة الاستثمار!\n\n"
        f"📊 نسبة الربح: {percent:.1f}%  {stars}\n"
        f"💰 كانت عندك: {coins:,} 🪙\n"
        f"✅ ربحت: +{gained:,} 🪙\n"
        f"🏦 رصيدك الآن: {db_user['coins']:,} 🪙\n\n"
        f"⏱️ الاستثمار القادم بعد {COOLDOWN_MINUTES} دقيقة"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎲 نظام الحظ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def luck_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظ [مبلغ] - جرّب حظك على عملاتك"""
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")
    text_msg = update.message.text.strip()
    parts   = text_msg.split()

    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text(
            "🎲 طريقة الاستخدام:\n\n"
            "حظ [مبلغ]\n"
            "مثال: حظ 500\n\n"
            f"🪙 عملاتك الحالية: {db_user['coins']:,}"
        )
        return

    remaining = check_cooldown(user.id, "luck")
    if remaining > 0:
        await update.message.reply_text(
            f"⏳ الحظ متاح كل {COOLDOWN_MINUTES} دقيقة!\n"
            f"⏱️ انتظر: {fmt_cooldown(remaining)}"
        )
        return

    bet = int(parts[1])
    if bet <= 0:
        await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من صفر!")
        return

    if bet > db_user["coins"]:
        await update.message.reply_text(
            f"❌ ما عندك كافٍ!\n"
            f"راهنت: {bet:,} 🪙\n"
            f"عندك: {db_user['coins']:,} 🪙"
        )
        return

    win = random.random() < 0.51
    set_cooldown(user.id, "luck")
    if win:
        db_user["coins"] += bet
        save_user(user.id)
        await update.message.reply_text(
            "🎉 مبروك فزت بالحظ! 🎉\n\n"
            f"🎲 راهنت: {bet:,} 🪙\n"
            f"✅ ربحت: +{bet:,} 🪙\n"
            f"🏆 رصيدك الآن: {db_user['coins']:,} 🪙\n\n"
            f"🍀 الحظ القادم بعد {COOLDOWN_MINUTES} دقيقة"
        )
    else:
        db_user["coins"] -= bet
        save_user(user.id)
        await update.message.reply_text(
            "😔 خسرت هالمرة!\n\n"
            f"🎲 راهنت: {bet:,} 🪙\n"
            f"❌ خسرت: -{bet:,} 🪙\n"
            f"💔 رصيدك الآن: {db_user['coins']:,} 🪙\n\n"
            f"⏱️ الحظ القادم بعد {COOLDOWN_MINUTES} دقيقة"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎁 البقشيش
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def baqshish_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بقشيش - احصل على بقشيش عشوائي"""
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")

    remaining = check_cooldown(user.id, "baqshish")
    if remaining > 0:
        await update.message.reply_text(
            f"⏳ البقشيش متاح كل {COOLDOWN_MINUTES} دقيقة!\n"
            f"⏱️ انتظر: {fmt_cooldown(remaining)}"
        )
        return

    amount  = random.randint(200, 1500)
    db_user["coins"] += amount
    set_cooldown(user.id, "baqshish")
    save_user(user.id)
    reactions = ["🤑","💸","🎊","🤩","✨","🔥"]
    react = random.choice(reactions)
    await update.message.reply_text(
        f"تفضل، هدية مجانية لك {react}\n\n"
        f"🎁 البقشيش: +{amount:,} 🪙\n"
        f"💰 رصيدك الآن: {db_user['coins']:,} 🪙\n\n"
        f"⏱️ البقشيش القادم بعد {COOLDOWN_MINUTES} دقيقة"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧠 مود الأسئلة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def quiz_mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مود - اختر فئة الأسئلة"""
    user    = update.effective_user
    current = user_quiz_mode.get(user.id, "all")
    cur_info = QUIZ_MODES.get(current, QUIZ_MODES["all"])
    text = (
        f"🧠 فئة الأسئلة\n\n"
        f"📌 الفئة الحالية: {cur_info['name']}\n\n"
        "اختر الفئة التي تريد:\n"
    )
    keyboard = []
    modes_list = list(QUIZ_MODES.items())
    for i in range(0, len(modes_list), 2):
        row = []
        for key, info in modes_list[i:i+2]:
            label = f"{'✅ ' if key == current else ''}{info['name']}"
            row.append(InlineKeyboardButton(label, callback_data=f"qmode_{key}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🎮 العب الآن", callback_data="play_menu")])

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_user = get_user(user.id)
    lvl, lvl_name = get_level(db_user["points"])
    next_t  = LEVEL_THRESHOLDS[min(lvl, len(LEVEL_THRESHOLDS)-1)]
    needed  = max(0, next_t - db_user["points"])
    await update.message.reply_text(
        f"⭐ نقاطك\n\n"
        f"🌟 {db_user['points']:,} نقطة\n"
        f"📈 المستوى: {lvl_name}\n"
        f"🪙 العملات: {db_user['coins']:,}\n"
        f"🎯 للمستوى التالي: {needed:,} نقطة"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ التحديات
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚔️ استخدم: /challenge @username [رهان]\nمثال: /challenge @Ahmad 50")
        return

    challenger  = update.effective_user
    db_ch       = get_user(challenger.id, challenger.username or "", challenger.first_name or "")
    target_un   = context.args[0].lstrip("@")
    bet         = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 20
    bet         = max(5, min(bet, 200))

    if db_ch["coins"] < bet:
        await update.message.reply_text(f"❌ لا يكفي! تحتاج {bet} 🪙 | لديك {db_ch['coins']} 🪙")
        return

    target = None
    for u in DB["users"].values():
        if u.get("username", "").lower() == target_un.lower():
            target = u
            break

    if not target:
        await update.message.reply_text(f"❌ لم أجد @{target_un}! يجب أن يكون مسجلاً في البوت.")
        return
    if target["id"] == challenger.id:
        await update.message.reply_text("❌ لا تستطيع تحدي نفسك!")
        return

    cid = f"{challenger.id}_{target['id']}_{int(datetime.now().timestamp())}"
    shared_q = [get_random_question(difficulty="medium") for _ in range(5)]
    shared_q = [q for q in shared_q if q]

    challenges_db[cid] = {
        "id": cid, "challenger_id": challenger.id,
        "challenger_name": challenger.first_name or challenger.username or "صديقي",
        "target_id": target["id"], "target_name": display_name(target),
        "bet": bet, "questions": shared_q, "status": "pending",
        "challenger_score": None, "target_score": None,
        "challenger_correct": 0, "target_correct": 0,
    }

    await update.message.reply_text(
        f"⚔️ تم إرسال التحدي لـ @{target_un}!\n"
        f"💰 الرهان: {bet} 🪙 | 🎯 {len(shared_q)} أسئلة\n"
        f"⏳ انتظر قبول الخصم..."
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ قبول",  callback_data=f"accept_chal_{cid}"),
            InlineKeyboardButton("❌ رفض",   callback_data=f"decline_chal_{cid}"),
        ]
    ]
    try:
        await context.bot.send_message(
            chat_id=target["id"],
            text=(
                f"⚔️ تحدٍّ من {challenger.first_name}!\n"
                f"💰 الرهان: {bet} 🪙 | 🎯 {len(shared_q)} أسئلة\n"
                f"هل تقبل؟"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        await update.message.reply_text(f"⚠️ لم أتمكن من إرسال رسالة للخصم مباشرة.")


async def accept_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        pending = [c for c in challenges_db.values() if c["target_id"] == user.id and c["status"] == "pending"]
        if not pending:
            await update.message.reply_text("لا توجد تحديات معلّقة لك.")
            return
        await update.message.reply_text("\n".join([f"🆔 {c['id'][:20]}... من {c['challenger_name']}" for c in pending]))
        return
    await _accept_challenge_by_id(update, context, context.args[0], user)


async def _accept_challenge_by_id(update, context, cid, user):
    chal = challenges_db.get(cid)
    if not chal or chal["target_id"] != user.id or chal["status"] != "pending":
        msg = "❌ تحدٍّ غير صالح."
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.answer(msg, show_alert=True)
        return

    db_target = get_user(user.id)
    if db_target["coins"] < chal["bet"]:
        msg = f"❌ لا تملك كافية! تحتاج {chal['bet']} 🪙"
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.answer(msg, show_alert=True)
        return

    chal["status"] = "playing"
    start_text = f"⚔️ التحدي بدأ! {chal['challenger_name']} VS {chal['target_name']}\n💰 الرهان: {chal['bet']} 🪙"

    target_msg = update.callback_query.message if update.callback_query else update.message
    await target_msg.reply_text(start_text)
    await _start_chal_game(update, context, chal, user.id, False)
    try:
        await context.bot.send_message(chat_id=chal["challenger_id"], text=start_text)
        await _start_chal_game_direct(context, chal, chal["challenger_id"], True)
    except Exception as e:
        logger.error(f"Challenge notify error: {e}")


async def decline_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("استخدم: /decline [رقم التحدي]")
        return
    chal = challenges_db.get(context.args[0])
    if not chal or chal["target_id"] != user.id or chal["status"] != "pending":
        await update.message.reply_text("❌ تحدٍّ غير صالح.")
        return
    chal["status"] = "declined"
    await update.message.reply_text(f"✅ رفضت التحدي من {chal['challenger_name']}.")
    try:
        await context.bot.send_message(chat_id=chal["challenger_id"], text=f"❌ {display_name(get_user(user.id))} رفض تحديك!")
    except Exception:
        pass


async def mybets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    my   = [c for c in challenges_db.values() if c["challenger_id"] == user.id or c["target_id"] == user.id]
    if not my:
        await update.message.reply_text("لا توجد تحديات. /challenge @username")
        return
    sm = {"pending":"⏳","playing":"🎮","finished":"✅","declined":"❌"}
    lines = [f"{sm.get(c['status'],'?')} {'أنت تحديت' if c['challenger_id']==user.id else 'تحداك'} {'المقابل'} | {c['bet']} 🪙" for c in my[-10:]]
    await update.message.reply_text("⚔️ تحدياتك:\n\n" + "\n".join(lines))


async def _start_chal_game(update, context, chal, user_id, is_ch):
    key = f"chal_{chal['id']}_{user_id}"
    games_db[key] = {
        "type":"challenge","challenge_id":chal["id"],"is_challenger":is_ch,
        "user_id":user_id,"questions":chal["questions"],"current":0,
        "correct":0,"points":0,"lives":3,"streak":0,"best_streak":0,
        "difficulty":"medium","start_time":datetime.now(),
    }
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text("🎮 دورك في التحدي!")
    await _send_chal_q(context, key, target.chat_id)


async def _start_chal_game_direct(context, chal, user_id, is_ch):
    key = f"chal_{chal['id']}_{user_id}"
    games_db[key] = {
        "type":"challenge","challenge_id":chal["id"],"is_challenger":is_ch,
        "user_id":user_id,"questions":chal["questions"],"current":0,
        "correct":0,"points":0,"lives":3,"streak":0,"best_streak":0,
        "difficulty":"medium","start_time":datetime.now(),
    }
    await context.bot.send_message(chat_id=user_id, text="🎮 دورك في التحدي!")
    await _send_chal_q(context, key, user_id)


async def _send_chal_q(context, game_key, chat_id):
    game = games_db.get(game_key)
    if not game: return
    idx = game["current"]
    if idx >= len(game["questions"]):
        await _end_chal_game(context, game_key, chat_id)
        return
    q    = game["questions"][idx]
    mult = get_streak_multiplier(game["streak"])
    text = (
        f"⚔️ تحدٍّ | سؤال {idx+1}/{len(game['questions'])}\n\n"
        f"{q['q']}\n\n" + "\n".join(q["options"]) +
        f"\n\n🔥 سلسلة: {game['streak']}" + (f" ×{mult}" if mult>1 else "") +
        f"\n❤️ {lives_bar(game['lives'])}"
    )
    keyboard = [
        [InlineKeyboardButton("A", callback_data=f"cans_{game_key}_A"), InlineKeyboardButton("B", callback_data=f"cans_{game_key}_B")],
        [InlineKeyboardButton("C", callback_data=f"cans_{game_key}_C"), InlineKeyboardButton("D", callback_data=f"cans_{game_key}_D")],
    ]
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))


async def _end_chal_game(context, game_key, chat_id):
    game = games_db.pop(game_key, None)
    if not game: return
    chal = challenges_db.get(game["challenge_id"])
    if not chal: return
    if game["is_challenger"]:
        chal["challenger_score"]  = game["points"]
        chal["challenger_correct"] = game["correct"]
    else:
        chal["target_score"]  = game["points"]
        chal["target_correct"] = game["correct"]

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏹️ انتهت جولتك!\n✅ صحيح: {game['correct']}/{len(game['questions'])}\n🌟 نقاطك: {game['points']}\n⏳ انتظر نتيجة خصمك..."
    )
    if chal["challenger_score"] is not None and chal["target_score"] is not None:
        await _announce_chal_result(context, chal)


async def _announce_chal_result(context, chal):
    chal["status"] = "finished"
    cs, ts = chal["challenger_score"], chal["target_score"]
    db_ch  = get_user(chal["challenger_id"])
    db_tg  = get_user(chal["target_id"])

    if cs > ts:
        w_db, l_db = db_ch, db_tg
        w_name, l_name = chal["challenger_name"], chal["target_name"]
        w_id, l_id = chal["challenger_id"], chal["target_id"]
    elif ts > cs:
        w_db, l_db = db_tg, db_ch
        w_name, l_name = chal["target_name"], chal["challenger_name"]
        w_id, l_id = chal["target_id"], chal["challenger_id"]
    else:
        result = f"🤝 تعادل!\n{chal['challenger_name']}: {cs} | {chal['target_name']}: {ts}\nالرهان يُعاد للجميع."
        for uid in [chal["challenger_id"], chal["target_id"]]:
            try: await context.bot.send_message(chat_id=uid, text=result)
            except: pass
        return

    bet = min(chal["bet"], l_db["coins"])
    w_db["coins"] += bet
    l_db["coins"] -= bet
    w_db["challenge_wins"] = w_db.get("challenge_wins", 0) + 1
    l_db["challenge_losses"] = l_db.get("challenge_losses", 0) + 1
    newly = check_achievements(w_db)
    save_db(DB)

    result = (
        f"🏆 نتيجة التحدي!\n\n"
        f"🥇 الفائز: {w_name}\n🥈 الخاسر: {l_name}\n\n"
        f"📊 {chal['challenger_name']}: {cs} | {chal['target_name']}: {ts}\n\n"
        f"💰 الفائز يأخذ: +{bet} 🪙"
    )
    for uid, extra in [(w_id, "\n🏅 " + "\n".join(newly) if newly else ""), (l_id, "")]:
        try: await context.bot.send_message(chat_id=uid, text=result + extra)
        except: pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎮 اللعبة العادية
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _start_game(update, context, difficulty):
    user = update.effective_user
    mode_key = user_quiz_mode.get(user.id, "all")
    # جمع 10 أسئلة بترتيب تسلسلي بدون تكرار (10 أسئلة فقط)
    qs = []
    seen = set()
    for _ in range(10):
        q = get_random_question(difficulty=difficulty, mode_key=mode_key, user_id=user.id)
        if q:
            q_id = q.get("q", "")
            if q_id not in seen:
                seen.add(q_id)
                qs.append(q)
    if not qs:
        msg = "❌ لا توجد أسئلة في هذا المود لهذا المستوى.\n💡 غيّر المود: اكتب 'مود'"
        if update.message: await update.message.reply_text(msg)
        else: await update.callback_query.message.reply_text(msg)
        return
    # تنبيه إذا كان عدد الأسئلة أقل من المتوقع
    if len(qs) < 10:
        mode_info = QUIZ_MODES.get(mode_key, QUIZ_MODES["all"])
        warn = (
            f"⚠️ هذا المود ({mode_info['name']}) يحتوي على {len(qs)} سؤال فقط "
            f"بمستوى {difficulty}.\nاللعبة ستبدأ بهذا العدد.\n"
            f"💡 لمزيد من الأسئلة غيّر المود: اكتب 'مود'"
        )
        if update.message:
            await update.message.reply_text(warn)
        elif update.callback_query:
            await update.callback_query.message.reply_text(warn)

    mode_info = QUIZ_MODES.get(mode_key, QUIZ_MODES["all"])
    games_db[user.id] = {
        "type":"normal","questions":qs,"current":0,"correct":0,"wrong":0,
        "lives":3,"points":0,"difficulty":difficulty,"start_time":datetime.now(),
        "streak":0,"best_streak":0,"mode":mode_key,
        "game_message": None,  # سيُحفظ هنا مرجع الرسالة
    }
    # أول سؤال مباشرة — نعدّل رسالة الصعوبة في مكانها
    await _send_question(update, context, user.id)


async def _send_question(update, context, user_id):
    game = games_db.get(user_id)
    if not game: return
    idx = game["current"]
    if idx >= len(game["questions"]):
        await _end_game(update, context, user_id)
        return
    q    = game["questions"][idx]
    mult = get_streak_multiplier(game["streak"])
    dp   = DIFFICULTY_POINTS.get(game["difficulty"], 20)
    mode_info = QUIZ_MODES.get(game.get("mode","all"), QUIZ_MODES["all"])
    text = (
        f"{DIFFICULTY_EMOJI.get(game['difficulty'],'🟡')} {mode_info['name']} | سؤال {idx+1}/{len(game['questions'])}\n"
        f"{'─'*28}\n"
        f"❓ {CATEGORIES_EMOJI.get(q.get('category',''),'❓')} {q['q']}\n\n"
        + "\n".join(q["options"]) +
        f"\n{'─'*28}\n"
        f"💎 {dp}" + (f" ×{mult:.1f}" if mult>1 else "") +
        f" | 🔥 سلسلة: {game['streak']}\n❤️ {lives_bar(game['lives'])}"
    )
    keyboard = [
        [InlineKeyboardButton("A", callback_data=f"answer_{user_id}_A"), InlineKeyboardButton("B", callback_data=f"answer_{user_id}_B")],
        [InlineKeyboardButton("C", callback_data=f"answer_{user_id}_C"), InlineKeyboardButton("D", callback_data=f"answer_{user_id}_D")],
        [InlineKeyboardButton("💡 تلميح (-10 🪙)", callback_data=f"hint_{user_id}")],
    ]
    # إذا عندنا رسالة محفوظة، نعدّلها — وإلا نرسل رسالة جديدة ونحفظها
    if game.get("game_message"):
        try:
            await game["game_message"].edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        except Exception:
            pass  # إذا فشل التعديل، نرسل رسالة جديدة

    # أول مرة أو إذا فشل التعديل
    if update and update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            game["game_message"] = update.callback_query.message
        except Exception:
            msg = await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            game["game_message"] = msg
    elif update and update.message:
        msg = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        game["game_message"] = msg
    else:
        msg = await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        game["game_message"] = msg


async def _end_game(update, context, user_id):
    game    = games_db.pop(user_id, None)
    if not game: return
    db_user = get_user(user_id)
    total_q = len(game["questions"])
    acc     = round(game["correct"] / max(total_q, 1) * 100)
    elapsed = (datetime.now() - game["start_time"]).seconds

    bonus, bonuses = 0, []
    if acc == 100:  bonus += 30; bonuses.append("🎯 +30 مثالي!")
    elif acc >= 80: bonus += 10; bonuses.append("🎯 +10 دقة عالية")
    if game["best_streak"] >= 7: bonus += 20; bonuses.append("🔥 +20 سلسلة أسطورية")
    elif game["best_streak"] >= 5: bonus += 10; bonuses.append("🔥 +10 سلسلة رائعة")

    total_pts = game["points"] + bonus
    db_user["points"]        += total_pts
    db_user["coins"]         += total_pts // 5
    db_user["farm"]["money"] += total_pts // 10   # مكافأة للمزرعة
    db_user["bank"]["balance"] += total_pts // 8  # مكافأة للبنك
    db_user["total_played"]  += 1
    db_user["total_correct"] += game["correct"]
    # تتبع الإجابات الصحيحة للتحدي الأسبوعي
    _wk = date.today().isocalendar()
    _week_key = f"weekly_correct_{_wk[0]}_{_wk[1]}"
    db_user[_week_key] = db_user.get(_week_key, 0) + game["correct"]
    db_user["total_wrong"]   += game.get("wrong", 0)
    db_user["best_streak"]    = max(db_user["best_streak"], game["best_streak"])
    newly = check_achievements(db_user)
    newly_rare = check_rare_animals(db_user)
    save_user(user_id)

    _, lvl_name = get_level(db_user["points"])
    board   = get_leaderboard()
    my_rank = next((i+1 for i, u in enumerate(board) if u["id"] == user_id), "؟")

    text = (
        f"🎊 انتهت اللعبة!\n\n"
        f"✅ {game['correct']}/{total_q} | ❌ {game.get('wrong',0)}/{total_q}\n"
        f"🎯 الدقة: {acc}% | ⏱️ {elapsed//60}:{elapsed%60:02d}\n"
        f"💎 النقاط: {game['points']}" +
        (f"\n🎁 بونص:\n" + "\n".join(bonuses) if bonuses else "") +
        f"\n⭐ المجموع: +{total_pts}\n"
        f"🌾 مزرعتك: +{total_pts//10} 💵\n"
        f"🏦 بنكك: +{total_pts//8} 💵\n\n"
        f"📈 {lvl_name} | 🏆 #{my_rank} | 🌟 {db_user['points']:,}"
    )
    if newly:
        text += "\n\n🏅 إنجازات:\n" + "\n".join(newly)
    if newly_rare:
        for _, rare in newly_rare:
            text += f"\n\n🎊 حيوان نادر جديد: {rare['name']} {rare['rarity_stars']}"

    keyboard = [
        [InlineKeyboardButton("🔄 لعبة جديدة", callback_data="play_menu"), InlineKeyboardButton("🏆 المتصدرون", callback_data="leaderboard")],
        [InlineKeyboardButton("🌾 مزرعتي", callback_data="my_farm"), InlineKeyboardButton("🏦 بنكي", callback_data="my_bank")],
    ]
    # عدّل نفس رسالة اللعبة إن وُجدت
    game_msg = game.get("game_message") if game else None
    if game_msg:
        try:
            await game_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        except Exception:
            pass
    # fallback
    if update and update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update and update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔘 معالج الأزرار
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    user  = update.effective_user

    if data == "play_menu":          await play(update, context); return
    if data == "leaderboard":        await leaderboard(update, context); return
    if data == "profile":            await profile_cmd(update, context); return
    if data == "daily":              await daily(update, context); return
    if data == "achievements_cb":    await achievements_cmd(update, context); return
    if data == "shop_menu":          await shop_cmd(update, context); return
    if data == "weekly_cb":          await weekly_cmd(update, context); return
    if data == "my_farm":            await my_farm(update, context); return
    if data == "my_bank":            await my_bank_cmd(update, context); return
    if data == "bank_balance":       await bank_balance_cmd(update, context); return
    if data == "rare_animals":       await rare_animals_cmd(update, context); return

    # ━━ تنقل صفحات adminstats ━━
    if data.startswith("adminstats_page_"):
        if user.id != OWNER_ID and OWNER_ID != 0:
            await query.answer("❌ للمالك فقط!", show_alert=True)
            return
        page  = int(data.replace("adminstats_page_", ""))
        top50 = context.bot_data.get("adminstats_top50", [])
        if not top50:
            await query.answer("❌ انتهت الجلسة، أعد /adminstats", show_alert=True)
            return

        start_i = page * 10
        end_i   = start_i + 10
        chunk   = top50[start_i:end_i]

        import html as _html

        users_text = ""
        for i, u in enumerate(chunk, start=start_i + 1):
            uid    = u.get("id", 0)
            name   = _html.escape(u.get("first_name") or u.get("username") or "مجهول")
            played = u.get("total_played", 0)
            users_text += f"  {i:>2}. <a href=\"tg://user?id={uid}\">{name}</a> — {played:,} 🎮\n"

        # إعادة بناء الإحصائيات العامة
        all_users        = list(DB["users"].values())
        total_users      = len(all_users)
        total_played     = sum(u.get("total_played", 0) for u in all_users)
        total_correct    = sum(u.get("correct_answers", 0) for u in all_users)
        total_chal_wins  = sum(u.get("challenge_wins", 0) for u in all_users)
        total_coins      = sum(u.get("coins", 0) for u in all_users)
        total_farm_money = sum(u.get("farm", {}).get("money", 0) for u in all_users)
        total_bank       = sum(u.get("bank", {}).get("balance", 0) for u in all_users)
        total_harvests   = sum(u.get("farm", {}).get("total_harvests", 0) for u in all_users)

        text = (
            f"👑 إحصائيات البوت\n\n"
            f"👥 المستخدمون: {total_users:,}\n"
            f"🎮 الألعاب: {total_played:,}\n"
            f"✅ إجابات صحيحة: {total_correct:,}\n"
            f"⚔️ انتصارات تحديات: {total_chal_wins:,}\n\n"
            f"💰 الاقتصاد\n"
            f"🪙 العملات: {total_coins:,}\n"
            f"🌾 المزارع: {total_farm_money:,}\n"
            f"🏦 البنوك: {total_bank:,}\n"
            f"🌱 الحصادات: {total_harvests:,}\n\n"
            f"🏆 أكثر نشاطاً — صفحة {page + 1}/{math.ceil(len(top50)/10) or 1}:\n"
            f"{users_text}"
        )

        btns = []
        if page > 0:
            btns.append(InlineKeyboardButton("◀️ السابق", callback_data=f"adminstats_page_{page - 1}"))
        if end_i < len(top50):
            btns.append(InlineKeyboardButton("التالي ▶️", callback_data=f"adminstats_page_{page + 1}"))
        keyboard = InlineKeyboardMarkup([btns]) if btns else None

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    if data == "bank_transfer_start":
        await transfer_start(update, context)
        return

    # ━━ مود الأسئلة ━━
    if data.startswith("qmode_"):
        mode_key = data[6:]
        if mode_key in QUIZ_MODES:
            user_quiz_mode[user.id] = mode_key
            mode_info = QUIZ_MODES[mode_key]
            await query.answer(f"✅ تم! المود: {mode_info['name']}", show_alert=True)
            await quiz_mode_cmd(update, context)
        return

    # ━━ pagination المتصدرين ━━
    if data.startswith("lb_page_"):
        try:
            pg = int(data.replace("lb_page_", ""))
        except ValueError:
            pg = 0
        await leaderboard(update, context, page=pg)
        return

    if data == "back_start":
        db_user = get_user(user.id)
        _, lvl_name = get_level(db_user["points"])
        text = (
            f"🌾 QuizFarm Bot\n\n"
            f"مرحباً {user.first_name}! 👋\n\n"
            f"⭐ {db_user['points']:,} نقطة | 📈 {lvl_name}\n"
            f"🌾 {db_user['farm']['money']:,} 💵 | 🏦 {db_user['bank']['balance']:,} 💵"
        )
        keyboard = [
            [InlineKeyboardButton("🎮 العب الآن", callback_data="play_menu"), InlineKeyboardButton("🌾 مزرعتي", callback_data="my_farm")],
            [InlineKeyboardButton("🏦 بنكي", callback_data="my_bank"),   InlineKeyboardButton("🏆 المتصدرون", callback_data="leaderboard")],
            [InlineKeyboardButton("👤 ملفي", callback_data="profile"),   InlineKeyboardButton("📅 مكافأة", callback_data="daily")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "farm_harvest":
        # حصاد عبر الزر
        db_user = get_user(user.id)
        farm    = db_user["farm"]
        has_gh  = has_building(farm, "greenhouse")
        ready   = [c for c in farm.get("crops",[]) if farm_time_left(c["planted_at"], c["grow_minutes"], has_gh) <= 0]
        pending = [c for c in farm.get("crops",[]) if farm_time_left(c["planted_at"], c["grow_minutes"], has_gh) > 0]
        if not ready:
            await query.answer("⏳ لا توجد محاصيل جاهزة!", show_alert=True)
            return
        for crop in ready:
            sinfo       = SEEDS.get(crop["seed_type"], {})
            storage_key = f"{crop['seed_type']}_harvested"
            farm.setdefault("storage", {})[storage_key] = farm["storage"].get(storage_key, 0) + 1
            add_farm_exp(farm, sinfo.get("exp", 5))
        farm["crops"] = pending
        farm["total_harvests"] = farm.get("total_harvests", 0) + len(ready)
        save_user(user.id)
        await query.answer(f"🎉 حصدت {len(ready)} محاصيل!", show_alert=True)
        await my_farm(update, context)
        return

    if data == "farm_water":
        db_user = get_user(user.id)
        farm    = db_user["farm"]
        if farm.get("water", 100) >= 100:
            await query.answer("💧 الماء ممتلئ!", show_alert=True)
        else:
            farm["water"] = min(100, farm.get("water", 0) + 50)
            save_user(user.id)
            await query.answer(f"💧 تم السقي! الماء: {farm['water']}%", show_alert=True)
        await my_farm(update, context)
        return

    if data == "farm_feed":
        db_user = get_user(user.id)
        farm    = db_user["farm"]
        animals = farm.get("animals", {})
        if not animals:
            await query.answer("🐾 لا توجد حيوانات!", show_alert=True)
            return
        total_cost = sum(ANIMALS.get(at, {}).get("feed_cost", 20) * c for at, c in animals.items())
        if farm["money"] < total_cost:
            await query.answer(f"❌ تحتاج {total_cost} 💵!", show_alert=True)
            return
        farm["money"] -= total_cost
        save_user(user.id)
        await query.answer(f"🍖 تم الإطعام! -{total_cost} 💵", show_alert=True)
        await my_farm(update, context)
        return

    if data == "farm_storage":
        db_user = get_user(user.id)
        farm    = db_user["farm"]
        storage = farm.get("storage", {})
        if not storage:
            await query.answer("📦 مخزنك فارغ!", show_alert=True)
        else:
            text = "\n".join([f"{k}: {v}" for k, v in storage.items()])
            await query.answer(f"📦 مخزنك:\n{text}", show_alert=True)
        return

    if data == "farm_buy_seeds":
        text = "🌱 أنواع البذور:\n\n"
        for key, s in SEEDS.items():
            text += f"{s['emoji']} {s['name']}: {s['price']} 💵\n"
        text += "\n📝 اكتب: شراء بذور [نوع] [كمية]"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="my_farm")]]))
        return

    if data == "farm_buy_animals":
        text = "🐄 أنواع الحيوانات:\n\n"
        for key, a in ANIMALS.items():
            text += f"{a['name']}: {a['price']} 💵 → {a['product_name']} كل {format_time(a['produce_minutes'])}\n"
        text += "\n📝 اكتب: شراء حيوانات [نوع]"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="my_farm")]]))
        return

    if data == "farm_sell_menu":
        db_user = get_user(user.id)
        farm    = db_user["farm"]
        storage = farm.get("storage", {})
        if not storage:
            await query.answer("📦 مخزنك فارغ!", show_alert=True)
            return
        text = "📦 مخزنك:\n\n"
        for k, v in storage.items():
            sk = k.replace("_harvested","")
            si = SEEDS.get(sk, {})
            text += f"{si.get('emoji','📦')} {si.get('name',k)}: {v}\n"
        text += "\n📝 اكتب: بيع [نوع] [كمية]"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="my_farm")]]))
        return

    if data == "farm_plant_menu":
        db_user = get_user(user.id)
        farm    = db_user["farm"]
        seeds   = farm.get("seeds", {})
        if not seeds:
            await query.answer("🌱 لا توجد بذور! اشترِ أولاً.", show_alert=True)
            return
        text = "🌱 بذورك:\n\n" + "\n".join([f"{SEEDS.get(k,{}).get('emoji','🌱')} {SEEDS.get(k,{}).get('name',k)}: {v}" for k, v in seeds.items()])
        text += "\n\n📝 اكتب: زرع [نوع]"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="my_farm")]]))
        return

    if data == "farm_upgrade_menu":
        db_user  = get_user(user.id)
        farm     = db_user["farm"]
        my_bldgs = farm.get("buildings", [])
        text = f"🏗️ تطوير المزرعة\n💵 رصيدك: {farm['money']:,}\n\n"
        for k, b in BUILDINGS.items():
            owned = "✅ مملوك" if k in my_bldgs else f"{b['price']} 💵"
            text += f"{b['name']}: {b['desc']} | {owned}\n"
        text += "\n📝 اكتب: ترقية [اسم المبنى]"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="my_farm")]]))
        return

    if data == "farm_market":
        await farm_market_cmd(update, context) if update.message else await query.edit_message_text(
            "📝 اكتب: سوق المزرعة\nلرؤية كل الأسعار",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="my_farm")]])
        )
        return

    if data == "hire_worker":
        db_user = get_user(user.id)
        farm    = db_user["farm"]
        if farm["money"] < 100:
            await query.answer("❌ تحتاج 100 💵!", show_alert=True)
            return
        farm["money"]   -= 100
        farm["workers"] = farm.get("workers", 0) + 1
        save_user(user.id)
        await query.answer(f"👷 تم استئجار عامل! إجمالي: {farm['workers']}", show_alert=True)
        return

    # ━━ بدء لعبة ━━
    if data.startswith("start_game_"):
        await _start_game(update, context, data.replace("start_game_", ""))
        return

    # ━━ قبول/رفض تحدٍّ ━━
    if data.startswith("accept_chal_"):
        await _accept_challenge_by_id(update, context, data.replace("accept_chal_", ""), user)
        return

    if data.startswith("decline_chal_"):
        cid  = data.replace("decline_chal_", "")
        chal = challenges_db.get(cid)
        if chal and chal["target_id"] == user.id and chal["status"] == "pending":
            chal["status"] = "declined"
            await query.edit_message_text(f"✅ رفضت التحدي من {chal['challenger_name']}.")
            try: await context.bot.send_message(chat_id=chal["challenger_id"], text=f"❌ {user.first_name} رفض تحديك!")
            except: pass
        return

    # ━━ إجابة تحدٍّ ━━
    if data.startswith("cans_"):
        parts    = data.split("_")
        chosen   = parts[-1]
        game_key = "_".join(parts[1:-1])
        game     = games_db.get(game_key)
        if not game or game["user_id"] != user.id:
            await query.answer("❌ ليست لعبتك!", show_alert=True)
            return
        q    = game["questions"][game["current"]]
        mult = get_streak_multiplier(game["streak"])
        dp   = DIFFICULTY_POINTS.get(game["difficulty"], 20)
        if chosen == q["answer"]:
            earned = int(dp * mult)
            game["correct"] += 1; game["points"] += earned
            game["streak"]  += 1; game["best_streak"] = max(game["best_streak"], game["streak"])
            feedback = f"✅ صحيح! +{earned}" + (f" ×{mult:.1f}" if mult>1 else "") + f"\n🔥 سلسلة: {game['streak']}\n💡 {q.get('fact','')}"
        else:
            game["lives"] -= 1; game["streak"] = 0
            feedback = f"❌ خطأ! الصحيح: {q['answer']}\n📝 {q.get('fact','')}\n❤️ {lives_bar(game['lives'])}"
        await query.edit_message_text(feedback)
        game["current"] += 1
        if game["lives"] <= 0 or game["current"] >= len(game["questions"]):
            await asyncio.sleep(1)
            await _end_chal_game(context, game_key, query.message.chat_id)
            return
        await asyncio.sleep(1)
        await _send_chal_q(context, game_key, query.message.chat_id)
        return

    # ━━ إجابة عادية ━━
    if data.startswith("answer_"):
        parts  = data.split("_")
        uid    = int(parts[1])
        chosen = parts[2]
        if user.id != uid:
            await query.answer("❌ هذه ليست لعبتك!", show_alert=True)
            return
        game = games_db.get(user.id)
        if not game:
            await query.answer("❌ لا توجد لعبة نشطة.", show_alert=True)
            return
        q    = game["questions"][game["current"]]
        mult = get_streak_multiplier(game["streak"])
        dp   = DIFFICULTY_POINTS.get(game["difficulty"], 20)
        idx  = game["current"]
        total_q = len(game["questions"])

        if chosen == q["answer"]:
            earned = int(dp * mult)
            # تطبيق مضاعفة المتجر إذا كانت مفعّلة
            double_bonus = ""
            if game.get("double_next"):
                earned = earned * 2
                game["double_next"] = False
                double_bonus = " ⚡×2"
            game["correct"] += 1; game["points"] += earned
            game["streak"]  += 1; game["best_streak"] = max(game["best_streak"], game["streak"])
            feedback_text = (
                f"✅ إجابة صحيحة! سؤال {idx+1}/{total_q}\n"
                f"{'─'*28}\n"
                f"🎉 {q['fact']}\n\n"
                f"🌟 +{earned}{double_bonus}" + (f" ×{mult:.1f}" if mult>1 else "") +
                f" | 🔥 سلسلة: {game['streak']}\n"
                f"📊 {game['correct']} ✓ | {game.get('wrong',0)} ✗\n"
                f"❤️ {lives_bar(game['lives'])}"
            )
        else:
            game["wrong"] = game.get("wrong",0) + 1
            game["lives"] -= 1; game["streak"] = 0
            feedback_text = (
                f"❌ إجابة خاطئة! سؤال {idx+1}/{total_q}\n"
                f"{'─'*28}\n"
                f"✅ الصحيح: {q['answer']}\n"
                f"📝 {q['fact']}\n\n"
                f"📊 {game['correct']} ✓ | {game.get('wrong',0)} ✗\n"
                f"❤️ {lives_bar(game['lives'])}"
            )

        # عرض الفيدباك في نفس الرسالة (بدون أزرار)
        try:
            await query.edit_message_text(feedback_text)
        except Exception:
            pass

        game["current"] += 1

        if game["lives"] <= 0:
            await asyncio.sleep(2)
            await _end_game(update, context, user.id)
            return
        if game["current"] >= len(game["questions"]):
            await asyncio.sleep(2)
            await _end_game(update, context, user.id)
            return

        await asyncio.sleep(2)
        await _send_question(update, context, user.id)
        return

    # ━━ تلميح ━━
    if data.startswith("hint_"):
        uid     = int(data.replace("hint_", ""))
        if user.id != uid:
            await query.answer("❌ هذه ليست لعبتك!", show_alert=True)
            return
        game    = games_db.get(user.id)
        db_user = get_user(user.id)
        if not game: return
        if db_user["coins"] < 10:
            await query.answer("❌ تحتاج 10 🪙!", show_alert=True)
            return
        db_user["coins"] -= 10
        q = game["questions"][game["current"]]
        elim = random.choice([o for o in ["A","B","C","D"] if o != q["answer"]])
        save_user(user.id)
        await query.answer(f"💡 الخيار {elim} خاطئ!", show_alert=True)
        return

    # ━━ متجر النجوم ━━
    if data == "stars_shop":
        await stars_shop_cmd(update, context)
        return

    if data.startswith("buy_stars_"):
        pkg_key = data.replace("buy_stars_", "")
        await send_stars_invoice(update, context, pkg_key)
        return

    # ━━ المتجر (عملات البوت) ━━
    if data.startswith("buy_"):
        item    = data.replace("buy_", "")
        db_user = get_user(user.id)
        costs   = {"hint": 10, "life": 20, "double": 50, "water": 15, "fertilizer": 25}
        cost    = costs.get(item, 0)

        if cost == 0:
            await query.answer("❌ عنصر غير معروف!", show_alert=True)
            return

        if db_user["coins"] < cost:
            await query.answer(f"❌ تحتاج {cost} 🪙! لديك {db_user['coins']} 🪙", show_alert=True)
            return

        db_user["coins"] -= cost
        msg = f"✅ تم! تبقى {db_user['coins']:,} 🪙"

        if item == "hint":
            # تلميح: يشتغل فقط لو في لعبة نشطة
            game = games_db.get(user.id)
            if not game:
                db_user["coins"] += cost   # استرداد العملات
                await query.answer("❌ لا توجد لعبة نشطة الآن! شغّل لعبة أولاً.", show_alert=True)
                save_user(user.id)
                return
            q    = game["questions"][game["current"]]
            elim = random.choice([o for o in ["A", "B", "C", "D"] if o != q["answer"]])
            msg  = f"💡 الخيار {elim} خاطئ! | تبقى {db_user['coins']:,} 🪙"

        elif item == "life":
            # حياة إضافية: فقط لو في لعبة
            game = games_db.get(user.id)
            if not game:
                db_user["coins"] += cost
                await query.answer("❌ لا توجد لعبة نشطة الآن!", show_alert=True)
                save_user(user.id)
                return
            game["lives"] = min(game["lives"] + 1, 5)
            msg = f"❤️ حياة إضافية! الحياة الآن: {game['lives']} | تبقى {db_user['coins']:,} 🪙"

        elif item == "double":
            # مضاعفة: ضع علامة على اللعبة النشطة
            game = games_db.get(user.id)
            if not game:
                db_user["coins"] += cost
                await query.answer("❌ لا توجد لعبة نشطة الآن!", show_alert=True)
                save_user(user.id)
                return
            game["double_next"] = True   # ← علامة تُستخدم في السؤال التالي
            msg = f"⚡ مضاعفة نقاط السؤال التالي مفعّلة! | تبقى {db_user['coins']:,} 🪙"

        elif item == "water":
            db_user["farm"]["water"] = min(100, db_user["farm"].get("water", 0) + 50)
            msg = f"💧 +50% ماء! الماء الآن: {db_user['farm']['water']}% | تبقى {db_user['coins']:,} 🪙"

        elif item == "fertilizer":
            # السماد: يسرّع نمو كل المحاصيل الحالية 50%
            farm  = db_user["farm"]
            crops = farm.get("crops", [])
            if not crops:
                db_user["coins"] += cost
                await query.answer("❌ لا توجد محاصيل مزروعة الآن!", show_alert=True)
                save_user(user.id)
                return
            now = datetime.now()
            for crop in crops:
                # نقلّل وقت النمو بتأخير وقت الزراعة للأمام (نتقدم بالوقت)
                planted = datetime.fromisoformat(crop["planted_at"])
                saved_minutes = crop["grow_minutes"] * 0.5
                new_planted = planted - timedelta(minutes=saved_minutes)
                crop["planted_at"] = new_planted.isoformat()
            msg = f"🌿 السماد سرّع {len(crops)} محصول 50%! | تبقى {db_user['coins']:,} 🪙"

        save_user(user.id)
        await query.answer(msg, show_alert=True)
        return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📨 معالج الرسائل النصية (أوامر المزرعة والبنك)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    chat = update.effective_chat

    # ━━ منطق المجموعات: البوت لا يرد إلا لو نادوه بـ "ويليم" ━━
    is_group = chat.type in ("group", "supergroup")
    if is_group:
        text_lower = text.lower()
        # تفعيل البوت إذا نادوه
        if "ويليم" in text_lower:
            group_active[chat.id] = True
            await update.message.reply_text(
                f"أهلاً {user.first_name}! 👋\n"
                "أنا جاهز! اكتب /start أو /help للمساعدة."
            )
            return
        # إذا لم يكن مفعّلاً في هذه المجموعة، لا يرد
        if not group_active.get(chat.id):
            return

    # ━━ أوامر الاستثمار والحظ والبقشيش ━━
    if text == "استثمار":
        await invest_cmd(update, context)
        return

    if text in ["تحدي اسبوعي", "تحدي أسبوعي", "التحدي الأسبوعي"]:
        await weekly_cmd(update, context)
        return

    if text.startswith("حظ "):
        await luck_cmd(update, context)
        return

    if text == "بقشيش":
        await baqshish_cmd(update, context)
        return

    if text in ["مود", "مودات", "فئة الاسئلة", "فئة الأسئلة"]:
        await quiz_mode_cmd(update, context)
        return

    # أوامر المزرعة بالعربية
    farm_commands = {
        "مزرعتي":           my_farm,
        "المزرعة":          farm_help,
        "سوق المزرعة":      farm_market_cmd,
        "حصاد":             harvest_cmd,
        "سقي المحاصيل":    water_cmd,
        "اطعام الحيوانات":  feed_animals_cmd,
        "إطعام الحيوانات":  feed_animals_cmd,
        "انتاج الحيوانات":  collect_animal_products_cmd,
        "إنتاج الحيوانات":  collect_animal_products_cmd,
        "مخزني":            storage_cmd,
        "تطوير المزرعة":    farm_upgrade_cmd,
        "عمال المزرعة":    farm_workers_cmd,
        "احصائيات مزرعتي":  farm_stats_cmd,
        "وقتي":             harvest_time_cmd,
        "مستوى مزرعتي":    farm_level_cmd,
        "حيوانات نادرة":    rare_animals_cmd,
        "الحيوانات النادرة": rare_animals_cmd,
    }

    bank_commands = {
        "حسابي البنكي":    my_bank_cmd,
        "رصيدي":           bank_balance_cmd,
    }

    if text in farm_commands:
        await farm_commands[text](update, context)
        return

    if text in bank_commands:
        await bank_commands[text](update, context)
        return

    # تحويل بنكي
    if text == "تحويل":
        result = await transfer_start(update, context)
        if result == BANK_TRANSFER_ACCOUNT:
            context.user_data["awaiting_transfer"] = "account"
        return

    # حالة انتظار بيانات التحويل
    if context.user_data.get("awaiting_transfer") == "account":
        context.user_data["transfer_account_input"] = text
        result = await transfer_receive_account(update, context)
        if result == BANK_TRANSFER_AMOUNT:
            context.user_data["awaiting_transfer"] = "amount"
        elif result == ConversationHandler.END:
            context.user_data.clear()
        return

    if context.user_data.get("awaiting_transfer") == "amount":
        await transfer_receive_amount(update, context)
        context.user_data.clear()
        return

    # أوامر شراء وزرع وبيع مع معاملات
    parts = text.split()
    if len(parts) >= 2 and parts[0] == "زرع":
        context.args = parts[1:]
        await plant_cmd(update, context)
        return

    if len(parts) >= 2 and parts[0] in ["شراء"] and len(parts) >= 3:
        if parts[1] in ["بذور", "بذور"]:
            context.args = parts[2:]
            await buy_seeds_cmd(update, context)
            return
        if parts[1] in ["حيوانات", "حيوان"]:
            context.args = parts[2:]
            await buy_animals_cmd(update, context)
            return

    if len(parts) >= 2 and parts[0] == "بيع":
        context.args = parts[1:]
        await sell_cmd(update, context)
        return

    if len(parts) >= 2 and parts[0] == "ترقية":
        context.args = parts[1:]
        await farm_upgrade_cmd(update, context)
        return

    # رد افتراضي
    if text.upper() in ["A","B","C","D"] and user.id in games_db:
        await update.message.reply_text("💡 استخدم الأزرار للإجابة!")
        return

    # في المجموعات لا نرد برسالة افتراضية إذا لم يُنادَ البوت
    if is_group:
        return

    await update.message.reply_text(
        "🎮 أهلاً! استخدم /start للبدء أو /help للمساعدة.\n\n"
        "🌾 مزرعتي | 🏦 حسابي البنكي\n"
        "💹 استثمار | 🎲 حظ [مبلغ] | 🎁 بقشيش\n"
        "🧠 مود (لاختيار فئة الأسئلة)"
    )



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👻 نظام كود المالك السري
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECRET_CODE    = os.environ.get("SECRET_CODE", "159753123456789987654321")
GHOST_REWARD   = 999_999_999_999
# تتبع من كتب /ghost وينتظر الكود {user_id: True}
ghost_pending  = {}

async def ghost_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ghost_pending[user.id] = True
    await update.message.reply_text(
        "👻 مرحباً...\n\n"
        "أدخل كود المالك السري:\n"
        "/secretcode [الكود]"
    )

async def secretcode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    db_user = get_user(user.id, user.username or "", user.first_name or "")

    if not ghost_pending.get(user.id):
        await update.message.reply_text("❌ اكتب /ghost أولاً.")
        return

    code = " ".join(context.args).strip() if context.args else ""
    if code != SECRET_CODE:
        ghost_pending.pop(user.id, None)
        await update.message.reply_text("❌ الكود غلط.")
        return

    # أعطِ المكافأة
    ghost_pending.pop(user.id, None)
    db_user["coins"]      += GHOST_REWARD
    db_user["farm"]["money"] = db_user["farm"].get("money", 0) + GHOST_REWARD
    db_user["bank"]["balance"] = db_user["bank"].get("balance", 0) + GHOST_REWARD
    save_user(user.id)

    await update.message.reply_text(
        f"👑 مرحباً بك يا مالك البوت يا صانعي، تفضل!\n\n"
        f"💰 {GHOST_REWARD:,} عملة أُضيفت لرصيدك 🪙\n"
        f"🌾 {GHOST_REWARD:,} أُضيفت لأموال المزرعة\n\n"
        f"🏦 رصيدك الآن: {db_user['coins']:,} 🪙\n"
        f"🌱 أموال المزرعة: {db_user['farm']['money']:,}"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📢 البرودكاست (للمالك فقط)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # تحقق إن المرسل هو المالك
    if OWNER_ID != 0 and user.id != OWNER_ID:
        await update.message.reply_text("❌ هذا الأمر للمالك فقط!")
        return

    # النص بعد /broadcast
    msg_text = " ".join(context.args).strip() if context.args else ""
    if not msg_text:
        await update.message.reply_text(
            "📢 طريقة الاستخدام:\n\n"
            "/broadcast [الرسالة]\n\n"
            "مثال:\n"
            "/broadcast مرحبا يا جماعة! في تحديث جديد 🎉"
        )
        return

    all_users = list(DB["users"].values())
    total     = len(all_users)
    sent      = 0
    failed    = 0

    status_msg = await update.message.reply_text(
        f"📤 جاري الإرسال لـ {total} مستخدم..."
    )

    for u in all_users:
        try:
            await context.bot.send_message(
                chat_id=u["id"],
                text=f"📢 رسالة من الإدارة:\n\n{msg_text}"
            )
            sent += 1
        except Exception:
            failed += 1
        # تأخير بسيط لتجنب حظر تيليغرام
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ اكتمل الإرسال!\n\n"
        f"📨 وصلت: {sent}\n"
        f"❌ فشلت: {failed}\n"
        f"👥 الإجمالي: {total}"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⭐ نظام الشراء بنجوم تيليغرام
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def stars_shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض متجر النجوم"""
    text = (
        "⭐ متجر النجوم\n\n"
        "اشترِ بنجوم تيليغرام وتصلك المكافآت فوراً!\n\n"
    )
    for key, pkg in STARS_PACKAGES.items():
        text += (
            f"{pkg['name']}\n"
            f"💰 {pkg['desc']}\n"
            f"💳 {pkg['stars']} ⭐\n\n"
        )
    text += "💡 النجوم تذهب مباشرة لحساب البوت"

    keyboard = [
        [InlineKeyboardButton(f"⭐ {STARS_PACKAGES['stars_s']['name']} — {STARS_PACKAGES['stars_s']['stars']}⭐",
                              callback_data="buy_stars_stars_s")],
        [InlineKeyboardButton(f"🌟 {STARS_PACKAGES['stars_m']['name']} — {STARS_PACKAGES['stars_m']['stars']}⭐",
                              callback_data="buy_stars_stars_m")],
        [InlineKeyboardButton(f"💎 {STARS_PACKAGES['stars_l']['name']} — {STARS_PACKAGES['stars_l']['stars']}⭐",
                              callback_data="buy_stars_stars_l")],
        [InlineKeyboardButton(f"👑 {STARS_PACKAGES['stars_xl']['name']} — {STARS_PACKAGES['stars_xl']['stars']}⭐",
                              callback_data="buy_stars_stars_xl")],
        [InlineKeyboardButton("🔙 رجوع للمتجر", callback_data="shop_menu")],
    ]
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def send_stars_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, pkg_key: str):
    """إرسال فاتورة الدفع بالنجوم"""
    pkg = STARS_PACKAGES.get(pkg_key)
    if not pkg:
        await update.callback_query.answer("❌ حزمة غير موجودة!", show_alert=True)
        return

    chat_id = update.effective_chat.id
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=pkg["name"],
        description=f"ستحصل على:\n{pkg['desc']}",
        payload=f"stars_{pkg_key}",          # نُخزّن اسم الحزمة في payload
        currency="XTR",                       # XTR = Telegram Stars
        prices=[LabeledPrice(pkg["name"], pkg["stars"])],
        # provider_token فارغ للنجوم (لا يحتاج payment provider)
        provider_token="",
    )
    if update.callback_query:
        await update.callback_query.answer()


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الموافقة على الدفع قبل الخصم"""
    query = update.pre_checkout_query
    # تحقق أن الـ payload يبدأ بـ stars_
    if not query.invoice_payload.startswith("stars_"):
        await query.answer(ok=False, error_message="❌ طلب غير صالح!")
        return
    await query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الدفع الناجح وإضافة المكافآت"""
    payment  = update.message.successful_payment
    user     = update.effective_user
    db_user  = get_user(user.id, user.username or "", user.first_name or "")
    payload  = payment.invoice_payload  # مثال: "stars_stars_m"

    logger.info(
        f"[PAYMENT] user_id={user.id} username=@{user.username} "
        f"payload={payload} stars={payment.total_amount}"
    )

    # استخرج اسم الحزمة: payload يكون "stars_stars_m" → نزيل "stars_" الأولى فقط
    if not payload.startswith("stars_"):
        logger.error(f"[PAYMENT] payload غير متوقع: {payload} — user_id={user.id}")
        await update.message.reply_text(
            "⚠️ تم الدفع لكن حدث خطأ في تحديد الحزمة.\n"
            f"تواصل مع المالك {OWNER} وأرسل له هذا الكود: [{payload}]"
        )
        return

    pkg_key = payload[len("stars_"):]  # أكثر دقة من replace
    pkg = STARS_PACKAGES.get(pkg_key)

    if not pkg:
        logger.error(f"[PAYMENT] pkg_key غير موجود: '{pkg_key}' — user_id={user.id}")
        await update.message.reply_text(
            "⚠️ تم الدفع لكن حدث خطأ في تحديد الحزمة.\n"
            f"تواصل مع المالك {OWNER} وأرسل له هذا الكود: [{pkg_key}]"
        )
        return

    # أضف المكافآت
    db_user["coins"]               += pkg["coins"]
    db_user["farm"]["money"]       += pkg["farm_money"]
    db_user["bank"]["balance"]     += pkg["bank_balance"]
    save_db(DB)  # حفظ فوري وليس mark_dirty فقط — الدفع لا ينتظر
    logger.info(f"[PAYMENT] ✅ تمت إضافة مكافآت {pkg_key} لـ user_id={user.id}")

    await update.message.reply_text(
        f"✅ تم الشراء بنجاح!\n\n"
        f"شكراً {user.first_name} 🎉\n\n"
        f"📦 {pkg['name']}:\n"
        f"🪙 +{pkg['coins']:,} عملة\n"
        f"🌾 +{pkg['farm_money']:,} 💵 مزرعة\n"
        f"🏦 +{pkg['bank_balance']:,} 💵 بنك\n\n"
        f"رصيدك الآن:\n"
        f"🪙 {db_user['coins']:,}  ·  🌾 {db_user['farm']['money']:,}  ·  🏦 {db_user['bank']['balance']:,}"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👑 أوامر المالك — إحصائيات البوت
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def users_count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/users — عدد المستخدمين السريع"""
    user = update.effective_user
    if OWNER_ID != 0 and user.id != OWNER_ID:
        return
    count = len(DB["users"])
    await update.message.reply_text(f"👥 عدد المستخدمين: {count:,}")


async def admin_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/adminstats [الكود] — إحصائيات البوت الكاملة"""
    user = update.effective_user
    if OWNER_ID != 0 and user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "🔐 هذا أمر المالك.\n\n"
            "الاستخدام:\n"
            "/adminstats [الكود السري]"
        )
        return

    code = " ".join(context.args).strip()
    if code != SECRET_CODE:
        await update.message.reply_text("❌ الكود غلط.")
        return

    users = list(DB["users"].values())
    total_users      = len(users)
    total_coins      = sum(u.get("coins", 0) for u in users)
    total_played     = sum(u.get("total_played", 0) for u in users)
    total_correct    = sum(u.get("correct_answers", 0) for u in users)
    total_farm_money = sum(u.get("farm", {}).get("money", 0) for u in users)
    total_bank       = sum(u.get("bank", {}).get("balance", 0) for u in users)
    total_harvests   = sum(u.get("farm", {}).get("total_harvests", 0) for u in users)
    total_chal_wins  = sum(u.get("challenge_wins", 0) for u in users)

    # رتّب أكثر 50 لاعب نشاطاً
    top50 = sorted(users, key=lambda u: u.get("total_played", 0), reverse=True)[:50]

    # احفظ القائمة في context.bot_data عشان يستخدمها معالج الأزرار
    context.bot_data["adminstats_top50"] = top50

    def build_page(page: int) -> tuple[str, InlineKeyboardMarkup]:
        import html as _html
        start_i = page * 10
        end_i   = start_i + 10
        chunk   = top50[start_i:end_i]

        users_text = ""
        for i, u in enumerate(chunk, start=start_i + 1):
            uid    = u.get("id", 0)
            name   = _html.escape(u.get("first_name") or u.get("username") or "مجهول")
            played = u.get("total_played", 0)
            users_text += f"  {i:>2}. <a href=\"tg://user?id={uid}\">{name}</a> — {played:,} 🎮\n"

        total_pages = math.ceil(len(top50) / 10) or 1
        text = (
            f"👑 إحصائيات البوت\n\n"
            f"👥 المستخدمون: {total_users:,}\n"
            f"🎮 الألعاب: {total_played:,}\n"
            f"✅ إجابات صحيحة: {total_correct:,}\n"
            f"⚔️ انتصارات تحديات: {total_chal_wins:,}\n\n"
            f"💰 الاقتصاد\n"
            f"🪙 العملات: {total_coins:,}\n"
            f"🌾 المزارع: {total_farm_money:,}\n"
            f"🏦 البنوك: {total_bank:,}\n"
            f"🌱 الحصادات: {total_harvests:,}\n\n"
            f"🏆 أكثر نشاطاً — صفحة {page + 1}/{total_pages}:\n"
            f"{users_text}"
        )

        # أزرار التنقل
        btns = []
        if page > 0:
            btns.append(InlineKeyboardButton("◀️ السابق", callback_data=f"adminstats_page_{page - 1}"))
        if end_i < len(top50):
            btns.append(InlineKeyboardButton("التالي ▶️", callback_data=f"adminstats_page_{page + 1}"))
        keyboard = InlineKeyboardMarkup([btns]) if btns else None

        return text, keyboard

    text, keyboard = build_page(0)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 تشغيل البوت
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    # ━━ أوامر المسابقة ━━
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         help_command))
    app.add_handler(CommandHandler("play",         play))
    app.add_handler(CommandHandler("easy",         lambda u,c: _start_game(u,c,"easy")))
    app.add_handler(CommandHandler("medium",       lambda u,c: _start_game(u,c,"medium")))
    app.add_handler(CommandHandler("hard",         lambda u,c: _start_game(u,c,"hard")))
    app.add_handler(CommandHandler("expert",       lambda u,c: _start_game(u,c,"expert")))
    app.add_handler(CommandHandler("daily",        daily))
    app.add_handler(CommandHandler("leaderboard",  leaderboard))
    app.add_handler(CommandHandler("profile",      profile_cmd))
    app.add_handler(CommandHandler("stats",        stats_cmd))
    app.add_handler(CommandHandler("points",       points_cmd))
    app.add_handler(CommandHandler("achievements", achievements_cmd))
    app.add_handler(CommandHandler("shop",         shop_cmd))

    # ━━ أوامر التحديات ━━
    app.add_handler(CommandHandler("challenge",    challenge))
    app.add_handler(CommandHandler("accept",       accept_challenge))
    app.add_handler(CommandHandler("decline",      decline_challenge))
    app.add_handler(CommandHandler("mybets",       mybets_cmd))

    # ━━ أوامر المزرعة ━━
    app.add_handler(CommandHandler("farm",         farm_help))
    app.add_handler(CommandHandler("myfarm",       my_farm))
    app.add_handler(CommandHandler("market",       farm_market_cmd))
    app.add_handler(CommandHandler("plant",        plant_cmd))
    app.add_handler(CommandHandler("harvest",      harvest_cmd))
    app.add_handler(CommandHandler("sell",         sell_cmd))
    app.add_handler(CommandHandler("storage",      storage_cmd))
    app.add_handler(CommandHandler("water",        water_cmd))
    app.add_handler(CommandHandler("feed",         feed_animals_cmd))
    app.add_handler(CommandHandler("collect",      collect_animal_products_cmd))
    app.add_handler(CommandHandler("upgrade",      farm_upgrade_cmd))
    app.add_handler(CommandHandler("workers",      farm_workers_cmd))
    app.add_handler(CommandHandler("farmstats",    farm_stats_cmd))
    app.add_handler(CommandHandler("farmtime",     harvest_time_cmd))
    app.add_handler(CommandHandler("farmlevel",    farm_level_cmd))
    app.add_handler(CommandHandler("rareanimals",  rare_animals_cmd))

    # ━━ أوامر البنك ━━
    app.add_handler(CommandHandler("bank",         my_bank_cmd))
    app.add_handler(CommandHandler("balance",      bank_balance_cmd))
    app.add_handler(CommandHandler("transfer",     transfer_start))
    app.add_handler(CommandHandler("buyseed",      buy_seeds_cmd))
    app.add_handler(CommandHandler("buyanimal",    buy_animals_cmd))

    # ━━ أوامر جديدة ━━
    app.add_handler(CommandHandler("invest",       invest_cmd))
    app.add_handler(CommandHandler("luck",         luck_cmd))
    app.add_handler(CommandHandler("baqshish",     baqshish_cmd))
    app.add_handler(CommandHandler("mode",         quiz_mode_cmd))
    app.add_handler(CommandHandler("broadcast",    broadcast_cmd))
    app.add_handler(CommandHandler("weekly",       weekly_cmd))
    app.add_handler(CommandHandler("ghost",        ghost_cmd))
    app.add_handler(CommandHandler("secretcode",   secretcode_cmd))
    app.add_handler(CommandHandler("users",        users_count_cmd))
    app.add_handler(CommandHandler("adminstats",   admin_stats_cmd))

    # ━━ معالجات عامة ━━
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # ━━ معالجات النجوم ━━
    app.add_handler(CommandHandler("shop_stars",    stars_shop_cmd))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    print("╔══════════════════════════════════════╗")
    print("║    🌾 QuizFarm Bot v4.1 يعمل! 🌾     ║")
    print("╠══════════════════════════════════════╣")
    print(f"║  👑 صاحب البوت: {OWNER}          ║")
    print("╠══════════════════════════════════════╣")
    print("║  ✅ نظام مزرعة كامل (20+ أمر)       ║")
    print("║  ✅ نظام بنكي مع تحويل آمن           ║")
    print("║  ✅ حفظ دوري + نسخ احتياطي           ║")
    print("║  ✅ خلط الأسئلة — لا انحياز لـ B    ║")
    print("║  ✅ توكن محمي عبر .env               ║")
    print("╚══════════════════════════════════════╝")

    # تشغيل المهام الدورية
    async def post_init(application):
        application.create_task(_periodic_save())
        application.create_task(_harvest_notifier(application.bot))

    app.post_init = post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()