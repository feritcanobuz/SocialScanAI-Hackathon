# api/main.py
import os
import sys
import json
import uuid
import time
import datetime
import traceback
import logging
from pathlib import Path
from typing import Optional, Literal
from contextlib import suppress

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Proje kökü ve config
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

# Config yükle
from config.config_loader import get_config
config = get_config()

# Logging
log_level = config.get("environment.LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger(__name__)

# --- Paths from config ---
DATA_ROOT = config.get_absolute_path(config.get("paths.root"))
DUKKANS_DIR = DATA_ROOT / "dukkans"
STATE_ROOT = config.get_absolute_path("state")
STATE_ROOT.mkdir(exist_ok=True)

# --- Import search modules ---
try:
    from tools.data_tool.search.search_by_text import search_with_rrf_pricelens
    from tools.data_tool.search.search_by_image import search_image_with_rrf_pricelens
    logger.info("✅ Arama modülleri import edildi.")
except ImportError as e:
    logger.error(f"❌ Arama modülleri import edilemedi: {e}")
    sys.exit(1)

# --- App Configuration ---
api_config = config.get_api_config()
app = FastAPI(
    title="SocialScanAI API",
    description="Hibrit AI Ürün Arama ve Takip Sistemi",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=str(DUKKANS_DIR)), name="static")

# --- Constants from config ---
KATEGORILER = config.get_category_names()
TRACKING_FILE = STATE_ROOT / "tracking.json"

def _validate_category(cat: str):
    """Kategori geçerliliğini kontrol et"""
    if not config.is_valid_category(cat):
        valid_categories = ", ".join(KATEGORILER)
        raise HTTPException(
            status_code=400, 
            detail=f"Geçersiz kategori: {cat}. Geçerli kategoriler: {valid_categories}"
        )

def _load_product_from_shop(shop: str, product_id: str, category: Optional[str]) -> Optional[dict]:
    """Belirli mağazadan product_id'yi canlı JSON'dan getirir."""
    shop_data_path = config.get_shop_data_path(shop)
    if not shop_data_path:
        logger.warning(f"Shop '{shop}' için data path bulunamadı")
        return None
    
    product_dir = shop_data_path / "product"
    if not product_dir.exists():
        logger.warning(f"Product directory bulunamadı: {product_dir}")
        return None
    
    # Kategori belirtilmişse sadece o dosyaya bak, yoksa tüm dosyalara bak
    if category:
        category_config = config.get(f"categories.{category}")
        if category_config and "product_file" in category_config:
            files = [product_dir / category_config["product_file"].split("/")[-1]]
        else:
            files = [product_dir / f"{category}.json"]
    else:
        files = list(product_dir.glob("*.json"))
    
    for p in files:
        if not p.exists():
            continue
        with suppress(Exception):
            items = json.loads(p.read_text(encoding="utf-8"))
            for it in items:
                if it.get("id") == product_id:
                    it = dict(it)
                    it["dukkan"] = shop
                    return it
    return None

def _atomic_write_json(path: Path, data: list):
    """Atomic JSON write işlemi"""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)

