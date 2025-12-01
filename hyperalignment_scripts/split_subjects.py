##### the code used to identify train/test percentage without excel #####

#!/usr/bin/env python3
"""
Flexible train/test splitting without requiring Excel file.
Supports random splitting, percentage-based, or explicit subject lists.
"""

import os
import sys
import random
import argparse
from read_config import (
    DTSERIES_ROOT, DTSERIES_FILENAME_PATTERN,
    TRAIN_PERCENTAGE, RANDOM_SEED
)
import glob


def discover_subjects():
    """Discover all available subjects from CIFTI files."""
    pattern = os.path.join(DTSERIES_ROOT, DTSERIES_FILENAME_PATTERN)
    subjects = []
    
    for filepath in glob.glob(pattern):
        filename = os.path.basename(filepath)
        # Extract subject ID before the pattern-specific part
        # For "*_bb.rfMRI.MNI.MSMAll.dtseries", extract everything before _bb
        subj_id = filename.split("_bb.rfMRI")[0] if "_bb.rfMRI" in filename else filename.split("_task-rest")[0]
        
        # Add "sub-" prefix if not present (for consistency)
        if not subj_id.startswith("sub-"):
            subj_id = f"sub-{subj_id}"
        
        subjects.append(subj_id)
    
    return sorted(set(subjects))


def random_split(subjects, train_pct, seed=42):
    """
    Randomly split subjects into train/test sets.
    
    Parameters
    ----------
    subjects : list
        List of subject IDs
    train_pct : float
        Percentage of subjects for training (0.0 to 1.0)
    seed : int
        Random seed for reproducibility
    
    Returns
    -------
    tuple
        (train_subjects, test_subjects)
    """
    random.seed(seed)
    shuffled = subjects.copy()
    random.shuffle(shuffled)
    
    n_train = max(1, int(len(shuffled) * train_pct))
    train = shuffled[:n_train]
    test = shuffled[n_train:]
    
    return train, test


def main():
    parser = argparse.ArgumentParser(
        description="Flexible train/test splitting for hyperalignment pipeline"
    )
    parser.add_argument(
        "--mode",
        choices=["random", "percentage", "explicit"],
        default="random",
        help="Splitting mode"
    )
    parser.add_argument(
        "--train-pct",
        type=float,
        default=float(TRAIN_PERCENTAGE),
        help="Training percentage (0.0 to 1.0). Default from config.sh"
    )
    parser.add_argument(
        "--train-subjects",
        type=str,
        default="",
        help="Comma-separated list of training subjects (for explicit mode)"
    )
    parser.add_argument(
        "--test-subjects",
        type=str,
        default="",
        help="Comma-separated list of test subjects (for explicit mode)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=int(RANDOM_SEED),
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="train_test_split.txt",
        help="Output file to save split"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("TRAIN/TEST SPLITTING")
    print("=" * 70)
    
    # Discover available subjects
    all_subjects = discover_subjects()
    print(f"\nDiscovered {len(all_subjects)} subjects from CIFTI files")
    
    if len(all_subjects) == 0:
        print(f"ERROR: No subjects found in {DTSERIES_ROOT}")
        print(f"Pattern: {DTSERIES_FILENAME_PATTERN}")
        sys.exit(1)
    
    print(f"Sample subjects: {all_subjects[:5]}")
    
    # Perform split based on mode
    if args.mode == "explicit":
        # Use explicitly provided subject lists
        if not args.train_subjects or not args.test_subjects:
            print("ERROR: explicit mode requires --train-subjects and --test-subjects")
            sys.exit(1)
        
        train_subjects = [s.strip() for s in args.train_subjects.split(",")]
        test_subjects = [s.strip() for s in args.test_subjects.split(",")]
        
        # Add "sub-" prefix if needed
        train_subjects = [s if s.startswith("sub-") else f"sub-{s}" for s in train_subjects]
        test_subjects = [s if s.startswith("sub-") else f"sub-{s}" for s in test_subjects]
        
        print(f"\nUsing explicit subject lists")
        
    else:
        # Random or percentage mode (same implementation)
        if args.train_pct <= 0 or args.train_pct >= 1:
            print(f"ERROR: train-pct must be between 0 and 1 (got {args.train_pct})")
            sys.exit(1)
        
        train_subjects, test_subjects = random_split(
            all_subjects, args.train_pct, args.seed
        )
        
        print(f"\nRandom split with seed={args.seed}")
        print(f"Train percentage: {args.train_pct:.1%}")
    
    # Validate subjects exist
    train_subjects = [s for s in train_subjects if s in all_subjects]
    test_subjects = [s for s in test_subjects if s in all_subjects]
    
    print("\n" + "=" * 70)
    print("SPLIT SUMMARY")
    print("=" * 70)
    print(f"Total subjects:     {len(all_subjects)}")
    print(f"Training subjects:  {len(train_subjects)} ({len(train_subjects)/len(all_subjects)*100:.1f}%)")
    print(f"Test subjects:      {len(test_subjects)} ({len(test_subjects)/len(all_subjects)*100:.1f}%)")
    
    if len(train_subjects) == 0 or len(test_subjects) == 0:
        print("\nERROR: Either train or test set is empty!")
        sys.exit(1)
    
    # Save to file
    with open(args.output, "w") as f:
        f.write("# Train/Test Split\n")
        f.write(f"# Mode: {args.mode}\n")
        f.write(f"# Train percentage: {args.train_pct}\n")
        f.write(f"# Random seed: {args.seed}\n")
        f.write(f"# Total: {len(all_subjects)}, Train: {len(train_subjects)}, Test: {len(test_subjects)}\n")
        f.write("\n[TRAIN]\n")
        for subj in train_subjects:
            f.write(f"{subj}\n")
        f.write("\n[TEST]\n")
        for subj in test_subjects:
            f.write(f"{subj}\n")
    
    print(f"\nSplit saved to: {args.output}")
    
    # Also save as environment variables format
    env_file = args.output.replace(".txt", "_env.sh")
    with open(env_file, "w") as f:
        f.write("# Source this file to set environment variables\n")
        f.write(f"export TRAIN_SUBJECTS='{' '.join(train_subjects)}'\n")
        f.write(f"export TEST_SUBJECTS='{' '.join(test_subjects)}'\n")
    
    print(f"Environment file saved to: {env_file}")
    print("\nTo use this split, run:")
    print(f"  source {env_file}")
    print("  ./test_pipeline.sh  # or full_pipeline.sh")
    
    print("\n" + "=" * 70)
    print("Sample training subjects:")
    for subj in train_subjects[:5]:
        print(f"  - {subj}")
    if len(train_subjects) > 5:
        print(f"  ... ({len(train_subjects) - 5} more)")
    
    print("\nSample test subjects:")
    for subj in test_subjects[:5]:
        print(f"  - {subj}")
    if len(test_subjects) > 5:
        print(f"  ... ({len(test_subjects) - 5} more)")
    print("=" * 70)


if __name__ == "__main__":
    main()
