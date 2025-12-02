#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
organize_subjects.py - Simple subject train/test split from Excel

This script reads an Excel file with subject IDs and train/test assignments,
then creates CSV files for the pipeline to use.

REQUIRED EXCEL COLUMNS:
- Subject ID column (configurable via SUBJECT_ID_COL in config.sh)
- Split column (configurable via SPLIT_COL in config.sh) with values "train" or "test"

OPTIONAL EXCEL COLUMNS:
- Any other columns you want (diagnosis, age, site, etc.) - will be preserved in output CSVs

That's it! Do your own stratification/splitting logic outside this script,
then provide the final subject assignments.
"""

import os
import argparse
import pandas as pd
from read_config import METADATA_EXCEL, SUBJECT_ID_COL, SPLIT_COL


def main():
    ap = argparse.ArgumentParser(
        description="Simple train/test split from Excel with subject assignments"
    )
    ap.add_argument(
        "--excel",
        default=METADATA_EXCEL,
        help="Path to metadata Excel (default from config.sh)"
    )
    ap.add_argument(
        "--subject_col",
        default=SUBJECT_ID_COL,
        help="Column name for subject IDs (default from config.sh)"
    )
    ap.add_argument(
        "--split_col",
        default=SPLIT_COL,
        help="Column name for train/test split (default from config.sh)"
    )
    ap.add_argument(
        "--out_prefix",
        default="",
        help="Optional prefix for output CSVs"
    )
    args = ap.parse_args()

    # Load Excel
    print(f"[info] Reading Excel: {args.excel}")
    df = pd.read_excel(args.excel)

    # Check required columns exist
    if args.subject_col not in df.columns:
        raise KeyError(
            f"Subject ID column '{args.subject_col}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    if args.split_col not in df.columns:
        raise KeyError(
            f"Split column '{args.split_col}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    # Normalize subject IDs to sub-XXXXX format
    df["subject_id"] = df[args.subject_col].astype(str).str.strip()

    # Normalize split column values
    df["split"] = df[args.split_col].astype(str).str.strip().str.lower()

    # Validate split values
    valid_splits = {"train", "test"}
    invalid_splits = set(df["split"].unique()) - valid_splits
    if invalid_splits:
        raise ValueError(
            f"Invalid split values found: {invalid_splits}. "
            f"Only 'train' or 'test' allowed (case-insensitive)."
        )

    # Separate into train and test
    df_train = df[df["split"] == "train"].copy()
    df_test = df[df["split"] == "test"].copy()

    if len(df_train) == 0:
        raise ValueError("No subjects assigned to 'train' split!")

    if len(df_test) == 0:
        raise ValueError("No subjects assigned to 'test' split!")

    # Save CSVs
    prefix = args.out_prefix
    train_file = f"{prefix}cha_train.csv"
    test_file = f"{prefix}test_pool.csv"

    df_train.to_csv(train_file, index=False)
    df_test.to_csv(test_file, index=False)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total subjects: {len(df)}")
    print(f"Train subjects: {len(df_train)} ({len(df_train)/len(df)*100:.1f}%)")
    print(f"Test subjects:  {len(df_test)} ({len(df_test)/len(df)*100:.1f}%)")
    print()
    print(f"Output files:")
    print(f"  - {train_file}")
    print(f"  - {test_file}")
    print("="*60)

    # Show first few subjects from each split
    print("\nSample train subjects:")
    print(df_train["subject_id"].head(10).to_string(index=False))
    print(f"\n... ({len(df_train)} total)")

    print("\nSample test subjects:")
    print(df_test["subject_id"].head(10).to_string(index=False))
    print(f"\n... ({len(df_test)} total)")


if __name__ == "__main__":
    main()
