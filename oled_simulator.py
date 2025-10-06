import tkinter as tk
from tkinter import font


class OLEDSimulator:
    """OLED/E-ink display simulator using tkinter"""
    
    def __init__(self, width=128, height=64, scale=4):
        self.width = width
        self.height = height
        self.scale = scale
        
        # Create main window
        self.root = tk.Tk()
        self.root.title(f"Display Simulator ({width}x{height})")
        self.root.configure(bg='black')
        
        # Create canvas for display
        canvas_width = width * scale
        canvas_height = height * scale
        self.canvas = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)
        
        # Pixel buffer - 0=black, 1=white for e-ink
        self.buffer = [[0 for _ in range(width)] for _ in range(height)]
        
        # Bind keyboard events
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.focus_set()
        
        # Font for text rendering
        self.mono_font = font.Font(family="Courier", size=8)
        
        print(f"Display simulator initialized: {width}x{height} "
              f"@ {scale}x scale")
    
    def on_key_press(self, event):
        """Handle key press events - override in subclasses"""
        if event.char == 'q':
            self.root.quit()
    
    def pixel(self, x, y, color):
        """Set a single pixel"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.buffer[y][x] = color
    
    def fill(self, color):
        """Fill entire display with color"""
        for y in range(self.height):
            for x in range(self.width):
                self.buffer[y][x] = color
    
    def text(self, text, x, y, color=1):
        """Draw text at position"""
        # Simple character rendering - each char is 6x8 pixels
        char_width = 6
        char_height = 8
        
        for i, char in enumerate(text):
            char_x = x + (i * char_width)
            if char_x >= self.width:
                break
            
            # Simple bitmap font simulation
            if char == ' ':
                continue
            
            # Draw a simple character representation
            for cy in range(min(char_height, self.height - y)):
                for cx in range(min(char_width, self.width - char_x)):
                    # Simple pattern for visible characters
                    if (cy == 0 or cy == char_height-1 or
                            cx == 0 or cx == char_width-1):
                        self.pixel(char_x + cx, y + cy, color)
    
    def rect(self, x, y, w, h, color):
        """Draw rectangle outline"""
        # Top and bottom lines
        for i in range(w):
            self.pixel(x + i, y, color)
            self.pixel(x + i, y + h - 1, color)
        
        # Left and right lines
        for i in range(h):
            self.pixel(x, y + i, color)
            self.pixel(x + w - 1, y + i, color)
    
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
    
    def show(self):
        """Update the display"""
        self.canvas.delete("all")
        
        # Draw pixels
        for y in range(self.height):
            for x in range(self.width):
                color = "white" if self.buffer[y][x] else "black"
                x1 = x * self.scale
                y1 = y * self.scale
                x2 = x1 + self.scale
                y2 = y1 + self.scale
                
                self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=color,
                    outline=color
                )
        
        self.root.update()
    
    def run(self):
        """Start the simulator main loop"""
        print("Starting display simulator...")
        print("Press 'q' to quit")
        self.show()
        self.root.mainloop()


if __name__ == "__main__":
    # Test the simulator
    sim = OLEDSimulator(212, 104, 3)
    
    # Draw some test content
    sim.fill(0)
    sim.text("Test Display", 10, 10)
    sim.rect(5, 5, 202, 94, 1)
    sim.fill_rect(50, 30, 100, 20, 1)
    
    sim.run()