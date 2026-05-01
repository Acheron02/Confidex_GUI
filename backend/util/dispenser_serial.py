import glob
import threading
import time

try:
    import serial
except Exception:
    serial = None


BAUD_RATE = 9600
SERIAL_TIMEOUT = 20

_SERIAL_LOCK = threading.Lock()
_SERIAL_CONN = None
_SERIAL_PORT = None


def map_product_to_command(product_id="", product_name=""):
    from config_manager import config

    pid = str(product_id).strip()
    pname = str(product_name).strip().lower()

    # 1) Preferred: use synced booth config
    product = config.get_product_by_id(pid) if pid else None
    if product:
        slot = str(product.get("dispense_slot", "")).strip().upper()

        if slot == "KIT1":
            return "DISPENSE:KIT1\n", "KIT1"
        if slot == "KIT2":
            return "DISPENSE:KIT2\n", "KIT2"
        if slot == "KIT3":
            return "DISPENSE:KIT3\n", "KIT3"

    # 2) Backward-compatible fallback for older products
    pid_lower = pid.lower()
    if pid_lower in ("1", "kit1", "oral", "oralkit", "hiv123", "hiv"):
        return "DISPENSE:KIT1\n", "KIT1"

    if pid_lower in ("2", "kit2", "blood", "bloodkit", "dengue123", "dengue"):
        return "DISPENSE:KIT2\n", "KIT2"

    if pid_lower in ("3", "kit3", "urine", "urinekit"):
        return "DISPENSE:KIT3\n", "KIT3"

    if "oral" in pname or "hiv" in pname:
        return "DISPENSE:KIT1\n", "KIT1"

    if "blood" in pname or "dengue" in pname:
        return "DISPENSE:KIT2\n", "KIT2"

    if "urine" in pname:
        return "DISPENSE:KIT3\n", "KIT3"

    return None, None


def _find_arduino_port():
    candidates = []
    candidates.extend(sorted(glob.glob("/dev/ttyACM*")))
    candidates.extend(sorted(glob.glob("/dev/ttyUSB*")))

    if not candidates:
        raise RuntimeError(
            "No Arduino serial device found. Connect the Uno by USB and check /dev/ttyACM0 or /dev/ttyUSB0."
        )

    return candidates[0]


def _close_serial_locked():
    global _SERIAL_CONN, _SERIAL_PORT

    try:
        if _SERIAL_CONN and _SERIAL_CONN.is_open:
            _SERIAL_CONN.close()
    except Exception:
        pass

    _SERIAL_CONN = None
    _SERIAL_PORT = None


def close_serial_connection():
    with _SERIAL_LOCK:
        _close_serial_locked()


def _ensure_serial_locked(force_reopen=False):
    global _SERIAL_CONN, _SERIAL_PORT

    if serial is None:
        raise RuntimeError("pyserial is not installed. Install it with: pip install pyserial")

    port = _find_arduino_port()

    if force_reopen:
        _close_serial_locked()

    if _SERIAL_CONN and _SERIAL_CONN.is_open and _SERIAL_PORT == port:
        return _SERIAL_CONN

    _close_serial_locked()

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = BAUD_RATE
    ser.timeout = 1
    ser.write_timeout = 1
    ser.rtscts = False
    ser.dsrdtr = False
    ser.open()

    try:
        ser.setDTR(False)
    except Exception:
        pass

    time.sleep(3)

    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception:
        pass

    _SERIAL_CONN = ser
    _SERIAL_PORT = port

    print(f"[SERIAL] Connected to Arduino on {port}", flush=True)
    return _SERIAL_CONN


def _read_replies(ser, command, timeout):
    start = time.time()
    replies = []

    while time.time() - start < timeout:
        raw = ser.readline()
        if not raw:
            continue

        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            continue

        replies.append(line)
        print(f"[SERIAL] Reply: {line}", flush=True)

        upper = line.upper()

        if upper == "PONG":
            break

        if upper in ("BILL_STATUS:ON", "BILL_STATUS:OFF"):
            break

        if upper.startswith("DISPENSED:"):
            break

        if upper.startswith("CHANGE_DISPENSED:"):
            break

        if upper.startswith("ERROR:"):
            break

    return replies


