import random
from typing import Optional

class ProxyManager:
    """Proxy rotasyonu için"""
    
    # Public proxy listesi (ücretsiz)
    PROXIES = [
        # Not: Gerçek proxy'ler kullanın
        # "http://proxy1:8080",
        # "http://proxy2:8080",
    ]
    
    @classmethod
    def get_proxy(cls) -> Optional[str]:
        """Rastgele bir proxy döndür"""
        if cls.PROXIES:
            return random.choice(cls.PROXIES)
        return None
    
    @classmethod
    def add_proxy(cls, proxy: str):
        """Proxy ekle"""
        if proxy not in cls.PROXIES:
            cls.PROXIES.append(proxy)
