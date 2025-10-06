#!/usr/bin/env python3
"""
E-Ink Display Simulator for LVGL
Runs your actual main.py logic locally for testing and refinement
"""

import json
import time
import sys
import tkinter as tk
from oled_simulator import OLEDSimulator


class EInkSimulator(OLEDSimulator):
    """E-Ink display simulator with LVGL support"""
    
    def __init__(self, width=212, height=104):
        super().__init__(width, height, scale=4)
        self.root.title("E-Ink Display Simulator (212x104) - LVGL")
        self.poll_callback = None
        self.last_display_update = 0
        self.setup_controls()
        
    def setup_controls(self):
        """Setup control panel"""
        control_frame = tk.Frame(self.root, bg='gray20')
        control_frame.pack(side='bottom', fill='x', padx=5, pady=5)
        
        # Instructions
        instructions = tk.Label(
            control_frame,
            text="Controls: SPACE=Poll Data | R=Refresh | Q=Quit",
            bg='gray20',
            fg='lightgreen',
            font=('Courier', 10)
        )
        instructions.pack(side='left')
        
        # Manual poll button
        poll_btn = tk.Button(
            control_frame,
            text="Poll Data",
            command=self.manual_poll,
            bg='darkgreen',
            fg='white'
        )
        poll_btn.pack(side='right', padx=5)
        
    def manual_poll(self):
        """Trigger manual data poll"""
        print("Manual data poll triggered...")
        if hasattr(self, 'poll_callback') and self.poll_callback:
            self.poll_callback()
    
    def on_key_press(self, event):
        """Handle key presses"""
        if event.char == 'q':
            print("Quitting simulator...")
            self.root.quit()
        elif event.char == 'r':
            print("Refreshing display...")
            self.show()
        elif event.char == ' ':
            self.manual_poll()
    
    def set_poll_callback(self, callback):
        """Set callback for manual polling"""
        self.poll_callback = callback


# Mock MicroPython modules
class MockTime:
    @staticmethod
    def ticks_ms():
        return int(time.time() * 1000)
    
    @staticmethod
    def ticks_diff(new, old):
        return new - old
    
    @staticmethod
    def sleep(seconds):
        time.sleep(seconds)
        
    @staticmethod
    def localtime(secs=None):
        if secs is None:
            secs = time.time()
        return time.localtime(secs)


class MockMachine:
    class Pin:
        def __init__(self, *args, **kwargs):
            pass
    
    class SPI:
        def __init__(self, *args, **kwargs):
            pass
        
    class Timer:
        def __init__(self, *args, **kwargs):
            pass


class MockNetwork:
    STA_IF = 0
    
    class WLAN:
        def __init__(self, mode):
            print("[SIM] WiFi WLAN initialized")
        
        def active(self, state):
            print(f"[SIM] WiFi active: {state}")
        
        def connect(self, ssid, password):
            print(f"[SIM] Connecting to {ssid}...")
        
        def isconnected(self):
            return True
        
        def ifconfig(self):
            return ["192.168.1.100", "255.255.255.0", "192.168.1.1", "8.8.8.8"]


class MockRequests:
    @staticmethod
    def get(url, timeout=None):
        print(f"[SIM] HTTP GET: {url}")
        
        # Try real HTTP request first
        try:
            import requests
            response = requests.get(url, timeout=timeout)
            
            class Response:
                def __init__(self, resp):
                    self.status_code = resp.status_code
                    self.text = resp.text
                
                def close(self):
                    pass
            
            return Response(response)
            
        except Exception as e:
            print(f"[SIM] HTTP Error: {e}, using mock data")
            
            # Fallback to realistic mock data
            class MockResponse:
                def __init__(self):
                    self.status_code = 200
                    self.text = json.dumps({
                        "gridPower": 2500,      # 2.5kW grid import
                        "pvPower": 11000,       # 11kW PV generation
                        "batterySoc": 14,       # 14% battery SoC
                        "loadpoints": [{
                            "chargePower": 3000,  # Tesla 3kW charging
                            "soc": 100,           # Tesla 100% charged
                            "charging": False,    # Tesla not charging
                            "plugged": True       # Tesla plugged in
                        }, {
                            "chargePower": 0,     # Smart not charging
                            "soc": -1,            # Smart SoC unknown
                            "charging": False,    # Smart not charging
                            "plugged": False      # Smart not plugged
                        }]
                    })
                
                def close(self):
                    pass
            
            return MockResponse()


class MockGC:
    @staticmethod
    def collect():
        pass


