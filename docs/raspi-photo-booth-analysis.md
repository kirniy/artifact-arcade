# raspi-photo-booth Analysis for ARTIFACT Integration

**Repository**: https://github.com/kriskbx/raspi-photo-booth  
**Date**: 2025-12-27  
**Purpose**: Extract patterns and code for thermal printing photobooth mode in ARTIFACT

---

## Overview

A minimalist photobooth implementation (2.4KB Python script) with:
- Single arcade button trigger
- Pi Camera capture
- Thermal printer output (POS58)
- LED + buzzer feedback
- Auto-resize for thermal printer width

---

## 1. Arcade Button Input

### Hardware Connection
```python
ButtonPin = 12  # GPIO 12 (BOARD numbering)
GPIO.setup(ButtonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
```

**Button wiring**: Arcade button → GPIO 12 → GND (uses internal pull-up resistor)

### Event Detection
```python
def loop():
    GPIO.add_event_detect(ButtonPin, GPIO.FALLING, callback=buttonPress)
    while True:
        pass
```

**Pattern**: 
- Uses `GPIO.FALLING` edge detection (button press pulls pin LOW)
- Callback function `buttonPress()` triggered on press
- Non-blocking event-driven approach

**ARTIFACT Equivalent**:
Our USB arcade button sends ENTER keycode. We use pygame event loop instead:
```python
for event in pygame.event.get():
    if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
        # Trigger photo sequence
```

**Key Difference**: They use GPIO edge detection, we use USB HID keyboard events.

---

## 2. Thermal Printer (POS58)

### Printer Setup
```python
import escpos.printer as printer

Thermal = printer.File("/dev/usb/lp0")  # USB printer device
```

### Print Sequence
```python
def printPhoto(image):
    Thermal = printer.File("/dev/usb/lp0")
    Thermal.image(image)
    Thermal.control('LF')  # Line feeds (5x for separation)
    Thermal.control('LF')
    Thermal.control('LF')
    Thermal.control('LF')
    Thermal.control('LF')
    Thermal.close()
```

### Image Processing
```python
def resizePhoto(photo):
    thumbnail = photo.replace('.jpg', '.thumbnail.jpg')
    try:
        im = Image.open(photo)
        im.thumbnail((380, 500), Image.ANTIALIAS)  # POS58 max width ~380px
        im.save(thumbnail, "JPEG")
        return thumbnail
    except IOError:
        print "cannot create thumbnail for '%s'" % photo
        return False
```

**Key Points**:
- POS58 thermal printer width: ~380 pixels (58mm at 203 DPI)
- Use PIL/Pillow `thumbnail()` to preserve aspect ratio
- 5× line feeds create tear-off spacing

**ARTIFACT Adaptation**:
```python
from escpos.printer import Serial

# Our printer is on UART, not USB
thermal = Serial(devfile='/dev/ttyAMA0', baudrate=9600)

# Print with dithering for better quality
from PIL import Image
img = Image.open('caricature.jpg')
img_resized = img.resize((380, 500), Image.LANCZOS)
img_bw = img_resized.convert('1')  # 1-bit dithering
thermal.image(img_bw)
thermal.cut()  # Auto-cut if supported
```

---

## 3. Pi Camera Capture

### Camera Usage
```python
import picamera

def takePhoto():
    image = ImagePath + str(time.time()) + '.jpg'
    print image
    Camera = picamera.PiCamera()
    Camera.resolution = (3280, 2464)  # Max resolution for Pi Camera V2
    Camera.capture(image)
    Camera.close()
    return image
```

**Pattern**:
- Open camera for each photo (not persistent)
- Max resolution: 3280×2464 (8MP)
- Close immediately after capture

**ARTIFACT Adaptation** (using picamera2):
```python
from picamera2 import Picamera2

picam = Picamera2()
config = picam.create_still_configuration(
    main={"size": (4608, 2592)},  # Pi Camera 3 max resolution (12MP)
    buffer_count=2
)
picam.configure(config)
picam.start()

# Capture
image_path = f'/tmp/photo_{time.time()}.jpg'
picam.capture_file(image_path)

picam.stop()
```

**Why picamera2?**
- Pi Camera Module 3 requires libcamera (not supported by old picamera)
- picamera2 is the official replacement for Raspberry Pi OS Bookworm+

