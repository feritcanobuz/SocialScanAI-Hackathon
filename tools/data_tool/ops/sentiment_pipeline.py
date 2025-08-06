# tools/data_tool/ops/sentiment_pipeline.py

import os
import sys
import json
import time
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

#PROJECT & CONFIG 
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from config.config_loader import get_config
from tools.data_tool.text_utils import (
    normalize_text,
    get_text_hash,
    load_cache,
    save_cache,
    load_json,
    save_json_atomic,
)

config = get_config()

# Yolları config’ten al

CACHE_PATH = config.get_absolute_path(config.get("paths.cache", "dukkans/cache.json"))

# Mağaza kategori bilgileri
SHOPS = config.get_shops()                         
CATEGORIES = config.get_categories()               

#  GEMINI
import google.generativeai as genai

MODEL_NAME = "models/gemini-1.5-flash"
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY/GOOGLE_API_KEY bulunamadı (.env ya da environment).")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(model_name=MODEL_NAME)

# TUNABLES
BATCH_SIZE = 5
BATCH_SLEEP = 0.2
RETRY_MAX = 3
BACKOFF_START = 1.0
BACKOFF_FACTOR = 1.5

# HELPERS 
def iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def build_prompt(items: List[Dict[str, str]]) -> str:
    """
    items: [{"id":"<hash>", "text":"<orijinal metin>"}]
    ÇIKTI: Sadece JSON dizi. Her öğe: {id, polarity[-1..1], intensity[0..1], density[0..1], sentiment_class}
    """
    directive = (
        "Aşağıda e-ticaret yorumları var. Her öğe için duygu analizi yap ve SADECE JSON döndür.\n"
        "- ÇIKTI: Tek bir JSON DİZİSİ; başka metin/markdown yok.\n"
        "- Her öğede alanlar: id (girdiyle aynı), polarity[-1..1], intensity[0..1], density[0..1], "
        "sentiment_class ('positive'|'neutral'|'negative').\n"
        "- Çok kısa/boş/kararsız metinlerde: polarity=0, intensity=0, density=0, sentiment_class='neutral'.\n"
    )
    input_json = json.dumps(items, ensure_ascii=False)
    prompt = (
        directive
        + "\nGirdi (JSON dizi):\n"
        + input_json
        + "\n\nÇıktı (SADECE JSON dizi, örn: "
        + '[{"id":"...","polarity":0.12,"intensity":0.3,"density":0.4,"sentiment_class":"neutral"}]):'
    )
    return prompt

