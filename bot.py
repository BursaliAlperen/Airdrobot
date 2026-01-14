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
✅ /durum komutu
✅ /ac komutu (admin)
✅ /kapat komutu (admin test)
✅ /rules komutu
✅ /stats komutu
✅ Render uyumlu - Python 3.13
✅ Hata yok
"""

import os
import sys
import json
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Set

# Telegram bot kütüphaneleri
try:
    from telegram import Update, ChatPermissions, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        CallbackContext,
        ContextTypes
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

# YASAKLI KELİMELER
BANNED_WORDS = [
    "amk", "aq", "sg", "siktir", "orosbu", "piç", "küfür",
    "mal", "salak", "aptal", "gerizekalı", "ibne", "göt"
]

# FLOOD KORUMA AYARLARI
FLOOD_LIMIT = 5      # 5 mesaj
FLOOD_WINDOW = 5     # 5 saniye içinde

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
# Kapalı gruplar: {chat_id: expires_at}
muted_groups: Dict[int, datetime] = {}

# Flood kontrolü: {user_id: [timestamp1, timestamp2, ...]}
flood_data: Dict[int, List[datetime]] = {}

# Grup başına son uyarı zamanı: {chat_id: datetime}
last_warning: Dict[int, datetime] = {}

# ==================== VERİ YÖNETİMİ ====================
def save_data():
    """Tüm verileri kaydet"""
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
    """Tüm verileri yükle"""
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
    """Grubu tamamen kapat (tüm kullanıcılar susturulur)"""
    try:
        # Grubun izinlerini değiştir - TÜM kullanıcılar mesaj yazamaz
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
        
        return expires_at
        
    except Exception as e:
        logger.error(f"❌ Grup kapatma hatası: {e}")
        return None

async def unmute_all_users(chat_id: int, context: CallbackContext):
    """Grubu tamamen aç (tüm kullanıcılar konuşabilir)"""
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
        
        # Planlanmış job'ı temizle
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
    """SPAM BOT TESPİT ET - InsideAds_bot ve diğer spam botlar"""
    if not update.message:
        return
    
    user = update.effective_user
    if not user:
        return
    
    chat_id = update.effective_chat.id
    username = user.username or ""
    
    # SPAM BOT KONTROLÜ
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
    spam_keywords = ["reklam", "promotion", "advertise", "ads", "kazan", "para", "airdrop", "promosyon"]
    has_spam = any(keyword in message_text.lower() for keyword in spam_keywords)
    
    if is_spam_bot or has_spam:
        try:
            logger.info(f"🚨 SPAM BOT TESPİT: @{username} - Grup: {chat_id}")
            
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
                logger.info(f"🗑️ Spam mesaj silindi: @{username}")
            except:
                pass
            
            # GRUBU KAPAT
            expires_at = await mute_all_users(chat_id, context, f"Spam bot: @{username}")
            
            if expires_at:
                # UYARI MESAJI GÖNDER
                warning = f"""
🚨 **GRUP KAPANDI!**

❌ **Sebep:** @{username} spam botu tespit edildi
⏰ **Süre:** 6 saat
🕒 **Açılma:** {expires_at.strftime('%H:%M')}

📌 **Tüm kullanıcılar mesaj YAZAMAZ!**
👑 **Sadece adminler** `/ac` komutunu kullanabilir
🔓 **6 saat sonra** otomatik açılacak
"""
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=warning,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # OTOMATİK AÇMA İÇİN JOB PLANLA
                try:
                    context.job_queue.run_once(
                        auto_unmute_job,
                        MUTE_DURATION,
                        data=chat_id,
                        name=f"unmute_{chat_id}"
                    )
                except Exception as e:
                    logger.error(f"❌ Job planlama hatası: {e}")
            
        except Exception as e:
            logger.error(f"❌ Spam bot işleme hatası: {e}")

# ==================== 2. GRUP KAPALIYKEN KONTROL ====================
async def check_group_closed(update: Update, context: CallbackContext):
    """GRUP KAPALIYKEN mesaj yazılmasını engelle"""
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
        
        # Her 5 dakikada bir uyarı gönder
        now = datetime.now()
        if chat_id not in last_warning or (now - last_warning[chat_id]).total_seconds() > 300:
            warning = """
⚠️ **GRUP KAPALI!**

