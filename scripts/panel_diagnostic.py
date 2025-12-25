#!/usr/bin/env python3
"""
LED Panel Pixel Diagnostic Script
Displays known patterns to help identify the panel's internal pixel arrangement.

Run on Raspberry Pi:
  sudo PYTHONPATH=/home/kirniy/rpi-rgb-led-matrix/bindings/python python3 panel_diagnostic.py

Options:
  --rows N        Panel rows (default: 64)
  --cols N        Panel columns (default: 64)
  --chain N       Number of chained panels (default: 1)
  --brightness N  Brightness 0-100 (default: 50)
  --slowdown N    GPIO slowdown (default: 4)
  --panel-type S  Panel type (e.g., FM6126A)
  --mux N         Multiplexing mode 0-22 (default: 0)
  --row-addr-type N  Row address type (default: 0)
  --rgb-sequence S   RGB sequence (e.g., RBG)
"""

import sys
import time
import argparse

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:
    print("ERROR: rgbmatrix not found. Run on Raspberry Pi with:")
    print("  sudo PYTHONPATH=/home/kirniy/rpi-rgb-led-matrix/bindings/python python3 panel_diagnostic.py")
    sys.exit(1)


def create_matrix(args):
    """Create RGB matrix with given options."""
    options = RGBMatrixOptions()
    options.hardware_mapping = 'regular'
    options.rows = args.rows
    options.cols = args.cols
    options.chain_length = args.chain
    options.parallel = 1
    options.brightness = args.brightness
    options.gpio_slowdown = args.slowdown
    options.disable_hardware_pulsing = True

    if args.panel_type:
        options.panel_type = args.panel_type
    if args.mux is not None:
        options.multiplexing = args.mux
    if args.row_addr_type is not None:
        options.row_address_type = args.row_addr_type
    if args.rgb_sequence:
        options.led_rgb_sequence = args.rgb_sequence

    return RGBMatrix(options=options)


