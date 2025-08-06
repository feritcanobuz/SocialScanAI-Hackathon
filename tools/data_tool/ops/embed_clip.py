# tools/data_tool/ops/embed_clip.py

import json
import numpy as np
import torch
from PIL import Image
from pathlib import Path
import open_clip

from config.config_loader import get_config


#  Model yükle (config'ten) 
def _parse_openclip_name(s: str):
    """
    config.models.clip.model_name = 'open_clip:ViT-B-32/laion2b_s34b_b79k'
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
        # Güvenli varsayılan
        return "ViT-B-32", "laion2b_s34b_b79k"


cfg = get_config()
models_cfg = cfg.get_models() or {}
clip_cfg = models_cfg.get("clip", {}) or {}
clip_model_name = clip_cfg.get("model_name", "open_clip:ViT-B-32/laion2b_s34b_b79k")

arch, pretrained = _parse_openclip_name(clip_model_name)

device = "cuda" if torch.cuda.is_available() else "cpu"
model, _, preprocess = open_clip.create_model_and_transforms(arch, pretrained=pretrained)
model = model.to(device).eval()


def resolve_image_path(base_dir: Path, rel_path: str) -> Path:
    """
    JSON'daki rel_path:
      - 'images/tshirt/...' ise: 'images' segmentini at ve base_dir ile birleştir
      - 'tshirt/...'        ise: direkt base_dir ile birleştir
      - absolute path        ise: aynen kullan
    """
    p = Path(rel_path)


    if p.is_absolute() or getattr(p, "drive", ""):
        return p

    parts = p.parts
    if parts and parts[0].lower() == "images":

        p = Path(*parts[1:])

    return Path(base_dir) / p


def get_clip_vector(image_path: Path):
    image_path = Path(image_path)
    if not image_path.exists():
        return None, f"Görsel bulunamadı: {image_path}"

    try:
        image = Image.open(str(image_path)).convert("RGB")
        image = preprocess(image).unsqueeze(0).to(device)
        with torch.no_grad():
            feats = model.encode_image(image).cpu().numpy()
            norm = np.linalg.norm(feats)
            if norm == 0.0:
                return None, f"Sıfır norm vektör: {image_path}"
            vec = (feats / norm).tolist()[0]
            return vec, None
    except Exception as e:
        return None, f" Görsel işlenemedi: {image_path} → {e}"


def generate_clip_vectors():
    shops = cfg.get_shops()
    categories = cfg.get_categories()

    for shop_name, shop_info in shops.items():
        print(f"\n Dükkan: {shop_name}")

        data_dir = cfg.get_shop_data_path(shop_name)
        image_dir = cfg.get_shop_image_path(shop_name)
        if not data_dir or not image_dir:
            print(f"   Path eksik: data={data_dir}, images={image_dir}")
            continue

        for cat_key, cat_info in categories.items():
            product_file = data_dir / cat_info["product_file"]
            if not product_file.exists():
                print(f"   {cat_key} için ürün dosyası yok.")
                continue

            with product_file.open("r", encoding="utf-8") as f:
                products = json.load(f)

            updated = False

            for item in products:
                if item.get("clip_vector"):
                    continue

                rel_paths = item.get("images") or []
                if not rel_paths:
                    continue

                vec = None
                chosen_path = None

                for rel in rel_paths:
                    final_path = resolve_image_path(image_dir, rel)
                    v, err = get_clip_vector(final_path)
                    if v is not None:
                        vec = v
                        chosen_path = final_path
                        break
                    else:

                        print(err)

                if vec:
                    item["clip_vector"] = vec
                    print(f"{item.get('id','?')} için clip vektörü üretildi. ({chosen_path.name})")
                    updated = True

            if updated:
                with product_file.open("w", encoding="utf-8") as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                print(f"{cat_key}.json güncellendi.")
            else:
                print(f"{cat_key}.json zaten güncel.")


if __name__ == "__main__":
    generate_clip_vectors()
