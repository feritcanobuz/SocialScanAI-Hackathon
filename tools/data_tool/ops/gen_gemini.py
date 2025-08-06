# tools/data_tool/ops/gen_gemini.py

import os
import json
import time
from pathlib import Path
from config.config_loader import get_config
import google.generativeai as genai

# prompt şablonu
def build_prompt(product):
    return f"""You are a fashion product assistant AI.

Your task is to write a very descriptive e-commerce product summary and generate detailed tags that describe the product visually, so that someone could find it by describing it.

Product name: {product['name']}
Brand: {product['brand']}
Model: {product['model']}
Colors: {', '.join(product['colors'])}
Category: {product['category']}

Requirements:
1. Write a vivid and visual description (2-3 sentences) that includes:
   - shoe type (e.g. sneaker, running shoe, high-top, low-top),
   - color placement (e.g. red toe box, white midsole, black laces),
   - materials (e.g. leather upper, mesh panel),
   - any visible logo or brand features (e.g. Nike swoosh, Adidas stripes, NB logo),
   - ankle style (e.g. low-cut, mid-cut, high-cut).

2. Generate 15-25 short English tags focusing on what can be seen in the image. Examples: ["yellow sole", "mesh upper", "N logo", "high top", "black laces", "retro style"]

3. Add logo visuals and materials to tag list if possible.

Return in this exact JSON format:
{{
  "description": "...",
  "tags": ["...", "...", "..."]
}}"""

# Tüm dükkan ve kategorilerde boş açıklamaları doldurur
def generate_all_descriptions():
    cfg = get_config()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not found in environment. Check your .env file.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")

    for shop_name, shop in cfg.get_shops().items():

        print(f"\nStore: {shop_name}")

        shop_path = Path(shop["data_path"])

        for cat_key, cat_info in cfg.get_categories().items():

            product_path = shop_path / cat_info["product_file"]
            if not product_path.exists():
                print(f" Missing product file: {product_path.name}, skipping...")
                continue

            try:
                with product_path.open("r", encoding="utf-8") as f:
                    products = json.load(f)
            except Exception as e:
                print(f"Failed to load {product_path.name}: {e}")
                continue

            updated = False
            for product in products:
                if product.get("description") and product.get("tags"):
                    print(f" {product['id']} already processed.")
                    continue

                try:
                    prompt = build_prompt(product)
                    resp = model.generate_content(prompt)
                    raw_text = resp.text

                    json_start = raw_text.find("{")
                    json_end = raw_text.rfind("}") + 1
                    json_str = raw_text[json_start:json_end]

                    data = json.loads(json_str)
                    product["description"] = data["description"]
                    product["tags"] = data["tags"]

                    print(f"{product['id']} processed.")
                    updated = True
                    time.sleep(1.2)

                except Exception as e:
                    print(f"Error with {product['id']}: {e}")
                    continue

            if updated:
                try:
                    with product_path.open("w", encoding="utf-8") as f:
                        json.dump(products, f, ensure_ascii=False, indent=2)
                    print(f"{product_path.name} updated.")
                except Exception as e:
                    print(f"Failed to write {product_path.name}: {e}")
            else:
                print(f"{product_path.name} is already up to date.")

if __name__ == "__main__":
    generate_all_descriptions()
