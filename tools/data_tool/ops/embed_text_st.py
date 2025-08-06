# tools/data_tool/ops/embed_text_st.py

import json
from pathlib import Path
from typing import List

from sentence_transformers import SentenceTransformer

from config.config_loader import get_config


def _get_model_name() -> str:
    cfg = get_config()
    models = cfg.get_models() or {}
    st = models.get("text_st", {}) or {}
    return st.get("model_name", "sentence-transformers:all-MiniLM-L6-v2").split(":")[-1]


MODEL_NAME = _get_model_name()
print(f"Loading Sentence-Transformers model: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME)


def build_text(item: dict) -> str:
    desc = (item.get("description") or "").strip()
    tags: List[str] = item.get("tags") or []
    return (desc + " " + " ".join(tags)).strip()


def main():
    cfg = get_config()
    shops = cfg.get_shops()
    categories = cfg.get_categories()

    for shop_name, _shop in shops.items():
        print(f"\nShop: {shop_name}")
        data_dir = cfg.get_shop_data_path(shop_name)
        if not data_dir:
            print(f"Data path yok: {shop_name}")
            continue

        for cat_key, cat_info in categories.items():
            file_path = data_dir / cat_info["product_file"]
            if not file_path.exists():
                print(f"Dosya bulunamadı, atlanıyor: {file_path}")
                continue

            with file_path.open("r", encoding="utf-8") as f:
                items = json.load(f)

            batch_texts = []
            batch_indices = []
            for idx, it in enumerate(items):
                if it.get("text_vector_st"):  
                    continue
                text = build_text(it)
                if not text:
                    it["text_vector_st"] = []
                    continue
                batch_texts.append(text)
                batch_indices.append(idx)

            if batch_texts:
                print(f"Embedding {len(batch_texts)} item(s)...")
                embeddings = model.encode(
                    batch_texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=True,
                )
                for i, emb in zip(batch_indices, embeddings):
                    items[i]["text_vector_st"] = emb.tolist()

                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(items, f, indent=2, ensure_ascii=False)
                print(f"Kaydedildi: {file_path}")
            else:
                print(f"Zaten güncel: {file_path}")


if __name__ == "__main__":
    main()
