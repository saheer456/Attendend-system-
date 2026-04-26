import sys
from pathlib import Path

# Keep local dependencies inside the repo for restricted environments.
vendor_path = Path(__file__).resolve().parent / ".vendor"
if vendor_path.exists():
    sys.path.insert(0, str(vendor_path))

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
