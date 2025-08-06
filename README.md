# SocialScanAI

**Projenin ayrıntılı sunumunu kök dizinde Rapor_SocialScanAI olarak paylaştık**

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

### Yeni ürün ekleme (ID üretimi + ilgili comment dosyasında boş liste)
python -m tools.data_tool.ops.product_add

#### Boş description/tags alanlarını Gemini ile doldur
python -m tools.data_tool.ops.gen_gemini

#### Vektör üretimi
python -m tools.data_tool.ops.embed_clip
python -m tools.data_tool.ops.embed_text_st
python -m tools.data_tool.ops.embed_text_clip
python -m tools.data_tool.ops.embed_combined

### Metinle arama
python -m tools.data_tool.search.search_by_text

### Görselle arama
python -m tools.data_tool.search.search_by_image

python -m tools.data_tool.ops.run_all_pipeline

### API (FastAPI)
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

### WhatsApp bildirim worker’ı (Twilio)
python api/notification_worker.py

### Kök dizinde
python run_all_store.py
