# import_taxonomy.py
import sys
from pathlib import Path

from app import create_app
from app.records import import_csv


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_taxonomy.py path/to/file.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])

    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        sys.exit(1)

    app = create_app()

    with app.app_context():
        import_csv(str(csv_path))

    print("Import complete.")


if __name__ == "__main__":
    main()