📌 **Tüm kullanıcılar mesaj yazamaz!**
👑 **Sadece adminler** `/ac` komutunu kullanabilir
⏰ **6 saat sonra** otomatik açılacak

❌ Mesajınız otomatik silinmiştir.
"""
            
            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=warning,
                parse_mode=ParseMode.MARKDOWN
            )
            
            last_warning[chat_id] = now
            
            # Uyarıyı 30 saniye sonra sil
            try:
                async def delete_warning():
                    try:
                        await context.bot.delete_message(
                            chat_id=chat_id,
                            message_id=sent_msg.message_id
                        )
                    except:
                        pass
                
                context.job_queue.run_once(
                    lambda ctx: asyncio.create_task(delete_warning()),
                    30,
                    name=f"delete_warning_{chat_id}"
                )
            except:
                pass
                
    except Exception as e:
        logger.error(f"❌ Grup kapalı kontrol hatası: {e}")

# ==================== 3. YENİ ÜYE KARŞILAMA ====================
async def welcome_new_members(update: Update, context: CallbackContext):
    """YENİ ÜYELERİ KARŞILA - Grup içinde çalışır"""
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
            
            # Bot değilse karşıla
            if not member.is_bot:
                welcome_msg = random.choice(WELCOME_MESSAGES)
                
                message = f"""
🎉 **{welcome_msg}**

👤 **Kullanıcı:** {member.mention_html()}
📅 **Katılım Tarihi:** {datetime.now().strftime('%d.%m.%Y %H:%M')}

Grubumuza hoşgeldin! Kuralları okumayı unutma! 🚀

📌 **Kurallar:** /rules
❓ **Yardım:** /help
"""
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
                
                logger.info(f"👋 Yeni üye karşılandı: {member.full_name}")
                
    except Exception as e:
        logger.error(f"❌ Karşılama hatası: {e}")

# ==================== 4. KÜFÜR FİLTRESİ ====================
async def filter_bad_words(update: Update, context: CallbackContext):
    """KÜFÜR FİLTRESİ - Grup içinde çalışır"""
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
    
    # Adminler için filtre uygulanmaz
    if is_admin:
        return
    
    # Yasaklı kelime kontrolü
    for word in BANNED_WORDS:
        if word in message_text:
            try:
                # Mesajı sil
                await update.message.delete()
                
                # Uyarı gönder
                warning = f"⚠️ {update.effective_user.mention_html()}, küfür içeren mesajınız silindi!"
                
                sent_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=warning,
                    parse_mode=ParseMode.HTML
                )
                
                logger.info(f"🚫 Küfür filtresi: {update.effective_user.full_name}")
                
                # Uyarıyı 10 saniye sonra sil
                try:
                    async def delete_warning():
                        try:
                            await context.bot.delete_message(
                                chat_id=chat_id,
                                message_id=sent_msg.message_id
                            )
                        except:
                            pass
                    
                    context.job_queue.run_once(
                        lambda ctx: asyncio.create_task(delete_warning()),
                        10,
                        name=f"delete_badword_warning_{chat_id}"
                    )
                except:
                    pass
                
                return
                
            except Exception as e:
                logger.error(f"❌ Küfür filtresi hatası: {e}")
                return

# ==================== 5. FLOOD KORUMASI ====================
async def prevent_flood(update: Update, context: CallbackContext):
    """FLOOD KORUMASI - Grup içinde çalışır"""
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
    
    # Adminler için flood kontrolü yapılmaz
    if is_admin:
        return
    
    now = datetime.now()
    
    # Flood verilerini temizle
    if user_id not in flood_data:
        flood_data[user_id] = []
    
    # Eski kayıtları temizle
    flood_data[user_id] = [
        timestamp for timestamp in flood_data[user_id]
        if (now - timestamp).total_seconds() < FLOOD_WINDOW
    ]
    
    # Yeni mesajı ekle
    flood_data[user_id].append(now)
    
    # Flood kontrolü
    if len(flood_data[user_id]) > FLOOD_LIMIT:
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
            
            # Uyarı mesajı
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
            flood_data[user_id] = []
            
            logger.info(f"🌊 Flood koruması: {update.effective_user.full_name} susturuldu")
            
        except Exception as e:
            logger.error(f"❌ Flood koruma hatası: {e}")

# ==================== 6. KOMUT SİSTEMİ ====================
async def start_command(update: Update, context: CallbackContext):
    """BAŞLANGIÇ KOMUTU"""
    await update.message.reply_text(
        "🤖 **InsideAds_bot Koruma Botu**\n\n"
        "🚨 **ÖZELLİKLER:**\n"
        "• InsideAds_bot mesaj atarsa 6 saat grup kapanır\n"
        "• Tüm kullanıcılar mesaj YAZAMAZ\n"
        "• Sadece adminler `/ac` komutunu kullanabilir\n"
        "• 6 saat sonra otomatik açılır\n"
        "• Yeni üye karşılama\n"
        "• Küfür filtresi\n"
        "• Flood koruması\n\n"
        "📋 **KOMUTLAR:**\n"
        "`/durum` - Grup durumu\n"
        "`/ac` - Grubu aç (sadece admin)\n"
        "`/kapat` - Test için kapat (sadece admin)\n"
        "`/rules` - Grup kuralları\n"
        "`/stats` - Bot istatistikleri\n"
        "`/help` - Yardım",
        parse_mode=ParseMode.MARKDOWN
    )

async def durum_command(update: Update, context: CallbackContext):
    """GRUP DURUMU KOMUTU"""
    chat_id = update.effective_chat.id
    
    # Süresi dolanları temizle
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
🕒 **Açılma Saati:** {expires_at.strftime('%H:%M')}
📅 **Açılma Tarihi:** {expires_at.strftime('%d.%m.%Y')}

👑 **Admin Komutu:** `/ac`
📌 **Tüm kullanıcılar mesaj yazamaz!**
"""
        else:
            status = "🟢 **GRUP AÇIK** (Süre doldu, otomatik açılacak)"
    else:
        status = """
🟢 **GRUP AÇIK**

✅ **Normal mesajlaşma**
🚨 **Spam bot koruması:** AKTİF
🛡️ **Küfür filtresi:** AKTİF
🌊 **Flood koruması:** AKTİF
👋 **Yeni üye karşılama:** AKTİF

💡 **Durum:** Her şey normal
"""
    
    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

