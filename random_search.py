import torch
import numpy as np
import random
import json
from pprint import pprint

from argus.callbacks import MonitorCheckpoint, \
    EarlyStopping, LoggingToFile, ReduceLROnPlateau

from torch.utils.data import DataLoader

from src.datasets import FreesoundDataset, get_folds_data
from src.transforms import get_transforms
from src.argus_models import FreesoundModel
from src import config


EXPERIMENT_NAME = 'feature_extractor_rs_001'
VAL_FOLDS = [0]
TRAIN_FOLDS = [1, 2, 3, 4]
CROP_SIZE = 128
SAVE_DIR = config.experiments_dir / EXPERIMENT_NAME
START_FROM = 25


if __name__ == "__main__":
    print("Start load train data")
    folds_data = get_folds_data()

    for i in range(START_FROM, 10000):
        experiment_dir = SAVE_DIR / f'{i:04}'
        np.random.seed(i)
        random.seed(i)
        random_params = {
            'p_dropout': float(np.random.uniform(0.0, 0.5)),
            'batch_size': int(np.random.choice([64, 128, 256, 512])),
            'base_size': int(np.random.choice([16, 32, 64])),
            'lr': float(np.random.choice([0.003, 0.001, 0.0003])),
            'patience': int(np.random.randint(10, 40)),
            'factor': float(np.random.uniform(0.5, 0.8)),
        }
        pprint(random_params)

        params = {
            'nn_module': ('FeatureExtractor', {
                'num_classes': len(config.classes),
                'input_channels': 3,
                'base_size': random_params['base_size'],
                'dropout': random_params['p_dropout']
            }),
            'loss': 'BCEWithLogitsLoss',
            'optimizer': ('Adam', {'lr': random_params['lr']}),
            'device': 'cuda'
        }
        pprint(params)
        try:
            train_dataset = FreesoundDataset(folds_data, TRAIN_FOLDS,
                                             get_transforms(True, CROP_SIZE))
            val_dataset = FreesoundDataset(folds_data, VAL_FOLDS,
                                           get_transforms(False, CROP_SIZE))
            train_loader = DataLoader(train_dataset, batch_size=random_params['batch_size'],
                                      shuffle=True, drop_last=True, num_workers=4)
            val_loader = DataLoader(val_dataset, batch_size=random_params['batch_size'],
                                    shuffle=False, num_workers=4)

            model = FreesoundModel(params)

            callbacks = [
                MonitorCheckpoint(experiment_dir, monitor='val_lwlrap', max_saves=1),
                ReduceLROnPlateau(monitor='val_lwlrap',
                                  patience=random_params['patience'],
                                  factor=random_params['factor'],
                                  min_lr=1e-8),
                EarlyStopping(monitor='val_lwlrap', patience=50),
                LoggingToFile(experiment_dir / 'log.txt'),
            ]

            with open(experiment_dir / 'random_params.json', 'w') as outfile:
                json.dump(random_params, outfile)

            model.fit(train_loader,
                      val_loader=val_loader,
                      max_epochs=300,
                      callbacks=callbacks,
                      metrics=['multi_accuracy', 'lwlrap'])
        except KeyboardInterrupt as e:
            print("Keyboard interrupt")
            break
        except BaseException as e:
            print(f"Exception '{e}' with random params '{random_params}'")

        model = None
        torch.cuda.empty_cache()