def _send_command_and_collect(command, timeout=SERIAL_TIMEOUT):
    with _SERIAL_LOCK:
        last_error = None

        for attempt in range(2):
            try:
                ser = _ensure_serial_locked(force_reopen=(attempt == 1))

                try:
                    ser.reset_input_buffer()
                except Exception:
                    pass

                ser.write(command.encode("utf-8"))
                ser.flush()

                print(f"[SERIAL] Sent: {command.strip()}", flush=True)

                replies = _read_replies(ser, command, timeout)
                return replies

            except Exception as e:
                last_error = e
                print(f"[SERIAL] command attempt {attempt + 1} failed: {e}", flush=True)
                _close_serial_locked()
                time.sleep(0.5)

        print(f"[SERIAL] final failure sending {command.strip()}: {last_error}", flush=True)
        return []


def ping_arduino():
    replies = _send_command_and_collect("PING\n", timeout=3)

    for line in replies:
        if line.upper() == "PONG":
            return {
                "success": True,
                "message": "Arduino is reachable.",
                "replies": replies,
            }

    return {
        "success": False,
        "message": "No PONG reply received.",
        "replies": replies,
    }


def send_bill_on_command():
    replies = _send_command_and_collect("BILL_ON\n", timeout=3)

    for line in replies:
        upper = line.upper()

        if upper == "BUSY":
            return {
                "success": False,
                "message": "Arduino is busy.",
                "replies": replies,
            }

        if upper.startswith("ERROR:"):
            return {
                "success": False,
                "message": line,
                "replies": replies,
            }

        if upper == "BILL_STATUS:ON":
            return {
                "success": True,
                "message": line,
                "replies": replies,
            }

    return {
        "success": False,
        "message": "No BILL_STATUS:ON confirmation received.",
        "replies": replies,
    }


def send_bill_off_command():
    replies = _send_command_and_collect("BILL_OFF\n", timeout=3)

    for line in replies:
        upper = line.upper()

        if upper == "BUSY":
            return {
                "success": False,
                "message": "Arduino is busy.",
                "replies": replies,
            }

        if upper.startswith("ERROR:"):
            return {
                "success": False,
                "message": line,
                "replies": replies,
            }

        if upper == "BILL_STATUS:OFF":
            return {
                "success": True,
                "message": line,
                "replies": replies,
            }

    return {
        "success": False,
        "message": "No BILL_STATUS:OFF confirmation received.",
        "replies": replies,
    }


def _normalize_breakdown(breakdown: dict):
    normalized = {}

    if not isinstance(breakdown, dict):
        return normalized

    for key, value in breakdown.items():
        try:
            denom = int(key)
            qty = int(value)
        except Exception:
            continue

        if denom not in (20, 5, 1):
            continue

        if qty > 0:
            normalized[denom] = qty

    return normalized


def _build_change_command_payload(breakdown: dict):
    normalized = _normalize_breakdown(breakdown)
    ordered_denoms = [20, 5, 1]
    parts = []

    for denom in ordered_denoms:
        qty = normalized.get(denom, 0)
        if qty > 0:
            parts.append(f"{denom}x{qty}")

    return ",".join(parts), normalized


def _parse_change_dispensed_line(change_line: str):
    result = {}

    try:
        payload = change_line.split(":", 1)[1].strip()
    except Exception:
        return result

    if not payload or payload == "0":
        return result

    parts = [p.strip() for p in payload.split(",") if p.strip()]
    for part in parts:
        if "x" not in part:
            continue

        left, right = part.split("x", 1)
        try:
            denom = int(left.strip())
            qty = int(right.strip())
        except Exception:
            continue

        if denom in (20, 5, 1) and qty > 0:
            result[denom] = qty

    return result

def send_raw_command(command: str, timeout=5):
    """
    Send a raw command to Arduino using the existing serial pipeline.
    """
    if not command.endswith("\n"):
        command = command + "\n"

    replies = _send_command_and_collect(command, timeout=timeout)

    if not replies:
        return {
            "success": False,
            "message": "No reply from Arduino",
            "replies": [],
        }

    return {
        "success": True,
        "message": replies[-1],
        "replies": replies,
    }


