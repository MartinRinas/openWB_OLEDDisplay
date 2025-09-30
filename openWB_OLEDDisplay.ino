// Core / Platform
#include <ESP8266WiFi.h>
#include <WiFiUDP.h>
#include <ESP8266mDNS.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPUpdateServer.h>
#include <SPI.h>
#include <Wire.h>

// Display libraries
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Local modules
#include "parser.h"
#include "http_client.h"

// Define UI style (graphic style adds symbols & alignment logic)
#define UI_GRAPHIC_STYLE

// TODO: Replace static credentials with WiFiManager / captive portal for production use.

// Network setup
const char* ssid = "SSID";              // your network SSID (name)
const char* pass = "PASSWORD";        // your network password
const char* hostname = "evcc-Display";      

// ------------------------------------------------
// HTTP Polling Configuration
// ------------------------------------------------
// Uses evcc state endpoint with minimized jq filter to keep payload & RAM small.

const char* HTTP_HOST = "192.168.178.29";   // evcc IP 
const uint16_t HTTP_PORT = 7070;              // HTTP port, default 7070
// For evcc switch to the state endpoint; adding jq filter returns full structure. Remove jq param if not supported.
// Use minimized EVCC state (much smaller) via jq filter: returns only needed keys.
// Original (full) was: /api/state?jq=.  (very large ~ >10KB)
// Minified filter now requests up to first two loadpoints (filters out null), each mapped to minimal fields.
// Unencoded jq filter:
// {gridPower:.grid.power,pvPower:.pvPower,loadpoints:[.loadpoints[0],.loadpoints[1]]|map(select(.!=null)|{chargePower:.chargePower,soc:(.vehicleSoc//.soc),charging:.charging,plugged:(.connected//.plugged)})}
// URL-encoded version below (safer for query string):
const char* HTTP_PATH = "/api/state?jq=%7BgridPower:.grid.power,pvPower:.pvPower,loadpoints:[.loadpoints[0],.loadpoints[1]]%7Cmap(select(.!=null)%7C%7BchargePower:.chargePower,soc:(.vehicleSoc//.soc),charging:.charging,plugged:(.connected//.plugged)%7D)%7D"; 

// Polling interval (ms)
const unsigned long POLL_INTERVAL_MS = 5000; // configurable polling interval

// Data variables (updated after each successful poll & parse)
#ifndef UI_GRAPHIC_STYLE
float EVU_kW = 0;        // EVU power (shown in kW if text mode)
float PV_kW = 0;         // PV power (negative import handling similar to previous logic)
#else
int EVU_W = 0;           // Absolute grid power value (always positive for display)
int EVU_dir = 1;         // 1 import, -1 export (direction arrow)
int PV_W = 0;            // PV power (positive generation)
#endif
int LP_all_W = 0;        // Combined power of all charge points (sum of chargePower)
int LP1_SOC = -1;             // (legacy) Currently displayed LP SoC (kept for minimal changes in text UI path)
bool LP1_PlugStat = false;    // (legacy) Currently displayed LP plugged
bool LP1_IsCharging = false;  // (legacy) Currently displayed LP charging

// Global metrics structure holding up to two loadpoints
Metrics g_metrics;            // Filled by PollAndUpdate(); used for cycling display between loadpoints

// Loadpoint display cycling
const unsigned long LP_CYCLE_INTERVAL_MS = 7000; // Interval to auto-switch displayed loadpoint (if >=2)
uint8_t currentLpIndex = 0;                      // Which loadpoint is currently shown
unsigned long lastLpSwitchMillis = 0;            // Timestamp of last automatic switch


// Display Setup
#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels

// Display rotation (0=normal, 1=90°, 2=180°, 3=270°). Set to 2 to flip 180°.
#ifndef DISPLAY_ROTATION
#define DISPLAY_ROTATION 2
#endif

#ifdef UI_GRAPHIC_STYLE
#define shift_k_value  3
#define shift_dot  1

const uint8_t blitz[10] = { 0x3c, 0x78, 0x70, 0xe0,
                            0xfc, 0x38, 0x30, 0x60,
                            0xc0, 0x80};
const uint8_t arrow_right[10] = { 0x00, 0x08, 0x0c, 0x0e,
                                  0xff, 0xff, 0x0e, 0x0c,
                                  0x08, 0x00 };
