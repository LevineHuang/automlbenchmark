import logging
import sys

from amlb.benchmark import TaskConfig
from amlb.data import Dataset
from amlb.datautils import Encoder, impute
from amlb.results import NoResultError, save_predictions_to_file
from amlb.utils import Timer, dir_of

sys.path.append("{}/lib/oboe/automl".format(dir_of(__file__)))
from auto_learner import AutoLearner

log = logging.getLogger(__name__)


def run(dataset: Dataset, config: TaskConfig):
    log.info("\n**** Oboe ****\n")

    is_classification = config.type == 'classification'
    if not is_classification:
        # regression currently fails (as of 26.02.2019: still under development state by oboe team)
        raise ValueError('Regression is not yet supported (under development).')

    X_train, X_test = impute(dataset.train.X_enc, dataset.test.X_enc)
    y_train, y_test = dataset.train.y_enc, dataset.test.y_enc

    training_params = {k: v for k, v in config.framework_params.items() if not k.startswith('_')}
    n_cores = config.framework_params.get('_n_cores', config.cores)

    log.info('Running oboe with a maximum time of {}s on {} cores.'.format(config.max_runtime_seconds, n_cores))
    log.warning('We completely ignore the advice to optimize towards metric: {}.'.format(config.metric))

    aml = AutoLearner(p_type='classification' if is_classification else 'regression',
                      n_cores=n_cores,
                      runtime_limit=config.max_runtime_seconds,
                      **training_params)

    aml_models = lambda: [aml.ensemble, *aml.ensemble.base_learners] if len(aml.ensemble.base_learners) > 0 else []

    with Timer() as training:
        try:
            aml.fit(X_train, y_train)
        except IndexError as e:
            if len(aml_models()) == 0:  # incorrect handling of some IndexError in oboe if ensemble is empty
                raise NoResultError("Oboe could not produce any model in the requested time.") from e
            raise e

    predictions = aml.predict(X_test).reshape(len(X_test))

    if is_classification:
        target_values_enc = dataset.target.label_encoder.transform(dataset.target.values)
        probabilities = Encoder('one-hot', target=False, encoded_type=float).fit(target_values_enc).transform(predictions)
    else:
        probabilities = None

    save_predictions_to_file(dataset=dataset,
                             output_file=config.output_predictions_file,
                             probabilities=probabilities,
                             predictions=predictions,
                             truth=y_test,
                             target_is_encoded=True)

    return dict(
        models_count=len(aml_models()),
        training_duration=training.duration
    )
