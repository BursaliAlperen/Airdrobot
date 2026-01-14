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
✅ Render uyumlu - ÇALIŞIYOR
"""

import os
import sys
import json
import logging
import time
import random
from datetime import datetime, timedelta
from threading import Thread

# Telegram bot kütüphaneleri
try:
    from telegram import Update, ChatPermissions
    from telegram.ext import (
        Updater,
        CommandHandler,
        MessageHandler,
        Filters,
        CallbackContext,
        JobQueue
    )
    from telegram.parsemode import ParseMode
    print("✅ Telegram kütüphanesi yüklendi")
except ImportError as e:
    print(f"❌ Telegram kütüphanesi hatası: {e}")
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
muted_groups = {}          # {chat_id: expires_at}
user_messages = {}         # {user_id: [timestamp1, timestamp2, ...]}
last_warnings = {}         # {chat_id: last_warning_time}

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
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Veri kaydedildi: {len(muted_groups)} kapalı grup")
    except Exception as e:
        logger.error(f"❌ Kaydetme hatası: {e}")

def load_data():
    """Verileri yükle"""
    global muted_groups
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
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
def mute_all_users(bot, chat_id, reason="Spam bot"):
    """Grubu kapat"""
    try:
        bot.set_chat_permissions(
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
        muted_groups[chat_id] = expires_at
        save_data()
        
        logger.info(f"🔒 Grup kapatıldı: {chat_id} - Sebep: {reason}")
        
        return expires_at
        
    except Exception as e:
        logger.error(f"❌ Grup kapatma hatası: {e}")
        return None

def unmute_all_users(bot, chat_id):
    """Grubu aç"""
    try:
        bot.set_chat_permissions(
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
        logger.error(f"❌ Grup açma hatası: {e}")
        return False

def auto_unmute_job(context):
    """6 saat sonra otomatik aç"""
    try:
        chat_id = context.job.context
        bot = context.bot
        
        if chat_id in muted_groups:
            success = unmute_all_users(bot, chat_id)
            if success:
                bot.send_message(
                    chat_id=chat_id,
                    text="✅ *GRUP OTOMATİK AÇILDI!*\n6 saat doldu.",
                    parse_mode=ParseMode.MARKDOWN
                )
    except Exception as e:
        logger.error(f"❌ Otomatik açma hatası: {e}")

# ==================== 1. SPAM BOT KORUMASI ====================
def handle_spam_bots(update, context):
    """Spam bot tespit et"""
    bot = context.bot
    message = update.message
    
    if not message:
        return
    
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat_id
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
    message_text = message.text or message.caption or ""
    spam_keywords = ["reklam", "promotion", "advertise", "ads", "kazan", "para"]
    has_spam = any(keyword in message_text.lower() for keyword in spam_keywords)
    
    if is_spam_bot or has_spam:
        try:
            logger.info(f"🚨 Spam bot: @{username}")
            
            # Grup zaten kapalı mı?
            if chat_id in muted_groups:
                try:
                    bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except:
                    pass
                return
            
            # Mesajı sil
            try:
                bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except:
                pass
            
            # Grubu kapat
            expires_at = mute_all_users(bot, chat_id, f"@{username}")
            
            if expires_at:
                warning = f"""
🚨 *GRUP KAPANDI!*

❌ *Sebep:* @{username} spam botu
⏰ *Süre:* 6 saat
🕒 *Açılma:* {expires_at.strftime('%H:%M')}