const uint8_t arrow_left[10] = { 0x00, 0x10, 0x30, 0x70,
                                 0xff, 0xff, 0x70, 0x30,
                                 0x10, 0x00 };
const uint8_t haus[15] = { 0x0c, 0x01, 0xe0, 0x3f, 
                           0x07, 0xf8, 0xff, 0xcc, 
                           0xcc, 0xcc, 0xcf, 0xcc,
                           0xfc, 0xcf, 0xcc};
const uint8_t haus2[20] = { 0x0c, 0x00, 0x1e, 0x00, 
                            0x3f, 0x00, 0x7f, 0x80,
                            0xff, 0xc0, 0xcc, 0xc0,
                            0xcc, 0xc0, 0xfc, 0xc0,
                            0xfc, 0xc0, 0xfc, 0xc0 };
const uint8_t unplugged[30] = { 0x00, 0x00, 0x00,
                                0xf0, 0x00, 0x00,
                                0xb0, 0x00, 0x00,
                                0xb0, 0x60, 0x00,
                                0x90, 0x40, 0x00,
                                0xde, 0x40, 0x00,
                                0xd2, 0x40, 0x00,
                                0xf2, 0x40, 0x00,
                                0xf3, 0xc0, 0x00,
                                0xf0, 0x00, 0x00 };
const uint8_t plugged[30] = { 0x00, 0x07, 0xf0,
                              0xf0, 0x04, 0x10,
                              0xb0, 0x08, 0x08,
                              0xb0, 0x08, 0x08,
                              0x90, 0x38, 0x0e,
                              0xde, 0x0f, 0xf8,
                              0xd2, 0x79, 0xc8,
                              0xf2, 0x4f, 0xf8,
                              0xf3, 0xcf, 0xf8,
                              0xf0, 0x0c, 0x18 };
#endif


// Declaration for an SSD1306 display connected to I2C (SDA, SCL pins)
#define OLED_RESET     0 // Reset pin # (or -1 if sharing Arduino reset pin)
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

unsigned long lastDataReceived = 0;          // when last successful HTTP data was parsed
const unsigned long DATA_STALE_MS = 30UL * 1000UL; // age at which we mark data stale

WiFiClient httpClient;                       // used for HTTP requests
unsigned long lastPollAttempt = 0;           // last poll attempt timestamp
uint8_t consecutiveFailures = 0;             // track failures for optional backoff

// Config flags do enable features
const bool isDebug = 1;                        // Send debug messages to serial port?

// -----------------------------
// In-memory Log Buffer (HTTP accessible)
// -----------------------------
#define LOG_BUFFER_LINES 120            // number of lines to keep
#define LOG_MAX_LINE_LEN 120            // max length per stored line (longer lines truncated)
String LogBuffer[LOG_BUFFER_LINES];
uint16_t LogWriteIndex = 0;             // next slot to write
bool LogWrapped = false;                // indicates wrap-around occurred

void AddLogLine(const String &line)
{
  String trimmed = line;
  // Ensure line length bounded to save RAM
  if(trimmed.length() > LOG_MAX_LINE_LEN) {
    trimmed = trimmed.substring(0, LOG_MAX_LINE_LEN-3) + "...";
  }
  LogBuffer[LogWriteIndex] = trimmed;
  LogWriteIndex = (LogWriteIndex + 1) % LOG_BUFFER_LINES;
  if(LogWriteIndex == 0) LogWrapped = true;
}

String GetAllLogs()
{
  String out;
  if(LogWrapped)
  {
    for(uint16_t i = LogWriteIndex; i < LOG_BUFFER_LINES; i++)
    {
      out += LogBuffer[i];
      out += '\n';
    }
  }
  for(uint16_t i = 0; i < LogWriteIndex; i++)
  {
    out += LogBuffer[i];
    out += '\n';
  }
  return out;
}

void ClearLogs()
{
  for(uint16_t i=0;i<LOG_BUFFER_LINES;i++) LogBuffer[i] = "";
  LogWriteIndex = 0;
  LogWrapped = false;
  AddLogLine("<log cleared>");
}

