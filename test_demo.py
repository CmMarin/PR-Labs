#!/usr/bin/env python3
"""
Test Script for HTTP File Server - Lab 1
This script demonstrates the server and client functionality.
"""

import subprocess
import time
import os
import sys

def run_tests():
    """Run a series of tests to demonstrate functionality"""
    
    print("="*60)
    print("HTTP FILE SERVER - LAB 1 TEST SCRIPT")
    print("="*60)
    
    # Test 1: Show directory structure
    print("\n1. PROJECT STRUCTURE:")
    print("-" * 20)
    os.system("dir /s")
    
    # Test 2: Start server (manual step)
    print("\n2. TO START THE SERVER:")
    print("-" * 20)
    print("Run: docker-compose up --build")
    print("Or manually: python server.py ./content")
    
    # Test 3: Client usage examples
    print("\n3. CLIENT USAGE EXAMPLES:")
    print("-" * 20)
    print("# Download HTML file:")
    print("python client.py localhost 8080 /index.html ./downloads")
    print()
    print("# Download PNG image:")
    print("python client.py localhost 8080 /image.png ./downloads")
    print()
    print("# Download PDF document:")
    print("python client.py localhost 8080 /document.pdf ./downloads")
    print()
    print("# Get directory listing:")
    print("python client.py localhost 8080 /subdirectory/ ./downloads")
    print()
    print("# Test 404 error:")
    print("python client.py localhost 8080 /nonexistent.txt ./downloads")
    
    # Test 4: Browser URLs
    print("\n4. BROWSER TEST URLS:")
    print("-" * 20)
    print("http://localhost:8080/                 # Directory listing")
    print("http://localhost:8080/index.html       # HTML page with image")
    print("http://localhost:8080/image.png        # PNG image")
    print("http://localhost:8080/document.pdf     # PDF document")
    print("http://localhost:8080/subdirectory/    # Subdirectory listing")
    print("http://localhost:8080/nonexistent.txt  # 404 error test")
    
    print("\n" + "="*60)
    print("Ready for testing! Start the server first, then run the tests.")
    print("="*60)

if __name__ == "__main__":
    run_tests()