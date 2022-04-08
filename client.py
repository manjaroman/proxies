import socket 
import ssl
from weakref import proxy

def httpget_json(url):
    import urllib.request
    import json
    req = urllib.request.Request(url, headers={"user-agent": "mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))


def parse_url(url):
    protocol, url = url.split("://")
    sp = url.split("?")
    if len(sp) > 1:
        params = f"?{sp.pop()}"
        url = sp.pop()
    else:
        params = ""
    sp = url.split("/")
    hostname = sp.pop(0)
    url = f'/{"/".join(sp)}'
    return protocol, url, hostname, params


def parse_response(sock, debug=False):
    s = ""
    try:
        while s[-4:] != "\r\n\r\n":
            s += sock.recv(1).decode("utf-8")
    except socket.timeout:
        return
    if not s.startswith("HTTP"):
        return
    s = s.splitlines()
    sp = s[0].split(" ")
    code = int(sp[1])
    reason = " ".join(sp[2:])
    if code != 200: 
        if debug:
            print(code, reason)
        return
    return "\n".join(s)


def httpget_proxy(url, pip):
    protocol, url, hostname, params = parse_url(url)
    port = 443 if protocol == "https" else 80
    proxy_addr = pip.split(":")
    proxy_addr[1] = int(proxy_addr[1])
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    try:
        sock.connect(tuple(proxy_addr))
        sock.send(f"CONNECT {hostname}:{port} HTTP/1.1\r\n\r\n".encode("utf-8"))
        if (r := parse_response(sock)) is None: 
            return
        # print(r)
        context = ssl.create_default_context()
        ssock = context.wrap_socket(sock, server_hostname=hostname)
        ssock.settimeout(30)
        ssock.send(f"GET {url}{params} HTTP/1.1\r\nHost: {hostname}\r\n\r\n".encode("utf-8"))
        if (r := parse_response(ssock)) is None:
            return
        # print(r)
        response = ssock.recv(2048).decode("utf-8")
        return response
    except socket.error as e:
        return


def httpget_proxied(url, pips, chain_length, timeout=60, debug=True):
    print(pips)
    assert len(pips) > chain_length
    protocol, url = url.split("://")
    if protocol == "http":
        print("No http")
        return
    sp = url.split("?")
    if len(sp) > 1:
        params = f"?{sp.pop()}"
        url = sp.pop()
    else:
        params = ""
    sp = url.split("/")
    hostname = sp.pop(0)
    url = f'/{"/".join(sp)}'

    while True:
        pip = pips.pop(0)
        proxy_addr = pip.split(":")
        proxy_addr[1] = int(proxy_addr[1])
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            print('→', pip, end=' ', flush=True)
            sock.connect(tuple(proxy_addr))
            break
        except socket.error:
            print('\r', end='', flush=True)

    c = 0
    while c < chain_length:
        pip = pips.pop(0)
        if debug:
            print(c, "→", pip)
        sock.sendall(f"CONNECT {pip} HTTP/1.1\r\n\r\n".encode("utf-8"))
        try:
            s = ""
            while s[-4:] != "\r\n\r\n":
                # print(sock.timeout)
                s += sock.recv(1).decode("utf-8")
            if not s.startswith("HTTP"):
                continue
            
            s = s.splitlines()
            sp = s[0].split(" ")
            code = int(sp[1])
            reason = " ".join(sp[2:])
            print(code, reason)
            if code != 200: 
                continue
            c += 1
        except socket.timeout: 
            print("\r", end="", flush=True)

    if debug:
        print("→", hostname, end=' ', flush=True)
    sock.sendall(f"CONNECT {hostname}:443 HTTP/1.1\r\n\r\n".encode("utf-8"))
    
    s = ""
    while s[-4:] != "\r\n\r\n":
        s += sock.recv(1).decode("utf-8")
    s = s.splitlines()
    sp = s[0].split(" ")
    code = int(sp[1])
    reason = " ".join(sp[2:])
    if debug:
        print(code, reason)
    if code != 200: 
        return code

    context = ssl.create_default_context()
    ssock = context.wrap_socket(sock, server_hostname=hostname)
    if debug:
        print(ssock.version())
    
    ssock.send(f"GET {url}{params} HTTP/1.1\r\nHost: {hostname}\r\n\r\n".encode("utf-8"))
    s = ""
    while s[-4:] != "\r\n\r\n":
        s += ssock.recv(1).decode("utf-8")
    s = s.splitlines()
    sp = s[0].split(" ")
    code = int(sp[1])
    reason = " ".join(sp[2:])
    # print(code, reason)
    response = ssock.recv(2048).decode("utf-8")
    if debug:
        print(response)
    ssock.close()
    sock.close()
    return response


proxy_api = "http://localhost:8000/api/proxies"
proxies = httpget_json(proxy_api)

pips = list(proxies.keys())
ip_api = "https://api.ipify.org?format=json"
httpget_proxied(ip_api, pips, 1, debug=True)