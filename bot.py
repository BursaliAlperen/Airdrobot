#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 TELEGRAM BOT - SPAM BOT KORUMASI
✅ InsideAds_bot mesaj atınca 6 saat grup kapanır
✅ Tüm kullanıcılar mesaj yazamaz
✅ Sadece adminler /ac komutunu kullanabilir
✅ 6 saat sonra otomatik açılır
✅ Render uyumlu - Python 3.13 ile çalışır
"""

import os
import sys
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

# Telegram bot kütüphaneleri
try:
    from telegram import Update, ChatPermissions, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        CallbackContext
    )
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    print(f"❌ Telegram kütüphanesi yüklenemedi: {e}")
    TELEGRAM_AVAILABLE = False
    sys.exit(1)

# ==================== AYARLAR ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# BOT TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN", "8122690327:AAHTN0X87h7q81xj9rThs0vaqGrcra_Nf28")

# SPAM BOTLAR
SPAM_BOTS = [
    "InsideAds_bot",
    "PromotionBot",
    "advertise_bot",
    "ads_bot",
    "spam_bot",
    "reklam_bot"
]

# KAPALI KALMA SÜRESİ (6 SAAT)
MUTE_DURATION = 6 * 60 * 60  # 6 saat

# VERİ DOSYASI
DATA_FILE = "bot_data.json"

# GLOBAL VERİ
muted_groups: Dict[int, datetime] = {}

# ==================== VERİ YÖNETİMİ ====================
def save_data():
    """Verileri kaydet"""
    try:
        data = {
            'muted_groups': {
                str(chat_id): expires_at.isoformat()
                for chat_id, expires_at in muted_groups.items()
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
                    int(k): datetime.fromisoformat(v)
                    for k, v in data.get('muted_groups', {}).items()
                }
            logger.info(f"📂 {len(muted_groups)} kapalı grup yüklendi")
    except Exception as e:
        logger.error(f"❌ Yükleme hatası: {e}")
        muted_groups = {}

def cleanup_expired_groups():
    """Süresi dolmuş grupları temizle"""
    now = datetime.now()
    expired = [chat_id for chat_id, expires_at in list(muted_groups.items()) 
               if expires_at < now]
    for chat_id in expired:
        del muted_groups[chat_id]
    if expired:
        save_data()
        logger.info(f"♻️ {len(expired)} grup temizlendi")

# ==================== TEMEL FONKSİYONLAR ====================
async def close_group(chat_id: int, context: CallbackContext, reason: str = "Spam bot"):
    """Grubu kapat"""
    try:
        logger.info(f"🔒 Grup kapatılıyor: {chat_id} - Sebep: {reason}")
        
        # Grubu kapat
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
        
        # Süreyi kaydet
        expires_at = datetime.now() + timedelta(seconds=MUTE_DURATION)
        muted_groups[chat_id] = expires_at
        save_data()
        
        # Uyarı mesajı
        warning = f"""
🚨 **GRUP KAPANDI!**

❌ **Sebep:** {reason}
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
        
        # Otomatik açma için job planla
        try:
            context.job_queue.run_once(
                auto_open_group,
                MUTE_DURATION,
                data=chat_id,
                name=f"unmute_{chat_id}"
            )
        except Exception as e:
            logger.error(f"Job planlama hatası: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Grup kapatma hatası: {e}")
        return False

async def open_group(chat_id: int, context: CallbackContext):
    """Grubu aç"""
    try:
        logger.info(f"🔓 Grup açılıyor: {chat_id}")
        
        # Grubu aç
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
        
        # Veriden kaldır
        if chat_id in muted_groups:
            del muted_groups[chat_id]
            save_data()
        
        # Başarı mesajı
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ **GRUP AÇILDI!**\nArtık herkes mesaj yazabilir.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Planlanmış job'ı temizle
        try:
            jobs = context.job_queue.get_jobs_by_name(f"unmute_{chat_id}")
            for job in jobs:
                job.schedule_removal()
        except:
            pass
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Grup açma hatası: {e}")
        return False

