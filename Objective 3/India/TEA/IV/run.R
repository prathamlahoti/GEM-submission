# Case: Objective 3 | india | TEA | iv
# Invoked by run.do/run_case.ps1. All fitted models are defined in shared analysis/models.R.
args <- commandArgs(trailingOnly = TRUE)
project_arg <- grep("^--project=", args, value = TRUE)
if (length(project_arg) != 1L) stop("One --project=... argument is required")
project_root <- sub("^--project=", "", project_arg)
source(file.path(project_root, "analysis", "run_analysis.R"), local = TRUE)
