#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 TELEGRAM BOT - TÜM ÖZELLİKLER
1. InsideAds_bot mesaj atınca 6 saat grup kapanır
2. Tüm kullanıcılar mesaj yazamaz
3. Adminler sadece /ac komutunu kullanabilir
4. 6 saat sonra otomatik açılır
5. Yeni üye karşılama
6. Küfür filtresi
7. Flood koruması
8. Komut sistemi
9. Render uyumlu
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext,
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

# DİĞER SPAM BOTLAR
SPAM_BOTS = [
    "InsideAds_bot",
    "PromotionBot", 
    "advertise_bot",
    "ads_bot",
    "spam_bot",
    "reklam_bot",
    "airdrop_bot",
    "crypto_ads_bot"
]

# KAPALI KALMA SÜRESİ (6 SAAT)
MUTE_DURATION = 6 * 60 * 60

# YASAKLI KELİMELER
BANNED_WORDS = [
    "amk", "aq", "sg", "siktir", "orosbu", "piç", "küfür",
    "mal", "salak", "aptal", "gerizekalı", "ibne", "göt",
    "yarrak", "anan", "baban", "pezevenk", "kahpe", "orospu"
]

# FLOOD KORUMA AYARLARI
FLOOD_LIMIT = 5  # 5 saniyede maksimum mesaj
FLOOD_WINDOW = 5  # Saniye cinsinden zaman penceresi

# VERİ DOSYASI
DATA_FILE = "bot_data.json"

# KARŞILAMA MESAJLARI
WELCOME_MESSAGES = [
    "Hoşgeldin airdropçu! 👋",
    "Yeni airdropçu aramıza katıldı! 🎉",
    "Hoşgeldin! Airdrop fırsatlarını kaçırma! 💰",
    "Aramıza hoşgeldin airdrop avcısı! 🚀",
    "Hoşgeldin! Bol şans ve bol kazançlar dileriz! 🍀"
]

# ==================== VERİ YAPILARI ====================
muted_groups = {}  # Kapalı gruplar: {chat_id: {expires_at, reason}}
user_messages = {}  # Flood kontrolü: {user_id: [timestamp1, timestamp2...]}
group_settings = {}  # Grup ayarları

# ==================== VERİ YÖNETİMİ ====================
def save_data():
    """Tüm verileri kaydet"""
    try:
        data = {
            'muted_groups': {
                str(chat_id): {
                    'expires_at': info['expires_at'].isoformat(),
                    'reason': info['reason'],
                    'muted_at': info.get('muted_at', datetime.now().isoformat())
                }
                for chat_id, info in muted_groups.items()
            },
            'group_settings': group_settings,
            'last_update': datetime.now().isoformat()
        }
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Veriler kaydedildi: {len(muted_groups)} kapalı grup")
        return True
    except Exception as e:
        logger.error(f"❌ Kaydetme hatası: {e}")
        return False

def load_data():
    """Tüm verileri yükle"""
    global muted_groups, group_settings
    
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # muted_groups yükle
                muted_groups = {}
                for chat_id_str, info in data.get('muted_groups', {}).items():
                    muted_groups[int(chat_id_str)] = {
                        'expires_at': datetime.fromisoformat(info['expires_at']),
                        'reason': info['reason'],
                        'muted_at': datetime.fromisoformat(info.get('muted_at', datetime.now().isoformat()))
                    }
                
                # group_settings yükle
                group_settings = data.get('group_settings', {})
                
            logger.info(f"📂 Veriler yüklendi: {len(muted_groups)} kapalı grup")
        else:
            logger.info("📂 Veri dosyası yok, yeni oluşturulacak")
            muted_groups = {}
            group_settings = {}
    except Exception as e:
        logger.error(f"❌ Yükleme hatası: {e}")
        muted_groups = {}
        group_settings = {}

