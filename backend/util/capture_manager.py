
import json
from datetime import datetime
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[2]
CAPTURES_DIR = ROOT / 'captures'
CAPTURES_DIR.mkdir(exist_ok=True)


def create_capture_session(user_id: str):
    safe_user = str(user_id or 'unknown')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = CAPTURES_DIR / safe_user / ts
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def save_capture_set(session_dir: Path, raw_frame, annotated_frame, metadata: dict):
    raw_path = session_dir / 'raw.png'
    cv2.imwrite(str(raw_path), raw_frame)

    annotated_path = session_dir / 'annotated.png'
    if annotated_frame is not None:
        cv2.imwrite(str(annotated_path), annotated_frame)

    meta_path = session_dir / 'result_metadata.json'
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    return str(raw_path), str(annotated_path), str(meta_path)
