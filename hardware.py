"""Locker hardware layer.

SIMULATE_HARDWARE = True  -> everything is simulated (doors just print to the console,
                             the IR sensor is a button on the return screen).

To go real: set SIMULATE_HARDWARE = False in config.py and fill in the two TODO
spots below (Arduino over serial, GPIO relay board, USB relay, etc.).
"""
import config

_sim_present = {}   # (item_name, compartment_no) -> bool  (simulated IR sensor)

# Fill this in later: which relay/lock and which IR sensor belongs to each compartment.
DOOR_MAP = {
    # ("Basketball", 1): {"lock_channel": 1, "ir_channel": 1},
    # ("Basketball", 2): {"lock_channel": 2, "ir_channel": 2},
}


def open_compartment(item_name, compartment_no):
    """Unlock the door of this compartment."""
    print(f"[HW] OPEN  {item_name} - compartment {compartment_no}")
    if config.SIMULATE_HARDWARE:
        return True
    # TODO: send the unlock signal using DOOR_MAP[(item_name, compartment_no)]
    print("[HW] Real hardware not implemented yet (open_compartment)")
    return False


def item_present(item_name, compartment_no):
    """Optical IR proximity sensor: True when an object is inside the compartment."""
    if config.SIMULATE_HARDWARE:
        return _sim_present.get((item_name, compartment_no), False)
    # TODO: read the IR sensor of this compartment (many IR modules output LOW when an object is detected)
    return False


def set_sim_present(item_name, compartment_no, present):
    """Only used by the simulation buttons on the kiosk screen."""
    if config.SIMULATE_HARDWARE:
        _sim_present[(item_name, compartment_no)] = present
