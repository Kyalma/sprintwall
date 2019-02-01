import time

import datetime

from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.led_matrix.device import max7219
from luma.core.legacy import text
from luma.core.legacy import show_message
from luma.core.legacy.font import proportional, CP437_FONT, LCD_FONT, TINY_FONT

serial = spi(port=0, device=1, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=90)

for font in (CP437_FONT, LCD_FONT, TINY_FONT):
	real_time = datetime.datetime.today().strftime("%Hh%Mm%Ss")
	with canvas(device) as draw:
		text(draw, (0, 0), real_time, fill="white", font=proportional(font))
	time.sleep(3)
	show_message(device, real_time, fill="white", scroll_delay=0.1, font=proportional(font))
