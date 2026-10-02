from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from .config import TARGET_COLUMN


class FeatureEngineer:
    _CATEGORICAL_COLS: list[str] = [
        "gender",
        "region",
        "highest_education",
        "imd_band",
        "age_band",
        "disability",
    ]

    def __init__(self) -> None:
        self._encoders: dict[str, LabelEncoder] = {}


    def create_weekly_clicks(self, student_vle_df: pd.DataFrame) -> pd.DataFrame:
        df = student_vle_df.copy()
        df["week"] = np.ceil(df["date"] / 7).astype(int)
        weekly = (
            df.groupby(
                ["id_student", "code_module", "code_presentation", "week"],
                as_index=False,
            )["sum_click"]
            .sum()
            .rename(columns={"sum_click": "weekly_clicks"})
        )
        print(f"Weekly clicks: {weekly.shape[0]:,} rows, "
              f"{weekly['week'].nunique()} distinct weeks")
        return weekly


    def create_target_variable(self, student_info_df: pd.DataFrame) -> pd.DataFrame:
        df = student_info_df.copy()
        df[TARGET_COLUMN] = (df["final_result"] == "Withdrawn").astype(int)
        rate = df[TARGET_COLUMN].mean() * 100
        print(f"Withdrawal rate: {rate:.1f}%  "
              f"({df[TARGET_COLUMN].sum():,} at-risk / {len(df):,} total)")
        return df


    def create_static_features(
        self, student_info_df: pd.DataFrame
    ) -> pd.DataFrame:
        df = student_info_df.copy()
        for col in self._CATEGORICAL_COLS:
            if col not in df.columns:
                continue
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            self._encoders[col] = le

        keep_cols = (
            ["id_student", "code_module", "code_presentation"]
            + self._CATEGORICAL_COLS
            + ["num_of_prev_attempts", "studied_credits"]
        )
        keep_cols = [c for c in keep_cols if c in df.columns]
        print(f"Static features: {len(keep_cols)} columns retained")
        return df[keep_cols]


    def create_assessment_features(
        self,
        student_assessment_df: pd.DataFrame,
        assessments_df: pd.DataFrame,
    ) -> pd.DataFrame:
        merged = student_assessment_df.merge(
            assessments_df[["id_assessment", "date", "assessment_type", "weight"]],
            on="id_assessment",
            how="left",
        )
        merged["score"] = merged["score"].fillna(0).clip(0, 100)
        merged["submitted_on_time"] = (
            merged["date_submitted"] <= merged["date"]
        ).astype(int)
        print(f"Assessment features: {merged.shape[0]:,} rows, "
              f"{merged['id_student'].nunique():,} unique students")
        return merged


    def build_feature_matrix(
        self,
        weekly_clicks: pd.DataFrame,
        static_features: pd.DataFrame,
        assessment_features: pd.DataFrame,
        target: pd.DataFrame,
    ) -> pd.DataFrame:
        join_keys = ["id_student", "code_module", "code_presentation"]

        clicks_wide = weekly_clicks.pivot_table(
            index=join_keys,
            columns="week",
            values="weekly_clicks",
            aggfunc="sum",
            fill_value=0,
        )
        clicks_wide.columns = [f"clicks_week_{w}" for w in clicks_wide.columns]
        clicks_wide = clicks_wide.reset_index()

        agg_assessments = (
            assessment_features.groupby(join_keys, as_index=False)
            .agg(
                mean_score=("score", "mean"),
                on_time_rate=("submitted_on_time", "mean"),
                num_assessments=("id_assessment", "count"),
            )
        )

        target_cols = join_keys + [TARGET_COLUMN]
        target_subset = target[
            [c for c in target_cols if c in target.columns]
        ].drop_duplicates(subset=join_keys)

        matrix = (
            target_subset
            .merge(static_features, on=join_keys, how="left")
            .merge(clicks_wide, on=join_keys, how="left")
            .merge(agg_assessments, on=join_keys, how="left")
        )
        matrix = matrix.fillna(0)

        print(f"Feature matrix: {matrix.shape[0]:,} rows × {matrix.shape[1]} columns")
        print(f"Columns: {list(matrix.columns)}")
        return matrix
