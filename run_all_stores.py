# run_all_stores.py
import os
import sys
import time
import subprocess
import threading
import webbrowser
import signal
import http.server
import socketserver
import socket
from functools import partial
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
os.chdir(ROOT)

SHOPS = {
    "ecommerce1": {"port": 8001, "name": "Store 1"},
    "ecommerce2": {"port": 8002, "name": "Store 2"},
    "ecommerce3": {"port": 8003, "name": "Store 3"},
}

processes = {}
running = True


def stop_all():
    global running
    running = False
    print("\nTüm store'lar kapatılıyor...")
    for name, proc in list(processes.items()):
        try:
            proc.terminate()
            print(f" {name} kapatıldı")
        except Exception:
            pass


def signal_handler(sig, frame):
    stop_all()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

class SimpleHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """CORS + no-cache + JS içinde BASE_URL auto-rewrite."""

    def __init__(self, *args, backend_port=None, directory=None, **kwargs):
        self.backend_port = backend_port
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Access-Control-Allow-Headers", "*")

        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):

        if self.path in ("/", "/index.html"):
            print(f" [{self.server.server_address[1]}] index serve → {self.directory}")

        if self.path.endswith(".js") and "/js/" in self.path:
            try:
                file_path = self.translate_path(self.path)
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    print(f" [{self.server.server_address[1]}] JS patch: {self.path}")
                    replacements = [
                        ("http://127.0.0.1:8001", f"http://127.0.0.1:{self.backend_port}"),
                        ('"http://127.0.0.1:8001"', f'"http://127.0.0.1:{self.backend_port}"'),
                        ("'http://127.0.0.1:8001'", f"'http://127.0.0.1:{self.backend_port}'"),
                        (
                            'const BASE_URL = "http://127.0.0.1:8001"',
                            f'const BASE_URL = "http://127.0.0.1:{self.backend_port}"',
                        ),
                    ]
                    for old, new in replacements:
                        if old in content:
                            content = content.replace(old, new)
                            print(f" {old} → {new}")

                    self.send_response(200)
                    self.send_header("Content-Type", "application/javascript; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))
                    return
            except Exception as e:
                print(f"JS patch hatası: {e}")

        super().do_GET()


def start_backend(shop_name, port):
    backend_dir = ROOT / "dukkans" / shop_name / "backend"
    main_py = backend_dir / "main.py"

    print(f"{shop_name} Backend başlatılıyor...")
    print(f"Dir: {backend_dir}")
    print(f"File: {main_py} | Exists: {main_py.exists()}")

    if not main_py.exists():
        print(f" {shop_name} main.py bulunamadı!")
        return None

    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--reload",
            ],
            cwd=str(backend_dir),
        )

        for _ in range(25):
            try:
                sock = socket.socket()
                sock.settimeout(1)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()
                if result == 0:
                    print(f" {shop_name} Backend hazır → http://localhost:{port}")
                    return proc
                time.sleep(0.4)
            except Exception:
                time.sleep(0.4)

        print(f" {shop_name} Backend başlatılamadı")
        proc.terminate()
        return None

    except Exception as e:
        print(f" {shop_name} Backend hatası: {e}")
        return None


def start_frontend(shop_name, backend_port):
    frontend_dir = ROOT / "dukkans" / shop_name / "frontend" / "src"
    frontend_port = backend_port + 100  # 8001→8101, 8002→8102, 8003→8103

    print(f" {shop_name} Frontend başlatılıyor...")
    print(f"   Dir: {frontend_dir} | Exists: {frontend_dir.exists()}")
    print(f"    Port: {frontend_port} | Backend: {backend_port}")

    if not frontend_dir.exists():
        print(f" {shop_name} frontend dizini bulunamadı!")
        return None

    def run_server():
        Handler = partial(
            SimpleHTTPHandler, backend_port=backend_port, directory=str(frontend_dir)
        )
        with http.server.ThreadingHTTPServer(("", frontend_port), Handler) as server:
            print(
                f" {shop_name} Frontend hazır : http://localhost:{frontend_port}  | dir={frontend_dir}"
            )
            server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread


def main():
    print("\n SocialScanAI Dukkan Demolar\n=====================================\n")

    for shop_name, cfg in SHOPS.items():
        port = cfg["port"]
        print(f"\n {shop_name.upper()} — {cfg['name']}\n" + "-" * 40)
        backend_proc = start_backend(shop_name, port)
        if backend_proc:
            processes[f"{shop_name}_backend"] = backend_proc
            start_frontend(shop_name, port)
            time.sleep(1.0)

    print("\n PLATFORM HAZIR!\n-----------\n\n Store Links:\n")
    urls = []
    for shop_name, cfg in SHOPS.items():
        p = cfg["port"] + 100
        print(f" {cfg['name']}: http://localhost:{p}")
        urls.append(f"http://localhost:{p}")

    print("\n Backend APIs:\n")
    for shop_name, cfg in SHOPS.items():
        print(f" {cfg['name']}: http://localhost:{cfg['port']}")
    print("\n Kullanım:\n• Ctrl+C - Tüm servisleri durdur\n• Browser'da yukarıdaki linkleri açın")

    try:
        choice = input("Store'ları otomatik açmak ister misiniz? (y/n): ").lower()
        if choice in ["y", "yes", "evet", ""]:
            ts = int(time.time())
            for url in urls:
                webbrowser.open(f"{url}?t={ts}")
                time.sleep(0.5)
    except Exception:
        pass

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()


if __name__ == "__main__":
    main()
