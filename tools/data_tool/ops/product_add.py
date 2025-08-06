# tools/data_tool/ops/product_add.py

import json
import shutil
from pathlib import Path
import typer

from config.config_loader import get_config
from tools.data_tool.util_id import generate_new_id

app = typer.Typer()

def coerce_bool(s: str) -> bool:
    s = (s or "").strip().lower()
    return s in {"true", "t", "1", "yes", "y", "evet", "e"}

def get_sizes_for_category(category: str) -> list[str]:
    """Kategoriye göre sabit beden listesi döndür."""
    if category == "ayakkabi":
        return [str(x) for x in range(37, 43)]  
    if category == "sapka":
        return ["OS"]
    if category in {"sweat", "tshirt"}:
        return ["S", "M", "L", "XL"]
    return ["STD"]

@app.command()
def product_add(
    category: str = typer.Option(..., prompt="Kategori (ayakkabi/sapka/sweat/tshirt)"),
    shops: str = typer.Option(..., prompt="Hangi dükkanlara eklemek istiyorsun? (virgül ile)"),
):
    cfg = get_config()

    category = category.lower().strip()
    shop_list = [s.strip() for s in shops.split(",") if s.strip()]


    if not cfg.is_valid_category(category):
        typer.echo("Geçersiz kategori.")
        raise typer.Exit(code=1)

    shops_dict = cfg.get_shops()
    for s in shop_list:
        if s not in shops_dict:
            typer.echo(f"Geçersiz shop: {s}")
            raise typer.Exit(code=1)

    # Paths / files
    cat_info = cfg.get_category(category)
    product_file_rel = cat_info["product_file"]
    comments_file_rel = cat_info["comments_file"]

    first_shop = shop_list[0]
    first_shop_data_dir = cfg.get_shop_data_path(first_shop)
    first_shop_product_path = first_shop_data_dir / product_file_rel

    # ID üretimi
    if first_shop_product_path.exists():
        with first_shop_product_path.open("r", encoding="utf-8") as f:
            example_products = json.load(f) or []
            existing_ids = [item.get("id", "") for item in example_products if isinstance(item, dict)]
    else:
        existing_ids = []

    prefix = cat_info["id_prefix"] + "_"
    new_id = generate_new_id(existing_ids, prefix)
    typer.echo(f"Yeni ID: {new_id}")

    # Kategoriye göre sabit bedenler
    sizes = get_sizes_for_category(category)
    typer.echo(f"Bedenler: {', '.join(sizes)}")

    # Ürün alanları
    name = typer.prompt("Ürün adı")
    brand = typer.prompt("Marka")
    model = typer.prompt("Model")
    colors = [c.strip() for c in typer.prompt("Renkler (virgül ile)").split(",") if c.strip()]

    img1 = typer.prompt("Görsel 1 yolu").strip().strip('"')
    img2 = typer.prompt("Görsel 2 yolu").strip().strip('"')
    img1_path = Path(img1); img2_path = Path(img2)
    if not img1_path.exists():
        typer.echo(f"Görsel 1 bulunamadı: {img1_path}"); raise typer.Exit(code=1)
    if not img2_path.exists():
        typer.echo(f"Görsel 2 bulunamadı: {img2_path}"); raise typer.Exit(code=1)

    img_name1 = f"{new_id}_1.jpg"
    img_name2 = f"{new_id}_2.jpg"

    # Görselleri kopyala
    for shop in shop_list:
        image_root = cfg.get_shop_image_path(shop)
        if not image_root:
            typer.echo(f"image path bulunamadı: {shop}")
            raise typer.Exit(code=1)
        target_dir = image_root / category
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(img1, target_dir / img_name1)
        shutil.copy(img2, target_dir / img_name2)

    images = [f"images/{category}/{img_name1}", f"images/{category}/{img_name2}"]

    base_product = {
        "id": new_id,
        "name": name,
        "brand": brand,
        "model": model,
        "category": category,
        "images": images,
        "colors": colors,
        "description":"",
        "tags": [],
        "clip_vector": [],
        "text_vector_st": [],
        "text_vector_clip": [],
        "combined_vector": []
    }

    # Yaz ve comments entry oluştur
    for shop in shop_list:
        data_dir = cfg.get_shop_data_path(shop)
        if not data_dir:
            typer.echo(f"Data path bulunamadı: {shop}")
            raise typer.Exit(code=1)

        product_json = data_dir / product_file_rel
        if product_json.exists():
            with product_json.open("r", encoding="utf-8") as f:
                try:
                    products = json.load(f)
                    if not isinstance(products, list):
                        products = []
                except Exception:
                    products = []
        else:
            product_json.parent.mkdir(parents=True, exist_ok=True)
            products = []

        price = float(typer.prompt(f"{shop} için fiyat (örn 999.90)"))

        # Her sabit beden için availability sor
        stock = []
        for sz in sizes:
            ans = typer.prompt(f"{shop} stok '{sz}' var mı? (true/false)", default="true")
            is_avail = coerce_bool(ans)
            stock.append({"size": sz, "isAvailable": is_avail})

        product = dict(base_product)
        product.update({"price": price, "rating": None, "stock": stock})
        products.append(product)

        with product_json.open("w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        typer.echo(f"{shop} → {product_json} yazıldı ")

        # comments dosyasına [] ekle
        comments_json = data_dir / comments_file_rel
        if comments_json.exists():
            try:
                with comments_json.open("r", encoding="utf-8") as f:
                    comments = json.load(f)
                    if not isinstance(comments, dict):
                        comments = {}
            except Exception:
                comments = {}
        else:
            comments_json.parent.mkdir(parents=True, exist_ok=True)
            comments = {}

        if new_id not in comments:
            comments[new_id] = []
            with comments_json.open("w", encoding="utf-8") as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            typer.echo(f"{shop} → {comments_json} → boş yorum listesi eklendi ")
        else:
            typer.echo(f"{shop} → {comments_json} içinde {new_id} zaten var ")

cmd_product_add = product_add

if __name__ == "__main__":
    app()
