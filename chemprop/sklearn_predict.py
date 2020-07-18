import csv
import pickle

import numpy as np
from tqdm import tqdm

from chemprop.args import SklearnPredictArgs, SklearnTrainArgs
from chemprop.data import get_data
from chemprop.features import get_features_generator
from chemprop.sklearn_train import predict
from chemprop.utils import makedirs


def predict_sklearn(args: SklearnPredictArgs):
    print('Loading data')
    data = get_data(path=args.test_path, smiles_column=args.smiles_column, target_columns=[])

    print('Loading training arguments')
    with open(args.checkpoint_paths[0], 'rb') as f:
        model = pickle.load(f)
        train_args: SklearnTrainArgs = SklearnTrainArgs().from_dict(model.train_args, skip_unsettable=True)

    print('Computing morgan fingerprints')
    morgan_fingerprint = get_features_generator('morgan')
    for datapoint in tqdm(data, total=len(data)):
        datapoint.set_features(morgan_fingerprint(mol=datapoint.smiles, radius=train_args.radius, num_bits=train_args.num_bits))

    print(f'Predicting with an ensemble of {len(args.checkpoint_paths)} models')
    sum_preds = np.zeros((len(data), train_args.num_tasks))

    for checkpoint_path in tqdm(args.checkpoint_paths, total=len(args.checkpoint_paths)):
        with open(checkpoint_path, 'rb') as f:
            model = pickle.load(f)

        model_preds = predict(
            model=model,
            model_type=train_args.model_type,
            dataset_type=train_args.dataset_type,
            features=data.features()
        )
        sum_preds += np.array(model_preds)

    # Ensemble predictions
    avg_preds = sum_preds / len(args.checkpoint_paths)
    avg_preds = avg_preds.tolist()

    print(f'Saving predictions to {args.preds_path}')
    assert len(data) == len(avg_preds)
    makedirs(args.preds_path, isfile=True)

    # Copy predictions over to data
    for datapoint, preds in zip(data, avg_preds):
        for pred_name, pred in zip(train_args.task_names, preds):
            datapoint.row[pred_name] = pred

    # Save
    with open(args.preds_path, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].row.keys())
        writer.writeheader()

        for datapoint in data:
            writer.writerow(datapoint.row)


def sklearn_predict() -> None:
    """Runs sklearn predicting."""
    predict_sklearn(SklearnPredictArgs().parse_args())
