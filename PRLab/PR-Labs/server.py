#!/usr/bin/env python3
"""
HTTP File Server - Lab 1
A simple HTTP file server using TCP sockets that serves files from a specified directory.
Supports HTML, PNG, and PDF files with directory listing capability.
"""

# I forgot to push this one, fix

import socket
import os
import sys
import urllib.parse
import mimetypes
from datetime import datetime


class HTTPServer:
    def __init__(self, host='0.0.0.0', port=8080, root_dir='./content'):
        self.host = host
        self.port = port
        self.root_dir = os.path.abspath(root_dir)
        
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
    
    def build_directory_html_old(self, url_path, dirs, files):
        """Build HTML for directory listing"""
        # Ensure url_path ends with /
        if not url_path.endswith('/'):
            url_path += '/'
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Directory: {url_path}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #ffffff;
            min-height: 100vh;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 40px;
            position: relative;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: -15px;
            left: 50%;
            transform: translateX(-50%);
            width: 80px;
            height: 3px;
            background: linear-gradient(90deg, #8b5cf6, #a855f7, #c084fc);
            border-radius: 2px;
        }}
        
        h1 {{ 
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #8b5cf6, #c084fc, #ffffff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }}
        
        .controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 20px 0;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        .path-display {{
            background: rgba(139, 92, 246, 0.1);
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
            font-family: 'Consolas', 'Monaco', monospace;
            color: #c084fc;
            font-size: 0.9rem;
            flex: 1;
            min-width: 200px;
        }}
        
        .view-toggle {{
            display: flex;
            background: rgba(139, 92, 246, 0.1);
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .toggle-btn {{
            background: transparent;
            border: none;
            color: #c084fc;
            padding: 10px 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }}
        
        .toggle-btn.active {{
            background: rgba(139, 92, 246, 0.3);
            color: #ffffff;
        }}
        
        .toggle-btn:hover {{
            background: rgba(139, 92, 246, 0.2);
        }}
        
        .items-grid {{
            display: none;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .items-list {{
            display: none;
            margin: 30px 0;
        }}
        
        .items-list.active {{
            display: block;
        }}
        
        .items-grid.active {{
            display: grid;
        }}
        
        .item-card {{
            background: rgba(139, 92, 246, 0.08);
            border: 1px solid rgba(139, 92, 246, 0.2);
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .item-row {{
            display: flex;
            align-items: center;
            background: rgba(139, 92, 246, 0.08);
            border: 1px solid rgba(139, 92, 246, 0.2);
            border-radius: 8px;
            padding: 15px 20px;
            margin: 8px 0;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .item-card::before, .item-row::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, #8b5cf6, #a855f7);
            transform: scaleX(0);
            transition: transform 0.3s ease;
        }}
        
        .item-card:hover, .item-row:hover {{
            transform: translateY(-3px);
            border-color: rgba(139, 92, 246, 0.4);
            box-shadow: 0 10px 25px rgba(139, 92, 246, 0.15);
        }}
        
        .item-card:hover::before, .item-row:hover::before {{
            transform: scaleX(1);
        }}
        
        .item-card a, .item-row a {{
            text-decoration: none;
            color: inherit;
            display: block;
        }}
        
        .item-row a {{
            display: flex;
            align-items: center;
            width: 100%;
        }}
        
        .item-icon {{
            font-size: 2.2rem;
            margin-bottom: 12px;
            color: #8b5cf6;
        }}
        
        .item-icon-small {{
            font-size: 1.5rem;
            color: #8b5cf6;
            margin-right: 15px;
            min-width: 25px;
        }}
        
        .item-name {{
            color: #ffffff;
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 8px;
            word-break: break-word;
        }}
        
        .item-name-small {{
            color: #ffffff;
            font-weight: 600;
            font-size: 1rem;
            flex: 1;
        }}
        
        .item-type {{
            color: #a5b4fc;
            font-size: 0.9rem;
            text-transform: capitalize;
        }}
        
        .item-type-small {{
            color: #a5b4fc;
            font-size: 0.8rem;
            text-transform: capitalize;
            min-width: 80px;
            text-align: right;
        }}
        
        .directory {{ 
            border-left: 3px solid #8b5cf6;
        }}
        
        .file {{ 
            border-left: 3px solid #c084fc;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding-top: 25px;
            border-top: 1px solid rgba(139, 92, 246, 0.2);
            color: #a5b4fc;
            font-style: italic;
        }}
        
        .status-info {{
            background: rgba(16, 33, 62, 0.6);
            border: 1px solid rgba(139, 92, 246, 0.2);
            border-radius: 10px;
            padding: 20px;
            margin: 30px 0;
            text-align: center;
        }}
        
        .status-info span {{
            color: #c084fc;
            font-weight: 500;
        }}
    </style>
    <script>
        function toggleView(viewType) {{
            const gridView = document.querySelector('.items-grid');
            const listView = document.querySelector('.items-list');
            const gridBtn = document.querySelector('[data-view="grid"]');
            const listBtn = document.querySelector('[data-view="list"]');
            
            if (viewType === 'grid') {{
                gridView.classList.add('active');
                listView.classList.remove('active');
                gridBtn.classList.add('active');
                listBtn.classList.remove('active');
            }} else {{
                gridView.classList.remove('active');
                listView.classList.add('active');
                gridBtn.classList.remove('active');
                listBtn.classList.add('active');
            }}
        }}
        
        // Set default view on load
        document.addEventListener('DOMContentLoaded', function() {{
            toggleView('grid');
        }});
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Directory Hub</h1>
        </div>
        
        <div class="controls">
            <div class="path-display">
                Current Path: {url_path}
            </div>
            <div class="view-toggle">
                <button class="toggle-btn active" data-view="grid" onclick="toggleView('grid')">[+] Grid</button>
                <button class="toggle-btn" data-view="list" onclick="toggleView('list')">[=] List</button>
            </div>
        </div>
        
        <div class="items-grid active">
"""
        
        # Add parent directory link if not root
        list_items = ""
        if url_path != '/':
            parent_path = '/'.join(url_path.rstrip('/').split('/')[:-1]) + '/'
            if parent_path == '/':
                parent_path = '/'
            html += f"""            <div class="item-card directory">
                <a href="{parent_path}">
                    <div class="item-icon">&lt;</div>
                    <div class="item-name">Parent Directory</div>
                    <div class="item-type">navigation</div>
                </a>
            </div>
"""
            list_items += f"""            <div class="item-row directory">
                <a href="{parent_path}">
                    <div class="item-icon-small">&lt;</div>
                    <div class="item-name-small">Parent Directory</div>
                    <div class="item-type-small">navigation</div>
                </a>
            </div>
"""
        
        # Add directories
        for dir_name in dirs:
            dir_url = url_path + dir_name + '/'
            html += f"""            <div class="item-card directory">
                <a href="{dir_url}">
                    <div class="item-icon">[D]</div>
                    <div class="item-name">{dir_name}/</div>
                    <div class="item-type">directory</div>
                </a>
            </div>
"""
            list_items += f"""            <div class="item-row directory">
                <a href="{dir_url}">
                    <div class="item-icon-small">[D]</div>
                    <div class="item-name-small">{dir_name}/</div>
                    <div class="item-type-small">directory</div>
                </a>
            </div>
"""
        
        # Add files
        for file_name in files:
            file_url = url_path + file_name
            file_icon = self.get_file_icon(file_name)
            file_type = self.get_file_type_display(file_name)
            html += f"""            <div class="item-card file">
                <a href="{file_url}">
                    <div class="item-icon">{file_icon}</div>
                    <div class="item-name">{file_name}</div>
                    <div class="item-type">{file_type}</div>
                </a>
            </div>
"""
            list_items += f"""            <div class="item-row file">
                <a href="{file_url}">
                    <div class="item-icon-small">{file_icon}</div>
                    <div class="item-name-small">{file_name}</div>
                    <div class="item-type-small">{file_type}</div>
                </a>
            </div>
"""
        
        html += f"""        </div>
        
        <div class="items-list">
{list_items}        </div>
        
        <div class="status-info">
            <span>DevPortal File Server</span> | Directory listing active
        </div>
        
        <div class="footer">
            <p>Network File Server Infrastructure</p>
        </div>
    </div>
</body>
</html>"""
        
        return html
    
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
    
    def get_file_icon(self, filename):
        """Get icon for file type"""
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        icons = {
            '.html': '[H]',
            '.htm': '[H]',
            '.png': '[I]',
            '.pdf': '[P]',
            '.txt': '[T]'
        }
        
        return icons.get(ext, '[F]')
    
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


def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python server.py <directory_to_serve>")
        sys.exit(1)
    
    directory = sys.argv[1]
    
    if not os.path.exists(directory):
        print(f"Error: Directory '{directory}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)
    
    # Create and start server
    server = HTTPServer(root_dir=directory)
    server.start()


if __name__ == "__main__":
    main()