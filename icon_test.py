#!/usr/bin/env python3
"""
Icon Test - Quick preview of the sun icon
"""

import tkinter as tk
from icons import draw_sun_icon_small, draw_sun_icon


class IconTest:
    def __init__(self):
        # Mock framebuffer for testing
        self.width = 212
        self.height = 104
        self.pixels = [[0 for _ in range(self.width)] for _ in range(self.height)]
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title("Icon Preview")
        self.root.configure(bg='black')
        
        # Canvas for icon display
        self.scale = 4
        self.canvas = tk.Canvas(
            self.root,
            width=self.width * self.scale,
            height=self.height * self.scale,
            bg='black'
        )
        self.canvas.pack(padx=10, pady=10)
        
        # Info label
        info = tk.Label(
            self.root,
            text="Sun Icons Preview: Small (16x16) and Large (48x48)",
            bg='black',
            fg='white',
            font=('Arial', 12)
        )
        info.pack(pady=5)
        
        self.show_icons()
    
    def pixel(self, x, y, color):
        """Mock pixel function for icons"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color
            
            # Draw on canvas
            if color:
                x1 = x * self.scale
                y1 = y * self.scale
                x2 = x1 + self.scale
                y2 = y1 + self.scale
                self.canvas.create_rectangle(x1, y1, x2, y2, 
                                           fill='white', outline='white')
    
    def show_icons(self):
        """Display the icons"""
        # Clear
        self.canvas.delete("all")
        for y in range(self.height):
            for x in range(self.width):
                self.pixels[y][x] = 0
        
        # Draw small sun icon (16x16)
        draw_sun_icon_small(self, 5, 5, 1)
        
        # Draw large sun icon (48x48) - but only part of it
        draw_sun_icon(self, 30, 5, 1)
        
        # Labels
        self.canvas.create_text(13 * self.scale, 22 * self.scale, 
                               text="16x16", fill='yellow', 
                               font=('Arial', 8))
        self.canvas.create_text(54 * self.scale, 55 * self.scale, 
                               text="48x48", fill='yellow', 
                               font=('Arial', 8))
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    test = IconTest()
    test.run()