// ESP8266 Webserver and update server
ESP8266WebServer server(80);              // HTTP server port
ESP8266HTTPUpdateServer httpUpdater;      // HTTP update server, allows OTA flash by navigating to http://<ESP8266IP>/update

void WriteLog(String msg,bool NewLine=1)  // helper function for logging, only write to serial if isDebug is true
{
  if(NewLine)
  {
    if(isDebug){Serial.println(msg);}    
    AddLogLine(msg);
  }
  else
  {
    if(isDebug){Serial.print(msg);}
  } 
}

// Poll + parse helper
bool PollAndUpdate()
{
    String body;
    if(!HttpGet(HTTP_HOST, HTTP_PORT, HTTP_PATH, body)) return false;
    Metrics m;
    if(!ParseEvccState(body, m)) {
        WriteLog("Parse failed");
        return false;
    }
    // Map metrics to display globals
#ifdef UI_GRAPHIC_STYLE
  EVU_dir = (m.gridPower >= 0) ? 1 : -1;
  EVU_W   = (m.gridPower >= 0) ? m.gridPower : -m.gridPower;
  PV_W    = (m.pvPower < 0) ? -m.pvPower : m.pvPower;
#else
    EVU_kW  = ((float)m.gridPower) / 1000.0f;
    PV_kW   = ((float)m.pvPower) / 1000.0f;
#endif
  LP_all_W      = (int)m.totalChargePower;

  // Persist full metrics for cycling logic
  g_metrics = m; // struct copy (small)

  // Update legacy single-LP vars from currently selected index
  if (g_metrics.lpCount > currentLpIndex) {
    LP1_SOC        = g_metrics.lps[currentLpIndex].soc;
    LP1_IsCharging = g_metrics.lps[currentLpIndex].charging;
    LP1_PlugStat   = g_metrics.lps[currentLpIndex].plugged;
  } else if (g_metrics.lpCount > 0) {
    // fallback to first
    LP1_SOC        = g_metrics.lps[0].soc;
    LP1_IsCharging = g_metrics.lps[0].charging;
    LP1_PlugStat   = g_metrics.lps[0].plugged;
  } else {
    LP1_SOC = -1; LP1_IsCharging = false; LP1_PlugStat = false;
  }
    lastDataReceived = millis();
    consecutiveFailures = 0;
    UpdateDisplay();
    return true;
}

void HandleRoot()                                                 // Handle Webserver request on root
{
  String res = "HTTP Server up and running.";
  WebserverResponse(res);
}

void HandleLogs()
{
  String logs = GetAllLogs();
  server.sendHeader("Cache-Control","no-cache");
  server.send(200, "text/plain", logs);
}

void HandleLogsClear()
{
  ClearLogs();
  server.send(200, "text/plain", "cleared");
}

void HandleMQTTStatus() // Retained for compatibility: now returns static info
{
  String res = String("MQTT disabled; using HTTP polling");
  WebserverResponse(res);
}

void WebserverResponse(String str)
{ 
    str.trim();
    WriteLog("Sending WebServer response, requested URI: " + server.uri());
    server.sendHeader("Cache-Control", "no-cache");
    server.send(200, "text/plain",String(str));
    WriteLog("Sending HTTP response: " + str);
}

// Removed MQTT callback (logic replaced by HTTP JSON polling)

void WriteDisplayNewText(String msg)
{
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(0,0);
  WriteDisplayText(msg);
}

void WriteDisplayText(String msg)
{
  display.println(msg);
  display.display();
}