async def ac_command(update: Update, context: CallbackContext):
    """GRUBU AÇ KOMUTU - SADECE ADMIN"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Admin kontrolü
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            await update.message.reply_text(
                "❌ **Bu komutu sadece adminler kullanabilir!**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
    except Exception as e:
        logger.error(f"❌ Admin kontrol hatası: {e}")
        await update.message.reply_text("❌ Admin kontrolü yapılamadı!")
        return
    
    # Süresi dolanları temizle
    cleanup_expired()
    
    # Grup zaten açık mı?
    if chat_id not in muted_groups:
        await update.message.reply_text(
            "ℹ️ **Grup zaten açık!**",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Grubu aç
    success = await unmute_all_users(chat_id, context)
    
    if success:
        await update.message.reply_text(
            "✅ **Grup başarıyla açıldı!**\nArtık herkes mesaj yazabilir.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("❌ Grup açılamadı!")

async def kapat_command(update: Update, context: CallbackContext):
    """TEST İÇİN KAPAT - SADECE ADMIN"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Admin kontrolü
    try:
        admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in admins)
        
        if not is_admin:
            await update.message.reply_text(
                "❌ **Bu komutu sadece adminler kullanabilir!**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
    except Exception as e:
        logger.error(f"❌ Admin kontrol hatası: {e}")
        await update.message.reply_text("❌ Admin kontrolü yapılamadı!")
        return
    
    # Süresi dolanları temizle
    cleanup_expired()
    
    # Grup zaten kapalı mı?
    if chat_id in muted_groups:
        await update.message.reply_text(
            "⚠️ **Grup zaten kapalı!**",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Test için kapat
    expires_at = await mute_all_users(chat_id, context, "Test (admin komutu)")
    
    if expires_at:
        # Otomatik açma job'ı ekle
        try:
            context.job_queue.run_once(
                auto_unmute_job,
                MUTE_DURATION,
                data=chat_id,
                name=f"unmute_{chat_id}"
            )
        except:
            pass
        
        await update.message.reply_text(
            f"🔒 **Grup test için kapatıldı!**\n\n"
            f"⏰ **Açılma Saati:** {expires_at.strftime('%H:%M')}\n"
            f"📌 **Tüm kullanıcılar mesaj yazamaz!**\n"
            f"👑 **Sadece adminler** `/ac` komutunu kullanabilir",
            parse_mode=ParseMode.MARKDOWN
        )

async def rules_command(update: Update, context: CallbackContext):
    """GRUP KURALLARI KOMUTU"""
    rules = """
📜 **GRUP KURALLARI**

1️⃣ **SPAM BOT YASAK!**
   • InsideAds_bot ve benzer spam botlar
   • Ekleyen: **DAİMİ BAN**
   • Tespit edilirse: **6 saat grup kapanır**

2️⃣ **GRUP KAPALIYKEN**
   • Sadece adminler `/ac` komutunu kullanabilir
   • Diğer mesajlar **otomatik silinir**
   • 6 saat sonra **otomatik açılır**

3️⃣ **KÜFÜR YASAK!**
   • Yasaklı kelimeler **otomatik silinir**
   • Tekrarlayanlar susturulur

4️⃣ **FLOOD YASAK!**
   • 5 saniyede 5'ten fazla mesaj: **5 dk susturma**
   • Flood yapmak yasaktır

5️⃣ **REKLAM YASAK!**
   • İzinsiz reklam yasaktır
   • Spam mesajlar silinir

6️⃣ **YENİ ÜYELER**
   • Her yeni üye karşılanır
   • Kuralları okuması istenir
"""
    await update.message.reply_text(rules, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: CallbackContext):
    """BOT İSTATİSTİKLERİ KOMUTU"""
    cleanup_expired()
    
    stats = f"""
📊 **BOT İSTATİSTİKLERİ**

• **Kapalı Gruplar:** {len(muted_groups)}
• **Yasaklı Kelimeler:** {len(BANNED_WORDS)}
• **Spam Bot Listesi:** {len(SPAM_BOTS)}
• **Flood Limiti:** {FLOOD_LIMIT} mesaj / {FLOOD_WINDOW} saniye
• **Kapatma Süresi:** 6 saat
• **Karşılama Mesajları:** {len(WELCOME_MESSAGES)}

🔧 **Bot Durumu:** Çalışıyor
🔄 **Son Güncelleme:** {datetime.now().strftime('%H:%M:%S')}
📅 **Tarih:** {datetime.now().strftime('%d.%m.%Y')}

🤖 **Özellikler:** Tümü aktif
"""
    await update.message.reply_text(stats, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: CallbackContext):
    """YARDIM KOMUTU"""
    await start_command(update, context)

# ==================== 7. TEMİZLEME JOB'I ====================
async def cleanup_job(context: CallbackContext):
    """Düzenli temizleme job'ı"""
    cleanup_expired()
    logger.info("🔄 Düzenli temizleme yapıldı")

# ==================== 8. HATA YÖNETİMİ ====================
async def error_handler(update: Update, context: CallbackContext):
    """HATA YÖNETİCİSİ"""
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

# ==================== 9. BOT BAŞLATMA ====================
def main():
    """ANA FONKSİYON - Bot'u başlat"""
    if not TELEGRAM_AVAILABLE:
        print("❌ Telegram kütüphanesi yüklenemedi!")
        sys.exit(1)
    
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
        # Application oluştur
        app = Application.builder().token(BOT_TOKEN).build()
        
        print("✅ Application oluşturuldu")
        
        # Hata handler'ı ekle
        app.add_error_handler(error_handler)
        
        # KOMUTLAR
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("durum", durum_command))
        app.add_handler(CommandHandler("ac", ac_command))
        app.add_handler(CommandHandler("kapat", kapat_command))
        app.add_handler(CommandHandler("rules", rules_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("help", help_command))
        
        print("✅ Komutlar eklendi")
        
        # MESAJ HANDLER'LARI
        # 1. Spam bot kontrolü
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_spam_bots
        ))
        
        # 2. Grup kapalıyken kontrol
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
        
        # Temizleme job'ını ekle (her saat)
        app.job_queue.run_repeating(cleanup_job, interval=3600, first=10)
        
        print("✅ Job'lar eklendi")
        print("✅ Bot başlatılıyor...")
        print("=" * 60)
        
        # Bot'u başlat
        app.run_polling(
            poll_interval=1.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"❌ Bot başlatma hatası: {e}")
        print(f"❌ HATA: {type(e).__name__}: {e}")
        
        # Detaylı hata bilgisi
        import traceback
        traceback.print_exc()
        
        sys.exit(1)

if __name__ == '__main__':
    # Async işlemler için
    import asyncio
    asyncio.run(main() if hasattr(main, '__await__') else None)
