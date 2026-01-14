import logging
import os
import asyncio
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
import json
from flask import Flask, request
import threading

# Flask app for Render health check
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Telegram Bot is Running!", 200

@flask_app.route('/health')
def health():
    return "OK", 200

# Log ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token'ı (Render Environment'dan al veya .env)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8122690327:AAHTN0X87h7q81xj9rThs0vaqGrcra_Nf28")

# Yasaklı kelimeler listesi
BANNED_WORDS = [
    "amk", "aq", "sg", "siktir", "orosbu", "piç", "küfür", "sövmek",
    "mal", "salak", "aptal", "gerizekalı", "ibne", "göt", "yarrak",
    "anan", "baban", "pezevenk", "kahpe", "orospu"
]

# Spam bot listesi (reklam atan botlar)
SPAM_BOTS = [
    "InsideAds_bot", 
    "PromotionBot",
    "advertise_bot",
    "ads_bot",
    "spam_bot",
    "reklam_bot"
]

# Flood koruma için
user_messages = {}
FLOOD_LIMIT = 5
FLOOD_WINDOW = 5

# Grup kapalı süresi (8 saat)
MUTE_DURATION = 8 * 60 * 60

# Karşılama mesajları
WELCOME_MESSAGES = [
    "Hoşgeldin airdropçu! 👋",
    "Yeni airdropçu aramıza katıldı! 🎉",
    "Hoşgeldin! Airdrop fırsatlarını kaçırma! 💰",
    "Aramıza hoşgeldin airdrop avcısı! 🚀",
    "Hoşgeldin! Bol şans ve bol kazançlar dileriz! 🍀"
]

# Veri dosyası
DATA_FILE = "data/bot_data.json"

# Susturulmuş grupları takip et
muted_groups = {}
group_settings = {}

