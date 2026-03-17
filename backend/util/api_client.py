import os
from pathlib import Path
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / '.env.local'


def reload_env():
    load_dotenv(ENV_PATH, override=True)


reload_env()


def _base_url() -> str:
    reload_env()
    base = os.getenv('BASE_URL') or os.getenv('networkIP') or '127.0.0.1:3000'
    if not base.startswith('http://') and not base.startswith('https://'):
        base = f'http://{base}'
    return base.rstrip('/')


def url(path: str) -> str:
    return f"{_base_url()}{path}"


def post_json(path: str, payload: dict, timeout: int = 10):
    reload_env()
    return requests.post(url(path), json=payload, timeout=timeout)


def get_json(path: str, timeout: int = 10):
    reload_env()
    return requests.get(url(path), timeout=timeout)


def verify_login_qr(qr_code: str):
    return post_json('/api/qr-tokens/verify', {'qrCode': qr_code})


def validate_discount_token(user_id: str, token: str):
    return post_json('/api/qr-tokens/validate', {'userId': user_id, 'token': token})


def store_qr_token(user_id: str, token: str):
    return post_json('/api/qr-tokens', {'userId': user_id, 'token': token})


def post_transaction(payload: dict):
    return post_json('/api/transaction', payload)


def post_result(payload: dict):
    return post_json('/api/results', payload)


def upload_result_image(user_id: str, product_id: str, image_path: str):
    reload_env()
    with open(image_path, 'rb') as f:
        files = {'image': (os.path.basename(image_path), f, 'image/jpeg')}
        return requests.post(
            url(f'/api/results/image/{user_id}/{product_id}'),
            files=files,
            timeout=10
        )


def create_paymongo_checkout(payload: dict):
    reload_env()
    return post_json('/api/paymongo/checkout', payload, timeout=15)


def get_paymongo_checkout_status(session_id: str):
    reload_env()
    return get_json(f'/api/paymongo/checkout-status/{session_id}', timeout=15)