# tools/data_tool/hashutil.py

import hashlib
import json
from typing import Dict, Any, List

def compute_full_hash(prod: Dict[str, Any], comments: List[Dict[str, Any]]) -> str:
    """
    Ürünün açıklama, tag, görsel, yıldızlar, skorlar ve yorum verilerinden hash üretir.
    Değişiklikleri tespit etmek için kullanılır.
    """

    def safe_get(d, *keys, default=""):
        for key in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(key, default)
        return d

    # Ürün temel alanları
    img0 = prod.get("images", [""])[0] if isinstance(prod.get("images"), list) else ""
    desc = prod.get("description", "")
    tags = prod.get("tags", []) if isinstance(prod.get("tags"), list) else []
    rating_count = str(prod.get("rating_count", ""))
    pricelens_score = str(prod.get("pricelens_score", ""))
    rating_stats = safe_get(prod, "rating_stats", "ratings", default=[])
    pricelens_metadata = prod.get("pricelens_metadata", {})

    # Yorum alanları (yorum varsa text + rating, yoksa boş)
    comment_bits = []
    if isinstance(comments, list):
        for c in comments:
            txt = c.get("text", "").strip()
            rating = str(c.get("rating", "")).strip()
            if txt or rating:
                comment_bits.append(txt + "|" + rating)

    # Hash giriş verisi
    parts = [
        img0.strip(),
        desc.strip(),
        "|".join(sorted([str(t).strip() for t in tags])),
        "|".join([str(r) for r in rating_stats]),
        rating_count,
        pricelens_score,
        json.dumps(pricelens_metadata, sort_keys=True, ensure_ascii=False),
        "|".join(comment_bits)
    ]

    key = "||".join(parts)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
