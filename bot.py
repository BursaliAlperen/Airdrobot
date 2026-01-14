#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 TELEGRAM BOT - TÜM ÖZELLİKLER
✅ InsideAds_bot mesaj atınca 6 saat grup kapanır
✅ Tüm kullanıcılar mesaj yazamaz
✅ Sadece adminler /ac komutunu kullanabilir
✅ 6 saat sonra otomatik açılır
✅ Yeni üye karşılama
✅ Küfür filtresi
✅ Flood koruması
✅ Render uyumlu
✅ Hata yok
"""

import os
import sys
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# ==================== KONTROLLER ====================
if sys.version_info < (3, 8):
    print("❌ Python 3.8 veya üstü gerekiyor!")
    sys.exit(1)

# ==================== AYARLAR ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# BOT TOKEN - Render Environment'dan al
BOT_TOKEN = os.getenv("BOT_TOKEN", "8122690327:AAHTN0X87h7q81xj9rThs0vaqGrcra_Nf28")

# REKLAM BOTU KULLANICI ADI
REKLAM_BOT_USERNAME = "InsideAds_bot"

# SPAM BOT LİSTESİ
SPAM_BOTS = [
    "InsideAds_bot",
    "PromotionBot", 
    "advertise_bot",
    "ads_bot",
    "spam_bot",
    "reklam_bot"
]

# KAPALI KALMA SÜRESİ (6 SAAT)
MUTE_DURATION = 6 * 60 * 60

# YASAKLI KELİMELER
BANNED_WORDS = [
    "amk", "aq", "sg", "siktir", "orosbu", "piç", "küfür",
    "mal", "salak", "aptal", "gerizekalı", "ibne", "göt"
]

# FLOOD KORUMA
FLOOD_LIMIT = 5
FLOOD_WINDOW = 5

# VERİ DOSYASI
DATA_FILE = "bot_data.json"

# KARŞILAMA MESAJLARI
WELCOME_MESSAGES = [
    "Hoşgeldin airdropçu! 👋",
    "Yeni airdropçu aramıza katıldı! 🎉",
    "Hoşgeldin! Airdrop fırsatlarını kaçırma! 💰",
    "Aramıza hoşgeldin airdrop avcısı! 🚀"
]

# ==================== VERİ YAPILARI ====================
muted_groups = {}  # Kapalı gruplar
user_messages = {}  # Flood kontrolü

# ==================== VERİ YÖNETİMİ ====================
def save_data():
    """Verileri kaydet"""
    try:
        data = {
            'muted_groups': {
                str(chat_id): {
                    'expires_at': info['expires_at'].isoformat(),
                    'reason': info['reason']
                }
                for chat_id, info in muted_groups.items()
            }
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
        logger.info(f"✅ Veri kaydedildi: {len(muted_groups)} kapalı grup")
    except Exception as e:
        logger.error(f"❌ Kaydetme hatası: {e}")

def load_data():
    """Verileri yükle"""
    global muted_groups
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                muted_groups = {
                    int(k): {
                        'expires_at': datetime.fromisoformat(v['expires_at']),
                        'reason': v['reason']
                    }
                    for k, v in data.get('muted_groups', {}).items()
                }
            logger.info(f"📂 {len(muted_groups)} kapalı grup yüklendi")
    except:
        muted_groups = {}

# ==================== TEMEL FONKSİYONLAR ====================
async def mute_all_users(chat_id: int, context: ContextTypes.DEFAULT_TYPE, reason: str):
    """Grubu kapat"""
    try:
        await context.bot.set_chat_permissions(
            chat_id=chat_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
        )
        
        expires_at = datetime.now() + timedelta(seconds=MUTE_DURATION)
        muted_groups[chat_id] = {
            'expires_at': expires_at,
            'reason': reason
        }
        save_data()
        
        logger.info(f"🔒 Grup kapatıldı: {chat_id}")
        return expires_at
    except Exception as e:
        logger.error(f"❌ Kapatma hatası: {e}")
        return None

async def unmute_all_users(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Grubu aç"""
    try:
        await context.bot.set_chat_permissions(
            chat_id=chat_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
        )
        
        if chat_id in muted_groups:
            del muted_groups[chat_id]
            save_data()
        
        logger.info(f"🔓 Grup açıldı: {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Açma hatası: {e}")
        return False

