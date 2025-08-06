# backend/main.py  (ecommerce1)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, json, glob

app = FastAPI()

# Geliştirme için CORS serbest
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = "data"

# /images/... -> data/images/... klasörünü serve eder
app.mount("/images", StaticFiles(directory=os.path.join(BASE_DIR, "images")), name="images")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/")
def root():
    return {"message": "SocialScan AI backend API çalışıyor."}

# Tek kategori ürünleri
@app.get("/products/{category}")
def get_products(category: str):
    filepath = os.path.join(BASE_DIR, "product", f"{category}.json")
    if not os.path.exists(filepath):
        return JSONResponse(content={"error": "Kategori bulunamadı"}, status_code=404)
    return load_json(filepath)

# Tüm kategorileri birleştir
@app.get("/products")
def get_all_products():
    product_dir = os.path.join(BASE_DIR, "product")
    all_products = []
    for path in glob.glob(os.path.join(product_dir, "*.json")):
        cat_key = os.path.splitext(os.path.basename(path))[0]  # ayakkabi, tshirt...
        items = load_json(path)
        for p in items:
            p["_cat"] = cat_key  # ürün hangi dosyadan geldi (detayda lazım)
        all_products.extend(items)
    return all_products

@app.get("/product/{category}/{product_id}")
def get_single_product(category: str, product_id: str):
    filepath = os.path.join(BASE_DIR, "product", f"{category}.json")
    if not os.path.exists(filepath):
        return JSONResponse(content={"error": "Kategori bulunamadı"}, status_code=404)
    
    items = load_json(filepath)
    for p in items:
        if p.get("id") == product_id:
            p["_cat"] = category # Tutarlılık için _cat anahtarını burada da ekleyelim
            return p
    return JSONResponse(content={"error": "Ürün bulunamadı"}, status_code=404)

# Yorumları kategori bazında ver
@app.get("/comments/{category}")
def get_comments(category: str):
    filepath = os.path.join(BASE_DIR, "comments", f"{category}_comments.json")
    if not os.path.exists(filepath):
        return JSONResponse(content={"error": "Yorum bulunamadı"}, status_code=404)
    return load_json(filepath)

# =========================
# RATING ÖZET ENDPOINT'LERİ
# =========================

def _compute_stats(entries):
    """entries: [{user, rating, text?}, ...]"""
    counts = {1:0, 2:0, 3:0, 4:0, 5:0}
    total = 0
    s = 0.0
    for c in entries or []:
        r = c.get("rating", None)
        try:
            r = float(r)
        except (TypeError, ValueError):
            continue
        if 1 <= r <= 5:
            r_int = int(round(r))
            counts[r_int] = counts.get(r_int, 0) + 1
            total += 1
            s += r
    avg = (s / total) if total else 0.0
    # avg'i çok hassas tutup frontend'de yuvarlayacağız
    return {"avg": avg, "total": total, "counts": counts}

def _load_comments_for_category(category: str):
    path = os.path.join(BASE_DIR, "comments", f"{category}_comments.json")
    if not os.path.exists(path):
        return {}
    return load_json(path)

def _build_summary_for_category(category: str):
    data = _load_comments_for_category(category)  # {product_id: [entries]}
    summary = {}
    for pid, entries in (data or {}).items():
        summary[pid] = _compute_stats(entries)
    return summary

def _detect_categories_from_comments():
    """comments klasöründeki *_comments.json dosyalarından kategori adlarını çıkarır."""
    comment_dir = os.path.join(BASE_DIR, "comments")
    cats = []
    for path in glob.glob(os.path.join(comment_dir, "*_comments.json")):
        name = os.path.basename(path)
        if name.endswith("_comments.json"):
            cats.append(name.replace("_comments.json", ""))
    return cats

@app.get("/rating-summary")
def rating_summary(flat: bool = False):
    """
    Tüm kategoriler için özet.
    flat=false -> {ayakkabi:{id:{...}}, tshirt:{...}, ...}
    flat=true  -> {id:{...}} (id çakışması yoksa pratik)
    """
    result = {}
    for cat in _detect_categories_from_comments():
        result[cat] = _build_summary_for_category(cat)
    if flat:
        flat_map = {}
        for m in result.values():
            flat_map.update(m)
        return flat_map
    return result

@app.get("/rating-summary/{category}")
def rating_summary_by_cat(category: str):
    return _build_summary_for_category(category)

@app.get("/rating-summary/{category}/{product_id}")
def rating_summary_for_item(category: str, product_id: str):
    m = _build_summary_for_category(category)
    stats = m.get(product_id)
    if not stats:
        return JSONResponse(content={"error": "Ürün için rating bulunamadı"}, status_code=404)
    return stats
