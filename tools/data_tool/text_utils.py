# tools/data_tool/text_utils.py

import re
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Union

def normalize_text(text: str) -> str:
    """Yorum metnini normalize eder: küçük harf, noktalama temizliği, Türkçe karakter sadeleştirme."""
    if not text:
        return ""
    text = text.casefold().strip()
    text = text.replace("i̇", "i")  
    text = text.translate(str.maketrans("çğıöşü", "cgiosu")) 
    text = re.sub(r"[^\w\s]", " ", text)  
    text = re.sub(r"\s+", " ", text).strip() 
    return text

def get_text_hash(text: str) -> str:
    """Normalize edilmiş metinden SHA256 hash üretir."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_json(path: Union[str, Path]) -> Any:
    """Verilen JSON dosyasını yükler. Dosya yoksa None döner."""
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Union[str, Path], data: Any) -> None:
    """Verilen veriyi JSON formatında dosyaya yazar (üstüne yazar)."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_json_atomic(path: Union[str, Path], data: Any) -> None:
    """Verilen veriyi önce geçici dosyaya yazar, sonra atomik olarak hedefe taşır."""
    path = Path(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    save_json(tmp_path, data)
    tmp_path.replace(path)

def load_cache(path: Union[str, Path]) -> Dict[str, Any]:
    """Cache dosyasını yükler, yoksa boş dict döner."""
    cache = load_json(path)
    return cache if cache else {}

def save_cache(path: Union[str, Path], cache_data: Dict[str, Any]) -> None:
    """Cache verisini güvenli şekilde kaydeder."""
    save_json_atomic(path, cache_data)
