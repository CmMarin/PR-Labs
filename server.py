#!/usr/bin/env python3
"""
HTTP File Server - Lab 2
Concurrent HTTP server with request counters and per-IP rate limiting.
"""

import argparse
import math
import os
import socket
import sys
import threading
import time
import urllib.parse
from collections import defaultdict, deque
from datetime import datetime


class HTTPServer:
    def __init__(
        self,
        host='0.0.0.0',
        port=8080,
        root_dir='./content',
        handler_delay=0.0,
        use_counter_lock=True,
        counter_delay=0.0,
        rate_limit=5,
        rate_window=1.0,
    ):
        self.host = host
        self.port = port
        self.root_dir = os.path.abspath(root_dir)
        self.handler_delay = max(0.0, handler_delay)
        self.use_counter_lock = use_counter_lock
        self.counter_delay = max(0.0, counter_delay)
        self.rate_limit = max(1, rate_limit)
        self.rate_window = max(0.1, rate_window)

        self.mime_types = {
            '.html': 'text/html',
            '.htm': 'text/html',
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
        }

        self.request_counts = defaultdict(int)
        self.counter_lock = threading.Lock()
        self.rate_lock = threading.Lock()
        self.client_windows = defaultdict(deque)

    def get_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(('8.8.8.8', 80))
                return sock.getsockname()[0]
        except Exception:
            return '127.0.0.1'

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(64)

            local_ip = self.get_local_ip()

            print('=' * 60)
            print('Concurrent File Server - READY')
            print('=' * 60)
            print(f'Server binding: {self.host}:{self.port}')
            print(f'Serving directory: {self.root_dir}')
            print(f'Handler delay: {self.handler_delay:.2f}s | Counter lock: {self.use_counter_lock}')
            print(f'Rate limit: {self.rate_limit} requests/{self.rate_window:.2f}s')
            print()
            print('Access URLs:')
            print(f'  Local:   http://localhost:{self.port}')
            print(f'  Network: http://{local_ip}:{self.port}')
            print()
            print('Press Ctrl+C to stop the server')
            print('=' * 60)

            while True:
                client_socket, client_address = server_socket.accept()
                worker = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True,
                )
                worker.start()

        except KeyboardInterrupt:
            print('\nServer stopped by user')
        except Exception as exc:
            print(f'Server error: {exc}')
        finally:
            server_socket.close()

    def handle_client(self, client_socket, client_address):
        try:
            allowed, retry_after, remaining = self.check_rate_limit(client_address[0])
            if not allowed:
                headers = self.build_rate_headers(remaining=None)
                headers['Retry-After'] = str(max(1, math.ceil(retry_after)))
                self.send_error_response(
                    client_socket,
                    429,
                    'Too Many Requests',
                    message='Rate limit exceeded. Please retry later.',
                    extra_headers=headers,
                )
                return

            rate_headers = self.build_rate_headers(remaining)
            self.handle_request(client_socket, client_address, rate_headers)

        except Exception as exc:
            print(f'Error handling connection {client_address}: {exc}')
        finally:
            client_socket.close()

    def handle_request(self, client_socket, client_address, extra_headers):
        request_data = client_socket.recv(4096).decode('utf-8', errors='ignore')
        if not request_data:
            return

        request_lines = request_data.split('\n')
        request_line = request_lines[0].strip()
        if not request_line:
            return

        try:
            method, path, _ = request_line.split()
        except ValueError:
            self.send_error_response(
                client_socket,
                400,
                'Bad Request',
                message='Malformed request line.',
                extra_headers=extra_headers,
            )
            return

        if method != 'GET':
            self.send_error_response(
                client_socket,
                405,
                'Method Not Allowed',
                message='Only GET is supported.',
                extra_headers=extra_headers,
            )
            return

        print(f'Request from {client_address}: {method} {path}')

        path = urllib.parse.unquote(path)
        if '?' in path:
            path = path.split('?', 1)[0]

        if self.handler_delay:
            time.sleep(self.handler_delay)

        if path == '/':
            path = '/index.html'

        file_path = os.path.join(self.root_dir, path.lstrip('/'))
        file_path = os.path.abspath(file_path)

        if not file_path.startswith(self.root_dir):
            self.send_error_response(
                client_socket,
                403,
                'Forbidden',
                message='Access denied.',
                extra_headers=extra_headers,
            )
            return

        if not os.path.exists(file_path):
            self.send_error_response(
                client_socket,
                404,
                'Not Found',
                message='The requested resource was not found.',
                extra_headers=extra_headers,
            )
            return

        is_directory = os.path.isdir(file_path)
        counter_key = self.normalize_counter_key(file_path, is_directory)
        self.increment_counter(counter_key)

        if is_directory:
            self.send_directory_listing(client_socket, file_path, path, extra_headers)
        else:
            self.send_file(client_socket, file_path, extra_headers)

    def send_file(self, client_socket, file_path, extra_headers):
        try:
            _, ext = os.path.splitext(file_path)
            content_type = self.mime_types.get(ext.lower(), 'application/octet-stream')

            if ext.lower() not in self.mime_types:
                self.send_error_response(
                    client_socket,
                    415,
                    'Unsupported Media Type',
                    message='File type is not supported.',
                    extra_headers=extra_headers,
                )
                return

            if content_type.startswith('text/'):
                with open(file_path, 'r', encoding='utf-8') as handle:
                    content_bytes = handle.read().encode('utf-8')
            else:
                with open(file_path, 'rb') as handle:
                    content_bytes = handle.read()

            headers = self.build_headers(
                200,
                'OK',
                content_type,
                len(content_bytes),
                extra_headers=extra_headers,
            )
            client_socket.send(headers.encode('utf-8'))
            client_socket.send(content_bytes)
            print(f'Sent file: {file_path} ({len(content_bytes)} bytes)')

        except Exception as exc:
            print(f'Error sending file {file_path}: {exc}')
            self.send_error_response(
                client_socket,
                500,
                'Internal Server Error',
                message='Unexpected server error.',
                extra_headers=extra_headers,
            )

    def send_directory_listing(self, client_socket, dir_path, url_path, extra_headers):
        try:
            files = []
            dirs = []

            for item in sorted(os.listdir(dir_path)):
                item_path = os.path.join(dir_path, item)
                if os.path.isdir(item_path):
                    dirs.append(item)
                else:
                    files.append(item)

            dir_entries = []
            for dir_name in dirs:
                relative = os.path.join(dir_path, dir_name)
                key = self.normalize_counter_key(relative, is_directory=True)
                count = self.get_request_count(key)
                href = url_path.rstrip('/') + '/' + dir_name + '/'
                dir_entries.append((dir_name + '/', href, count))

            file_entries = []
            for file_name in files:
                relative = os.path.join(dir_path, file_name)
                key = self.normalize_counter_key(relative, is_directory=False)
                count = self.get_request_count(key)
                href = url_path.rstrip('/') + '/' + file_name if url_path != '/' else '/' + file_name
                file_entries.append((file_name, href, count, self.get_file_type_display(file_name)))

            html_content = self.build_directory_html(url_path, dir_entries, file_entries)
            content_bytes = html_content.encode('utf-8')

            headers = self.build_headers(
                200,
                'OK',
                'text/html',
                len(content_bytes),
                extra_headers=extra_headers,
            )
            client_socket.send(headers.encode('utf-8'))
            client_socket.send(content_bytes)
            print(f'Sent directory listing: {dir_path}')

        except Exception as exc:
            print(f'Error sending directory listing {dir_path}: {exc}')
            self.send_error_response(
                client_socket,
                500,
                'Internal Server Error',
                message='Unexpected server error.',
                extra_headers=extra_headers,
            )

    def build_directory_html(self, url_path, dir_entries, file_entries):
        if not url_path.endswith('/'):
            url_path += '/'

        html = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            f'    <title>Directory: {url_path}</title>',
            '    <style>',
            '        body { font-family: Arial; margin: 20px; background: white; color: black; }',
            '        a { color: blue; text-decoration: none; }',
            '        a:hover { text-decoration: underline; }',
            '        .path { background: #f0f0f0; padding: 10px; margin: 10px 0; }',
            '        ul { list-style: none; padding: 0; }',
            '        li { margin: 5px 0; padding: 5px; border-bottom: 1px solid #ddd; }',
            '        .count { color: #333; font-size: 0.85rem; margin-left: 10px; }',
            '    </style>',
            '</head>',
            '<body>',
            '    <h1>Directory Listing</h1>',
            f'    <div class="path">Path: {url_path}</div>',
            '    <ul>',
        ]

        if url_path != '/':
            parent_path = '/'.join(url_path.rstrip('/').split('/')[:-1]) + '/'
            if parent_path == '//':
                parent_path = '/'
            html.append(f'        <li><a href="{parent_path}">.. (Parent Directory)</a></li>')

        for name, href, count in dir_entries:
            html.append(
                f'        <li><a href="{href}">{name}</a> - Directory <span class="count">Requests: {count}</span></li>'
            )

        for name, href, count, file_type in file_entries:
            html.append(
                f'        <li><a href="{href}">{name}</a> - {file_type} <span class="count">Requests: {count}</span></li>'
            )

        html.extend([
            '    </ul>',
            '    <p>Concurrent File Server</p>',
            '</body>',
            '</html>',
        ])

        return '\n'.join(html)

    def get_file_type_display(self, filename):
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        types = {
            '.html': 'webpage',
            '.htm': 'webpage',
            '.png': 'image',
            '.pdf': 'document',
            '.txt': 'text',
        }

        return types.get(ext, 'file')

    def send_error_response(self, client_socket, status_code, status_text, message=None, extra_headers=None):
        body = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            f'    <title>Error {status_code}</title>',
            '    <style>',
            '        body { font-family: Arial; margin: 20px; background: white; color: black; text-align: center; }',
            '        a { color: blue; text-decoration: none; }',
            '        a:hover { text-decoration: underline; }',
            '    </style>',
            '</head>',
            '<body>',
            f'    <h1>Error {status_code}</h1>',
            f'    <h2>{status_text}</h2>',
            f'    <p>{message or "Unable to process the request."}</p>',
            '    <p><a href="/">Back to Home</a></p>',
            '    <p>Concurrent File Server</p>',
            '</body>',
            '</html>',
        ]
        content_bytes = '\n'.join(body).encode('utf-8')
        headers = self.build_headers(
            status_code,
            status_text,
            'text/html',
            len(content_bytes),
            extra_headers=extra_headers,
        )

        try:
            client_socket.send(headers.encode('utf-8'))
            client_socket.send(content_bytes)
            print(f'Sent error response: {status_code} {status_text}')
        except Exception:
            pass

    def build_headers(self, status_code, status_text, content_type, content_length, extra_headers=None):
        lines = [
            f'HTTP/1.1 {status_code} {status_text}',
            f'Date: {datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")}',
            'Server: ConcurrentHTTPServer/2.0',
            f'Content-Type: {content_type}',
            f'Content-Length: {content_length}',
            'Connection: close',
        ]

        if extra_headers:
            for key, value in extra_headers.items():
                lines.append(f'{key}: {value}')

        lines.append('')
        lines.append('')
        return '\r\n'.join(lines)

    def normalize_counter_key(self, absolute_path, is_directory):
        relative = os.path.relpath(absolute_path, self.root_dir)
        relative = relative.replace('\\', '/')
        if relative in ('.', ''):
            relative = ''
        if not relative.startswith('/'):
            relative = '/' + relative if relative else '/'
        if is_directory and not relative.endswith('/'):
            relative += '/'
        if not is_directory and relative.endswith('/'):
            relative = relative.rstrip('/')
        return relative or '/'

    def increment_counter(self, key):
        if self.use_counter_lock:
            with self.counter_lock:
                if self.counter_delay:
                    time.sleep(self.counter_delay)
                self.request_counts[key] += 1
        else:
            current = self.request_counts[key]
            if self.counter_delay:
                time.sleep(self.counter_delay)
            self.request_counts[key] = current + 1

    def get_request_count(self, key):
        if self.use_counter_lock:
            with self.counter_lock:
                return self.request_counts.get(key, 0)
        return self.request_counts.get(key, 0)

    def check_rate_limit(self, client_ip):
        now = time.time()
        with self.rate_lock:
            window = self.client_windows[client_ip]
            while window and now - window[0] > self.rate_window:
                window.popleft()
            if len(window) >= self.rate_limit:
                retry_after = self.rate_window - (now - window[0]) if window else self.rate_window
                return False, max(0.0, retry_after), self.rate_limit - len(window)
            window.append(now)
            remaining = self.rate_limit - len(window)
            return True, 0.0, remaining

    def build_rate_headers(self, remaining):
        headers = {
            'X-RateLimit-Limit': str(self.rate_limit),
            'X-RateLimit-Window': f'{self.rate_window:.2f}',
        }
        if remaining is not None:
            headers['X-RateLimit-Remaining'] = str(max(0, remaining))
        return headers