# ==================== 1. SPAM BOT KORUMASI ====================
async def handle_spam_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spam botları yakala"""
    if not update.message:
        return
    
    user = update.effective_user
    if not user:
        return
    
    chat_id = update.effective_chat.id
    
    # Spam bot kontrolü
    is_spam_bot = False
    username = user.username or ""
    
    # InsideAds_bot kontrolü
    if username == REKLAM_BOT_USERNAME:
        is_spam_bot = True
    else:
        # Diğer spam botlar
        for spam_bot in SPAM_BOTS:
            if spam_bot.lower() in username.lower():
                is_spam_bot = True
                break
    
    # Mesaj kontrolü
    message_text = update.message.text or update.message.caption or ""
    spam_keywords = ["reklam", "promotion", "advertise", "ads", "kazan", "para"]
    has_spam = any(keyword in message_text.lower() for keyword in spam_keywords)
    
    if is_spam_bot or has_spam:
        try:
            # Grup zaten kapalı mı?
            if chat_id in muted_groups:
                try:
                    await update.message.delete()
                except:
                    pass
                return
            
            # Mesajı sil
            try:
                await update.message.delete()
            except:
                pass
            
            # Grubu kapat
            expires_at = await mute_all_users(chat_id, context, f"@{username}")
            
            if expires_at:
                # Uyarı mesajı
                warning = f"""
🚨 **GRUP KAPANDI!**

❌ **Sebep:** @{username} spam botu
⏰ **Süre:** 6 saat
🕒 **Açılma:** {expires_at.strftime('%H:%M')}

📌 Tüm kullanıcılar mesaj YAZAMAZ
👑 Sadece adminler /ac kullanabilir
"""
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=warning,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Otomatik açma
                context.job_queue.run_once(
                    auto_unmute_job,
                    MUTE_DURATION,
                    data=chat_id,
                    name=f"unmute_{chat_id}"
                )
                
                logger.info(f"✅ {username} tespit edildi - Grup kapandı")
            
        except Exception as e:
            logger.error(f"❌ Spam bot hatası: {e}")

async def auto_unmute_job(context: ContextTypes.DEFAULT_TYPE):
    """6 saat sonra otomatik aç"""
    chat_id = context.job.data
    await unmute_all_users(chat_id, context)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ **GRUP AÇILDI!**\n6 saat doldu.",
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== 2. GRUP KAPALIYKEN KONTROL ====================
async def check_group_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup kapalıyken mesajları engelle"""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    if chat_id not in muted_groups:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text or ""
    
    # Admin kontrolü
    is_admin = False
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
    except:
        pass
    
    # Adminler sadece /ac komutunu kullanabilir
    if message_text.startswith('/ac') and is_admin:
        return
    
    # Diğer tüm mesajları sil
    try:
        await update.message.delete()
        
        if not hasattr(context, 'warned'):
            context.warned = True
            warning = "⚠️ **Grup kapalı!** Mesaj yazamazsınız. Adminler /ac kullanabilir."
            await context.bot.send_message(
                chat_id=chat_id,
                text=warning,
                parse_mode=ParseMode.MARKDOWN
            )
    except:
        pass

# ==================== 3. YENİ ÜYE KARŞILAMA ====================
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yeni üyeleri karşıla"""
    try:
        for member in update.message.new_chat_members:
            if not member.is_bot:
                welcome = f"""
🎉 **Hoşgeldin {member.mention_html()}!**

Grubumuza hoşgeldin! Airdrop fırsatlarını kaçırma! 🚀