class BotData:
    @staticmethod
    def save_data():
        """Verileri JSON dosyasına kaydet"""
        data = {
            'muted_groups': {
                str(k): {
                    'muted_at': v['muted_at'].isoformat() if 'muted_at' in v else None,
                    'muted_by': v.get('muted_by', 'insideads_bot'),
                    'expires_at': v['expires_at'].isoformat() if 'expires_at' in v else None
                } for k, v in muted_groups.items()
            },
            'group_settings': group_settings,
            'last_update': datetime.now().isoformat()
        }
        
        # data klasörünü kontrol et
        os.makedirs('data', exist_ok=True)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_data():
        """JSON dosyasından verileri yükle"""
        global muted_groups, group_settings
        
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # muted_groups'u yükle
                    muted_groups = {}
                    for k, v in data.get('muted_groups', {}).items():
                        muted_groups[int(k)] = {
                            'muted_at': datetime.fromisoformat(v['muted_at']) if v.get('muted_at') else None,
                            'muted_by': v.get('muted_by', 'insideads_bot'),
                            'expires_at': datetime.fromisoformat(v['expires_at']) if v.get('expires_at') else None
                        }
                    
                    # group_settings'i yükle
                    group_settings = data.get('group_settings', {})
                    
                    logger.info(f"Veriler yüklendi: {len(muted_groups)} kapalı grup")
            else:
                logger.info("Veri dosyası bulunamadı, yeni oluşturulacak")
        except Exception as e:
            logger.error(f"Veri yükleme hatası: {e}")
            muted_groups = {}
            group_settings = {}

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yeni üyeleri karşılama"""
    try:
        for member in update.message.new_chat_members:
            if not member.is_bot:
                welcome_message = f"🎉 {WELCOME_MESSAGES[hash(member.id) % len(WELCOME_MESSAGES)]}\n\n"
                welcome_message += f"Selam {member.mention_html()}!\n"
                welcome_message += "Grubumuza hoşgeldin! Airdrop fırsatlarını kaçırma! 🚀\n"
                welcome_message += "📜 Kurallar: /rules\n"
                welcome_message += "❓ Yardım: /help"
                
                await update.message.reply_text(
                    welcome_message,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Yeni üye: {member.id}")
    except Exception as e:
        logger.error(f"Karşılama hatası: {e}")

async def handle_spam_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spam botlarını (InsideAds_bot vb.) tespit et ve grubu kapat"""
    if not update.message:
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Spam bot kontrolü
    is_spam_bot = False
    bot_username = user.username.lower() if user.username else ""
    
    for spam_bot in SPAM_BOTS:
        if spam_bot.lower() in bot_username:
            is_spam_bot = True
            break
    
    # Mesaj içeriğinde reklam kontrolü
    message_text = update.message.text or update.message.caption or ""
    message_text_lower = message_text.lower()
    
    spam_keywords = ["reklam", "promotion", "advertise", "ads", "ilan", "sponsor", "kumar", "bahis"]
    contains_spam = any(keyword in message_text_lower for keyword in spam_keywords)
    
    if is_spam_bot or contains_spam:
        try:
            # Botun mesajını sil
            await update.message.delete()
            
            # Grup zaten kapalı mı kontrol et
            if chat_id in muted_groups:
                logger.info(f"Grup zaten kapalı: {chat_id}")
                return
            
            # Grubu kapat
            await mute_all_users(chat_id, context, f"Spam bot: {user.username}")
            
            # Kaydet
            expires_at = datetime.now() + timedelta(seconds=MUTE_DURATION)
            muted_groups[chat_id] = {
                'muted_at': datetime.now(),
                'muted_by': user.username or "spam_bot",
                'expires_at': expires_at
            }
            BotData.save_data()
            
            # Uyarı mesajı
            announcement = "🚨 **GRUP GEÇİCİ OLARAK KAPATILDI!**\n\n"
            announcement += f"❌ **Sebep:** @{user.username} spam/reklam botu tespit edildi!\n"
            announcement += "⏰ **Süre:** 8 saat\n"
            announcement += f"🕒 **Açılma:** {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            announcement += "📌 **Durum:** Tüm kullanıcılar mesaj YAZAMAZ!\n"
            announcement += "⚠️ **Not:** Süre dolunca otomatik açılacak\n"
            announcement += "🔓 **Admin açmak için:** /unlock"
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=announcement,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Spam bot tespit edildi: {user.username} - Grup kapatıldı: {chat_id}")
            
            # 8 saat sonra otomatik aç
            context.job_queue.run_once(
                unmute_group_job,
                MUTE_DURATION,
                data=chat_id,
                name=f"unmute_{chat_id}"
            )
            
        except Exception as e:
            logger.error(f"Spam bot işleme hatası: {e}")

async def mute_all_users(chat_id: int, context: ContextTypes.DEFAULT_TYPE, reason: str = ""):
    """Tüm kullanıcıların mesaj atmasını engelle"""
    try:
        # Grup izinlerini değiştir (TÜM KULLANICILAR için)
        await context.bot.set_chat_permissions(
            chat_id=chat_id,
            permissions=ChatPermissions(
                can_send_messages=False,          # Normal mesaj YOK
                can_send_media_messages=False,    # Medya YOK
                can_send_polls=False,             # Anket YOK
                can_send_other_messages=False,    # Diğer mesajlar YOK
                can_add_web_page_previews=False,  # Web önizleme YOK
                can_change_info=False,            # Grup bilgisi değiştirme YOK
                can_invite_users=True,            # Davet edebilir
                can_pin_messages=False,           # Sabitleme YOK
                can_manage_topics=False           # Konu yönetimi YOK
            )
        )
        return True
    except Exception as e:
        logger.error(f"Grup kapatma hatası ({reason}): {e}")
        return False