async def auto_open_group(context: CallbackContext):
    """Otomatik grup açma"""
    try:
        chat_id = context.job.data
        logger.info(f"⏰ Otomatik açma: {chat_id}")
        
        if chat_id in muted_groups:
            await open_group(chat_id, context)
    except Exception as e:
        logger.error(f"❌ Otomatik açma hatası: {e}")

# ==================== SPAM BOT KORUMASI ====================
async def handle_spam_bot(update: Update, context: CallbackContext):
    """Spam bot tespit et"""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if not user:
        return
    
    username = user.username or ""
    
    # Spam bot kontrolü
    is_spam_bot = any(spam_bot.lower() in username.lower() for spam_bot in SPAM_BOTS)
    
    # Mesaj içeriği kontrolü
    message_text = update.message.text or update.message.caption or ""
    spam_keywords = ["reklam", "promotion", "advertise", "ads", "kazan", "para"]
    has_spam = any(keyword in message_text.lower() for keyword in spam_keywords)
    
    if is_spam_bot or has_spam:
        try:
            logger.info(f"🚨 Spam bot tespit edildi: @{username} - Grup: {chat_id}")
            
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
                logger.info(f"🗑️ Mesaj silindi: @{username}")
            except:
                pass
            
            # Grubu kapat
            await close_group(chat_id, context, f"@{username}")
            
        except Exception as e:
            logger.error(f"❌ Spam bot işleme hatası: {e}")

# ==================== GRUP KAPALIYKEN MESAJ KONTROLÜ ====================
async def check_group_closed(update: Update, context: CallbackContext):
    """Grup kapalıyken mesajları engelle"""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    
    # Grup kapalı mı?
    if chat_id not in muted_groups:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text or ""
    
    # Bot'un kendisi mi?
    if user_id == context.bot.id:
        return
    
    # Admin mi kontrol et
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
    except:
        pass

# ==================== KOMUTLAR ====================
async def start(update: Update, context: CallbackContext):
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

async def durum(update: Update, context: CallbackContext):
    """Grup durumu"""
    chat_id = update.effective_chat.id
    
    cleanup_expired_groups()  # Süresi dolanları temizle
    
    if chat_id in muted_groups:
        expires_at = muted_groups[chat_id]
        time_left = expires_at - datetime.now()
        
        if time_left.total_seconds() > 0:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            
            status = f"""
🔴 **GRUP KAPALI**

⏰ **Kalan Süre:** {hours} saat {minutes} dakika
🕒 **Açılma:** {expires_at.strftime('%H:%M')}
👑 **Admin Komutu:** /ac

📌 Tüm kullanıcılar mesaj yazamaz!
"""
        else:
            status = "🟢 **GRUP AÇIK** (Süre doldu ama açılmadı)"
    else:
        status = """
🟢 **GRUP AÇIK**

✅ Normal mesajlaşma
🚨 Spam bot koruması: **AKTİF**
👑 Admin komutu: /ac

💡 Durum: Her şey normal
"""
    
    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

async def ac(update: Update, context: CallbackContext):
    """Grubu aç"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Admin kontrolü
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Bu komutu sadece adminler kullanabilir!")
            return
    except Exception as e:
        logger.error(f"❌ Admin kontrol hatası: {e}")
        await update.message.reply_text("❌ Admin kontrolü yapılamadı!")
        return
    
    # Grup zaten açık mı?
    cleanup_expired_groups()
    if chat_id not in muted_groups:
        await update.message.reply_text("ℹ️ Grup zaten açık!")
        return
    
    # Grubu aç
    success = await open_group(chat_id, context)
    
    if not success:
        await update.message.reply_text("❌ Grup açılamadı!")

async def kapat(update: Update, context: CallbackContext):
    """Test için grubu kapat"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Admin kontrolü
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Bu komutu sadece adminler kullanabilir!")
            return
    except Exception as e:
        logger.error(f"❌ Admin kontrol hatası: {e}")
        await update.message.reply_text("❌ Admin kontrolü yapılamadı!")
        return
    
    # Grup zaten kapalı mı?
    cleanup_expired_groups()
    if chat_id in muted_groups:
        await update.message.reply_text("⚠️ Grup zaten kapalı!")
        return
    
    # Test için kapat
    success = await close_group(chat_id, context, "Test (admin komutu)")
    
    if not success:
        await update.message.reply_text("❌ Grup kapatılamadı!")