def parse_args():
    parser = argparse.ArgumentParser(description='Concurrent HTTP file server for Lab 2.')
    parser.add_argument('directory', help='Directory to serve.')
    parser.add_argument('--host', default='0.0.0.0', help='Interface to bind. Default: 0.0.0.0')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind. Default: 8080')
    parser.add_argument('--delay', type=float, default=0.0, help='Artificial handler delay in seconds.')
    parser.add_argument(
        '--counter-mode',
        choices=['safe', 'naive'],
        default='safe',
        help='Use thread-safe counters (safe) or deliberately unsafe counters (naive).',
    )
    parser.add_argument(
        '--counter-delay',
        type=float,
        default=0.0,
        help='Artificial delay when updating counters to highlight races.',
    )
    parser.add_argument('--rate-limit', type=int, default=5, help='Allowed requests per window per IP.')
    parser.add_argument('--rate-window', type=float, default=1.0, help='Window size in seconds for rate limiting.')
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        sys.exit(1)

    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory")
        sys.exit(1)

    server = HTTPServer(
        host=args.host,
        port=args.port,
        root_dir=args.directory,
        handler_delay=args.delay,
        use_counter_lock=(args.counter_mode == 'safe'),
        counter_delay=args.counter_delay,
        rate_limit=args.rate_limit,
        rate_window=args.rate_window,
    )
    server.start()


if __name__ == '__main__':
    main()
