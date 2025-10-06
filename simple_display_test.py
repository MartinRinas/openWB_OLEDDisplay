#!/usr/bin/env python3
"""
Simple E-Ink Display Test - Direct visual simulator
"""

import tkinter as tk
import time


class SimpleEInkSimulator:
    """Simple E-Ink display simulator with direct visualization"""
    
    def __init__(self):
        self.width = 212
        self.height = 104
        self.scale = 4
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("E-Ink Display Simulator (212x104)")
        self.root.configure(bg='darkgray')
        self.root.geometry("900x600")
        
        # Create display frame
        display_frame = tk.Frame(self.root, bg='black', relief='sunken', bd=2)
        display_frame.pack(pady=20, padx=20)
        
        # Create canvas for e-ink display
        canvas_width = self.width * self.scale
        canvas_height = self.height * self.scale
        self.canvas = tk.Canvas(
            display_frame,
            width=canvas_width,
            height=canvas_height,
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack(padx=5, pady=5)
        
        # Control panel
        control_frame = tk.Frame(self.root, bg='lightgray')
        control_frame.pack(fill='x', padx=20, pady=10)
        
        # Status label
        self.status_label = tk.Label(
            control_frame,
            text="E-Ink Display Simulator Ready",
            bg='lightgray',
            font=('Arial', 12, 'bold')
        )
        self.status_label.pack(pady=5)
        
        # Buttons
        button_frame = tk.Frame(control_frame, bg='lightgray')
        button_frame.pack(pady=5)
        
        tk.Button(
            button_frame,
            text="Test Display",
            command=self.test_display,
            bg='blue',
            fg='white',
            font=('Arial', 10),
            padx=20
        ).pack(side='left', padx=5)
        
        tk.Button(
            button_frame,
            text="Simulate EVCC Data",
            command=self.simulate_evcc,
            bg='green',
            fg='white',
            font=('Arial', 10),
            padx=20
        ).pack(side='left', padx=5)
        
        tk.Button(
            button_frame,
            text="Clear Display",
            command=self.clear_display,
            bg='red',
            fg='white',
            font=('Arial', 10),
            padx=20
        ).pack(side='left', padx=5)
        
        # Instructions
        instructions = tk.Label(
            control_frame,
            text="This simulator shows how your 212x104 E-Ink display "
                 "will look",
            bg='lightgray',
            font=('Arial', 10)
        )
        instructions.pack(pady=5)
        
        print("Simple E-Ink simulator initialized")
        print("Window should now be visible!")
    
    def clear_display(self):
        """Clear the display"""
        self.canvas.delete("all")
        self.canvas.configure(bg='black')
        self.status_label.config(text="Display Cleared")
        print("Display cleared")
    
    def draw_pixel(self, x, y, color='white'):
        """Draw a single pixel"""
        if 0 <= x < self.width and 0 <= y < self.height:
            x1 = x * self.scale
            y1 = y * self.scale
            x2 = x1 + self.scale
            y2 = y1 + self.scale
            
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=color,
                outline=color
            )
    
    def draw_text(self, text, x, y, size=8):
        """Draw text on the display"""
        # Scale position for canvas
        canvas_x = x * self.scale
        canvas_y = y * self.scale
        
        self.canvas.create_text(
            canvas_x, canvas_y,
            text=text,
            fill='white',
            font=('Courier', size, 'bold'),
            anchor='nw'
        )
    
    def draw_rect(self, x, y, w, h, fill=False):
        """Draw rectangle"""
        x1 = x * self.scale
        y1 = y * self.scale
        x2 = (x + w) * self.scale
        y2 = (y + h) * self.scale
        
        if fill:
            self.canvas.create_rectangle(
                x1, y1, x2, y2, fill='white', outline='white')
        else:
            self.canvas.create_rectangle(
                x1, y1, x2, y2, fill='', outline='white', width=2)
    
    def test_display(self):
        """Test the display with basic graphics"""
        self.clear_display()
        
        # Border
        self.draw_rect(0, 0, self.width-1, self.height-1, fill=False)
        
        # Title
        self.draw_text("E-Ink Test Display", 5, 5, 10)
        
        # Test rectangles
        self.draw_rect(10, 25, 50, 20, fill=True)
        self.draw_rect(70, 25, 50, 20, fill=False)
        
        # Test text
        self.draw_text("212x104 Resolution", 10, 50, 8)
        self.draw_text("Ready for EVCC Data", 10, 65, 8)
        
        # Some pixels
        for i in range(10, 50, 2):
            self.draw_pixel(i, 85)
        
        self.status_label.config(text="Test Display Rendered")
        print("Test display rendered")
    
    def simulate_evcc(self):
        """Simulate EVCC energy data display"""
        self.clear_display()
        
        # Mock EVCC data
        data = {
            "gridPower": 2500,    # 2.5kW
            "pvPower": 11000,     # 11kW
            "batterySoc": 14,     # 14%
            "loadpoints": [
                {"chargePower": 3000, "soc": 100, "charging": False,
                 "plugged": True},   # Tesla
                {"chargePower": 0, "soc": -1, "charging": False,
                 "plugged": False}   # Smart
            ]
        }
        
        # Title
        self.draw_text("EVCC Energy Monitor", 5, 2, 9)
        
        # Grid Power
        grid_text = f"Grid: {data['gridPower']/1000:.1f}kW"
        self.draw_text(grid_text, 5, 15, 8)
        
        # PV Power
        pv_text = f"PV: {data['pvPower']/1000:.1f}kW"
        self.draw_text(pv_text, 110, 15, 8)
        
        # Battery
        battery_text = f"Battery: {data['batterySoc']}%"
        self.draw_text(battery_text, 5, 28, 8)
        
        # Battery bar (simplified)
        bar_width = int(80 * data['batterySoc'] / 100)
        self.draw_rect(5, 40, 80, 8, fill=False)
        if bar_width > 0:
            self.draw_rect(6, 41, bar_width-2, 6, fill=True)
        
        # Tesla (LP1)
        self.draw_text("Tesla:", 5, 55, 8)
        if data['loadpoints'][0]['plugged']:
            charging = 'CHG' if data['loadpoints'][0]['charging'] else 'RDY'
            status = f"{data['loadpoints'][0]['soc']}% {charging}"
            power = f"{data['loadpoints'][0]['chargePower']/1000:.1f}kW"
        else:
            status = "Not Connected"
            power = "0.0kW"
        
        self.draw_text(status, 45, 55, 8)
        self.draw_text(power, 110, 55, 8)
        
        # Smart (LP2)
        self.draw_text("Smart:", 5, 70, 8)
        if data['loadpoints'][1]['plugged']:
            charging = 'CHG' if data['loadpoints'][1]['charging'] else 'RDY'
            status = f"{data['loadpoints'][1]['soc']}% {charging}"
            power = f"{data['loadpoints'][1]['chargePower']/1000:.1f}kW"
        else:
            status = "Not Connected"
            power = "0.0kW"
        
        self.draw_text(status, 45, 70, 8)
        self.draw_text(power, 110, 70, 8)
        
        # Timestamp
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        self.draw_text(f"Updated: {timestamp}", 5, 90, 7)
        
        self.status_label.config(
            text="EVCC Data Simulated - This is how your display will look!")
        print("EVCC simulation rendered")

    def run(self):
        """Start the simulator"""
        print("="*50)
        print("E-Ink Display Simulator")
        print("="*50)
        print("Window should be visible now!")
        print("Use the buttons to test different displays")
        print("Close the window to exit")
        print("="*50)

        # Show initial test
        self.test_display()

        # Start the GUI
        self.root.mainloop()


if __name__ == "__main__":
    simulator = SimpleEInkSimulator()
    simulator.run()
