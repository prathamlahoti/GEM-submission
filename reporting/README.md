# Generate Objective 1 tables and figures

`generate_tables_figures.py` rebuilds the Objective 1 tables, four figures, and combined PDF **from saved analysis outputs**. It does not fit models. The supplied `Objective1_Complete_Results.pdf` is the verified report from the original completed batch.

## Inputs

The repository deliberately omits respondent-level data and the large saved batch outputs. To reproduce the report, provide:

- the completed `objective1_batch_20260927` folder, with its `objective_1` case folders, performance CSVs, ROC/PR coordinates, importance CSVs, and completion markers;
- `model_input.csv` in that batch folder's parent (`analysis_output/model_input.csv`), used only to calculate the household-size quartiles in Table 3.

The scripts check that all 120 model statuses are successful and that IV and IV+CV use identical held-out row IDs. They stop if required files are absent.

## Run

Install Python with `pandas`, `numpy`, and `matplotlib`. Install either `pdfunite` or `pypdf` for the combined figure PDF, and `pdflatex` for the table and full-report PDFs.

From the repository root:

```powershell
python generate_tables_figures.py --batch-dir "C:\path\to\analysis_output\objective1_batch_20260927"
```

If `pdflatex` is not on `PATH`, add `--pdflatex "C:\path\to\pdflatex.exe"`. Add `--skip-compile` to generate the LaTeX table source and figure PDFs without compiling the table and full-report PDFs. Use `--output-dir` to choose a different destination. The default is `reporting/generated/`, which Git ignores.

The output has 6 main tables, 2 appendix tables, 4 vector figures, and the combined `objective1_complete/Objective1_Complete_Results.pdf`. The main results use IV+CV for Global and India across TEA, OME, and NME. The comparison table and figure show IV versus IV+CV.

## Objective 2 and 3 reports

`generate_objectives23_reports.py` at the repository root reads the completed `objective2_batch_20260928` and `objective3_batch_20260928` directories. It checks all 120 model statuses per objective and verifies matched IV and IV+CV held-out row IDs. It then writes one PDF per objective plus the seven underlying tables as CSV and five figures as PNG. Every table and figure has Global and India interpretation paragraphs. It never refits a model.

The original batch directories are intentionally excluded from Git because they contain large model and respondent-level files. To regenerate, install `pandas`, `numpy`, `matplotlib`, `reportlab`, and Pillow, then run from the GEM workspace:

```powershell
python GEM_Submission/generate_objectives23_reports.py --batch-root analysis_output
```

The journal-style Word reports use the same saved tables and underlying batch outputs. From the GEM workspace, run `python GEM_Submission/generate_objectives23_word.py` with `pandas`, `numpy`, `matplotlib`, Pillow, and `python-docx` installed. The Word figures are redrawn from saved coordinates and importance CSVs; the documents are built from saved result CSVs. No classifier is refitted.

## Separate India and Global Word studies for Objectives 1–3

The [`split_studies`](split_studies/) directory contains six sample-specific Word studies. Each study has its own descriptive and performance tables, sample-specific figures, two-paragraph interpretations of each main table and figure, discussion, conclusion, and full ten-model supplementary results. To regenerate them from completed local batch outputs, run `python GEM_Submission/reporting/generate_six_studies.py` from the GEM workspace. The script checks batch completion and matching held-out records, and does not refit classifiers.
