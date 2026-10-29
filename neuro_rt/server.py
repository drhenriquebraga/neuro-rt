import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .service import Service, Settings

PREFIX = '/neuro/'


def make_server(service, port=8766):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Caminhos de estudos não entram no log HTTP.

        def reply(self, code, value):
            data = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            return self.headers.get('Host', '') in (
                f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {'error': 'Host não permitido.'})
            url = urlsplit(self.path)
            route = url.path.removeprefix(PREFIX)
            try:
                if url.path == '/':
                    self.send_response(302)
                    self.send_header('Location', PREFIX)
                    self.end_headers()
                    return
                if route == 'api/status':
                    return self.reply(200, service.status())
                if route.startswith('api/demos/') and len(route.split('/')) == 3:
                    return self.reply(200, service.demo(route.split('/')[2]))
                if route.startswith('api/jobs/'):
                    parts = route.split('/')
                    if len(parts) == 3:
                        return self.reply(200, service.job(parts[2]))
                    if len(parts) == 5 and parts[3] == 'artifacts':
                        return self.file(service.artifact(parts[2], parts[4]), download=True)
                    if len(parts)==5 and parts[3]=='views':
                        return self.file(service.view_file(parts[2],parts[4]))
                if route == 'api/series':
                    from .imaging import dicom_series
                    path = parse_qs(url.query).get('path', [''])[0]
                    if not path or not Path(path).is_dir():
                        raise ValueError('Informe uma pasta DICOM existente.')
                    return self.reply(200, {'series': dicom_series(path)})
                if url.path.startswith(PREFIX) and route in ('', 'index.html', 'app.js', 'style.css','mesh-view.html','mesh-view.js','mesh-view.css','viewer.js','bibliografia.html'):
                    return self.file(service.settings.root / 'web' / (route or 'index.html'))
                return self.reply(404, {'error': 'Rota não encontrada.'})
            except (KeyError, FileNotFoundError):
                return self.reply(404, {'error': 'Resultado não encontrado.'})
            except ValueError as exc:
                return self.reply(400, {'error': str(exc)})
            except Exception:
                return self.reply(500, {'error': 'Não foi possível concluir a leitura local.'})

        def file(self, path, download=False):
            data = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if download:
                self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
            else:
                self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'self'; connect-src 'self'")
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if (not self.valid_host() or self.headers.get('Origin') not in
                (None, f"http://{self.headers.get('Host')}") or
                self.headers.get('X-Neuro-Token') != service.token):
                return self.reply(403, {'error': 'Origem ou token inválido.'})
            if urlsplit(self.path).path != PREFIX + 'api/jobs':
                return self.reply(404, {'error': 'Rota não encontrada.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    raise ValueError('Pedido JSON inválido.')
                request = json.loads(self.rfile.read(length))
                return self.reply(202, service.submit(request))
            except (ValueError, TypeError) as exc:
                return self.reply(400, {'error': str(exc)})
            except RuntimeError as exc:
                return self.reply(409, {'error': str(exc)})
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    service = Service(Settings(args.root))
    server = make_server(service, args.port)
    print(f'NeuroRT disponível em http://127.0.0.1:{server.server_port}/neuro/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()


if __name__ == '__main__':
    main()
