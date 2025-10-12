#!/usr/bin/env python3
"""
Test script for E Ink Spectra 6 display
Tests basic display functionality before running Flask app
"""

import sys
import os
sys.path.append(os.path.expanduser('~/e-Paper/RaspberryPi_JetsonNano/python/lib'))
from waveshare_epd import epd7in3e

def test_clear():
    """Test clearing the display"""
    print("Testing clear function...")
    try:
        epd = epd7in3e.EPD()
        epd.init()
        epd.Clear()
        epd.sleep()
        print("✓ Clear successful!")
        return True
    except Exception as e:
        print(f"✗ Clear failed: {e}")
        return False

def test_color_bands():
    """Test displaying horizontal color bands"""
    print("\nTesting color bands...")
    try:
        epd = epd7in3e.EPD()
        epd.init()
        
        # Create test pattern with color bands
        # 6 colors: black, white, yellow, red, blue, green
        test_data = bytearray(192000)
        
        band_height = 80  # 480 / 6 = 80 pixels per color
        colors = [0x0, 0x1, 0x2, 0x3, 0x5, 0x6]  # Color codes
        
        for row in range(480):
            color_idx = row // band_height
            if color_idx >= len(colors):
                color_idx = len(colors) - 1
            
            color = colors[color_idx]
            # Fill entire row with same color (2 pixels per byte)
            byte_value = (color << 4) | color
            
            for col in range(400):  # 800 pixels / 2 = 400 bytes per row
                byte_index = row * 400 + col
                test_data[byte_index] = byte_value
        
        epd.display(bytes(test_data))
        epd.sleep()
        print("✓ Color bands displayed!")
        print("  You should see 6 horizontal bands:")
        print("  1. Black")
        print("  2. White") 
        print("  3. Yellow")
        print("  4. Red")
        print("  5. Blue")
        print("  6. Green")
        return True
        
    except Exception as e:
        print(f"✗ Color bands failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_checkerboard():
    """Test checkerboard pattern"""
    print("\nTesting checkerboard pattern...")
    try:
        epd = epd7in3e.EPD()
        epd.init()
        
        test_data = bytearray(192000)
        
        for row in range(480):
            for col in range(0, 800, 2):
                # Checkerboard: alternate black (0x0) and white (0x1)
                if (row // 20 + col // 20) % 2 == 0:
                    byte_value = 0x00  # Black, Black
                else:
                    byte_value = 0x11  # White, White
                
                byte_index = row * 400 + col // 2
                test_data[byte_index] = byte_value
        
        epd.display(bytes(test_data))
        epd.sleep()
        print("✓ Checkerboard displayed!")
        return True
        
    except Exception as e:
        print(f"✗ Checkerboard failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("E Ink Spectra 6 Display Test")
    print("=" * 40)
    
    print("\nThis will test your display with:")
    print("1. Clear screen")
    print("2. Color bands (all 6 colors)")
    print("3. Checkerboard pattern")
    print("\nPress Ctrl+C to cancel, Enter to continue...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        sys.exit(0)
    
    results = []
    results.append(("Clear", test_clear()))
    results.append(("Color Bands", test_color_bands()))
    results.append(("Checkerboard", test_checkerboard()))
    
    print("\n" + "=" * 40)
    print("Test Results:")
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name}: {status}")
    
    if all(r[1] for r in results):
        print("\n✓ All tests passed! Your display is working correctly.")
        print("You can now run the Flask app: python3 app.py")
    else:
        print("\n✗ Some tests failed. Check connections and library installation.")
