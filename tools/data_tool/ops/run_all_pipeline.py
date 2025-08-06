# tools/data_tool/ops/run_all_pipeline.py

import os
import sys
import json
import hashlib
from pathlib import Path
from subprocess import run

# tools/data_tool/ops/ içindeyiz
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from config.config_loader import load_config


config = load_config()
BASE_DIR = config.get_project_root()
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

PRODUCT_STATE = STATE_DIR / "product_hashes.json"
COMMENT_STATE = STATE_DIR / "comment_hashes.json"

# Config yükle
try:
    config = load_config()
    BASE_DIR = config.get_project_root()
    print(f"Config yüklendi. Proje dizini: {BASE_DIR}")
except Exception as e:
    print(f"Config yüklenirken hata: {e}")
    sys.exit(1)

# Dizinleri oluştur 
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(exist_ok=True)

PRODUCT_STATE = STATE_DIR / "product_hashes.json"
COMMENT_STATE = STATE_DIR / "comment_hashes.json"

#Yardımcı Fonksiyonlar 
def calc_hash(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def read_json_safe(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"JSON okuma hatası {path}: {e}")
        return {}

def save_json(path, data):
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"JSON kaydetme hatası {path}: {e}")

def get_changed_files(shops, categories, state_path, file_key):
    prev_hashes = read_json_safe(state_path)
    curr_hashes = {}
    changed_files = []

    for shop_name, shop_cfg in shops.items():
        data_path = config.get_shop_data_path(shop_name)
        if not data_path:
            print(f"{shop_name} için data_path bulunamadı")
            continue
        
        if not data_path.exists():
            print(f"Dizin mevcut değil: {data_path}")
            continue

        for category, cat_cfg in categories.items():
            category_file = cat_cfg.get(file_key)
            if not category_file:
                continue

            path = data_path / category_file
            if not path.exists():
                print(f"Dosya mevcut değil: {path}")
                continue

            try:
                content = path.read_text(encoding="utf-8")
                h = calc_hash(content)
                curr_hashes[str(path)] = h
                
                if prev_hashes.get(str(path)) != h:
                    changed_files.append(path)
                    print(f"Değişiklik tespit edildi: {path}")
            except Exception as e:
                print(f"Dosya okuma hatası {path}: {e}")

    save_json(state_path, curr_hashes)
    return changed_files

def run_script(script_path):
    if not script_path.exists():
        print(f"Script bulunamadı: {script_path}")
        return False

    relative_path = script_path.relative_to(BASE_DIR)
    module_path = str(relative_path).replace("/", ".").replace("\\", ".").replace(".py", "")

    print(f"Çalıştırılıyor: {module_path}")
    try:
        child_env = os.environ.copy()

        child_env["PYTHONIOENCODING"] = "utf-8"

        result = run(
            [sys.executable, "-m", module_path],
            capture_output=True,
            text=True,
            encoding="utf-8",   
            cwd=str(BASE_DIR),
            env=child_env
        )
        if result.returncode != 0:
            print(f"Script hatası: {result.stderr}")
            return False
        else:
            print(f"Tamamlandı: {script_path.name}")
            return True
    except Exception as e:
        print(f"Çalıştırma hatası: {e}")
        return False


def check_required_scripts():
    """Gerekli scriptlerin varlığını kontrol et"""
    scripts = [
        BASE_DIR / "tools" / "data_tool" / "ops" / "gen_gemini.py",
        BASE_DIR / "tools" / "data_tool" / "ops" / "embed_clip.py",
        BASE_DIR / "tools" / "data_tool" / "ops" / "embed_text_clip.py", 
        BASE_DIR / "tools" / "data_tool" / "ops" / "embed_text_st.py",
        BASE_DIR / "tools" / "data_tool" / "ops" / "embed_combined.py",
        BASE_DIR / "tools" / "data_tool" / "ops" / "sentiment_pipeline.py",
        BASE_DIR / "tools" / "data_tool" / "ops" / "calc_metrics.py",
        BASE_DIR / "tools" / "data_tool" / "ops" / "rating_updater.py"
    ]
    
    missing_scripts = []
    for script in scripts:
        if not script.exists():
            missing_scripts.append(script)
    
    if missing_scripts:
        print("❌ Eksik scriptler:")
        for script in missing_scripts:
            print(f"   - {script}")
        return False
    
    print("Tüm gerekli scriptler mevcut")
    return True

# === Ana Fonksiyon ===
def main():
    print("=" * 50)
    print("SocialScanAI Pipeline Başlatılıyor...")
    print("=" * 50)
    
    # Script kontrolü
    if not check_required_scripts():
        print("Eksik scriptler nedeniyle pipeline durduruluyor")
        return
    
    # Config kontrolü
    shops = config.get_shops()
    categories = config.get_categories()
    
    if not shops:
        print("Hiç shop tanımlanmamış!")
        return
    
    if not categories:
        print("Hiç kategori tanımlanmamış!")
        return
    
    print(f"📊 Toplam {len(shops)} shop, {len(categories)} kategori kontrol ediliyor...")

    print("\nÜrün dosyaları kontrol ediliyor...")
    changed_products = get_changed_files(shops, categories, PRODUCT_STATE, "product_file")
    
    if changed_products:
        print(f"Yeni/Güncellenmiş Ürün: {len(changed_products)} dosya")
        

        scripts_to_run = [
            BASE_DIR / "tools" / "data_tool" / "ops" / "gen_gemini.py",
            BASE_DIR / "tools" / "data_tool" / "ops" / "embed_clip.py",
            BASE_DIR / "tools" / "data_tool" / "ops" / "embed_text_clip.py",
            BASE_DIR / "tools" / "data_tool" / "ops" / "embed_text_st.py", 
            BASE_DIR / "tools" / "data_tool" / "ops" / "embed_combined.py"
        ]
        
        for script in scripts_to_run:
            if not run_script(script):
                print(f"Pipeline durduruluyor - {script.name} hatası")
                return
    else:
        print("Ürün dosyalarında değişiklik yok")

    # Yorum dosyaları kontrolü  
    print("\nYorum dosyaları kontrol ediliyor...")
    changed_comments = get_changed_files(shops, categories, COMMENT_STATE, "comments_file")
    
    if changed_comments:
        print(f"Yeni/Güncellenmiş Yorum: {len(changed_comments)} dosya")
        
        # Yorum pipeline'ı
        scripts_to_run = [
            BASE_DIR / "tools" / "data_tool" / "ops" / "sentiment_pipeline.py",
            BASE_DIR / "tools" / "data_tool" / "ops" / "calc_metrics.py",
            BASE_DIR / "tools" / "data_tool" / "ops" / "rating_updater.py"
        ]
        
        for script in scripts_to_run:
            if not run_script(script):
                print(f"Pipeline durduruluyor - {script.name} hatası")
                return
    else:
        print("Yorum dosyalarında değişiklik yok")
    
    print("\n" + "=" * 50)
    print("Pipeline tamamlandı!")
    print("=" * 50)

if __name__ == "__main__":
    main()