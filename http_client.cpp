#include "http_client.h"

// Forward declaration of logging function implemented in main sketch
// Provide default parameter to match original definition.
void WriteLog(String msg, bool NewLine = true);

bool HttpGet(const char* host, uint16_t port, const char* path, String& outBody) {
    WiFiClient client;
    WriteLog(String("HTTP poll: connecting ") + host + ":" + port + " path " + path, true);
    if (!client.connect(host, port)) {
    WriteLog("HTTP connect failed", true);
        return false;
    }
    client.print(String("GET ") + path + " HTTP/1.1\r\n" \
                 + "Host: " + host + "\r\n" \
                 + "Connection: close\r\n" \
                 + "Cache-Control: no-cache\r\n\r\n");

    unsigned long start = millis();
    while(!client.available() && millis() - start < 3000) {
        delay(10);
    }
    if(!client.available()) {
    WriteLog("HTTP timeout waiting for response", true);
        client.stop();
        return false;
    }

    // Read full response (small, due to jq filter). Limit to 4096 for safety.
    String response;
    while(client.available()) {
        char c = client.read();
        response += c;
        if(response.length() > 4096) {
            WriteLog("Response exceeded 4KB limit", true);
            client.stop();
            return false;
        }
    }
    client.stop();

    int bodyIndex = response.indexOf("\r\n\r\n");
    if(bodyIndex < 0) {
    WriteLog("Malformed response (no header terminator)", true);
        return false;
    }
    outBody = response.substring(bodyIndex + 4);
    outBody.trim();
    if(outBody.isEmpty()) {
    WriteLog("Empty body", true);
        return false;
    }
    // Quick sanity snippet
    String snippet; snippet.reserve(80);
    int n = outBody.length() < 80 ? outBody.length() : 80;
    for(int i=0;i<n;i++){ char ch = outBody[i]; snippet += (ch >=32 && ch<127)?ch:'.'; }
    WriteLog("Body " + String(outBody.length()) + "B snippet: " + snippet, true);
    return true;
}
