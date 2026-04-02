import time
import random
import string
import glob

from serial import Serial
from serial.tools import list_ports

DEFAULT_BAUD = 9600
PRINTER_NAME = "CONFIDEX"
EMAIL = "confidex@gmail.com"
WEBSITE = "https://irretraceably-chirographical-shayne.ngrok-free.dev"

PREFERRED_PRINTER_PORT = None


def generate_token(user_id=None, length=12):
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=length))
    if user_id:
        return f"{str(user_id)[:6]}-{random_part}"
    return random_part


def _safe_text(value):
    if value is None:
        return ''
    return str(value)


def _peso(value):
    try:
        return f"PHP {float(value):.2f}"
    except Exception:
        return f"PHP {_safe_text(value)}"


def _write(ser, cmd: bytes, delay=0.10):
    ser.write(cmd)
    ser.flush()
    time.sleep(delay)


def _center(ser):
    _write(ser, b'\x1B\x61\x01', 0.10)


def _left(ser):
    _write(ser, b'\x1B\x61\x00', 0.10)


def _big(ser, on=True):
    _write(ser, b'\x1B\x21' + (b'\x30' if on else b'\x00'), 0.10)


def _normal(ser):
    _write(ser, b'\x1B\x21\x00', 0.10)


def _looks_like_arduino(port_info):
    text = " ".join([
        _safe_text(port_info.device),
        _safe_text(port_info.description),
        _safe_text(port_info.manufacturer),
        _safe_text(port_info.product),
        _safe_text(port_info.hwid),
    ]).lower()

    arduino_keywords = [
        "arduino",
        "uno",
        "mega",
        "wch",
        "ch340",
        "cp210",
        "acm",
    ]

    return any(word in text for word in arduino_keywords)


def _looks_like_printer(port_info):
    text = " ".join([
        _safe_text(port_info.device),
        _safe_text(port_info.description),
        _safe_text(port_info.manufacturer),
        _safe_text(port_info.product),
        _safe_text(port_info.hwid),
    ]).lower()

    printer_keywords = [
        "printer",
        "thermal",
        "pos",
        "receipt",
        "ttl",
        "usb serial",
        "usb-serial",
        "serial",
        "uart",
        "ch340",
        "cp210",
        "pl2303",
        "ftdi",
        "qinhen",
        "wch",
    ]

    return any(word in text for word in printer_keywords)


def list_serial_devices():
    devices = []
    for p in list_ports.comports():
        devices.append({
            "device": p.device,
            "description": p.description,
            "manufacturer": p.manufacturer,
            "product": p.product,
            "hwid": p.hwid,
            "vid": p.vid,
            "pid": p.pid,
        })
    return devices


def _find_printer_port():
    # 1) Prefer stable /dev/serial/by-id if explicitly configured
    if PREFERRED_PRINTER_PORT:
        return PREFERRED_PRINTER_PORT

    # 2) If only one /dev/serial/by-id device exists and it is not Arduino, use it
    by_id_ports = sorted(glob.glob("/dev/serial/by-id/*"))
    if by_id_ports:
        for stable_port in by_id_ports:
            lowered = stable_port.lower()
            if "arduino" not in lowered and "uno" not in lowered:
                return stable_port

    # 3) Inspect enumerated serial devices and skip Arduino-looking ports
    ports = list(list_ports.comports())

    # First pass: choose port that looks like a printer and not like Arduino
    for p in ports:
        if _looks_like_printer(p) and not _looks_like_arduino(p):
            return p.device

    # Second pass: allow ttyUSB ports that do not look like Arduino
    for p in ports:
        dev = _safe_text(p.device)
        if dev.startswith("/dev/ttyUSB") and not _looks_like_arduino(p):
            return dev

    # Third pass: allow ttyAMA/ttyS if needed, still avoiding Arduino
    for p in ports:
        dev = _safe_text(p.device)
        if (dev.startswith("/dev/ttyAMA") or dev.startswith("/dev/ttyS")) and not _looks_like_arduino(p):
            return dev

    raise RuntimeError(
        "No thermal printer serial port found. "
        "Run list_serial_devices() and set PREFERRED_PRINTER_PORT to the correct device."
    )


