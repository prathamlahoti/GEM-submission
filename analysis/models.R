fit_predict_model <- function(name, frames, matrices, y, seed, h2o_ready = FALSE) {
  x_train <- frames$train
  x_val <- frames$validation
  x_test <- frames$test
  m_train <- matrices$train
  m_val <- matrices$validation
  m_test <- matrices$test
  y_train <- y$train
  y_val <- y$validation

  if (name == "Logistic Regression") {
    # A small fixed ridge penalty keeps the baseline finite when intention
    # missingness separates the outcome in this survey.
    fit <- glmnet::glmnet(m_train, y_train, family = "binomial", alpha = 0,
                          lambda = exp(seq(log(1), log(0.001), length.out = 50)),
                          standardize = TRUE, control = list(maxit = 1000000))
    return(list(
      validation = as.numeric(stats::predict(fit, m_val, type = "response", s = 0.001)),
      test = as.numeric(stats::predict(fit, m_test, type = "response", s = 0.001))
    ))
  }

  if (name %in% c("Lasso", "Ridge", "Elastic Net")) {
    alpha <- switch(name, Lasso = 1, Ridge = 0, `Elastic Net` = 0.5)
    set.seed(seed)
    fit <- glmnet::cv.glmnet(m_train, y_train, family = "binomial",
                             alpha = alpha, nfolds = 3,
                             type.measure = "auc", parallel = FALSE)
    return(list(
      validation = as.numeric(stats::predict(fit, m_val, type = "response", s = "lambda.min")),
      test = as.numeric(stats::predict(fit, m_test, type = "response", s = "lambda.min"))
    ))
  }

  if (name == "Naive Bayes") {
    fit <- e1071::naiveBayes(x = x_train,
                             y = factor(y_train, levels = c(0, 1)))
    return(list(
      validation = as.numeric(stats::predict(fit, x_val, type = "raw")[, "1"]),
      test = as.numeric(stats::predict(fit, x_test, type = "raw")[, "1"])
    ))
  }

  if (name == "Decision Tree") {
    training <- x_train
    training$.outcome <- factor(y_train, levels = c(0, 1))
    fit <- rpart::rpart(.outcome ~ ., data = training, method = "class",
                        control = rpart::rpart.control(cp = 0.001,
                                                        minsplit = 50,
                                                        maxdepth = 12, xval = 0))
    return(list(
      validation = as.numeric(stats::predict(fit, x_val, type = "prob")[, "1"]),
      test = as.numeric(stats::predict(fit, x_test, type = "prob")[, "1"])
    ))
  }

  if (name == "XGBoost") {
    train_matrix <- xgboost::xgb.DMatrix(m_train, label = y_train)
    val_matrix <- xgboost::xgb.DMatrix(m_val, label = y_val)
    fit <- xgboost::xgb.train(
      params = list(objective = "binary:logistic", eval_metric = "auc",
                    eta = 0.08, max_depth = 5, subsample = 0.8,
                    colsample_bytree = 0.8, nthread = 4, seed = seed),
      data = train_matrix, nrounds = 250,
      evals = list(validation = val_matrix), early_stopping_rounds = 20,
      verbose = 0
    )
    return(list(
      validation = as.numeric(stats::predict(fit, m_val)),
      test = as.numeric(stats::predict(fit, m_test))
    ))
  }

  if (name == "CatBoost") {
    train_pool <- catboost::catboost.load_pool(x_train, label = y_train)
    val_pool <- catboost::catboost.load_pool(x_val, label = y_val)
    test_pool <- catboost::catboost.load_pool(x_test)
    fit <- catboost::catboost.train(
      learn_pool = train_pool, test_pool = val_pool,
      params = list(loss_function = "Logloss", eval_metric = "AUC",
                    iterations = 250, depth = 6, learning_rate = 0.08,
                    random_seed = seed, thread_count = 4,
                    early_stopping_rounds = 20, use_best_model = TRUE,
                    logging_level = "Silent", allow_writing_files = FALSE)
    )
    return(list(
      validation = as.numeric(catboost::catboost.predict(fit, val_pool,
                                                         prediction_type = "Probability")),
      test = as.numeric(catboost::catboost.predict(fit, test_pool,
                                                   prediction_type = "Probability"))
    ))
  }

  if (name == "Random Forest") {
    training <- x_train
    training$.outcome <- factor(y_train, levels = c(0, 1))
    fit <- ranger::ranger(
      dependent.variable.name = ".outcome", data = training,
      probability = TRUE, num.trees = 200, min.node.size = 20,
      importance = "impurity", num.threads = 4, seed = seed,
      respect.unordered.factors = "order"
    )
    return(list(
      validation = as.numeric(stats::predict(fit, data = x_val)$predictions[, "1"]),
      test = as.numeric(stats::predict(fit, data = x_test)$predictions[, "1"]),
      importance = fit$variable.importance
    ))
  }

  if (name == "H2O GBM") {
    if (!h2o_ready) stop("H2O cluster was not initialized")
    training <- x_train
    validation <- x_val
    testing <- x_test
    training$.outcome <- factor(y_train, levels = c(0, 1))
    validation$.outcome <- factor(y_val, levels = c(0, 1))
    testing$.outcome <- factor(y$test, levels = c(0, 1))
    h_train <- h2o::as.h2o(training)
    h_val <- h2o::as.h2o(validation)
    h_test <- h2o::as.h2o(testing)
    fit <- h2o::h2o.gbm(
      x = colnames(x_train), y = ".outcome",
      training_frame = h_train, validation_frame = h_val,
      ntrees = 250, max_depth = 5, learn_rate = 0.08,
      sample_rate = 0.8, col_sample_rate = 0.8,
      stopping_rounds = 5, stopping_metric = "AUC", stopping_tolerance = 0.001,
      score_tree_interval = 5, seed = seed
    )
    result <- list(
      validation = as.numeric(as.data.frame(h2o::h2o.predict(fit, h_val))$p1),
      test = as.numeric(as.data.frame(h2o::h2o.predict(fit, h_test))$p1)
    )
    h2o::h2o.removeAll()
    return(result)
  }

  stop(sprintf("Unknown model: %s", name))
}
