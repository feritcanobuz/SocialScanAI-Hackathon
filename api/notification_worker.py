# api/notification_worker.py
import os
import re
import json
import time
import sys
from pathlib import Path
from contextlib import suppress
from typing import Optional, Dict, Any
from collections import defaultdict
from twilio.rest import Client

# Proje kökü ve config
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# Config yükle
from config.config_loader import get_config
config = get_config()

# --- Paths from config ---
DUKKANS_DIR = config.get_absolute_path("dukkans")
STATE_ROOT = config.get_absolute_path("state")
STATE_ROOT.mkdir(exist_ok=True)
TRACKING_FILE = STATE_ROOT / "tracking.json"
B2B_NOTIFIED_FILE = STATE_ROOT / "b2b_notified.json"

# --- Configuration from config.yaml ---
api_config = config.get_api_config()
notification_config = config.get_notification_config()

CHECK_INTERVAL_SECONDS = api_config.get("notification_worker", {}).get("check_interval", 30)

# --- Twilio Configuration ---
twilio_config = notification_config.get("twilio", {})
TWILIO_ACCOUNT_SID = twilio_config.get("account_sid")
TWILIO_AUTH_TOKEN = twilio_config.get("auth_token")
TWILIO_WHATSAPP_FROM = twilio_config.get("whatsapp_from")

# --- B2B Configuration ---
b2b_config = notification_config.get("b2b", {})
B2B_SELLER_PHONE = b2b_config.get("seller_phone")

# B2B satıcı numaraları (tüm shoplar için aynı numara)
shops = config.get_shops()
B2B_SELLERS = {shop_name: B2B_SELLER_PHONE for shop_name in shops.keys()}

# --- Twilio Client ---
client = None
if all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM]):
    with suppress(Exception):
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("✅ Twilio Client hazır.")
else:
    print("⚠️ Twilio env eksik; mesaj gönderilmeyecek.")
    print(f"   ACCOUNT_SID: {'✓' if TWILIO_ACCOUNT_SID else '✗'}")
    print(f"   AUTH_TOKEN: {'✓' if TWILIO_AUTH_TOKEN else '✗'}")
    print(f"   WHATSAPP_FROM: {'✓' if TWILIO_WHATSAPP_FROM else '✗'}")

# --- Price Parser ---
_price_rx = re.compile(r"[^\d,\.]")

def parse_price(val) -> float:
    """Fiyat string'ini float'a çevir"""
    if val is None:
        raise ValueError("price is None")
    if isinstance(val, (int, float)):
        return float(val)
    s = _price_rx.sub("", str(val))
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and len(s.split(",")[-1]) in (1, 2):
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)

def load_product_from_shop(shop: str, product_id: str, category: Optional[str]) -> Optional[Dict[str, Any]]:
    """Belirli mağazadan ürün bilgisini yükle"""
    shop_data_path = config.get_shop_data_path(shop)
    if not shop_data_path:
        print(f"  ⚠️ Shop '{shop}' için data path bulunamadı")
        return None
    
    product_dir = shop_data_path / "product"
    if not product_dir.exists():
        print(f"  ⚠️ Product directory bulunamadı: {product_dir}")
        return None
    
    # Kategori belirtilmişse o kategori dosyasına bak
    if category:
        category_config = config.get(f"categories.{category}")
        if category_config and "product_file" in category_config:
            files = [product_dir / category_config["product_file"].split("/")[-1]]
        else:
            files = [product_dir / f"{category}.json"]
    else:
        files = list(product_dir.glob("*.json"))
    
    for fp in files:
        if not fp.exists():
            continue
        with suppress(Exception):
            items = json.loads(fp.read_text(encoding="utf-8"))
            for it in items:
                if it.get("id") == product_id:
                    it = dict(it)
                    it["dukkan"] = shop
                    return it
    return None

def read_tracking() -> list:
    """Takip dosyasını oku"""
    if not TRACKING_FILE.exists():
        return []
    for _ in range(3):
        try:
            return json.loads(TRACKING_FILE.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            time.sleep(0.1)
    return []

def write_tracking(data: list) -> None:
    """Takip dosyasına yaz"""
    tmp = TRACKING_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, TRACKING_FILE)

def read_b2b_notified() -> dict:
    """B2B bildirim geçmişini oku"""
    if not B2B_NOTIFIED_FILE.exists():
        return {}
    try:
        return json.loads(B2B_NOTIFIED_FILE.read_text(encoding="utf-8") or "{}")
    except:
        return {}

