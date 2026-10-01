sct_vars <- c(
  "suskill_2015_2022", "opportunity_perception", "fearfail_2015_2022",
  "knowing_entrepreneur", "entrepreneurial_intention", "media_coverage",
  "discent", "busang", "established_business_owner", "good_career_choice",
  "ease_start_business", "high_status", "social_enterprise"
)
legatum_vars <- c(
  "prosperity_index_score", "safety__security", "personal_freedom",
  "governance", "social_capital", "investment_environment",
  "enterprise_conditions", "market_access__infrastructure",
  "economic_quality", "living_conditions", "health", "education",
  "natural_environment"
)
efw_vars <- c(
  "EFW", "EFW_quartile", "EFW_government", "EFW_legal", "EFW_money",
  "EFW_trade", "EFW_regulation"
)
control_vars <- c(
  "yrsurv", "age", "gender", "education_attainment", "household_income",
  "hhsize", "occupation_status", "gdp_per_capita_ppp",
  "population_totalthousands", "gdp_growth"
)
outcomes <- c("fearfail_2015_2022", "EXIT_ENT_harmonized")
model_names <- c(
  "Logistic Regression", "Lasso", "Ridge", "Elastic Net", "Naive Bayes",
  "Decision Tree", "XGBoost", "CatBoost", "Random Forest", "H2O GBM"
)
categorical_vars <- c(
  "entrepreneurial_intention", "EFW_quartile", "yrsurv", "gender",
  "education_attainment", "household_income", "occupation_status"
)

objective_features <- function(objective) {
  if (objective == 4L) return(c(setdiff(sct_vars, "fearfail_2015_2022"), legatum_vars))
  if (objective == 5L) return(c(setdiff(sct_vars, "discent"), legatum_vars))
  stop("Objective must be 4 or 5")
}
objective_outcome <- function(objective) {
  if (objective == 4L) "fearfail_2015_2022" else if (objective == 5L) "EXIT_ENT_harmonized" else stop("Invalid objective")
}

assert_binary <- function(x, name) {
  bad <- !is.na(x) & !(x %in% c(0, 1))
  if (any(bad)) stop(sprintf("%s has %s non-binary values", name, sum(bad)))
}

make_split <- function(y, seed = 20260925L) {
  if (anyNA(y)) stop("Make split after excluding missing outcomes")
  set.seed(seed)
  test <- integer()
  validation <- integer()
  for (cls in c(0, 1)) {
    ids <- which(y == cls)
    if (length(ids) < 20L) stop("At least 20 cases per outcome class are needed")
    ids <- sample(ids)
    n_test <- max(1L, floor(length(ids) * 0.20))
    n_val <- max(1L, floor(length(ids) * 0.12))
    test <- c(test, ids[seq_len(n_test)])
    validation <- c(validation, ids[seq.int(n_test + 1L, n_test + n_val)])
  }
  train <- setdiff(seq_along(y), c(test, validation))
  list(train = sort(train), validation = sort(validation), test = sort(test))
}

prepare_predictors <- function(train, validation, test, features) {
  parts <- list(train = train, validation = validation, test = test)
  medians <- list()
  levels_by_var <- list()
  for (name in features) {
    if (name %in% categorical_vars) {
      values <- as.character(train[[name]])
      values[is.na(values) | trimws(values) == ""] <- "Missing"
      lev <- sort(unique(c(values, "Missing")))
      if (name == "entrepreneurial_intention") {
        lev <- unique(c("0", "1", "Missing", lev))
      }
      levels_by_var[[name]] <- lev
      for (part in names(parts)) {
        v <- as.character(parts[[part]][[name]])
        v[is.na(v) | trimws(v) == "" | !(v %in% lev)] <- "Missing"
        parts[[part]][[name]] <- factor(v, levels = lev)
      }
    } else {
      v <- suppressWarnings(as.numeric(train[[name]]))
      med <- stats::median(v, na.rm = TRUE)
      if (!is.finite(med)) med <- 0
      medians[[name]] <- med
      for (part in names(parts)) {
        v <- suppressWarnings(as.numeric(parts[[part]][[name]]))
        missing <- !is.finite(v)
        v[missing] <- med
        parts[[part]][[name]] <- v
        parts[[part]][[paste0(name, "__missing")]] <- as.integer(missing)
      }
    }
  }
  for (part in names(parts)) {
    parts[[part]] <- as.data.frame(parts[[part]], optional = TRUE)
  }
  list(parts = parts, medians = medians, levels = levels_by_var)
}

make_sparse_matrices <- function(parts) {
  f <- stats::as.formula("~ . - 1")
  mats <- lapply(parts, function(d) Matrix::sparse.model.matrix(f, data = d))
  reference <- colnames(mats$train)
  for (name in c("validation", "test")) {
    if (!identical(colnames(mats[[name]]), reference)) {
      stop("Predictor matrix columns changed between data partitions")
    }
  }
  mats
}

