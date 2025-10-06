# E-Ink Display Layout Implementation (212x104px)

## Overview
This implementation provides a new layout for a 2.13" e-ink display with 212x104 pixel resolution, designed to match the provided design image. The layout efficiently displays all the key energy system information in a compact format.

## Layout Design

### Display Sections
The 212x104 pixel display is divided into several sections:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  ☀ 11kW                                                            ⚡ 11kW         │  ← Top row
├─────────────────────────────────────────────────────────────────────────────────────┤
│  🔋 -2kW     14% ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░              │  ← Battery
├─────────────────────────────────────────────────────────────────────────────────────┤
│  100% ████████████████████████████████░ Tesla      -% ░░░░░░░░░░░░░░░░░ Smart        │  ← Charge points
│  3kW                               P    0kW                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  🏠 1kW                                                                    14:25    │  ← Bottom row
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Position Mapping
- **Top Left (PV)**: Solar icon + power value (2, 2)
- **Top Right (Grid)**: Lightning icon + power value (160, 2)
- **Middle Left (Battery)**: Battery icon + power + SoC% + bar (2, 22)
- **Middle Center (LP1)**: SoC% + bar + vehicle name + power (2, 42)
- **Middle Right (LP2)**: SoC% + bar + vehicle name + power (130, 42)
- **Bottom Left (House)**: House icon + consumption (2, 82)
- **Bottom Right (Time)**: Current time (160, 83)

## Implementation Details

### Key Features
1. **Compact Power Formatting**: Shows values as W, k (for kW), with appropriate decimal places
2. **SoC Bars**: Visual battery/vehicle charge indicators with percentage fill
3. **Status Indicators**: 'P' for plugged, 'C' for charging
4. **Icons**: Simple 8x8 pixel icons for PV, grid, battery, and house
5. **Dual Loadpoint Support**: Shows both Tesla and Smart vehicle data

### Data Structure
The implementation extends the original `DisplayData` class with:
```python
class DisplayData:
    def __init__(self):
        # Existing fields...
        self.house_kw = 0.0                # House consumption
        self.battery_power_kw = 0.0        # Battery power (+ charging, - discharging)
        # Loadpoint 1 (Tesla)
        self.lp1_power_kw = 0.0
        self.lp1_vehicle_name = "Tesla"
        # Loadpoint 2 (Smart)
        self.lp2_soc = -1
        self.lp2_plug_stat = False
        self.lp2_is_charging = False
        self.lp2_power_kw = 0.0
        self.lp2_vehicle_name = "Smart"
```

### Helper Functions
- `draw_solar_icon()`: 8x8 solar panel icon
- `draw_grid_icon()`: 8x8 lightning bolt icon
- `draw_battery_icon()`: 8x6 battery icon with terminal
- `draw_house_icon()`: 8x8 house icon
- `draw_soc_bar()`: Draws percentage-filled bars
- `format_power_compact()`: Formats power values for space efficiency

## File Changes Made

### main.py
1. **Updated display dimensions**: Changed from 250x122 to 212x104
2. **Enhanced data structure**: Added new fields for house consumption, battery power, and dual loadpoints
3. **New layout function**: Complete rewrite of `update_display()` with the new design
4. **Improved data parsing**: Better handling of multiple loadpoints and power calculations

### eink_simulator.py
1. **Updated dimensions**: Changed simulator to 212x104 with 4x scaling
2. **Mock data**: Provides realistic test data matching the design image
3. **Better error handling**: Always uses mock data for consistent testing

### test_layout_demo.py (New)
A standalone demo that shows exactly how the layout will look with the data from your attached image:
- PV: 11kW
- Grid: 11kW 
- Battery: -2kW (discharging), 14% SoC
- Tesla: 100% SoC, 3kW charging power, plugged
- Smart: No data, not connected
- House: 1kW consumption

## Usage

### Running the Simulator
```bash
python eink_simulator.py
```
This runs the full simulation with periodic data updates.

### Running the Layout Demo
```bash
python test_layout_demo.py
```
This shows a static layout with the exact data from your design image.

## Configuration
The layout automatically:
- Handles missing vehicle data (shows "-%" for unknown SoC)
- Formats power values appropriately (W/kW with decimals as needed)
- Shows charging status (C) or plugged status (P) indicators
- Calculates house consumption from available data
- Estimates battery power flow

## Hardware Requirements
- 2.13" e-ink display with 212x104 resolution
- ESP32-S3 or compatible microcontroller
- Compatible e-ink driver (Waveshare or similar)

The implementation is optimized for e-ink displays with:
- Minimal updates (10-second intervals)
- High contrast black/white design
- Large, readable text and icons
- Clear visual hierarchy

This layout maximizes information density while maintaining readability on the compact 2.13" e-ink display.