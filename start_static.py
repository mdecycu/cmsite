import http.server
import socket
import threading
import sys
import os

httpd = None

def get_wan_address():
    """get wide area network address"""
    try:
        ipv4_address = get_wan_ipv4_address()
        if ipv4_address:
            return ipv4_address

        ipv6_address = get_wan_ipv6_address()
        if ipv6_address:
            return ipv6_address
    except socket.gaierror:
        pass

    return 'localhost'

def get_wan_ipv4_address():
    """get IPv4 wide area network address"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))  # Use Google Public DNS as the external host
        ip_address = sock.getsockname()[0]
        sock.close()
        return ip_address
    except socket.error:
        return None

def get_wan_ipv6_address():
    """get IPv6 wide area network address"""
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.connect(("2001:4860:4860::8888", 80))  # Use Google Public DNS as the external host
        ip_address = sock.getsockname()[0]
        sock.close()
        return ip_address
    except socket.error:
        return None

def start_server():
    global httpd
    static_port = 80

    server_address = get_wan_address() or 'localhost'
    server_port = static_port
    address_family = socket.AF_INET if ':' not in server_address else socket.AF_INET6

    httpd = http.server.HTTPServer((server_address, server_port), http.server.SimpleHTTPRequestHandler, bind_and_activate=False)
    httpd.socket = socket.socket(address_family, socket.SOCK_STREAM)
    httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if address_family == socket.AF_INET6:
        httpd.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        httpd.socket.bind((server_address, server_port, 0, 0))
    else:
        httpd.socket.bind((server_address, server_port))

    httpd.server_activate()
    httpd.serve_forever()

def stop_server():
    global httpd
    if httpd:
        httpd.shutdown()
        httpd.server_close()

def keyboard_listener():
    global httpd
    while True:
        char = sys.stdin.read(1)
        if char.lower() == 'q':
            print("Stopping the server...")
            stop_server()
            os._exit(0)  # Force exit the application

# Start the server in a separate thread
server_thread = threading.Thread(target=start_server)
server_thread.start()

# Start the keyboard listener thread
keyboard_thread = threading.Thread(target=keyboard_listener)
keyboard_thread.daemon = True  # Daemonize the thread so it exits when the main thread exits
keyboard_thread.start()
