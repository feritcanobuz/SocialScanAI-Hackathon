# tools/data_tool/ops/calc_metrics.py

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

# === PATH bootstrap ===
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
sys.path.append(str(PROJECT_ROOT))

from config.config_loader import get_config
from tools.data_tool.text_utils import load_json, save_json_atomic


def safe_div(x: float, y: float) -> float:
    try:
        return x / y if y != 0 else 0.0
    except Exception:
        return 0.0


def safe_float(value, default=0.0):
    """Güvenli float dönüşümü - None, boş string vs. için default döner"""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def normalize_by_keys(raw: Dict[str, float]) -> Dict[str, float]:
    """
    raw: {pid -> value}
    return: {pid -> normalized 0..1}
    """
    if not raw:
        return {}
    vals = list(raw.values())
    mn, mx = min(vals), max(vals)
    if mn == mx:
        return {k: 0.5 for k in raw}  # hepsi eşitse 0.5 sabitle
    return {k: (v - mn) / (mx - mn) for k, v in raw.items()}


def main():
    print(" PriceLens hesaplaması başlatılıyor...")
    print(" Formül: 40% Sentiment + 30% Rating + 30% Value (yoksa: 50/50)")
    print("=" * 60)

    cfg = get_config()
    shops = cfg.get_shops()           # dict
    categories = cfg.get_categories() # dict

    for shop_name, shop_info in shops.items():
        print(f"\n {shop_name} işleniyor...")
        data_dir = cfg.get_shop_data_path(shop_name)
        if not data_dir:
            print(f"Data path yok: {shop_name}")
            continue

        for cat_key, cat_info in categories.items():
            product_path = data_dir / cat_info["product_file"]
            comment_path = data_dir / cat_info["comments_file"]

            if not product_path.exists() or not comment_path.exists():
                print(f" {shop_name}/{cat_key} eksik (product/comments), atlanıyor.")
                continue

            products = load_json(product_path)
            comments_data = load_json(comment_path)

            if not isinstance(products, list) or not isinstance(comments_data, dict):
                print(f"{shop_name}/{cat_key} veri formatı hatalı, atlanıyor.")
                continue

            print(f" {cat_key.upper()}: {len(products)} ürün işleniyor...")

            value_scores_raw: Dict[str, float] = {}
            for p in products:
                try:
                    pid = p.get("id")
                    price = safe_float(p.get("price", 0))
                    rating = safe_float(p.get("rating", 0))
                    
                    if pid is None:
                        continue

                    if price > 0 and rating > 0:
                        # Yüksek rating & düşük fiyat = yüksek değer
                        val_score = (rating * 1000.0) / price
                    else:
                        val_score = 0.0

                    value_scores_raw[pid] = val_score
                except Exception as e:
                    pid = p.get("id", "Unknown")
                    print(f" Value score hatası {pid}: {e}")
                    if pid:
                        value_scores_raw[pid] = 0.0

            # Normalize → pid→0..1
            value_scores_norm = normalize_by_keys(value_scores_raw)

            # max_reviews hesapla (confidence için)
            if products:
                max_reviews = max(len(comments_data.get(p.get("id", ""), [])) for p in products)
            else:
                max_reviews = 0

            updated = False
            products_with_sentiment = 0
            products_without_sentiment = 0

            for p in products:
                pid = p.get("id")
                if not pid:
                    continue

                price = safe_float(p.get("price", 0))
                rating = safe_float(p.get("rating", 0))
                normalized_rating = rating / 5.0 if rating > 0 else 0.0  # 0..1

                comments: List[Dict[str, Any]] = comments_data.get(pid, [])
                

                if not comments or len(comments) == 0:
                    print(f"{pid}: Yorum yok, atlanıyor.")
                    continue
                

                valid_comments = []
                for c in comments:
                    if isinstance(c, dict) and c: 
                        valid_comments.append(c)
                
                if not valid_comments:
                    print(f" {pid}: Geçerli yorum yok, atlanıyor.")
                    continue
                
                num_reviews = len(valid_comments)
                if max_reviews > 0:
                    confidence = max(0.2, num_reviews / max_reviews)  # min %20
                else:
                    confidence = 0.2


                sentiments = []
                for c in valid_comments:
                    polarity = c.get("polarity")
                    intensity = c.get("intensity") 
                    density = c.get("density")
                    
                    # Hepsi geçerli sayı mı?
                    if (isinstance(polarity, (int, float)) and polarity is not None and
                        isinstance(intensity, (int, float)) and intensity is not None and
                        isinstance(density, (int, float)) and density is not None):
                        sentiments.append(c)

                if sentiments:
                    avg_sentiment = sum(
                        (safe_float(c["polarity"]) + safe_float(c["intensity"]) + safe_float(c["density"])) / 3.0
                        for c in sentiments
                    ) / len(sentiments)
                    products_with_sentiment += 1
                else:
                    avg_sentiment = 0.0
                    products_without_sentiment += 1

                # Value (0..1)
                value_score_norm = safe_float(value_scores_norm.get(pid, 0.0))

                # PriceLens skoru
                if sentiments:
                    pricelens = 0.40 * avg_sentiment + 0.30 * normalized_rating + 0.30 * value_score_norm
                else:
                    pricelens = 0.50 * normalized_rating + 0.50 * value_score_norm

                # Güven katsayısı uygula
                pricelens = round(pricelens * confidence, 4)

                # Yaz
                p["pricelens_score"] = pricelens
                p["pricelens_metadata"] = {
                    "avg_sentiment": round(avg_sentiment, 3),
                    "normalized_rating": round(normalized_rating, 3),
                    "value_score_norm": round(value_score_norm, 3),
                    "confidence": round(confidence, 3),
                    "comment_count": num_reviews,
                    "has_sentiment": bool(sentiments),
                }
                updated = True

            if updated:
                save_json_atomic(product_path, products)
                print(f"{shop_name}/{cat_key}.json güncellendi")
                print(f"Sentiment olan: {products_with_sentiment}, olmayan: {products_without_sentiment}")

    print("\n" + "=" * 60)
    print("PriceLens hesaplaması tamamlandı!")
    print("\nFormül Özeti:")
    print("Sentiment varsa: 40% Sentiment + 30% Rating + 30% Value")
    print("Sentiment yoksa: 50% Rating + 50% Value")
    print(" + Güven katsayısı (min %20, yorum sayısı bazlı)")
    print("\n Arama sistemini test edebilirsin!")
    

if __name__ == "__main__":
    main()