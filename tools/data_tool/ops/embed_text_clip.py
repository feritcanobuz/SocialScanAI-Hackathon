# tools/data_tool/ops/embed_text_clip.py

import json
import torch
import numpy as np
import open_clip
from pathlib import Path

from config.config_loader import get_config


def _parse_openclip_name(s: str):
    """
    models.text_clip.model_name = 'open_clip:ViT-B-32/laion2b_s34b_b79k'
    -> ('ViT-B-32', 'laion2b_s34b_b79k')
    Farklı format gelirse güvenli fallback uygular.
    """
    try:
        if ":" in s:
            _, rest = s.split(":", 1)
        else:
            rest = s
        arch, pretrained = rest.split("/", 1)
        return arch.strip(), pretrained.strip()
    except Exception:
        return "ViT-B-32", "laion2b_s34b_b79k"


cfg = get_config()
models_cfg = cfg.get_models() or {}
text_clip_cfg = models_cfg.get("text_clip", {}) or {}
model_name = text_clip_cfg.get("model_name", "open_clip:ViT-B-32/laion2b_s34b_b79k")

arch, pretrained = _parse_openclip_name(model_name)

#  Model 
device = "cuda" if torch.cuda.is_available() else "cpu"
model, _, _preprocess = open_clip.create_model_and_transforms(arch, pretrained=pretrained)
tokenizer = open_clip.get_tokenizer(arch)
model = model.to(device).eval()


def get_text_clip_vector(desc, tags):
    text = f"{desc or ''} " + " ".join(tags or [])
    text = text.strip()
    if not text:
        return []
    try:
        tokenized = tokenizer([text]).to(device)
        with torch.no_grad():
            vec = model.encode_text(tokenized).cpu().numpy()
            norm = np.linalg.norm(vec)
            if norm == 0.0:
                return []
            vec = (vec / norm).tolist()[0]
            return vec
    except Exception as e:
        print(f"Metin işlenemedi → {e}")
        return []


def main():
    shops = cfg.get_shops()
    categories = cfg.get_categories()

    for shop_name, shop_info in shops.items():
        print(f"\nDükkan: {shop_name}")
        data_dir = cfg.get_shop_data_path(shop_name)
        if not data_dir:
            print(f"Data path bulunamadı: {shop_name}")
            continue

        for cat_key, cat_info in categories.items():
            product_path = data_dir / cat_info["product_file"]
            if not product_path.exists():
                print(f"{cat_key} dosyası yok, atlanıyor.")
                continue

            with product_path.open("r", encoding="utf-8") as f:
                products = json.load(f)

            updated = False
            for item in products:

                if item.get("text_vector_clip"):
                    continue

                desc = item.get("description", "")
                tags = item.get("tags", [])
                vec = get_text_clip_vector(desc, tags)
                item["text_vector_clip"] = vec
                if vec:
                    updated = True

            if updated:
                with product_path.open("w", encoding="utf-8") as f:
                    json.dump(products, f, indent=2, ensure_ascii=False)
                print(f"{cat_key}.json güncellendi.")
            else:
                print(f"{cat_key}.json zaten güncel.")


if __name__ == "__main__":
    main()
