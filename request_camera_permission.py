#!/usr/bin/env python3
"""
Request camera permission on macOS Tahoe (26+).

This script uses multiple methods to trigger the camera permission dialog:
1. AVFoundation via PyObjC (most reliable on Tahoe)
2. OpenCV fallback

IMPORTANT: Run this script using the SAME Python interpreter as the simulator:
    .venv/bin/python request_camera_permission.py

This ensures that the "Python" app in System Settings > Privacy gets the permission,
not Terminal.app. Each macOS app has its own camera permission entry.
"""

import sys
import time
import subprocess

def check_pyobjc():
    """Check if PyObjC is available."""
    try:
        import objc
        import AVFoundation
        return True
    except ImportError:
        return False

def request_via_avfoundation():
    """Request camera using AVFoundation (most reliable on macOS Tahoe)."""
    try:
        import objc
        import AVFoundation
        from Foundation import NSRunLoop, NSDate

        print("Using AVFoundation to request camera permission...")

        # Request authorization
        auth_status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeVideo
        )

        status_names = {
            0: "Not Determined",
            1: "Restricted",
            2: "Denied",
            3: "Authorized"
        }

        print(f"Current authorization status: {status_names.get(auth_status, 'Unknown')}")

        if auth_status == 0:  # Not Determined
            print("Requesting permission... (dialog should appear)")

            # This will trigger the permission dialog
            result = [None]
            def callback(granted):
                result[0] = granted

            AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                AVFoundation.AVMediaTypeVideo,
                callback
            )

            # Run the run loop to process the callback
            end_date = NSDate.dateWithTimeIntervalSinceNow_(5.0)
            while result[0] is None:
                NSRunLoop.currentRunLoop().runMode_beforeDate_(
                    "kCFRunLoopDefaultMode",
                    end_date
                )
                if NSDate.date().compare_(end_date) == 1:  # Past end date
                    break

            if result[0]:
                print("✅ Camera permission GRANTED via AVFoundation!")
                return True
            else:
                print("❌ Camera permission DENIED via AVFoundation")
                return False

        elif auth_status == 3:  # Authorized
            print("✅ Camera already authorized!")
            return True
        elif auth_status == 2:  # Denied
            print("❌ Camera access DENIED in System Settings")
            print("   → Go to System Settings > Privacy & Security > Camera")
            print("   → Enable access for Terminal (or your IDE)")
            return False
        else:  # Restricted
            print("⚠️ Camera access is restricted (parental controls?)")
            return False

    except Exception as e:
        print(f"AVFoundation error: {e}")
        return None

def request_via_opencv():
    """Request camera using OpenCV (fallback method)."""
    try:
        import cv2
    except ImportError:
        print("OpenCV not installed - skipping fallback")
        return None

    print("Using OpenCV to request camera permission...")

    cap = cv2.VideoCapture(0)
    time.sleep(1)  # Give time for dialog

    if cap.isOpened():
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            print("✅ Camera access granted via OpenCV!")
            print(f"   Frame: {frame.shape[1]}x{frame.shape[0]}")
            return True
        else:
            print("⚠️ Camera opened but no frames")
            return False
    else:
        print("❌ OpenCV could not open camera")
        return False

def main():
    print("=" * 60)
    print("ARTIFACT Camera Permission Request (macOS Tahoe)")
    print("=" * 60)
    print()

    # Check if running from Terminal
    import os
    parent = os.environ.get('TERM_PROGRAM', 'Unknown')
    print(f"Running from: {parent}")
    print()

    # Try AVFoundation first (more reliable on Tahoe)
    if check_pyobjc():
        result = request_via_avfoundation()
        if result is True:
            print()
            print("🎉 SUCCESS! You can now use the camera in ARTIFACT.")
            return
        elif result is False:
            pass  # Continue to show help
    else:
        print("PyObjC not installed - trying OpenCV directly")
        print("(For best results: pip install pyobjc-framework-AVFoundation)")
        print()

    # Fallback to OpenCV
    result = request_via_opencv()

    if result is True:
        print()
        print("🎉 SUCCESS! You can now use the camera in ARTIFACT.")
    else:
        print()
        print("=" * 60)
        print("TROUBLESHOOTING")
        print("=" * 60)
        print()
        print("If the permission dialog never appeared:")
        print()
        print("1. Reset camera permissions (run in Terminal):")
        print("   tccutil reset Camera")
        print()
        print("2. Then run this script again")
        print()
        print("3. If still not working, manually add Terminal:")
        print("   System Settings > Privacy & Security > Camera")
        print("   Click '+' and add /Applications/Utilities/Terminal.app")
        print()
        print("4. For VS Code/Cursor, add those apps instead")
        print()

    print("=" * 60)

if __name__ == "__main__":
    main()
