#!/usr/bin/env python3

"""Deterministic local HTTP fixture used instead of third-party targets (httpbin.org, pastebin.com, ...)."""

import http.server
import socketserver
import threading
import time

RFI_PROGRAM = """import re, subprocess, urllib.parse
params = dict((match.group("parameter"), urllib.parse.unquote(match.group("value"))) for match in re.finditer(r"((\\A|[?&])(?P<parameter>[\\w\\[\\]]+)=)(?P<value>[^&]+)", QUERY_STRING))
if "cmd" in params:
    print("<pre>%s</pre>" % subprocess.check_output(params["cmd"], shell=True, stderr=subprocess.STDOUT).decode())
"""

SLOW_PROGRAM = """import time
time.sleep(%f)
print("SLOW-DONE")
"""

BINARY_CONTENT = b"\x00\xff\xfe\x80binary-marker\x00\x1b"


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    slow_delay = 1.2

    def log_message(self, *args):
        pass

    def _respond(self, code, content, content_type="text/plain"):
        body = content if isinstance(content, bytes) else content.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        agent = self.headers.get("User-Agent") or ""
        if path == "/hello.txt":
            self._respond(200, "Hello, fixture!")
        elif path == "/xxe.txt":
            self._respond(200, "XXE-REMOTE-OK")
        elif path == "/binary.bin":
            self._respond(200, BINARY_CONTENT, "application/octet-stream")
        elif path == "/rfi.py":
            self._respond(200, RFI_PROGRAM)
        elif path == "/slow.py":
            self._respond(200, SLOW_PROGRAM % self.slow_delay)
        elif path == "/ua-guard.py":                                    # mimics hosts (e.g. pastebin.com) rejecting 'Python-urllib'
            self._respond(200, RFI_PROGRAM) if agent.startswith("Mozilla/") else self._respond(403, "Forbidden\n")
        elif path == "/ua-guard.txt":
            self._respond(200, "UA-GUARD-OK") if agent.startswith("Mozilla/") else self._respond(403, "Forbidden\n")
        else:
            self._respond(404, "Not Found\n")


class FixtureServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start(address="127.0.0.1"):
    server = FixtureServer((address, 0), FixtureHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://%s:%d" % (address, server.server_address[1])


if __name__ == "__main__":
    server, url = start()
    print("[i] fixture running at '%s'" % url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
