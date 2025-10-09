# HTTP File Server - Lab 1

A simple HTTP file server implementation using Python and TCP sockets, containerized with Docker Compose.

## Features

- HTTP file server with TCP sockets
- Supports HTML, PNG, and PDF file types
- Directory listing for nested directories
- HTTP client for downloading files
- Docker Compose setup for easy deployment
- 404 error handling for missing files

## Project Structure

```
PR-lab1/
├── server.py          # HTTP server implementation
├── client.py          # HTTP client implementation
├── docker-compose.yml # Docker Compose configuration
├── Dockerfile         # Docker image configuration
├── content/           # Directory to be served
│   ├── index.html     # Main HTML page
│   ├── image.png      # Test PNG image
│   ├── document.pdf   # Test PDF file
│   └── subdirectory/  # Nested directory with files
└── downloads/         # Directory for client downloads
```

## Usage

### Running with Docker Compose

1. Start the server:
```bash
docker-compose up --build
```

2. Access the server:
   - **Locally:** `http://localhost:8080`
   - **From friends on network:** `http://YOUR_IP:8080`

### Running Manually

1. Start the server:
```bash
python server.py ./content
```

2. Find your IP address:
```bash
ipconfig | findstr "IPv4"
```

3. Share your IP with friends: `http://192.168.1.XXX:8080`

### Running the client

```bash
# Download from your own server
python client.py localhost 8080 /index.html ./downloads

# Download from friend's server
python client.py 192.168.1.50 8080 /document.pdf ./downloads
```

### Network Setup

See `NETWORK_SETUP.md` for detailed instructions on:
- Configuring Windows Firewall
- Finding your local IP address
- Connecting to friends' servers
- Troubleshooting network issues

## Requirements Met

- ✅ Uses Docker Compose
- ✅ Uses Python with TCP sockets
- ✅ Handles HTML, PNG, and PDF files
- ✅ Implements 404 error handling
- ✅ HTTP client implementation (10 points)
- ✅ Directory listing support (10 points)
- ✅ Ready for network browsing (10 points)