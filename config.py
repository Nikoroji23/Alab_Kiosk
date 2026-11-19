"""Central settings for the Sports Equipment Locker kiosk + admin panel."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "kiosk.db")
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")

# ---------------- Hardware ----------------
SIMULATE_HARDWARE = True      # True = on-screen simulation. Set False once real hardware code is in hardware.py
CAMERA_INDEX = "auto"         # "auto" = USB webcam if plugged in, otherwise the built-in laptop camera
                              # or force one with a number, e.g. 0 or 1
CAMERA_PREFER_EXTERNAL = True # auto mode: prefer the external (higher index) camera
CAMERA_SCAN_RANGE = 5         # auto mode: how many camera indexes to check (0..4)
CAPTURE_COUNTDOWN = 5         # seconds the borrower gets to pose after tapping CAPTURE
SKIP_CAMERA_FOR_TESTING = False  # True = skip face capture (only for testing without a webcam)
RETURN_TIMEOUT_SECONDS = 60   # how long to wait for the IR sensor to see the returned item

# ---------------- Kiosk rules ----------------
STUDENT_NUMBER_LENGTH = 10    # e.g. 2023200742

DEPARTMENTS = [               # EDIT to match your campus
    "Computer Engineering",
    "Information Technology",
    "Industrial Technology",
    "Education",
    "Business Admin",
    "Other",
]
YEAR_LEVELS = ["1st Year", "2nd Year", "3rd Year", "4th Year"]

# (item name, compartment number). Numbering is per item:
# Basketball 1, Basketball 2, Volleyball 1, Volleyball 2 ...
# This list is only used to create the database the FIRST time.
# After that, the 'compartments' table in kiosk.db is the source of truth.
COMPARTMENTS = [
    ("Volleyball", 1), ("Volleyball", 2),
    ("Basketball", 1), ("Basketball", 2),
    ("Chess Board", 1), ("Chess Board", 2),
    ("Arnis", 1),
    ("Badminton", 1),
    ("Cone", 1),
]

# ---------------- Admin panel ----------------
ADMIN_HOST = "127.0.0.1"      # use "0.0.0.0" to open the admin page from other PCs on the network
ADMIN_PORT = 5001
ADMIN_PASSWORD = "admin123"   # CHANGE THIS
SECRET_KEY = "change-this-secret-key"