#ifdef UI_GRAPHIC_STYLE
void WriteWattValue(int Watt, int x, int y)
{
  // check if Watt Value is smaller than 1000 (=1kW)
  if (Watt < 1000)
  {
	// value is smaller than 1kW, 
	// need to write value right-aligned
    if (Watt < 10)
    {
      display.setCursor(x-1*12, y);
    }
    else if (Watt < 100)
    {
      display.setCursor(x-2*12, y);
    }
    else
    {
      display.setCursor(x-3*12, y);
    }
    display.println(String(Watt));
  }
  else
  {
    if (Watt < 10000)
    {
      int D_Watt_kW=Watt/1000;
      //int D_Watt_W=Watt-D_Watt_kW*1000;
      int D_Watt_W=Watt%1000;
      if (D_Watt_W <10)
      {
        display.setCursor(x-3*12, y);
        display.print("00"+String(D_Watt_W));
        display.setCursor(x-4*12+shift_dot, y);
        display.print(".");
        display.setCursor(x-5*12+shift_k_value+shift_dot, y);
        display.print(String(D_Watt_kW));
      }
      else if (D_Watt_W < 100)
      {
        display.setCursor(x-3*12, y);
        display.print("0"+String(D_Watt_W));
        display.setCursor(x-4*12+shift_dot, y);
        display.print(".");
        display.setCursor(x-5*12+shift_k_value+shift_dot, y);
        display.print(String(D_Watt_kW));
      }
      else
      {
        display.setCursor(x-3*12, y);
        display.print(String(D_Watt_W));
        display.setCursor(x-4*12+shift_dot, y);
        display.print(".");
        display.setCursor(x-5*12+shift_k_value+shift_dot, y);
        display.print(String(D_Watt_kW));
      }
    }
    else
    {
      int D_Watt_kW=Watt/1000;
      //int D_Watt_W=Watt-D_Watt_kW*1000;
      int D_Watt_W=(Watt%1000)/10;
      if (D_Watt_W <100)
      {
        display.setCursor(x-2*12, y);
        display.print("0"+String(D_Watt_W));
        display.setCursor(x-3*12+shift_dot, y);
        display.print(".");
        display.setCursor(x-5*12+shift_k_value+shift_dot, y);
        display.print(String(D_Watt_kW));
      }
      else
      {
        display.setCursor(x-2*12, y);
        display.print(String(D_Watt_W));
        display.setCursor(x-3*12+shift_dot, y);
        display.print(".");
        display.setCursor(x-5*12+shift_k_value+shift_dot, y);
        display.print(String(D_Watt_kW));
      }
    }
  }
}

void drawBitmap(uint16_t x, uint16_t y, uint8_t bitmap[], uint16_t w, uint16_t h)
{
  for (int i=0; i<w; i++)
  {
    for (int j=0; j<h; i++)
    {
      uint16_t bitindex = i+j*h;
      uint16_t byteindex = bitindex/8;
      uint8_t bytebitindex = bitindex % 8;
      uint16_t color = (bitmap[byteindex] >> bytebitindex) & 0x01;
      //drawPixel(x+i, y+j, color);
    }
  }
}
#endif

