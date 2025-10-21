#!/usr/bin/env python3
"""
HTTP Client - Lab 1
A simple HTTP client that downloads files from the HTTP server.
Handles HTML, PNG, and PDF file types appropriately.
"""

import socket
import os
import sys
import urllib.parse


class HTTPClient:
    def __init__(self):
        self.buffer_size = 4096
    
    def download(self, host, port, url_path, save_directory):
        """Download file from HTTP server"""
        try:
            # Create socket
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Connect to server
            print(f"Connecting to {host}:{port}")
            client_socket.connect((host, port))
            
            # Send HTTP GET request
            request = f"GET {url_path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            client_socket.send(request.encode('utf-8'))
            print(f"Sent request: GET {url_path}")
            
            # Receive response
            response_data = b""
            while True:
                data = client_socket.recv(self.buffer_size)
                if not data:
                    break
                response_data += data
            
            client_socket.close()
            
            # Parse response
            self.process_response(response_data, url_path, save_directory)
            
        except ConnectionRefusedError:
            print(f"Error: Could not connect to {host}:{port}")
            print("Make sure the server is running and accessible.")
        except Exception as e:
            print(f"Error: {e}")
    
    def process_response(self, response_data, url_path, save_directory):
        """Process HTTP response"""
        try:
            # Split headers and body
            header_end = response_data.find(b'\r\n\r\n')
            if header_end == -1:
                print("Error: Invalid HTTP response")
                return
            
            headers_bytes = response_data[:header_end]
            body_bytes = response_data[header_end + 4:]
            
            headers_text = headers_bytes.decode('utf-8')
            header_lines = headers_text.split('\r\n')
            
            # Parse status line
            status_line = header_lines[0]
            print(f"Response: {status_line}")
            
            # Check status code
            status_parts = status_line.split()
            if len(status_parts) >= 2:
                status_code = int(status_parts[1])
                if status_code != 200:
                    print(f"Server returned error: {status_line}")
                    if status_code == 404:
                        print("The requested file was not found on the server.")
                    return
            
            # Parse headers
            content_type = self.get_header_value(header_lines, 'Content-Type')
            content_length = self.get_header_value(header_lines, 'Content-Length')
            
            print(f"Content-Type: {content_type}")
            if content_length:
                print(f"Content-Length: {content_length}")
            
            # Process based on content type
            self.handle_content(body_bytes, content_type, url_path, save_directory)
            
        except Exception as e:
            print(f"Error processing response: {e}")
    
    def get_header_value(self, header_lines, header_name):
        """Extract header value from response headers"""
        for line in header_lines:
            if line.lower().startswith(header_name.lower() + ':'):
                return line.split(':', 1)[1].strip()
        return None
    
    def handle_content(self, body_bytes, content_type, url_path, save_directory):
        """Handle content based on type"""
        if not body_bytes:
            print("No content received")
            return
        
        # Determine file type from content type or URL
        file_type = self.determine_file_type(content_type, url_path)
        
        if file_type == 'html':
            # HTML: print body as-is
            self.handle_html(body_bytes)
        elif file_type in ['png', 'pdf']:
            # PNG/PDF: save to directory
            self.handle_binary_file(body_bytes, url_path, save_directory, file_type)
        else:
            print(f"Unknown content type: {content_type}")
            print("Saving as binary file...")
            self.handle_binary_file(body_bytes, url_path, save_directory, 'bin')
    
    def determine_file_type(self, content_type, url_path):
        """Determine file type from content type or URL extension"""
        if content_type:
            content_type = content_type.lower()
            if 'text/html' in content_type:
                return 'html'
            elif 'image/png' in content_type:
                return 'png'
            elif 'application/pdf' in content_type:
                return 'pdf'
        
        # Fallback to URL extension
        _, ext = os.path.splitext(url_path)
        ext = ext.lower()
        
        if ext in ['.html', '.htm']:
            return 'html'
        elif ext == '.png':
            return 'png'
        elif ext == '.pdf':
            return 'pdf'
        
        return 'unknown'
    
    def handle_html(self, body_bytes):
        """Handle HTML content - print to console"""
        try:
            html_content = body_bytes.decode('utf-8')
            print("\n" + "="*50)
            print("HTML CONTENT:")
            print("="*50)
            print(html_content)
            print("="*50 + "\n")
        except UnicodeDecodeError:
            print("Error: Could not decode HTML content as UTF-8")
    
    def handle_binary_file(self, body_bytes, url_path, save_directory, file_type):
        """Handle binary files - save to directory"""
        try:
            # Create save directory if it doesn't exist
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
                print(f"Created directory: {save_directory}")
            
            # Extract filename from URL path
            filename = os.path.basename(url_path)
            if not filename:
                filename = f"downloaded_file.{file_type}"
            
            # Full path to save file
            save_path = os.path.join(save_directory, filename)
            
            # Save file
            with open(save_path, 'wb') as f:
                f.write(body_bytes)
            
            print(f"File saved: {save_path} ({len(body_bytes)} bytes)")
            
        except Exception as e:
            print(f"Error saving file: {e}")


def main():
    """Main function"""
    if len(sys.argv) != 5:
        print("Usage: python client.py <server_host> <server_port> <url_path> <directory>")
        print("Example: python client.py localhost 8080 /index.html ./downloads")
        sys.exit(1)
    
    host = sys.argv[1]
    
    try:
        port = int(sys.argv[2])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)
    
    url_path = sys.argv[3]
    save_directory = sys.argv[4]
    
    # Ensure URL path starts with /
    if not url_path.startswith('/'):
        url_path = '/' + url_path
    
    print(f"HTTP Client - Lab 1")
    print(f"Server: {host}:{port}")
    print(f"Path: {url_path}")
    print(f"Save directory: {save_directory}")
    print("-" * 40)
    
    # Create and use client
    client = HTTPClient()
    client.download(host, port, url_path, save_directory)


if __name__ == "__main__":
    main()