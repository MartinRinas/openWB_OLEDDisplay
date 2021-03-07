# openWB_OLEDDisplay
OpenWB status display using ESP8266 and 0.96" OLED Display.
Displays current EVU, PV and combined power of all charging ports plus SoC of charge port 1.

Allows OTA updates via integrated WebBrowser on <ip of ESP>/update

Sketch assumes SPI Display, wiring for Wemos D1 & compatible:
SCL: D1
SDA: D2
GND: GND
VCC: 3.3V

# Configuration
You need to enter SSID, PW and IP of openWB in .ino source file
