# openWB E-Ink Display - MicroPython Version for ESP32-S3
# Updated for 2.13" e-ink display module

import network
import urequests
import ujson
import time
import gc
from machine import Pin, SPI, Timer
import framebuf
import lvgl as lv
from icons import (draw_sun_icon_small, SUN_ICON_16_WIDTH, 
                  SUN_ICON_16_HEIGHT)
from wifi_config import WIFI_SSID, WIFI_PASSWORD, HOSTNAME, WIFI_TIMEOUT_SECONDS, WIFI_RETRY_DELAY

# Initialize LVGL
lv.init()

# E-ink display driver for 2.13" display (adjust based on your specific model)
# Common 2.13" e-ink displays use SSD1680 or similar controllers
try:
    from epaper2in13_V3 import EPD_2in13_V3  # Waveshare 2.13" V3
    DISPLAY_TYPE = "waveshare_2in13_v3"
except ImportError:
    try:
        from epaper2in13 import EPD_2in13  # Waveshare 2.13" older
        DISPLAY_TYPE = "waveshare_2in13"
    except ImportError:
        print("E-ink display driver not found. Please install appropriate driver.")
        DISPLAY_TYPE = "none"

# Configuration (WiFi settings imported from wifi_config.py)

# HTTP Configuration
HTTP_HOST = "192.168.178.29"
HTTP_PORT = 7070
HTTP_PATH = ("/api/state?jq=%7BgridPower:.grid.power,pvPower:.pvPower,"
             "batterySoc:.batterySoc,loadpoints:[.loadpoints[0],"
             ".loadpoints[1]]%7Cmap(select(.!=null)%7C%7BchargePower:"
             ".chargePower,soc:(.vehicleSoc//.soc),charging:.charging,"
             "plugged:(.connected//.plugged)%7D)%7D")

# Timing Configuration
POLL_INTERVAL_MS = 30000  # 30 seconds for e-ink (slower refresh)
DATA_STALE_MS = 120000    # 2 minutes stale data timeout
LP_CYCLE_INTERVAL_MS = 60000  # 1 minute LP cycling

# Display Configuration - 2.13" e-ink actual dimensions
SCREEN_WIDTH = 212   # Actual e-ink width
SCREEN_HEIGHT = 104  # Actual e-ink height

# ESP32-S3 SPI pins (adjust based on your specific board)
SPI_CLK = 18
SPI_MOSI = 23
SPI_CS = 5
SPI_DC = 17
SPI_RST = 16
SPI_BUSY = 4

# UI Configuration
UI_GRAPHIC_STYLE = False  # E-ink works better with simple layouts


# Global Variables
class DisplayData:
    def __init__(self):
        self.evu_kw = 0.0
        self.pv_kw = 0.0
        self.house_kw = 0.0  # House consumption
        self.lp_all_w = 0
        self.battery_soc = -1
        self.battery_power_kw = 0.0  # Battery charging/discharging power
        # Loadpoint 1 data
        self.lp1_soc = -1
        self.lp1_plug_stat = False
        self.lp1_is_charging = False
        self.lp1_power_kw = 0.0
        self.lp1_vehicle_name = "Tesla"
        # Loadpoint 2 data
        self.lp2_soc = -1
        self.lp2_plug_stat = False
        self.lp2_is_charging = False
        self.lp2_power_kw = 0.0
        self.lp2_vehicle_name = "Smart"
        self.metrics = {}
        self.current_lp_index = 0
        self.last_data_received = 0
        self.last_poll_attempt = 0
        self.last_lp_switch = 0
        self.consecutive_failures = 0
        self.last_display_update = 0


data = DisplayData()

# Battery bitmap (8x6 pixels) - for e-ink
battery_bitmap = bytearray([
    0xfe, 0x82, 0x82, 0x82, 0x82, 0xfe
])