---

## 4. User Flow

```
1. [Idle State]
   ├─ LED: ON (ready indicator)
   └─ Buzzer: OFF

2. [Button Press Detected]
   └─ Call buttonPress()

3. [Countdown Sequence]
   ├─ Loop 4 times:
   │  ├─ LED ON + Buzzer ON (0.2s beep)
   │  ├─ LED OFF + Buzzer OFF
   │  └─ Wait 0.8s
   └─ Total: ~4 seconds

4. [Photo Capture]
   ├─ LED ON + Buzzer ON (flash simulation)
   ├─ Take photo at max resolution
   ├─ LED OFF + Buzzer OFF
   └─ Save image with timestamp

5. [Image Processing]
   ├─ Resize to 380×500 (thermal printer width)
   ├─ Save thumbnail
   └─ Print to thermal printer

6. [Return to Idle]
   └─ Working flag = 0 (ready for next photo)
```

**Concurrency Control**:
```python
Working = 0  # Global flag

def buttonPress(ev=None):
    global Working
    if Working == 0:  # Prevent re-entry
        Working = 1
        # ... do photo sequence
        Working = 0
```

**Prevents**:
- Multiple simultaneous captures
- Button spam causing queue buildup

---

## 5. Feedback System

### LED (Arcade Button Illumination)
```python
LedPin = 11  # GPIO 11

def ledOn():
    GPIO.output(LedPin, GPIO.LOW)  # Active LOW

def ledOff():
    GPIO.output(LedPin, GPIO.HIGH)
```

### Buzzer (Audible Feedback)
```python
BeepPin = 13  # GPIO 13
DisableBeep = False  # Global toggle

def beepOn():
    if DisableBeep == False:
        GPIO.output(BeepPin, GPIO.LOW)  # Active LOW

def beepOff():
    GPIO.output(BeepPin, GPIO.HIGH)
```

**Circuit Notes**:
- Both LED and buzzer use PNP transistor (S8550)
- Active LOW logic (GPIO LOW = device ON)
- 220Ω resistors for base current limiting

**ARTIFACT Equivalent**:
- LED feedback: Use WS2812B ticker LEDs (we have 384 LEDs!)
- Audio feedback: Use pygame.mixer for sound effects (no buzzer needed)

---

## Reusable Code Patterns for ARTIFACT

### 1. Event-Driven Photo Capture
```python
# In ARTIFACT's AI Prophet mode
def handle_button_press():
    if not self.capturing:
        self.capturing = True
        self.start_countdown()
        self.capture_photo()
        self.process_and_print()
        self.capturing = False
```

### 2. Countdown with Feedback
```python
# Use our existing display system
def countdown(self):
    for i in range(4, 0, -1):
        # Main display: Show number
        self.render_text(str(i), scale=4, center=True)
        
        # Ticker: Flash animation
        self.ticker.flash_color((255, 255, 0))
        
        # Audio: Beep sound
        pygame.mixer.Sound('beep.wav').play()
        
        time.sleep(1)
```

### 3. Image Resize for Thermal Printer
```python
from PIL import Image

def prepare_for_thermal(image_path):
    img = Image.open(image_path)
    
    # POS58 thermal printer: 384 dots/line at 203 DPI = ~58mm
    # Use 380px width to leave margins
    img.thumbnail((380, 500), Image.LANCZOS)
    
    # Convert to 1-bit for better dithering
    img_bw = img.convert('1')
    
    return img_bw
```

### 4. Thermal Printing Workflow
```python
from escpos.printer import Serial
from PIL import Image

def print_caricature(image_path, prediction_text):
    thermal = Serial(devfile='/dev/ttyAMA0', baudrate=9600)
    
    # Header
    thermal.set(align='center', bold=True, double_height=True)
    thermal.text('ARTIFACT\n')
    thermal.set(bold=False, double_height=False)
    thermal.text('AI Prophet\n\n')
    
    # Caricature image
    img = prepare_for_thermal(image_path)
    thermal.image(img)
    thermal.text('\n')
    
    # Prediction text
    thermal.set(align='left')
    thermal.text(prediction_text + '\n\n')
    
    # Footer
    thermal.set(align='center', bold=True)
    thermal.text(f'{datetime.now().strftime("%Y-%m-%d %H:%M")}\n')
    
    # Spacing for tear-off
    thermal.text('\n\n\n\n')
    
    thermal.cut()  # Auto-cut if supported
    thermal.close()
```

