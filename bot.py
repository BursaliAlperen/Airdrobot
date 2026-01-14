# Python 3.13 imghdr fix
try:
    import imghdr
except ImportError:
    # imghdr_fix.py'yi çalıştır
    import imghdr_fix
    import sys
    sys.modules['imghdr'] = imghdr_fix
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 TELEGRAM BOT - TÜM ÖZELLİKLER
✅ InsideAds_bot mesaj atınca 6 saat grup kapanır
✅ Tüm kullanıcılar mesaj yazamaz
✅ Sadece adminler /ac komutunu kullanabilir
✅ 6 saat sonra otomatik açılır
✅ Yeni üye karşılama (GRUP İÇİ)
✅ Küfür filtresi (GRUP İÇİ)
✅ Flood koruması (GRUP İÇİ)
✅ Tüm komutlar çalışır
✅ Render uyumlu - Python 3.13
"""

import os
import sys
import json
import logging
import time
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

# Python 3.13 için imghdr workaround
try:
    import imghdr
except ImportError:
    # Python 3.13'te imghdr kaldırıldı, alternatif
    import mimetypes
    imghdr = None

# Telegram bot kütüphaneleri
try:
    from telegram import Update, ChatPermissions
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
    print(f"❌ Telegram kütüphanesi hatası: {e}")
    print("ℹ️ Kütüphaneler yükleniyor...")
    TELEGRAM_AVAILABLE = False

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

# YASAKLI KELİMELER
BANNED_WORDS = [
    "amk", "aq", "sg", "siktir", "orosbu", "piç", "küfür",
    "mal", "salak", "aptal", "gerizekalı", "ibne", "göt"
]

# FLOOD KORUMA
FLOOD_LIMIT = 5      # 5 mesaj
FLOOD_WINDOW = 5     # 5 saniye

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
muted_groups: Dict[int, datetime] = {}  # Kapalı gruplar
user_messages: Dict[int, List[datetime]] = {}  # Flood kontrol
group_warnings: Dict[int, datetime] = {}  # Son uyarı zamanları

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
            json.dump(data, f, indent=2)
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

def cleanup_expired():
    """Süresi dolmuş grupları temizle"""
    now = datetime.now()
    expired = []
    
    for chat_id, expires_at in list(muted_groups.items()):
        if expires_at < now:
            expired.append(chat_id)
    
    for chat_id in expired:
        del muted_groups[chat_id]
    
    if expired:
        save_data()
        logger.info(f"♻️ {len(expired)} grup temizlendi")

# ==================== TEMEL FONKSİYONLAR ====================
async def mute_all_users(chat_id: int, context: CallbackContext, reason: str = "Spam bot"):
    """Grubu kapat"""
    try:
        # Grubun izinlerini değiştir
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
        
        logger.info(f"🔒 Grup kapatıldı: {chat_id} - Sebep: {reason}")
        
        # Otomatik açma job'ı
        try:
            context.job_queue.run_once(
                auto_unmute_job,
                MUTE_DURATION,
                data=chat_id,
                name=f"unmute_{chat_id}"
            )
        except Exception as e:
            logger.error(f"❌ Job planlama hatası: {e}")
        
        return expires_at
        
    except Exception as e:
        logger.error(f"❌ Grup kapatma hatası: {e}")
        return None

async def unmute_all_users(chat_id: int, context: CallbackContext):
    """Grubu aç"""
    try:
        # Normal izinlere geri dön
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
        
        # Job'ları temizle
        try:
            jobs = context.job_queue.get_jobs_by_name(f"unmute_{chat_id}")
            for job in jobs:
                job.schedule_removal()
        except:
            pass
        
        logger.info(f"🔓 Grup açıldı: {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Grup açma hatası: {e}")
        return False

async def auto_unmute_job(context: CallbackContext):
    """6 saat sonra otomatik aç"""
    try:
        chat_id = context.job.data
        
        if chat_id in muted_groups:
            success = await unmute_all_users(chat_id, context)
            if success:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ **GRUP OTOMATİK AÇILDI!**\n6 saat doldu.",
                    parse_mode=ParseMode.MARKDOWN
                )
    except Exception as e:
        logger.error(f"❌ Otomatik açma hatası: {e}")

# ==================== 1. SPAM BOT KORUMASI ====================
async def handle_spam_bots(update: Update, context: CallbackContext):
    """Spam bot tespit et"""
    if not update.message:
        return
    
    user = update.effective_user
    if not user:
        return
    
    chat_id = update.effective_chat.id
    username = user.username or ""
    
    # Spam bot kontrolü
    is_spam_bot = False
    
    # InsideAds_bot kontrolü
    if "insideads" in username.lower() or username == "InsideAds_bot":
        is_spam_bot = True
    else:
        # Diğer spam botlar
        for spam_bot in SPAM_BOTS:
            if spam_bot.lower() in username.lower():
                is_spam_bot = True
                break
    
    # Mesaj içeriği kontrolü
    message_text = update.message.text or update.message.caption or ""
    spam_keywords = ["reklam", "promotion", "advertise", "ads", "kazan", "para"]
    has_spam = any(keyword in message_text.lower() for keyword in spam_keywords)
    
    if is_spam_bot or has_spam:
        try:
            logger.info(f"🚨 Spam bot: @{username}")
            
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
            
        except Exception as e:
            logger.error(f"❌ Spam bot hatası: {e}")

# ==================== 2. GRUP KAPALIYKEN KONTROL ====================
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
        
        # Uyarı gönder (her 5 dakikada bir)
        now = datetime.now()
        if chat_id not in group_warnings or (now - group_warnings[chat_id]).total_seconds() > 300:
            warning = "⚠️ **Grup kapalı!** Mesaj yazamazsınız. Adminler /ac kullanabilir."
            await context.bot.send_message(
                chat_id=chat_id,
                text=warning,
                parse_mode=ParseMode.MARKDOWN
            )
            group_warnings[chat_id] = now
            
    except Exception as e:
        logger.error(f"❌ Grup kapalı kontrol hatası: {e}")

# ==================== 3. YENİ ÜYE KARŞILAMA ====================
async def welcome_new_members(update: Update, context: CallbackContext):
    """Yeni üyeleri karşıla"""
    try:
        if not update.message or not update.message.new_chat_members:
            return
        
        chat_id = update.effective_chat.id
        
        # Grup kapalıysa karşılama yapma
        if chat_id in muted_groups:
            return
        
        for member in update.message.new_chat_members:
            # Bot kendisi mi?
            if member.id == context.bot.id:
                continue
            
            if not member.is_bot:
                welcome_msg = random.choice(WELCOME_MESSAGES)
                
                message = f"""