📌 Tüm kullanıcılar mesaj YAZAMAZ
👑 Sadece adminler /ac kullanabilir
"""
                
                bot.send_message(
                    chat_id=chat_id,
                    text=warning,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Otomatik açma job'ı
                try:
                    context.job_queue.run_once(
                        auto_unmute_job,
                        MUTE_DURATION,
                        context=chat_id,
                        name=f"unmute_{chat_id}"
                    )
                except Exception as e:
                    logger.error(f"❌ Job planlama hatası: {e}")
            
        except Exception as e:
            logger.error(f"❌ Spam bot hatası: {e}")

# ==================== 2. GRUP KAPALIYKEN KONTROL ====================
def check_group_closed(update, context):
    """Grup kapalıyken mesajları engelle"""
    bot = context.bot
    message = update.message
    
    if not message:
        return
    
    chat_id = message.chat_id
    
    # Grup kapalı mı?
    if chat_id not in muted_groups:
        return
    
    user_id = message.from_user.id
    message_text = message.text or ""
    
    # Bot'un kendisi mi?
    if user_id == bot.id:
        return
    
    # Admin kontrolü
    is_admin = False
    try:
        chat = bot.get_chat(chat_id)
        admins = chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
    except:
        pass
    
    # Adminler sadece /ac komutunu kullanabilir
    if message_text.startswith('/ac') and is_admin:
        return
    
    # Diğer tüm mesajları sil
    try:
        bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        
        # Uyarı gönder (her 5 dakikada bir)
        now = datetime.now()
        if chat_id not in last_warnings or (now - last_warnings.get(chat_id, datetime.min)).total_seconds() > 300:
            warning = "⚠️ *Grup kapalı!* Mesaj yazamazsınız. Adminler /ac kullanabilir."
            bot.send_message(
                chat_id=chat_id,
                text=warning,
                parse_mode=ParseMode.MARKDOWN
            )
            last_warnings[chat_id] = now
            
    except Exception as e:
        logger.error(f"❌ Grup kapalı kontrol hatası: {e}")

# ==================== 3. YENİ ÜYE KARŞILAMA ====================
def welcome_new_members(update, context):
    """Yeni üyeleri karşıla"""
    bot = context.bot
    message = update.message
    
    if not message or not message.new_chat_members:
        return
    
    chat_id = message.chat_id
    
    # Grup kapalıysa karşılama yapma
    if chat_id in muted_groups:
        return
    
    for member in message.new_chat_members:
        # Bot kendisi mi?
        if member.id == bot.id:
            continue
        
        if not member.is_bot:
            welcome_msg = random.choice(WELCOME_MESSAGES)
            
            bot.send_message(
                chat_id=chat_id,
                text=f"🎉 *{welcome_msg}*\n\n👤 {member.first_name}\n\nGrubumuza hoşgeldin! 🚀\n\n📌 Kurallar: /rules",
                parse_mode=ParseMode.MARKDOWN
            )

# ==================== 4. KÜFÜR FİLTRESİ ====================
def filter_bad_words(update, context):
    """Küfür filtresi"""
    bot = context.bot
    message = update.message
    
    if not message or not message.text:
        return
    
    chat_id = message.chat_id
    
    # Grup kapalıysa kontrol yapma
    if chat_id in muted_groups:
        return
    
    user_id = message.from_user.id
    message_text = message.text.lower()
    
    # Bot'un kendisi mi?
    if user_id == bot.id:
        return
    
    # Admin kontrolü
    is_admin = False
    try:
        chat = bot.get_chat(chat_id)
        admins = chat.get_administrators()
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
                bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                warning = f"⚠️ {message.from_user.first_name}, küfür içeren mesajınız silindi!"
                bot.send_message(chat_id=chat_id, text=warning)
                return
            except Exception as e:
                logger.error(f"❌ Küfür filtresi hatası: {e}")
                return

# ==================== 5. FLOOD KORUMASI ====================
def prevent_flood(update, context):
    """Flood koruması"""
    bot = context.bot
    message = update.message
    
    if not message:
        return
    
    chat_id = message.chat_id
    
    # Grup kapalıysa flood kontrolü yapma
    if chat_id in muted_groups:
        return
    
    user_id = message.from_user.id
    
    # Bot'un kendisi mi?
    if user_id == bot.id:
        return
    
    # Admin kontrolü
    is_admin = False
    try:
        chat = bot.get_chat(chat_id)
        admins = chat.get_administrators()
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
            
            bot.restrict_chat_member(
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
            
            warning = f"⚠️ {message.from_user.first_name}, flood yaptığınız için 5 dakika susturuldunuz!"
            bot.send_message(chat_id=chat_id, text=warning)
            
            # Flood mesajını sil
            try:
                bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except:
                pass
            
            # Flood verilerini temizle
            user_messages[user_id] = []
            
        except Exception as e:
            logger.error(f"❌ Flood koruma hatası: {e}")

# ==================== 6. KOMUT SİSTEMİ ====================
def start_command(update, context):
    """Başlangıç komutu"""
    update.message.reply_text(
        "🤖 *InsideAds_bot Koruma Botu*\n\n"
        "🚨 *Özellikler:*\n"
        "• InsideAds_bot mesaj atarsa 6 saat grup kapanır\n"
        "• Tüm kullanıcılar mesaj YAZAMAZ\n"
        "• Sadece adminler /ac komutunu kullanabilir\n"
        "• 6 saat sonra otomatik açılır\n\n"
        "📋 *Komutlar:*\n"
        "/durum - Grup durumu\n"
        "/ac - Grubu aç (admin)\n"
        "/kapat - Test kapatma (admin)\n"
        "/rules - Grup kuralları\n"
        "/stats - İstatistikler\n"
        "/help - Yardım"
    )

def durum_command(update, context):
    """Grup durumu"""
    chat_id = update.message.chat_id
    
    cleanup_expired()
    
    if chat_id in muted_groups:
        expires_at = muted_groups[chat_id]
        time_left = expires_at - datetime.now()
        
        if time_left.total_seconds() > 0:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            
            status = f"""
