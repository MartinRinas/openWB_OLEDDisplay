#include <ESP8266WiFi.h>
#include <WiFiUDP.h>
#include <ESP8266mDNS.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPUpdateServer.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// UI_STYLE defines the style of the UI
// 1 is orignal, 2 is with grafic symbols
#define UI_GRAPHIC_STYLE

// Global constants for WiFi connections
// ***********************************
// Need to replace with WiFiManager
// ***********************************

// Network setup
const char* ssid = "YOUR-SSID";              // your network SSID (name)
const char* pass = "YOUR-WiFi-Password";        // your network password
const char* hostname = "openWB-Display";      

// MQTT Setup
IPAddress MQTT_Broker(192,168,10,140); // openWB IP address
const int MQTT_Broker_Port = 1883;

// MQTT topics and variables for retrieved values
const char* MQTT_EVU_W = "openWB/evu/W";    // current power at EVU
#ifndef UI_GRAPHIC_STYLE
float EVU_kW = 0;
#else UI_GRAPHIC_STYLE
int EVU_W = 0;
int EVU_dir = 1;
#endif

const char* MQTT_PV_W = "openWB/pv/W";      // current PV power
#ifndef UI_GRAPHIC_STYLE
float PV_kW = 0;
#else
int PV_W = 0;
#endif

const char* MQTT_LP_all_W= "openWB/global/WAllChargePoints";  // current power draw for all charge points
int LP_all_W = 0;

const char* MQTT_LP1_SOC= "openWB/lp/1/%Soc";  // current power draw for all charge points
int LP1_SOC = 0;

const char* MQTT_LP1_PlugStat = "openWB/lp/1/boolPlugStat"; // is the car plugged in?
bool LP1_PlugStat = false;

const char* MQTT_LP1_IsCharging = "openWB/lp/1/boolChargeStat"; // charging active?
bool LP1_IsCharging = false;


// Display Setup
#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels

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

unsigned long currentMillis;
unsigned long previousMillis = 0;         // last time data was fetched
unsigned long lastMQTTDataReceived = 0;
int MaxDataAge = 30*1000; // max wait time for new data from MQTT subscription

WiFiClient espClient;
PubSubClient MQTTClient(espClient);
long lastReconnectAttempt = 0; // WiFi Reconnection timer

// Config flags do enable features
const bool isDebug = 1;                        // Send debug messages to serial port?

// ESP8266 Webserver and update server
ESP8266WebServer server(80);              // HTTP server port
ESP8266HTTPUpdateServer httpUpdater;      // HTTP update server, allows OTA flash by navigating to http://<ESP8266IP>/update

void WriteLog(String msg,bool NewLine=1)  // helper function for logging, only write to serial if isDebug is true
{
  if(NewLine)
  {
    if(isDebug){Serial.println(msg);}
  }
  else
  {
    if(isDebug){Serial.print(msg);}
  } 
}

boolean MQTTReconnect() 
{
  if (MQTTClient.connect(hostname)) 
  {
    WriteLog("MQTT Reconnected");
    boolean r = MQTTClient.subscribe(MQTT_EVU_W);
    if (r)
    {
        WriteLog("MQTT subscription suceeded");
    }
    else
    {
        WriteLog("MQTT subscription failed");
    }
    
    r = MQTTClient.subscribe(MQTT_LP_all_W);
    r = MQTTClient.subscribe(MQTT_PV_W);
    r = MQTTClient.subscribe(MQTT_LP1_SOC);
    r = MQTTClient.subscribe(MQTT_LP1_IsCharging);
    r = MQTTClient.subscribe(MQTT_LP1_PlugStat);
  }
  return MQTTClient.connected();
}

void HandleRoot()                                                 // Handle Webserver request on root
{
  String res = "HTTP Server up and running.";
  WebserverResponse(res);
}