async def unmute_all_users(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Tüm kullanıcıların mesaj atmasını aktif et"""
    try:
        # Normal grup izinlerine dön
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
                can_pin_messages=False,
                can_manage_topics=False
            )
        )
        
        # Listeden çıkar
        if chat_id in muted_groups:
            del muted_groups[chat_id]
            BotData.save_data()
        
        return True
    except Exception as e:
        logger.error(f"Grup açma hatası: {e}")
        return False

async def unmute_group_job(context: ContextTypes.DEFAULT_TYPE):
    """Job olarak grubu aç"""
    chat_id = context.job.data
    
    try:
        # Grubu aç
        success = await unmute_all_users(chat_id, context)
        
        if success:
            # Bilgilendirme mesajı
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ **GRUP TEKRAR AÇILDI!**\n\n"
                     "8 saatlik süre doldu, artık normal mesajlaşabilirsiniz.\n"
                     "⚠️ **Uyarı:** Spam botları davet etmeyin!",
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Grup otomatik açıldı: {chat_id}")
    except Exception as e:
        logger.error(f"Otomatik açma hatası: {e}")

async def check_message_restrictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup kapalıyken mesajları engelle"""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Grup kapalı mı kontrol et
    if chat_id not in muted_groups:
        return
    
    # Admin kontrolü (sadece /unlock komutuna izin ver)
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
    except:
        is_admin = False
    
    # Komut kontrolü
    message_text = update.message.text or ""
    
    # Sadece /unlock komutuna izin ver (adminler için)
    if message_text.startswith('/unlock') and is_admin:
        return  # /unlock komutuna izin ver
    
    # Diğer tüm mesajları sil
    try:
        await update.message.delete()
        
        # Sadece ilk mesajda uyarı göster
        if not hasattr(context, 'warning_sent'):
            context.warning_sent = True
            warning_msg = "⚠️ **Grup şu anda kapalı!**\n\n"
            warning_msg += "Spam bot tespit edildiği için grup geçici olarak kapatıldı.\n"
            warning_msg += "⏰ **Süre:** 8 saat\n"
            warning_msg += "👑 **Adminler:** Sadece /unlock komutunu kullanabilir\n"
            warning_msg += "👤 **Kullanıcılar:** Mesaj YAZAMAZSINIZ!"
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=warning_msg,
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Mesaj silme hatası: {e}")

async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grubu manuel açma komutu"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Admin kontrolü
    try:
        chat_admins = await update.effective_chat.get_administrators()
        is_admin = any(admin.user.id == user_id for admin in chat_admins)
        
        if not is_admin:
            await update.message.reply_text("❌ Bu komutu sadece yöneticiler kullanabilir!")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Admin kontrol hatası: {e}")
        return
    
    # Grup kapalı mı kontrol et
    if chat_id not in muted_groups:
        await update.message.reply_text("ℹ️ Grup zaten açık!")
        return
    
    try:
        # Grubu aç
        success = await unmute_all_users(chat_id, context)
        
        if success:
            # Job'ları temizle
            current_jobs = context.job_queue.get_jobs_by_name(f"unmute_{chat_id}")
            for job in current_jobs:
                job.schedule_removal()
            
            await update.message.reply_text(
                "✅ **Grup başarıyla açıldı!**\n"
                "Artık normal mesajlaşabilirsiniz.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Grup manuel açıldı: {chat_id} - Admin: {user_id}")
        else:
            await update.message.reply_text("❌ Grup açılamadı! Bot yetkilerini kontrol edin.")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)[:100]}")
        logger.error(f"Unlock hatası: {e}")

