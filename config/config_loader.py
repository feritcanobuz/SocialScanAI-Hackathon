"""
SocialScanAI Configuration Loader
Merkezi config dosyasını okur ve environment variables ile birleştirir.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class ConfigLoader:
    """Merkezi config yöneticisi"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.project_root = Path(__file__).resolve().parents[1]
        
        # .env dosyasını yükle
        env_path = self.project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        # Config dosyasını belirle
        if config_path is None:
            config_path = self.project_root / "config" / "config.yaml"
        else:
            config_path = Path(config_path)
        
        self.config_path = config_path
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Config dosyasını yükle ve environment variables ile birleştir"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config dosyası bulunamadı: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # Environment variables ile değiştir
        self._replace_env_vars(self._config)
    
    def _replace_env_vars(self, obj):
        """YAML'daki ${VAR_NAME} formatındaki environment variables'ı değiştir"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = self._replace_env_vars(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = self._replace_env_vars(item)
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]  # ${VAR_NAME} -> VAR_NAME
            return os.getenv(env_var)
        return obj
    
    def get(self, key_path: str, default=None):
        """
        Dot notation ile config değeri al
        Örnek: config.get("shops.ecommerce1.port")
        """
        keys = key_path.split(".")
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def get_shops(self) -> Dict[str, Any]:
        """Tüm shop bilgilerini al"""
        return self.get("shops", {})
    
    def get_categories(self) -> Dict[str, Any]:
        """Tüm kategori bilgilerini al"""
        return self.get("categories", {})
    
    def get_models(self) -> Dict[str, Any]:
        """Model konfigürasyonlarını al"""
        return self.get("models", {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """API konfigürasyonlarını al"""
        return self.get("api", {})
    
    def get_notification_config(self) -> Dict[str, Any]:
        """Bildirim konfigürasyonlarını al"""
        return self.get("notifications", {})
    
    def get_paths(self) -> Dict[str, Any]:
        """Path konfigürasyonlarını al"""
        return self.get("paths", {})
    
    def get_project_root(self) -> Path:
        """Proje kök dizinini al"""
        return self.project_root
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Relative path'i absolute path'e çevir"""
        return self.project_root / relative_path
    
    def get_shop_data_path(self, shop_name: str) -> Optional[Path]:
        """Belirli bir shop'un data path'ini al"""
        shop_config = self.get(f"shops.{shop_name}")
        if shop_config and "data_path" in shop_config:
            return self.get_absolute_path(shop_config["data_path"])
        return None
    
    def get_shop_image_path(self, shop_name: str) -> Optional[Path]:
        """Belirli bir shop'un image path'ini al"""
        shop_config = self.get(f"shops.{shop_name}")
        if shop_config and "image_path" in shop_config:
            return self.get_absolute_path(shop_config["image_path"])
        return None
    
    def get_category_names(self) -> list:
        """Tüm kategori isimlerini al"""
        return list(self.get_categories().keys())
    
    def is_valid_category(self, category: str) -> bool:
        """Kategori geçerli mi?"""
        return category in self.get_category_names()
    

    def get_shop(self, shop_name: str) -> Dict[str, Any]:
        """Tek bir shop döndürür (yoksa boş dict)."""
        return self.get(f"shops.{shop_name}", {}) or {}

    def get_category(self, category_name: str) -> Dict[str, Any]:
        """Tek bir kategori döndürür (yoksa boş dict)."""
        return self.get(f"categories.{category_name}", {}) or {}


# Global config instance
_config_instance = None

def get_config() -> ConfigLoader:
    """Global config instance'ını al"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader()
    return _config_instance

def reload_config():
    """Config'i yeniden yükle"""
    global _config_instance
    _config_instance = ConfigLoader()
    return _config_instance

def load_config() -> ConfigLoader:
    #pipeline
    return get_config()