async def rules(update: Update, context: CallbackContext):
    """Grup kuralları"""
    rules_text = """
📜 **GRUP KURALLARI**

1️⃣ **SPAM BOT YASAK!**
   - InsideAds_bot ve benzerleri
   - Ekleyen: DAİMİ BAN
   - Tespit edilirse: 6 saat grup kapanır

2️⃣ **GRUP KAPALIYKEN**
   - Sadece adminler /ac komutunu kullanabilir
   - Diğer mesajlar otomatik silinir

3️⃣ **REKLAM YASAK!**
   - İzinsiz reklam yasak

4️⃣ **KÜFÜR YASAK!**
   - Küfür içeren mesajlar silinir
"""
    await update.message.reply_text(rules_text)

async def help_command(update: Update, context: CallbackContext):
    """Yardım komutu"""
    await start(update, context)

# ==================== HATA YÖNETİMİ ====================
async def error_handler(update: Update, context: CallbackContext):
    """Hataları yönet"""
    try:
        logger.error(f"Bot hatası: {context.error}")
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin."
                )
            except:
                pass
    except:
        pass

# ==================== ANA FONKSİYON ====================
def main():
    """Bot'u başlat"""
    if not TELEGRAM_AVAILABLE:
        print("❌ Telegram kütüphanesi yüklenemedi!")
        sys.exit(1)
    
    # Verileri yükle
    load_data()
    cleanup_expired_groups()
    
    print("=" * 60)
    print("🤖 TELEGRAM BOT BAŞLATILIYOR")
    print("=" * 60)
    print(f"🔐 Token: {BOT_TOKEN[:10]}...")
    print(f"🎯 Spam Botlar: {len(SPAM_BOTS)} adet")
    print("⏰ Kapatma Süresi: 6 SAAT")
    print("👤 Etkilenen: TÜM kullanıcılar")
    print("👑 Admin Komutu: /ac")
    print("=" * 60)
    
    try:
        # Application oluştur - SIMPLE MODE
        app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
        
        print("✅ Application oluşturuldu")
        
        # Hata handler'ı ekle
        app.add_error_handler(error_handler)
        
        # Komutlar
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("durum", durum))
        app.add_handler(CommandHandler("ac", ac))
        app.add_handler(CommandHandler("kapat", kapat))
        app.add_handler(CommandHandler("rules", rules))
        app.add_handler(CommandHandler("help", help_command))
        
        # Mesaj handler'ları
        # Spam bot kontrolü
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_spam_bot
        ))
        
        # Grup kapalıyken kontrol
        app.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND,
            check_group_closed
        ))
        
        print("✅ Handlers eklendi")
        print("✅ Bot başlatılıyor...")
        print("=" * 60)
        
        # Bot'u başlat - BASİT MOD
        app.run_polling(
            poll_interval=1.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"❌ Bot başlatma hatası: {e}")
        print(f"❌ HATA: {e}")
        
        # Alternatif başlatma yöntemi
        print("🔄 Alternatif başlatma deneniyor...")
        try:
            from telegram.ext import Updater
            updater = Updater(BOT_TOKEN, use_context=True)
            
            # Handlers'ları ekle
            dp = updater.dispatcher
            
            dp.add_handler(CommandHandler("start", start))
            dp.add_handler(CommandHandler("durum", durum))
            dp.add_handler(CommandHandler("ac", ac))
            dp.add_handler(CommandHandler("kapat", kapat))
            dp.add_handler(CommandHandler("rules", rules))
            
            dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_spam_bot))
            dp.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, check_group_closed))
            
            updater.start_polling()
            print("✅ Bot alternatif yöntemle başlatıldı!")
            updater.idle()
            
        except Exception as e2:
            print(f"❌ Alternatif başlatma da başarısız: {e2}")
            sys.exit(1)

if __name__ == '__main__':
    main()
