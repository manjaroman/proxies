import multiprocessing
import socket 
import ssl
import time
import json
import datetime
import concurrent.futures 

socket.setdefaulttimeout(30)

def httpget(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"user-agent": "mozilla/5.0"})
    return urllib.request.urlopen(req).read().decode("utf-8")

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
    # print(port, url, hostname, params)
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


def test_proxy(pip):
    start = time.time()
    if (r := httpget_proxy("https://api.ipify.org?format=json", pip)) is None: 
        return -1
    if json.loads(r)["ip"] != pip.split(":")[0]:
        return -1
    return time.time() - start

    
import html.parser
class Parser(html.parser.HTMLParser):
    def __init__(self, *, convert_charrefs: bool = ...) -> None:
        self.nexttr = False
        self.tdi = 0
        self.proxies = list()
        self.pips = list()
        self.url = ""
        super().__init__(convert_charrefs=convert_charrefs)
    def handle_starttag(self, tag, attrs) -> None:
        if tag == "tr": 
            self.nexttr = True
            self.proxies.append([])
        return super().handle_starttag(tag, attrs)
    
    def handle_endtag(self, tag: str) -> None:
        if tag == "tr":
            self.nexttr = False
        if tag == "html": 
            if "sslproxies.org" in self.url:
                self.proxies = [x for x in self.proxies if x][:-16]
                self.pips = [f"{x[0]}:{x[1]}" for x in self.proxies]
            elif "free-proxy.cz" in self.url: 
                self.proxies = [x for x in self.proxies if x]
                self.pips =  [f"{x[0]}:{x[1]}" for x in self.proxies]
        return super().handle_endtag(tag)
    
    def handle_data(self, data: str) -> None:
        if self.nexttr:
            text = self.get_starttag_text()
            if text.startswith("<td"):
                self.proxies[-1].append(data)
        return super().handle_data(data)
    
    def feedurl(self, url): 
        self.url = url 
        self.feed(httpget(url))

pips = list()
pips += [x["addr"] for x in json.loads(httpget(f'https://checkerproxy.net/api/archive/{(datetime.date.today() - datetime.timedelta(days = 1)).strftime("%Y-%m-%d")}')) if x["type"] == 2]

parser = Parser()
parser.feedurl("https://www.sslproxies.org/")
# parser.feedurl("http://free-proxy.cz/en/proxylist/country/all/https/uptime/all")

pips += ["66.42.56.128:1080", "64.235.204.107:3128", "134.122.26.11:80", "161.139.20.83:80", "194.233.86.75:45232", "165.225.26.31:10366", "85.25.235.82:5566", "154.239.1.73:1981"]
pips += parser.pips
pips = list(set(pips))
pips.insert(0, "161.139.20.83:80")
chain_length = 2
print(len(pips))


def test_proxies(pips, nthreads):
    with concurrent.futures.ProcessPoolExecutor(nthreads) as pool:
        yield pool
        while True:
            for pip, time in zip(pips, pool.map(test_proxy, pips)):
                if time > -1: 
                    yield pip, time


MANAGER = multiprocessing.Manager()
ns = MANAGER.Namespace()
ns.running = False
ns.pool = None 
ns.working = MANAGER.dict()
POOL = None
CONSOOMER = None

def api_proxies():
    global ns, POOL, CONSOOMER
    if "cmd" not in request.args: 
        return jsonify(dict(ns.working))
    elif (cmd := request.args['cmd']) == "start":
        if not ns.running:
            nthreads = 300
            if "nthreads" in request.args:
                nthreads = int(request.args["nthreads"])
            gen = test_proxies(pips, nthreads)
            POOL = next(gen)
            def consume():
                ns.running = True
                while (obj := next(gen)) is not None: 
                    pip, time = obj
                    ns.working[pip] = time
            CONSOOMER = multiprocessing.Process(target=consume)
            CONSOOMER.start()
            ns.nthreads = nthreads
            return f"Started {nthreads} Threads"
        else:
            return "Error: Already running"
    elif cmd == "stop":
        if ns.running:
            POOL.shutdown(wait=True)
            CONSOOMER.terminate()
            POOL = None
            CONSOOMER = None
            ns.running = False
            return "Stopped"
        return "Error: Nothing is running"
    elif cmd == "info": 
        info = ""
        if POOL: 
            info += f"pool: {POOL._queue_count} "
        else:
            info += "no pool "
        if CONSOOMER:
            info += f"consoomer: {CONSOOMER.is_alive()} "
        else:
            info += "no consoomer "
        info += f"working: {len(ns.working)} is_running: {ns.running} "
        if ns.running:
            info += f"on {ns.nthreads} threads"
        return info
    else:
        return "Error: Unknown Command"


from flask import Flask, jsonify, request
from wsgiref.simple_server import make_server

app = Flask(__name__)

app.add_url_rule("/api/proxies", None, api_proxies)

with make_server('', 8000, app) as httpd:
    httpd.serve_forever()