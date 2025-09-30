// http_client.h - Simple blocking HTTP GET helper for ESP8266
#pragma once
#include <Arduino.h>
#include <ESP8266WiFi.h>

// Performs a simple HTTP/1.1 GET (Connection: close) and returns body in 'outBody'.
// Returns true if a 200 status and non-empty body were received.
// On failure returns false (caller can inspect logs).
bool HttpGet(const char* host, uint16_t port, const char* path, String& outBody);
