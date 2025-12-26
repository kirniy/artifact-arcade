# Thermal Printer Integration Quick Reference

**Based on**: raspi-photo-booth analysis  
**Target**: ARTIFACT AI Prophet mode with thermal receipt printing

---

## Hardware Differences

| Component | raspi-photo-booth | ARTIFACT |
|-----------|-------------------|----------|
| Printer Port | `/dev/usb/lp0` (USB) | `/dev/ttyAMA0` (UART) |
| Printer Model | POS58 | POS58 (same) |
| Print Width | 380px (58mm @ 203 DPI) | 380px (58mm @ 203 DPI) |

---

## Code Template for ARTIFACT

### 1. Initialize Thermal Printer (UART)

```python
from escpos.printer import Serial

class ThermalPrinter:
    def __init__(self, port='/dev/ttyAMA0', baudrate=9600):
        self.printer = Serial(devfile=port, baudrate=baudrate)
    
    def __enter__(self):
        return self.printer
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.printer.close()
```

### 2. Image Preparation (Critical!)

```python
from PIL import Image

def prepare_image_for_thermal(image_path):
    """
    Resize and dither image for thermal printer.
    POS58 max width: 384 dots (use 380 for margins)
    """
    img = Image.open(image_path)
    
    # Resize preserving aspect ratio
    img.thumbnail((380, 500), Image.LANCZOS)
    
    # Convert to 1-bit with Floyd-Steinberg dithering
    img_bw = img.convert('1')
    
    return img_bw
```

### 3. Print Receipt with Caricature

```python
from datetime import datetime

def print_receipt(image_path, prediction_text):
    thermal = Serial(devfile='/dev/ttyAMA0', baudrate=9600)
    
    # Header
    thermal.set(align='center', bold=True, double_height=True)
    thermal.text('ARTIFACT\n')
    thermal.set(bold=False, double_height=False)
    thermal.text('AI Prophet\n\n')
    
    # Caricature image
    img = prepare_image_for_thermal(image_path)
    thermal.image(img)
    thermal.text('\n')
    
    # Prediction text (word wrap at ~32 chars)
    thermal.set(align='left')
    wrapped_text = '\n'.join(
        prediction_text[i:i+32] 
        for i in range(0, len(prediction_text), 32)
    )
    thermal.text(wrapped_text + '\n\n')
    
    # Footer
    thermal.set(align='center', bold=True)
    thermal.text(f'{datetime.now().strftime("%Y-%m-%d %H:%M")}\n')
    
    # Spacing for tear-off (5 line feeds)
    thermal.text('\n\n\n\n\n')
    
    # Auto-cut if supported
    thermal.cut()
    
    thermal.close()
```

---

## Testing on Pi

### Test 1: Basic Printing
```bash
ssh kirniy@artifact.local
cd ~/modular-arcade

# Test script
python3 << 'PYTHON'
from escpos.printer import Serial

thermal = Serial(devfile='/dev/ttyAMA0', baudrate=9600)
thermal.set(align='center', bold=True)
thermal.text('ARTIFACT TEST\n')
thermal.text('\n\n\n')
thermal.cut()
thermal.close()
PYTHON
```

### Test 2: Image Printing
```bash
# Download a test image
wget https://via.placeholder.com/400x400.png -O /tmp/test.png

# Print it
python3 << 'PYTHON'
from escpos.printer import Serial
from PIL import Image

img = Image.open('/tmp/test.png')
img.thumbnail((380, 500), Image.LANCZOS)
img_bw = img.convert('1')

thermal = Serial(devfile='/dev/ttyAMA0', baudrate=9600)
thermal.image(img_bw)
thermal.text('\n\n\n\n\n')
thermal.cut()
thermal.close()
PYTHON
```

---

## Concurrency Pattern (Anti-Spam)

```python
class PhotoboothMode:
    def __init__(self):
        self.capturing = False
    
    def handle_button_press(self):
        if not self.capturing:
            self.capturing = True
            try:
                self.run_photo_sequence()
            finally:
                self.capturing = False
    
    def run_photo_sequence(self):
        # Countdown
        self.countdown(4)
        
        # Capture
        photo_path = self.capture_photo()
        
        # AI processing
        caricature_path, prediction = self.generate_caricature(photo_path)
        
        # Print
        print_receipt(caricature_path, prediction)
```

---

## Countdown Display Integration

```python
def countdown(self, seconds=4):
    """Show countdown on 128x128 main display"""
    for i in range(seconds, 0, -1):
        # Clear screen
        self.display.fill((0, 0, 0))
        
        # Render large number
        self.render_text(
            str(i), 
            scale=4, 
            center=True,
            color=(255, 255, 0)
        )
        
        # Ticker flash
        self.ticker.flash_color((255, 255, 0))
        
        # Audio beep
        pygame.mixer.Sound('assets/beep.wav').play()
        
        pygame.display.flip()
        time.sleep(1)
    
    # Flash white (camera flash simulation)
    self.display.fill((255, 255, 255))
    pygame.display.flip()
    time.sleep(0.2)
```

---

## Image Dithering Comparison

| Method | Quality | Speed | Use Case |
|--------|---------|-------|----------|
| `convert('1')` | Good (Floyd-Steinberg) | Fast | Default |
| `convert('1', dither=Image.NONE)` | Poor (threshold) | Fastest | Line art only |
| Custom dithering | Best | Slow | Not needed |

**Recommendation**: Use `convert('1')` for automatic Floyd-Steinberg dithering.

---

## Common Issues

### Issue 1: Printer Not Responding
```bash
# Check UART is enabled
ls -l /dev/ttyAMA0

# Test with simple command
echo "test" > /dev/ttyAMA0
```

### Issue 2: Image Too Dark/Light
```python
# Adjust contrast before dithering
from PIL import ImageEnhance

img = Image.open(path)
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(1.5)  # Increase contrast
img_bw = img.convert('1')
```

### Issue 3: Slow Printing
```python
# Use lower resolution for faster printing
img.thumbnail((256, 340), Image.LANCZOS)  # 2/3 width
```

---

## Next Steps

1. Test basic thermal printing on Pi (ssh to artifact.local)
2. Create `ThermalPrinter` wrapper class
3. Implement image dithering pipeline
4. Add countdown display to AI Prophet mode
5. Test full photo-to-print workflow