def write_b2b_notified(data: dict) -> None:
    """B2B bildirim geçmişine yaz"""
    tmp = B2B_NOTIFIED_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, B2B_NOTIFIED_FILE)

def send_notification(user: str, text: str) -> None:
    """WhatsApp bildirimi gönder"""
    if not client:
        print("  - Twilio pasif, mesaj atlanıyor.")
        return
    
    try:
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            body=text,
            to=user
        )
        print(f"  ✅ Bildirim gönderildi: {message.sid}")
    except Exception as e:
        print(f"  ❌ Bildirim gönderme hatası: {e}")

def check_b2b_opportunities() -> None:
    """B2B satıcı bildirimleri - takip talebi analizi"""
    print("📊 B2B fırsat analizi...")
    
    if not b2b_config.get("enabled", False):
        print("  - B2B bildirimleri devre dışı")
        return
    
    tracking_list = read_tracking()
    active_tracks = [t for t in tracking_list if t.get("is_active")]
    
    if not active_tracks:
        print("  - Aktif takip yok")
        return
    
    # Takipleri grupla: shop + product_id + track_type
    groups = defaultdict(list)
    for track in active_tracks:
        shop = track.get("shop")
        product_id = track.get("product_id")
        track_type = track.get("track_type")
        
        if shop and product_id and track_type:
            key = f"{shop}|{product_id}|{track_type}"
            groups[key].append(track)
    
    # B2B bildirim geçmişi
    notified = read_b2b_notified()
    updated_notified = False
    
    for group_key, tracks in groups.items():
        if len(tracks) < 2:  # En az 2 takip gerekli
            continue
            
        shop, product_id, track_type = group_key.split("|")
        
        # Bu grup için daha önce bildirim gönderilmiş mi?
        if group_key in notified:
            continue
        
        # Shop config'te var mı kontrol et
        if shop not in shops:
            print(f"  ⚠️ Bilinmeyen shop: {shop}")
            continue
            
        # Ürün bilgilerini al
        product = load_product_from_shop(shop, product_id, tracks[0].get("category"))
        if not product:
            print(f"  - {shop}/{product_id} ürünü bulunamadı")
            continue
            
        product_name = product.get("name", product_id)
        track_count = len(tracks)
        
        # Satıcı numarasını al
        seller_phone = B2B_SELLERS.get(shop)
        if not seller_phone:
            print(f"  ⚠️ {shop} için satıcı numarası bulunamadı")
            continue
        
        # B2B mesajı oluştur
        shop_display_name = shops[shop].get("name", shop)
        
        if track_type == "stock":
            # Stok takibi analizi
            sizes = [t.get("value") for t in tracks if t.get("value")]
            if sizes:
                size_info = f" ({', '.join(set(sizes))} numaraları)"
            else:
                size_info = ""
                
            message = (
                f"📦 STOK TALEBİ TESPİT EDİLDİ\n\n"
                f"{track_count} müşteri {shop_display_name} mağazanızda '{product_name}'{size_info} için stok takibi aktif.\n"
                f"Stok tamamlarsanız yüksek satış potansiyeli var!\n\n"
                f"🎯 Önerilen aksiyon: Stok güncellemesi"
            )
            
        elif track_type == "price":
            # Fiyat takibi analizi
            message = (
                f"💰 FİYAT DUYARLILIĞI ANALİZİ\n\n"
                f"{track_count} müşteri {shop_display_name} mağazanızda '{product_name}' ürününü fiyat değişimi için takip ediyor.\n"
                f"Kampanya düzenlerseniz satış artış potansiyeli yüksek!\n\n"
                f"🎯 Önerilen aksiyon: Promosyon kampanyası"
            )
        else:
            continue
            
        # B2B bildirimi gönder
        print(f"  📤 {shop_display_name} satıcısına B2B bildirimi: {track_count} {track_type} takibi")
        send_notification(seller_phone, message)
        
        # Bildirim geçmişine ekle
        notified[group_key] = {
            "timestamp": time.time(),
            "track_count": track_count,
            "product_name": product_name,
            "shop": shop
        }
        updated_notified = True
    
    if updated_notified:
        write_b2b_notified(notified)
        print("  ✅ B2B bildirim geçmişi güncellendi.")
    else:
        print("  - Yeni B2B bildirimi gerekmedi")

