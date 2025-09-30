// parser.h - Extraction of EVCC state JSON into internal Metrics structure
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

struct MetricsLoadpoint {
    long chargePower = 0;
    int  soc = -1;
    bool charging = false;
    bool plugged = false;
};

struct Metrics {
    long gridPower = 0;         // signed W (import positive / export negative per evcc convention)
    long pvPower = 0;           // PV generation W
    long totalChargePower = 0;  // Sum of all loadpoint charge powers (up to 2 considered)
    uint8_t lpCount = 0;        // number of parsed loadpoints (0..2)
    MetricsLoadpoint lps[2];    // first two loadpoints
};

// Parses either minimized filtered JSON or (fallback) a larger legacy structure.
// Returns true on success and fills Metrics; false if unparsable / required keys missing.
bool ParseEvccState(const String& body, Metrics& out);
