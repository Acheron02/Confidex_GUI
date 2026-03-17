from serial import Serial
import time
import random
import string

DEFAULT_COM_PORT = '/dev/ttyUSB0'
DEFAULT_BAUD = 9600
PRINTER_NAME = "CONFIDEX"
EMAIL = "confidex@gmail.com"
WEBSITE = "https://confidex.com/"


def generate_token(user_id=None, length=12):
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=length))
    if user_id:
        return f"{str(user_id)[:6]}-{random_part}"
    return random_part


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


def _safe_text(value):
    if value is None:
        return ''
    return str(value)


def _peso(value):
    try:
        return f"PHP {float(value):.2f}"
    except Exception:
        return f"PHP {_safe_text(value)}"


def print_discount_qr(token: str, com_port=DEFAULT_COM_PORT, baud=DEFAULT_BAUD):
    """
    Prints only the discount QR coupon.
    No purchase details are printed.
    """
    try:
        print(f'[PRINTER] Opening printer port {com_port} at {baud} for QR-only print', flush=True)
        ser = Serial(com_port, baud, timeout=2, write_timeout=2)
        time.sleep(1.0)

        ser.reset_input_buffer()
        ser.reset_output_buffer()

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
        qr_data = token.encode('ascii')
        module_size = 6

        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x43' + bytes([module_size]), 0.20)

        pL = (len(qr_data) + 3) & 0xFF
        pH = ((len(qr_data) + 3) >> 8) & 0xFF
        _write(ser, b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + qr_data, 0.30)
        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x51\x30', 1.20)

        print('[PRINTER] Printing QR-only coupon footer', flush=True)
        _write(ser, b'\nThis code is one-time use only\n', 0.08)
        _write(ser, b'and will expire after 3 months.\n', 0.08)
        _write(ser, b'Keep this paper for your next purchase.\n\n', 0.08)
        _write(ser, f'Visit: {WEBSITE}\n'.encode('ascii', errors='ignore'), 0.08)
        _write(ser, b'\n\n\n', 0.30)

        ser.flush()
        time.sleep(2.0)
        ser.close()

        print('[PRINTER] QR-only coupon printed successfully', flush=True)

    except Exception as e:
        print(f'[PRINTER] Printer error in print_discount_qr: {e}', flush=True)


def print_receipt_with_discount_qr(
    token: str,
    receipt_data: dict,
    com_port=DEFAULT_COM_PORT,
    baud=DEFAULT_BAUD
):
    """
    Prints:
    - CONFIDEX header
    - purchase receipt details
    - discount QR code
    - coupon footer
    Kept here in case you still want the full printed receipt later.
    """
    try:
        print(f'[PRINTER] Opening printer port {com_port} at {baud}', flush=True)
        ser = Serial(com_port, baud, timeout=2, write_timeout=2)
        time.sleep(1.0)

        ser.reset_input_buffer()
        ser.reset_output_buffer()

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
        qr_data = token.encode('ascii')
        module_size = 6

        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x43' + bytes([module_size]), 0.20)

        pL = (len(qr_data) + 3) & 0xFF
        pH = ((len(qr_data) + 3) >> 8) & 0xFF
        _write(ser, b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + qr_data, 0.30)
        _write(ser, b'\x1D\x28\x6B\x03\x00\x31\x51\x30', 1.20)

        print('[PRINTER] Printing footer', flush=True)
        _write(ser, b'\nThis code is one-time use only\n', 0.08)
        _write(ser, b'and will expire after 3 months.\n', 0.08)
        _write(ser, b'Keep this paper for your next purchase.\n\n', 0.08)
        _write(ser, f'Visit: {WEBSITE}\n'.encode('ascii', errors='ignore'), 0.08)
        _write(ser, b'\n\n\n', 0.30)

        ser.flush()
        time.sleep(2.0)
        ser.close()

        print('[PRINTER] Receipt with discount QR printed successfully', flush=True)

    except Exception as e:
        print(f'[PRINTER] Printer error: {e}', flush=True)