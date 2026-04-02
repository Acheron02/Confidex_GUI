import time
import glob
import threading

try:
    import serial
except Exception:
    serial = None


BAUD_RATE = 9600
SERIAL_TIMEOUT = 15

_SERIAL_LOCK = threading.Lock()
_SERIAL_CONN = None
_SERIAL_PORT = None


def map_product_to_command(product_id="", product_name=""):
    pid = str(product_id).strip().lower()
    pname = str(product_name).strip().lower()

    if pid in ("1", "kit1", "oral", "oralkit", "hiv123", "hiv"):
        return "DISPENSE:KIT1\n", "KIT1"

    if pid in ("2", "kit2", "blood", "bloodkit", "dengue123", "dengue"):
        return "DISPENSE:KIT2\n", "KIT2"

    if pid in ("3", "kit3", "urine", "urinekit"):
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
            continue

        if upper.startswith("ERROR:"):
            if "DISPENSE_CHANGE:" not in command:
                break
            continue

        if upper.startswith("COIN_STATUS:") and (
            "GET_COIN_STATUS" in command or "DISPENSE_CHANGE:" in command
        ):
            break

        if upper.startswith("COIN_STOCK:") and "GET_COIN_STOCK" in command:
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


def _parse_coin_stock_line(stock_line):
    stock = {}
    raw = stock_line.split(":", 1)[1]
    parts = raw.split(",")

    for part in parts:
        denom, count = part.split("=")
        stock[int(denom.strip())] = int(count.strip())

    return stock


def _parse_coin_status_line(status_line):
    raw = status_line.split(":", 1)[1]
    parts = raw.split(",")

    data = {}
    for part in parts:
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key == "restock":
            data[key] = [] if value == "NONE" else [int(v) for v in value.split("+")]
        else:
            data[key] = int(value)

    return data


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


def get_coin_stock():
    replies = _send_command_and_collect("GET_COIN_STOCK\n", timeout=3)

    stock_line = None
    for line in replies:
        if line.upper().startswith("COIN_STOCK:"):
            stock_line = line
            break

    if not stock_line:
        return {
            "success": False,
            "message": "No coin stock response received.",
            "stock": {},
            "replies": replies,
        }

    try:
        stock = _parse_coin_stock_line(stock_line)
        return {
            "success": True,
            "message": "Coin stock received.",
            "stock": stock,
            "replies": replies,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to parse coin stock: {e}",
            "stock": {},
            "replies": replies,
        }


def get_coin_status():
    replies = _send_command_and_collect("GET_COIN_STATUS\n", timeout=3)

    status_line = None
    for line in replies:
        if line.upper().startswith("COIN_STATUS:"):
            status_line = line
            break

    if not status_line:
        return {
            "success": False,
            "message": "No coin status response received.",
            "status": {},
            "replies": replies,
        }

    try:
        status = _parse_coin_status_line(status_line)
        return {
            "success": True,
            "message": "Coin status received.",
            "status": status,
            "replies": replies,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to parse coin status: {e}",
            "status": {},
            "replies": replies,
        }


def send_change_command(amount):
    try:
        amount = int(amount)
    except Exception:
        return {
            "success": False,
            "message": "Invalid change amount.",
            "replies": [],
        }

    if amount <= 0:
        return {
            "success": False,
            "message": "Change amount must be greater than zero.",
            "replies": [],
        }

    replies = _send_command_and_collect(f"DISPENSE_CHANGE:{amount}\n", timeout=SERIAL_TIMEOUT)

    got_ok = False
    change_line = None
    error_line = None
    stock_line = None
    status_line = None
    busy = False

    for line in replies:
        upper = line.upper()

        if upper == "OK":
            got_ok = True
        elif upper == "BUSY":
            busy = True
        elif upper.startswith("CHANGE_DISPENSED:"):
            change_line = line
        elif upper.startswith("COIN_STOCK:"):
            stock_line = line
        elif upper.startswith("COIN_STATUS:"):
            status_line = line
        elif upper.startswith("ERROR:"):
            error_line = line

    stock = {}
    status = {}

    if stock_line:
        try:
            stock = _parse_coin_stock_line(stock_line)
        except Exception:
            stock = {}

    if status_line:
        try:
            status = _parse_coin_status_line(status_line)
        except Exception:
            status = {}

    if busy:
        return {
            "success": False,
            "message": "Arduino is busy.",
            "stock": stock,
            "status": status,
            "replies": replies,
        }

    if error_line:
        return {
            "success": False,
            "message": error_line,
            "stock": stock,
            "status": status,
            "replies": replies,
        }

    if change_line:
        return {
            "success": True,
            "message": change_line,
            "stock": stock,
            "status": status,
            "replies": replies,
        }

    if got_ok:
        return {
            "success": False,
            "message": "Command accepted, but no final CHANGE_DISPENSED confirmation was received.",
            "stock": stock,
            "status": status,
            "replies": replies,
        }

    return {
        "success": False,
        "message": "No valid change response received from Arduino.",
        "stock": stock,
        "status": status,
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