#!/usr/bin/env python3
# imghdr_fix.py - Python 3.13 için imghdr workaround

import sys
import mimetypes

class ImghdrModule:
    """Python 3.13'te kaldırılan imghdr modülünün yerine geçer"""
    
    @staticmethod
    def what(file, h=None):
        """Dosya tipini tespit et"""
        try:
            if hasattr(file, 'read'):
                # File-like object
                file.seek(0)
                data = file.read(32)
                file.seek(0)
            else:
                # File path
                with open(file, 'rb') as f:
                    data = f.read(32)
            
            # Dosya imzalarını kontrol et
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
        except:
            pass
        return None
    
    @staticmethod
    def test(file, h=None):
        """Test fonksiyonu"""
        return ImghdrModule.what(file, h)
    
    tests = [what]

# Sisteme ekle
sys.modules['imghdr'] = ImghdrModule()
