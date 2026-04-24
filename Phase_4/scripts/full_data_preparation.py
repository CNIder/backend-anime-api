from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

RAW_FILE = DATA_DIR / "anime-dataset-2023.csv"
UTF8_FILE = DATA_DIR / "anime-dataset-2023-utf8.csv"
TRIMMED_FILE = DATA_DIR / "anime_trimmed.csv"

USE_COLS = [
    "anime_id",
    "English name",
    "Score",
    "Genres",
    "Episodes",
    "Studios",
    "Rank",
    "Popularity",
    "Members",
    "Synopsis",
]

def convert_to_utf8(input_file: Path, output_file: Path) -> None:
    """
    Reads the original CSV and writes it back explicitly as UTF-8.
    """
    df = pd.read_csv(input_file)
    df.to_csv(output_file, index=False, encoding="utf-8")
    print(f"UTF-8 file created: {output_file}")

def create_trimmed_dataset(input_file: Path, output_file: Path, nrows: int | None = 5000) -> None:
    """
    Reads the UTF-8 CSV, keeps only selected columns, renames fields,
    and saves a smaller trimmed dataset.
    """
    df = pd.read_csv(
        input_file,
        usecols=USE_COLS,
        nrows=nrows
    )

    df.rename(columns={"English name": "english_name"}, inplace=True)

    print("Columns:")
    print(df.columns.tolist())
    print("\nData types:")
    print(df.dtypes)
    print("\nPreview:")
    print(df.head(3))

    df.to_csv(output_file, index=False, encoding="utf-8")
    print(f"\nTrimmed dataset created: {output_file}")

def main():
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Input dataset not found: {RAW_FILE}\n"
            f"Please place the downloaded Kaggle file in the data/ folder."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    convert_to_utf8(RAW_FILE, UTF8_FILE)
    create_trimmed_dataset(UTF8_FILE, TRIMMED_FILE, nrows=5000)

if __name__ == "__main__":
    main()