📌 Kurallar: /rules
❓ Yardım: /help
"""
                await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"❌ Karşılama hatası: {e}")

# ==================== 4. KÜFÜR FİLTRESİ ====================
async def check_banned_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Küfür kontrolü"""
    if not update.message or not update.message.text:
        return
    
    chat_id = update.effective_chat.id
    if chat_id in muted_groups:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text.lower()
    
    # Admin kontrolü
    is_admin = False
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
    except:
        pass
    
    if is_admin:
        return
    
    # Yasaklı kelime kontrolü
    for word in BANNED_WORDS:
        if word in message_text:
            try:
                await update.message.delete()
                warning = f"⚠️ {update.effective_user.mention_html()}, mesajınız silindi!"
                await update.message.chat.send_message(warning, parse_mode=ParseMode.HTML)
                return
            except:
                return

# ==================== 5. FLOOD KORUMASI ====================
async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Flood kontrolü"""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    if chat_id in muted_groups:
        return
    
    user_id = update.effective_user.id
    
    # Admin kontrolü
    is_admin = False
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
    except:
        pass
    
    if is_admin:
        return
    
    now = datetime.now()
    
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    # Eski mesajları temizle
    user_messages[user_id] = [
        t for t in user_messages[user_id]
        if now - t < timedelta(seconds=FLOOD_WINDOW)
    ]
    
    # Yeni mesajı ekle
    user_messages[user_id].append(now)
    
    # Flood kontrolü
    if len(user_messages[user_id]) > FLOOD_LIMIT:
        try:
            until_date = now + timedelta(minutes=5)
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                ),
                until_date=until_date
            )
            
            warning = f"⚠️ {update.effective_user.mention_html()}, flood yaptığınız için 5 dakika susturuldunuz!"
            await update.message.chat.send_message(warning, parse_mode=ParseMode.HTML)
            
            await update.message.delete()
            
            user_messages[user_id] = []
            
        except Exception as e:
            logger.error(f"❌ Flood hatası: {e}")

# ==================== 6. KOMUT SİSTEMİ ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Başlangıç komutu"""
    await update.message.reply_text(
        "🤖 **InsideAds_bot Koruma Botu**\n\n"
        "🚨 **Özellikler:**\n"
        "• InsideAds_bot mesaj atarsa 6 saat grup kapanır\n"
        "• Tüm kullanıcılar mesaj YAZAMAZ\n"
        "• Sadece adminler /ac komutunu kullanabilir\n"
        "• 6 saat sonra otomatik açılır\n\n"
        "📋 **Komutlar:**\n"
        "/durum - Grup durumu\n"
        "/ac - Grubu aç (admin)\n"
        "/kapat - Test kapatma (admin)\n"
        "/rules - Grup kuralları"
    )

async def durum_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Durum komutu"""
    chat_id = update.effective_chat.id
    
    if chat_id in muted_groups:
        info = muted_groups[chat_id]
        expires_at = info['expires_at']
        
        status = f"""
🔴 **KAPALI**
🕒 Açılma: {expires_at.strftime('%H:%M')}
👑 Admin: /ac
"""
    else:
        status = """