🎉 **{welcome_msg}**

👤 **Kullanıcı:** {member.mention_html()}

Grubumuza hoşgeldin! 🚀

📌 Kurallar: /rules
❓ Yardım: /help
"""
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
                
    except Exception as e:
        logger.error(f"❌ Karşılama hatası: {e}")

# ==================== 4. KÜFÜR FİLTRESİ ====================
async def filter_bad_words(update: Update, context: CallbackContext):
    """Küfür filtresi"""
    if not update.message or not update.message.text:
        return
    
    chat_id = update.effective_chat.id
    
    # Grup kapalıysa kontrol yapma
    if chat_id in muted_groups:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text.lower()
    
    # Bot'un kendisi mi?
    if user_id == context.bot.id:
        return
    
    # Admin kontrolü
    is_admin = False
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
    except:
        pass
    
    # Adminler için filtre yok
    if is_admin:
        return
    
    # Yasaklı kelime kontrolü
    for word in BANNED_WORDS:
        if word in message_text:
            try:
                await update.message.delete()
                warning = f"⚠️ {update.effective_user.mention_html()}, küfür içeren mesajınız silindi!"
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=warning,
                    parse_mode=ParseMode.HTML
                )
                return
            except Exception as e:
                logger.error(f"❌ Küfür filtresi hatası: {e}")
                return

# ==================== 5. FLOOD KORUMASI ====================
async def prevent_flood(update: Update, context: CallbackContext):
    """Flood koruması"""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    
    # Grup kapalıysa flood kontrolü yapma
    if chat_id in muted_groups:
        return
    
    user_id = update.effective_user.id
    
    # Bot'un kendisi mi?
    if user_id == context.bot.id:
        return
    
    # Admin kontrolü
    is_admin = False
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
    except:
        pass
    
    # Adminler için flood kontrolü yok
    if is_admin:
        return
    
    now = datetime.now()
    
    # Flood verilerini temizle
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    # Eski kayıtları temizle
    user_messages[user_id] = [
        timestamp for timestamp in user_messages[user_id]
        if (now - timestamp).total_seconds() < FLOOD_WINDOW
    ]
    
    # Yeni mesajı ekle
    user_messages[user_id].append(now)
    
    # Flood kontrolü
    if len(user_messages[user_id]) > FLOOD_LIMIT:
        try:
            # Kullanıcıyı 5 dakika sustur
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
            await context.bot.send_message(
                chat_id=chat_id,
                text=warning,
                parse_mode=ParseMode.HTML
            )
            
            # Flood mesajını sil
            try:
                await update.message.delete()
            except:
                pass
            
            # Flood verilerini temizle
            user_messages[user_id] = []
            
        except Exception as e:
            logger.error(f"❌ Flood koruma hatası: {e}")

# ==================== 6. KOMUT SİSTEMİ ====================
async def start_command(update: Update, context: CallbackContext):
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

async def durum_command(update: Update, context: CallbackContext):
    """Grup durumu"""
    chat_id = update.effective_chat.id
    
    cleanup_expired()
    
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
"""
        else:
            status = "🟢 **GRUP AÇIK** (Süre doldu)"
    else:
        status = """
🟢 **GRUP AÇIK**

✅ Normal mesajlaşma
🚨 Spam bot koruması: **AKTİF**
🛡️ Küfür filtresi: **AKTİF**
🌊 Flood koruması: **AKTİF**
👋 Yeni üye karşılama: **AKTİF**
"""
    
    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