# Mock LVGL
class MockLVGL:
    class ANIM:
        OFF = 0
    
    class PART:
        INDICATOR = 1
    
    @staticmethod
    def init():
        print("[SIM] LVGL initialized")
    
    @staticmethod
    def task_handler():
        pass
    
    @staticmethod
    def color_white():
        return 1
    
    @staticmethod
    def color_black():
        return 0
    
    class obj:
        def __init__(self, parent=None):
            pass
        def set_size(self, w, h): pass
        def set_pos(self, x, y): pass
        def center(self): pass
        def set_style_bg_color(self, color, part=0): pass
        def set_style_border_width(self, width, part=0): pass
        def set_style_pad_all(self, pad, part=0): pass
        def set_style_text_color(self, color, part=0): pass
    
    class label:
        def __init__(self, parent): pass
        def set_pos(self, x, y): pass
        def set_text(self, text): pass
        def set_style_text_color(self, color, part=0): pass
    
    class bar:
        def __init__(self, parent): pass
        def set_size(self, w, h): pass
        def set_pos(self, x, y): pass
        def set_range(self, min_val, max_val): pass
        def set_value(self, value, anim): pass
        def set_style_bg_color(self, color, part=0): pass
    
    class disp_drv_t:
        def __init__(self):
            self.buffer = None
            self.flush_cb = None
            self.hor_res = 0
            self.ver_res = 0
        def init(self): pass
    
    class disp_buf_t:
        def __init__(self): pass
        def init(self, buf1, buf2, size): pass
    
    @staticmethod
    def disp_drv_register(drv): pass
    
    @staticmethod
    def scr_load(scr): pass


# Mock FrameBuffer that connects to simulator
class MockFrameBuffer:
    def __init__(self, buffer, width, height, format):
        self.buffer = buffer
        self.width = width
        self.height = height
        self.simulator = EInkSimulator(width, height)
    
    def fill(self, color):
        self.simulator.fill(color)
    
    def pixel(self, x, y, color):
        self.simulator.pixel(x, y, color)
    
    def text(self, text, x, y, color=1):
        self.simulator.text(text, x, y, color)
    
    def rect(self, x, y, w, h, color):
        self.simulator.rect(x, y, w, h, color)
    
    def fill_rect(self, x, y, w, h, color):
        self.simulator.fill_rect(x, y, w, h, color)


# Mock E-ink display
class MockEInkDisplay:
    def __init__(self):
        self.width = 212
        self.height = 104
    
    def init(self):
        print("[SIM] E-ink display initialized")
    
    def Clear(self):
        print("[SIM] E-ink display cleared")
    
    def display(self, buffer):
        print("[SIM] E-ink display updated")


def setup_mocks():
    """Setup all module mocks"""
    # Replace modules with mocks
    sys.modules['time'] = MockTime()
    sys.modules['machine'] = MockMachine()
    sys.modules['network'] = MockNetwork()
    sys.modules['urequests'] = MockRequests()
    sys.modules['ujson'] = json
    sys.modules['gc'] = MockGC()
    sys.modules['lvgl'] = MockLVGL()
    
    # Mock framebuf
    sys.modules['framebuf'] = type('MockFramebuf', (), {
        'FrameBuffer': MockFrameBuffer,
        'MONO_HLSB': 0
    })()
    
    # Mock e-ink drivers
    sys.modules['epaper2in13_V3'] = type('MockEPaper', (), {
        'EPD_2in13_V3': MockEInkDisplay
    })()
    sys.modules['epaper2in13'] = type('MockEPaper', (), {
        'EPD_2in13': MockEInkDisplay
    })()


def run_main_simulator():
    """Run the main.py logic in simulator"""
    print("="*60)
    print("EVCC E-Ink Display Simulator")
    print("="*60)
    print("Features:")
    print("- Real main.py logic execution")
    print("- 212x104 pixel e-ink simulation")
    print("- LVGL UI with live/mock data")
    print("- Interactive controls")
    print()
    print("Controls:")
    print("- SPACE: Manual data poll")
    print("- R: Refresh display")
    print("- Q: Quit")
    print("- Button: Poll Data")
    print()
    
    # Setup all mocks before importing main
    setup_mocks()
    
    # Read and modify main.py for faster testing
    with open("main.py", "r") as f:
        source_code = f.read()
    
    # Speed up polling for testing
    modified_source = source_code.replace(
        "POLL_INTERVAL_MS = 30000",
        "POLL_INTERVAL_MS = 3000"  # 3 second polls
    ).replace(
        "DATA_STALE_MS = 120000",
        "DATA_STALE_MS = 15000"    # 15 second timeout
    )
    
    # Create execution namespace
    namespace = {}
    
    print("Initializing simulator...")
    
    try:
        # Execute the modified main.py
        exec(modified_source, namespace)
        
        # Setup manual polling if display exists
        if 'display' in namespace:
            display_obj = namespace['display']
            if hasattr(display_obj, 'framebuf') and hasattr(display_obj.framebuf, 'simulator'):
                simulator = display_obj.framebuf.simulator
                
                def manual_poll():
                    if 'poll_and_update' in namespace:
                        result = namespace['poll_and_update']()
                        print(f"[SIM] Poll result: {'Success' if result else 'Failed'}")
                
                simulator.set_poll_callback(manual_poll)
                print("Manual polling enabled - press SPACE or click button")
        
        print("\nStarting main application...")
        
        # Run the main function
        if 'main' in namespace:
            namespace['main']()
        else:
            print("Error: main() function not found in main.py")
    
    except KeyboardInterrupt:
        print("\nSimulator stopped by user")
    except Exception as e:
        print(f"\nError running simulator: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_main_simulator()