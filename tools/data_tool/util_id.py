# Bu fonksiyon, kategori bazlı yeni bir ID oluşturur
# tools/data_tool/util_id.py

def generate_new_id(existing_ids: list[str], prefix: str = "ayk_") -> str:
    nums = [
        int(i.split("_")[1]) for i in existing_ids
        if i.startswith(prefix) and i.split("_")[1].isdigit()
    ]
    next_num = max(nums, default=0) + 1
    return f"{prefix}{str(next_num).zfill(2)}"
