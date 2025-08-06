# tools/data_tool/search/search_by_image.py

import os
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
import open_clip
import matplotlib.pyplot as plt

# CONFIG =
from config.config_loader import get_config
_cfg = get_config()

BASE_DIR = _cfg.get_absolute_path("dukkans")                 
DUKKANLAR = list(_cfg.get_shops().keys()) 
KATEGORILER = list(_cfg.get_categories().keys())        
device = "cuda" if torch.cuda.is_available() else "cpu"

# MODEL LOAD 
model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
model = model.to(device).eval()

# Optimize edilmiş cosine similarity 
def cosine_sim(a, b):
    """
    Normalize edilmiş vektörler için optimize edildi
    """
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b))

def show_image(img_path, title="Ürün"):
    """
    Ürün görselini göster - API modunda çalışmaz
    """
    if Path(img_path).exists():
        img = Image.open(img_path)
        plt.imshow(img)
        plt.title(title)
        plt.axis("off")
        plt.show()

# RRF algoritması =
def reciprocal_rank_fusion(results_dict, k=60):
    """
    RRF algoritması - görsel aramada hibrit sonuçlar
    """
    rrf_scores = {}
    for method, results in results_dict.items():
        for rank, (pid, name, score, item) in enumerate(results, 1):
            if pid not in rrf_scores:
                rrf_scores[pid] = {
                    "name": name,
                    "item": item,
                    "scores": {},
                    "rrf_score": 0.0,
                }
            # RRF formülü: 1/(k + rank)
            rrf_scores[pid]["rrf_score"] += 1 / (k + rank)
            rrf_scores[pid]["scores"][method] = {"rank": rank, "score": score}

    final_results = sorted(rrf_scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)
    return final_results

