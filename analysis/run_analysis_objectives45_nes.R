#!/usr/bin/env Rscript

parse_arguments <- function(items) {
  result <- list()
  for (item in items) {
    if (!startsWith(item, "--") || !grepl("=", item, fixed = TRUE)) {
      stop("Arguments must have the form --name=value")
    }
    parts <- strsplit(substring(item, 3), "=", fixed = TRUE)[[1]]
    result[[parts[1]]] <- paste(parts[-1], collapse = "=")
  }
  result
}

args <- parse_arguments(commandArgs(trailingOnly = TRUE))
for (name in c("input", "output", "project")) {
  if (is.null(args[[name]]) || !nzchar(args[[name]])) {
    stop(sprintf("Missing required argument --%s=...", name))
  }
}
project <- normalizePath(args$project, winslash = "/", mustWork = TRUE)
input <- normalizePath(args$input, winslash = "/", mustWork = TRUE)
output <- normalizePath(args$output, winslash = "/", mustWork = FALSE)
dir.create(output, recursive = TRUE, showWarnings = FALSE)
completion_marker <- file.path(output, "pipeline_complete.txt")
if (file.exists(completion_marker)) file.remove(completion_marker)
lib <- file.path(project, ".r-lib")
resume <- identical(args$resume, "true")
signature <- tools::md5sum(c(input, file.path(project, "analysis", c("run_analysis_objectives45_nes.R", "common_objectives45_nes.R", "models.R"))))
signature_file <- file.path(output, "input_code_signature.rds")
if (file.exists(signature_file) && !identical(readRDS(signature_file), signature)) {
  stop("Input or analysis code changed; use a new output folder to avoid mixing results")
}
saveRDS(signature, signature_file)
if (dir.exists(lib)) .libPaths(c(lib, .libPaths()))
source(file.path(project, "analysis", "common_objectives45_nes.R"), local = TRUE)
source(file.path(project, "analysis", "models.R"), local = TRUE)
runtime <- file.path(project, "analysis", "runtime")
java8_candidates <- list.dirs(runtime, recursive = FALSE, full.names = TRUE)
java8_candidates <- java8_candidates[
  grepl("^jdk8", basename(java8_candidates)) &
    file.exists(file.path(java8_candidates, "bin", "java.exe"))
]
java8 <- if (length(java8_candidates)) java8_candidates[1] else ""
java17 <- "C:/Program Files/Eclipse Adoptium/jdk-17.0.12.7-hotspot"
if (nzchar(java8)) {
  Sys.setenv(JAVA_HOME = java8)
} else if (file.exists(file.path(java17, "bin", "java.exe"))) {
  Sys.setenv(JAVA_HOME = java17)
}

log_path <- file.path(output, "r_analysis.log")
if (file.exists(log_path)) file.remove(log_path)
log_line <- function(...) {
  line <- paste(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), paste(..., collapse = " "))
  cat(line, "\n")
  cat(line, "\n", file = log_path, append = TRUE)
}

if (!requireNamespace("data.table", quietly = TRUE) ||
    !requireNamespace("Matrix", quietly = TRUE)) {
  stop("Required data.table or Matrix package is missing. See analysis/README.md")
}

objectives_to_run <- if (is.null(args$objective)) 4:5 else as.integer(args$objective)
scopes_to_run <- if (is.null(args$scope)) c("global", "india") else args$scope
feature_sets_to_run <- if (is.null(args$feature_set)) "iv_cv_nes" else args$feature_set
outcomes_to_run <- if (is.null(args$outcome)) outcomes else args$outcome
models_to_run <- if (is.null(args$models)) model_names else strsplit(args$models, ",", fixed = TRUE)[[1]]
if (anyNA(objectives_to_run) || !all(objectives_to_run %in% 4:5) ||
    !all(scopes_to_run %in% c("global", "india")) ||
    !all(feature_sets_to_run %in% "iv_cv_nes") ||
    !all(outcomes_to_run %in% outcomes) ||
    !all(models_to_run %in% model_names)) {
  stop("Invalid objective, scope, feature_set, outcome, or model filter")
}