void HandleMQTTStatus()
{
  String res = String(MQTTClient.state());
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

void MQTTCallback(char* topic, byte* payload, unsigned int length) 
{
  lastMQTTDataReceived = millis();
  WriteLog("Message arrived: [" ,0);
  WriteLog(topic ,0);
  WriteLog("]" ,0);
  String msg;
  for (int i=0;i<length;i++) { // extract payload
    msg = msg + (char)payload[i];
  }
  WriteLog(msg);
  
  // store values in variables
  // todo use MQTT_ constants instead of hard coded values to compare
#ifndef UI_GRAPHIC_STYLE
  if (strcmp(topic,"openWB/evu/W")==0){EVU_kW = (msg.toFloat())/1000;}
  if (strcmp(topic,"openWB/pv/W")==0){PV_kW = (msg.toFloat()*-1)/1000;}
#else
  if (strcmp(topic,"openWB/evu/W")==0){ EVU_W = (msg.toInt()); EVU_dir = 1;
                                        if (EVU_W < 0)
                                        {
                                           EVU_W = EVU_W*(-1);
                                           EVU_dir = -1;
                                        }
                                      }
  if (strcmp(topic,"openWB/pv/W")==0){PV_W = (msg.toInt()*-1);}
#endif
  if (strcmp(topic,"openWB/global/WAllChargePoints")==0){LP_all_W = msg.toInt();}
  if (strcmp(topic,"openWB/lp/1/%Soc")==0){LP1_SOC = msg.toInt();}
  if (strcmp(topic,"openWB/lp/1/boolChargeStat")==0){LP1_IsCharging = msg.toInt();}
  if (strcmp(topic,"openWB/lp/1/boolPlugStat")==0){LP1_PlugStat = msg.toInt();}
  
  // processed incoming message, lets update the display
  UpdateDisplay();
}

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
  
  String ChargeStatus="";
  if(LP1_IsCharging)
  {
    ChargeStatus = "C";
  }
  else if(LP1_PlugStat==true)
  {
    ChargeStatus="P";
  }
  else
  {
    ChargeStatus=" ";
  }

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
  display.println(ChargeStatus+" SoC LP1"); // Charge Status as Symbol also available, could be removed from this line
  display.setTextSize(2);
  if (LP1_SOC < 10)
  {
    display.setCursor(SCREEN_WIDTH-2*12,50);
  }
  else if (LP1_SOC < 100)
  {
    display.setCursor(SCREEN_WIDTH-3*12,50);
  }
  else 
  {
    display.setCursor(SCREEN_WIDTH-4*12,50);
  }
  display.print(String(LP1_SOC)+"%");

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
  WriteLog("openWB Display Init");
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { // Address 0x3D for 128x64
  Serial.println(F("SSD1306 allocation failed"));
  for(;;); // Don't proceed, loop forever
  }
  display.display();
  
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
  
  httpUpdater.setup(&server);         // Updater
  server.begin();                     // start HTTP server
  WriteLog("HTTP server started");
   
  MQTTClient.setServer(MQTT_Broker,MQTT_Broker_Port);
  MQTTClient.setCallback(MQTTCallback);
  lastReconnectAttempt = 0;
  MQTTReconnect;
  
  WriteLog("Exiting Setup, starting main loop");
  UpdateDisplay();
}

// ------------------------------------------------
//   MAIN LOOP RUNNING all the time
// ------------------------------------------------
void loop() 
{
  if (!MQTTClient.connected())      // non blocking MQTT reconnect sequence
    {
        long now = millis();
        if (now - lastReconnectAttempt > 5000) 
        {
          lastReconnectAttempt = now;
          WriteLog("Attempting to reconnect MQTT");
          if (MQTTReconnect()) 
          {
              lastReconnectAttempt = 0;
          }
        }
    }
    else                            // MQTT is connected, lets send some data
    { 
        // do things
    }
  if (millis()-lastMQTTDataReceived > MaxDataAge)
  {
    display.clearDisplay();
    display.setTextSize(3);
    display.setCursor(0,0);
    display.println("Error");
    display.println("no data");
    display.display();
  }

  MQTTClient.loop();                    // handle MQTT client & subscription. Display logic is subscription event triggered and can be found in the callback function.
  server.handleClient();                // handle webserver requests
  MDNS.update();                        // handle mDNS requests
}