#RRF + Pricelens Entegre Görsel Arama 
def search_image_with_rrf_pricelens(image_path, kategori, top_n=3, api_mode=False):
    """
    RRF ile hibrit görsel arama + Pricelens entegrasyonu
    api_mode: True ise print'leri bastır
    """
    image_path = str(image_path)
    if not Path(image_path).exists():
        if not api_mode:
            print(" Görsel bulunamadı.")
        return [], []


    image = Image.open(image_path).convert("RGB")
    image_tensor = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        image_features = model.encode_image(image_tensor)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        query_vector = image_features.squeeze().cpu().numpy()

    if not api_mode:
        print(f"\n Görsel araması başlatıldı: {Path(image_path).name} ({kategori})")
        print(f"Query vektör boyutu: {len(query_vector)}")

    #dükkanlardan sonuçları topla
    global_results = {"CLIP": [], "COMB": []}

    for dukkan in DUKKANLAR:
        json_path = Path(BASE_DIR) / dukkan / "backend" / "data" / "product" / f"{kategori}.json"
        if not json_path.exists():
            continue

        with json_path.open("r", encoding="utf-8") as f:
            products = json.load(f)

        if not api_mode:
            print(f"\n {dukkan} - {len(products)} ürün işleniyor")


        results_clip = []
        results_comb = []

        for item in products:
            pid = item["id"]
            name = item.get("name", "Unknown")

            clip_vec = item.get("clip_vector")
            if clip_vec:
                sim_clip = cosine_sim(query_vector, clip_vec)
                results_clip.append((pid, name, sim_clip, item))


            comb_vec = item.get("combined_vector")
            if comb_vec:
                sim_comb = cosine_sim(query_vector, comb_vec)
                results_comb.append((pid, name, sim_comb, item))

        # Sırala
        results_clip.sort(key=lambda x: x[2], reverse=True)
        results_comb.sort(key=lambda x: x[2], reverse=True)


        global_results["CLIP"].extend(results_clip[:top_n])
        global_results["COMB"].extend(results_comb[:top_n])

        # Debug çıktı
        if not api_mode:
            if results_clip:
                best_clip = results_clip[0]
                print(f"CLIP En İyi: {best_clip[1]} → {best_clip[2]:.4f}")
            if results_comb:
                best_comb = results_comb[0]
                print(f"COMB En İyi: {best_comb[1]} → {best_comb[2]:.4f}")

    # Her yöntemi global olarak tekrar sırala ve kes
    for method in global_results:
        global_results[method].sort(key=lambda x: x[2], reverse=True)
        global_results[method] = global_results[method][:top_n]

    # RRF uygula
    if not api_mode:
        print(f"\nRRF ile sonuçlar birleştiriliyor...")
    final_results = reciprocal_rank_fusion(global_results)

    # RRF sonuçlarını göster
    if not api_mode:
        print(f"\nRRF Sonuçları:")
        for i, (pid, data) in enumerate(final_results[:5], 1):
            name = data["name"]
            rrf_score = data["rrf_score"]
            print(f"{i}. {name} (RRF: {rrf_score:.4f})")
            methods_info = []
            for method, info in data["scores"].items():
                methods_info.append(f"{method}:{info['rank']}({info['score']:.3f})")
            print(f"{' | '.join(methods_info)}")

    # PRİCELENS ENTEGRASYONU 
    product_variants = []
    if final_results:

        best_product_id = final_results[0][0]
        if not api_mode:
            print(f"\n Pricelens analizi başlatılıyor - Hedef ürün ID: {best_product_id}")

        # Tüm e-commerce'lerde aynı ürünü ara
        for dukkan in DUKKANLAR:
            json_path = Path(BASE_DIR) / dukkan / "backend" / "data" / "product" / f"{kategori}.json"
            if not json_path.exists():
                continue

            with json_path.open("r", encoding="utf-8") as f:
                products = json.load(f)

            for item in products:
                if item["id"] == best_product_id:
                    variant = {
                        "dukkan": dukkan,
                        "name": item["name"],
                        "pricelens_score": item.get("pricelens_score", 0),
                        "price": item.get("price", "Bilinmiyor"),
                        "rating": item.get("rating", "N/A"),
                        "image": item["images"][0] if item.get("images") else None,
                        "item_data": item,
                    }
                    product_variants.append(variant)
                    if not api_mode:
                        print(
                            f" {dukkan}: Pricelens {variant['pricelens_score']:.4f} | "
                            f"Fiyat: {variant['price']} | Rating: {variant['rating']}"
                        )

        if product_variants:
            # Pricelens skoruna göre sırala (en yüksekten en düşüğe)
            product_variants.sort(key=lambda x: x["pricelens_score"], reverse=True)

            if not api_mode:
                print(f"\n PRİCELENS SIRALAMASI:")
                for i, variant in enumerate(product_variants, 1):
                    print(f"{i}. {variant['dukkan']}")
                    print(f"Ürün: {variant['name']}")
                    print(f"Fiyat: {variant['price']}")
                    print(f"Rating: {variant['rating']}")
                    print(f"Pricelens Skoru: {variant['pricelens_score']:.4f}")
                    print()

                # En iyi Pricelens skoruna sahip ürünü göster
                best_variant = product_variants[0]
                print(f"EN İYİ SEÇENEK:")
                print(f"E-commerce: {best_variant['dukkan']}")
                print(f"ürün: {best_variant['name']}")
                print(f"Fiyat: {best_variant['price']}")
                print(f"Rating: {best_variant['rating']}")
                print(f"Pricelens Skoru: {best_variant['pricelens_score']:.4f}")

                if best_variant["image"]:
                    img_path = Path(BASE_DIR) / best_variant["dukkan"] / "backend" / "data" / best_variant["image"]
                    show_image(img_path, f"{best_variant['name']} - {best_variant['dukkan']} (En İyi Seçenek)")
        else:
            if not api_mode:
                print("Pricelens karşılaştırması yapılacak varyant bulunamadı.")
                # Yine de ilk RRF sonucunu göster
                best_id, best_data = final_results[0]
                best_item = best_data["item"]
                print(f"\n📸 RRF En İyi Sonuç: {best_data['name']}")
                if best_item.get("images"):
                    dukkan_name = best_item.get("dukkan", DUKKANLAR[0])
                    img_path = Path(BASE_DIR) / dukkan_name / "backend" / "data" / best_item["images"][0]
                    show_image(img_path, best_data["name"])

    return final_results, product_variants

# === MAIN ===
if __name__ == "__main__":
    kategori = input(f"Hangi kategoride arama yapmak istiyorsunuz? ({', '.join(KATEGORILER)}): ").strip().lower()
    if kategori not in KATEGORILER:
        print("Geçersiz kategori.")
        raise SystemExit(1)

    image_path = input("Test görselinin yolunu girin (örn: test.jpg): ").strip()

    print("\n" + "=" * 60)
    print(" RRF + PRİCELENS ENTEGRE GÖRSEL ARAMA SİSTEMİ")
    print("=" * 60)

    results, variants = search_image_with_rrf_pricelens(image_path, kategori, api_mode=False)