def extract_json(text: str) -> Any:
    """Model çıktısından sağlam JSON çıkar (fence vs. eklerse)."""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.findall(r"```json(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        s = m[0].strip()
        try:
            return json.loads(s)
        except Exception:
            pass

    i, j = text.find("["), text.rfind("]")
    if i != -1 and j != -1 and j > i:
        s = text[i : j + 1]
        try:
            return json.loads(s)
        except Exception:
            pass
    raise ValueError("Model çıktısı JSON parse edilemedi.")

def send_batch_with_retry(items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Gemini'ye 5'li batch gönder; retry/backoff uygula; JSON liste döndür."""
    assert len(items) <= BATCH_SIZE
    prompt = build_prompt(items)

    delay = BACKOFF_START
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    response_mime_type="text/plain",
                ),
            )
            raw = resp.text or ""
            data = extract_json(raw)
            if not isinstance(data, list):
                raise ValueError("Beklenen çıktı listesi değil.")
            for d in data:
                if "id" not in d:
                    raise ValueError("Çıktı öğesinde 'id' yok.")
            return data

        except Exception as e:
            if attempt >= RETRY_MAX:
                raise
            print(f"  WARN: batch hatası ({e}); retry {attempt}/{RETRY_MAX}...")
            time.sleep(delay)
            delay *= BACKOFF_FACTOR

def ensure_null_fields_on_empty(comment: Dict[str, Any]) -> None:
    """Boş text için null sentiment alanları ekle."""
    comment["polarity"] = None
    comment["intensity"] = None
    comment["density"] = None
    comment["sentiment_class"] = None

def enrich_comment_with_cache(comment: Dict[str, Any], cache: Dict[str, Any]) -> None:
    """Dolu text için cache’ten sentiment ekle; yoksa null yaz."""
    text = (comment.get("text") or "").strip()
    if not text:
        ensure_null_fields_on_empty(comment)
        return
    h = get_text_hash(text)
    entry = cache.get(h)
    if not entry or "sentiment" not in entry:
        ensure_null_fields_on_empty(comment)
        return
    s = entry["sentiment"]
    comment["polarity"] = s.get("polarity")
    comment["intensity"] = s.get("intensity")
    comment["density"] = s.get("density")
    comment["sentiment_class"] = s.get("sentiment_class")

# MAIN 
def main():

    cache: Dict[str, Any] = load_cache(CACHE_PATH)
    print(f"INFO: Cache loaded -> {len(cache)} entries")
    to_send_map: Dict[str, str] = {}
    files_found = 0

    for shop_name, shop in SHOPS.items():
        data_root = Path(shop["data_path"])
        for cat_key, cat in CATEGORIES.items():
            comments_rel = cat.get("comments_file")
            if not comments_rel:
                continue
            fpath = data_root / comments_rel
            if not fpath.exists():
                print(f"INFO: {shop_name}/{comments_rel} not found, skipping.")
                continue
            files_found += 1

            data = load_json(fpath)
            if not isinstance(data, dict):
                print(f"INFO: {shop_name}/{comments_rel} invalid or empty JSON, skipping.")
                continue

            for product_id, comments in data.items():
                if not isinstance(comments, list):
                    continue
                for c in comments:
                    text = (c.get("text") or "").strip()
                    if not text:
                        continue
                    h = get_text_hash(text)
                    if h not in cache and h not in to_send_map:
                        to_send_map[h] = text

    if files_found == 0:
        print("WARN: Hiç yorum dosyası bulunamadı. Çıkılıyor.")
        return

    miss_count = len(to_send_map)
    print(f"INFO: Unique cache-miss comments -> {miss_count}")

    if miss_count > 0:
        hashes = list(to_send_map.keys())
        total_batches = math.ceil(len(hashes) / BATCH_SIZE)

        for b in range(total_batches):
            start = b * BATCH_SIZE
            end = min((b + 1) * BATCH_SIZE, len(hashes))
            batch_hashes = hashes[start:end]
            items = [{"id": h, "text": to_send_map[h]} for h in batch_hashes]

            print(f"INFO: Sending batch {b+1}/{total_batches} (size={len(items)})...")
            results = send_batch_with_retry(items)

            # id -> result
            result_map = {r["id"]: r for r in results}

            created_at = iso_utc()
            for h in batch_hashes:
                r = result_map.get(h)
                if not r:
                    print(f"  WARN: no result for id={h} in batch response; skipping.")
                    continue

                # Şema normalize
                try:
                    pol = float(r.get("polarity"))
                except Exception:
                    pol = 0.0
                try:
                    inten = float(r.get("intensity"))
                except Exception:
                    inten = 0.0
                try:
                    dens = float(r.get("density"))
                except Exception:
                    dens = 0.0
                sc = (r.get("sentiment_class") or "neutral").strip().lower()
                if sc not in ("positive", "neutral", "negative"):
                    sc = "neutral"

                cache[h] = {
                    "original": to_send_map[h],
                    "normalized": normalize_text(to_send_map[h]),
                    "sentiment": {
                        "polarity": max(-1.0, min(1.0, pol)),
                        "intensity": max(0.0, min(1.0, inten)),
                        "density": max(0.0, min(1.0, dens)),
                        "sentiment_class": sc,
                    },
                    "source": MODEL_NAME,
                    "created_at": created_at,
                    "version": 1,
                }
            save_cache(CACHE_PATH, cache)
            time.sleep(BATCH_SLEEP)

    print(f"INFO: Cache filled → {len(cache)} entries total")

    # 4) ENRICHMENT: comments dosyalarına yaz (in-place, atomik)
    updated_files = 0
    for shop_name, shop in SHOPS.items():
        data_root = Path(shop["data_path"])
        for cat_key, cat in CATEGORIES.items():
            comments_rel = cat.get("comments_file")
            if not comments_rel:
                continue
            fpath = data_root / comments_rel
            if not fpath.exists():
                continue

            data = load_json(fpath)
            if not isinstance(data, dict):
                continue

            changed = False
            for product_id, comments in data.items():
                if not isinstance(comments, list):
                    continue
                for c in comments:
                    before = (
                        c.get("polarity"),
                        c.get("intensity"),
                        c.get("density"),
                        c.get("sentiment_class"),
                    )
                    text = (c.get("text") or "").strip()
                    if not text:
                        ensure_null_fields_on_empty(c)
                    else:
                        enrich_comment_with_cache(c, cache)

                    after = (
                        c.get("polarity"),
                        c.get("intensity"),
                        c.get("density"),
                        c.get("sentiment_class"),
                    )
                    if before != after:
                        changed = True

            if changed:
                save_json_atomic(fpath, data)
                updated_files += 1
                print(f"INFO: Enriched → {shop_name}/{comments_rel}")

    print(f"INFO: Enrichment done. Files updated: {updated_files}")
    print("Done.")


if __name__ == "__main__":
    main()
