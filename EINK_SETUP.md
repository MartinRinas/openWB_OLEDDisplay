# E-Ink Display Setup Instructions for ESP32-S3
# 2.13" E-Ink Display Module Setup

## Hardware Requirements:
- ESP32-S3 board with USB-C
- 2.13" E-Ink display module (Waveshare or compatible)
- Connecting wires

## Wiring for ESP32-S3:
```
E-Ink Display -> ESP32-S3
VCC           -> 3.3V
GND           -> GND
DIN (MOSI)    -> GPIO 23
CLK (SCLK)    -> GPIO 18
CS            -> GPIO 5
DC            -> GPIO 17
RST           -> GPIO 16
BUSY          -> GPIO 4
```

## Required Libraries:
You need to install the appropriate e-ink display driver for your specific module.

### For Waveshare 2.13" V3:
Download from: https://github.com/waveshare/e-Paper/tree/master/MicroPython/src
Files needed:
- epaper2in13_V3.py

### For Waveshare 2.13" (older versions):
Download from: https://github.com/waveshare/e-Paper/tree/master/MicroPython/src  
Files needed:
- epaper2in13.py

### Installation:
1. Upload the driver file to your ESP32-S3 root directory
2. Upload main.py
3. Adjust pin assignments in main.py if your wiring is different

## Key Differences from OLED:
- **Slower refresh**: E-ink displays update slowly (1-2 seconds)
- **Power efficient**: Only uses power during updates
- **Sunlight readable**: Great visibility in bright light
- **Larger screen**: 250x122 pixels vs 128x64 OLED
- **Less frequent updates**: Updates every 30 seconds instead of 5

## Display Features:
- Clear power readings (EVU, PV, Battery, Charging)
- Large battery status bar
- Vehicle SoC percentage
- Charging status indicators
- Last update timestamp
- Optimized layout for e-ink visibility

## Configuration:
Edit these variables in main.py:
- WIFI_SSID, WIFI_PASSWORD: Your WiFi credentials
- HTTP_HOST: Your EVCC server IP
- SPI pin assignments if different wiring

## Pin Adjustments:
If you need different pins, modify these constants in main.py:
```python
SPI_CLK = 18    # Clock
SPI_MOSI = 23   # Data
SPI_CS = 5      # Chip Select
SPI_DC = 17     # Data/Command
SPI_RST = 16    # Reset
SPI_BUSY = 4    # Busy signal
```