void UpdateDisplay()
{
  // for a 128*64px display:
  // Text Size 1: single char 6*8px, 21 chars per row, 8 rows 
  // Text Size 2: single char 12*16px, 10 chars per row, 4 rows 
  // Text Size 3: single char 18*24x, 7 chars per row, 2.5 rows 
  // Text Size 4: single char 24*32x, 5 chars per row, 2 rows 
  // Text Size 8: single char 48*64x, 2 chars per row, 1 row 

#ifndef UI_GRAPHIC_STYLE
  display.clearDisplay();
  display.setCursor(0,0); //set upper left corner of cursor to upper left corner of display
  display.setTextSize(1);
  
  String ChargeStatus="";
  if(LP1_IsCharging)
  {
    ChargeStatus = "  C";
  }
  else
  {
    if(LP1_PlugStat==true)
    {
      ChargeStatus="  P";
    }
  }
  
 
  display.println("EVU (kW)");
  display.setCursor(SCREEN_WIDTH/2,0);
  display.println("PV (kW)");
  display.setTextSize(2);
  display.print(EVU_kW);
  display.setCursor(11*6,8); // 11 chars a 6 px right, one row 8 px down
  display.println(PV_kW);
  display.setTextSize(1);
  display.setCursor(0,32); //continue in the middle of the screen
  display.println("All LP     SoC LP1"+ChargeStatus);
  display.setTextSize(2);
  display.print(LP_all_W);
  display.setCursor(11*6,32+8); //11 chars a 6px right, one 8px row below half of the display height (32px)
  String LP1_SOC_string="";
  if (LP1_SOC < 10)
  {
    LP1_SOC_string = "  "+String(LP1_SOC);
  }
  else if (LP1_SOC < 100)
  {
    LP1_SOC_string = " "+String(LP1_SOC);
  }
  else LP1_SOC_string = String(LP1_SOC);
  display.print(LP1_SOC_string + "%");
#else
  display.clearDisplay();
  display.setCursor(0,0); //set upper left corner of cursor to upper left corner of display
  
  // Determine currently displayed loadpoint data (cycling aware)
  int dispSoc = LP1_SOC;
  bool dispCharging = LP1_IsCharging;
  bool dispPlugged = LP1_PlugStat;
  String ChargeStatus="";
  if(dispCharging)      ChargeStatus = "C";
  else if(dispPlugged)  ChargeStatus = "P";
  else                  ChargeStatus = " ";

  display.setTextSize(1);
  display.setCursor(SCREEN_WIDTH/2-shift_k_value-shift_dot-8*6,0); // Text size 1 has width of 6
  // check if EVU power is smaller than 1 kW
  if (EVU_W < 1000)
  {
    // display description and value in W
    display.println(" EVU (W)");
  }
  else
  {
    // display description and value in kW
    display.println("EVU (kW)");
  }
  display.setTextSize(2);
  WriteWattValue(EVU_W, SCREEN_WIDTH/2-shift_k_value-shift_dot, 10);

  display.setTextSize(1);
  display.setCursor(SCREEN_WIDTH-7*6,0); // Text size 1 has width of 6
  // check if PV power is smaller than 1 kW
  if (PV_W < 1000)
  {
    // display description and value in W
    display.println(" PV (W)");
  }
  else
  {
    // display description and value in kW
    display.println("PV (kW)");
  }
  display.setTextSize(2);
  WriteWattValue(PV_W, SCREEN_WIDTH, 10);

  display.setTextSize(1);
  display.setCursor(SCREEN_WIDTH/2-shift_k_value-shift_dot-8*6,40); // Text size 1 has width of 6
  // check if ALL LP power is smaller than 1 kW
  if (LP_all_W < 1000)
  {
    // display description and value in W
    display.println(" ALL (W)");
  }
  else
  {
    // display description and value in kW
    display.println("ALL (kW)");
  }
  display.setTextSize(2);
  WriteWattValue(LP_all_W, SCREEN_WIDTH/2-shift_k_value-shift_dot, 50);
  
  display.setTextSize(1);
  display.setCursor(SCREEN_WIDTH-9*6,40); // Text size 1 has width of 6
  // Add LP index label (LP1 / LP2) if more than one loadpoint available
  String lpLabel = String(" SoC LP") + String(currentLpIndex+1);
  display.println(ChargeStatus + lpLabel); // Charge Status + dynamic LP label
  display.setTextSize(2);
  if (dispSoc < 10)
  {
    display.setCursor(SCREEN_WIDTH-2*12,50);
  }
  else if (dispSoc < 100)
  {
    display.setCursor(SCREEN_WIDTH-3*12,50);
  }
  else 
  {
    display.setCursor(SCREEN_WIDTH-4*12,50);
  }
  display.print(String(dispSoc)+"%");

  // drawing if energy is imported or exported
  // drawing the Power Symbol
  display.drawBitmap(20+0, 27, blitz, 8, 10, WHITE);
  // drawing the arrow (from or to house)
  if (EVU_dir > 0)
  {
    display.drawBitmap(20+8, 27, arrow_right, 8, 10, WHITE);
  }
  else
  {
    display.drawBitmap(20+8, 27, arrow_left, 8, 10, WHITE);
  }
  // drawing the house
  display.drawBitmap(20+18, 27, haus2, 16, 10, WHITE);

  // drawing the status of the charging station PLUGGED - UNPLUGGED - CHARGING (charging is also plugged!)
  if(LP1_IsCharging)
  {
    // charging, drawing plugged car plus Power symbol
    display.drawBitmap(SCREEN_WIDTH/2+20, 27, plugged, 24, 10, WHITE);
    display.drawBitmap(SCREEN_WIDTH/2+20+24+2, 27, blitz, 8, 10, WHITE);
  }
  else if(LP1_PlugStat==true)
  {
    // charging, drawing plugged car only - IMPORTANT BUG POSSIBLE POWER SYMBOL COULD STAY, MIGHT NEED BLACK SQUARE DRAWING
    display.drawBitmap(SCREEN_WIDTH/2+20, 27, plugged, 24, 10, WHITE);
  }
  else
  {
    // charging, drawing unplugged car only - IMPORTANT BUG POSSIBLE POWER SYMBOL COULD STAY, MIGHT NEED BLACK SQUARE DRAWING
    display.drawBitmap(SCREEN_WIDTH/2+20, 27, unplugged, 20, 10, WHITE);
  }
#endif
  display.display();
}

