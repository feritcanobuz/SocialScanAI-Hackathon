# backend/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, json, glob
from typing import Dict, List, Any

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


# -------------------- Helpers --------------------
def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def comments_file(category: str) -> str:
    return os.path.join(BASE_DIR, "comments", f"{category}_comments.json")

def calc_stats(arr: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bir ürün yorum listesinden ortalama ve dağılımı hesapla."""
    counts = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    total = 0
    s = 0.0
    for c in arr or []:
        try:
            r = float(c.get("rating", 0))
        except Exception:
            r = 0
        if 1 <= r <= 5:
            total += 1
            s += r
            key = str(int(round(r)))
            if key in counts:
                counts[key] += 1
    avg = (s / total) if total else 0.0
    return {"avg": avg, "total": total, "counts": counts}


# -------------------- API --------------------
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
    filepath = comments_file(category)
    if not os.path.exists(filepath):
        return JSONResponse(content={"error": "Yorum bulunamadı"}, status_code=404)
    return load_json(filepath)


# -------------------- Rating Summary (yeni) --------------------
# 1) Tüm kategoriler için özet
#    /rating-summary                -> { "ayakkabi": { "ayk_01": {...}, ... }, "tshirt": { ... }, ... }
#    /rating-summary?flat=true      -> { "ayk_01": {...}, "tsh_02": {...}, ... }  (liste sayfası için pratik)
@app.get("/rating-summary")
def rating_summary(flat: bool = False):
    comments_dir = os.path.join(BASE_DIR, "comments")
    if not os.path.isdir(comments_dir):
        return {}

    nested: Dict[str, Dict[str, Any]] = {}
    flat_map: Dict[str, Any] = {}

    for path in glob.glob(os.path.join(comments_dir, "*_comments.json")):
        cat = os.path.basename(path).replace("_comments.json", "")
        try:
            by_id = load_json(path)  # { product_id: [ {user, rating, text}, ... ] }
        except Exception:
            by_id = {}

        nested[cat] = {}
        for pid, arr in by_id.items():
            stats = calc_stats(arr)
            nested[cat][pid] = stats
            flat_map[pid] = stats

    return flat_map if flat else nested

# 2) Tek kategori özeti
@app.get("/rating-summary/{category}")
def rating_summary_category(category: str):
    path = comments_file(category)
    if not os.path.exists(path):
        return JSONResponse(content={"error": "Kategori bulunamadı"}, status_code=404)
    by_id = load_json(path)
    return {pid: calc_stats(arr) for pid, arr in (by_id or {}).items()}

# 3) Tek ürün özeti
@app.get("/rating-summary/{category}/{product_id}")
def rating_summary_product(category: str, product_id: str):
    path = comments_file(category)
    if not os.path.exists(path):
        return JSONResponse(content={"error": "Kategori bulunamadı"}, status_code=404)
    by_id = load_json(path)
    if product_id not in by_id:
        return JSONResponse(content={"error": "Ürün yorumu bulunamadı"}, status_code=404)
    return calc_stats(by_id[product_id])
