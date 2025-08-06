# tools/data_tool/search/search_by_text.py

import os
import json
from pathlib import Path

import torch
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer
import open_clip
import matplotlib.pyplot as plt

# Config 
from config.config_loader import get_config
_cfg = get_config()

BASE_DIR = _cfg.get_absolute_path("dukkans")               
DUKKANLAR = list(_cfg.get_shops().keys())                 
KATEGORILER = list(_cfg.get_categories().keys())         

device = "cuda" if torch.cuda.is_available() else "cpu"
st_model = SentenceTransformer("all-MiniLM-L6-v2")
clip_model, _, clip_preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
tokenizer = open_clip.get_tokenizer("ViT-B-32")
clip_model = clip_model.to(device).eval()


def cosine_sim(a, b):
    """
    Normalize edilmiş vektörler için optimize edildi
    """
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b))

def vectorize_query(query):

    query_st = st_model.encode(query, normalize_embeddings=True)


    with torch.no_grad():
        tokens = tokenizer([query]).to(device)
        query_clip = clip_model.encode_text(tokens).float().cpu().numpy()
        query_clip /= np.linalg.norm(query_clip, axis=1, keepdims=True)

    query_clip_flat = query_clip[0].astype(np.float32)
    query_comb = query_clip_flat

    return query_st.astype(np.float32), query_clip_flat, query_comb


# === RRF algoritması ===
def reciprocal_rank_fusion(results_dict, k=60):
    """
    RRF algoritması - farklı arama yöntemlerini akıllıca birleştir
    """
    rrf_scores = {}
    for method, results in results_dict.items():
        for rank, (pid, score, item) in enumerate(results, 1):
            if pid not in rrf_scores:
                rrf_scores[pid] = {"item": item, "scores": {}, "rrf_score": 0.0}
            rrf_scores[pid]["rrf_score"] += 1 / (k + rank)  # 1/(k+rank)
            rrf_scores[pid]["scores"][method] = {"rank": rank, "score": score}

    final_results = sorted(rrf_scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)
    return final_results

def get_top_n(data, vector_key, query_vector, top_n=2):
    """
    Cosine similarity ile en iyi N sonucu getir
    """
    scores = []
    for item in data:
        vec = item.get(vector_key)
        if vec:
            score = cosine_sim(query_vector, vec)
            scores.append((item["id"], score, item))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_n]

def show_image(img_path, title="Ürün"):
    """
    Ürün görselini göster - API modunda çalışmaz
    """
    p = Path(img_path)
    if p.exists():
        img = Image.open(p)
        plt.imshow(img)
        plt.title(title)
        plt.axis("off")
        plt.show()