packages_by_model <- c(
  `Logistic Regression` = "glmnet", Lasso = "glmnet", Ridge = "glmnet",
  `Elastic Net` = "glmnet", `Naive Bayes` = "e1071",
  `Decision Tree` = "rpart", XGBoost = "xgboost",
  CatBoost = "catboost", `Random Forest` = "ranger", `H2O GBM` = "h2o"
)
packages <- unique(c("data.table", "Matrix", unname(packages_by_model[models_to_run])))
versions <- data.frame(
  package = packages,
  version = vapply(packages, function(package) {
    if (requireNamespace(package, quietly = TRUE)) {
      as.character(utils::packageVersion(package))
    } else "NOT INSTALLED"
  }, character(1))
)
data.table::fwrite(versions, file.path(output, "package_versions.csv"))
writeLines(c(R.version.string, paste("Input:", input), paste("Seed:", 20260925L)),
           file.path(output, "run_manifest.txt"))

log_line("Loading selected GEM data from", input)
data <- data.table::fread(input, na.strings = c("", "NA", "."),
                          showProgress = TRUE)
required <- unique(c("__rowid", "country_name", "setid", "EXIT_ENT", "exit_ent", outcomes,
                     sct_vars, legatum_vars, efw_vars, control_vars, nes_vars))
missing_columns <- setdiff(required, names(data))
if (length(missing_columns)) {
  stop("Input lacks required columns: ", paste(missing_columns, collapse = ", "))
}
if (anyDuplicated(data[["__rowid"]])) stop("__rowid must uniquely identify source rows")
for (name in c(outcomes, "EXIT_ENT", "exit_ent")) assert_binary(data[[name]], name)
expected_exit <- data$EXIT_ENT
expected_exit[is.na(expected_exit)] <- data$exit_ent[is.na(expected_exit)]
if (!identical(is.na(expected_exit), is.na(data$EXIT_ENT_harmonized)) ||
    any(expected_exit != data$EXIT_ENT_harmonized, na.rm = TRUE)) stop("Exit harmonization mismatch")
if (any(!is.na(data$EXIT_ENT) & !is.na(data$exit_ent))) stop("Unexpected exit source overlap")
if (any(data$discent != expected_exit, na.rm = TRUE)) stop("Exit duplicate audit changed")
data.table::fwrite(data[, .(rows=.N, known_exit=sum(!is.na(EXIT_ENT_harmonized)),
  known_fear=sum(!is.na(fearfail_2015_2022)), exit_positive=sum(EXIT_ENT_harmonized==1,na.rm=TRUE)),
  by=.(country_name,yrsurv)], file.path(output,"new_outcomes_audit.csv"))
rm(expected_exit)
if (anyNA(data$country_name)) stop("country_name has missing values")

log_line("Rows:", nrow(data), "Countries:", data.table::uniqueN(data$country_name))
key <- paste(data$country_name, data$yrsurv, data$setid, sep = "|")
audit <- data.frame(
  item = c("rows", "countries", "india_rows", "duplicate_country_year_setid"),
  value = c(nrow(data), data.table::uniqueN(data$country_name),
            sum(tolower(trimws(data$country_name)) == "india"), sum(duplicated(key)))
)
data.table::fwrite(audit, file.path(output, "data_audit.csv"))
rm(key)
gc(verbose = FALSE)

