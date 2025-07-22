#!/usr/bin/env python3
"""
Simple HTTP Proxy Server for Testing
Creates a basic HTTP/HTTPS proxy server for testing proxy connectivity
"""

import socket
import threading
import select
import time
import sys
from urllib.parse import urlparse

class SimpleProxyServer:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.running = False
        self.connections = 0
        
    def start(self):
        """Start the proxy server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True
            
            print(f"🔗 Simple Proxy Server started on {self.host}:{self.port}")
            print(f"📋 Configure your client to use: http://{self.host}:{self.port}")
            print("🔍 Proxy requests will be logged below:")
            print("-" * 60)
            
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    self.connections += 1
                    print(f"📥 Connection #{self.connections} from {addr[0]}:{addr[1]}")
                    
                    # Handle each connection in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error:
                    break
                    
        except Exception as e:
            print(f"❌ Error starting proxy server: {e}")
        finally:
            self.stop()
    
    def handle_client(self, client_socket, addr):
        """Handle individual client connections"""
        try:
            # Receive the request
            request = client_socket.recv(4096).decode('utf-8')
            if not request:
                return
                
            # Parse the first line
            first_line = request.split('\n')[0]
            print(f"🌐 {addr[0]} -> {first_line}")
            
            # Extract URL from request
            url_start = first_line.find(' ') + 1
            url_end = first_line.find(' ', url_start)
            url = first_line[url_start:url_end]
            
            # Handle CONNECT method (HTTPS)
            if first_line.startswith('CONNECT'):
                self.handle_connect(client_socket, url, addr)
            else:
                # Handle HTTP requests
                self.handle_http(client_socket, request, url, addr)
                
        except Exception as e:
            print(f"❌ Error handling client {addr[0]}: {e}")
        finally:
            client_socket.close()
    
    def handle_connect(self, client_socket, url, addr):
        """Handle HTTPS CONNECT requests"""
        try:
            # Parse host and port
            if ':' in url:
                host, port = url.split(':')
                port = int(port)
            else:
                host = url
                port = 443
                
            print(f"🔒 HTTPS CONNECT to {host}:{port}")
            
            # Create connection to target server
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(10)
            target_socket.connect((host, port))
            
            # Send success response
            client_socket.send(b'HTTP/1.1 200 Connection established\r\n\r\n')
            
            # Start tunneling data
            self.tunnel_data(client_socket, target_socket, addr)
            
        except Exception as e:
            print(f"❌ CONNECT error for {addr[0]} -> {url}: {e}")
            client_socket.send(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
    
    def handle_http(self, client_socket, request, url, addr):
        """Handle regular HTTP requests"""
        try:
            # Parse URL
            if not url.startswith('http'):
                # Relative URL, extract host from Host header
                lines = request.split('\n')
                host = None
                for line in lines:
                    if line.lower().startswith('host:'):
                        host = line.split(':', 1)[1].strip()
                        break
                if host:
                    url = f"http://{host}{url}"
                    
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or 80
            
            print(f"🌍 HTTP request to {host}:{port}{parsed.path}")
            
            # Create connection to target server
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(10)
            target_socket.connect((host, port))
            
            # Forward the request
            target_socket.send(request.encode())
            
            # Get response and forward back
            response = target_socket.recv(4096)
            client_socket.send(response)
            
            target_socket.close()
            
        except Exception as e:
            print(f"❌ HTTP error for {addr[0]} -> {url}: {e}")
            error_response = b'HTTP/1.1 502 Bad Gateway\r\n\r\nProxy Error'
            client_socket.send(error_response)
    
    def tunnel_data(self, client_socket, target_socket, addr):
        """Tunnel data between client and target for HTTPS"""
        try:
            while True:
                ready, _, _ = select.select([client_socket, target_socket], [], [], 1)
                
                if client_socket in ready:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    target_socket.send(data)
                    
                if target_socket in ready:
                    data = target_socket.recv(4096)
                    if not data:
                        break
                    client_socket.send(data)
                    
        except Exception as e:
            print(f"⚠️  Tunnel error for {addr[0]}: {e}")
        finally:
            target_socket.close()
    
    def stop(self):
        """Stop the proxy server"""
        self.running = False
        if hasattr(self, 'server_socket'):
            self.server_socket.close()
        print(f"\n🛑 Proxy server stopped. Handled {self.connections} connections.")

def main():
    port = 8888
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Usage: python simple_proxy_server.py [port]")
            sys.exit(1)
    
    proxy = SimpleProxyServer(port=port)
    
    try:
        proxy.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down proxy server...")
        proxy.stop()

if __name__ == "__main__":
    main() 