def test_single_pixels(matrix, canvas):
    """Light up single pixels to identify mapping."""
    print("\n=== SINGLE PIXEL TEST ===")
    print("Watch which physical pixel lights up for each coordinate.")

    tests = [
        (0, 0, "red", (255, 0, 0)),      # Top-left
        (31, 0, "green", (0, 255, 0)),   # Top-middle (for 64-col)
        (63, 0, "blue", (0, 0, 255)),    # Top-right
        (0, 31, "yellow", (255, 255, 0)),# Middle-left
        (31, 31, "cyan", (0, 255, 255)), # Center
        (63, 31, "magenta", (255, 0, 255)), # Middle-right
        (0, 63, "white", (255, 255, 255)), # Bottom-left
        (31, 63, "orange", (255, 128, 0)), # Bottom-middle
        (63, 63, "pink", (255, 128, 128)), # Bottom-right
    ]

    for x, y, name, color in tests:
        if x < matrix.width and y < matrix.height:
            canvas.Clear()
            canvas.SetPixel(x, y, color[0], color[1], color[2])
            matrix.SwapOnVSync(canvas)
            print(f"  Pixel ({x}, {y}) = {name} - Press Enter to continue...")
            input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def test_rows(matrix, canvas):
    """Light up rows one at a time."""
    print("\n=== ROW TEST ===")
    print("Each row should light up as a horizontal line.")

    for y in range(0, matrix.height, 8):  # Every 8th row
        canvas.Clear()
        for x in range(matrix.width):
            canvas.SetPixel(x, y, 255, 255, 255)
        matrix.SwapOnVSync(canvas)
        print(f"  Row {y} - Press Enter to continue...")
        input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def test_columns(matrix, canvas):
    """Light up columns one at a time."""
    print("\n=== COLUMN TEST ===")
    print("Each column should light up as a vertical line.")

    for x in range(0, matrix.width, 8):  # Every 8th column
        canvas.Clear()
        for y in range(matrix.height):
            canvas.SetPixel(x, y, 255, 255, 255)
        matrix.SwapOnVSync(canvas)
        print(f"  Column {x} - Press Enter to continue...")
        input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def test_quadrants(matrix, canvas):
    """Light up quadrants with different colors."""
    print("\n=== QUADRANT TEST ===")
    print("This shows where the 4 quadrants appear physically.")

    canvas.Clear()
    half_w = matrix.width // 2
    half_h = matrix.height // 2

    # Top-left = Red
    for y in range(half_h):
        for x in range(half_w):
            canvas.SetPixel(x, y, 255, 0, 0)

    # Top-right = Green
    for y in range(half_h):
        for x in range(half_w, matrix.width):
            canvas.SetPixel(x, y, 0, 255, 0)

    # Bottom-left = Blue
    for y in range(half_h, matrix.height):
        for x in range(half_w):
            canvas.SetPixel(x, y, 0, 0, 255)

    # Bottom-right = Yellow
    for y in range(half_h, matrix.height):
        for x in range(half_w, matrix.width):
            canvas.SetPixel(x, y, 255, 255, 0)

    matrix.SwapOnVSync(canvas)
    print("  RED=top-left, GREEN=top-right, BLUE=bottom-left, YELLOW=bottom-right")
    print("  Press Enter to continue...")
    input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def test_numbered_grid(matrix, canvas):
    """Display a numbered grid pattern."""
    print("\n=== NUMBERED GRID TEST ===")
    print("Displays 8x8 blocks with different intensities.")

    canvas.Clear()
    block_size = 8

    for by in range(matrix.height // block_size):
        for bx in range(matrix.width // block_size):
            # Use different brightness levels to identify blocks
            intensity = ((by * (matrix.width // block_size) + bx) * 20) % 255 + 20

            for y in range(by * block_size, (by + 1) * block_size):
                for x in range(bx * block_size, (bx + 1) * block_size):
                    if x < matrix.width and y < matrix.height:
                        # Alternate colors for visibility
                        if (bx + by) % 3 == 0:
                            canvas.SetPixel(x, y, intensity, 0, 0)
                        elif (bx + by) % 3 == 1:
                            canvas.SetPixel(x, y, 0, intensity, 0)
                        else:
                            canvas.SetPixel(x, y, 0, 0, intensity)

    matrix.SwapOnVSync(canvas)
    print("  8x8 blocks with varying colors/intensities")
    print("  Take a photo to analyze block positions!")
    print("  Press Enter to continue...")
    input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def test_diagonal(matrix, canvas):
    """Display diagonal lines."""
    print("\n=== DIAGONAL TEST ===")
    print("Shows diagonal lines - helps identify row/column mapping.")

    canvas.Clear()

    # Main diagonal (top-left to bottom-right)
    for i in range(min(matrix.width, matrix.height)):
        canvas.SetPixel(i, i, 255, 0, 0)  # Red

    # Anti-diagonal (top-right to bottom-left)
    for i in range(min(matrix.width, matrix.height)):
        canvas.SetPixel(matrix.width - 1 - i, i, 0, 255, 0)  # Green

    matrix.SwapOnVSync(canvas)
    print("  RED = main diagonal (top-left to bottom-right)")
    print("  GREEN = anti-diagonal (top-right to bottom-left)")
    print("  Press Enter to continue...")
    input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def test_scan_pattern(matrix, canvas):
    """Visualize the scan pattern."""
    print("\n=== SCAN PATTERN TEST ===")
    print("Lights up rows in sequence to show scan order.")

    for y in range(matrix.height):
        canvas.Clear()
        for x in range(matrix.width):
            canvas.SetPixel(x, y, 255, 255, 255)
        matrix.SwapOnVSync(canvas)
        time.sleep(0.1)

    print("  Scan complete. Did rows light up top-to-bottom?")
    print("  Press Enter to continue...")
    input()


def test_address_lines(matrix, canvas):
    """Test address line response."""
    print("\n=== ADDRESS LINE TEST ===")
    print("For 1/32 scan, tests which rows share address lines.")

    # For 1/32 scan, rows 0 and 32 share same address
    # Light row pairs to see mapping
    pairs = [(0, 32), (1, 33), (2, 34), (3, 35)]

    for r1, r2 in pairs:
        if r2 < matrix.height:
            canvas.Clear()
            for x in range(matrix.width):
                canvas.SetPixel(x, r1, 255, 0, 0)  # Red
                canvas.SetPixel(x, r2, 0, 255, 0)  # Green
            matrix.SwapOnVSync(canvas)
            print(f"  Rows {r1} (red) and {r2} (green) - Press Enter...")
            input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def test_fill(matrix, canvas):
    """Test full panel fill."""
    print("\n=== FULL FILL TEST ===")

    colors = [
        ("RED", 255, 0, 0),
        ("GREEN", 0, 255, 0),
        ("BLUE", 0, 0, 255),
        ("WHITE", 255, 255, 255),
    ]

    for name, r, g, b in colors:
        canvas.Fill(r, g, b)
        matrix.SwapOnVSync(canvas)
        print(f"  {name} fill - does entire panel light up? Press Enter...")
        input()

    canvas.Clear()
    matrix.SwapOnVSync(canvas)


def main():
    parser = argparse.ArgumentParser(description='LED Panel Pixel Diagnostic')
    parser.add_argument('--rows', type=int, default=64, help='Panel rows')
    parser.add_argument('--cols', type=int, default=64, help='Panel columns')
    parser.add_argument('--chain', type=int, default=1, help='Chain length')
    parser.add_argument('--brightness', type=int, default=50, help='Brightness 0-100')
    parser.add_argument('--slowdown', type=int, default=4, help='GPIO slowdown')
    parser.add_argument('--panel-type', type=str, default=None, help='Panel type (e.g., FM6126A)')
    parser.add_argument('--mux', type=int, default=None, help='Multiplexing mode 0-22')
    parser.add_argument('--row-addr-type', type=int, default=None, help='Row address type')
    parser.add_argument('--rgb-sequence', type=str, default=None, help='RGB sequence (e.g., RBG)')
    args = parser.parse_args()

    print("=" * 60)
    print("LED PANEL PIXEL DIAGNOSTIC")
    print("=" * 60)
    mux_label = args.mux if args.mux is not None else 0
    print(f"Config: {args.rows}x{args.cols}, chain={args.chain}, mux={mux_label}")
    if args.panel_type:
        print(f"Panel type: {args.panel_type}")
    if args.row_addr_type is not None:
        print(f"Row address type: {args.row_addr_type}")
    if args.rgb_sequence:
        print(f"RGB sequence: {args.rgb_sequence}")
    print("=" * 60)

    matrix = create_matrix(args)
    canvas = matrix.CreateFrameCanvas()

    try:
        test_fill(matrix, canvas)
        test_quadrants(matrix, canvas)
        test_diagonal(matrix, canvas)
        test_single_pixels(matrix, canvas)
        test_rows(matrix, canvas)
        test_columns(matrix, canvas)
        test_numbered_grid(matrix, canvas)
        test_address_lines(matrix, canvas)
        test_scan_pattern(matrix, canvas)

        print("\n" + "=" * 60)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 60)
        print("Based on the results, determine:")
        print("1. Are rows and columns swapped?")
        print("2. Is the image mirrored or rotated?")
        print("3. Which address lines map to which physical rows?")
        print("4. Is the scan pattern normal or interleaved?")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        canvas.Clear()
        matrix.SwapOnVSync(canvas)


if __name__ == '__main__':
    main()