dictionary_path <- file.path(project, "analysis", "variable_dictionary_objectives45_nes.csv")
if (!file.exists(dictionary_path)) stop("Missing analysis/variable_dictionary.csv")
dictionary <- data.table::fread(dictionary_path)
dictionary <- dictionary[match(required[-1], dictionary$variable), ]
if (anyNA(dictionary$variable)) stop("The variable dictionary is incomplete")
dictionary$role <- vapply(dictionary$variable, function(name) {
  if (name %in% outcomes) "outcome" else if (name %in% c("EXIT_ENT", "exit_ent")) "outcome source (audit only)" else if (name == "country_name") "sample selector" else
    if (name == "setid") "record identifier" else if (name %in% c(control_vars, nes_vars)) "control" else
      "independent variable"
}, character(1))
dictionary$data_type <- vapply(dictionary$variable, function(name) {
  paste(class(data[[name]]), collapse = "/")
}, character(1))
dictionary$n_missing <- vapply(dictionary$variable, function(name) {
  values <- data[[name]]
  sum(if (is.character(values)) is.na(values) | trimws(values) == "" else is.na(values))
}, numeric(1))
data.table::fwrite(dictionary, file.path(output, "appendix_A1_variables.csv"))

model_status <- list()
all_performance <- list()
all_sample_counts <- list()
status_file <- file.path(output, "model_status.csv")
if (file.exists(status_file)) file.remove(status_file)
performance_file <- file.path(output, "all_performance.csv")
if (file.exists(performance_file)) file.remove(performance_file)

write_descriptives <- function(d, features, path) {
  rows <- lapply(features, function(name) {
    values <- d[[name]]
    missing <- if (is.character(values)) is.na(values) | trimws(values) == "" else is.na(values)
    if (name %in% categorical_vars) {
      observed <- as.character(values[!missing])
      levels <- sort(unique(observed))
      data.frame(variable = name, type = "categorical", n = length(values),
                 n_missing = sum(missing), mean = NA_real_, sd = NA_real_,
                 minimum = NA_real_, maximum = NA_real_,
                 categories = paste(head(levels, 30), collapse = ";"))
    } else {
      numeric <- suppressWarnings(as.numeric(values))
      valid <- numeric[is.finite(numeric)]
      data.frame(variable = name, type = "numeric", n = length(values),
                 n_missing = length(values) - length(valid),
                 mean = if (length(valid)) mean(valid) else NA_real_,
                 sd = if (length(valid) > 1L) stats::sd(valid) else NA_real_,
                 minimum = if (length(valid)) min(valid) else NA_real_,
                 maximum = if (length(valid)) max(valid) else NA_real_,
                 categories = "")
    }
  })
  data.table::fwrite(data.table::rbindlist(rows), path)
}

write_status <- function(row) {
  model_status[[length(model_status) + 1L]] <<- row
  data.table::fwrite(row, status_file, append = file.exists(status_file),
                     col.names = !file.exists(status_file))
}

h2o_ready <- FALSE
queue <- data.table::rbindlist(lapply(objectives_to_run, function(o) {
  data.table::rbindlist(lapply(feature_sets_to_run, function(f) {
    data.table::rbindlist(lapply(scopes_to_run, function(s) {
      data.frame(objective = o, scope = s, feature_set = f, outcome = intersect(outcomes_to_run, objective_outcome(o)))
    }))
  }))
}))
queue$run_id <- sprintf("%02d_obj%d_%s_%s_%s", seq_len(nrow(queue)), queue$objective,
                         queue$scope, queue$feature_set, queue$outcome)
queue$status <- "queued"
queue$started <- ""
queue$finished <- ""
data.table::fwrite(queue, file.path(output, "run_queue.csv"))
if (!nrow(queue)) stop("No matching objective/outcome combinations")
if ("H2O GBM" %in% models_to_run && requireNamespace("h2o", quietly = TRUE)) {
  log_line("Starting local H2O cluster")
  h2o_ready <- tryCatch({
    h2o::h2o.init(ip = "127.0.0.1", port = 55555,
                  nthreads = 4, max_mem_size = "8G", startH2O = TRUE)
    h2o::h2o.no_progress()
    TRUE
  }, error = function(e) {
    log_line("H2O startup failed:", conditionMessage(e))
    FALSE
  })
}

