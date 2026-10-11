"""Regenerate Objectives 2 and 3 reports from the completed saved batches."""

from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent / "reporting" / "generate_objectives23_reports.py"),
    run_name="__main__",
)