# Initialize E-ink Display with LVGL
class EInkDisplay:
    def __init__(self):
        self.width = SCREEN_WIDTH
        self.height = SCREEN_HEIGHT
        self.buffer = bytearray(self.width * self.height // 8)
        self.framebuf = framebuf.FrameBuffer(
            self.buffer, self.width, self.height, framebuf.MONO_HLSB)

        # Initialize hardware display driver
        if DISPLAY_TYPE == "waveshare_2in13_v3":
            self.epd = EPD_2in13_V3()
        elif DISPLAY_TYPE == "waveshare_2in13":
            self.epd = EPD_2in13()
        else:
            self.epd = None
            print("No e-ink driver available - using framebuffer only")

        self.init_display()
        self.setup_lvgl()

    def init_display(self):
        """Initialize the e-ink display hardware"""
        if self.epd:
            try:
                self.epd.init()
                self.epd.Clear()
                print("E-ink display initialized")
            except Exception as e:
                print(f"E-ink init error: {e}")

    def setup_lvgl(self):
        """Setup LVGL display driver"""
        # Create display driver
        self.disp_drv = lv.disp_drv_t()
        self.disp_buf1 = lv.disp_buf_t()

        # Allocate buffers for LVGL
        buf1_1 = bytearray(self.width * 10)  # 10 lines buffer
        buf1_2 = bytearray(self.width * 10)  # Double buffering

        # Initialize display buffer
        self.disp_buf1.init(buf1_1, buf1_2, len(buf1_1) // 4)

        # Set up display driver
        self.disp_drv.init()
        self.disp_drv.buffer = self.disp_buf1
        self.disp_drv.flush_cb = self.disp_flush
        self.disp_drv.hor_res = self.width
        self.disp_drv.ver_res = self.height

        # Register the driver
        lv.disp_drv_register(self.disp_drv)

        # Create main screen
        self.scr = lv.obj()
        lv.scr_load(self.scr)

        print("LVGL display driver initialized")

    def disp_flush(self, disp_drv, area, color_p):
        """LVGL flush callback - updates the e-ink display"""
        # Copy LVGL buffer to framebuffer
        x1 = area.x1
        y1 = area.y1
        x2 = area.x2
        y2 = area.y2

        # Convert LVGL color buffer to monochrome framebuffer
        w = x2 - x1 + 1
        h = y2 - y1 + 1

        for y in range(h):
            for x in range(w):
                if x1 + x < self.width and y1 + y < self.height:
                    # Get color from LVGL buffer (simplified for monochrome)
                    color_val = color_p[(y * w + x) * 4]  # 32-bit color
                    pixel_color = 1 if color_val > 128 else 0
                    self.framebuf.pixel(x1 + x, y1 + y, pixel_color)

        # Update e-ink display if this is a full screen update
        if (x1 == 0 and y1 == 0 and
                x2 >= self.width - 1 and y2 >= self.height - 1):
            if self.epd:
                try:
                    self.epd.display(self.buffer)
                    print("E-ink display updated via LVGL")
                except Exception as e:
                    print(f"E-ink show error: {e}")
            data.last_display_update = time.ticks_ms()

        # Tell LVGL we're done
        disp_drv.flush_ready()

    # Legacy methods for compatibility
    def fill(self, color):
        """Fill entire display (legacy compatibility)"""
        self.framebuf.fill(color)

    def text(self, text, x, y, color=1):
        """Draw text (legacy compatibility)"""
        self.framebuf.text(text, x, y, color)

    def show(self):
        """Update display (legacy compatibility)"""
        if self.epd:
            try:
                self.epd.display(self.buffer)
                print("E-ink display updated")
            except Exception as e:
                print(f"E-ink show error: {e}")
        data.last_display_update = time.ticks_ms()

    def draw_sun_icon_at_position(self, x, y):
        """Draw sun icon on framebuffer at specified position"""
        # Draw the small sun icon directly on the framebuffer
        # This will overlay on top of LVGL content
        draw_sun_icon_small(self.framebuf, x, y, 1)

    def draw_custom_icons(self):
        """Draw custom icons that overlay LVGL content"""
        # Only draw if there's space and it makes sense
        # PV icon position - top left area
        # Use small 16x16 icon that fits in available space
        self.draw_sun_icon_at_position(2, 2)


# Initialize display
display = EInkDisplay()


# LVGL UI Manager
class LVGLDisplayUI:
    def __init__(self, eink_display):
        self.eink = eink_display
        self.create_ui()

    def create_ui(self):
        """Create the LVGL UI elements"""
        # Main container with white background
        self.main_cont = lv.obj(self.eink.scr)
        self.main_cont.set_size(212, 104)
        self.main_cont.center()
        self.main_cont.set_style_bg_color(lv.color_white(), 0)
        self.main_cont.set_style_border_width(0, 0)
        self.main_cont.set_style_pad_all(0, 0)

        # Create all UI elements
        self.create_top_row()
        self.create_battery_section()
        self.create_charging_points()
        self.create_bottom_row()

    def create_top_row(self):
        """Create PV and Grid display"""
        # PV section (top left)
        self.pv_icon = lv.obj(self.main_cont)
        self.pv_icon.set_size(8, 8)
        self.pv_icon.set_pos(2, 2)
        self.pv_icon.set_style_bg_color(lv.color_black(), 0)
        self.pv_icon.set_style_border_width(1, 0)

        self.pv_label = lv.label(self.main_cont)
        self.pv_label.set_pos(12, 3)
        self.pv_label.set_text("11k")
        self.pv_label.set_style_text_color(lv.color_black(), 0)

        # Grid section (top right)
        self.grid_icon = lv.obj(self.main_cont)
        self.grid_icon.set_size(8, 8)
        self.grid_icon.set_pos(160, 2)
        self.grid_icon.set_style_bg_color(lv.color_black(), 0)

        self.grid_label = lv.label(self.main_cont)
        self.grid_label.set_pos(170, 3)
        self.grid_label.set_text("11k")
        self.grid_label.set_style_text_color(lv.color_black(), 0)

    def create_battery_section(self):
        """Create battery display with SoC bar"""
        # Battery icon
        self.battery_icon = lv.obj(self.main_cont)
        self.battery_icon.set_size(8, 6)
        self.battery_icon.set_pos(2, 22)
        self.battery_icon.set_style_bg_color(lv.color_black(), 0)
        self.battery_icon.set_style_border_width(1, 0)

        # Battery power label
        self.battery_power_label = lv.label(self.main_cont)
        self.battery_power_label.set_pos(12, 23)
        self.battery_power_label.set_text("-2k")
        self.battery_power_label.set_style_text_color(lv.color_black(), 0)

        # Battery SoC percentage
        self.battery_soc_label = lv.label(self.main_cont)
        self.battery_soc_label.set_pos(50, 23)
        self.battery_soc_label.set_text("14%")
        self.battery_soc_label.set_style_text_color(lv.color_black(), 0)

        # Battery SoC bar
        self.battery_bar = lv.bar(self.main_cont)
        self.battery_bar.set_size(40, 6)
        self.battery_bar.set_pos(70, 25)
        self.battery_bar.set_range(0, 100)
        self.battery_bar.set_value(14, lv.ANIM.OFF)
        self.battery_bar.set_style_bg_color(lv.color_white(), 0)
        self.battery_bar.set_style_bg_color(
            lv.color_black(), lv.PART.INDICATOR)

    def create_charging_points(self):
        """Create charging point displays"""
        # LP1 (Tesla) - left side
        lp1_x, lp1_y = 2, 42

        self.lp1_soc_label = lv.label(self.main_cont)
        self.lp1_soc_label.set_pos(lp1_x, lp1_y)
        self.lp1_soc_label.set_text("100%")
        self.lp1_soc_label.set_style_text_color(lv.color_black(), 0)

        self.lp1_bar = lv.bar(self.main_cont)
        self.lp1_bar.set_size(30, 6)
        self.lp1_bar.set_pos(lp1_x + 25, lp1_y + 2)
        self.lp1_bar.set_range(0, 100)
        self.lp1_bar.set_value(100, lv.ANIM.OFF)
        self.lp1_bar.set_style_bg_color(lv.color_white(), 0)
        self.lp1_bar.set_style_bg_color(
            lv.color_black(), lv.PART.INDICATOR)

        self.lp1_name_label = lv.label(self.main_cont)
        self.lp1_name_label.set_pos(lp1_x, lp1_y + 12)
        self.lp1_name_label.set_text("Tesla")
        self.lp1_name_label.set_style_text_color(lv.color_black(), 0)

        self.lp1_power_label = lv.label(self.main_cont)
        self.lp1_power_label.set_pos(lp1_x, lp1_y + 22)
        self.lp1_power_label.set_text("3k")
        self.lp1_power_label.set_style_text_color(lv.color_black(), 0)

        self.lp1_status_label = lv.label(self.main_cont)
        self.lp1_status_label.set_pos(60, lp1_y + 22)
        self.lp1_status_label.set_text("P")
        self.lp1_status_label.set_style_text_color(lv.color_black(), 0)

        # LP2 (Smart) - right side
        lp2_x, lp2_y = 130, 42

        self.lp2_soc_label = lv.label(self.main_cont)
        self.lp2_soc_label.set_pos(lp2_x, lp2_y)
        self.lp2_soc_label.set_text("-%")
        self.lp2_soc_label.set_style_text_color(lv.color_black(), 0)

        self.lp2_bar = lv.bar(self.main_cont)
        self.lp2_bar.set_size(30, 6)
        self.lp2_bar.set_pos(lp2_x + 25, lp2_y + 2)
        self.lp2_bar.set_range(0, 100)
        self.lp2_bar.set_value(0, lv.ANIM.OFF)
        self.lp2_bar.set_style_bg_color(lv.color_white(), 0)
        self.lp2_bar.set_style_bg_color(
            lv.color_black(), lv.PART.INDICATOR)

        self.lp2_name_label = lv.label(self.main_cont)
        self.lp2_name_label.set_pos(lp2_x, lp2_y + 12)
        self.lp2_name_label.set_text("Smart")
        self.lp2_name_label.set_style_text_color(lv.color_black(), 0)

        self.lp2_power_label = lv.label(self.main_cont)
        self.lp2_power_label.set_pos(lp2_x, lp2_y + 22)
        self.lp2_power_label.set_text("-k")
        self.lp2_power_label.set_style_text_color(lv.color_black(), 0)

    def create_bottom_row(self):
        """Create house consumption and time display"""
        # House icon
        self.house_icon = lv.obj(self.main_cont)
        self.house_icon.set_size(8, 8)
        self.house_icon.set_pos(2, 82)
        self.house_icon.set_style_bg_color(lv.color_black(), 0)
        self.house_icon.set_style_border_width(1, 0)

        # House consumption
        self.house_label = lv.label(self.main_cont)
        self.house_label.set_pos(12, 83)
        self.house_label.set_text("1k")
        self.house_label.set_style_text_color(lv.color_black(), 0)

        # Time display
        self.time_label = lv.label(self.main_cont)
        self.time_label.set_pos(160, 83)
        self.time_label.set_text("14:25")
        self.time_label.set_style_text_color(lv.color_black(), 0)

    def format_power_compact(self, kw):
        """Format power value for compact display"""
        w = int(abs(kw) * 1000)
        if w < 1000:
            return f"{w}W"
        elif w < 10000:
            kw_val = w / 1000.0
            return f"{kw_val:.1f}k"
        else:
            kw_int = w // 1000
            return f"{kw_int}k"

    def update_display_data(self):
        """Update all UI elements with current data"""
        # Update PV
        self.pv_label.set_text(self.format_power_compact(data.pv_kw))

        # Update Grid
        self.grid_label.set_text(self.format_power_compact(data.evu_kw))

        # Update Battery
        if data.battery_soc >= 0:
            battery_power_text = self.format_power_compact(data.battery_power_kw)
            if data.battery_power_kw > 0:
                battery_power_text = "+" + battery_power_text
            elif data.battery_power_kw < 0:
                battery_power_text = ("-" +
                    self.format_power_compact(-data.battery_power_kw))

            self.battery_power_label.set_text(battery_power_text)
            self.battery_soc_label.set_text(f"{data.battery_soc}%")
            self.battery_bar.set_value(data.battery_soc, lv.ANIM.OFF)
        else:
            self.battery_power_label.set_text("-kW")
            self.battery_soc_label.set_text("-%")
            self.battery_bar.set_value(0, lv.ANIM.OFF)

        # Update LP1
        if data.lp1_soc >= 0:
            self.lp1_soc_label.set_text(f"{data.lp1_soc}%")
            self.lp1_bar.set_value(data.lp1_soc, lv.ANIM.OFF)
        else:
            self.lp1_soc_label.set_text("-%")
            self.lp1_bar.set_value(0, lv.ANIM.OFF)

        self.lp1_power_label.set_text(self.format_power_compact(data.lp1_power_kw))
        self.lp1_name_label.set_text(data.lp1_vehicle_name)

        if data.lp1_is_charging:
            self.lp1_status_label.set_text("C")
        elif data.lp1_plug_stat:
            self.lp1_status_label.set_text("P")
        else:
            self.lp1_status_label.set_text("")

        # Update LP2
        if data.lp2_soc >= 0:
            self.lp2_soc_label.set_text(f"{data.lp2_soc}%")
            self.lp2_bar.set_value(data.lp2_soc, lv.ANIM.OFF)
        else:
            self.lp2_soc_label.set_text("-%")
            self.lp2_bar.set_value(0, lv.ANIM.OFF)

        self.lp2_power_label.set_text(self.format_power_compact(data.lp2_power_kw))
        self.lp2_name_label.set_text(data.lp2_vehicle_name)

        # Update house consumption
        self.house_label.set_text(self.format_power_compact(data.house_kw))

        # Update time
        t = time.localtime()
        time_str = f"{t[3]:02d}:{t[4]:02d}"
        self.time_label.set_text(time_str)


# Initialize LVGL UI
lvgl_ui = LVGLDisplayUI(display)


def connect_wifi():
    """Connect to WiFi network"""
    print("Connecting to WiFi...")
    display.fill(0)
    display.text("Connecting WiFi", 0, 0)
    display.show()

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    timeout = 0
    while not wlan.isconnected() and timeout < WIFI_TIMEOUT_SECONDS:
        print(".", end="")
        display.text(".", timeout * 6, 16)
        display.show()
        time.sleep(WIFI_RETRY_DELAY)
        timeout += 1

    if wlan.isconnected():
        print(f"\nConnected! IP: {wlan.ifconfig()[0]}")
        return True
    else:
        print("\nFailed to connect to WiFi")
        display.fill(0)
        display.text("WiFi Error", 0, 0)
        display.show()
        return False


def http_get(host, port, path):
    """Perform HTTP GET request"""
    try:
        url = f"http://{host}:{port}{path}"
        response = urequests.get(url, timeout=10)
        if response.status_code == 200:
            body = response.text
            response.close()
            return body
        else:
            response.close()
            return None
    except Exception as e:
        print(f"HTTP Error: {e}")
        return None


def parse_evcc_state(body):
    """Parse EVCC JSON state into metrics"""
    try:
        doc = ujson.loads(body)
        metrics = {
            'gridPower': 0,
            'pvPower': 0,
            'batterySoc': -1,
            'totalChargePower': 0,
            'lpCount': 0,
            'lps': []
        }

        # Extract main values
        if 'gridPower' in doc:
            metrics['gridPower'] = doc['gridPower']
        if 'pvPower' in doc:
            metrics['pvPower'] = doc['pvPower']
        if 'batterySoc' in doc:
            battery_soc = doc['batterySoc']
            metrics['batterySoc'] = (int(battery_soc)
                                     if battery_soc is not None else -1)

        # Extract loadpoints
        if 'loadpoints' in doc and doc['loadpoints']:
            # Max 2 loadpoints
            for i, lp in enumerate(doc['loadpoints'][:2]):
                if lp:
                    lp_soc = lp.get('soc', -1)
                    lp_data = {
                        'chargePower': lp.get('chargePower', 0),
                        'soc': int(lp_soc) if lp_soc is not None else -1,
                        'charging': lp.get('charging', False),
                        'plugged': lp.get('plugged', False)
                    }
                    metrics['lps'].append(lp_data)
                    metrics['totalChargePower'] += lp_data['chargePower']
                    metrics['lpCount'] += 1

        return metrics
    except Exception as e:
        print(f"Parse error: {e}")
        return None


def format_power_value(kw):
    """Format power value according to display rules"""
    w = int(kw * 1000)
    if w < 1000:
        return str(w)
    elif w < 10000:
        kw_val = w / 1000.0
        return f"{kw_val:.1f}k"
    else:
        kw_int = w // 1000
        return f"{kw_int}k"


def draw_battery_icon(x, y):
    """Draw battery icon bitmap"""
    for row in range(6):
        for col in range(8):
            if battery_bitmap[row] & (0x80 >> col):
                display.pixel(x + col, y + row, 1)


def draw_solar_icon(x, y):
    """Draw simple solar panel icon (8x8)"""
    # Simple solar panel representation
    display.rect(x, y, 8, 8, 1)
    display.pixel(x+2, y+2, 1)
    display.pixel(x+5, y+2, 1)
    display.pixel(x+2, y+5, 1)
    display.pixel(x+5, y+5, 1)


def draw_grid_icon(x, y):
    """Draw grid/lightning icon (8x8)"""
    # Lightning bolt shape
    for i in range(8):
        display.pixel(x+3, y+i, 1)
    display.pixel(x+2, y+2, 1)
    display.pixel(x+4, y+5, 1)


def draw_house_icon(x, y):
    """Draw house icon (8x8)"""
    # Simple house shape
    display.rect(x+1, y+3, 6, 5, 1)
    display.pixel(x+3, y+1, 1)
    display.pixel(x+2, y+2, 1)
    display.pixel(x+4, y+2, 1)
    display.pixel(x+1, y+3, 1)
    display.pixel(x+5, y+3, 1)


def draw_soc_bar(x, y, width, height, soc):
    """Draw SoC bar with percentage"""
    if soc < 0:
        return

    # Draw border
    display.rect(x, y, width, height, 1)

    # Fill based on SoC
    fill_width = (soc * (width - 2)) // 100
    if fill_width > 0:
        display.fill_rect(x + 1, y + 1, fill_width, height - 2, 1)


def format_power_compact(kw):
    """Format power value for compact display"""
    w = int(abs(kw) * 1000)
    if w < 1000:
        return f"{w}W"
    elif w < 10000:
        kw_val = w / 1000.0
        return f"{kw_val:.1f}k"
    else:
        kw_int = w // 1000
        return f"{kw_int}k"


def update_display():
    """Update the e-ink display using LVGL"""
    # Only update if enough time has passed (e-ink is slow)
    current_time = time.ticks_ms()
    time_diff = time.ticks_diff(current_time, data.last_display_update)
    if time_diff < 10000:  # 10 second minimum
        return

    # Update LVGL UI with current data
    lvgl_ui.update_display_data()

    # Draw custom icons on the framebuffer (overlays LVGL content)
    display.draw_custom_icons()

    # Process LVGL tasks to trigger display update
    lv.task_handler()

    print("Display updated with LVGL")


def poll_and_update():
    """Poll EVCC API and update display"""
    body = http_get(HTTP_HOST, HTTP_PORT, HTTP_PATH)
    if not body:
        return False

    metrics = parse_evcc_state(body)
    if not metrics:
        print("Parse failed")
        return False

    # Update global data
    data.evu_kw = metrics['gridPower'] / 1000.0
    data.pv_kw = metrics['pvPower'] / 1000.0
    data.lp_all_w = int(metrics['totalChargePower'])
    data.battery_soc = metrics['batterySoc']

    # Calculate house consumption (rough estimate)
    # House = Grid + PV - Battery - Charging
    # For now, use simplified calculation
    total_consumption = data.evu_kw + data.pv_kw - (data.lp_all_w / 1000.0)
    data.house_kw = max(0, total_consumption)

    # Estimate battery power (positive = charging, negative = discharging)
    # This is a rough estimate based on grid/PV balance
    data.battery_power_kw = -(data.evu_kw - (data.lp_all_w / 1000.0))

    data.metrics = metrics

    # Update LP1 data (first loadpoint)
    if metrics['lpCount'] > 0:
        lp1 = metrics['lps'][0]
        data.lp1_soc = lp1['soc']
        data.lp1_is_charging = lp1['charging']
        data.lp1_plug_stat = lp1['plugged']
        data.lp1_power_kw = lp1['chargePower'] / 1000.0
    else:
        data.lp1_soc = -1
        data.lp1_is_charging = False
        data.lp1_plug_stat = False
        data.lp1_power_kw = 0.0

    # Update LP2 data (second loadpoint)
    if metrics['lpCount'] > 1:
        lp2 = metrics['lps'][1]
        data.lp2_soc = lp2['soc']
        data.lp2_is_charging = lp2['charging']
        data.lp2_plug_stat = lp2['plugged']
        data.lp2_power_kw = lp2['chargePower'] / 1000.0
    else:
        data.lp2_soc = -1
        data.lp2_is_charging = False
        data.lp2_plug_stat = False
        data.lp2_power_kw = 0.0

    data.last_data_received = time.ticks_ms()
    data.consecutive_failures = 0
    update_display()
    return True


def show_error_screen():
    """Show error screen when data is stale"""
    display.fill(0)
    display.text("Error", 0, 0)
    display.text("no data", 0, 16)
    display.show()


def main_loop():
    """Main application loop"""
    while True:
        current_time = time.ticks_ms()

        # Poll for new data
        poll_diff = time.ticks_diff(current_time, data.last_poll_attempt)
        if poll_diff >= POLL_INTERVAL_MS:
            data.last_poll_attempt = current_time
            if not poll_and_update():
                data.consecutive_failures += 1
                print(f"Poll failed (#{data.consecutive_failures})")

        # Check for stale data
        data_age = time.ticks_diff(current_time, data.last_data_received)
        if data_age > DATA_STALE_MS:
            show_error_screen()

        # Handle loadpoint cycling
        has_multiple_lps = data.metrics.get('lpCount', 0) > 1
        data_fresh = (time.ticks_diff(current_time, data.last_data_received) <=
                      DATA_STALE_MS)
        if has_multiple_lps and data_fresh:
            lp_switch_diff = time.ticks_diff(current_time, data.last_lp_switch)
            if lp_switch_diff >= LP_CYCLE_INTERVAL_MS:
                data.last_lp_switch = current_time
                data.current_lp_index = (
                    (data.current_lp_index + 1) % data.metrics['lpCount'])

                # Update LP display data
                if data.current_lp_index < len(data.metrics['lps']):
                    lp = data.metrics['lps'][data.current_lp_index]
                    data.lp1_soc = lp['soc']
                    data.lp1_is_charging = lp['charging']
                    data.lp1_plug_stat = lp['plugged']
                    update_display()

        # Handle LVGL tasks
        lv.task_handler()

        # Small delay and garbage collection
        time.sleep(0.05)  # Shorter delay for LVGL responsiveness
        gc.collect()


def main():
    """Main entry point"""
    print("EVCC E-Ink Display Init - MicroPython Version for ESP32-S3")

    # Test display with initial screen
    display.fill(1)  # White background for e-ink
    display.text("EVCC Display", 50, 30)
    display.text("Initializing...", 50, 50)
    display.show()
    time.sleep(2)

    display.fill(0)  # Clear to black
    display.text("Connecting WiFi", 50, 50)
    display.show()

    # Connect to WiFi
    if not connect_wifi():
        display.fill(0)
        display.text("WiFi Failed", 50, 50)
        display.show()
        return

    display.fill(0)
    display.text("WiFi Connected", 50, 40)
    display.text("Starting...", 50, 60)
    display.show()
    time.sleep(1)

    print("Starting HTTP polling loop")
    data.last_data_received = time.ticks_ms()

    # Initial display update
    update_display()

    # Start main loop
    try:
        main_loop()
    except KeyboardInterrupt:
        print("Shutting down...")
        display.fill(0)
        display.text("Shutdown", 100, 50)
        display.show()


if __name__ == "__main__":
    main()
