# Momentobooth Analysis for ARTIFACT Integration

**Date**: 2025-12-27
**Repository**: https://github.com/momentobooth/momentobooth
**License**: Open Source (check LICENSE file)

## Executive Summary

Momentobooth is a cross-platform photobooth application built with Flutter/Dart frontend and Rust backend. Key features relevant to ARTIFACT:

1. **Photo Sharing via QR Code** - Uses ffsend (Firefox Send) to upload photos and generate QR codes
2. **Camera Support** - Webcam (Nokhwa) + DSLR (libgphoto2) integration
3. **Thermal Printing** - PDF generation and printing via CUPS/Flutter Printing

## Technology Stack

### Frontend
- **Language**: Dart 3.10+
- **Framework**: Flutter 3.38.0+ (desktop app, not mobile)
- **UI Kit**: fluent_ui (Windows Fluent Design)
- **Routing**: go_router
- **State Management**: MobX + Freezed
- **QR Code**: `pretty_qr_code` package

### Backend
- **Language**: Rust (2024 edition)
- **FFI Bridge**: flutter_rust_bridge 2.11.1
- **Camera**: Nokhwa (webcam), libgphoto2 (DSLR)
- **File Sharing**: ffsend-api 0.7.3 (Firefox Send client)
- **Printing**: ipp (Internet Printing Protocol), CUPS

### Key Dependencies (Rust)
```toml
ffsend-api = "0.7.3"           # Firefox Send file upload
nokhwa = "0.10"                # Webcam capture
gphoto2 = "3.4.1"              # DSLR camera control
ipp = "5.3.2"                  # Printing via IPP/CUPS
image = "0.25.9"               # Image processing
jpeg-encoder = "0.6.1"         # JPEG encoding
```

## 1. Photo Sharing via QR Code (ffsend)

### How It Works

**Flow**: Photo → Upload to Firefox Send → Get download URL → Generate QR Code → Display

**File**: `rust/src/utils/ffsend_client.rs`

```rust
pub fn upload_file(
    host_url: String,
    file_path: String,
    download_filename: Option<String>,
    max_downloads: Option<u8>,
    expires_after_seconds: Option<u32>,
    update_sink: StreamSink<FfSendTransferProgress>,
    control_command_timeout: Duration,
    transfer_timeout: Duration
)
```