---

## Differences: raspi-photo-booth vs ARTIFACT

| Feature | raspi-photo-booth | ARTIFACT |
|---------|-------------------|----------|
| **Button Input** | GPIO 12 (hardware button) | USB HID keyboard (ENTER key) |
| **Camera** | Pi Camera V2 (picamera) | Pi Camera 3 NoIR (picamera2) |
| **Printer Port** | `/dev/usb/lp0` (USB) | `/dev/ttyAMA0` (UART) |
| **Display** | None | 128×128 LED matrix + ticker + LCD |
| **Feedback** | GPIO LED + buzzer | WS2812B LEDs + pygame audio |
| **Image Size** | 3280×2464 (8MP) | 4608×2592 (12MP) |
| **State Machine** | Simple flag (Working) | Full FSM with modes |
| **AI Integration** | None | Gemini (caricature + predictions) |

---

## Integration Recommendations for ARTIFACT

### HIGH PRIORITY

1. **Thermal Printer Module** (`src/artifact/printing/thermal.py`)
   ```python
   class ThermalPrinter:
       def __init__(self, port='/dev/ttyAMA0', baudrate=9600):
           self.printer = Serial(devfile=port, baudrate=baudrate)
       
       def print_receipt(self, image_path, text, header='ARTIFACT'):
           # Implementation based on patterns above
   ```

2. **Photo Capture Module** (`src/artifact/hardware/camera.py`)
   ```python
   class Camera:
       def __init__(self):
           self.picam = Picamera2()
           # Setup configuration
       
       def capture_photo(self, path):
           # Implementation with picamera2
       
       def capture_with_countdown(self, display_callback):
           # Show countdown on main display
   ```

3. **Photobooth Mode** (`src/artifact/modes/photobooth.py`)
   ```python
   class PhotoboothMode(BaseMode):
       def handle_button_press(self):
           if not self.capturing:
               self.run_photo_sequence()
       
       def run_photo_sequence(self):
           self.countdown()
           self.capture()
           self.print_receipt()
   ```

### MEDIUM PRIORITY

4. **Image Processing** (`src/artifact/graphics/image_processing.py`)
   - Dithering algorithms for thermal printer
   - Resize with aspect ratio preservation
   - 1-bit conversion with error diffusion

5. **Feedback System Integration**
   - Replace GPIO LED with WS2812B ticker animations
   - Replace buzzer with pygame sound effects
   - Unified feedback API for all modes

### LOW PRIORITY

6. **Testing on Hardware**
   - Test thermal printer with different image types
   - Verify print quality with dithering settings
   - Benchmark capture-to-print latency

---

## Code Snippets to Copy

### Concurrency Flag Pattern
```python
# Prevent button spam
self.capturing = False

def handle_button_press(self):
    if not self.capturing:
        self.capturing = True
        try:
            self.photo_sequence()
        finally:
            self.capturing = False
```

### Countdown Loop
```python
def countdown(self):
    for i in range(4, 0, -1):
        self.show_number(i)
        self.beep()
        time.sleep(1)
```

### Image Thumbnail for Printer
```python
img = Image.open(path)
img.thumbnail((380, 500), Image.LANCZOS)
img_bw = img.convert('1')  # Dithering
```

### Thermal Print with Line Feeds
```python
thermal.image(img)
thermal.text('\n\n\n\n\n')  # 5 line feeds
thermal.cut()
```

---

## Next Steps

1. Create `ThermalPrinter` class in `src/artifact/printing/thermal.py`
2. Implement picamera2 wrapper in `src/artifact/hardware/camera.py`
3. Add photobooth mode to `src/artifact/modes/photobooth.py`
4. Test thermal printing with sample images on Pi
5. Integrate countdown display with main 128×128 LED matrix

---

## References

- **Repository**: https://github.com/kriskbx/raspi-photo-booth
- **escpos-python docs**: https://python-escpos.readthedocs.io/
- **picamera2 docs**: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
- **ARTIFACT hardware specs**: `/Users/kirniy/dev/modular-arcade/CLAUDE.md`
