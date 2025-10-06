#!/usr/bin/env python3
"""
Unified E-Ink Display Simulator
Combines visual interface with actual main.py execution for comprehensive testing
"""

import tkinter as tk
import time
import json
import sys
import threading
from icons import draw_sun_icon_small


# Mock modules for MicroPython
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
    
    @staticmethod
    def time():
        return time.time()


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
            print("[SIM] WiFi initialized")
        
        def active(self, state):
            pass
        
        def connect(self, ssid, password):
            print(f"[SIM] Connected to {ssid}")
        
        def isconnected(self):
            return True
        
        def ifconfig(self):
            return ["192.168.1.100", "255.255.255.0", "192.168.1.1", "8.8.8.8"]


class MockRequests:
    @staticmethod
    def get(url, timeout=None):
        print(f"[SIM] API Call: {url[:50]}...")
        
        # Try real HTTP request first - import real requests, not mocked
        try:
            # Import the real requests module directly
            import importlib
            import sys
            
            # Temporarily save the mocked modules
            saved_time = sys.modules.get('time')
            
            # Restore real time module for requests
            if 'time' in sys.modules:
                del sys.modules['time']
            
            # Import real modules
            import time
            import requests
            
            print("[SIM] Making real HTTP request to EVCC...")
            response = requests.get(url, timeout=timeout or 10)
            
            # Restore mocked time
            if saved_time:
                sys.modules['time'] = saved_time
            
            class RealResponse:
                def __init__(self, resp):
                    self.status_code = resp.status_code
                    self.text = resp.text
                    print(f"[SIM] Live EVCC data received "
                          f"(status: {resp.status_code})")
                    
                    # Store the data for simulator display
                    try:
                        data = resp.json()
                        # Find the simulator instance in the call stack
                        import inspect
                        for frame_info in inspect.stack():
                            frame = frame_info.frame
                            if 'self' in frame.f_locals:
                                obj = frame.f_locals['self']
                                if hasattr(obj, 'current_data') and hasattr(obj, 'data_display'):
                                    obj.current_data = data
                                    obj.data_display.delete(1.0, tk.END)
                                    obj.data_display.insert(tk.END, json.dumps(data, indent=2))
                                    break
                    except Exception as e:
                        print(f"[SIM] Error storing data for display: {e}")
                
                def close(self):
                    pass
            
            return RealResponse(response)
            
        except Exception as e:
            print(f"[SIM] EVCC endpoint unreachable ({e}), using mock data")
            
            class MockResponse:
                def __init__(self):
                    self.status_code = 200
                    self.text = json.dumps({
                        "gridPower": 2500,
                        "pvPower": 11000,
                        "batterySoc": 14,
                        "loadpoints": [
                            {"chargePower": 3000, "soc": 100, 
                             "charging": False, "plugged": True},
                            {"chargePower": 0, "soc": -1, 
                             "charging": False, "plugged": False}
                        ]
                    })
                
                def close(self):
                    pass
            
            return MockResponse()


class MockGC:
    @staticmethod
    def collect():
        pass
    
    @staticmethod
    def isenabled():
        return True
    
    @staticmethod
    def enable():
        pass
    
    @staticmethod
    def disable():
        pass


# Mock LVGL with visual feedback
class MockLVGL:
    def __init__(self, simulator):
        self.simulator = simulator
    
    class ANIM:
        OFF = 0
    
    class PART:
        INDICATOR = 1
    
    def init(self):
        self.simulator.log("LVGL initialized")
    
    def task_handler(self):
        # Add debug logging
        print("[SIM] LVGL task_handler called - triggering visual update")
        
        # Trigger visual update when LVGL processes
        if hasattr(self.simulator, 'update_visual_display'):
            self.simulator.update_visual_display()
        # Also trigger framebuffer content display specifically
        if hasattr(self.simulator, 'show_framebuffer_content'):
            if (hasattr(self.simulator, 'main_running') and
                self.simulator.main_running and
                'display' in self.simulator.main_namespace):
                display_obj = self.simulator.main_namespace['display']
                if (hasattr(display_obj, 'framebuf') and
                    hasattr(display_obj.framebuf, 'pixel_data')):
                    self.simulator.show_framebuffer_content()
    
    def color_white(self):
        return 1
    
    def color_black(self):
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
        def __init__(self, parent): 
            pass
        def set_pos(self, x, y): 
            pass
        def set_text(self, text): 
            # Log important text updates
            if any(word in text.lower() for word in 
                   ['kw', 'charging', 'battery', 'tesla', 'smart']):
                print(f"[SIM] LVGL Label: {text}")
        def set_style_text_color(self, color, part=0): 
            pass
    
    class bar:
        def __init__(self, parent): 
            pass
        def set_size(self, w, h): 
            pass
        def set_pos(self, x, y): 
            pass
        def set_range(self, min_val, max_val): 
            pass
        def set_value(self, value, anim): 
            # Log battery level updates
            if 0 <= value <= 100:
                print(f"[SIM] Battery level: {value}%")
        def set_style_bg_color(self, color, part=0): 
            pass
    
    class disp_drv_t:
        def __init__(self):
            self.buffer = None
            self.flush_cb = None
            self.hor_res = 0
            self.ver_res = 0
        def init(self): 
            pass
    
    class disp_buf_t:
        def __init__(self): 
            pass
        def init(self, buf1, buf2, size): 
            pass
    
    def disp_drv_register(self, drv): 
        pass
    
    def scr_load(self, scr): 
        pass


