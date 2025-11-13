#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
organize_subjects.py - Flexible subject selection for hyperalignment

This script reads metadata from an Excel file and creates train/test splits
for hyperalignment. Configuration is loaded from config.sh.

CUSTOMIZATION FOR YOUR DATASET:
1. Update config.sh with your Excel path and column names
2. Modify derive_dx_row() function (lines ~170-180) for your selection logic
3. Or skip this script and provide subject lists via TEST_SUBJECTS_LIST env var

Example: For a study with "CONTROL" and "PATIENT" columns instead of ASD/ADHD:
- Set SELECTION_COL_1="CONTROL" and SELECTION_COL_2="PATIENT" in config.sh
- Update derive_dx_row() to return "Control" or "Patient" based on your logic
"""

import os, re, glob, argparse
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from read_config import (
    METADATA_EXCEL, SUBJECT_ID_COL, SITE_COL, SEX_COL, AGE_COL, MOTION_COL,
    SELECTION_COL_1, SELECTION_COL_2, SELECTION_COL_3,
    TRAIN_FRACTION, CV_FOLDS,
    STRATIFY_BY_SITE, STRATIFY_BY_SEX, STRATIFY_BY_AGE, STRATIFY_BY_MOTION
)

# ---------------------------- Helpers ----------------------------

def to01(series_or_value):
    """
    Convert values to {0,1} robustly:
    NaN/None/'' -> 0; '1'/'true'/'yes' -> 1; numeric nonzero -> 1; zero -> 0.
    """
    s = pd.Series(series_or_value)
    s = pd.to_numeric(s, errors='coerce').fillna(0)
    return (s != 0).astype(int) if isinstance(series_or_value, (pd.Series, pd.Index)) else int((s.iloc[0] != 0))

def ensure_bins_numeric(series, bins=None, q=None, labels=None, default_label="all"):
    """
    Return categorical bins from a numeric series, or a single-bin fallback.
    """
    if series is None:
        return pd.Categorical([default_label] * 0, categories=[default_label])
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() < 5 or s.nunique(dropna=True) < 2:
        return pd.Categorical([default_label] * len(s), categories=[default_label])
    try:
        if bins is not None:
            return pd.cut(s, bins=bins, labels=labels, include_lowest=True)
        if q is not None:
            return pd.qcut(s, q=q, labels=labels, duplicates="drop")
    except Exception:
        pass
    return pd.Categorical([default_label] * len(s), categories=[default_label])

def normalize_sex(col):
    sx = col.astype(str).str.upper().str.strip()
    sx = sx.replace({"MALE":"M","FEMALE":"F"})
    sx = sx.where(sx.isin(["M","F"]), "O")
    return sx

def to_sub_id(eid):
    s = str(eid).strip()
    return s if s.startswith("sub-") else f"sub-{s}"

def norm_key(s):
    """
    Lowercase, drop leading 'sub-' and non-alphanumerics for robust matching.
    """
    if pd.isna(s): return ""
    s = str(s).strip().lower()
    s = re.sub(r'^sub-?', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def find_local_subjects(local_dir):
    """
    Return (nk2sub_local, local_subids):
      - nk2sub_local: dict norm_key -> actual 'sub-XXXX' ID
      - local_subids: set of actual 'sub-XXXX' IDs

    Handles:
      a) sub-*/**/*.dtseries.nii
      b) sub-*.dtseries.nii directly in local_dir (your case)
      c) any '*.dtseries.nii' where filename starts with 'sub-XXXX_...'
    """
    sub_ids = set()

    # a) sub-* directories present
    for p in glob.glob(os.path.join(local_dir, "sub-*")):
        b = os.path.basename(p)
        if b.startswith("sub-"):
            sub_ids.add(b)

    # b) files directly in the folder
    for f in glob.glob(os.path.join(local_dir, "sub-*.dtseries.nii")):
        base = os.path.basename(f)
        sub = base.split("_", 1)[0]  # 'sub-XXXX' before first underscore
        if sub.startswith("sub-"):
            sub_ids.add(sub)

    # c) nested files
    for f in glob.glob(os.path.join(local_dir, "sub-*", "**", "*.dtseries.nii"), recursive=True):
        base = os.path.basename(f)
        sub = base.split("_", 1)[0]
        if sub.startswith("sub-"):
            sub_ids.add(sub)

    nk2sub = {norm_key(s): s for s in sub_ids}
    return nk2sub, sub_ids

def choose_n_splits(labels, requested):
    """
    Ensure each class has at least n_splits samples; shrink if necessary.
    """
    vc = pd.Series(labels).value_counts()
    max_splits = int(vc.min()) if not vc.empty else 1
    return max(2, min(requested, max_splits))

# ---------------------------- Main ----------------------------

def main():
    ap = argparse.ArgumentParser(description="Diagnosis-agnostic, representative CHA train/test split + CV folds.")
    ap.add_argument("--excel", default=METADATA_EXCEL, help="Path to metadata Excel (default from config.sh)")
    ap.add_argument("--local_dir", default="ASD/CHA2/Data_mirror/HBN_rsfMRI_32k_sm5_gsr", help="Root with dtseries files")
    ap.add_argument("--train_frac", type=float, default=TRAIN_FRACTION, help="Fraction for CHA training (0-1, default from config.sh)")
    ap.add_argument("--folds", type=int, default=CV_FOLDS, help="Requested number of CV folds for test pool (default from config.sh)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--out_prefix", default="", help="Optional prefix for output CSVs")
    args = ap.parse_args()

    # right after: args = ap.parse_args()
    args.local_dir = os.path.abspath(os.path.expanduser(args.local_dir))
    print(f"[info] Using local_dir: {args.local_dir}")
    if not os.path.isdir(args.local_dir):
        raise RuntimeError(f"local_dir does not exist or is not a directory: {args.local_dir}")

    # Temporarily show a few matches to confirm the pattern
    print("[info] Probing for files...")
    print("  sub-* dirs:", len(glob.glob(os.path.join(args.local_dir, "sub-*"))))
    print("  sub-*.dtseries.nii (top-level):", len(glob.glob(os.path.join(args.local_dir, "sub-*.dtseries.nii"))))
    print("  **/*.dtseries.nii (recursive):", len(glob.glob(os.path.join(args.local_dir, "sub-*", "**", "*.dtseries.nii"), recursive=True)))


    # ---- Load Excel ----
    df = pd.read_excel(args.excel)

    # ---- Map known columns (from config.sh) ----
    if SUBJECT_ID_COL not in df.columns:
        raise KeyError(f"{SUBJECT_ID_COL} column not found. Available: {list(df.columns)}")

    # Optional columns - use config values if they exist and are not empty strings
    SITE_col   = SITE_COL   if SITE_COL   and SITE_COL   in df.columns else None
    SEX_col    = SEX_COL    if SEX_COL    and SEX_COL    in df.columns else None
    AGE_col    = AGE_COL    if AGE_COL    and AGE_COL    in df.columns else None
    MEANFD_col = MOTION_COL if MOTION_COL and MOTION_COL in df.columns else None

    # Selection columns - these are used for deriving groups/diagnosis
    SEL_col_1 = SELECTION_COL_1 if SELECTION_COL_1 and SELECTION_COL_1 in df.columns else None
    SEL_col_2 = SELECTION_COL_2 if SELECTION_COL_2 and SELECTION_COL_2 in df.columns else None
    SEL_col_3 = SELECTION_COL_3 if SELECTION_COL_3 and SELECTION_COL_3 in df.columns else None

    # ---- Excel-side normalized key and candidate subject_id ----
    df["EID_str"] = df[SUBJECT_ID_COL].astype(str).str.strip()
    df["nk"] = df["EID_str"].map(norm_key)
    df["subject_id_excel"] = df["EID_str"].map(to_sub_id)  # e.g., sub-NDARINV...

    # ---- Group/Diagnosis derivation (NaN-safe) ----
    # CUSTOMIZE THIS FUNCTION for your dataset:
    # For example, if you have "CONTROL" and "PATIENT" columns, update the logic below
    df["_sel01_1"] = to01(df[SEL_col_1]) if SEL_col_1 else 0
    df["_sel01_2"] = to01(df[SEL_col_2]) if SEL_col_2 else 0
    df["_sel01_3"] = to01(df[SEL_col_3]) if SEL_col_3 else 0

    def derive_dx_row(row):
        """
        CUSTOMIZE THIS FUNCTION for your dataset.

        Default logic for HBN ASD/ADHD dataset:
        - If both ASD and ADHD (or ASD+ADHD column is 1): "ASD+ADHD"
        - If only ASD: "ASD"
        - If only ADHD: "ADHD"
        - Otherwise: "TD" (Typically Developing)

        For other datasets, modify this to match your groups.
        Example for a control/patient study:
            if row["_sel01_1"] == 1:
                return "Patient"
            else:
                return "Control"
        """
        sel1, sel2, sel3 = row["_sel01_1"], row["_sel01_2"], row["_sel01_3"]
        if sel3 == 1 or (sel1 == 1 and sel2 == 1):
            return "ASD+ADHD"
        if sel1 == 1:
            return "ASD"
        if sel2 == 1:
            return "ADHD"
        return "TD"
    df["diagnosis"] = df.apply(derive_dx_row, axis=1)

    # ---- Covariates / bins for representativeness ----
    # These are used for stratified sampling to ensure train/test splits are representative
    df["site"] = df[SITE_col].astype(str) if SITE_col else "NA"
    df["sex"]  = normalize_sex(df[SEX_col]) if SEX_col else "U"

    if AGE_col:
        df["age_bin"] = ensure_bins_numeric(df[AGE_col], bins=[7,10,13,18],
                                            labels=["8-10","11-13","14-17"],
                                            default_label="allAge")
    else:
        df["age_bin"] = pd.Categorical(["allAge"] * len(df), categories=["allAge"])

    if MEANFD_col:
        fd_bins = ensure_bins_numeric(df[MEANFD_col], q=3,
                                      labels=["lowFD","midFD","highFD"],
                                      default_label="allFD")
        df["fd_bin"] = fd_bins if len(fd_bins) == len(df) \
                       else pd.Categorical(["allFD"] * len(df), categories=["allFD"])
    else:
        df["fd_bin"] = pd.Categorical(["allFD"] * len(df), categories=["allFD"])

    # ---- Find local subjects and intersect via normalized key ----
    nk2sub_local, local_subids = find_local_subjects(args.local_dir)
    df["matched_local_subid"] = df["nk"].map(nk2sub_local.get)
    matched = df[~df["matched_local_subid"].isna()].copy()

    # Diagnostics if no/low overlap
    if matched.empty:
        print("\n[diagnostics] No overlap found after normalization.")
        print(f"Excel rows: {len(df)} | Local subjects found: {len(local_subids)}")
        print("\nSample Excel EID → norm_key (first 10):")
        print(df[["EID_str","nk"]].head(10).to_string(index=False))
        print("\nSample local sub-* (first 10):")
        print(pd.Series(sorted(list(local_subids))).head(10).to_string(index=False))
        raise RuntimeError("No overlap between Excel EIDs and local sub-* after normalized matching. "
                           "Check --local_dir and EID formatting (e.g., NDAR, NDARINV, etc.).")

    # Use the *actual local* sub-id for downstream paths
    matched["subject_id"] = matched["matched_local_subid"]

    # ---- Build strata based on config.sh STRATIFY_BY_* settings ----
    # Build list of columns to stratify by
    strata_cols = []
    if STRATIFY_BY_SITE:
        strata_cols.append(matched["site"].astype(str))
    if STRATIFY_BY_SEX:
        strata_cols.append(matched["sex"].astype(str))
    if STRATIFY_BY_AGE:
        strata_cols.append(matched["age_bin"].astype(str))
    if STRATIFY_BY_MOTION:
        strata_cols.append(matched["fd_bin"].astype(str))

    # Combine into strata string
    if strata_cols:
        matched["strata"] = strata_cols[0]
        for col in strata_cols[1:]:
            matched["strata"] = matched["strata"] + "_" + col
    else:
        # If no stratification enabled, use single stratum
        matched["strata"] = pd.Categorical(["all"] * len(matched), categories=["all"])

    # ---- Diagnosis-agnostic CHA training via stratified sampling ----
    train_ids = []
    for s, subdf in matched.groupby("strata"):
        k = max(1, int(round(len(subdf) * args.train_frac)))
        train_ids.extend(subdf.sample(k, random_state=args.seed)["subject_id"].tolist())

    matched["CHA_train"] = matched["subject_id"].isin(train_ids)
    df_train = matched[matched["CHA_train"]].copy()
    df_test  = matched[~matched["CHA_train"]].copy()

    # ---- Save train/test ----
    prefix = args.out_prefix
    df_train.to_csv(f"{prefix}cha_train.csv", index=False)
    df_test.to_csv(f"{prefix}test_pool.csv", index=False)

    # ---- CV folds on test pool (stratify by diagnosis+site) ----
    if len(df_test) == 0:
        raise RuntimeError("Test pool is empty after split. Reduce --train_frac or verify filters.")

    y_strat = (df_test["diagnosis"].astype(str) + "_" + df_test["site"].astype(str)).values
    n_splits = choose_n_splits(y_strat, args.folds)
    if n_splits < args.folds:
        print(f"[warn] Reduced folds from {args.folds} to {n_splits} due to small class/site counts.")

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=args.seed)
    df_test["cv_fold"] = -1
    for fold, (_, te_idx) in enumerate(skf.split(np.zeros(len(df_test)), y_strat)):
        df_test.iloc[te_idx, df_test.columns.get_loc("cv_fold")] = fold

    df_test.to_csv(f"{prefix}test_pool_folds.csv", index=False)

    # ---- Summary ----
    print("\n=== Overlap summary ===")
    print(f"Excel total: {len(df)} | Local found: {len(local_subids)} | Matched: {len(matched)}")
    print(f"CHA train: {len(df_train)} | Test pool: {len(df_test)} | Folds: {n_splits}")
    print("\nDiagnosis (test pool):")
    print(df_test["diagnosis"].value_counts())
    print("\nFold × Diagnosis (test pool):")
    print(df_test.groupby(['cv_fold','diagnosis']).size().unstack(fill_value=0))

if __name__ == "__main__":
    main()
