# backend/main.py
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, json, glob
from typing import Dict, Any

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


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _comment_path(category: str) -> str:
    return os.path.join(BASE_DIR, "comments", f"{category}_comments.json")


def _list_categories() -> list:
    """data/comments altındaki *_comments.json dosyalarından kategori isimlerini çıkar."""
    paths = glob.glob(os.path.join(BASE_DIR, "comments", "*_comments.json"))
    cats = []
    for p in paths:
        base = os.path.basename(p)
        cat = base.replace("_comments.json", "")
        cats.append(cat)
    return cats


def _summarize_reviews(items: list) -> Dict[str, Any]:
    """
    items: [{user, rating, text?}, ...]
    returns: {"avg": float, "total": int, "counts": {"1":n,..."5":m}}
    """
    counts = {str(i): 0 for i in range(1, 6)}
    total = 0
    star_sum = 0.0
    for it in items or []:
        try:
            r = float(it.get("rating", 0))
        except Exception:
            r = 0.0
        if 1 <= r <= 5:
            key = str(int(round(r)))
            counts[key] += 1
            total += 1
            star_sum += r
    avg = round(star_sum / total, 2) if total else 0.0
    return {"avg": avg, "total": total, "counts": counts}


def _build_category_summary(category: str) -> Dict[str, Any]:
    """Bir kategori içindeki tüm ürünlerin özetini döndür."""
    path = _comment_path(category)
    if not os.path.exists(path):
        return {}
    cm = load_json(path)  # {product_id: [ ... ]}
    out = {}
    for pid, reviews in cm.items():
        out[pid] = _summarize_reviews(reviews)
    return out


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
            p["_cat"] = category  # Tutarlılık için _cat anahtarını burada da ekleyelim
            return p
    return JSONResponse(content={"error": "Ürün bulunamadı"}, status_code=404)


# Yorumları kategori bazında ver
@app.get("/comments/{category}")
def get_comments(category: str):
    filepath = _comment_path(category)
    if not os.path.exists(filepath):
        return JSONResponse(content={"error": "Yorum bulunamadı"}, status_code=404)
    return load_json(filepath)


# ---------- Rating Summary ENDPOINT'leri ----------
@app.get("/rating-summary")
def rating_summary(flat: bool = Query(False)):
    """
    flat=false -> {"ayakkabi": {"ayk_01": {...}, ...}, "tshirt": {...}, ...}
    flat=true  -> {"ayk_01": {...}, "ayk_02": {...}, "tsh_01": {...}, ...}
    """
    cats = _list_categories()
    nested = {cat: _build_category_summary(cat) for cat in cats}
    if not flat:
        return nested
    flat_map = {}
    for cat, mp in nested.items():
        flat_map.update(mp)
    return flat_map


@app.get("/rating-summary/{category}")
def rating_summary_by_category(category: str):
    path = _comment_path(category)
    if not os.path.exists(path):
        return JSONResponse(content={"error": "Kategori bulunamadı"}, status_code=404)
    return _build_category_summary(category)


@app.get("/rating-summary/{category}/{product_id}")
def rating_summary_by_product(category: str, product_id: str):
    path = _comment_path(category)
    if not os.path.exists(path):
        return JSONResponse(content={"error": "Kategori bulunamadı"}, status_code=404)
    cm = load_json(path)
    if product_id not in cm:
        return JSONResponse(content={"error": "Ürün bulunamadı"}, status_code=404)
    return _summarize_reviews(cm[product_id])