def _estimate_change_timeout(normalized: dict) -> int:
    """
    Estimate how long the Arduino will need.
    Uses generous values so the Pi does not give up too early.
    """
    count20 = int(normalized.get(20, 0))
    count5 = int(normalized.get(5, 0))
    count1 = int(normalized.get(1, 0))

    # Conservative estimates in seconds per coin
    sec_per_20 = 5.5
    sec_per_5 = 4.0
    sec_per_1 = 3.5

    base = 8.0
    group_pause = 2.0

    groups = 0
    if count20 > 0:
        groups += 1
    if count5 > 0:
        groups += 1
    if count1 > 0:
        groups += 1

    estimated = (
        base
        + (count20 * sec_per_20)
        + (count5 * sec_per_5)
        + (count1 * sec_per_1)
        + max(0, groups - 1) * group_pause
    )

    # Add margin
    estimated += 8.0

    # Never too short
    return max(20, int(round(estimated)))


def send_change_command(breakdown: dict):
    command_payload, normalized = _build_change_command_payload(breakdown)

    if not normalized:
        return {
            "success": False,
            "message": "Invalid or empty change breakdown.",
            "requested_breakdown": {},
            "confirmed_breakdown": {},
            "replies": [],
        }

    timeout = _estimate_change_timeout(normalized)

    replies = _send_command_and_collect(
        f"DISPENSE_CHANGE:{command_payload}\n",
        timeout=timeout
    )

    got_ok = False
    change_line = None
    error_line = None
    busy = False

    for line in replies:
        upper = line.upper()

        if upper == "OK":
            got_ok = True
        elif upper == "BUSY":
            busy = True
        elif upper.startswith("CHANGE_DISPENSED:"):
            change_line = line
        elif upper.startswith("ERROR:"):
            error_line = line

    if busy:
        return {
            "success": False,
            "message": "Arduino is busy.",
            "requested_breakdown": normalized,
            "confirmed_breakdown": {},
            "replies": replies,
        }

    if error_line:
        return {
            "success": False,
            "message": error_line,
            "requested_breakdown": normalized,
            "confirmed_breakdown": {},
            "replies": replies,
        }

    if change_line:
        confirmed = _parse_change_dispensed_line(change_line)

        if confirmed != normalized:
            return {
                "success": False,
                "message": (
                    f"Arduino confirmed a different breakdown. "
                    f"Requested={normalized}, Confirmed={confirmed}"
                ),
                "requested_breakdown": normalized,
                "confirmed_breakdown": confirmed,
                "replies": replies,
            }

        return {
            "success": True,
            "message": change_line,
            "requested_breakdown": normalized,
            "confirmed_breakdown": confirmed,
            "replies": replies,
        }

    if got_ok:
        return {
            "success": False,
            "message": "Command accepted, but no final CHANGE_DISPENSED confirmation was received.",
            "requested_breakdown": normalized,
            "confirmed_breakdown": {},
            "replies": replies,
        }

    return {
        "success": False,
        "message": "No valid change response received from Arduino.",
        "requested_breakdown": normalized,
        "confirmed_breakdown": {},
        "replies": replies,
    }


def send_dispense_command(product_id="", product_name=""):
    command, expected_kit = map_product_to_command(
        product_id=product_id,
        product_name=product_name
    )

    if not command or not expected_kit:
        return {
            "success": False,
            "message": f"Unknown product mapping. product_id={product_id}, product_name={product_name}",
            "replies": [],
        }

    replies = _send_command_and_collect(command, timeout=SERIAL_TIMEOUT)

    got_ok = False
    dispensed_line = None
    error_line = None
    busy = False

    for line in replies:
        upper = line.upper()

        if upper == "OK":
            got_ok = True
        elif upper == "BUSY":
            busy = True
        elif upper.startswith("DISPENSED:"):
            dispensed_line = line
        elif upper.startswith("ERROR:"):
            error_line = line

    if busy:
        return {
            "success": False,
            "message": "Arduino is busy dispensing another operation.",
            "replies": replies,
        }

    if error_line:
        return {
            "success": False,
            "message": error_line,
            "replies": replies,
        }

    if dispensed_line:
        actual_kit = dispensed_line.split(":", 1)[1].strip().upper()
        if actual_kit != expected_kit:
            return {
                "success": False,
                "message": f"Arduino dispensed {actual_kit}, but expected {expected_kit}.",
                "replies": replies,
            }

        return {
            "success": True,
            "message": dispensed_line,
            "replies": replies,
        }

    if got_ok:
        return {
            "success": False,
            "message": f"Command accepted for {expected_kit}, but no final DISPENSED confirmation was received.",
            "replies": replies,
        }

    return {
        "success": False,
        "message": "No valid dispense response received from Arduino.",
        "replies": replies,
    }