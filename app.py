from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import os

SITE_DIR = Path(__file__).resolve().parent / "site"


def serve(host: str, port: int) -> None:
    if not SITE_DIR.exists():
        raise SystemExit("site/ folder not found. Add your built files first.")
    os.chdir(SITE_DIR)
    httpd = ThreadingHTTPServer((host, port), SimpleHTTPRequestHandler)
    print(f"Serving on http://{host}:{port}")
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the restaurant site.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
