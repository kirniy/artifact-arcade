#!/usr/bin/env python3
"""Printer calibration and test script for ARTIFACT.

Run on Raspberry Pi to test printer connection and calibration:
    python scripts/test_printer.py

Tests performed:
1. Auto-detect printer port
2. Full-width test pattern (384 dots)
3. Text test with Cyrillic (CP866)
4. Image test (dithered)
5. Cut paper
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from artifact.hardware.printer.em5820 import EM5820Printer, auto_detect_printer_port


async def main():
    print("=" * 50)
    print("ARTIFACT Printer Calibration Test")
    print("=" * 50)
    
    # 1. Auto-detect port
    print("\n[1] Detecting printer port...")
    port = auto_detect_printer_port()
    
    if port:
        print(f"    ✓ Found printer at: {port}")
    else:
        print("    ✗ No printer detected!")
        print("    Check connections and try:")
        print("      ls -l /dev/ttyUSB* /dev/ttyACM* /dev/usb/lp* /dev/serial0")
        return
    
    # 2. Connect
    print("\n[2] Connecting to printer...")
    printer = EM5820Printer(port=port)
    
    if await printer.connect():
        print(f"    ✓ Connected!")
    else:
        print("    ✗ Connection failed!")
        return
    
    # 3. Initialize
    print("\n[3] Initializing printer...")
    await printer._send_command(b'\x1b\x40')  # ESC @ - Reset
    print("    ✓ Initialized")
    
    # 4. Full-width test pattern (384 dots = 48 bytes per line)
    print("\n[4] Printing full-width test pattern (384px)...")
    
    # Header
    await printer._send_command(b'\x1b\x61\x01')  # Center align
    await printer.print_text("=== ARTIFACT CALIBRATION ===")
    await printer.print_text("")
    
    # Test pattern - alternating black/white bars
    # Raster mode: GS v 0 m xL xH yL yH [data]
    width_bytes = 48  # 384 dots / 8 = 48 bytes
    height = 16  # 16 lines of pattern
    
    # Create alternating pattern
    pattern_data = bytearray()
    for y in range(height):
        for x in range(width_bytes):
            if y % 4 < 2:
                pattern_data.append(0xAA if x % 2 == 0 else 0x55)
            else:
                pattern_data.append(0x55 if x % 2 == 0 else 0xAA)
    
    # Send raster command
    raster_cmd = bytes([
        0x1d, 0x76, 0x30, 0x00,  # GS v 0 0
        width_bytes & 0xff, (width_bytes >> 8) & 0xff,  # Width
        height & 0xff, (height >> 8) & 0xff,  # Height
    ]) + bytes(pattern_data)
    
    await printer._send_command(raster_cmd)
    print("    ✓ Pattern printed")
    
    # 5. Text test
    print("\n[5] Printing text test (Cyrillic CP866)...")
    await printer.print_text("")
    await printer.print_text("VNVNC ARCADE TEST")
    await printer.print_text("ПРИВЕТ АРКАДА!")
    await printer.print_text("ФАКУЛЬТЕТ ТЕСТ")
    await printer.print_text("")
    
    # Width ruler
    await printer._send_command(b'\x1b\x61\x00')  # Left align
    await printer.print_text("0----5----10---15---20---25---30")
    await printer.print_text("================================")
    print("    ✓ Text printed")
    
    # 6. Paper feed and cut
    print("\n[6] Feeding and cutting paper...")
    await printer.feed_paper(3)
    await printer.cut_paper(partial=True)
    print("    ✓ Paper cut")
    
    # 7. Disconnect
    await printer.disconnect()
    
    print("\n" + "=" * 50)
    print("Calibration complete!")
    print("=" * 50)
    print("\nCheck the printout:")
    print("  - Pattern should be 58mm wide (full paper width)")
    print("  - Text should be readable and centered")
    print("  - Cyrillic characters should display correctly")
    print("  - If clipped, adjust layout.py paper_width (try 380)")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
