#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, glob, argparse
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

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
    ap.add_argument("--excel", default="HBN_ASD_ADHD.xlsx", help="Path to metadata Excel")
    ap.add_argument("--local_dir", default="ASD/CHA2/Data_mirror/HBN_rsfMRI_32k_sm5_gsr", help="Root with dtseries files")
    ap.add_argument("--train_frac", type=float, default=0.25, help="Fraction for CHA training (0-1)")
    ap.add_argument("--folds", type=int, default=5, help="Requested number of CV folds for test pool")
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

    # ---- Map known columns (from your sheet) ----
    if "EID" not in df.columns:
        raise KeyError(f"EID column not found. Available: {list(df.columns)}")

    SITE   = "SITE"    if "SITE"    in df.columns else None
    SEX    = "Sex"     if "Sex"     in df.columns else None
    AGE    = "Age"     if "Age"     in df.columns else None
    MEANFD = "MeanFD"  if "MeanFD"  in df.columns else None

    ASD_col     = "ASD"        if "ASD"        in df.columns else None
    ADHD_col    = "ADHD"       if "ADHD"       in df.columns else None
    ASDADHD_col = "ASD+ADHD"   if "ASD+ADHD"   in df.columns else None

    # ---- Excel-side normalized key and candidate subject_id ----
    df["EID_str"] = df["EID"].astype(str).str.strip()
    df["nk"] = df["EID_str"].map(norm_key)
    df["subject_id_excel"] = df["EID_str"].map(to_sub_id)  # e.g., sub-NDARINV...

    # ---- Diagnosis (NaN-safe) ----
    df["_asd01"]   = to01(df[ASD_col])      if ASD_col      else 0
    df["_adhd01"]  = to01(df[ADHD_col])     if ADHD_col     else 0
    df["_both01"]  = to01(df[ASDADHD_col])  if ASDADHD_col  else 0

    def derive_dx_row(row):
        asd, adhd, both = row["_asd01"], row["_adhd01"], row["_both01"]
        if both == 1 or (asd == 1 and adhd == 1):
            return "ASD+ADHD"
        if asd == 1:
            return "ASD"
        if adhd == 1:
            return "ADHD"
        return "TD"
    df["diagnosis"] = df.apply(derive_dx_row, axis=1)

    # ---- Covariates / bins for representativeness ----
    df["site"] = df[SITE].astype(str) if SITE else "NA"
    df["sex"]  = normalize_sex(df[SEX]) if SEX else "U"

    if AGE:
        df["age_bin"] = ensure_bins_numeric(df[AGE], bins=[7,10,13,18],
                                            labels=["8-10","11-13","14-17"],
                                            default_label="allAge")
    else:
        df["age_bin"] = pd.Categorical(["allAge"] * len(df), categories=["allAge"])

    if MEANFD:
        fd_bins = ensure_bins_numeric(df[MEANFD], q=3,
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

    # ---- Build strata: site × sex × age_bin × fd_bin ----
    parts = [matched["site"].astype(str), matched["sex"].astype(str),
             matched["age_bin"].astype(str), matched["fd_bin"].astype(str)]
    matched["strata"] = parts[0]
    for p in parts[1:]:
        matched["strata"] = matched["strata"] + "_" + p

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
