# imghdr_fix.py
# Python 3.13'te kaldırılan imghdr modülü için workaround

import mimetypes
import os

# Telegram bot'un ihtiyaç duyduğu imghdr fonksiyonlarını sağla
def what(file, h=None):
    """imghdr.what yerine geçecek fonksiyon"""
    if hasattr(file, 'read'):
        # File-like object
        file.seek(0)
        data = file.read(32)
        file.seek(0)
    else:
        # File path
        with open(file, 'rb') as f:
            data = f.read(32)
    
    # Basit dosya imza kontrolü
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    elif data[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    elif data.startswith(b'BM'):
        return 'bmp'
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'webp'
    
    # MIME type'dan tahmin et
    if isinstance(file, str):
        mime_type, _ = mimetypes.guess_type(file)
        if mime_type:
            if 'jpeg' in mime_type or 'jpg' in mime_type:
                return 'jpeg'
            elif 'png' in mime_type:
                return 'png'
            elif 'gif' in mime_type:
                return 'gif'
            elif 'bmp' in mime_type:
                return 'bmp'
            elif 'webp' in mime_type:
                return 'webp'
    
    return None

def test(file, h=None):
    """imghdr.test yerine geçecek fonksiyon"""
    return what(file, h)

# Global değişkenler
tests = [what]

# imghdr modülünü taklit et
class ImghdrModule:
    what = what
    test = test
    tests = tests
    
    def __getattr__(self, name):
        # Eksik özellikler için None döndür
        return None

# sys.modules'e ekle
import sys
sys.modules['imghdr'] = ImghdrModule()
