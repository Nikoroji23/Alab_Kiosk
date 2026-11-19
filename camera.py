"""Camera auto-detection.

Priority: external USB webcam first, built-in laptop camera as fallback.
Laptops list the built-in camera as the LOWEST index (0); a USB webcam that is
plugged in shows up with a HIGHER index. So with CAMERA_INDEX = "auto" we scan
all working cameras and pick the highest index (= the USB webcam if present,
otherwise the only camera = the built-in one).

Test it on its own:   python camera.py
"""
import sys

import cv2

import config


def _backends():
    if sys.platform.startswith("win"):
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]   # DSHOW first (fast), then fallbacks
    if sys.platform.startswith("linux"):
        return [cv2.CAP_V4L2, cv2.CAP_ANY]
    return [cv2.CAP_ANY]


def _open_working(index, backend):
    """Open a camera and make sure it really delivers frames (skips metadata/virtual devices)."""
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return None
    for _ in range(15):               # some cameras need a few reads to warm up
        ok, frame = cap.read()
        if ok and frame is not None and frame.size > 0:
            return cap
    cap.release()
    return None


def list_cameras():
    """Returns (backend, [working indexes]) for the first backend that finds any camera."""
    for backend in _backends():
        found = []
        for idx in range(config.CAMERA_SCAN_RANGE):
            cap = _open_working(idx, backend)
            if cap is not None:
                found.append(idx)
                cap.release()
        if found:
            return backend, found
    return None, []


def find_camera():
    """Returns (cap, description) or (None, error_message)."""
    # 1) A fixed index in config.py (CAMERA_INDEX = 1, ...) is tried first
    if isinstance(config.CAMERA_INDEX, int):
        for backend in _backends():
            cap = _open_working(config.CAMERA_INDEX, backend)
            if cap is not None:
                return cap, f"Camera {config.CAMERA_INDEX}"

    # 2) Auto mode: pick USB webcam if present, otherwise the built-in camera
    backend, found = list_cameras()
    if not found:
        return None, ("Camera not found. Check that no other app is using it and that camera "
                      "access is allowed (Windows: Settings > Privacy & security > Camera).")
    index = max(found) if config.CAMERA_PREFER_EXTERNAL else min(found)
    cap = _open_working(index, backend)
    if cap is None:
        return None, f"Camera {index} could not be opened."
    kind = "external/USB camera" if (len(found) > 1 and index == max(found)) else "built-in camera"
    return cap, f"Using {kind} (index {index})"


if __name__ == "__main__":
    backend, found = list_cameras()
    print("Working camera indexes:", found)
    cap, info = find_camera()
    print(info)
    if cap is not None:
        ok, frame = cap.read()
        if ok:
            cv2.imwrite("camera_test.jpg", frame)
            print("Saved camera_test.jpg - open it to check the picture.")
        cap.release()