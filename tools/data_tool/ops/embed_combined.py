# tools/data_tool/ops/embed_combined.py

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

from config.config_loader import get_config


def combine_vectors(vec1: List[float], vec2: List[float], weight1: float = 0.6, weight2: float = 0.4) -> List[float]:
    """
    - Boyut uyumu kontrolü
    - Ağırlıklı ortalama
    - Normalize
    - Sıfır-norm koruması
    """
    if not vec1 or not vec2:
        return []

    v1 = np.array(vec1, dtype=float)
    v2 = np.array(vec2, dtype=float)

    if len(v1) != len(v2):
        print(f"Boyut uyumsuzluğu: v1={len(v1)}, v2={len(v2)}")
        min_dim = min(len(v1), len(v2))
        v1 = v1[:min_dim]
        v2 = v2[:min_dim]
        print(f"Boyutlar {min_dim} olarak eşitlendi")

    combined = (v1 * weight1 + v2 * weight2) / (weight1 + weight2)

    norm = np.linalg.norm(combined)
    if norm <= 0:
        print("Sıfır norm vektör tespit edildi!")
        return []
    combined = combined / norm
    return combined.tolist()


def main():
    cfg = get_config()

    weights = (cfg.get("combined.weights") or {}) if hasattr(cfg, "get") else {}
    w_clip = float(weights.get("clip", 0.6))
    w_text = float(weights.get("text_clip", 0.4))
    print(f"Birleştirme ağırlıkları: CLIP={w_clip}, Text-CLIP={w_text}")

    shops = cfg.get_shops()
    categories = cfg.get_categories()

    for shop_name, shop_info in shops.items():
        print(f"\nDükkan: {shop_name}")
        data_dir = cfg.get_shop_data_path(shop_name)
        if not data_dir:
            print(f"Data path yok: {shop_name}")
            continue

        for category, cat_info in categories.items():
            product_path = data_dir / cat_info["product_file"]
            if not product_path.exists():
                print(f"{category}.json yok, atlanıyor.")
                continue

            with product_path.open("r", encoding="utf-8") as f:
                products: list[Dict[str, Any]] = json.load(f)

            updated = False
            processed_count = 0
            error_count = 0

            for item in products:
                # Zaten doluysa atla
                cv = item.get("combined_vector")
                if isinstance(cv, list) and len(cv) > 0:
                    continue

                clip_vec = item.get("clip_vector") or []
                # Legacy fallback: clip_text_vector
                text_vec = item.get("text_vector_clip") or item.get("clip_text_vector") or []

                if not clip_vec or not text_vec:
                    error_count += 1
                    continue

                combined = combine_vectors(clip_vec, text_vec, w_clip, w_text)
                if combined:
                    item["combined_vector"] = combined
                    processed_count += 1
                    updated = True

            if updated:
                with product_path.open("w", encoding="utf-8") as f:
                    json.dump(products, f, indent=2, ensure_ascii=False)
                print(f"{category}.json güncellendi. İşlenen: {processed_count}, Hatalı: {error_count}")
            else:
                print(f"{category}.json zaten güncel.")


if __name__ == "__main__":
    main()
