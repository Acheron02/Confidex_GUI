# discount_printer.py
import serial
import time
import random
import string

# -------------------- Configuration --------------------
DEFAULT_COM_PORT = '/dev/ttyUSB0'
DEFAULT_BAUD = 9600
PRINTER_NAME = "CONFIDEX"
EMAIL = "confidex@gmail.com"
WEBSITE = "https://confidex.com/"

# -------------------- QR Token Generation --------------------
def generate_token(user_id=None, length=12):
    """
    Generate a QR token.
    Optionally include first 6 characters of user_id for uniqueness.
    """
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=length))
    if user_id:
        return f"{user_id[:6]}-{random_part}"
    return random_part

# -------------------- Printer Helpers --------------------
def _write(ser, cmd: bytes):
    ser.write(cmd)
    time.sleep(0.05)

def _center(ser):
    _write(ser, b'\x1B\x61\x01')   # ESC a 1 -> center

def _big(ser, on=True):
    _write(ser, b'\x1B\x21' + (b'\x30' if on else b'\x00'))  # double width + height

# -------------------- Main Print Function --------------------
def print_discount_qr(token: str, com_port=DEFAULT_COM_PORT, baud=DEFAULT_BAUD):
    try:
        ser = serial.Serial(com_port, baud, timeout=1)
        time.sleep(0.2)  # allow printer to initialize

        # Initialize printer
        ser.write(b'\x1B@')  # reset printer
        time.sleep(0.05)

        # Center text
        ser.write(b'\x1Ba\x01')
        time.sleep(0.05)

        # Header
        ser.write(b'\x1B!\x30')  # big font
        ser.write(f'{PRINTER_NAME}\n'.encode('ascii'))
        ser.write(b'\x1B!\x00')  # normal font
        ser.write(f'{EMAIL}\n\n'.encode('ascii'))
        ser.write(b'Discount Coupon\n')
        time.sleep(0.05)

        # QR code
        qr_data = token.encode('ascii')
        module_size = 6

        ser.write(b'\x1D\x28\x6B\x03\x00\x31\x43' + bytes([module_size]))
        pL = (len(qr_data) + 3) & 0xFF
        pH = ((len(qr_data) + 3) >> 8) & 0xFF
        ser.write(b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + qr_data)
        ser.write(b'\x1D\x28\x6B\x03\x00\x31\x51\x30')
        time.sleep(0.2)

        # Footer
        ser.write(b'\nThis code is one-time use only\n')
        ser.write(b'and will expire after 3 months.\n\n')
        ser.write(f'Visit: {WEBSITE}\n\n\n'.encode('ascii'))
        time.sleep(0.2)

        ser.flush()
        ser.close()
        print("Discount QR printed successfully")

    except Exception as e:
        print("Printer error:", e)

