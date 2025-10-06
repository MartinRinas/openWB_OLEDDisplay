#!/usr/bin/env python3
"""
Advanced E-Ink LVGL Simulator
Runs your main.py with visual feedback
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
        
        # Try real HTTP request first
        try:
            import requests
            print(f"[SIM] Making real HTTP request to EVCC...")
            response = requests.get(url, timeout=timeout or 10)
            
            class RealResponse:
                def __init__(self, resp):
                    self.status_code = resp.status_code
                    self.text = resp.text
                    print(f"[SIM] Live EVCC data received (status: {resp.status_code})")
                
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
                            {"chargePower": 3000, "soc": 100, "charging": False, "plugged": True},
                            {"chargePower": 0, "soc": -1, "charging": False, "plugged": False}
                        ]
                    })
                
                def close(self):
                    pass
            
            return MockResponse()


class VisualEInkSimulator:
    """Visual E-Ink simulator with LVGL-like interface"""
    
    def __init__(self):
        self.width = 212
        self.height = 104
        self.scale = 4
        
        # Data for display
        self.current_data = None
        self.last_update = time.time()
        self.use_live_data = True
        self.evcc_connected = False
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("EVCC E-Ink Display Simulator")
        self.root.configure(bg='#2b2b2b')
        self.root.geometry("1000x700")
        
        # Header
        header = tk.Frame(self.root, bg='#1e1e1e', height=60)
        header.pack(fill='x', padx=10, pady=5)
        header.pack_propagate(False)
        
        title = tk.Label(
            header,
            text="EVCC E-Ink Display Simulator (212x104)",
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
            text="E-Ink Display Preview",
            bg='#2b2b2b',
            fg='white',
            font=('Arial', 12, 'bold')
        )
        display_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Canvas container
        canvas_container = tk.Frame(display_frame, bg='black', relief='sunken', bd=3)
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
            width=300
        )
        control_frame.pack(side='right', fill='y')
        control_frame.pack_propagate(False)
        
        # Status display
        self.status_text = tk.Text(
            control_frame,
            bg='#1e1e1e',
            fg='lightgreen',
            font=('Courier', 9),
            height=10,
            width=35
        )
        self.status_text.pack(pady=10, padx=10, fill='x')
        
        # Control buttons
        button_frame = tk.Frame(control_frame, bg='#2b2b2b')
        button_frame.pack(pady=10, padx=10, fill='x')
        
        tk.Button(
            button_frame,
            text="Start Main.py Simulation",
            command=self.start_main_simulation,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10, 'bold'),
            height=2
        ).pack(fill='x', pady=5)
        
        tk.Button(
            button_frame,
            text="Poll Data Now",
            command=self.manual_poll,
            bg='#2196F3',
            fg='white',
            font=('Arial', 10)
        ).pack(fill='x', pady=5)
        
        # Toggle live/mock data button
        self.data_mode_btn = tk.Button(
            button_frame,
            text="Mode: Live Data",
            command=self.toggle_data_mode,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10)
        )
        self.data_mode_btn.pack(fill='x', pady=5)
        
        tk.Button(
            button_frame,
            text="Test Display",
            command=self.test_display,
            bg='#FF9800',
            fg='white',
            font=('Arial', 10)
        ).pack(fill='x', pady=5)
        
        tk.Button(
            button_frame,
            text="Clear Display",
            command=self.clear_display,
            bg='#f44336',
            fg='white',
            font=('Arial', 10)
        ).pack(fill='x', pady=5)
        
        # Data display
        data_frame = tk.LabelFrame(
            control_frame,
            text="Current Data",
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
            height=8
        )
        self.data_display.pack(pady=5, padx=5, fill='both', expand=True)
        
        # Initialize
        self.log("Simulator initialized")
        self.log("Showing simple test content - will switch to live data when main.py starts")
        self.log("Ready to run main.py simulation")
        
        print("Visual E-Ink simulator ready!")
    
    def toggle_data_mode(self):
        """Toggle between live and mock data"""
        self.use_live_data = not self.use_live_data
        mode_text = "Live Data" if self.use_live_data else "Mock Data"
        self.data_mode_btn.config(text=f"Mode: {mode_text}")
        
        if self.use_live_data:
            self.data_mode_btn.config(bg='#4CAF50')
            self.log("Switched to live EVCC data mode")
        else:
            self.data_mode_btn.config(bg='#FF9800')
            self.log("Switched to mock data mode")
        
        # Immediately poll with new mode
        self.manual_poll()
    
    def update_connection_status(self, connected):
        """Update the connection status indicator"""
        self.evcc_connected = connected
        if connected:
            self.connection_status.config(text="● ONLINE", fg='green')
        else:
            self.connection_status.config(text="● OFFLINE", fg='red')
    
    def log(self, message):
        """Add message to status log"""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_msg = f"[{timestamp}] {message}\n"
        self.status_text.insert(tk.END, log_msg)
        self.status_text.see(tk.END)
        self.root.update()
    
    def clear_display(self):
        """Clear the display"""
        self.canvas.delete("all")
        self.canvas.configure(bg='black')
        self.log("Display cleared")
    
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
    
    def test_display(self):
        """Test display with simple content"""
        self.clear_display()
        
        # Simple test content
        self.draw_text("Test content", 10, 40, 12)
        
        self.log("Test display rendered")
    
    def draw_sun_symbol(self, x, y):
        """Draw a simple sun symbol"""
        # Draw a circle for the sun
        center_x = x + 8
        center_y = y + 8
        
        # Sun rays (simple lines)
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
        radius = 4 * self.scale
        self.canvas.create_oval(
            (center_x - 4) * self.scale, (center_y - 4) * self.scale,
            (center_x + 4) * self.scale, (center_y + 4) * self.scale,
            outline='white', width=2
        )
    
    def update_display_from_data(self, data):
        """Update display using actual EVCC data - this will replace test content when live data is available"""
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
            if lp1.get('plugged', False):
                soc = lp1.get('soc', 0)
                charging = 'CHG' if lp1.get('charging', False) else 'RDY'
                power = lp1.get('chargePower', 0) / 1000
                self.draw_text(f"Tesla: {soc}% {charging}", 5, 56, 8)
                self.draw_text(f"{power:.1f}kW", 140, 56, 8)
            else:
                self.draw_text("Tesla: Not Connected", 5, 56, 8)
                self.draw_text("0.0kW", 140, 56, 8)
        
        # Smart (LP2)
        if len(loadpoints) > 1:
            lp2 = loadpoints[1]
            if lp2.get('plugged', False):
                soc = lp2.get('soc', 0)
                if soc < 0:
                    soc_text = "??"
                else:
                    soc_text = f"{soc}%"
                charging = 'CHG' if lp2.get('charging', False) else 'RDY'
                power = lp2.get('chargePower', 0) / 1000
                self.draw_text(f"Smart: {soc_text} {charging}", 5, 70, 8)
                self.draw_text(f"{power:.1f}kW", 140, 70, 8)
            else:
                self.draw_text("Smart: Not Connected", 5, 70, 8)
                self.draw_text("0.0kW", 140, 70, 8)
        
        # Timestamp
        timestamp = time.strftime("%H:%M:%S")
        self.draw_text(f"Updated: {timestamp}", 5, 88, 7)
        
        # Update data display
        self.data_display.delete(1.0, tk.END)
        self.data_display.insert(tk.END, json.dumps(data, indent=2))
        
        self.log("Display updated with live data")
    
    def manual_poll(self):
        """Manual data poll - tries live EVCC data first"""
        self.log("Polling EVCC data...")
        
        # Check if we should use live data
        if not self.use_live_data:
            self.log("Using mock data (live mode disabled)")
            self.update_connection_status(False)
            data = {
                "gridPower": 2500,
                "pvPower": 11000,
                "batterySoc": 14,
                "loadpoints": [
                    {"chargePower": 3000, "soc": 100, "charging": False, "plugged": True},
                    {"chargePower": 0, "soc": -1, "charging": False, "plugged": False}
                ]
            }
            self.current_data = data
            self.update_display_from_data(data)
            self.log("Mock data poll completed")
            return
        
        # EVCC API URL (same as in main.py)
        base_url = "http://192.168.178.29:7070/api/state"
        jq_query = ("?jq=%7BgridPower:.grid.power,pvPower:.pvPower,"
                   "batterySoc:.batterySoc,loadpoints:[.loadpoints[0],"
                   ".loadpoints[1]]%7Cmap(select(.!=null)%7C%7B"
                   "chargePower:.chargePower,soc:(.vehicleSoc//.soc),"
                   "charging:.charging,plugged:(.connected//.plugged)%7D)%7D")
        url = base_url + jq_query
        
        try:
            import requests
            self.log("Attempting live EVCC connection...")
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                self.log("✓ Live EVCC data received!")
                self.update_connection_status(True)
                self.current_data = data
                self.update_display_from_data(data)
                return
            else:
                self.log(f"✗ EVCC returned status {response.status_code}")
                self.update_connection_status(False)
                
        except ImportError:
            self.log("✗ Requests module not available")
            self.update_connection_status(False)
        except Exception as e:
            if 'timeout' in str(e).lower():
                self.log("✗ EVCC connection timeout")
            elif 'connection' in str(e).lower():
                self.log("✗ EVCC connection refused - is EVCC running?")
            else:
                self.log(f"✗ EVCC error: {e}")
            self.update_connection_status(False)
        
        # Fallback to mock data
        self.log("Using mock data as fallback")
        data = {
            "gridPower": 2500,
            "pvPower": 11000,
            "batterySoc": 14,
            "loadpoints": [
                {"chargePower": 3000, "soc": 100, "charging": False, "plugged": True},
                {"chargePower": 0, "soc": -1, "charging": False, "plugged": False}
            ]
        }
        
        self.current_data = data
        self.update_display_from_data(data)
        self.log("Mock data poll completed")
    
    def start_main_simulation(self):
        """Start running the actual main.py simulation"""
        self.log("Starting main.py simulation...")
        
        def run_simulation():
            try:
                # Setup mocks
                sys.modules['time'] = MockTime()
                sys.modules['machine'] = type('MockMachine', (), {
                    'Pin': lambda *args, **kwargs: None,
                    'SPI': lambda *args, **kwargs: None,
                    'Timer': lambda *args, **kwargs: None
                })()
                sys.modules['network'] = MockNetwork()
                sys.modules['urequests'] = MockRequests()
                sys.modules['ujson'] = json
                sys.modules['gc'] = type('MockGC', (), {'collect': lambda: None})()
                
                # Mock framebuf module
                sys.modules['framebuf'] = type('MockFramebuf', (), {
                    'FrameBuffer': lambda *args, **kwargs: None,
                    'MONO_HLSB': 0
                })()
                
                # Mock e-ink display drivers
                sys.modules['epaper2in13_V3'] = type('MockEPaper', (), {
                    'EPD_2in13_V3': lambda *args, **kwargs: None
                })()
                sys.modules['epaper2in13'] = type('MockEPaper', (), {
                    'EPD_2in13': lambda *args, **kwargs: None
                })()
                
                # Mock LVGL and display
                simulator_ref = self
                
                class MockLVGL:
                    @staticmethod
                    def init():
                        simulator_ref.log("LVGL initialized")
                    
                    @staticmethod
                    def task_handler():
                        pass
                    
                    @staticmethod
                    def color_white():
                        return 1
                    
                    @staticmethod
                    def color_black():
                        return 0
                    
                    @staticmethod
                    def disp_drv_register(drv):
                        pass
                    
                    @staticmethod
                    def scr_load(scr):
                        pass
                    
                    # LVGL constants
                    class ANIM:
                        OFF = 0
                    
                    class PART:
                        MAIN = 0
                        INDICATOR = 1
                    
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
                    
                    class obj:
                        def __init__(self, parent=None): pass
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
                        def set_text(self, text): 
                            simulator_ref.log(f"LVGL Label: {text}")
                        def set_style_text_color(self, color, part=0): pass
                    
                    class bar:
                        def __init__(self, parent): pass
                        def set_size(self, w, h): pass
                        def set_pos(self, x, y): pass
                        def set_range(self, min_val, max_val): pass
                        def set_value(self, value, anim): 
                            simulator_ref.log(f"LVGL Bar: {value}")
                        def set_style_bg_color(self, color, part=0): pass
                
                sys.modules['lvgl'] = MockLVGL()
                
                # Read and execute main.py
                with open("main.py", "r") as f:
                    source = f.read()
                
                # Speed up for testing
                source = source.replace("POLL_INTERVAL_MS = 30000", "POLL_INTERVAL_MS = 5000")
                
                namespace = {}
                exec(source, namespace)
                
                self.log("main.py executed successfully")
                
                # Start periodic updates
                self.start_periodic_updates()
                
            except Exception as e:
                self.log(f"Error in simulation: {e}")
                import traceback
                traceback.print_exc()
        
        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=run_simulation, daemon=True)
        thread.start()
    
    def start_periodic_updates(self):
        """Start periodic display updates"""
        def update():
            if hasattr(self, 'current_data') and self.current_data:
                self.update_display_from_data(self.current_data)
            
            # Schedule next update
            self.root.after(3000, update)
        
        # Start updates
        self.manual_poll()  # Initial data
        self.root.after(1000, update)
    
    def run(self):
        """Start the simulator"""
        print("="*60)
        print("EVCC E-Ink Display Simulator")
        print("="*60)
        print("Window should be visible!")
        print("Use 'Start Main.py Simulation' to run your actual code")
        print("="*60)
        
        # Show test display initially
        self.test_display()
        
        # Start GUI
        self.root.mainloop()


if __name__ == "__main__":
    simulator = VisualEInkSimulator()
    simulator.run()