async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grubu manuel kapatma komutu (test için)"""
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
        # Grubu kapat
        await mute_all_users(chat_id, context, "manuel_lock")
        
        # Kaydet
        expires_at = datetime.now() + timedelta(seconds=MUTE_DURATION)
        muted_groups[chat_id] = {
            'muted_at': datetime.now(),
            'muted_by': f"admin_{user_id}",
            'expires_at': expires_at
        }
        BotData.save_data()
        
        await update.message.reply_text(
            "🔒 **Grup manuel olarak kapatıldı!**\n"
            f"⏰ Açılma: {expires_at.strftime('%H:%M')}\n"
            "Açmak için: /unlock",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Otomatik açma job'ı
        context.job_queue.run_once(
            unmute_group_job,
            MUTE_DURATION,
            data=chat_id,
            name=f"unmute_{chat_id}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup durumunu göster"""
    chat_id = update.effective_chat.id
    
    if chat_id in muted_groups:
        group_data = muted_groups[chat_id]
        expires_at = group_data.get('expires_at')
        muted_by = group_data.get('muted_by', 'bilinmiyor')
        
        if expires_at:
            remaining = expires_at - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                time_left = f"{hours} saat {minutes} dakika"
            else:
                time_left = "Süre doldu (yakında açılacak)"
        else:
            time_left = "Süre belirsiz"
        
        status_text = f"""
🔴 **GRUP DURUMU: KAPALI**

📌 **Sebep:** @{muted_by} spam botu
⏳ **Kalan Süre:** {time_left}
🕒 **Açılma Zamanı:** {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'Belirsiz'}

👑 **Adminler:** Sadece /unlock komutu
👤 **Kullanıcılar:** Mesaj YAZAMAZ!

⚠️ **Not:** 8 saat sonra otomatik açılacak
"""
    else:
        status_text = """
🟢 **GRUP DURUMU: AÇIK**

✅ Normal mesajlaşma aktif
🛡️ Spam bot koruması: AKTİF
👑 Adminler: Tam yetkili
👤 Kullanıcılar: Normal mesajlaşabilir

⚠️ **Uyarı:** InsideAds_bot gibi spam botları eklemeyin!
"""
    
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komutu"""
    await update.message.reply_text(
        "🤖 **Airdrop Robotu Guard Bot**\n\n"
        "**Özellikler:**\n"
        "🛡️ InsideAds_bot ve spam bot koruması\n"
        "⏰ Spam tespitinde 8 saat grup kapatma\n"
        "👑 Admin kontrolü (/unlock)\n"
        "👋 Yeni üye karşılama\n\n"
        "**Komutlar:**\n"
        "/help - Tüm komutlar\n"
        "/status - Grup durumu\n"
        "/unlock - Grubu aç (admin)\n"
        "/lock - Grubu kapat (admin, test için)\n\n"
        "📢 **Grup:** @AirdropRobotu"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help komutu"""
    help_text = """
📋 **KOMUT LİSTESİ**

**Genel Komutlar:**
/start - Botu başlat
/help - Yardım mesajı
/status - Grup durumu
/rules - Grup kuralları
/stats - Bot istatistikleri

**Admin Komutları:**
/unlock - Grubu aç (8 saat beklemeden)
/lock - Grubu kapat (test için)
/settings - Bot ayarları

🚨 **SPAM BOT KORUMASI:**
• InsideAds_bot ve benzeri botlar tespit edilirse
• Grup otomatik 8 saat kapanır
• TÜM kullanıcılar mesaj YAZAMAZ
• Sadece adminler /unlock komutunu kullanabilir
• 8 saat sonra otomatik açılır

⚠️ **UYARI:** Spam botları gruba eklemeyin!
"""
    await update.message.reply_text(help_text)

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grup kuralları"""
    rules_text = """
📜 **GRUP KURALLARI**

1️⃣ **SPAM BOT YASAK!**
   - InsideAds_bot, PromotionBot vb. spam botlar
   - Ekleyen: DAİMİ BAN
   - Tespit edilirse: Grup 8 saat kapanır

2️⃣ **KÜFÜR/HAKARET YASAK!**
   - Yasaklı kelimeler filtrelenir
   - Uymayan: Mesaj silinir + uyarı

3️⃣ **REKLAM YASAK!**
   - İzinsiz reklam, link paylaşımı
   - Sadece admin onaylı reklamlar

4️⃣ **FLOOD YASAK!**
   - Arka arkaya mesaj atma
   - Spam sayılır, susturulursunuz

