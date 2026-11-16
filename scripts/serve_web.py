"""Mở web hỏi tài liệu tại localhost; không cung cấp file ngoài thư mục web."""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.web_app import Application

STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "application/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


class Handler(BaseHTTPRequestHandler):
    def send(self, status, data, content_type="application/json; charset=utf-8"):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if isinstance(data, (dict, list)) else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        params=parse_qs(urlsplit(self.path).query)
        dataset=params.get("dataset",["basic"])[0]
        try:
            if dataset not in ("basic","advanced"):raise ValueError("Tài liệu không hợp lệ.")
            if path in STATIC:
                name, mime = STATIC[path]
                self.send(200, (ROOT / "web" / name).read_bytes(), mime)
            elif path == "/api/status":
                self.send(200, self.server.application.status())
            elif path == "/api/examples":
                self.send(200, self.server.application.examples(dataset))
            elif path == "/api/results":
                self.send(200, self.server.application.results(dataset))
            elif path=="/api/page":
                self.send(200,self.server.application.page_image(int(params.get("page",["0"])[0])),"image/jpeg")
            else:
                self.send(404, {"error": "Không có trang này."})
        except ValueError as error:
            self.send(400,{"error":str(error)})
        except Exception:
            self.send(503, {"error": "Dữ liệu đang được cập nhật. Vui lòng thử lại."})

    def do_POST(self):
        if self.path != "/api/ask":
            self.send(404, {"error": "Không có API này."})
            return
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed:
            self.send(403, {"error": "Chỉ nhận yêu cầu từ giao diện local."})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.send(415, {"error": "Cần gửi JSON."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 20000:
                raise ValueError("Yêu cầu quá dài hoặc rỗng.")
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            self.send(200, self.server.application.ask(payload))
        except (ValueError, json.JSONDecodeError) as error:
            self.send(400, {"error": str(error)})
        except RuntimeError as error:
            self.send(409, {"error": str(error)})
        except Exception:
            self.send(500, {"error": "Không xử lý được câu hỏi. Kiểm tra database hoặc log máy chủ."})

    def log_message(self, format, *args):
        print(format % args, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    app = Application(args.day6.resolve())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.application = app
    print(f"Web local: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