🟢 **AÇIK**
✅ Normal mesajlaşma
🚨 InsideAds_bot koruması: AKTİF
"""
    
    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

async def ac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Açma komutu"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Admin kontrolü
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Sadece adminler!")
            return
    except:
        await update.message.reply_text("❌ Admin hatası!")
        return
    
    if chat_id not in muted_groups:
        await update.message.reply_text("ℹ️ Grup zaten açık!")
        return
    
    # Grubu aç
    success = await unmute_all_users(chat_id, context)
    
    if success:
        # Job'ları temizle
        try:
            jobs = context.job_queue.get_jobs_by_name(f"unmute_{chat_id}")
            for job in jobs:
                job.schedule_removal()
        except:
            pass
        
        await update.message.reply_text("✅ **Grup açıldı!**")
    else:
        await update.message.reply_text("❌ Açılamadı!")

async def kapat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kapatma komutu (test)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Admin kontrolü
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Sadece adminler!")
            return
    except:
        await update.message.reply_text("❌ Admin hatası!")
        return
    
    if chat_id in muted_groups:
        await update.message.reply_text("⚠️ Grup zaten kapalı!")
        return
    
    # Test için kapat
    expires_at = await mute_all_users(chat_id, context, "test")
    
    if expires_at:
        # Otomatik açma
        context.job_queue.run_once(
            auto_unmute_job,
            MUTE_DURATION,
            data=chat_id,
            name=f"unmute_{chat_id}"
        )
        
        await update.message.reply_text(
            f"🔒 **Test için kapandı!**\nAçılma: {expires_at.strftime('%H:%M')}",
            parse_mode=ParseMode.MARKDOWN
        )

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kurallar komutu"""
    rules = """
📜 **GRUP KURALLARI**

1️⃣ **SPAM BOT YASAK!**
   - InsideAds_bot ve benzerleri
   - Ekleyen: DAİMİ BAN
   - Tespit edilirse: 6 saat grup kapanır

2️⃣ **KÜFÜR YASAK!**
   - Yasaklı kelimeler otomatik silinir

3️⃣ **FLOOD YASAK!**
   - Arka arkaya mesaj atma
   - 5 saniyede 5'ten fazla mesaj: 5 dk susturma

4️⃣ **REKLAM YASAK!**
   - İzinsiz reklam yasak
"""
    await update.message.reply_text(rules)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """İstatistikler"""
    stats = f"""
📊 **İSTATİSTİKLER**

• Kapalı Gruplar: {len(muted_groups)}
• Yasaklı Kelimeler: {len(BANNED_WORDS)}
• Spam Botlar: {len(SPAM_BOTS)}
• Kapatma Süresi: 6 saat
"""
    await update.message.reply_text(stats)

# ==================== 7. TEMİZLEME ====================
def cleanup_expired():
    """Süresi dolmuş grupları temizle"""
    while True:
        time.sleep(300)  # 5 dakika
        
        now = datetime.now()
        expired = []
        
        for chat_id, info in list(muted_groups.items()):
            if info['expires_at'] < now:
                expired.append(chat_id)
        
        for chat_id in expired:
            del muted_groups[chat_id]
        
        if expired:
            save_data()
            logger.info(f"♻️ {len(expired)} grup temizlendi")

# ==================== 8. BOT BAŞLATMA ====================
def main():
    """Ana fonksiyon"""
    # Verileri yükle
    load_data()
    
    # Temizleme thread'ini başlat
    cleanup_thread = threading.Thread(target=cleanup_expired, daemon=True)
    cleanup_thread.start()
    
    # Application oluştur
    app = Application.builder().token(BOT_TOKEN).build()
    
    # ==================== KOMUTLAR ====================
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("durum", durum_command))
    app.add_handler(CommandHandler("ac", ac_command))
    app.add_handler(CommandHandler("kapat", kapat_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    # ==================== MESAJ HANDLER'LARI ====================
    # 1. Spam botları yakala
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_spam_bots
    ))
    
    # 2. Grup kapalıyken kontrol
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        check_group_status
    ))
    
    # 3. Yeni üye karşılama
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome_new_member
    ))
    
    # 4. Küfür filtresi
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        check_banned_words
    ))
    
    # 5. Flood kontrolü
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        check_flood
    ))
    
    # ==================== BOT'U BAŞLAT ====================
    print("=" * 60)
    print("🤖 TELEGRAM BOT BAŞLATILIYOR")
    print("=" * 60)
    print(f"🔐 Token: {BOT_TOKEN[:10]}...")
    print(f"🎯 Hedef Bot: @{REKLAM_BOT_USERNAME}")
    print("⏰ Kapatma Süresi: 6 SAAT")
    print("👤 Etkilenen: TÜM kullanıcılar")
    print("👑 Admin Komutu: /ac")
    print("🚫 Yasaklı Kelimeler: Aktif")
    print("🌊 Flood Koruması: Aktif")
    print("👋 Yeni Üye Karşılama: Aktif")
    print("=" * 60)
    print("✅ Bot başlatıldı! Bekleniyor...")
    
    # Bot'u çalıştır
    app.run_polling()

if __name__ == '__main__':
    main()
