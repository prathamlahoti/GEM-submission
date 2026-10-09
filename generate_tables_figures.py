"""Generate Objective 1 tables and figures from saved analysis outputs.

Run ``python generate_tables_figures.py --help`` for usage. The implementation
and documentation are in the reporting/ directory of this repository.
"""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "reporting" / "generate_tables_figures.py"),
               run_name="__main__")