def _open_printer_serial(com_port=None, baud=DEFAULT_BAUD):
    port = com_port or _find_printer_port()

    print(f"[PRINTER] Opening printer port {port} at {baud}", flush=True)

    ser = Serial(
        port=port,
        baudrate=baud,
        timeout=2,
        write_timeout=2
    )

    time.sleep(1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser


def print_discount_qr(token: str, com_port=None, baud=DEFAULT_BAUD):
    """
    Prints only the discount QR coupon.
    No purchase details are printed.
    """
    ser = None
    try:
        ser = _open_printer_serial(com_port=com_port, baud=baud)

        _write(ser, b'\x1B@', 0.20)
        time.sleep(0.50)

        print('[PRINTER] Printing QR-only coupon header', flush=True)
        _center(ser)
        _big(ser, True)
        _write(ser, f'{PRINTER_NAME}\n'.encode('ascii', errors='ignore'), 0.15)
        _normal(ser)
        _write(ser, f'{EMAIL}\n\n'.encode('ascii', errors='ignore'), 0.10)
        _write(ser, b'DISCOUNT COUPON\n', 0.10)
        _write(ser, b'Scan this QR on your next use\n\n', 0.10)

        print('[PRINTER] Printing QR-only coupon QR', flush=True)
        qr_data = token.encode('ascii', errors='ignore')
        module_size = 6

        _write(ser, b'\x1D\x28\x6B\x04\x00\x31\x41\x32\x00', 0.20)
        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x43' + bytes([module_size]), 0.20)
        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x45\x31', 0.20)

        pL = (len(qr_data) + 3) & 0xFF
        pH = ((len(qr_data) + 3) >> 8) & 0xFF
        _write(ser, b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + qr_data, 0.30)

        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x51\x30', 1.20)

        print('[PRINTER] Printing QR-only coupon footer', flush=True)
        _left(ser)
        _write(ser, b'\nThis code is one-time use only\n', 0.08)
        _write(ser, b'and will expire after 3 months.\n', 0.08)
        _write(ser, b'Keep this paper for your next purchase.\n\n', 0.08)
        _write(ser, f'Visit: {WEBSITE}\n'.encode('ascii', errors='ignore'), 0.08)
        _write(ser, b'\n\n\n', 0.30)

        ser.flush()
        time.sleep(2.0)

        print('[PRINTER] QR-only coupon printed successfully', flush=True)
        return True

    except Exception as e:
        print(f'[PRINTER] Printer error in print_discount_qr: {e}', flush=True)
        return False

    finally:
        if ser and ser.is_open:
            ser.close()


def print_receipt_with_discount_qr(
    token: str,
    receipt_data: dict,
    com_port=None,
    baud=DEFAULT_BAUD
):
    """
    Prints:
    - CONFIDEX header
    - purchase receipt details
    - discount QR code
    - coupon footer
    """
    ser = None
    try:
        ser = _open_printer_serial(com_port=com_port, baud=baud)

        _write(ser, b'\x1B@', 0.20)
        time.sleep(0.50)

        user = receipt_data.get('user', {})
        purchase = receipt_data.get('purchase', {})
        product = receipt_data.get('product', {})
        amounts = receipt_data.get('amounts', {})
        payment = receipt_data.get('payment', {})

        transaction_id = _safe_text(receipt_data.get('transaction_id'))
        username = _safe_text(user.get('username', 'User'))
        user_id = _safe_text(user.get('user_id', 'Unknown'))
        date_str = _safe_text(purchase.get('date'))
        time_str = _safe_text(purchase.get('time'))

        product_name = _safe_text(product.get('name', 'Unknown'))
        product_id = _safe_text(product.get('product_id', 'Unknown'))
        product_type = _safe_text(product.get('type', 'Unknown'))
        price = _peso(product.get('price', 0))

        discount_percent = _safe_text(amounts.get('discount_percent', 0))
        total = _peso(amounts.get('total', 0))
        total_paid = _peso(amounts.get('total_paid', 0))
        change = _peso(amounts.get('change', 0))

        mode_of_payment = _safe_text(payment.get('mode_of_payment', 'Cash'))

        print('[PRINTER] Printing header', flush=True)
        _center(ser)
        _big(ser, True)
        _write(ser, f'{PRINTER_NAME}\n'.encode('ascii', errors='ignore'), 0.15)
        _normal(ser)
        _write(ser, f'{EMAIL}\n'.encode('ascii', errors='ignore'), 0.10)
        _write(ser, f'{WEBSITE}\n\n'.encode('ascii', errors='ignore'), 0.10)
        _write(ser, b'PURCHASE RECEIPT\n', 0.10)
        _write(ser, b'------------------------------\n', 0.10)

        print('[PRINTER] Printing details', flush=True)
        _left(ser)
        details_lines = [
            f"Transaction ID: {transaction_id}",
            f"Username: {username}",
            f"User ID: {user_id}",
            f"Date: {date_str}",
            f"Time: {time_str}",
            "",
            f"Item: {product_name}",
            f"Product ID: {product_id}",
            f"Type: {product_type}",
            f"Price: {price}",
            f"Discount: {discount_percent}%",
            f"Total: {total}",
            f"Paid: {total_paid}",
            f"Change: {change}",
            f"Payment: {mode_of_payment}",
            "",
            "------------------------------",
            "DISCOUNT COUPON",
            "Scan this QR on your next use",
            "",
        ]

        for line in details_lines:
            _write(ser, (line + '\n').encode('ascii', errors='ignore'), 0.05)

        print('[PRINTER] Printing QR', flush=True)
        _center(ser)
        qr_data = token.encode('ascii', errors='ignore')
        module_size = 6

        # Select model 2
        _write(ser, b'\x1D\x28\x6B\x04\x00\x31\x41\x32\x00', 0.20)

        # Set module size
        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x43' + bytes([module_size]), 0.20)

        # Set error correction level M
        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x45\x31', 0.20)

        # Store QR data
        pL = (len(qr_data) + 3) & 0xFF
        pH = ((len(qr_data) + 3) >> 8) & 0xFF
        _write(ser, b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + qr_data, 0.30)

        # Print QR
        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x51\x30', 1.20)

        print('[PRINTER] Printing footer', flush=True)
        _left(ser)
        _write(ser, b'\nThis code is one-time use only\n', 0.08)
        _write(ser, b'and will expire after 3 months.\n', 0.08)
        _write(ser, b'Keep this paper for your next purchase.\n\n', 0.08)
        _write(ser, f'Visit: {WEBSITE}\n'.encode('ascii', errors='ignore'), 0.08)
        _write(ser, b'\n\n\n', 0.30)

        ser.flush()
        time.sleep(2.0)

        print('[PRINTER] Receipt with discount QR printed successfully', flush=True)
        return True

    except Exception as e:
        print(f'[PRINTER] Printer error: {e}', flush=True)
        return False

    finally:
        if ser and ser.is_open:
            ser.close()


def debug_list_serial_devices():
    print("[SERIAL] Available serial devices:", flush=True)
    for dev in list_serial_devices():
        print(
            f"  device={dev['device']} | "
            f"description={dev['description']} | "
            f"manufacturer={dev['manufacturer']} | "
            f"product={dev['product']} | "
            f"hwid={dev['hwid']}",
            flush=True
        )