def check_for_updates_and_notify() -> None:
    """Müşteri takip kontrolü ve bildirimleri"""
    print(f"\n[{time.ctime()}] Takip kontrolü...")
    lst = read_tracking()
    if not lst:
        print("- Kayıt yok.")
        return

    active_count = len([t for t in lst if t.get("is_active")])
    print(f"- Toplam {len(lst)} kayıt, {active_count} aktif")

    updated = False
    for t in lst:
        if not t.get("is_active"):
            continue

        product_id = t.get("product_id")
        shop = t.get("shop")
        category = t.get("category")
        user = t.get("user_identifier")
        ttype = t.get("track_type")

        # Shop validation
        if shop not in shops:
            print(f"  ⚠️ Bilinmeyen shop: {shop}")
            continue

        # Category validation
        if not config.is_valid_category(category):
            print(f"  ⚠️ Geçersiz kategori: {category}")
            continue

        # Ürün bilgisini yükle
        prod = load_product_from_shop(shop, product_id, category)
        if not prod:
            print(f"  - {shop}/{product_id} bulunamadı.")
            continue

        shop_display_name = shops[shop].get("name", shop)
        product_name = prod.get("name", product_id)

        if ttype == "stock":
            tracked_size = t.get("value")
            stock_items = prod.get("stock") or []
            
            for s in stock_items:
                if s.get("size") == tracked_size and s.get("isAvailable"):
                    msg = (
                        "🎉 Aradığın Beden Bulundu! 🎉\n\n"
                        f"{shop_display_name} mağazasında takip ettiğiniz '{product_name}' ürününün "
                        f"{tracked_size} numarası stoğa girdi.\n\n"
                        "Bu fırsatı kaçırma!"
                    )
                    print(f"  📱 Stok bildirimi: {user} -> {product_name} ({tracked_size})")
                    send_notification(user, msg)
                    t["is_active"] = False
                    t["completed_at"] = time.time()
                    updated = True
                    break

        elif ttype == "price":
            try:
                initial_raw = t.get("value")
                current_raw = prod.get("price")

                initial = parse_price(initial_raw)
                current = parse_price(current_raw)

                print(f"  💸 {product_name} fiyat kontrolü: {initial:.2f}₺ → {current:.2f}₺")

                if current < initial:
                    discount_percent = ((initial - current) / initial) * 100
                    msg = (
                        "🎉 Fiyat Düştü! 🎉\n\n"
                        f"{shop_display_name} mağazasında takip ettiğiniz '{product_name}' "
                        f"ürününün fiyatı {initial:.1f}₺'den {current:.1f}₺'ye düştü! "
                        f"(%{discount_percent:.1f} indirim)\n\n"
                        "Bu fırsatı kaçırma!"
                    )
                    print(f"  📱 Fiyat bildirimi: {user} -> {product_name} ({discount_percent:.1f}% indirim)")
                    send_notification(user, msg)
                    t["is_active"] = False
                    t["completed_at"] = time.time()
                    updated = True
            except Exception as e:
                print(f"  ❌ Fiyat kıyas hatası: {e}")
                print(f"    - initial: {t.get('value')}, current: {prod.get('price')}")

    if updated:
        write_tracking(lst)
        print("- ✅ Takip dosyası güncellendi.")
    else:
        print("- Değişiklik yok.")

def main():
    """Ana worker döngüsü"""
    print("🚀 SocialScanAI Bildirim Servisi Başlatıldı (B2B Özellikli)")
    print(f"📧 Twilio durumu: {'Aktif' if client else 'Pasif'}")
    print(f"🏪 Takip edilen mağazalar: {', '.join(shops.keys())}")
    print(f"📂 Kategoriler: {', '.join(config.get_category_names())}")
    print(f"⏱️ Kontrol aralığı: {CHECK_INTERVAL_SECONDS} saniye")
    print(f"📍 State dizini: {STATE_ROOT}")
    print("-" * 50)
    
    while True:
        try:
            check_for_updates_and_notify()  # Müşteri bildirimleri
            check_b2b_opportunities()       # B2B satıcı bildirimleri
        except KeyboardInterrupt:
            print("\n Servis durduruldu.")
            break
        except Exception as e:
            print(f" Döngü hatası: {e}")
            import traceback
            traceback.print_exc()
        
        print(f" {CHECK_INTERVAL_SECONDS} saniye bekleniyor...")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()