🔴 *GRUP KAPALI*

⏰ *Kalan Süre:* {hours} saat {minutes} dakika
🕒 *Açılma:* {expires_at.strftime('%H:%M')}
👑 *Admin Komutu:* /ac

📌 Tüm kullanıcılar mesaj yazamaz!
"""
        else:
            status = "🟢 *GRUP AÇIK* (Süre doldu)"
    else:
        status = """
🟢 *GRUP AÇIK*

✅ Normal mesajlaşma
🚨 Spam bot koruması: *AKTİF*
🛡️ Küfür filtresi: *AKTİF*
🌊 Flood koruması: *AKTİF*
👋 Yeni üye karşılama: *AKTİF*

💡 Durum: Her şey normal
"""
    
    update.message.reply_text(status)

def ac_command(update, context):
    """Grubu aç"""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    bot = context.bot
    
    # Admin kontrolü
    try:
        chat = bot.get_chat(chat_id)
        admins = chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            update.message.reply_text("❌ *Bu komutu sadece adminler kullanabilir!*")
            return
    except Exception as e:
        logger.error(f"❌ Admin kontrol hatası: {e}")
        update.message.reply_text("❌ Admin kontrolü yapılamadı!")
        return
    
    cleanup_expired()
    
    # Grup zaten açık mı?
    if chat_id not in muted_groups:
        update.message.reply_text("ℹ️ *Grup zaten açık!*")
        return
    
    # Grubu aç
    success = unmute_all_users(bot, chat_id)
    
    if success:
        update.message.reply_text("✅ *Grup başarıyla açıldı!*\nArtık herkes mesaj yazabilir.")
    else:
        update.message.reply_text("❌ Grup açılamadı!")

def kapat_command(update, context):
    """Test için kapat"""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    bot = context.bot
    
    # Admin kontrolü
    try:
        chat = bot.get_chat(chat_id)
        admins = chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            update.message.reply_text("❌ *Bu komutu sadece adminler kullanabilir!*")
            return
    except Exception as e:
        logger.error(f"❌ Admin kontrol hatası: {e}")
        update.message.reply_text("❌ Admin kontrolü yapılamadı!")
        return
    
    cleanup_expired()
    
    # Grup zaten kapalı mı?
    if chat_id in muted_groups:
        update.message.reply_text("⚠️ *Grup zaten kapalı!*")
        return
    
    # Test için kapat
    expires_at = mute_all_users(bot, chat_id, "Test (admin komutu)")
    
    if expires_at:
        update.message.reply_text(
            f"🔒 *Grup test için kapatıldı!*\n\n"
            f"⏰ *Açılma:* {expires_at.strftime('%H:%M')}\n"
            f"📌 Tüm kullanıcılar mesaj yazamaz!\n"
            f"👑 Sadece adminler /ac komutunu kullanabilir"
        )

def rules_command(update, context):
    """Grup kuralları"""
    rules = """
📜 *GRUP KURALLARI*

1️⃣ *SPAM BOT YASAK!*
   - InsideAds_bot ve benzerleri
   - Ekleyen: DAİMİ BAN
   - Tespit edilirse: 6 saat grup kapanır

2️⃣ *KÜFÜR YASAK!*
   - Yasaklı kelimeler otomatik silinir