def _safe_read_json_list(path: Path) -> list:
    """Güvenli JSON okuma"""
    if not path.exists():
        return []
    for _ in range(3):
        try:
            return json.loads(path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            time.sleep(0.1)
    return []

# --- Pydantic Models ---
class TextSearchRequest(BaseModel):
    query: str
    category: str
    top_n: Optional[int] = 5

class TrackRequest(BaseModel):
    user_identifier: str
    product_id: str
    track_type: Literal['stock', 'price']
    value: Optional[str] = None      # beden veya başlangıç fiyatı
    shop: str                        # pricelens kazanan mağaza
    category: str                    # Config'ten alınacak valid kategoriler

# --- Root Endpoint ---
@app.get("/")
async def root():
    """API ana endpoint"""
    return {
        "message": "SocialScanAI API çalışıyor!", 
        "version": app.version,
        "available_categories": KATEGORILER,
        "available_shops": list(config.get_shops().keys())
    }

# --- Result Formatter ---
def format_search_results(final_results, product_variants, *, category: str):
    """Search sonuçlarını formatla"""
    if not product_variants:
        return {"best_offer": {}, "other_offers": []}

    best = product_variants[0]
    best_pid = (best.get("item_data") or {}).get("id")
    best_shop = best.get("dukkan")

    live_best = _load_product_from_shop(best_shop, best_pid, category) or (best.get("item_data") or {})

    # Image URL oluştur
    image_url = None
    if live_best.get("images"):
        shop_config = config.get(f"shops.{best_shop}")
        if shop_config:
            # Static mount path'ini kullan
            image_url = f"/static/{best_shop}/backend/data/{live_best['images'][0]}"

    best_offer = {
        "product_id": live_best.get("id"),
        "name": live_best.get("name"),
        "brand": live_best.get("brand"),
        "shop": best_shop,
        "price": best.get("price"),
        "rating": best.get("rating"),
        "pricelens_score": round(best.get("pricelens_score", 0.0), 4),
        "image_url": image_url,
        "stock_details": live_best.get("stock", []),
    }

    other_offers = [{
        "shop": v.get("dukkan"),
        "name": v.get("name"),
        "price": v.get("price"),
        "rating": v.get("rating"),
        "pricelens_score": round(v.get("pricelens_score", 0.0), 4),
    } for v in product_variants[1:]]

    return {"best_offer": best_offer, "other_offers": other_offers}

# --- Search Endpoints ---
@app.post("/api/search/text")
async def text_search(request: TextSearchRequest):
    """Text tabanlı ürün arama"""
    _validate_category(request.category)
    start_time = time.time()
    
    logger.info(f"🔍 Text search: '{request.query}' in category '{request.category}'")
    
    try:
        final_results, product_variants = search_with_rrf_pricelens(
            request.query, request.category, request.top_n, api_mode=True
        )
        formatted = format_search_results(final_results, product_variants, category=request.category)
        
        processing_time = round(time.time() - start_time, 3)
        logger.info(f"✅ Text search completed in {processing_time}s")
        
        return {
            "success": True,
            "best_offer": formatted["best_offer"],
            "other_offers": formatted["other_offers"],
            "processing_time": processing_time
        }
    except Exception as e:
        logger.error(f"❌ Metin arama hatası: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Sunucu hatası oluştu.")

@app.post("/api/search/image")
async def image_search(category: str = Form(...), image: UploadFile = File(...), top_n: int = Form(5)):
    """Image tabanlı ürün arama"""
    _validate_category(category)
    
    import tempfile
    start_time = time.time()
    logger.info(f"🖼️ Image search: {image.filename} in category '{category}'")

    temp_image_path = None
    try:
        # Geçici dosya oluştur
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(await image.read())
            temp_image_path = tmp.name

        final_results, product_variants = search_image_with_rrf_pricelens(
            temp_image_path, category, top_n, api_mode=True
        )
        formatted = format_search_results(final_results, product_variants, category=category)
        
        processing_time = round(time.time() - start_time, 3)
        logger.info(f"✅ Image search completed in {processing_time}s")
        
        return {
            "success": True,
            "best_offer": formatted["best_offer"],
            "other_offers": formatted["other_offers"],
            "processing_time": processing_time
        }
    except Exception as e:
        logger.error(f"❌ Görsel arama hatası: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Sunucu hatası oluştu.")
    finally:
        # Geçici dosyayı temizle
        with suppress(Exception):
            if temp_image_path and os.path.exists(temp_image_path):
                os.unlink(temp_image_path)

@app.post("/api/track")
async def track_product(request: TrackRequest):
    """Ürün takip isteği"""
    _validate_category(request.category)
    logger.info(f"📝 Track request: user={request.user_identifier}, product={request.product_id}, shop={request.shop}")

    # Telefon normalizasyonu
    raw_digits = ''.join(filter(str.isdigit, str(request.user_identifier)))
    if len(raw_digits) == 10:
        formatted_phone = f"whatsapp:+90{raw_digits}"
    elif len(raw_digits) == 11 and raw_digits.startswith('0'):
        formatted_phone = f"whatsapp:+90{raw_digits[1:]}"
    else:
        raise HTTPException(status_code=400, detail="Geçersiz telefon numarası formatı.")

    # Yeni takip kaydı
    new_track_entry = {
        "track_id": str(uuid.uuid4()),
        "user_identifier": formatted_phone,
        "product_id": request.product_id,
        "track_type": request.track_type,
        "value": request.value,
        "shop": request.shop,
        "category": request.category,
        "created_at": datetime.datetime.now().isoformat(),
        "is_active": True
    }

    try:
        tracking_list = _safe_read_json_list(TRACKING_FILE)

        # Aynı kayıt varsa ekleme (opsiyonel)
        for t in tracking_list:
            if (t.get("user_identifier") == new_track_entry["user_identifier"] and
                t.get("product_id") == new_track_entry["product_id"] and
                t.get("track_type") == new_track_entry["track_type"] and
                t.get("value") == new_track_entry["value"] and
                t.get("shop") == new_track_entry["shop"]):
                return {"success": True, "message": "Takip zaten aktif."}

        tracking_list.append(new_track_entry)
        _atomic_write_json(TRACKING_FILE, tracking_list)
        
        logger.info(f"✅ Track added: {new_track_entry['track_id']}")
        return {"success": True, "message": "Ürün takibe alındı."}
    except Exception as e:
        logger.error(f"❌ Takip dosyasına yazma hatası: {e}")
        raise HTTPException(status_code=500, detail="Takip isteği kaydedilemedi.")

# --- Health Check ---
@app.get("/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "config_loaded": True,
        "categories": len(KATEGORILER),
        "shops": len(config.get_shops())
    }

# --- Run Server ---
if __name__ == "__main__":
    # Config'ten port al
    port = api_config.get("main_port", 8000)
    host = api_config.get("host", "0.0.0.0")
    reload = api_config.get("reload", True)
    
    logger.info(f"🚀 Starting SocialScanAI API on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=reload)