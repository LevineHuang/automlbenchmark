import logging
import os
import tempfile as tmp

os.environ['JOBLIB_TEMP_FOLDER'] = tmp.gettempdir()
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from amlb.benchmark import TaskConfig
from amlb.data import Dataset
from amlb.datautils import impute
from amlb.results import save_predictions_to_file
from amlb.utils import Timer

log = logging.getLogger(__name__)


def run(dataset: Dataset, config: TaskConfig):
    log.info("\n**** Random Forest (sklearn) ****\n")

    is_classification = config.type == 'classification'

    X_train, X_test = impute(dataset.train.X_enc, dataset.test.X_enc)
    y_train, y_test = dataset.train.y_enc, dataset.test.y_enc

    training_params = {k: v for k, v in config.framework_params.items() if not k.startswith('_')}
    n_jobs = config.framework_params.get('_n_jobs', config.cores)  # useful to disable multicore, regardless of the dataset config

    log.info("Running RandomForest with a maximum time of {}s on {} cores.".format(config.max_runtime_seconds, n_jobs))
    log.warning("We completely ignore the requirement to stay within the time limit.")
    log.warning("We completely ignore the advice to optimize towards metric: {}.".format(config.metric))

    estimator = RandomForestClassifier if is_classification else RandomForestRegressor
    rf = estimator(n_jobs=n_jobs,
                   random_state=config.seed,
                   **training_params)

    with Timer() as training:
        rf.fit(X_train, y_train)

    predictions = rf.predict(X_test)
    probabilities = rf.predict_proba(X_test) if is_classification else None

    save_predictions_to_file(dataset=dataset,
                             output_file=config.output_predictions_file,
                             probabilities=probabilities,
                             predictions=predictions,
                             truth=y_test,
                             target_is_encoded=True)

    return dict(
        models_count=len(rf),
        training_duration=training.duration
    )
