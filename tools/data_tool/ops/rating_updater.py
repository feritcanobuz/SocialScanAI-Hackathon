# tools/data_tool/ops/rating_updater.py

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

# Proje kökü import yolu
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
sys.path.append(str(PROJECT_ROOT))

from config.config_loader import get_config
from tools.data_tool.text_utils import load_json, save_json_atomic


def calculate_average_rating(comments: List[Dict]) -> float:
    """Yorum listesinden ortalama rating (0 yok sayılır)."""
    if not comments:
        return 0.0

    vals: List[float] = []
    for c in comments:
        r = c.get("rating")
        if isinstance(r, (int, float)) and r > 0:
            vals.append(float(r))

    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 2)


def get_rating_stats(comments: List[Dict]) -> Dict[str, Any]:
    """Min/Max/Count ve listeyi döndürür; boşsa 0'lar."""
    if not comments:
        return {"average": 0.0, "count": 0, "ratings": []}

    vals: List[float] = []
    for c in comments:
        r = c.get("rating")
        if isinstance(r, (int, float)) and r > 0:
            vals.append(float(r))

    if not vals:
        return {"average": 0.0, "count": 0, "ratings": []}

    return {
        "average": round(sum(vals) / len(vals), 2),
        "count": len(vals),
        "ratings": vals,
        "min": min(vals),
        "max": max(vals),
    }


def main():
    cfg = get_config()

    shops = cfg.get_shops()               # dict
    categories = cfg.get_categories()     # dict

    print("Comments'ten Rating güncelleme başlatılıyor...")
    print("=" * 60)

    total_products_updated = 0
    total_products_no_comments = 0

    for shop_name, shop_info in shops.items():
        print(f"\n {shop_name} işleniyor...")

        data_dir = cfg.get_shop_data_path(shop_name)
        if not data_dir:
            print(f"Data path bulunamadı: {shop_name}")
            continue

        for cat_key, cat_info in categories.items():
            product_path = data_dir / cat_info["product_file"]
            comment_path = data_dir / cat_info["comments_file"]

            if not product_path.exists():
                print(f"Product dosyası yok: {product_path}")
                continue
            if not comment_path.exists():
                print(f"Comment dosyası yok: {comment_path}")
                continue

            try:
                products = load_json(product_path)
                comments_data = load_json(comment_path)
            except Exception as e:
                print(f"Dosya okuma hatası {shop_name}/{cat_key}: {e}")
                continue

            if not isinstance(products, list):
                print(f"Product dosyası list değil: {shop_name}/{cat_key}")
                continue
            if not isinstance(comments_data, dict):
                print(f"Comments dosyası dict değil: {shop_name}/{cat_key}")
                continue

            print(f"\n{cat_key.upper()}: {len(products)} ürün, {len(comments_data)} ürün için yorum grubu")

            updated_count = 0
            no_comments_count = 0

            for product in products:
                pid = product.get("id")
                if not pid:
                    print(f" ID eksik ürün atlandı: {product.get('name', 'Bilinmeyen')}")
                    continue

                product_comments = comments_data.get(pid, [])
                if not product_comments:
                    no_comments_count += 1

                    print(f"{pid}: Yorum yok (Mevcut rating: {product.get('rating')})")
                    continue

                stats = get_rating_stats(product_comments)

                product["rating"] = stats["average"]
                product["rating_count"] = stats["count"]
                product["rating_stats"] = {
                    "min": stats.get("min", 0),
                    "max": stats.get("max", 0),
                    "ratings": stats["ratings"],
                }


                meta = product.get("pricelens_metadata")
                if isinstance(meta, dict):
                    meta["comment_count"] = stats["count"]

                updated_count += 1

            # Kaydet
            if updated_count > 0:
                try:
                    save_json_atomic(product_path, products)
                    print(f"\n💾 {shop_name}/{cat_key}.json güncellendi.")
                except Exception as e:
                    print(f"Kaydetme hatası {shop_name}/{cat_key}: {e}")
            else:
                print(f"\n{shop_name}/{cat_key}: Güncellenecek ürün bulunamadı")

            print(f"Özet: {updated_count} güncellendi, {no_comments_count} yorumsuz")
            total_products_updated += updated_count
            total_products_no_comments += no_comments_count

    print("\n" + "=" * 60)
    print("Rating güncelleme tamamlandı!")
    print(f"Toplam güncellenen ürün: {total_products_updated}")
    print(f"Yorumsuz ürün sayısı: {total_products_no_comments}")


if __name__ == "__main__":
    main()