for (objective in objectives_to_run) {
  independent <- objective_features(objective)
  for (feature_set in feature_sets_to_run) {
    features <- if (feature_set == "iv") independent else c(independent, control_vars, nes_vars)
    if (any(features %in% c("country_name", "setid", "__rowid"))) {
      stop("Country or record ID entered the predictor list")
    }
    for (scope in scopes_to_run) {
      scope_rows <- if (scope == "global") seq_len(nrow(data)) else
        which(tolower(trimws(data$country_name)) == "india")
      if (length(scope_rows) == 0L) stop("India sample is empty")
      for (outcome in intersect(outcomes_to_run, objective_outcome(objective))) {
        if (any(features %in% c(outcome, "EXIT_ENT", "exit_ent", "EXIT_ENT_harmonized"))) stop("Outcome entered predictors")
        if (objective == 5L && "discent" %in% features) stop("Duplicate exit predictor entered model")
        case_name <- sprintf("objective_%d_%s_%s_%s", objective, scope,
                             feature_set, outcome)
        case_dir <- file.path(output, sprintf("objective_%d", objective),
                              scope, feature_set, outcome)
        dir.create(case_dir, recursive = TRUE, showWarnings = FALSE)
        queue_index <- which(queue$objective == objective & queue$scope == scope &
                               queue$feature_set == feature_set & queue$outcome == outcome)
        run_id <- queue$run_id[queue_index]
        queue$status[queue_index] <- "running"
        queue$started[queue_index] <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
        data.table::fwrite(queue, file.path(output, "run_queue.csv"))
        writeLines(c(paste("Run:", run_id), paste("Features:", paste(features, collapse = ", ")),
                     "Country and setid excluded as predictors.",
                     "Intention missingness retained; importance is not causal."),
                   file.path(case_dir, "RUN_LABEL.txt"))
        data.table::fwrite(data.frame(variable = features,
                                      role = ifelse(features %in% c(control_vars, nes_vars), "control", "independent")),
                           file.path(case_dir, "features.csv"))
        log_line("Starting", case_name)

        eligible <- scope_rows[!is.na(data[[outcome]][scope_rows])]
        d <- data[eligible, unique(c("__rowid", "country_name", "yrsurv", outcome, features)),
                  with = FALSE]
        y <- as.integer(d[[outcome]])
        if (!all(y %in% c(0, 1))) stop("Invalid outcome in case ", case_name)
        split <- make_split(y, seed = 20260925L +
                            match(scope, c("global", "india")) * 100L +
                            match(outcome, outcomes))
        baseline_case <- if (!is.null(args$baseline_case)) args$baseline_case else ""
        if (nzchar(baseline_case) && file.exists(file.path(baseline_case,"heldout_rowids.csv"))) {
          baseline_ids <- data.table::fread(file.path(baseline_case,"heldout_rowids.csv"))
          expected_ids <- data.frame(rowid=d[["__rowid"]][c(split$validation,split$test)],
            partition=c(rep("validation",length(split$validation)),rep("test",length(split$test))))
          if (!identical(as.numeric(baseline_ids$rowid),as.numeric(expected_ids$rowid)) ||
              !identical(as.character(baseline_ids$partition),expected_ids$partition)) stop("NES held-out IDs differ from original controls case")
          baseline_counts <- data.table::fread(file.path(baseline_case,"sample_counts.csv"))
          if (baseline_counts$n != length(y) || baseline_counts$positive != sum(y==1)) stop("NES eligible sample changed")
          writeLines("Validation/test row IDs and outcome counts match the available IV + controls rerun",
            file.path(case_dir,"baseline_partition_check.txt"))
        } else {
          writeLines("Original IV + controls rerun unavailable; using the same fixed stratified split seed",
            file.path(case_dir,"baseline_partition_check.txt"))
        }
        counts <- data.frame(
          objective = objective, scope = scope, feature_set = feature_set,
          outcome = outcome, n = nrow(d), positive = sum(y == 1),
          prevalence = mean(y), n_train = length(split$train),
          n_validation = length(split$validation), n_test = length(split$test),
          countries = data.table::uniqueN(d$country_name),
          years = data.table::uniqueN(d$yrsurv)
        )
        all_sample_counts[[length(all_sample_counts) + 1L]] <- counts
        data.table::fwrite(counts, file.path(case_dir, "sample_counts.csv"))
        partitions <- rep("train", nrow(d))
        partitions[split$validation] <- "validation"
        partitions[split$test] <- "test"
        data.table::fwrite(data.frame(rowid = d[["__rowid"]], outcome = y,
                                      country = d$country_name, year = d$yrsurv,
                                      partition = partitions),
                           file.path(case_dir, "sample_partitions.csv.gz"))
        frequencies <- data.table::rbindlist(lapply(features, function(name) {
          v <- d[[name]]
          if (!(name %in% categorical_vars) && data.table::uniqueN(v) > 30) return(NULL)
          v <- as.character(v)
          v[is.na(v) | trimws(v) == ""] <- "Missing"
          tab <- as.data.frame(table(v), stringsAsFactors = FALSE)
          data.frame(variable = name, level = tab$v, count = tab$Freq,
                     proportion = tab$Freq / length(v))
        }))
        data.table::fwrite(frequencies, file.path(case_dir, "categorical_frequencies.csv"))
        data.table::fwrite(d[, .(n = .N, positive = sum(get(outcome))), by = .(country_name, yrsurv)],
                           file.path(case_dir, "country_year_coverage.csv"))
        data.table::fwrite(
          data.frame(rowid = d[["__rowid"]][c(split$validation, split$test)],
                     partition = c(rep("validation", length(split$validation)),
                                   rep("test", length(split$test)))),
          file.path(case_dir, "heldout_rowids.csv")
        )
        write_descriptives(d, features, file.path(case_dir, "descriptive_statistics.csv"))
        if ("entrepreneurial_intention" %in% features) {
          intention_missing <- is.na(d$entrepreneurial_intention) |
            trimws(as.character(d$entrepreneurial_intention)) == ""
          data.table::fwrite(
            as.data.frame(table(outcome = y, intention_missing = intention_missing)),
            file.path(case_dir, "intention_missingness_by_outcome.csv")
          )
        }

        raw <- lapply(split, function(ids) as.data.frame(d[ids, ..features]))
        prep <- prepare_predictors(raw$train, raw$validation, raw$test, features)
        saveRDS(list(features = features, medians = prep$medians, levels = prep$levels),
                file.path(case_dir, "preprocessing.rds"))
        frames <- prep$parts
        matrices <- make_sparse_matrices(frames)
        targets <- lapply(split, function(ids) y[ids])
        data.table::fwrite(
          data.frame(variable = names(prep$medians),
                     training_median = unlist(prep$medians, use.names = FALSE)),
          file.path(case_dir, "training_imputation.csv")
        )
        curves <- list()
        performance <- list()
        confusions <- list()

        for (model in models_to_run) {
          started <- Sys.time()
          model_dir <- file.path(case_dir, "models", gsub("[^a-z0-9]+", "_", tolower(model)))
          dir.create(model_dir, recursive = TRUE, showWarnings = FALSE)
          cache_file <- file.path(model_dir, "prediction_checkpoint.rds")
          from_cache <- FALSE
          package <- unname(packages_by_model[model])
          result <- tryCatch({
            if (!requireNamespace(package, quietly = TRUE)) {
              stop(sprintf("Required package %s is not installed", package))
            }
            if (resume && file.exists(cache_file)) {
              fitted <- readRDS(cache_file)
              from_cache <- TRUE
            } else {
              log_line(case_name, model, "fitting")
              fit_start <- Sys.time()
              fitted <- fit_predict_model(model, frames, matrices, targets,
                                          seed = 20260925L, h2o_ready = h2o_ready)
              fitted$fit_predict_seconds <- as.numeric(difftime(Sys.time(), fit_start, units = "secs"))
            }
            if (length(fitted$validation) != length(targets$validation) ||
                length(fitted$test) != length(targets$test) ||
                anyNA(fitted$validation) || anyNA(fitted$test)) {
              stop("Predictions have the wrong length or contain missing values")
            }
            threshold <- choose_threshold(targets$validation, fitted$validation)
            scored <- calculate_metrics(targets$test, fitted$test, threshold)
            if (!from_cache) {
              saveRDS(fitted, paste0(cache_file, ".tmp"))
              if (!file.rename(paste0(cache_file, ".tmp"), cache_file)) stop("Could not save prediction checkpoint")
            }
            for (partition in c("validation", "test")) {
              prediction <- fitted[[partition]]
              data.table::fwrite(data.frame(run_id = run_id, model = model,
                rowid = d[["__rowid"]][split[[partition]]], actual = targets[[partition]],
                probability = sprintf("%.17g", prediction), threshold = sprintf("%.17g", threshold),
                predicted = as.integer(prediction >= threshold)),
                file.path(model_dir, paste0(partition, "_predictions.csv.gz")))
            }
            data.table::fwrite(scored$curves$roc, file.path(model_dir, "roc_coordinates.csv.gz"))
            data.table::fwrite(scored$curves$pr, file.path(model_dir, "pr_coordinates.csv.gz"))
            perf <- data.frame(
              objective = objective, scope = scope, feature_set = feature_set,
              outcome = outcome, model = model,
              t(scored$values), check.names = FALSE
            )
            confusion <- data.frame(
              objective = objective, scope = scope, feature_set = feature_set,
              outcome = outcome, model = model,
              t(scored$counts), check.names = FALSE
            )
            perf$fit_predict_seconds <- fitted$fit_predict_seconds
            data.table::fwrite(perf, file.path(model_dir, "performance.csv"))
            data.table::fwrite(confusion, file.path(model_dir, "confusion_matrix.csv"))
            performance[[length(performance) + 1L]] <- perf
            confusions[[length(confusions) + 1L]] <- confusion
            curves[[model]] <- scored$curves
            if (model == "Random Forest" && !is.null(fitted$importance)) {
              importance <- fitted$importance
              data.table::fwrite(
                data.frame(variable = names(importance), importance = as.numeric(importance)),
                file.path(case_dir, "random_forest_importance.csv")
              )
              save_importance_plot(
                importance, file.path(case_dir, "random_forest_importance.png"),
                paste("Random forest importance:", case_name)
              )
              institutional <- legatum_vars
              if (length(institutional)) {
                nes_selected <- importance[names(importance) %in% nes_vars]
                data.table::fwrite(data.frame(variable=names(nes_selected),importance=as.numeric(nes_selected)),
                  file.path(case_dir,"nes_importance.csv"))
                save_importance_plot(nes_selected,file.path(case_dir,"nes_importance.png"),paste("NES importance:",case_name))
                selected <- importance[names(importance) %in% institutional]
                save_importance_plot(
                  selected, file.path(case_dir, "institutional_importance.png"),
                  paste("Institutional importance:", case_name)
                )
              }
            }
            list(ok = TRUE, error = "")
          }, error = function(e) list(ok = FALSE, error = conditionMessage(e)))
          if (model == "H2O GBM" && h2o_ready) {
            try(h2o::h2o.removeAll(), silent = TRUE)
          }
          seconds <- as.numeric(difftime(Sys.time(), started, units = "secs"))
          row <- data.frame(
            objective = objective, scope = scope, feature_set = feature_set,
            outcome = outcome, model = model,
            status = if (result$ok) "success" else "failed",
            seconds = seconds, from_cache = from_cache, error = result$error
          )
          data.table::fwrite(row, file.path(model_dir, "status.csv"))
          write_status(row)
          log_line(case_name, model, row$status, sprintf("%.1f sec", seconds),
                   result$error)
        }
        case_ok <- length(performance) == length(models_to_run) &&
          all(vapply(tail(model_status, length(models_to_run)), function(r) r$status == "success", logical(1)))
        if (length(performance)) {
          table <- data.table::rbindlist(performance, fill = TRUE)
          table <- table[order(-table$auc_roc), ]
          data.table::fwrite(table, file.path(case_dir, "classifier_performance.csv"))
          data.table::fwrite(table, performance_file,
                             append = file.exists(performance_file),
                             col.names = !file.exists(performance_file))
          data.table::fwrite(data.table::rbindlist(confusions),
                             file.path(case_dir, "confusion_matrices.csv"))
          save_curve_plot(curves, file.path(case_dir, "roc_curves.png"), "roc",
                          paste("ROC curves:", case_name))
          save_curve_plot(curves, file.path(case_dir, "precision_recall_curves.png"),
                          "pr", paste("Precision-recall curves:", case_name))
        }
        queue$status[queue_index] <- if (case_ok) "complete" else "failed"
        queue$finished[queue_index] <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
        data.table::fwrite(queue, file.path(output, "run_queue.csv"))
        if (case_ok) writeLines("All requested models and output exports succeeded", file.path(case_dir, "case_complete.txt"))
        rm(d, raw, prep, frames, matrices, targets, curves, performance, confusions)
        gc(verbose = FALSE)
      }
    }
  }
}