confusion_counts <- function(y, p, threshold) {
  pred <- as.integer(p >= threshold)
  c(TP = sum(pred == 1 & y == 1), FP = sum(pred == 1 & y == 0),
    TN = sum(pred == 0 & y == 0), FN = sum(pred == 0 & y == 1))
}

safe_divide <- function(a, b) if (b == 0) NA_real_ else a / b

choose_threshold <- function(y, p) {
  candidates <- sort(unique(c(0.5, as.numeric(stats::quantile(
    p, probs = seq(0.01, 0.99, by = 0.01), na.rm = TRUE
  )))))
  scores <- vapply(candidates, function(threshold) {
    counts <- confusion_counts(y, p, threshold)
    safe_divide(2 * counts["TP"], 2 * counts["TP"] + counts["FP"] + counts["FN"])
  }, numeric(1))
  scores[!is.finite(scores)] <- -Inf
  candidates[which.max(scores)]
}

curve_points <- function(y, p) {
  if (length(y) != length(p) || anyNA(p) || any(!is.finite(p))) {
    stop("Invalid predicted probabilities")
  }
  if (!all(y %in% c(0, 1))) stop("Curve requires binary labels")
  n_pos <- sum(y == 1)
  n_neg <- sum(y == 0)
  if (n_pos == 0 || n_neg == 0) stop("Curve requires both classes")
  ordered <- order(p, decreasing = TRUE)
  y_ordered <- y[ordered]
  p_ordered <- p[ordered]
  ends <- which(!duplicated(p_ordered, fromLast = TRUE))
  tp <- cumsum(y_ordered == 1)[ends]
  fp <- cumsum(y_ordered == 0)[ends]
  recall <- tp / n_pos
  precision <- tp / (tp + fp)
  list(
    roc = data.frame(fpr = c(0, fp / n_neg), tpr = c(0, recall)),
    pr = data.frame(recall = c(0, recall), precision = c(1, precision))
  )
}

calculate_metrics <- function(y, p, threshold) {
  counts <- confusion_counts(y, p, threshold)
  curves <- curve_points(y, p)
  auc_roc <- sum(diff(curves$roc$fpr) *
                   (head(curves$roc$tpr, -1) + tail(curves$roc$tpr, -1)) / 2)
  # Stepwise precision-recall area (average precision); a constant score
  # correctly returns the positive-class prevalence.
  auc_pr <- sum(diff(curves$pr$recall) * tail(curves$pr$precision, -1))
  precision <- unname(safe_divide(counts["TP"], counts["TP"] + counts["FP"]))
  recall <- unname(safe_divide(counts["TP"], counts["TP"] + counts["FN"]))
  f1 <- unname(safe_divide(2 * counts["TP"],
                           2 * counts["TP"] + counts["FP"] + counts["FN"]))
  list(
    counts = counts, curves = curves,
    values = c(auc_roc = auc_roc, auc_pr = auc_pr, accuracy = mean((p >= threshold) == y),
               precision = precision, recall = recall, f1 = f1, threshold = threshold)
  )
}

save_curve_plot <- function(curves, path, kind, title) {
  if (length(curves) == 0L) return(invisible(NULL))
  grDevices::png(path, width = 1600, height = 1100, res = 160)
  on.exit(grDevices::dev.off(), add = TRUE)
  xname <- if (kind == "roc") "fpr" else "recall"
  yname <- if (kind == "roc") "tpr" else "precision"
  xlab <- if (kind == "roc") "False positive rate" else "Recall"
  ylab <- if (kind == "roc") "True positive rate" else "Precision"
  graphics::plot(NA, xlim = c(0, 1), ylim = c(0, 1), xlab = xlab, ylab = ylab,
                 main = title)
  colors <- grDevices::hcl.colors(length(curves), palette = "Dark 3")
  for (i in seq_along(curves)) {
    points <- curves[[i]][[kind]]
    keep <- unique(round(seq(1, nrow(points), length.out = min(1000, nrow(points)))))
    graphics::lines(points[[xname]][keep], points[[yname]][keep],
                    col = colors[i], lwd = 2)
  }
  if (kind == "roc") graphics::abline(0, 1, lty = 3, col = "gray")
  graphics::legend("bottomright", legend = names(curves), col = colors,
                   lwd = 2, cex = 0.75, bg = "white")
}

save_importance_plot <- function(importance, path, title) {
  values <- sort(importance, decreasing = TRUE)
  values <- head(values[is.finite(values)], 20)
  if (length(values) == 0L) return(invisible(NULL))
  grDevices::png(path, width = 1600, height = 1100, res = 160)
  on.exit(grDevices::dev.off(), add = TRUE)
  graphics::par(mar = c(5, 16, 5, 2))
  graphics::barplot(rev(values), horiz = TRUE, las = 1,
                    col = "steelblue", border = NA, main = title,
                    xlab = "Random forest impurity importance")
}

nes_vars <- c("financing", "govt_support", "taxes_bureaucracy", "govt_programs", "education_training", "commercial_infrastructure", "rd_transfer", "market_dynamics", "market_changes", "market_entry", "physical_infrastructure", "cultural_social_norms")
