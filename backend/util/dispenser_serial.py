import time

try:
    import serial
except Exception:
    serial = None


SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 9600
SERIAL_TIMEOUT = 15


def map_product_to_command(product_id="", product_name=""):
    pid = str(product_id).strip().lower()
    pname = str(product_name).strip().lower()

    if pid in ("1", "kit1", "oral", "oralkit", "hiv123"):
        return "DISPENSE:KIT1\n"

    if pid in ("2", "kit2", "blood", "bloodkit", "dengue123"):
        return "DISPENSE:KIT2\n"

    if pid in ("3", "kit3", "urine", "urinekit"):
        return "DISPENSE:KIT3\n"

    if "oral" in pname or "hiv" in pname:
        return "DISPENSE:KIT1\n"

    if "blood" in pname or "dengue" in pname:
        return "DISPENSE:KIT2\n"

    if "urine" in pname:
        return "DISPENSE:KIT3\n"

    return "DISPENSE:KIT1\n"


def _open_serial():
    if serial is None:
        raise RuntimeError("pyserial is not installed. Install it with: pip install pyserial")

    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUD_RATE,
        timeout=1
    )

    time.sleep(2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser


def _send_command_and_collect(command, timeout=SERIAL_TIMEOUT):
    ser = None
    try:
        ser = _open_serial()

        ser.write(command.encode("utf-8"))
        ser.flush()

        print(f"[SERIAL] Using port: {SERIAL_PORT}", flush=True)
        print(f"[SERIAL] Sent: {command.strip()}", flush=True)

        start = time.time()
        replies = []

        while time.time() - start < timeout:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            replies.append(line)
            print(f"[SERIAL] Reply: {line}", flush=True)

            upper = line.upper()

            # Stop early for commands that have a final known response
            if upper == "PONG":
                break

            if upper.startswith("DISPENSED:"):
                break

            if upper.startswith("CHANGE_DISPENSED:"):
                # keep reading a bit more for COIN_STOCK
                continue

            if upper.startswith("ERROR:"):
                # keep reading a bit more in case COIN_STOCK follows
                continue

            if upper.startswith("COIN_STOCK:") and ("GET_COIN_STOCK" in command or "DISPENSE_CHANGE:" in command):
                break

        return replies

    finally:
        if ser and ser.is_open:
            ser.close()


def send_dispense_command(product_id="", product_name=""):
    command = map_product_to_command(product_id=product_id, product_name=product_name)
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
        return {
            "success": True,
            "message": dispensed_line,
            "replies": replies,
        }

    if got_ok:
        return {
            "success": False,
            "message": "Command was accepted, but no final DISPENSED confirmation was received.",
            "replies": replies,
        }

    return {
        "success": False,
        "message": "No valid dispense response received from Arduino.",
        "replies": replies,
    }


def _parse_coin_stock_line(stock_line):
    stock = {}
    raw = stock_line.split(":", 1)[1]
    parts = raw.split(",")

    for part in parts:
        denom, count = part.split("=")
        stock[int(denom.strip())] = int(count.strip())

    return stock


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
        elif upper.startswith("ERROR:"):
            error_line = line

    stock = {}
    if stock_line:
        try:
            stock = _parse_coin_stock_line(stock_line)
        except Exception:
            stock = {}

    if busy:
        return {
            "success": False,
            "message": "Arduino is busy.",
            "stock": stock,
            "replies": replies,
        }

    if error_line:
        return {
            "success": False,
            "message": error_line,
            "stock": stock,
            "replies": replies,
        }

    if change_line:
        return {
            "success": True,
            "message": change_line,
            "stock": stock,
            "replies": replies,
        }

    if got_ok:
        return {
            "success": False,
            "message": "Command accepted, but no final CHANGE_DISPENSED confirmation was received.",
            "stock": stock,
            "replies": replies,
        }

    return {
        "success": False,
        "message": "No valid change response received from Arduino.",
        "stock": stock,
        "replies": replies,
    }


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