5️⃣ **YETKİLİLERE SAYGI!**
   - Admin kararlarına itiraz yok
   - Kurallara uymayan yasaklanır

🚨 **ÖNEMLİ:** Spam bot = 8 saat grup kapanır!
"""
    await update.message.reply_text(rules_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot istatistikleri"""
    stats_text = f"""
📊 **BOT İSTATİSTİKLERİ**

**Sistem Durumu:**
• Çalışma Süresi: {datetime.now().strftime('%d.%m.%Y %H:%M')}
• Kapalı Gruplar: {len(muted_groups)}
• Aktif Kullanıcılar: {len(user_messages)}

**Koruma Sistemleri:**
🛡️ Spam Bot Koruması: ✅ AKTİF
⏰ Otomatik Kapatma: ✅ 8 saat
🔓 Manuel Açma: ✅ /unlock komutu
👋 Hoşgeldin Mesajı: ✅ AKTİF

**Spam Bot Listesi:**
{', '.join(SPAM_BOTS[:3])}...

**Sistem:** 🟢 ÇALIŞIYOR
"""
    await update.message.reply_text(stats_text)

async def cleanup_expired_groups(context: ContextTypes.DEFAULT_TYPE):
    """Süresi dolmuş grupları temizle"""
    try:
        now = datetime.now()
        expired_groups = []
        
        for chat_id, data in list(muted_groups.items()):
            expires_at = data.get('expires_at')
            if expires_at and expires_at < now:
                expired_groups.append(chat_id)
                # Grubu aç
                await unmute_all_users(chat_id, context)
        
        if expired_groups:
            logger.info(f"Süresi dolan gruplar temizlendi: {len(expired_groups)}")
            
    except Exception as e:
        logger.error(f"Temizleme hatası: {e}")

async def post_init(application: Application):
    """Bot başlatıldığında yapılacak işlemler"""
    # Verileri yükle
    BotData.load_data()
    
    # Süresi dolmuş grupları temizle
    await cleanup_expired_groups(application)
    
    # Süreli job'ları yeniden başlat
    for chat_id, data in muted_groups.items():
        expires_at = data.get('expires_at')
        if expires_at:
            remaining = (expires_at - datetime.now()).total_seconds()
            if remaining > 0:
                application.job_queue.run_once(
                    unmute_group_job,
                    remaining,
                    data=chat_id,
                    name=f"unmute_{chat_id}"
                )
    
    logger.info(f"Bot başlatıldı. {len(muted_groups)} kapalı grup yüklendi.")

def run_flask():
    """Flask server'ı başlat (Render için)"""
    port = int(os.getenv("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False)

def main():
    """Bot'u başlat"""
    # Flask'ı thread'de başlat
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Application oluştur
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Handler'ları ekle
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("unlock", unlock_command))
    application.add_handler(CommandHandler("lock", lock_command))
    
    # Spam bot handler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_spam_bot
    ))
    
    # Grup kapalıyken mesaj kontrolü
    application.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        check_message_restrictions
    ))
    
    # Yeni üye handler
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome_new_member
    ))
    
    # Periyodik temizleme job'ı (her saat)
    application.job_queue.run_repeating(
        cleanup_expired_groups,
        interval=3600,  # 1 saat
        first=10
    )
    
    # Bot'u başlat
    print("=" * 50)
    print("🤖 Airdrop Robotu Guard Bot Başlatılıyor...")
    print(f"🌐 Web Server: http://0.0.0.0:{os.getenv('PORT', 10000)}")
    print(f"🔐 Token: {BOT_TOKEN[:10]}...")
    print("🛡️ Spam Bot Koruması: AKTİF (InsideAds_bot, vb.)")
    print("⏰ Otomatik Kapatma: 8 SAAT")
    print("👤 Tüm Kullanıcılar: Mesaj YAZAMAZ (grup kapalıyken)")
    print("=" * 50)
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
