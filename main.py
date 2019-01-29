from __future__ import print_function
import queue
import os
import json
import datetime

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet import task

from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.led_matrix.device import max7219
from luma.core.legacy import text
from luma.core.legacy import show_message
from luma.core.legacy.font import proportional, CP437_FONT, LCD_FONT, TINY_FONT


serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=90)


class SprintParams:
    def __init__(self, settings_path: str, **kwargs):
        if kwargs.get('zero', False):
            self.start = datetime.datetime.now()
            self.end = datetime.datetime.now()
            self.mode = 'countdown'
        else:
            self.load_file(settings_path)

    def load_file(self, settings_path: str):
        print(f"Loading file {settings_path}")
        with open(settings_path, 'r') as fhandler:
            j_data = json.load(fhandler)
        self.start = datetime.datetime.strptime(j_data.get('start'), "%Y-%m-%d %H:%M:%S")
        self.end = datetime.datetime.strptime(j_data.get('end'), "%Y-%m-%d %H:%M:%S")
        self.mode = j_data.get('mode')


class SprintWallProtocol(DatagramProtocol):
    def __init__(self, queue):
        self.queue = queue
        super().__init__()

    def datagramReceived(self, data, *args):
        print(f"Received {data}")
        self.queue.put(data)


def deferred_error(failure):
    print(failure.getBriefTraceback())


def consume(th_queue, params):
    try:
        item = th_queue.get_nowait()
        print(f"Consuming {item}")
        if os.path.isfile(item):
            params.load_file(item)
        else:
            print(f"file {item} does not exist, skipping.")
        th_queue.task_done()
    except queue.Empty:
        pass
    if params.mode == 'countdown':
        delta = params.end - params.start
        with canvas(device) as draw:
            text(draw, (0, 0), str(delta), fill="white", font=proportional(TINY_FONT))
    else:
        raise NotImplementedError


def main():
    l_params = SprintParams('./settings.json')
    l_queue = queue.Queue()
    reactor.listenUDP(7000, SprintWallProtocol(l_queue))
    loop = task.LoopingCall(consume, l_queue, l_params)
    loop_deffered = loop.start(60)
    loop_deffered.addErrback(deferred_error)
    try:
        print("Running reactor")
        reactor.run()
    except KeyboardInterrupt:
        print("Killing the machine (yeah!)")


if __name__ == "__main__":
    main()