# ==================== TEMEL FONKSİYONLAR ====================
async def mute_all_users(chat_id: int, context: ContextTypes.DEFAULT_TYPE, reason: str):
    """Grubu kapat - Tüm kullanıcılar mesaj yazamaz"""
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
        
        # Kaydet
        expires_at = datetime.now() + timedelta(seconds=MUTE_DURATION)
        muted_groups[chat_id] = {
            'expires_at': expires_at,
            'reason': reason,
            'muted_at': datetime.now()
        }
        save_data()
        
        logger.info(f"🔒 Grup kapatıldı: {chat_id} - Sebep: {reason}")
        return True, expires_at
    except Exception as e:
        logger.error(f"❌ Grup kapatma hatası: {e}")
        return False, None

async def unmute_all_users(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Grubu aç - Normal mesajlaşmaya dön"""
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
        
        # Listeden çıkar
        if chat_id in muted_groups:
            del muted_groups[chat_id]
            save_data()
        
        logger.info(f"🔓 Grup açıldı: {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Grup açma hatası: {e}")
        return False

# ==================== İÇİNDEKİLER ====================
# 1. InsideAds_bot Koruma
# 2. Grup Kapalıyken Mesaj Kontrolü
# 3. Yeni Üye Karşılama
# 4. Küfür Filtresi
# 5. Flood Koruması
# 6. Komut Sistemi
# 7. Otomatik Temizleme

# ==================== 1. INSIDEADS_BOT KORUMA ====================
async def handle_spam_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spam botları tespit et ve grubu kapat"""
    if not update.message or not update.effective_user:
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Spam bot kontrolü
    is_spam_bot = False
    username = user.username.lower() if user.username else ""
    
    for spam_bot in SPAM_BOTS:
        if spam_bot.lower() in username:
            is_spam_bot = True
            break
    
    # Mesajda reklam kontrolü
    message_text = update.message.text or update.message.caption or ""
    message_lower = message_text.lower()
    
    spam_keywords = ["reklam", "promotion", "advertise", "ads", "sponsor", "ilan", "click", "join", "kazan"]
    has_spam = any(keyword in message_lower for keyword in spam_keywords)
    
    # InsideAds_bot ÖZEL kontrol
    if user.username == REKLAM_BOT_USERNAME:
        is_spam_bot = True
    
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
                logger.info(f"🗑️ Spam bot mesajı silindi: @{user.username}")
            except:
                pass
            
            # Grubu 6 saat kapat
            success, expires_at = await mute_all_users(chat_id, context, f"@{user.username}")
            
            if success and expires_at:
                # Uyarı mesajı
                warning = f"""
🚨 **🚨 GRUP KAPATILDI! 🚨**

❌ **SEBEP:** @{user.username} spam/reklam botu
⏰ **SÜRE:** 6 SAAT
🕒 **AÇILMA:** {expires_at.strftime('%d.%m.%Y %H:%M')}

📌 **KURALLAR:**
• TÜM kullanıcılar mesaj YAZAMAZ
• Sadece yöneticiler /ac komutunu kullanabilir
• 6 saat sonra otomatik açılır

⚠️ **UYARI:** Spam botları gruba EKLEMEYİN!
"""
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=warning,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # 6 saat sonra otomatik aç
                context.job_queue.run_once(
                    auto_unmute_job,
                    MUTE_DURATION,
                    data=chat_id,
                    name=f"unmute_{chat_id}"
                )
                
                logger.info(f"✅ {user.username} tespit edildi - Grup 6 saat kapandı")
            
        except Exception as e:
            logger.error(f"❌ Spam bot işleme hatası: {e}")

# ==================== 2. GRUP KAPALIYKEN MESAJ KONTROLÜ ====================
async def check_group_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup kapalıyken mesajları engelle"""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    
    # Grup açık mı?
    if chat_id not in muted_groups:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text or ""
    
    # Admin kontrolü
    is_admin = False
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
    except:
        pass
    
    # Adminler sadece /ac komutunu kullanabilir
    if message_text.startswith('/ac') and is_admin:
        return
    
    # Diğer TÜM mesajları SİL
    try:
        await update.message.delete()
        
        # Sadece ilk mesajda uyarı göster
        if not hasattr(context, 'warning_shown'):
            context.warning_shown = True
            
            # Grup bilgilerini al
            group_info = muted_groups.get(chat_id, {})
            expires_at = group_info.get('expires_at', datetime.now())
            reason = group_info.get('reason', 'spam bot')
            
            # Kalan süre
            remaining = expires_at - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                time_left = f"{hours} saat {minutes} dakika"
            else:
                time_left = "yakında açılacak"
            
            warning = f"""
⚠️ **GRUP ŞU ANDA KAPALI!**

📌 **Sebep:** {reason}
⏳ **Kalan süre:** {time_left}
🕒 **Açılma zamanı:** {expires_at.strftime('%H:%M')}

👑 **Adminler:** Sadece /ac komutunu kullanabilir
👤 **Kullanıcılar:** Mesaj YAZAMAZSINIZ!

🔓 Açmak için (adminler): /ac
"""
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=warning,
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        logger.error(f"❌ Mesaj silme hatası: {e}")

# ==================== 3. YENİ ÜYE KARŞILAMA ====================
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yeni üyeleri karşıla"""
    try:
        for member in update.message.new_chat_members:
            if not member.is_bot:  # Botları karşılama
                welcome_index = hash(member.id) % len(WELCOME_MESSAGES)
                welcome_msg = WELCOME_MESSAGES[welcome_index]
                
                message = f"""
🎉 **{welcome_msg}**

Selam {member.mention_html()}! 👋

📌 **Grubumuza hoşgeldin!**
• Kurallar: /rules
• Yardım: /help
• Durum: /durum

💰 Airdrop fırsatlarını kaçırma!
"""
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"👋 Yeni üye karşılandı: {member.id}")
                
    except Exception as e:
        logger.error(f"❌ Karşılama hatası: {e}")

