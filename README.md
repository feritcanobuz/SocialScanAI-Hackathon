# SocialScanAI

**Projenin ayrıntılı github reposundasunumunu kök dizinde Rapor_SocialScanAI olarak paylaştık.**

Multimodal (görsel + metin) ürün arama, mağazalar arası karşılaştırma (Pricelens) ve WhatsApp bildirimleri (B2C/B2B) sağlayan hızlı bir demo.
Amacımız, kullanıcı ürünün adını bilmese bile görsel ya da betimleyici metinle aradığını hızlı ve doğru bulsun; ardından üç mağaza arasında tek bir “en iyi teklif” önerisi alsın. Bunu; ürünlerden çıkardığımız görsel ve metinsel vektörleri (CLIP + ST) birleştirip, RRF ile farklı arama sinyallerini tek listede toplayarak yapıyoruz. Son adımda Pricelens skoru ile fiyat–yorum–algı dengesini özetleyip en mantıklı seçeneği öne çıkarıyoruz. Kullanıcı isterse ürün için stok ve fiyat takibi açıyor; değişiklikte WhatsApp’tan bildirim gidiyor. Aynı ürün/mağazada talep artarsa satıcıya B2B içgörü (stok güncelle, kampanya önerisi) üretiyoruz.

**Videoda kullandığımız test görseli projenin kök dizininde yer almaktadır. Test sorgusu ise : I saw a silver grey sneaker with a chunky retro sole, breathable mesh panels, and an 'N' shaped side logo. Probably suede or synthetic overlay**


# Projeyi hızlıca ayağa kaldırmak için :
terminalde aşağıdaki komutu çalıştırın:
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
kök dizindeki frontend klasöründeki index.html sağ tık open with live server ile başlatabilirsiniz.



python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # anahtarlarını doldur

# Yeni ürün ekleme (ID üretimi + ilgili comment dosyasında boş liste)
python -m tools.data_tool.ops.product_add

# Boş description/tags alanlarını Gemini ile doldur
python -m tools.data_tool.ops.gen_gemini

# Vektör üretimi
python -m tools.data_tool.ops.embed_clip
python -m tools.data_tool.ops.embed_text_st
python -m tools.data_tool.ops.embed_text_clip
python -m tools.data_tool.ops.embed_combined

# Metinle arama
python -m tools.data_tool.search.search_by_text

# Görselle arama
python -m tools.data_tool.search.search_by_image

python -m tools.data_tool.ops.run_all_pipeline

# API (FastAPI)
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# WhatsApp bildirim worker’ı (Twilio)
python api/notification_worker.py

# Kök dizinde
python run_all_store.py

socialscanai/
├── .env
├── .gitignore
├── bunukesinokumanLAZIM.md
├── README.md
├── requirements.txt
│
├── api/
│   ├── main.py
│   └── notification_worker.py
│
├── frontend/
│   └── index.html
│
├── state/
│   ├── tracking.json
│   └── b2b_notified.json
│
├── config/
│   ├── categories.yml
│   ├── config.yaml
│   ├── models.yml
│   └── shops.yml
│
├── dukkans/
│   ├── cache.json
│   ├── ecommerce1/               # ecommerce2 / ecommerce3 aynı şema
│   │   ├── backend/
│   │   │   ├── main.py
│   │   │   └── data/
│   │   │       ├── comments/
│   │   │       │   ├── ayakkabi_comments.json
│   │   │       │   ├── sapka_comments.json
│   │   │       │   ├── sweat_comments.json
│   │   │       │   └── tshirt_comments.json
│   │   │       ├── images/
│   │   │       │   ├── ayakkabi/ayk_01_1.jpg, ayk_01_2.jpg, …
│   │   │       │   ├── sapka/…
│   │   │       │   ├── sweat/…
│   │   │       │   └── tshirt/…
│   │   │       └── product/
│   │   │           ├── ayakkabi.json
│   │   │           ├── sapka.json
│   │   │           ├── sweat.json
│   │   │           └── tshirt.json
│   │   └── frontend/
│   │       ├── index.html
│   │       ├── product.html
│   │       └── src/
│   │           ├── css/style.css
│   │           └── js/
│   │               ├── detail.js
│   │               └── render.js
│   └── ecommerce2/, ecommerce3/  # ↑ birebir aynı
│
└── tools/
    └── data_tool/
        ├── __init__.py
        ├── cfg.py
        ├── config.yaml
        ├── hashutil.py
        ├── io.py
        ├── main.py
        ├── schema.py
        ├── text_utils.py
        ├── util_id.py
        │
        ├── ops/
        │   ├── __init__.py
        │   ├── add_missing_vectors.py
        │   ├── calc_metrics.py
        │   ├── embed_clip.py
        │   ├── embed_combined.py
        │   ├── embed_text_clip.py
        │   ├── embed_text_st.py
        │   ├── gen_gemini.py
        │   ├── product_add.py
        │   ├── run_all_pipeline.py
        │   ├── sentiment_pipeline.py
        │   └── validate.py
        │
        └── search/
            ├── search_by_image.py
            └── search_by_text.py