data.table::fwrite(data.table::rbindlist(all_sample_counts),
                   file.path(output, "all_sample_counts.csv"))
if (file.exists(performance_file)) {
  perf <- data.table::fread(performance_file)
  baseline_performance <- if (!is.null(args$baseline_performance)) args$baseline_performance else ""
  if (nzchar(baseline_performance) && file.exists(baseline_performance)) {
    baseline <- data.table::fread(baseline_performance)
    baseline <- baseline[feature_set == "iv_cv"]
    comparison <- merge(baseline,perf,by=c("objective","scope","outcome","model"),
                        suffixes=c("_iv_cv","_iv_cv_nes"))
    if (nrow(comparison) != nrow(perf)) stop("Missing original controls performance for NES comparison")
    data.table::fwrite(comparison,file.path(output,"feature_set_comparison.csv"))
  }

}

model_notes <- data.frame(
  model = model_names,
  feature = c(
    "Logistic probability model with a small fixed stabilizing penalty",
    "Logistic model with L1 shrinkage",
    "Logistic model with L2 shrinkage",
    "Logistic model with mixed L1 and L2 shrinkage",
    "Probabilistic classifier using conditional feature distributions",
    "Single classification tree",
    "Gradient boosted trees",
    "Gradient boosted trees with native categorical handling",
    "Ensemble of randomized decision trees",
    "H2O gradient boosted trees"
  ),
  advantage = c(
    "Clear probability baseline", "Can select predictors", "Stable with correlated predictors",
    "Can select predictors while handling correlation", "Fast baseline", "Simple to inspect",
    "Strong nonlinear benchmark", "Handles categorical predictors", "Strong nonlinear benchmark",
    "Scalable distributed implementation"
  ),
  limitation = c(
    "Small fixed penalty stabilizes the logistic baseline",
    "May select one of several correlated predictors", "Does not select predictors",
    "Requires tuning two penalty components", "Assumes conditional feature independence",
    "Can be unstable and less accurate", "Requires tuning and more compute",
    "Requires separate installation and more compute", "Requires more memory and compute",
    "Requires Java and a local H2O service"
  )
)
if (file.exists(status_file)) {
  times <- data.table::fread(status_file)[status == "success",
    .(successful_runs = .N, total_seconds = sum(seconds)), by = model]
  model_notes <- merge(model_notes, times, by = "model", all.x = TRUE, sort = FALSE)
}
data.table::fwrite(model_notes, file.path(output, "appendix_A2_models.csv"))

if (h2o_ready) try(h2o::h2o.shutdown(prompt = FALSE), silent = TRUE)
failed <- sum(vapply(model_status, function(row) row$status == "failed", logical(1)))
log_line("Finished. Model successes:", length(model_status) - failed,
         "failures:", failed)
if (failed > 0L) {
  stop(sprintf("%d required model runs failed; inspect model_status.csv", failed))
}
writeLines(format(Sys.time(), "%Y-%m-%d %H:%M:%S"),
           file.path(output, "pipeline_complete.txt"))
