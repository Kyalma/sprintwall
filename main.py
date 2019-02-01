from __future__ import print_function
import argparse
import queue
import os
import json
import datetime
import math

from threading import Lock

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
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

serial0 = spi(port=0, device=0, gpio=noop())
serial1 = spi(port=0, device=1, gpio=noop())
top_bar = max7219(serial1, cascaded=MATRIX_COUNT, block_orientation=-90)
low_bar = max7219(serial0, cascaded=MATRIX_COUNT, block_orientation=90)


class TooLongError(Exception):
    def __init__(self, message=None, errors=None):
        super().__init__(message or "Message too long to fit the screen")
        self.errors = errors


class SprintParams:
    def __init__(self, settings_path: str, **kwargs):
        if kwargs.get('zero', False):
            self.start = datetime.datetime.now()
            self.end = datetime.datetime.now()
            self.mode = 'countdown'
            self.msg = 'No settings file initialized'
        else:
            self.load_file(settings_path)

    def load_file(self, settings_path: str):
        print(f"Loading file {settings_path}")
        with open(settings_path, 'r') as fhandler:
            j_data = json.load(fhandler)
        self.msg = j_data.get('message')
        self.start = datetime.datetime.strptime(j_data.get('start'), DATETIME_FORMAT)
        self.end = datetime.datetime.strptime(j_data.get('end'), DATETIME_FORMAT)
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


def display_text(text_msg: str, font=TINY_FONT, device=low_bar):
    if len(text_msg) <= MATRIX_COUNT * 2:
        if font == TINY_FONT:
            pos = ((MATRIX_COUNT * 2 - len(text_msg)) * 2 , 0)
        else:
            pos = ((MATRIX_COUNT - len(text_msg)) * 4, 0)
        with canvas(device) as draw:
            text(draw, pos, text_msg, fill="white", font=proportional(font))
    else:
        raise TooLongError
        # show_message(device, text_msg, fill="white", font=proportional(font))


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
    display_text(params.msg, TINY_FONT, top_bar)
    if params.mode == 'countdown':
        delta =  params.end - datetime.datetime.now()
        date_r = datetime.datetime(1, 1, 1) + delta
        remaining = format_remaining_time(date_r)
        # print(f"Remaining {remaining}")
        display_text(remaining, TINY_FONT, low_bar)
    else:
        until_start = params.end - params.start
        until_now = params.end - datetime.datetime.now()
        percent = math.floor(100 - (until_now.total_seconds() / until_start.total_seconds()))
        display_text(f"{percent}%", TINY_FONT, low_bar)
        # raise NotImplementedError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--settings',
                        type=str,
                        default='./settings.json',
                        help='location of the default settings json file')
    args = parser.parse_args()
    l_params = SprintParams(args.settings)
    l_queue = queue.Queue()

    # display_text(l_params.msg, CP437_FONT, top_bar)
    tasks = [
        # task.LoopingCall(display_text, l_params.msg, CP437_FONT, top_bar).start(1),
        task.LoopingCall(consume, l_queue, l_params).start(60)
    ]
    for deffered_task in tasks:
        deffered_task.addErrback(deferred_error)
    reactor.listenUDP(7000, SprintWallProtocol(l_queue))
    try:
        print("Running reactor")
        reactor.run()
    except KeyboardInterrupt:
        print("Killing the machine (yeah!)")


if __name__ == "__main__":
    main()

