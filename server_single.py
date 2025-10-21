#!/usr/bin/env python3
"""
HTTP File Server - Lab 1 (single-threaded baseline)
A simple HTTP file server using TCP sockets that serves files from a specified directory.
This version preserves the original Lab 1 behaviour for comparison with the concurrent server.
"""

import argparse
import socket
import os
import sys
import urllib.parse
import mimetypes
import time
from datetime import datetime


class HTTPServer:
    def __init__(self, host='0.0.0.0', port=8080, root_dir='./content', handler_delay=0.0):
        self.host = host
        self.port = port
        self.root_dir = os.path.abspath(root_dir)
        self.handler_delay = max(0.0, handler_delay)
        
        # Supported MIME types
        self.mime_types = {
            '.html': 'text/html',
            '.htm': 'text/html',
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain'
        }
    
    def get_local_ip(self):
        """Get the local IP address"""
        try:
            # Create a temporary socket to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to a remote address (doesn't need to be reachable)
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception:
            return '127.0.0.1'
    
    def start(self):
        """Start the HTTP server"""
        # Create socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # Bind and listen
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            
            # Get local IP for network access
            local_ip = self.get_local_ip()
            
            print("=" * 60)
            print(f"DevPortal File Server - READY")
            print("=" * 60)
            print(f"Server binding: {self.host}:{self.port}")
            print(f"Serving directory: {self.root_dir}")
            print()
            print("Access URLs:")
            print(f"  Local:   http://localhost:{self.port}")
            print(f"  Network: http://{local_ip}:{self.port}")
            print()
            print("Press Ctrl+C to stop the server")
            print("=" * 60)
            
            while True:
                # Accept client connection
                client_socket, client_address = server_socket.accept()
                print(f"Connection from {client_address}")
                
                try:
                    self.handle_request(client_socket)
                except Exception as e:
                    print(f"Error handling request: {e}")
                finally:
                    client_socket.close()
                    
        except KeyboardInterrupt:
            print("\nServer stopped by user")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            server_socket.close()
    
    def handle_request(self, client_socket):
        """Handle HTTP request from client"""
        # Receive request
        request_data = client_socket.recv(1024).decode('utf-8')
        if not request_data:
            return
        
        if self.handler_delay:
            time.sleep(self.handler_delay)

        # Parse request
        request_lines = request_data.split('\n')
        request_line = request_lines[0].strip()
        
        if not request_line:
            return
        
        # Parse HTTP method and path
        try:
            method, path, version = request_line.split()
        except ValueError:
            self.send_error_response(client_socket, 400, "Bad Request")
            return
        
        if method != 'GET':
            self.send_error_response(client_socket, 405, "Method Not Allowed")
            return
        
        print(f"Request: {method} {path}")
        
        # Decode URL path
        path = urllib.parse.unquote(path)
        
        # Remove query parameters
        if '?' in path:
            path = path.split('?')[0]
        
        # Handle root path
        if path == '/':
            path = '/index.html'
        
        # Get absolute file path
        file_path = os.path.join(self.root_dir, path.lstrip('/'))
        file_path = os.path.abspath(file_path)
        
        # Security check: ensure file is within root directory
        if not file_path.startswith(self.root_dir):
            self.send_error_response(client_socket, 403, "Forbidden")
            return
        
        # Check if path exists
        if not os.path.exists(file_path):
            self.send_error_response(client_socket, 404, "Not Found")
            return
        
        # Handle directory
        if os.path.isdir(file_path):
            self.send_directory_listing(client_socket, file_path, path)
        else:
            # Handle file
            self.send_file(client_socket, file_path)
    
    def send_file(self, client_socket, file_path):
        """Send file to client"""
        try:
            # Get file extension and MIME type
            _, ext = os.path.splitext(file_path)
            content_type = self.mime_types.get(ext.lower(), 'application/octet-stream')
            
            # Check if file extension is supported
            if ext.lower() not in self.mime_types:
                self.send_error_response(client_socket, 415, "Unsupported Media Type")
                return
            
            # Read file content
            if content_type.startswith('text/'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                content_bytes = content.encode('utf-8')
            else:
                with open(file_path, 'rb') as f:
                    content_bytes = f.read()
            
            # Send response
            response_headers = self.build_headers(200, "OK", content_type, len(content_bytes))
            client_socket.send(response_headers.encode('utf-8'))
            client_socket.send(content_bytes)
            
            print(f"Sent file: {file_path} ({len(content_bytes)} bytes)")
            
        except Exception as e:
            print(f"Error sending file {file_path}: {e}")
            self.send_error_response(client_socket, 500, "Internal Server Error")
    
    def send_directory_listing(self, client_socket, dir_path, url_path):
        """Send directory listing as HTML"""
        try:
            # Get directory contents
            files = []
            dirs = []
            
            for item in sorted(os.listdir(dir_path)):
                item_path = os.path.join(dir_path, item)
                if os.path.isdir(item_path):
                    dirs.append(item)
                else:
                    files.append(item)
            
            # Build HTML content
            html_content = self.build_directory_html(url_path, dirs, files)
            content_bytes = html_content.encode('utf-8')
            
            # Send response
            response_headers = self.build_headers(200, "OK", "text/html", len(content_bytes))
            client_socket.send(response_headers.encode('utf-8'))
            client_socket.send(content_bytes)
            
            print(f"Sent directory listing: {dir_path}")
            
        except Exception as e:
            print(f"Error sending directory listing {dir_path}: {e}")
            self.send_error_response(client_socket, 500, "Internal Server Error")
    
    def build_directory_html(self, url_path, dirs, files):
        """Build minimal HTML for directory listing"""
        # Ensure url_path ends with /
        if not url_path.endswith('/'):
            url_path += '/'
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Directory: {url_path}</title>
    <style>
        body {{
            font-family: Arial;
            margin: 20px;
            background: white;
            color: black;
        }}
        a {{
            color: blue;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .path {{
            background: #f0f0f0;
            padding: 10px;
            margin: 10px 0;
        }}
        ul {{
            list-style: none;
            padding: 0;
        }}
        li {{
            margin: 5px 0;
            padding: 5px;
            border-bottom: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <h1>Directory Listing</h1>
    <div class="path">Path: {url_path}</div>
    <ul>
"""
        
        # Add parent directory link if not root
        if url_path != '/':
            parent_path = '/'.join(url_path.rstrip('/').split('/')[:-1]) + '/'
            if parent_path == '/':
                parent_path = '/'
            html += f'        <li><a href="{parent_path}">.. (Parent Directory)</a></li>\n'
        
        # Add directories
        for dir_name in dirs:
            dir_url = url_path + dir_name + '/'
            html += f'        <li><a href="{dir_url}">{dir_name}/</a> - Directory</li>\n'
        
        # Add files
        for file_name in files:
            file_url = url_path + file_name
            file_type = self.get_file_type_display(file_name)
            html += f'        <li><a href="{file_url}">{file_name}</a> - {file_type}</li>\n'
        
        html += """    </ul>
    <p>File Server</p>
</body>
</html>"""
        
        return html
    
    def get_file_type_display(self, filename):
        """Get file type display name"""
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        types = {
            '.html': 'webpage',
            '.htm': 'webpage',
            '.png': 'image',
            '.pdf': 'document',
            '.txt': 'text'
        }
        
        return types.get(ext, 'file')
    
    def send_error_response(self, client_socket, status_code, status_text):
        """Send HTTP error response"""
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Error {status_code}</title>
    <style>
        body {{
            font-family: Arial;
            margin: 20px;
            background: white;
            color: black;
            text-align: center;
        }}
        a {{
            color: blue;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <h1>Error {status_code}</h1>
    <h2>{status_text}</h2>
    <p>The requested resource could not be found.</p>
    <p><a href="/">Back to Home</a></p>
    <p>File Server</p>
</body>
</html>"""
        
        content_bytes = html_content.encode('utf-8')
        response_headers = self.build_headers(status_code, status_text, "text/html", len(content_bytes))
        
        try:
            client_socket.send(response_headers.encode('utf-8'))
            client_socket.send(content_bytes)
            print(f"Sent error response: {status_code} {status_text}")
        except:
            pass
    
    def build_headers(self, status_code, status_text, content_type, content_length):
        """Build HTTP response headers"""
        headers = f"""HTTP/1.1 {status_code} {status_text}\r
Date: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r
Server: HTTPServer/1.0\r
Content-Type: {content_type}\r
Content-Length: {content_length}\r
Connection: close\r
\r
"""
        return headers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-threaded HTTP file server (Lab 1 baseline).")
    parser.add_argument("directory", help="Directory to serve.")
    parser.add_argument("--host", default="0.0.0.0", help="Interface to bind. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind. Default: 8080")
    parser.add_argument("--delay", type=float, default=0.0, help="Artificial handler delay in seconds.")
    return parser.parse_args()


def main():
    """Main function"""
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
    )
    server.start()


if __name__ == "__main__":
    main()
