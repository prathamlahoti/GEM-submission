"""Regenerate the Objective 2 and 3 Word reports from saved outputs.

Requires pandas, numpy, matplotlib, Pillow and python-docx. No models are fit.
Run this from the GEM workspace that contains analysis_output and GEM_Submission.
"""

from pathlib import Path
import runpy

reporting = Path(__file__).resolve().parent / "reporting"
runpy.run_path(str(reporting / "build_objectives23_word_figures.py"), run_name="__main__")
runpy.run_path(str(reporting / "generate_objectives23_manuscripts.py"), run_name="__main__")