def search_with_rrf_pricelens(query, kategori_sec, top_n=3, api_mode=False):
    """
    RRF ile hibrit arama + Pricelens entegrasyonu
    api_mode: True ise print'leri bastır
    """
    # Query vektörlerini oluştur
    query_st, query_clip, query_comb = vectorize_query(query)

    if not api_mode:
        print(f"\n Hibrit arama başlatıldı: '{query}' ({kategori_sec})")
        print(f" Vektör boyutları: ST={len(query_st)}, CLIP={len(query_clip)}, COMB={len(query_comb)}")


    global_results = {"ST": [], "CLIP": [], "COMB": []}

    for dukkan in DUKKANLAR:
        json_path = Path(BASE_DIR) / dukkan / "backend" / "data" / "product" / f"{kategori_sec}.json"
        if not json_path.exists():
            continue

        with json_path.open("r", encoding="utf-8") as f:
            items = json.load(f)

        if not api_mode:
            print(f"\n🏪 {dukkan} - {len(items)} ürün işleniyor")

 
        st_results = get_top_n(items, "text_vector_st", query_st, top_n)
        clip_results = get_top_n(items, "text_vector_clip", query_clip, top_n)
        comb_results = get_top_n(items, "combined_vector", query_comb, top_n)

        global_results["ST"].extend(st_results)
        global_results["CLIP"].extend(clip_results)
        global_results["COMB"].extend(comb_results)

        if not api_mode:
            for method, results in [(" ST", st_results), ("CLIP", clip_results), (" COMB", comb_results)]:
                if results:
                    best = results[0]
                    print(f"  {method}: {best[2]['name']} → {best[1]:.4f}")

    # Her yöntemi global olarak tekrar sırala
    for method in global_results:
        global_results[method].sort(key=lambda x: x[1], reverse=True)
        global_results[method] = global_results[method][:top_n]

    # RRF uygula
    if not api_mode:
        print(f"\n RRF ile sonuçlar birleştiriliyor...")
    final_results = reciprocal_rank_fusion(global_results)

    # RRF sonuçlarını göster
    if not api_mode:
        print(f"\nRRF Sonuçları:")
        for i, (pid, data) in enumerate(final_results[:5], 1):
            item = data["item"]
            rrf_score = data["rrf_score"]
            print(f"{i}. {item['name']} (RRF: {rrf_score:.4f})")
            methods_info = []
            for method, info in data["scores"].items():
                methods_info.append(f"{method}:{info['rank']}({info['score']:.3f})")
            print(f"   📈 {' | '.join(methods_info)}")

    # PRİCELENS ENTEGRASYONU 
    product_variants = []
    if final_results:
        best_product_id = final_results[0][0]
        if not api_mode:
            print(f"\n Pricelens analizi başlatılıyor - Hedef ürün ID: {best_product_id}")

        # Tüm e-commerce'lerde aynı ürünü ara
        for dukkan in DUKKANLAR:
            json_path = Path(BASE_DIR) / dukkan / "backend" / "data" / "product" / f"{kategori_sec}.json"
            if not json_path.exists():
                continue

            with json_path.open("r", encoding="utf-8") as f:
                items = json.load(f)

            for item in items:
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
                            f"{dukkan}: Pricelens {variant['pricelens_score']:.2f} | "
                            f"Fiyat: {variant['price']} | Rating: {variant['rating']}"
                        )

        if product_variants:
            product_variants.sort(key=lambda x: x["pricelens_score"], reverse=True)

            if not api_mode:
                print(f"\n PRİCELENS SIRALAMASI:")
                for i, variant in enumerate(product_variants, 1):
                    print(f"{i}.{variant['dukkan']}")
                    print(f"Ürün: {variant['name']}")
                    print(f"Fiyat: {variant['price']}")
                    print(f"Rating: {variant['rating']}")
                    print(f"Pricelens Skoru: {variant['pricelens_score']:.2f}")
                    print()

                best_variant = product_variants[0]
                print(f"EN İYİ SEÇENEK:")
                print(f"E-commerce: {best_variant['dukkan']}")
                print(f"Ürün: {best_variant['name']}")
                print(f"Fiyat: {best_variant['price']}")
                print(f"Rating: {best_variant['rating']}")
                print(f"Pricelens Skoru: {best_variant['pricelens_score']:.2f}")

                if best_variant["image"]:
                    img_path = Path(BASE_DIR) / best_variant["dukkan"] / "backend" / "data" / best_variant["image"]
                    show_image(img_path, f"{best_variant['name']} - {best_variant['dukkan']} (En İyi Seçenek)")
        else:
            if not api_mode:
                print(" Pricelens karşılaştırması yapılacak varyant bulunamadı.")
                best_id, best_data = final_results[0]
                best_item = best_data["item"]
                print(f"\n📷 RRF En İyi Sonuç: {best_item['name']}")
                if best_item.get("images"):
                    dukkan_name = best_item.get("dukkan", DUKKANLAR[0])
                    img_path = Path(BASE_DIR) / dukkan_name / "backend" / "data" / best_item["images"][0]
                    show_image(img_path, best_item["name"])

    return final_results, product_variants

if __name__ == "__main__":
    kategori_sec = input(f" Hangi kategoride arama yapmak istersiniz? ({', '.join(KATEGORILER)}): ").strip().lower()
    if kategori_sec not in KATEGORILER:
        print(" Geçersiz kategori.")
        raise SystemExit(1)

    query = input(" Arama sorgusu girin: ")

    print("\n" + "=" * 60)
    print(" RRF + PRİCELENS ENTEGRE ARAMA SİSTEMİ")
    print("=" * 60)

    results, variants = search_with_rrf_pricelens(query, kategori_sec, api_mode=False)
