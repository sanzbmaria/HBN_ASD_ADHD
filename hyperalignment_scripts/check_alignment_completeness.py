#!/usr/bin/env python3
"""
Check hyperalignment output completeness per subject.
Reports which subjects have complete/incomplete aligned timeseries.
"""

import os
import sys
import glob
from collections import defaultdict
import argparse

# Import configuration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_config import BASE_OUTDIR, N_PARCELS


def check_alignment_completeness(mode='full', base_dir=None):
    """
    Check which subjects have complete aligned timeseries output.

    Parameters:
    -----------
    mode : str
        'full', 'split', or 'both'
    base_dir : str
        Base output directory (defaults to BASE_OUTDIR from config)
    """
    if base_dir is None:
        base_dir = BASE_OUTDIR

    aligned_ts_dir = os.path.join(base_dir, 'hyperalignment_output', 'aligned_timeseries')

    if not os.path.exists(aligned_ts_dir):
        print(f"ERROR: Aligned timeseries directory not found: {aligned_ts_dir}")
        return

    print(f"Checking alignment completeness in: {aligned_ts_dir}")
    print(f"Mode: {mode}")
    print(f"Expected parcels: {N_PARCELS}")
    print("="*80)

    # Track files per subject
    subject_files = defaultdict(lambda: {'full': set(), 'split_0': set(), 'split_1': set()})

    # Scan all parcel directories
    for parcel in range(1, N_PARCELS + 1):
        parcel_dir = os.path.join(aligned_ts_dir, f'parcel_{parcel:03d}')

        if not os.path.exists(parcel_dir):
            continue

        # Find full timeseries files
        if mode in ['full', 'both']:
            full_files = glob.glob(os.path.join(parcel_dir, '*_aligned_dtseries.npy'))
            for f in full_files:
                subj_id = os.path.basename(f).replace('_aligned_dtseries.npy', '')
                subject_files[subj_id]['full'].add(parcel)

        # Find split timeseries files
        if mode in ['split', 'both']:
            split0_files = glob.glob(os.path.join(parcel_dir, '*_aligned_dtseries_split_0.npy'))
            split1_files = glob.glob(os.path.join(parcel_dir, '*_aligned_dtseries_split_1.npy'))

            for f in split0_files:
                subj_id = os.path.basename(f).replace('_aligned_dtseries_split_0.npy', '')
                subject_files[subj_id]['split_0'].add(parcel)

            for f in split1_files:
                subj_id = os.path.basename(f).replace('_aligned_dtseries_split_1.npy', '')
                subject_files[subj_id]['split_1'].add(parcel)

    if not subject_files:
        print("No aligned timeseries files found!")
        return

    # Analyze completeness
    complete_subjects = []
    incomplete_subjects = []

    print(f"\nFound {len(subject_files)} subjects with aligned timeseries")
    print("\nSubject Completeness:")
    print("-"*80)

    for subj_id in sorted(subject_files.keys()):
        files = subject_files[subj_id]

        if mode == 'full':
            n_files = len(files['full'])
            is_complete = n_files == N_PARCELS
            status = "COMPLETE" if is_complete else f"INCOMPLETE ({n_files}/{N_PARCELS})"
            print(f"{subj_id:20s}  Full: {status}")

            if is_complete:
                complete_subjects.append(subj_id)
            else:
                incomplete_subjects.append((subj_id, N_PARCELS - n_files))

        elif mode == 'split':
            n_split0 = len(files['split_0'])
            n_split1 = len(files['split_1'])
            is_complete = (n_split0 == N_PARCELS) and (n_split1 == N_PARCELS)

            status0 = "COMPLETE" if n_split0 == N_PARCELS else f"INCOMPLETE ({n_split0}/{N_PARCELS})"
            status1 = "COMPLETE" if n_split1 == N_PARCELS else f"INCOMPLETE ({n_split1}/{N_PARCELS})"

            print(f"{subj_id:20s}  Split0: {status0}  Split1: {status1}")

            if is_complete:
                complete_subjects.append(subj_id)
            else:
                missing = max(N_PARCELS - n_split0, N_PARCELS - n_split1)
                incomplete_subjects.append((subj_id, missing))

        else:  # both
            n_full = len(files['full'])
            n_split0 = len(files['split_0'])
            n_split1 = len(files['split_1'])

            full_complete = n_full == N_PARCELS
            split_complete = (n_split0 == N_PARCELS) and (n_split1 == N_PARCELS)
            is_complete = full_complete and split_complete

            full_status = "✓" if full_complete else f"✗ ({n_full}/{N_PARCELS})"
            split_status = "✓" if split_complete else f"✗ ({n_split0},{n_split1}/{N_PARCELS})"

            print(f"{subj_id:20s}  Full: {full_status:20s}  Splits: {split_status}")

            if is_complete:
                complete_subjects.append(subj_id)
            else:
                missing = max(N_PARCELS - n_full, N_PARCELS - n_split0, N_PARCELS - n_split1)
                incomplete_subjects.append((subj_id, missing))

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total subjects found:       {len(subject_files)}")
    print(f"Complete subjects:          {len(complete_subjects)}")
    print(f"Incomplete subjects:        {len(incomplete_subjects)}")
    print(f"Completion rate:            {len(complete_subjects)/len(subject_files)*100:.1f}%")

    if incomplete_subjects:
        print("\nMost incomplete subjects (top 10):")
        incomplete_subjects.sort(key=lambda x: x[1], reverse=True)
        for subj_id, n_missing in incomplete_subjects[:10]:
            print(f"  {subj_id:20s}  Missing {n_missing} parcels")

    # Check for specific missing parcels across all subjects
    if mode in ['full', 'both']:
        print("\nParcel-wise analysis (Full timeseries):")
        parcel_counts = defaultdict(int)
        for files in subject_files.values():
            for parcel in files['full']:
                parcel_counts[parcel] += 1

        total_subjects = len(subject_files)
        missing_parcels = []
        for parcel in range(1, N_PARCELS + 1):
            count = parcel_counts.get(parcel, 0)
            if count < total_subjects:
                missing_parcels.append((parcel, total_subjects - count))

        if missing_parcels:
            missing_parcels.sort(key=lambda x: x[1], reverse=True)
            print(f"\nParcels with missing data (top 10):")
            for parcel, n_missing in missing_parcels[:10]:
                print(f"  Parcel {parcel:03d}: missing for {n_missing} subjects ({n_missing/total_subjects*100:.1f}%)")
        else:
            print("\nAll parcels have complete coverage across all subjects!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Check hyperalignment output completeness per subject',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check full timeseries only
  python check_alignment_completeness.py --mode full

  # Check split timeseries only
  python check_alignment_completeness.py --mode split

  # Check both full and split
  python check_alignment_completeness.py --mode both

  # Use custom base directory
  python check_alignment_completeness.py --base-dir /custom/path/connectomes
        """
    )

    parser.add_argument('--mode', type=str, choices=['full', 'split', 'both'], default='both',
                        help='Which timeseries to check (default: both)')
    parser.add_argument('--base-dir', type=str, default=None,
                        help='Base output directory (default: from config.sh)')

    args = parser.parse_args()

    check_alignment_completeness(mode=args.mode, base_dir=args.base_dir)
