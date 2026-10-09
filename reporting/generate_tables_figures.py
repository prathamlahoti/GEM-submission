"""Generate the Objective 1 tables, figures, and combined report from saved outputs.

Example:
    python generate_tables_figures.py \
        --batch-dir C:/path/to/analysis_output/objective1_batch_20260927

This does not fit or rerun any machine-learning model.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def compile_tex(tex_path: Path, pdflatex: str) -> None:
    for pass_number in (1, 2):
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tex_path.parent,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            tail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-35:])
            raise RuntimeError(f"LaTeX pass {pass_number} failed for {tex_path}:\n{tail}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, required=True,
                        help="Completed objective1_batch_20260927 directory")
    parser.add_argument("--output-dir", type=Path, default=HERE / "generated",
                        help="Directory for generated tables, figures, and report")
    parser.add_argument("--pdflatex", default=shutil.which("pdflatex"),
                        help="Path to pdflatex; required unless --skip-compile")
    parser.add_argument("--skip-compile", action="store_true",
                        help="Create table LaTeX and figure PDFs without compiled table/report PDFs")
    args = parser.parse_args()

    batch = args.batch_dir.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    required = [batch / "pipeline_complete.txt", batch / "all_performance.csv",
                batch / "objective_1", batch.parent / "model_input.csv"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        parser.error("Required saved analysis outputs are missing:\n  " + "\n  ".join(missing))
    if not args.skip_compile and not args.pdflatex:
        parser.error("pdflatex is required; supply --pdflatex or use --skip-compile")

    env = os.environ.copy()
    env["GEM_OBJECTIVE1_BATCH"] = str(batch)
    env["GEM_REPORT_OUTPUT"] = str(output)
    for script in ("build_objective1_tables.py", "build_objective1_figures.py",
                   "build_objective1_complete_report.py"):
        subprocess.run([sys.executable, str(HERE / script)], env=env, check=True)

    if not args.skip_compile:
        compile_tex(output / "objective1_tables" / "Objective1_Tables.tex", args.pdflatex)
        compile_tex(output / "objective1_complete" / "Objective1_Complete_Results.tex", args.pdflatex)
        print(f"Complete PDF: {output / 'objective1_complete' / 'Objective1_Complete_Results.pdf'}")
    else:
        print(f"Generated sources and figures: {output}")


if __name__ == "__main__":
    main()
