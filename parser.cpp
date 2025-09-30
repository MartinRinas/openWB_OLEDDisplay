#include "parser.h"

// Attempt to parse minimized jq filtered JSON first; fallback to broader legacy layout.
bool ParseEvccState(const String& body, Metrics& out) {
    StaticJsonDocument<1024> doc; // sized for minimized payload
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        return false; // caller may log details
    }

    // Primary (minimized) structure: {gridPower, pvPower, loadpoints:[{chargePower, soc/vehicleSoc, charging, plugged}, ...]}
    bool usedMin = true;
    JsonArray lps = doc["loadpoints"].as<JsonArray>();
    if (doc.containsKey("gridPower")) {
        out.gridPower = doc["gridPower"].as<long>();
    } else {
        usedMin = false;
    }
    if (doc.containsKey("pvPower")) {
        out.pvPower = doc["pvPower"].as<long>();
    } else {
        usedMin = false;
    }
    if (usedMin && !lps.isNull() && lps.size() > 0) {
        out.totalChargePower = 0;
        out.lpCount = 0;
        uint8_t limit = lps.size() < 2 ? lps.size() : 2;
        for (uint8_t i=0; i<limit; i++) {
            JsonVariant lpi = lps[i];
            MetricsLoadpoint &mlp = out.lps[i];
            mlp.chargePower = lpi["chargePower"].as<long>();
            if (lpi["soc"].is<int>()) mlp.soc = lpi["soc"].as<int>();
            else if (lpi["soc"].is<float>()) mlp.soc = (int)(lpi["soc"].as<float>() + 0.5f);
            else if (lpi["vehicleSoc"].is<int>()) mlp.soc = lpi["vehicleSoc"].as<int>();
            else if (lpi["vehicleSoc"].is<float>()) mlp.soc = (int)(lpi["vehicleSoc"].as<float>() + 0.5f);
            mlp.charging = lpi["charging"].as<bool>();
            mlp.plugged  = lpi["plugged"].as<bool>() || lpi["connected"].as<bool>();
            out.totalChargePower += mlp.chargePower;
            out.lpCount++;
        }
        return true;
    }

    // Fallback: try legacy / full state keys
    // grid.power, pvPower, loadpoints array objects with chargePower & vehicleSoc or soc
    JsonVariant grid = doc["grid"];
    if (grid.is<JsonObject>() && grid["power"].is<long>()) {
        out.gridPower = grid["power"].as<long>();
    }
    if (doc["pvPower"].is<long>()) {
        out.pvPower = doc["pvPower"].as<long>();
    }
    if (doc["loadpoints"].is<JsonArray>()) {
        lps = doc["loadpoints"].as<JsonArray>();
        out.totalChargePower = 0;
        out.lpCount = 0;
        if (!lps.isNull()) {
            uint8_t limit = lps.size() < 2 ? lps.size() : 2;
            for (uint8_t i=0; i<limit; i++) {
                JsonVariant lpv = lps[i];
                MetricsLoadpoint &mlp = out.lps[i];
                mlp.chargePower = lpv["chargePower"].as<long>();
                if (lpv["vehicleSoc"].is<int>()) mlp.soc = lpv["vehicleSoc"].as<int>();
                else if (lpv["vehicleSoc"].is<float>()) mlp.soc = (int)(lpv["vehicleSoc"].as<float>() + 0.5f);
                else if (lpv["soc"].is<int>()) mlp.soc = lpv["soc"].as<int>();
                else if (lpv["soc"].is<float>()) mlp.soc = (int)(lpv["soc"].as<float>() + 0.5f);
                mlp.charging = lpv["charging"].as<bool>();
                mlp.plugged  = lpv["connected"].as<bool>() || lpv["plugged"].as<bool>();
                out.totalChargePower += mlp.chargePower;
                out.lpCount++;
            }
        }
        return true;
    }

    return false; // nothing usable
}