// ------------------------------------------------
//   SETUP running once at the beginning
// ------------------------------------------------
//   Initialize  Serial, WiFi and Siplay

void setup() 
{
  Serial.begin(115200);

  while (!Serial) { // wait for serial port to connect. 
    ; 
  }
  WriteLog("evcc Display Init");
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { // Address 0x3D for 128x64
  Serial.println(F("SSD1306 allocation failed"));
  for(;;); // Don't proceed, loop forever
  }
  display.display();
  display.setRotation(DISPLAY_ROTATION); // apply rotation
  
  // Clear the buffer
  display.clearDisplay();
  
  WriteLog("Waiting for WiFi connection");
  WriteDisplayNewText("Connecting to WiFi");
  WiFi.mode(WIFI_STA);                             // connect to AP
  WiFi.begin(ssid, pass);                          // set WiFi connections params
  WiFi.hostname(hostname);
 
  // Connecting
  int timout = 0;
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    WriteLog("O",0);
    display.setTextSize(1);
    display.print("O");
    display.display();
    timout++;
    if  (timout > 20)                 // couldn'T connect to WiFi within timeout. No WiFi. Need to add better handling
    {
      WriteLog("");
      WriteLog("Not Connected to WiFi");
      WriteDisplayNewText("Error connecting to WiFi. Exiting.");
      break;
    }
  }
 
  if (WiFi.status() == WL_CONNECTED)
  {
    WriteLog("");
    WriteLog("Connected to WiFi:");
    Serial.println(WiFi.localIP());
  }

  MDNS.begin(hostname);               // Start mDNS 
  server.on("/", HandleRoot);         // Call function if root is called
  server.on("/logs", HandleLogs);     // Return recent log lines
  server.on("/logs/clear", HandleLogsClear); // Clear log buffer
  
  httpUpdater.setup(&server);         // Updater
  server.begin();                     // start HTTP server
  WriteLog("HTTP server started");
  WriteLog("Starting HTTP polling loop");
  UpdateDisplay();
}

// ------------------------------------------------
//   MAIN LOOP RUNNING all the time
// ------------------------------------------------
void loop() 
{
  if(millis() - lastPollAttempt >= POLL_INTERVAL_MS) {
    lastPollAttempt = millis();
    if(!PollAndUpdate()) {
      consecutiveFailures++;
      WriteLog("Poll failed (#" + String(consecutiveFailures) + ")");
    }
  }

  unsigned long now = millis(); // capture AFTER potential update
  if (now - lastDataReceived > DATA_STALE_MS)
  {
    // Extra debug line (only every second to reduce flicker)
    static unsigned long lastErrLog = 0;
    if(now - lastErrLog > 1000) {
      WriteLog(String("Data stale: now=") + now + " lastDataReceived=" + lastDataReceived + " age=" + (now - lastDataReceived));
      lastErrLog = now;
    }
    display.clearDisplay();
    display.setTextSize(3);
    display.setCursor(0,0);
    display.println("Error");
    display.println("no data");
    display.display();
  }

  // Handle automatic loadpoint display cycling (only if we have 2 loadpoints and fresh data)
  if (g_metrics.lpCount > 1 && (now - lastDataReceived) <= DATA_STALE_MS) {
    if (now - lastLpSwitchMillis >= LP_CYCLE_INTERVAL_MS) {
      lastLpSwitchMillis = now;
      currentLpIndex = (currentLpIndex + 1) % g_metrics.lpCount; // wrap
      // Refresh legacy vars for text layout path and update display
      LP1_SOC        = g_metrics.lps[currentLpIndex].soc;
      LP1_IsCharging = g_metrics.lps[currentLpIndex].charging;
      LP1_PlugStat   = g_metrics.lps[currentLpIndex].plugged;
      UpdateDisplay();
    }
  }

  server.handleClient();
  MDNS.update();
}
