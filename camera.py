"""Camera auto-detection.

Priority: external USB webcam first, built-in laptop camera as fallback.

Many Windows laptops expose MORE than one camera: the normal webcam plus an
infrared (Windows Hello) camera. The IR camera delivers black or gray frames, which
is why a naive "pick any camera" gives a black screen. So every camera is checked:
  good  = real colour picture        (preferred)
  gray  = gray-only picture (IR cam) (last resort)
  black = black picture              (rejected)
Among the good cameras the highest index wins (a USB webcam gets a higher index than
the built-in one). With no USB webcam, the built-in camera is chosen.

Test it on its own:   python camera.py
"""
import os
import sys
import time

# must be set BEFORE importing cv2: quieter logs + much faster camera start on Windows
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2  # noqa: E402

import config  # noqa: E402

BLACK_LEVEL = 8      # average brightness (0-255) at or below this = black picture
GRAY_SPREAD = 2.0    # colour difference between channels below this = gray (IR) picture


def _backend_list():
    choice = str(getattr(config, "CAMERA_BACKEND", "auto")).lower()
    named = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "v4l2": cv2.CAP_V4L2, "any": cv2.CAP_ANY}
    if choice in named:
        return [(choice, named[choice])]
    if sys.platform.startswith("win"):
        return [("dshow", cv2.CAP_DSHOW), ("msmf", cv2.CAP_MSMF), ("any", cv2.CAP_ANY)]
    if sys.platform.startswith("linux"):
        return [("v4l2", cv2.CAP_V4L2), ("any", cv2.CAP_ANY)]
    return [("any", cv2.CAP_ANY)]


def _probe(index, backend):
    """Open a camera, let it warm up, and judge the picture. Returns None if it can't be opened."""
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return None
    frame = None
    for _ in range(30):                      # auto-exposure needs a moment: first frames are often black
        ok, f = cap.read()
        if ok and f is not None and f.size:
            frame = f
            if f.mean() > BLACK_LEVEL:
                break
        time.sleep(0.03)
    if frame is None:
        cap.release()
        return None
    brightness = float(frame.mean())
    if brightness <= BLACK_LEVEL:
        quality = "black"
    elif frame.ndim == 2:
        quality = "gray"
    else:
        b, g, r = cv2.split(frame)
        spread = (cv2.absdiff(b, g).mean() + cv2.absdiff(g, r).mean()) / 2
        quality = "gray" if spread < GRAY_SPREAD else "good"
    return cap, quality, brightness, frame


def scan():
    """Checks every camera index. Returns a list of dicts (cameras are released again)."""
    results = []
    for name, backend in _backend_list():
        for idx in range(config.CAMERA_SCAN_RANGE):
            p = _probe(idx, backend)
            if p is None:
                continue
            cap, quality, brightness, frame = p
            cap.release()
            results.append({"backend": name, "backend_id": backend, "index": idx,
                            "quality": quality, "brightness": brightness, "frame": frame})
        if any(r["quality"] == "good" for r in results):
            break                            # a backend that works - no need to try the others
    return results


def find_camera():
    """Returns (cap, description) or (None, error_message)."""
    # 1) A fixed index in config.py (CAMERA_INDEX = 0, 1, ...) is tried first
    if isinstance(config.CAMERA_INDEX, int):
        for name, backend in _backend_list():
            p = _probe(config.CAMERA_INDEX, backend)
            if p is None:
                continue
            cap, quality, _, _ = p
            if quality != "black":
                return cap, f"Camera {config.CAMERA_INDEX} ({name})"
            cap.release()

    # 2) Auto mode
    results = scan()
    pool = [r for r in results if r["quality"] == "good"] or [r for r in results if r["quality"] == "gray"]
    if not pool:
        if results:
            return None, ("Camera found but the picture is black. Check the camera privacy shutter / "
                          "camera key (Fn), and that no other app is using the camera.")
        return None, ("Camera not found. Check that no other app is using it and that camera access "
                      "is allowed (Windows: Settings > Privacy & security > Camera).")
    pick = max(pool, key=lambda r: r["index"]) if config.CAMERA_PREFER_EXTERNAL else min(pool, key=lambda r: r["index"])
    p = _probe(pick["index"], pick["backend_id"])
    if p is None:
        return None, f"Camera {pick['index']} could not be opened."
    goods = [r for r in pool if r["quality"] == "good"]
    kind = "external/USB camera" if (len(goods) > 1 and pick["index"] == max(r["index"] for r in goods)) \
        else "built-in camera"
    return p[0], f"Using {kind} (index {pick['index']}, {pick['backend']})"


if __name__ == "__main__":
    print("Scanning cameras (takes a few seconds)...\n")
    found = scan()
    if not found:
        print("No camera could be opened.")
    for r in found:
        print(f"backend={r['backend']:6} index={r['index']}  picture={r['quality']:5}  brightness={r['brightness']:.0f}")
        cv2.imwrite(f"camera_test_{r['backend']}_{r['index']}.jpg", r["frame"])
    if found:
        print("\nSaved camera_test_<backend>_<index>.jpg for each - open them to see which one is your real camera.")
    cap, info = find_camera()
    print("\nKiosk would use ->", info)
    if cap is not None:
        cap.release()