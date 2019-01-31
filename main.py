from __future__ import print_function
import argparse
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
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT


MATRIX_COUNT = 4

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=MATRIX_COUNT, block_orientation=90)


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


def format_remaining_time(remaining) -> str:
    output = "{:02d}m".format(remaining.minute)
    if remaining.hour != 0 or remaining.day - 1 > 0:
        output = "{:02d}h{}".format(remaining.hour, output)
    if remaining.day - 1 > 0:
        output = f"{remaining.day - 1}d{output}"
    return output


def display_text(text_msg: str, font=TINY_FONT):
    if len(text_msg) <= MATRIX_COUNT * 2:
        with canvas(device) as draw:
            text(draw,
                 ((MATRIX_COUNT * 2 - len(text_msg)) * 2 , 0),
                 text_msg,
                 fill="white",
                 font=proportional(font))
    else:
        show_message(device, text_msg, fill="white", font=proportional(font))


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
        delta =  params.end - datetime.datetime.now()
        date_r = datetime.datetime(1, 1, 1) + delta
        remaining = format_remaining_time(date_r)
        # print(f"Remaining {remaining}")
        display_text(remaining, TINY_FONT)
    else:
        raise NotImplementedError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--settings',
                        type=str,
                        default='./settings.json',
                        help='location of the default settings json file')
    args = parser.parse_args()
    l_params = SprintParams(args.settings)
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

