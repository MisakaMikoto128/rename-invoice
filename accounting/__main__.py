"""Bootstrap: ensure schema exists. UI comes in M2."""
from accounting import db


def main():
    path = db.default_db_path()
    db.init_schema(str(path))
    print(f"[OK] schema initialized at {path}")


if __name__ == "__main__":
    main()
