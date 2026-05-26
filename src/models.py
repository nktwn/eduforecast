"""Model definitions: RandomForest, LSTM (PyTorch), and TFT wrapper."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import RandomForestClassifier

from .config import MODEL_PARAMS

# ── Random Forest ──────────────────────────────────────────────────────────────


class RandomForestModel:
    """Thin wrapper around scikit-learn RandomForestClassifier.

    Parameters
    ----------
    params:
        Hyperparameter dict. Defaults to ``config.MODEL_PARAMS["random_forest"]``.
    """

    def __init__(self, params: Optional[dict] = None) -> None:
        self.params = params or MODEL_PARAMS["random_forest"]
        self.model = RandomForestClassifier(**self.params)

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "RandomForestModel":
        """Fit the Random Forest on training data.

        Parameters
        ----------
        X_train:
            Feature matrix, shape ``(n_samples, n_features)``.
        y_train:
            Binary target vector, shape ``(n_samples,)``.
        """
        self.model.fit(X_train, y_train)
        return self

    def predict(self, X_test: np.ndarray) -> np.ndarray:
        """Return hard (thresholded) class predictions."""
        return self.model.predict(X_test)

    def predict_proba(self, X_test: np.ndarray) -> np.ndarray:
        """Return class probabilities, shape ``(n_samples, 2)``."""
        return self.model.predict_proba(X_test)

    def get_feature_importance(self) -> np.ndarray:
        """Return mean decrease in impurity for each feature."""
        return self.model.feature_importances_


# ── LSTM ───────────────────────────────────────────────────────────────────────


class LSTMModel(nn.Module):
    """Stacked LSTM binary classifier implemented in PyTorch.

    Parameters
    ----------
    input_size:
        Number of input features per time-step.
    hidden_size:
        Number of hidden units per LSTM layer.
    num_layers:
        Number of stacked LSTM layers.
    dropout:
        Dropout probability applied between LSTM layers (ignored if
        ``num_layers == 1``).
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Parameters
        ----------
        x:
            Input tensor of shape ``(batch, seq_len, input_size)``.

        Returns
        -------
        Logits tensor of shape ``(batch, 1)``.
        """
        # lstm_out: (batch, seq_len, hidden_size)
        lstm_out, _ = self.lstm(x)
        # Use only the last time-step representation
        last_hidden = self.dropout(lstm_out[:, -1, :])
        return self.fc(last_hidden)


# ── Temporal Fusion Transformer ────────────────────────────────────────────────


class TFTModel:
    """Wrapper around ``pytorch_forecasting.TemporalFusionTransformer``.

    pytorch-forecasting must be installed separately:

        pip install pytorch-forecasting

    If installation fails (e.g., dependency conflicts), try:

        pip install pytorch-forecasting --no-deps
        pip install lightning einops

    Parameters
    ----------
    params:
        Hyperparameter dict. Defaults to ``config.MODEL_PARAMS["tft"]``.
    """

    def __init__(self, params: Optional[dict] = None) -> None:
        self.params = params or MODEL_PARAMS["tft"]
        self._model: Any = None
        self._trainer: Any = None

    def prepare_dataset(self, df: "pd.DataFrame") -> Any:  # noqa: F821
        """Create a ``TimeSeriesDataSet`` from a long-format feature DataFrame.

        Parameters
        ----------
        df:
            Must contain columns: ``time_idx`` (int), ``group_id`` (str),
            target column, and any covariates.

        Returns
        -------
        ``pytorch_forecasting.TimeSeriesDataSet`` instance.
        """
        try:
            from pytorch_forecasting import TimeSeriesDataSet
        except ImportError as exc:
            raise ImportError(
                "pytorch-forecasting is required for TFTModel. "
                "Install with: pip install pytorch-forecasting"
            ) from exc

        dataset = TimeSeriesDataSet(
            df,
            time_idx="time_idx",
            target="weekly_clicks",
            group_ids=["id_student", "code_module", "code_presentation"],
            max_encoder_length=self.params.get("max_encoder_length", 20),
            max_prediction_length=self.params.get("max_prediction_length", 4),
            time_varying_known_reals=["time_idx"],
            time_varying_unknown_reals=["weekly_clicks"],
        )
        return dataset

    def fit(self, train_df: "pd.DataFrame", val_df: "pd.DataFrame") -> "TFTModel":
        """Build and train the TFT model.

        Parameters
        ----------
        train_df:
            Training split in long format (see :meth:`prepare_dataset`).
        val_df:
            Validation split in long format.
        """
        try:
            import pytorch_lightning as pl
            from pytorch_forecasting import TemporalFusionTransformer
            from pytorch_forecasting.metrics import QuantileLoss
        except ImportError as exc:
            raise ImportError(
                "pytorch-forecasting and pytorch-lightning are required. "
                "Install with: pip install pytorch-forecasting pytorch-lightning"
            ) from exc

        train_dataset = self.prepare_dataset(train_df)
        val_dataset = self.prepare_dataset(val_df)

        train_loader = train_dataset.to_dataloader(
            train=True, batch_size=self.params["batch_size"], num_workers=0
        )
        val_loader = val_dataset.to_dataloader(
            train=False, batch_size=self.params["batch_size"], num_workers=0
        )

        self._model = TemporalFusionTransformer.from_dataset(
            train_dataset,
            learning_rate=self.params["learning_rate"],
            hidden_size=self.params["hidden_size"],
            attention_head_size=self.params["attention_head_size"],
            dropout=self.params["dropout"],
            loss=QuantileLoss(),
        )

        self._trainer = pl.Trainer(max_epochs=self.params["epochs"], enable_progress_bar=True)
        self._trainer.fit(self._model, train_loader, val_loader)
        return self

    def predict(self, test_df: "pd.DataFrame") -> np.ndarray:
        """Generate predictions on *test_df*.

        Parameters
        ----------
        test_df:
            Test split in long format (see :meth:`prepare_dataset`).

        Returns
        -------
        Numpy array of predictions.
        """
        if self._model is None:
            raise RuntimeError("Call fit() before predict().")
        test_dataset = self.prepare_dataset(test_df)
        test_loader = test_dataset.to_dataloader(
            train=False, batch_size=self.params["batch_size"], num_workers=0
        )
        predictions = self._trainer.predict(self._model, test_loader)
        return np.concatenate([p.numpy() for p in predictions])