3️⃣ *FLOOD YASAK!*
   - Arka arkaya mesaj atma
   - 5 saniyede 5'ten fazla mesaj: 5 dk susturma

4️⃣ *REKLAM YASAK!*
   - İzinsiz reklam yasak

5️⃣ *GRUP KAPALIYKEN*
   - Sadece adminler /ac komutunu kullanabilir
   - Diğer mesajlar otomatik silinir
"""
    update.message.reply_text(rules)

def stats_command(update, context):
    """İstatistikler"""
    cleanup_expired()
    
    stats = f"""
📊 *İSTATİSTİKLER*

• Kapalı Gruplar: {len(muted_groups)}
• Yasaklı Kelimeler: {len(BANNED_WORDS)}
• Spam Botlar: {len(SPAM_BOTS)}
• Kapatma Süresi: 6 saat
• Flood Limiti: {FLOOD_LIMIT} mesaj / {FLOOD_WINDOW} saniye

🔄 Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}
"""
    update.message.reply_text(stats)

def help_command(update, context):
    """Yardım komutu"""
    start_command(update, context)

# ==================== 7. TEMİZLEME JOB'I ====================
def cleanup_job(context):
    """Düzenli temizleme job'ı"""
    cleanup_expired()

# ==================== 8. HATA YÖNETİMİ ====================
def error_handler(update, context):
    """Hata yönetimi"""
    try:
        logger.error(f"Bot hatası: {context.error}")
    except:
        pass

# ==================== 9. BOT BAŞLATMA ====================
def main():
    """Bot'u başlat"""
    # Verileri yükle
    load_data()
    cleanup_expired()
    
    print("=" * 60)
    print("🤖 TELEGRAM BOT BAŞLATILIYOR")
    print("=" * 60)
    print(f"🔐 Token: {BOT_TOKEN[:10]}...")
    print(f"🎯 Hedef Bot: InsideAds_bot")
    print(f"🎯 Diğer Spam Botlar: {len(SPAM_BOTS)} adet")
    print("⏰ Kapatma Süresi: 6 SAAT")
    print("👤 Etkilenen: TÜM kullanıcılar")
    print("👑 Admin Komutu: /ac")
    print("🚫 Yasaklı Kelimeler: Aktif")
    print("🌊 Flood Koruması: Aktif")
    print("👋 Yeni Üye Karşılama: Aktif")
    print("=" * 60)
    
    try:
        # Updater oluştur (ESKİ VERSİYON - ÇALIŞIYOR)
        updater = Updater(token=BOT_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        job_queue = updater.job_queue
        
        print("✅ Updater oluşturuldu")
        
        # Hata handler
        dispatcher.add_error_handler(error_handler)
        
        # Komutlar
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("durum", durum_command))
        dispatcher.add_handler(CommandHandler("ac", ac_command))
        dispatcher.add_handler(CommandHandler("kapat", kapat_command))
        dispatcher.add_handler(CommandHandler("rules", rules_command))
        dispatcher.add_handler(CommandHandler("stats", stats_command))
        dispatcher.add_handler(CommandHandler("help", help_command))
        print("✅ Komutlar eklendi")
        
        # Handler'lar
        # 1. Spam botlar
        dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command,
            handle_spam_bots
        ))
        
        # 2. Grup kapalı kontrol
        dispatcher.add_handler(MessageHandler(
            Filters.all & ~Filters.command,
            check_group_closed
        ))
        
        # 3. Yeni üye karşılama
        dispatcher.add_handler(MessageHandler(
            Filters.status_update.new_chat_members,
            welcome_new_members
        ))
        
        # 4. Küfür filtresi
        dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command,
            filter_bad_words
        ))
        
        # 5. Flood koruması
        dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command,
            prevent_flood
        ))
        print("✅ Handler'lar eklendi")
        
        # Temizleme job'ı (her saat)
        job_queue.run_repeating(cleanup_job, interval=3600, first=10)
        
        print("✅ Job'lar eklendi")
        print("✅ Bot başlatılıyor...")
        print("=" * 60)
        
        # Bot'u başlat
        updater.start_polling()
        print("🤖 Bot çalışıyor...")
        
        # Bot'u çalışır durumda tut
        updater.idle()
        
    except Exception as e:
        logger.error(f"❌ Bot başlatma hatası: {e}")
        print(f"❌ HATA: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
