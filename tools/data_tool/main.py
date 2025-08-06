# tools/data_tool/main.py

from typer import Typer
from config.config_loader import load_config

from tools.data_tool.ops.product_add import cmd_product_add

app = Typer(help="Dukkans data ops CLI")

@app.command()
def info():
    """
    Konfigleri yükler ve kısa bir özet basar.
    """
    cfg = load_config()
    shops = ", ".join(cfg["shops"].keys())
    cats = ", ".join(cfg["categories"].keys())
    has_key = "OK" if (cfg.get("env", {}).get("GOOGLE_API_KEY")) else "MISSING"
    print(f"Shops: {shops}")
    print(f"Categories: {cats}")
    print(f"GOOGLE_API_KEY: {has_key}")


app.command(name="product-add")(cmd_product_add)

if __name__ == "__main__":
    app()