# ==================== 4. KÜFÜR FİLTRESİ ====================
async def check_banned_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yasaklı kelimeleri kontrol et"""
    if not update.message or not update.message.text:
        return
    
    # Grup kapalıysa işlem yapma
    chat_id = update.effective_chat.id
    if chat_id in muted_groups:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text.lower()
    
    # Admin kontrolü (adminler küfürden etkilenmez)
    is_admin = False
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
    except:
        pass
    
    if is_admin:
        return
    
    # Yasaklı kelime kontrolü
    for word in BANNED_WORDS:
        if word in message_text:
            try:
                await update.message.delete()
                
                warning = f"⚠️ {update.effective_user.mention_html()}, mesajınız yasaklı kelime içerdiği için silindi!"
                await update.message.chat.send_message(
                    warning,
                    parse_mode=ParseMode.HTML
                )
                
                logger.info(f"🚫 Yasaklı kelime: {user_id} - Kelime: {word}")
                return
                
            except Exception as e:
                logger.error(f"❌ Küfür filtresi hatası: {e}")
                return

# ==================== 5. FLOOD KORUMASI ====================
async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Flood kontrolü"""
    if not update.message:
        return
    
    # Grup kapalıysa işlem yapma
    chat_id = update.effective_chat.id
    if chat_id in muted_groups:
        return
    
    user_id = update.effective_user.id
    
    # Admin kontrolü (adminler flood'dan etkilenmez)
    is_admin = False
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
    except:
        pass
    
    if is_admin:
        return
    
    now = datetime.now()
    
    # Flood kontrolü
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    # Eski mesajları temizle
    user_messages[user_id] = [
        msg_time for msg_time in user_messages[user_id]
        if now - msg_time < timedelta(seconds=FLOOD_WINDOW)
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
            await update.message.chat.send_message(warning, parse_mode=ParseMode.HTML)
            
            await update.message.delete()
            
            logger.info(f"🌊 Flood tespit edildi: {user_id}")
            user_messages[user_id] = []  # Reset
            
        except Exception as e:
            logger.error(f"❌ Flood susturma hatası: {e}")

# ==================== 6. KOMUT SİSTEMİ ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Başlangıç komutu"""
    await update.message.reply_text(
        "🤖 **TELEGRAM BOT - TÜM ÖZELLİKLER**\n\n"
        "🚨 **ANA ÖZELLİKLER:**\n"
        "• @InsideAds_bot mesaj atarsa 6 SAAT grup kapanır\n"
        "• Tüm kullanıcılar mesaj YAZAMAZ\n"
        "• Sadece adminler /ac komutunu kullanabilir\n"
        "• 6 saat sonra otomatik açılır\n\n"
        "🛡️ **DİĞER ÖZELLİKLER:**\n"
        "• Yeni üye karşılama\n"
        "• Küfür filtresi\n"
        "• Flood koruması\n"
        "• Spam bot koruması\n\n"
        "📋 **KOMUTLAR:**\n"
        "/start - Bu mesaj\n"
        "/help - Tüm komutlar\n"
        "/durum - Grup durumu\n"
        "/rules - Grup kuralları\n"
        "/stats - Bot istatistikleri\n"
        "/ac - Grubu aç (admin)\n"
        "/kapat - Test kapatma (admin)\n\n"
        "⚠️ **UYARI:** Spam botları eklemeyin!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım komutu"""
    help_text = """
📋 **TÜM KOMUTLAR**

**Genel Komutlar:**
/start - Bot bilgileri
/help - Yardım mesajı
/durum - Grup durumu
/rules - Grup kuralları
/stats - Bot istatistikleri

**Admin Komutları:**
/ac - Grubu aç (6 saat beklemeden)
/kapat - Test için kapat
/eklekelime [kelime] - Yasaklı kelime ekle
/silkelime [kelime] - Yasaklı kelime sil
/kelimeler - Yasaklı kelimeleri listele

🚨 **SPAM BOT KORUMASI:**
• InsideAds_bot mesaj atarsa
• Grup 6 SAAT kapanır
• TÜM kullanıcılar mesaj YAZAMAZ
• Sadece adminler /ac komutunu kullanabilir
"""
    await update.message.reply_text(help_text)

async def durum_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup durumu komutu"""
    chat_id = update.effective_chat.id
    
    if chat_id in muted_groups:
        info = muted_groups[chat_id]
        expires_at = info['expires_at']
        reason = info['reason']
        
        # Kalan süre
        remaining = expires_at - datetime.now()
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            time_left = f"{hours} saat {minutes} dakika"
        else:
            time_left = "yakında açılacak"
        
        status = f"""
🔴 **GRUP DURUMU: KAPALI**

📌 **Sebep:** {reason}
⏳ **Kalan süre:** {time_left}
🕒 **Açılma:** {expires_at.strftime('%H:%M')}

👑 **Adminler:** /ac komutuyla açabilir
👤 **Kullanıcılar:** Mesaj YAZAMAZ

⚠️ **Not:** 6 saat sonra otomatik açılacak
"""
    else:
        status = """
🟢 **GRUP DURUMU: AÇIK**

✅ Normal mesajlaşma aktif
🚨 Spam bot koruması: AKTİF
⏰ Kapatma süresi: 6 SAAT
👑 Admin açma komutu: /ac

📊 **Aktif korumalar:**
• InsideAds_bot koruması
• Küfür filtresi
• Flood koruması
• Yeni üye karşılama
"""
    
    await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup kuralları komutu"""
    rules = """
📜 **GRUP KURALLARI**

1️⃣ **SPAM BOT YASAK!**
   - InsideAds_bot, PromotionBot vb.
   - Ekleyen: DAİMİ BAN
   - Tespit edilirse: Grup 6 saat kapanır

2️⃣ **KÜFÜR/HAKARET YASAK!**
   - Yasaklı kelimeler otomatik silinir
   - Tekrarlayanlar: Susturulur

3️⃣ **REKLAM YASAK!**
   - İzinsiz reklam, link paylaşımı
   - Sadece admin onaylı reklamlar

4️⃣ **FLOOD YASAK!**
   - Arka arkaya mesaj atma
   - 5 saniyede 5'ten fazla mesaj: 5 dk susturma

5️⃣ **YETKİLİLERE SAYGI!**
   - Admin kararlarına itiraz yok
   - Kurallara uymayan yasaklanır

🚨 **ÖNEMLİ:** Spam bot = 6 saat grup kapanır!
"""
    await update.message.reply_text(rules)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """İstatistikler komutu"""
    stats = f"""
📊 **BOT İSTATİSTİKLERİ**

**Genel:**
• Kapalı Gruplar: {len(muted_groups)}
• Aktif Kullanıcılar: {len(user_messages)}
• Yasaklı Kelimeler: {len(BANNED_WORDS)}
• Spam Bot Listesi: {len(SPAM_BOTS)}

**Koruma Sistemleri:**
🛡️ InsideAds_bot Koruması: ✅ AKTİF
🚫 Küfür Filtresi: ✅ AKTİF
🌊 Flood Koruması: ✅ AKTİF
👋 Yeni Üye Karşılama: ✅ AKTİF

**Ayarlar:**
⏰ Kapatma Süresi: 6 SAAT
🚫 Flood Limiti: {FLOOD_LIMIT} mesaj/{FLOOD_WINDOW}s
👑 Admin Komutu: /ac

**Sistem:** 🟢 ÇALIŞIYOR
"""
    await update.message.reply_text(stats)

async def ac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grubu açma komutu (admin)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Admin kontrolü
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Bu komutu sadece yöneticiler kullanabilir!")
            return
    except Exception as e:
        await update.message.reply_text("❌ Admin bilgileri alınamadı!")
        return
    
    # Grup açık mı?
    if chat_id not in muted_groups:
        await update.message.reply_text("ℹ️ Grup zaten açık!")
        return
    
    try:
        # Grubu aç
        success = await unmute_all_users(chat_id, context)
        
        if success:
            # Job'ları temizle
            jobs = context.job_queue.get_jobs_by_name(f"unmute_{chat_id}")
            for job in jobs:
                job.schedule_removal()
            
            await update.message.reply_text(
                "✅ **Grup başarıyla açıldı!**\n"
                "Artık normal mesajlaşabilirsiniz.\n\n"
                "⚠️ **TEKRAR UYARI:**\n"
                "• Spam botları EKLEMEYİN\n"
                "• Eklenirse grup TEKRAR 6 saat kapanır!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"✅ Grup manuel açıldı: {chat_id}")
        else:
            await update.message.reply_text("❌ Grup açılamadı! Bot yetkilerini kontrol edin.")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)[:100]}")

async def kapat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test için grubu kapatma (admin)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Admin kontrolü
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Sadece yöneticiler!")
            return
    except:
        await update.message.reply_text("❌ Admin bilgileri alınamadı!")
        return
    
    if chat_id in muted_groups:
        await update.message.reply_text("⚠️ Grup zaten kapalı!")
        return
    
    try:
        # Test için kapat
        success, expires_at = await mute_all_users(chat_id, context, "test_kapatma")
        
        if success and expires_at:
            # Otomatik açma job'ı
            context.job_queue.run_once(
                auto_unmute_job,
                MUTE_DURATION,
                data=chat_id,
                name=f"unmute_{chat_id}"
            )
            
            await update.message.reply_text(
                f"🔒 **Grup test için kapandı!**\n"
                f"⏰ Açılma: {expires_at.strftime('%H:%M')}\n"
                f"Hemen açmak için: /ac",
                parse_mode=ParseMode.MARKDOWN
            )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")

async def eklekelime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yasaklı kelime ekle (admin)"""
    user_id = update.effective_user.id
    
    # Admin kontrolü
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Sadece yöneticiler!")
            return
    except:
        await update.message.reply_text("❌ Admin bilgileri alınamadı!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Kullanım: /eklekelime [kelime]")
        return
    
    word = context.args[0].lower()
    if word not in BANNED_WORDS:
        BANNED_WORDS.append(word)
        await update.message.reply_text(f"✅ '{word}' yasaklı kelimelere eklendi!")
    else:
        await update.message.reply_text(f"⚠️ '{word}' zaten listede var!")

async def silkelime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yasaklı kelime sil (admin)"""
    user_id = update.effective_user.id
    
    # Admin kontrolü
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Sadece yöneticiler!")
            return
    except:
        await update.message.reply_text("❌ Admin bilgileri alınamadı!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Kullanım: /silkelime [kelime]")
        return
    
    word = context.args[0].lower()
    if word in BANNED_WORDS:
        BANNED_WORDS.remove(word)
        await update.message.reply_text(f"✅ '{word}' listeden silindi!")
    else:
        await update.message.reply_text(f"⚠️ '{word}' listede bulunamadı!")

async def kelimeler_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yasaklı kelimeleri listele"""
    if not BANNED_WORDS:
        await update.message.reply_text("📝 Yasaklı kelime bulunmuyor.")
        return
    
    words_text = "📝 **Yasaklı Kelimeler:**\n\n"
    # İlk 15 kelimeyi göster
    for i, word in enumerate(BANNED_WORDS[:15], 1):
        words_text += f"{i}. {word}\n"
    
    if len(BANNED_WORDS) > 15:
        words_text += f"\n...ve {len(BANNED_WORDS) - 15} kelime daha"
    
    words_text += f"\n\nToplam: {len(BANNED_WORDS)} kelime"
    
    await update.message.reply_text(words_text)

# ==================== 7. OTOMATİK İŞLEMLER ====================
async def auto_unmute_job(context: CallbackContext):
    """6 saat sonra grubu otomatik aç"""
    chat_id = context.job.data
    
    success = await unmute_all_users(chat_id, context)
    if success:
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ **GRUP TEKRAR AÇILDI!**\n\n"
                 "6 saatlik süre doldu.\n"
                 "Artık normal mesajlaşabilirsiniz.\n\n"
                 "⚠️ **UYARI:** Spam botları gruba davet etmeyin!",
            parse_mode=ParseMode.MARKDOWN
        )

async def cleanup_job(context: CallbackContext):
    """Süresi dolmuş grupları temizle"""
    now = datetime.now()
    expired = []
    
    for chat_id, info in list(muted_groups.items()):
        if info['expires_at'] < now:
            expired.append(chat_id)
    
    for chat_id in expired:
        del muted_groups[chat_id]
    
    if expired:
        save_data()
        logger.info(f"♻️ {len(expired)} süresi dolmuş grup temizlendi")

# ==================== BOT BAŞLATMA ====================
def main():
    """Ana fonksiyon - Bot'u başlat"""
    # Verileri yükle
    load_data()
    
    # Application oluştur
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ==================== KOMUT HANDLER'LARI ====================
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("durum", durum_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("ac", ac_command))
    application.add_handler(CommandHandler("kapat", kapat_command))
    application.add_handler(CommandHandler("eklekelime", eklekelime_command))
    application.add_handler(CommandHandler("silkelime", silkelime_command))
    application.add_handler(CommandHandler("kelimeler", kelimeler_command))
    
    # ==================== MESAJ HANDLER'LARI ====================
    # 1. Spam botları yakala
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_spam_bots
    ))
    
    # 2. Grup kapalıyken mesaj kontrolü
    application.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        check_group_status
    ))
    
    # 3. Yeni üye karşılama
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome_new_member
    ))
    
    # 4. Küfür filtresi
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        check_banned_words
    ))
    
    # 5. Flood kontrolü
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        check_flood
    ))
    
    # ==================== JOB QUEUE ====================
    # Periyodik temizleme (her 10 dakikada)
    application.job_queue.run_repeating(
        cleanup_job,
        interval=600,
        first=10
    )
    
    # ==================== BOT'U BAŞLAT ====================
    print("=" * 60)
    print("🤖 TELEGRAM BOT - TÜM ÖZELLİKLER BAŞLATILIYOR")
    print("=" * 60)
    print(f"🔐 Token: {BOT_TOKEN[:10]}...")
    print(f"🎯 Hedef Bot: @{REKLAM_BOT_USERNAME}")
    print(f"🎯 Diğer Spam Botlar: {len(SPAM_BOTS)} adet")
    print("⏰ Kapatma Süresi: 6 SAAT")
    print("👤 Etkilenen: TÜM kullanıcılar (mesaj YAZAMAZ)")
    print("👑 Admin İstisnası: /ac komutu")
    print("🚫 Yasaklı Kelimeler: {len(BANNED_WORDS)} adet")
    print("🌊 Flood Koruması: {FLOOD_LIMIT} mesaj/{FLOOD_WINDOW}s")
    print("👋 Yeni Üye Karşılama: AKTİF")
    print("💾 Veri Kayıt: AKTİF")
    print("=" * 60)
    print("✅ Bot başarıyla başlatıldı! Bekleniyor...")
    
    # Bot'u çalıştır
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == '__main__':
    main()
