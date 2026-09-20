from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.data_generation import GenerationConfig, SyntheticDataGenerator


def main() -> None:
    output_dir = ROOT / "data" / "raw"
    generator = SyntheticDataGenerator(output_dir, GenerationConfig())
    paths = generator.generate_all()

    print("Synthetic demo data generated:")
    for name, path in paths.items():
        print(f"- {name}: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