# Mock FrameBuffer that connects to simulator
class MockFrameBuffer:
    def __init__(self, buffer, width, height, format, simulator):
        self.buffer = buffer
        # Ensure width and height are integers, not bytearrays
        self.width = int(width) if width is not None else 212
        self.height = int(height) if height is not None else 104
        self.simulator = simulator
        
        # Track framebuffer state for icon drawing
        self.pixel_data = {}  # Store pixel data as {(x, y): color}
    
    def fill(self, color):
        """Fill entire framebuffer with color"""
        self.simulator.fill(color)
        if color == 0:  # Clear
            self.pixel_data.clear()
        else:  # Fill with color
            for y in range(self.height):
                for x in range(self.width):
                    self.pixel_data[(x, y)] = color
    
    def pixel(self, x, y, color):
        """Set pixel in framebuffer and simulator"""
        # Ensure coordinates are integers
        try:
            x = int(x)
            y = int(y)
            color = int(color)
        except (ValueError, TypeError):
            return  # Skip invalid pixel operations
            
        if 0 <= x < self.width and 0 <= y < self.height and color:
            self.pixel_data[(x, y)] = color
            self.simulator.pixel(x, y, color)
            
            # Trigger visual update when pixels are drawn (for icons)
            if len(self.pixel_data) > 0 and len(self.pixel_data) % 25 == 0:
                # Update every 25 pixels to catch icon drawing
                if hasattr(self.simulator, 'show_framebuffer_content'):
                    self.simulator.show_framebuffer_content(self.pixel_data)
    
    def text(self, text, x, y, color=1):
        """Draw text on framebuffer"""
        self.simulator.text(text, x, y, color)
    
    def rect(self, x, y, w, h, color):
        """Draw rectangle outline"""
        # Draw outline pixels to both simulator and pixel data
        for i in range(w):
            self.pixel(x + i, y, color)  # Top
            self.pixel(x + i, y + h - 1, color)  # Bottom
        for i in range(h):
            self.pixel(x, y + i, color)  # Left
            self.pixel(x + w - 1, y + i, color)  # Right
    
    def fill_rect(self, x, y, w, h, color):
        """Draw filled rectangle"""
        for dy in range(h):
            for dx in range(w):
                self.pixel(x + dx, y + dy, color)
    
    def line(self, x0, y0, x1, y1, color):
        """Draw line using Bresenham's algorithm"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        while True:
            self.pixel(x, y, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
    
    def blit(self, source, x, y, *args, **kwargs):
        """Blit operation for copying pixel data"""
        # Handle bitmap blitting if source has pixel data
        if hasattr(source, 'pixel_data'):
            for (sx, sy), color in source.pixel_data.items():
                self.pixel(x + sx, y + sy, color)


# Mock E-ink display
class MockEInkDisplay:
    def __init__(self, simulator):
        self.width = 212
        self.height = 104
        self.simulator = simulator
    
    def init(self):
        self.simulator.log("E-ink display initialized")
    
    def Clear(self):
        self.simulator.log("E-ink display cleared")
    
    def display(self, buffer):
        self.simulator.log("E-ink display updated")
        # Trigger visual update when display is refreshed
        if hasattr(self.simulator, 'show_framebuffer_content'):
            self.simulator.show_framebuffer_content()


class UnifiedEInkSimulator:
    """Unified E-Ink simulator with visual interface and main.py execution"""
    
    def __init__(self):
        self.width = 212
        self.height = 104
        self.scale = 4
        
        # Data for display
        self.current_data = None
        self.last_update = time.time()
        self.use_live_data = True
        self.evcc_connected = False
        self.main_namespace = {}
        self.main_running = False
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("Unified EVCC E-Ink Display Simulator")
        self.root.configure(bg='#2b2b2b')
        self.root.geometry("1200x800")
        
        self.setup_ui()
        self.setup_mocks()
        
        print("Unified E-Ink simulator ready!")
    
    def setup_ui(self):
        """Setup the user interface"""
        # Header
        header = tk.Frame(self.root, bg='#1e1e1e', height=60)
        header.pack(fill='x', padx=10, pady=5)
        header.pack_propagate(False)
        
        title = tk.Label(
            header,
            text="Unified EVCC E-Ink Display Simulator (212x104)",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 16, 'bold')
        )
        title.pack(side='left', pady=15, padx=10)
        
        # Connection status
        self.connection_status = tk.Label(
            header,
            text="● OFFLINE",
            bg='#1e1e1e',
            fg='red',
            font=('Arial', 12, 'bold')
        )
        self.connection_status.pack(side='right', pady=15, padx=10)
        
        # Main content area
        content = tk.Frame(self.root, bg='#2b2b2b')
        content.pack(fill='both', expand=True, padx=10)
        
        # Display area
        display_frame = tk.LabelFrame(
            content,
            text="E-Ink Display Preview (Actual main.py execution)",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 12, 'bold')
        )
        display_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Canvas container
        canvas_container = tk.Frame(display_frame, bg='black', 
                                   relief='sunken', bd=3)
        canvas_container.pack(pady=10, padx=10)
        
        # Canvas for e-ink display
        canvas_width = self.width * self.scale
        canvas_height = self.height * self.scale
        self.canvas = tk.Canvas(
            canvas_container,
            width=canvas_width,
            height=canvas_height,
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack(padx=5, pady=5)
        
        # Control panel
        control_frame = tk.LabelFrame(
            content,
            text="Controls & Status",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 12, 'bold'),
            width=320
        )
        control_frame.pack(side='right', fill='y')
        control_frame.pack_propagate(False)
        
        # Status display
        self.status_text = tk.Text(
            control_frame,
            bg='#1e1e1e',
            fg='lightgreen',
            font=('Courier', 9),
            height=12,
            width=38
        )
        self.status_text.pack(pady=10, padx=10, fill='x')
        
        # Control buttons
        button_frame = tk.Frame(control_frame, bg='#2b2b2b')
        button_frame.pack(pady=10, padx=10, fill='x')
        
        # Main simulation button
        self.main_btn = tk.Button(
            button_frame,
            text="▶ Start Main.py Simulation",
            command=self.toggle_main_simulation,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10, 'bold'),
            height=2
        )
        self.main_btn.pack(fill='x', pady=5)
        
        # Poll button
        tk.Button(
            button_frame,
            text="📡 Poll Data Now",
            command=self.manual_poll,
            bg='#2196F3',
            fg='white',
            font=('Arial', 10)
        ).pack(fill='x', pady=5)
        
        # Toggle live/mock data button
        self.data_mode_btn = tk.Button(
            button_frame,
            text="🌐 Mode: Live Data",
            command=self.toggle_data_mode,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10)
        )
        self.data_mode_btn.pack(fill='x', pady=5)
        
        # Test display button
        tk.Button(
            button_frame,
            text="🧪 Test Display",
            command=self.test_display,
            bg='#FF9800',
            fg='white',
            font=('Arial', 10)
        ).pack(fill='x', pady=5)
        
        # Clear button
        tk.Button(
            button_frame,
            text="🗑 Clear Display",
            command=self.clear_display,
            bg='#f44336',
            fg='white',
            font=('Arial', 10)
        ).pack(fill='x', pady=5)
        
        # Data display
        data_frame = tk.LabelFrame(
            control_frame,
            text="Live EVCC Data",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        data_frame.pack(pady=10, padx=10, fill='both', expand=True)
        
        self.data_display = tk.Text(
            data_frame,
            bg='#1e1e1e',
            fg='cyan',
            font=('Courier', 8),
            height=10
        )
        self.data_display.pack(pady=5, padx=5, fill='both', expand=True)
        
        # Bind keyboard events
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.focus_set()
        
        # Initialize
        self.log("Unified simulator initialized")
        self.log("Ready to run actual main.py with visual feedback")
        self.log("Features: Live EVCC data + Visual UI + Real main.py code")
        
        # Auto-start main.py simulation by default
        self.root.after(1000, self.auto_start_simulation)
    
    def setup_mocks(self):
        """Setup all module mocks"""
        # Replace modules with mocks
        sys.modules['time'] = MockTime()
        sys.modules['machine'] = MockMachine()
        sys.modules['network'] = MockNetwork()
        sys.modules['urequests'] = MockRequests()
        sys.modules['ujson'] = json
        sys.modules['gc'] = MockGC()
        
        # Mock LVGL with visual feedback
        sys.modules['lvgl'] = MockLVGL(self)
        
        # Mock framebuf that connects to our visual display
        def create_mock_framebuffer(*args, **kwargs):
            # Handle variable number of arguments from FrameBuffer(buffer, width, height, format)
            buffer = args[0] if len(args) > 0 else None
            width = args[1] if len(args) > 1 else 212
            height = args[2] if len(args) > 2 else 104
            format_type = args[3] if len(args) > 3 else 0
            
            # Ensure width and height are integers
            if isinstance(width, (bytes, bytearray)):
                width = 212  # Default width if buffer passed as width
            if isinstance(height, (bytes, bytearray)):
                height = 104  # Default height if buffer passed as height
                
            return MockFrameBuffer(buffer, width, height, format_type, self)
        
        sys.modules['framebuf'] = type('MockFramebuf', (), {
            'FrameBuffer': create_mock_framebuffer,
            'MONO_HLSB': 0
        })()
        
        # Mock e-ink drivers that connect to our visual display
        def create_epd_v3(*args, **kwargs):
            return MockEInkDisplay(self)
        
        def create_epd(*args, **kwargs):
            return MockEInkDisplay(self)
        
        sys.modules['epaper2in13_V3'] = type('MockEPaper', (), {
            'EPD_2in13_V3': create_epd_v3
        })()
        sys.modules['epaper2in13'] = type('MockEPaper', (), {
            'EPD_2in13': create_epd
        })()
        
        # IMPORTANT: Don't mock icons.py - let it use the real module
        # This allows main.py to use actual icon drawing functions
        # The icons will be drawn on the MockFrameBuffer and captured
        # Icons.py has been patched to handle bytearray comparison issues
    
    def on_key_press(self, event):
        """Handle key presses"""
        if event.char == 'q':
            self.root.quit()
        elif event.char == 'r':
            self.update_visual_display()
        elif event.char == ' ':
            self.manual_poll()
        elif event.char == 'm':
            self.toggle_main_simulation()
    
    def log(self, message):
        """Add message to status log"""
        try:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            log_msg = f"[{timestamp}] {message}\n"
            if hasattr(self, 'status_text') and self.status_text.winfo_exists():
                self.status_text.insert(tk.END, log_msg)
                self.status_text.see(tk.END)
                self.root.update()
        except tk.TclError:
            # Widget has been destroyed, print to console instead
            print(f"[LOG] {message}")
    
    def auto_start_simulation(self):
        """Auto-start main.py simulation on startup"""
        self.log("🚀 Auto-starting main.py simulation...")
        self.start_main_simulation()
        
        # Perform initial data fetch after a short delay
        self.root.after(2000, self.initial_data_fetch)
    
    def initial_data_fetch(self):
        """Perform initial data fetch"""
        self.log("📡 Performing initial data fetch...")
        self.manual_poll()
    
    def toggle_main_simulation(self):
        """Toggle main.py simulation"""
        if not self.main_running:
            self.start_main_simulation()
        else:
            self.stop_main_simulation()
    
    def start_main_simulation(self):
        """Start running the actual main.py simulation"""
        if self.main_running:
            return  # Already running
            
        self.log("🚀 Starting main.py simulation...")
        self.main_btn.config(text="⏹ Stop Main.py Simulation", bg='#f44336')
        self.main_running = True
        
        def run_simulation():
            try:
                # Read and execute main.py
                with open("main.py", "r") as f:
                    source_code = f.read()
                
                # Speed up polling for testing
                modified_source = source_code.replace(
                    "POLL_INTERVAL_MS = 30000",
                    "POLL_INTERVAL_MS = 5000"  # 5 second polls
                ).replace(
                    "DATA_STALE_MS = 120000",
                    "DATA_STALE_MS = 20000"    # 20 second timeout
                )
                
                # Execute the modified main.py
                exec(modified_source, self.main_namespace)
                
                self.log("✅ main.py executed successfully")
                self.log("📊 Live EVCC integration active")
                
                # Setup periodic visual updates
                self.start_periodic_updates()
                
            except Exception as e:
                self.log(f"❌ Error in main.py simulation: {e}")
                self.main_running = False
                self.main_btn.config(text="▶ Start Main.py Simulation", 
                                   bg='#4CAF50')
                import traceback
                traceback.print_exc()
        
        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=run_simulation, daemon=True)
        thread.start()
    
    def stop_main_simulation(self):
        """Stop main.py simulation"""
        self.log("⏹ Stopping main.py simulation...")
        self.main_running = False
        self.main_btn.config(text="▶ Start Main.py Simulation", bg='#4CAF50')
    
    def start_periodic_updates(self):
        """Start periodic display updates"""
        def update():
            if self.main_running:
                # Trigger main.py poll if available
                if 'poll_and_update' in self.main_namespace:
                    try:
                        result = self.main_namespace['poll_and_update']()
                        if result:
                            self.log("📡 Main.py poll successful")
                        else:
                            self.log("⚠ Main.py poll failed")
                    except Exception as e:
                        self.log(f"❌ Poll error: {e}")
                
                # Update visual display
                self.update_visual_display()
                
                # Schedule next update
                self.root.after(5000, update)
        
        # Perform immediate initial poll and then start regular updates
        self.log("📊 Starting periodic updates with immediate poll...")
        if 'poll_and_update' in self.main_namespace:
            try:
                result = self.main_namespace['poll_and_update']()
                self.log(f"📡 Initial poll: {'Success' if result else 'Failed'}")
                self.update_visual_display()
            except Exception as e:
                self.log(f"❌ Initial poll error: {e}")
        
        # Start regular updates
        self.root.after(5000, update)
    
    def toggle_data_mode(self):
        """Toggle between live and mock data"""
        self.use_live_data = not self.use_live_data
        mode_text = "Live Data" if self.use_live_data else "Mock Data"
        icon = "🌐" if self.use_live_data else "🧪"
        self.data_mode_btn.config(text=f"{icon} Mode: {mode_text}")
        
        if self.use_live_data:
            self.data_mode_btn.config(bg='#4CAF50')
            self.log("🌐 Switched to live EVCC data mode")
        else:
            self.data_mode_btn.config(bg='#FF9800')
            self.log("🧪 Switched to mock data mode")
        
        # Immediately poll with new mode
        self.manual_poll()
    
    def update_connection_status(self, connected):
        """Update the connection status indicator"""
        self.evcc_connected = connected
        if connected:
            self.connection_status.config(text="● ONLINE", fg='green')
        else:
            self.connection_status.config(text="● OFFLINE", fg='red')
    
    def manual_poll(self):
        """Manual data poll"""
        if self.main_running and 'poll_and_update' in self.main_namespace:
            # Use main.py polling
            try:
                result = self.main_namespace['poll_and_update']()
                self.log(f"📡 Main.py poll: {'Success' if result else 'Failed'}")
                self.update_visual_display()
                return
            except Exception as e:
                self.log(f"❌ Main.py poll error: {e}")
        
        # Fallback to manual polling
        self.log("📡 Manual polling EVCC data...")
        
        if not self.use_live_data:
            self.log("🧪 Using mock data (live mode disabled)")
            self.update_connection_status(False)
            data = self.get_mock_data()
            self.current_data = data
            self.update_display_from_data(data)
            return
        
        # Try live EVCC data
        base_url = "http://192.168.178.29:7070/api/state"
        jq_query = ("?jq=%7BgridPower:.grid.power,pvPower:.pvPower,"
                   "batterySoc:.batterySoc,loadpoints:[.loadpoints[0],"
                   ".loadpoints[1]]%7Cmap(select(.!=null)%7C%7B"
                   "chargePower:.chargePower,soc:(.vehicleSoc//.soc),"
                   "charging:.charging,plugged:(.connected//.plugged)%7D)%7D")
        url = base_url + jq_query
        
        try:
            # Use real requests module, not mocked
            import importlib
            import sys
            
            # Temporarily save the mocked modules
            saved_time = sys.modules.get('time')
            
            # Import real modules
            if 'time' in sys.modules:
                del sys.modules['time']
            
            import time as real_time
            import requests
            
            # Restore mocked time
            if saved_time:
                sys.modules['time'] = saved_time
            
            self.log("🌐 Attempting live EVCC connection...")
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✅ Live EVCC data received!")
                self.update_connection_status(True)
                self.current_data = data
                self.update_display_from_data(data)
                return
            else:
                self.log(f"❌ EVCC returned status {response.status_code}")
                self.update_connection_status(False)
                
        except ImportError as e:
            self.log(f"❌ Import error: {e}")
            self.update_connection_status(False)
        except Exception as e:
            if 'Timeout' in str(e) or 'timeout' in str(e):
                self.log("❌ EVCC connection timeout")
            elif 'Connection' in str(e) or 'connection' in str(e):
                self.log("❌ EVCC connection refused - is EVCC running?")
            else:
                self.log(f"❌ EVCC error: {e}")
            self.update_connection_status(False)
        
        # Fallback to mock data
        self.log("🧪 Using mock data as fallback")
        data = self.get_mock_data()
        self.current_data = data
        self.update_display_from_data(data)
    
    def get_mock_data(self):
        """Get mock EVCC data"""
        return {
            "gridPower": 2500,
            "pvPower": 11000,
            "batterySoc": 14,
            "loadpoints": [
                {"chargePower": 3000, "soc": 100, 
                 "charging": False, "plugged": True},
                {"chargePower": 0, "soc": -1, 
                 "charging": False, "plugged": False}
            ]
        }
    
    # Visual display methods (similar to visual_simulator)
    def clear_display(self):
        """Clear the display"""
        self.canvas.delete("all")
        self.canvas.configure(bg='black')
        self.log("🗑 Display cleared")
    
    def update_visual_display(self):
        """Update the visual display based on main.py state"""
        # Always try to show actual framebuffer content first
        if self.main_running and 'display' in self.main_namespace:
            display_obj = self.main_namespace['display']
            if hasattr(display_obj, 'framebuf'):
                if hasattr(display_obj.framebuf, 'pixel_data'):
                    pixel_data = display_obj.framebuf.pixel_data
                    self.log(f"🔍 Checking framebuffer: {len(pixel_data)} pixels")
                    if self.show_framebuffer_content(pixel_data):
                        return  # Successfully showed framebuffer
                else:
                    self.log("⚠️ Framebuffer missing pixel_data attribute")
            else:
                self.log("⚠️ Display object missing framebuf attribute")
        else:
            self.log("⚠️ Main not running or display object not found")
        
        # Fallback: Try to get data from main.py namespace and show data-based display
        if self.main_running and 'data' in self.main_namespace:
            main_data = self.main_namespace['data']
            if hasattr(main_data, 'pv_kw'):
                # Convert main.py data to our format
                data = {
                    "gridPower": getattr(main_data, 'evu_kw', 0) * 1000,  # Fixed field name
                    "pvPower": getattr(main_data, 'pv_kw', 0) * 1000,
                    "batterySoc": getattr(main_data, 'battery_soc', 0),
                    "loadpoints": [
                        {
                            "chargePower": getattr(main_data, 'lp1_power_kw', 0) * 1000,
                            "soc": getattr(main_data, 'lp1_soc', 0),
                            "charging": getattr(main_data, 'lp1_is_charging', False),
                            "plugged": getattr(main_data, 'lp1_plug_stat', False)
                        },
                        {
                            "chargePower": getattr(main_data, 'lp2_power_kw', 0) * 1000,
                            "soc": getattr(main_data, 'lp2_soc', 0),
                            "charging": getattr(main_data, 'lp2_is_charging', False),
                            "plugged": getattr(main_data, 'lp2_plug_stat', False)
                        }
                    ]
                }
                self.current_data = data  # Update current data
                self.log("📊 Using main.py data for display")
                self.update_display_from_data(data)
                return
        
        # Final fallback to stored current data
        if self.current_data:
            self.log("📊 Using stored current data")
            self.update_display_from_data(self.current_data)
        else:
            # Show black screen as final fallback
            self.clear_display()
            self.log("📺 No data available - showing blank screen")
    
    def show_framebuffer_content(self, pixel_data=None):
        """Show the actual framebuffer content with real icons"""
        self.canvas.delete("all")
        self.canvas.configure(bg='black')  # Start with black background
        
        # If pixel_data is provided, use it; otherwise use the mock framebuffer
        if pixel_data is None and self.main_running and 'display' in self.main_namespace:
            display_obj = self.main_namespace['display']
            if hasattr(display_obj, 'framebuf') and hasattr(display_obj.framebuf, 'pixel_data'):
                pixel_data = display_obj.framebuf.pixel_data
                self.log(f"📺 Found framebuffer with {len(pixel_data)} pixels")
        
        if pixel_data and len(pixel_data) > 0:
            # Draw each pixel from the framebuffer
            pixel_count = 0
            for (x, y), color in pixel_data.items():
                try:
                    if color and 0 <= x < self.width and 0 <= y < self.height:
                        px = x * self.scale
                        py = y * self.scale
                        self.canvas.create_rectangle(
                            px, py, px + self.scale, py + self.scale,
                            fill='white', outline='white'
                        )
                        pixel_count += 1
                except (ValueError, TypeError):
                    continue
            
            if pixel_count > 0:
                self.log(f"🎨 Rendered framebuffer: {pixel_count} pixels")
                
                # Also update the data display with current data
                if self.current_data:
                    self.update_data_display_only(self.current_data)
                
                return True  # Successfully showed framebuffer content
            else:
                self.log("📺 Framebuffer has no visible pixels")
        else:
            self.log("📺 No framebuffer content available")
            
        return False  # Failed to show framebuffer content
    
    def draw_text(self, text, x, y, size=10, color='white'):
        """Draw text on the display"""
        canvas_x = x * self.scale
        canvas_y = y * self.scale
        
        self.canvas.create_text(
            canvas_x, canvas_y,
            text=text,
            fill=color,
            font=('Courier', size, 'bold'),
            anchor='nw'
        )
    
    def draw_rect(self, x, y, w, h, fill=False, color='white'):
        """Draw rectangle"""
        x1 = x * self.scale
        y1 = y * self.scale
        x2 = (x + w) * self.scale
        y2 = (y + h) * self.scale
        
        if fill:
            self.canvas.create_rectangle(x1, y1, x2, y2, 
                                       fill=color, outline=color)
        else:
            self.canvas.create_rectangle(x1, y1, x2, y2, 
                                       fill='', outline=color, width=2)
    
    def draw_bar(self, x, y, w, h, value, max_val=100, color='white'):
        """Draw a progress bar"""
        # Border
        self.draw_rect(x, y, w, h, fill=False, color=color)
        
        # Fill
        if value > 0 and max_val > 0:
            fill_width = int(w * value / max_val)
            if fill_width > 2:
                self.draw_rect(x+1, y+1, fill_width-2, h-2, 
                             fill=True, color=color)
    
    def draw_sun_symbol(self, x, y):
        """Draw a simple sun symbol"""
        center_x = x + 8
        center_y = y + 8
        
        # Sun rays
        self.canvas.create_line(
            (center_x - 6) * self.scale, center_y * self.scale,
            (center_x + 6) * self.scale, center_y * self.scale,
            fill='white', width=2
        )
        self.canvas.create_line(
            center_x * self.scale, (center_y - 6) * self.scale,
            center_x * self.scale, (center_y + 6) * self.scale,
            fill='white', width=2
        )
        
        # Sun circle
        self.canvas.create_oval(
            (center_x - 4) * self.scale, (center_y - 4) * self.scale,
            (center_x + 4) * self.scale, (center_y + 4) * self.scale,
            outline='white', width=2
        )
    
    def test_display(self):
        """Test display with sample layout"""
        self.clear_display()
        
        # Title
        self.draw_text("EVCC Test Display", 5, 2, 10)
        
        # Sun icon for PV
        self.draw_sun_symbol(5, 18)
        
        # Grid/PV
        self.draw_text("PV: 11.0kW", 25, 18, 8)
        self.draw_text("Grid: 2.5kW", 110, 18, 8)
        
        # Battery
        self.draw_text("Battery: 14%", 5, 32, 8)
        self.draw_bar(5, 44, 80, 8, 14, 100)
        
        # Loadpoints
        self.draw_text("Tesla: 100% RDY", 5, 58, 8)
        self.draw_text("3.0kW", 140, 58, 8)
        
        self.draw_text("Smart: Not Connected", 5, 72, 8)
        self.draw_text("0.0kW", 140, 72, 8)
        
        # Status
        timestamp = time.strftime("%H:%M:%S")
        self.draw_text(f"Updated: {timestamp}", 5, 90, 7)
        
        self.log("🧪 Test display rendered")
    
    def update_data_display_only(self, data):
        """Update only the data display window without changing the visual canvas"""
        try:
            if hasattr(self, 'data_display') and self.data_display.winfo_exists():
                self.data_display.delete(1.0, tk.END)
                self.data_display.insert(tk.END, json.dumps(data, indent=2))
                self.log("📊 Data display updated")
        except tk.TclError:
            # Widget has been destroyed, ignore
            pass
    
    def update_display_from_data(self, data):
        """Update display using actual EVCC data"""
        self.clear_display()
        
        # Title
        self.draw_text("EVCC Energy Monitor", 5, 2, 9)
        
        # Sun icon for PV
        self.draw_sun_symbol(5, 16)
        
        # Grid Power
        grid_kw = data.get('gridPower', 0) / 1000
        grid_text = f"Grid: {grid_kw:+.1f}kW"
        self.draw_text(grid_text, 110, 16, 8)
        
        # PV Power
        pv_kw = data.get('pvPower', 0) / 1000
        pv_text = f"PV: {pv_kw:.1f}kW"
        self.draw_text(pv_text, 25, 16, 8)
        
        # Battery
        battery_soc = data.get('batterySoc', 0)
        battery_text = f"Battery: {battery_soc}%"
        self.draw_text(battery_text, 5, 30, 8)
        self.draw_bar(5, 42, 80, 8, battery_soc)
        
        # Loadpoints
        loadpoints = data.get('loadpoints', [])
        
        # Tesla (LP1)
        if len(loadpoints) > 0:
            lp1 = loadpoints[0]
            # Get vehicle name from main.py data if available
            vehicle_name = "Tesla"
            if (self.main_running and 'data' in self.main_namespace and 
                hasattr(self.main_namespace['data'], 'lp1_vehicle_name')):
                vehicle_name = self.main_namespace['data'].lp1_vehicle_name
            
            if lp1.get('plugged', False):
                soc = lp1.get('soc', 0)
                charging = 'CHG' if lp1.get('charging', False) else 'RDY'
                power = lp1.get('chargePower', 0) / 1000
                self.draw_text(f"{vehicle_name}: {soc}% {charging}", 5, 56, 8)
                self.draw_text(f"{power:.1f}kW", 140, 56, 8)
            else:
                self.draw_text(f"{vehicle_name}: Not Connected", 5, 56, 8)
                self.draw_text("0.0kW", 140, 56, 8)
        
        # Smart (LP2)
        if len(loadpoints) > 1:
            lp2 = loadpoints[1]
            # Get vehicle name from main.py data if available
            vehicle_name = "Smart"
            if (self.main_running and 'data' in self.main_namespace and 
                hasattr(self.main_namespace['data'], 'lp2_vehicle_name')):
                vehicle_name = self.main_namespace['data'].lp2_vehicle_name
            
            if lp2.get('plugged', False):
                soc = lp2.get('soc', 0)
                if soc < 0:
                    soc_text = "??"
                else:
                    soc_text = f"{soc}%"
                charging = 'CHG' if lp2.get('charging', False) else 'RDY'
                power = lp2.get('chargePower', 0) / 1000
                self.draw_text(f"{vehicle_name}: {soc_text} {charging}", 5, 70, 8)
                self.draw_text(f"{power:.1f}kW", 140, 70, 8)
            else:
                self.draw_text(f"{vehicle_name}: Not Connected", 5, 70, 8)
                self.draw_text("0.0kW", 140, 70, 8)
        
        # Timestamp
        timestamp = time.strftime("%H:%M:%S")
        self.draw_text(f"Updated: {timestamp}", 5, 88, 7)
        
        # Update data display
        self.data_display.delete(1.0, tk.END)
        self.data_display.insert(tk.END, json.dumps(data, indent=2))
        
        self.log("📊 Display updated with data")
    
    # Mock framebuffer interface for main.py
    def fill(self, color):
        """Mock framebuffer fill"""
        if color == 0:
            self.clear_display()
        # Trigger visual update after fill
        if hasattr(self, 'update_visual_display'):
            self.update_visual_display()
    
    def pixel(self, x, y, color):
        """Mock framebuffer pixel"""
        if color and 0 <= x < self.width and 0 <= y < self.height:
            px = x * self.scale
            py = y * self.scale
            self.canvas.create_rectangle(px, py, px+self.scale, py+self.scale,
                                       fill='white', outline='white')
    
    def text(self, text, x, y, color=1):
        """Mock framebuffer text"""
        if color:
            self.draw_text(text, x, y, 8)
    
    def rect(self, x, y, w, h, color):
        """Mock framebuffer rectangle"""
        if color:
            self.draw_rect(x, y, w, h, fill=False)
    
    def fill_rect(self, x, y, w, h, color):
        """Mock framebuffer filled rectangle"""
        if color:
            self.draw_rect(x, y, w, h, fill=True)
    
    def run(self):
        """Start the simulator"""
        print("="*70)
        print("UNIFIED EVCC E-INK DISPLAY SIMULATOR")
        print("="*70)
        print("Features:")
        print("- Visual interface with live EVCC data")
        print("- Actual main.py code execution (AUTO-STARTED)")
        print("- Real-time display updates")
        print("- Mock/live data switching")
        print("- Complete UI validation")
        print("- Initial data fetch on startup")
        print()
        print("Controls:")
        print("- SPACE: Manual poll")
        print("- M: Toggle main.py simulation")
        print("- R: Refresh display")
        print("- Q: Quit")
        print("="*70)
        print("🚀 Main.py simulation will auto-start in 1 second...")
        print("📡 Initial data fetch will begin automatically...")
        print("="*70)
        
        # Show test display initially (will be replaced by real data)
        self.test_display()
        
        # Start GUI
        self.root.mainloop()


if __name__ == "__main__":
    simulator = UnifiedEInkSimulator()
    simulator.run()