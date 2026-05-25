from __future__ import annotations
from src.reporting.plots import generate_plots


def main():
    plots = generate_plots()
    print("generated plots:")
    for p in plots:
        print(p)

if __name__ == "__main__":
    main()