**Key Features**:
- Uploads photo to Firefox Send server (default: https://send.vis.ee or custom)
- Returns download URL + expiration date
- Supports progress tracking via StreamSink
- Configurable max downloads and expiration time
- Can delete uploaded files via `delete_file(file_id)`

**UI Implementation**: `lib/views/photo_booth_screen/screens/share_screen/`

```dart
// Upload photo and get URL
Future<void> uploadPhotoToSend() async {
  Stream<FfSendTransferProgress> stream = ffsendUploadFile(
    filePath: file.path,
    hostUrl: ffSendUrl,
    downloadFilename: filename,
    controlCommandTimeout: timeout,
    transferTimeout: timeout,
  );

  stream.listen((event) {
    if (event.isFinished) {
      _qrUrl = event.downloadUrl;  // Use this for QR code
    } else {
      _uploadProgress = event.transferredBytes / event.totalBytes;
    }
  });
}
```

**QR Code Generation**: `lib/views/components/qr_code.dart`

```dart
import 'package:pretty_qr_code/pretty_qr_code.dart';

PrettyQrView.data(
  data: downloadUrl,  // The URL from ffsend
  errorCorrectLevel: QrErrorCorrectLevel.L,
  decoration: const PrettyQrDecoration(
    shape: PrettyQrSmoothSymbol(roundFactor: 1),
  ),
)
```

### Firefox Send Servers

**Default**: https://send.vis.ee (community-run)

**Self-Hosted**: Can deploy own server using https://github.com/timvisee/send

**Configuration**: User-configurable in settings

### Adaptation for ARTIFACT

**What We Need**:
1. Python port of ffsend-api (already exists: https://github.com/ehuggett/ffsend)
2. QR code generation library for Python (qrcode + PIL)
3. Display QR code on 128x128 LED matrix

**Implementation Strategy**:

```python
# 1. Install ffsend Python client
# pip install ffsend

# 2. Upload photo
from ffsend import upload
url = upload(photo_path, host="https://send.vis.ee")

# 3. Generate QR code
import qrcode
qr = qrcode.QRCode(version=1, box_size=2, border=1)
qr.add_data(url)
qr.make(fit=True)
img = qr.make_image(fill_color="white", back_color="black")

# 4. Display on 128x128 LED matrix
# Convert PIL image to numpy array and render
```

**UI Flow for ARTIFACT**:
```
┌─────────────────────────────┐
│  PHOTO CAPTURED!            │
│                             │
│  [SHARE VIA QR] [PRINT]     │
└─────────────────────────────┘
         ↓ (Share pressed)
┌─────────────────────────────┐
│  UPLOADING...               │
│  [████████░░░░] 65%         │
└─────────────────────────────┘
         ↓ (Upload complete)
┌─────────────────────────────┐
│  ┌─────────────────┐         │
│  │ █▀▀▀█ ▄▀█ █▀▀▀█│         │
│  │ █   █ ▀▀▀ █   █│  SCAN   │
│  │ █▄▄▄█ █▀█ █▄▄▄█│  ME!    │
│  └─────────────────┘         │
│                             │
│  Expires in 24h             │
│  [DONE] [REPRINT]           │
└─────────────────────────────┘
```

## 2. Camera Integration

### Webcam (Nokhwa)

**File**: `rust/src/hardware_control/live_view/nokhwa.rs`

**Features**:
- Cross-platform webcam access
- Live view streaming
- Frame capture
- Image processing pipeline

**API**:
```rust
nokhwa_initialize()                           // Init camera system
nokhwa_get_cameras() -> Vec<NokhwaCameraInfo> // List cameras
nokhwa_open_camera(name, operations, texture_ptr) -> u32
nokhwa_get_last_frame(handle_id) -> Option<RawImage>
nokhwa_close_camera(handle_id)
```

**Python Equivalent**: We already use picamera2 for Pi Camera, which is better suited for our hardware.

### DSLR Camera (libgphoto2)

**File**: `rust/src/api/gphoto2.rs`

**Features**:
- DSLR camera control over USB
- Live view support
- Autofocus
- Photo capture
- Event handling

**Not Needed for ARTIFACT**: We use Pi Camera, not DSLR.

## 3. Thermal Printing

### Architecture

**Manager**: `lib/managers/printing_manager.dart`

**Backends**:
1. **Flutter Printing** (`printing` package) - Cross-platform PDF printing
2. **CUPS Client** (Rust + IPP protocol) - Direct CUPS integration for Linux/macOS

**File**: `lib/hardware_control/printing/`

### How It Works

**Flow**: Photo → Generate PDF → Print via CUPS/Flutter Printing

```dart
// 1. Generate PDF from photo
final pdfData = await PhotosManager.getOutputPDF(size);

// 2. Print PDF
await PrintingManager.printPdf(
  jobName: "MomentoBooth Picture",
  pdfData: pdfData,
  copies: 1,
  printSize: PrintSize.normal
);
```

**PDF Generation**: Uses `pdf` and `printing` packages to create printable layout.

### Adaptation for ARTIFACT

**What We Need**:
1. Python CUPS client (already have: python-escpos for thermal printer)
2. PDF generation (reportlab or PIL)
3. Layout templates for thermal printer

**Implementation Strategy**:

```python
# We already have thermal printer support via python-escpos
from escpos.printer import Serial

printer = Serial('/dev/ttyAMA0', baudrate=19200)

# Generate thermal receipt
printer.set(align='center')
printer.image(photo_path)  # Print dithered photo
printer.text("\n")
printer.text("ARTIFACT\n")
printer.text("Prediction: [AI text]\n")
printer.text(f"Date: {datetime.now()}\n")
printer.text("\n")
printer.qr(download_url, size=6)  # Print QR code
printer.cut()
```

**Note**: Momentobooth uses PDF printing for full-size photo prints on paper printers. We use thermal printers, so we stick with python-escpos (already implemented).

## 4. User Flow Analysis

### Momentobooth Flow
```
Start Screen
    ↓ (Tap to start)
Single Capture / Multi Capture
    ↓ (Take photo)
Collage Maker (if multi-capture)
    ↓ (Confirm)
Share Screen
    ├─ Print Button → Print Dialog → Print
    ├─ QR Button → Upload → QR Dialog → Display QR
    └─ Retake/Change Button → Back to capture
    ↓ (Next)
Start Screen (loop)
```

### Proposed ARTIFACT Photobooth Mode Flow
```
Idle Screen
    ↓ (Button press)
"POSE FOR CAMERA"
    ↓ (3-2-1 countdown)
📸 CAPTURE
    ↓
Preview Screen
    ├─ [RETAKE]  → Back to pose
    ├─ [SHARE]   → Upload → Display QR
    └─ [PRINT]   → Print thermal receipt
    ↓ (Auto-return after 30s)
Idle Screen
```

## 5. Key Takeaways for ARTIFACT

### ✅ What We Can Use Directly

1. **ffsend Integration Pattern**
   - Use Python ffsend client: https://github.com/ehuggett/ffsend
   - Upload photo to Firefox Send
   - Get download URL
   - Display as QR code on LED matrix

2. **QR Code Generation**
   - Use Python `qrcode` library
   - Render QR code at appropriate size for 128x128 display
   - High contrast (white on black) for LED visibility

3. **User Flow Inspiration**
   - Simple pose → capture → preview → share/print → done flow
   - Progress indicators during upload
   - Error handling for failed uploads

### ❌ What We Don't Need

1. **Flutter/Dart Stack** - We're Python-based
2. **DSLR Camera Support** - We use Pi Camera
3. **PDF Printing** - We use thermal printer (python-escpos)
4. **Desktop UI Framework** - We have custom pygame UI

### 🔧 What We Need to Build

1. **Python ffsend Integration**
   ```python
   from ffsend import upload, download

   class PhotoShareService:
       def __init__(self, server_url="https://send.vis.ee"):
           self.server_url = server_url

       def upload_photo(self, photo_path: str) -> str:
           """Upload photo and return download URL"""
           url = upload(photo_path, host=self.server_url)
           return url

       def generate_qr(self, url: str) -> np.ndarray:
           """Generate QR code as 128x128 numpy array"""
           import qrcode
           qr = qrcode.QRCode(version=1, box_size=2, border=1)
           qr.add_data(url)
           qr.make(fit=True)
           img = qr.make_image(fill_color="white", back_color="black")
           # Convert to numpy array for LED display
           return np.array(img.resize((128, 128)))
   ```

2. **Photobooth Mode for ARTIFACT**
   - New mode in `src/artifact/modes/photobooth.py`
   - Phases: POSE → COUNTDOWN → CAPTURE → PREVIEW → SHARE/PRINT
   - Integration with CameraService
   - QR code display on main 128x128 LED
   - Thermal receipt printing with QR code

3. **Thermal Printer Receipt Layout**
   ```
   ┌────────────────────────┐
   │                        │
   │    [PHOTO (dithered)]  │
   │                        │
   ├────────────────────────┤
   │      A R T I F A C T   │
   │                        │
   │  Prediction: "..."     │
   │  Date: 2025-12-27      │
   │                        │
   │  ┌──────────────┐      │
   │  │ QR CODE HERE │      │
   │  │ (download)   │      │
   │  └──────────────┘      │
   │                        │
   │  Scan to view/share    │
   └────────────────────────┘
   ```

## 6. Implementation Roadmap

### Phase 1: Basic Photobooth Mode
- [ ] Create `PhotoboothMode` class
- [ ] Implement POSE → COUNTDOWN → CAPTURE flow
- [ ] Show preview on 128x128 LED
- [ ] Add [RETAKE] [CONTINUE] buttons

### Phase 2: Photo Sharing
- [ ] Install Python ffsend client
- [ ] Implement photo upload to Firefox Send
- [ ] Generate QR code from download URL
- [ ] Display QR code on LED matrix
- [ ] Add upload progress indicator

### Phase 3: Thermal Printing
- [ ] Design thermal receipt layout
- [ ] Add photo dithering for thermal printer
- [ ] Print receipt with QR code
- [ ] Test thermal print quality

### Phase 4: Polish
- [ ] Add error handling for failed uploads
- [ ] Add timeout for QR display (return to idle)
- [ ] Add sound effects for capture
- [ ] Test full flow end-to-end

## 7. Dependencies to Add

```bash
# Python packages
pip install ffsend        # Firefox Send client
pip install qrcode[pil]   # QR code generation with PIL
pip install pillow        # Image processing
```

## 8. Configuration

Add to ARTIFACT config (if needed):

```python
PHOTOBOOTH_CONFIG = {
    "ffsend_server": "https://send.vis.ee",
    "upload_timeout": 60,  # seconds
    "qr_display_time": 30,  # seconds before auto-return to idle
    "max_downloads": 10,  # max downloads for shared photo
    "expire_after": 86400,  # 24 hours in seconds
}
```

## Conclusion

Momentobooth provides excellent reference architecture for:
1. **Firefox Send integration** - Well-tested Rust implementation we can port to Python
2. **QR code sharing** - Simple and effective user flow
3. **Printing workflows** - Though we adapt for thermal printer instead of PDF

The key insight is using **Firefox Send** (ffsend) as a free, privacy-respecting file sharing service that generates temporary download URLs perfect for QR codes. This is much simpler than building our own upload server.

**Next Steps**: Start with Phase 1 (basic photobooth mode) and integrate with existing ARTIFACT camera and display systems.