async def ac_command(update: Update, context: CallbackContext):
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
    
    cleanup_expired()
    
    if chat_id not in muted_groups:
        await update.message.reply_text("ℹ️ Grup zaten açık!")
        return
    
    success = await unmute_all_users(chat_id, context)
    
    if success:
        await update.message.reply_text("✅ **Grup başarıyla açıldı!**")
    else:
        await update.message.reply_text("❌ Grup açılamadı!")

async def kapat_command(update: Update, context: CallbackContext):
    """Test için kapat"""
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
    
    cleanup_expired()
    
    if chat_id in muted_groups:
        await update.message.reply_text("⚠️ Grup zaten kapalı!")
        return
    
    expires_at = await mute_all_users(chat_id, context, "Test (admin komutu)")
    
    if expires_at:
        await update.message.reply_text(
            f"🔒 **Grup test için kapatıldı!**\nAçılma: {expires_at.strftime('%H:%M')}",
            parse_mode=ParseMode.MARKDOWN
        )

async def rules_command(update: Update, context: CallbackContext):
    """Grup kuralları"""
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

5️⃣ **GRUP KAPALIYKEN**
   - Sadece adminler /ac komutunu kullanabilir
   - Diğer mesajlar otomatik silinir
"""
    await update.message.reply_text(rules)

async def stats_command(update: Update, context: CallbackContext):
    """İstatistikler"""
    cleanup_expired()
    
    stats = f"""
📊 **İSTATİSTİKLER**

• Kapalı Gruplar: {len(muted_groups)}
• Yasaklı Kelimeler: {len(BANNED_WORDS)}
• Spam Botlar: {len(SPAM_BOTS)}
• Kapatma Süresi: 6 saat
• Flood Limiti: {FLOOD_LIMIT} mesaj / {FLOOD_WINDOW} saniye

🔄 Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}
"""
    await update.message.reply_text(stats)

async def help_command(update: Update, context: CallbackContext):
    """Yardım komutu"""
    await start_command(update, context)

# ==================== 7. HATA YÖNETİMİ ====================
async def error_handler(update: Update, context: CallbackContext):
    """Hata yönetimi"""
    try:
        logger.error(f"Bot hatası: {context.error}")
    except:
        pass

# ==================== 8. TEMİZLEME JOB'I ====================
async def cleanup_job(context: CallbackContext):
    """Düzenli temizleme"""
    cleanup_expired()

# ==================== 9. BOT BAŞLATMA ====================
def main():
    """Bot'u başlat"""
    # Log başlangıcı
    print("=" * 60)
    print("🤖 TELEGRAM BOT BAŞLATILIYOR")
    print("=" * 60)
    
    if not TELEGRAM_AVAILABLE:
        print("❌ Telegram kütüphanesi yüklenemedi!")
        print("ℹ️ Lütfen requirements.txt kontrol edin")
        return
    
    # Verileri yükle
    load_data()
    cleanup_expired()
    
    print(f"🔐 Token: {BOT_TOKEN[:10]}...")
    print(f"🎯 Spam Botlar: {len(SPAM_BOTS)}")
    print("⏰ Kapatma Süresi: 6 SAAT")
    print("👤 Etkilenen: TÜM kullanıcılar")
    print("👑 Admin Komutu: /ac")
    print("=" * 60)
    
    try:
        # Application oluştur
        app = Application.builder().token(BOT_TOKEN).build()
        print("✅ Application oluşturuldu")
        
        # Hata handler
        app.add_error_handler(error_handler)
        
        # Komutlar
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("durum", durum_command))
        app.add_handler(CommandHandler("ac", ac_command))
        app.add_handler(CommandHandler("kapat", kapat_command))
        app.add_handler(CommandHandler("rules", rules_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("help", help_command))
        print("✅ Komutlar eklendi")
        
        # Handler'lar
        # 1. Spam botlar
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_spam_bots
        ))
        
        # 2. Grup kapalı kontrol
        app.add_handler(MessageHandler(
            filters.ALL & ~filters.COMMAND,
            check_group_closed
        ))
        
        # 3. Yeni üye karşılama
        app.add_handler(MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_members
        ))
        
        # 4. Küfür filtresi
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            filter_bad_words
        ))
        
        # 5. Flood koruması
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            prevent_flood
        ))
        print("✅ Handler'lar eklendi")
        
        # Temizleme job'ı
        app.job_queue.run_repeating(cleanup_job, interval=3600, first=10)
        
        print("✅ Bot başlatılıyor...")
        print("=" * 60)
        
        # Bot'u başlat
        app.run_polling(
            poll_interval=1.0,
            timeout=20,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Bot başlatma hatası: {e}")
        print(f"❌ HATA: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
