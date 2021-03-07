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


// Global constants for WiFi connections
// ***********************************
// Need to replace with WiFiManager
// ***********************************

// Network setup
const char* ssid = "YOUR-SSID";              // your network SSID (name)
const char* pass = "YOUR-WiFi-Password";        // your network password
const char* hostname = "openWB-Display";      

// MQTT Setup
IPAddress MQTT_Broker(192,168,178,51); // openWB IP address
const int MQTT_Broker_Port = 1883;

// MQTT topics and variables for retrieved values
const char* MQTT_EVU_W = "openWB/evu/W";    // current power at EVU
float EVU_kW = 0;

const char* MQTT_PV_W = "openWB/pv/W";      // current PV power
float PV_kW = 0;

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
  if (strcmp(topic,"openWB/evu/W")==0){EVU_kW = (msg.toFloat())/1000;}
  if (strcmp(topic,"openWB/pv/W")==0){PV_kW = (msg.toFloat()*-1)/1000;}
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


void UpdateDisplay()
{
  // for a 128*64px display:
  // Text Size 1: single char 6*8px, 21 chars per row, 8 rows 
  // Text Size 2: single char 12*16px, 10 chars per row, 4 rows 
  // Text Size 3: single char 18*24x, 7 chars per row, 2.5 rows 
  // Text Size 4: single char 24*32x, 5 chars per row, 2 rows 
  // Text Size 8: single char 48*64x, 2 chars per row, 1 row 
  
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
  display.print(String(LP1_SOC) + "%");
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
