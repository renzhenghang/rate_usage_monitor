# get rate from all VMs.

import asyncio
import websockets
import tornado.ioloop
import tornado.web
import tornado.httpserver as httpserver
import tornado.websocket as websocket
import json
import time
import sys
import curses
from curses import wrapper
import signal
from threading import Lock
from tornado.websocket import WebSocketClosedError

# hostname to bandwidth
host_bw = {}
# hostname to line
host_line = {}

class PrintCurses:
    stdscr = curses.initscr()
    scrlock = Lock()
    @staticmethod
    def init():
        curses.noecho()
        PrintCurses.stdscr.clear()
        PrintCurses.stdscr.addstr(0, 0, "hostname\t\ttx\t\trx\t\tcpu\t\tmem\n")
        PrintCurses.stdscr.refresh()
    @staticmethod
    def print(line, info):
        output = '{}\t\t{}\t\t{}\t\t{}\t\t{}\n'.format(info['hostname'], info['tx'], info['rx'], info['cpu_usage'], \
                info['mem_util'])
        PrintCurses.stdscr.addstr(line, 0, output)
        PrintCurses.stdscr.refresh()

def signal_handler(sig, frame):
    PrintCurses.stdscr.clear()
    curses.echo()
    curses.endwin()
    sys.exit(0)


timestap = lambda: int(time.time() * 1000)
class BwHistory:
    def __init__(self):
        self.bw_history = []
    def push(self, bw_data):
        if len(self.bw_history) >= 10:
            self.bw_history.pop(0)
        self.bw_history.append(bw_data)
    def dump(self):
        return json.dumps(self.bw_history)

    def get_latest(self):
        return self.bw_history[-1]
"""
async def show_usage(websocket, path):
    ip_addr = path.strip('/').strip().replace('-', '.')
    uri = 'ws://{}:9999'.format(ip_addr)
    if ip_addr not in host_bw:
        host_bw[ip_addr] = BwHistory()
    async with websockets.connect(uri) as the_socket:
        while True:
            msg = await the_socket.recv()
            usage = json.loads(msg)
            time = timestap()
            host_bw[ip_addr].push({'x': time, 'y': float(usage['tx'])})
            msg = json.dumps({'chart': host_bw[ip_addr].dump()})
            await websocket.send(msg)
"""
def print_bw(stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, "hostname\t\ttx\t\trx\t\tcpu\t\tmem\n")
    for host in host_bw:
        info = host_bw[host].get_latest()
        output = '{}\t\t{}\t\t{}\t\t{}\t\t{}\n'.format(info['hostname'], info['tx'], info['rx'], info['cpu_usage'], \
                info['mem_util'])
        stdscr.addstr(host_line[host], 0, output)
        stdscr.refresh()

class VMPostHandler(tornado.web.RequestHandler):
    def post(self):
        vm_info = json.loads(self.request.body.decode('utf-8'))
        #print('received:', vm_info)
        hostname = vm_info['hostname']
        if hostname not in host_bw:
            host_bw[hostname] = BwHistory()
            host_line[hostname] = len(host_bw)
        host_bw[hostname].push(vm_info)
        output = '{}\t\t{}\t\t{}\t\t{}\t\t{}\n'.format(vm_info['hostname'], vm_info['tx'], vm_info['rx'], vm_info['cpu_usage'], \
                vm_info['mem_util'])
        #print(output, end="")
        #wrapper(print_bw)
        PrintCurses.scrlock.acquire()
        try:
            PrintCurses.print(host_line[hostname], vm_info) 
        finally:
            PrintCurses.scrlock.release()
        self.set_status(200)
        self.finish()

class WebSocketHandler(websocket.WebSocketHandler):

    def on_message(self, message):
        try:
            while True:
                history = host_bw.get(message, BwHistory())
                msg = {'hostname': message, 'usage': history.dump()}
                self.write_message(msg)
                await asyncio.sleep(1)
        except WebSocketClosedError:
            pass


if __name__ == '__main__':
    app = tornado.web.Application([
        (r'/', VMPostHandler),
        (r'/get', WebSocketHandler)
        ])
    signal.signal(signal.SIGINT, signal_handler) 
    PrintCurses.init()
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(80, address='0.0.0.0')
    tornado.ioloop.IOLoop.instance().start()
