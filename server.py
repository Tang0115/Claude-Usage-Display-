import http.server
import socketserver
import os

# Serve files from the clawd-dash directory
os.chdir('/home/tang0115/clawd-dash')

PORT = 8080
handler = http.server.SimpleHTTPRequestHandler
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Serving on port {PORT}")
    httpd.serve_forever()
