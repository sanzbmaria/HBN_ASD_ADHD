#!/usr/bin/env python3
"""
Upload pipeline outputs to UK Biobank RAP using dxpy Python API.

Alternative to the bash script - uses Python API instead of dx CLI.
"""

import os
import sys
import glob
from datetime import datetime
import argparse

try:
    import dxpy
except ImportError:
    print("ERROR: dxpy module not found!")
    print("\nPlease install the DNAnexus SDK:")
    print("  pip install dxpy")
    print("\nOr run this script on a UK Biobank RAP node where dxpy is pre-installed.")
    sys.exit(1)


def upload_directory(local_path, remote_path, verbose=True):
    """
    Upload a directory and its contents to RAP.

    Parameters:
    -----------
    local_path : str
        Local directory path to upload
    remote_path : str
        Remote RAP destination path
    verbose : bool
        Print progress messages
    """
    if not os.path.exists(local_path):
        if verbose:
            print(f"  ⚠ Directory not found: {local_path}")
        return 0

    uploaded_count = 0

    if verbose:
        print(f"  Uploading: {local_path} -> {remote_path}")

    # Walk through directory tree
    for root, dirs, files in os.walk(local_path):
        # Calculate relative path
        rel_path = os.path.relpath(root, local_path)
        if rel_path == '.':
            current_remote = remote_path
        else:
            current_remote = os.path.join(remote_path, rel_path).replace('\\', '/')

        # Upload files in this directory
        for filename in files:
            local_file = os.path.join(root, filename)

            try:
                # Upload file
                dxpy.upload_local_file(
                    filename=local_file,
                    project=dxpy.WORKSPACE_ID,
                    folder=current_remote,
                    show_progress=False
                )
                uploaded_count += 1

                if verbose and uploaded_count % 10 == 0:
                    print(f"    Uploaded {uploaded_count} files...")

            except Exception as e:
                print(f"  ✗ Failed to upload {local_file}: {e}")

    if verbose:
        print(f"  ✓ Uploaded {uploaded_count} files")

    return uploaded_count


def upload_pipeline_outputs(outputs_root, rap_base_path,
                            upload_connectomes=True,
                            upload_similarity=True,
                            upload_reliability=True,
                            upload_logs=True,
                            upload_parcellation=False):
    """
    Upload all pipeline outputs to UK Biobank RAP.

    Parameters:
    -----------
    outputs_root : str
        Local path to pipeline outputs directory
    rap_base_path : str
        Base path on RAP platform (e.g., "/pipeline_outputs")
    upload_* : bool
        Flags to control what gets uploaded
    """

    print("=" * 60)
    print("UK BIOBANK RAP UPLOAD (Python API)")
    print("=" * 60)
    print()

    # Check workspace
    try:
        workspace = dxpy.DXProject(dxpy.WORKSPACE_ID)
        print(f"Connected to RAP project: {workspace.name}")
    except:
        print("ERROR: Not connected to a DNAnexus workspace")
        print("\nPlease ensure you're running on a UK Biobank RAP node")
        print("or have configured dx credentials.")
        sys.exit(1)

    if not os.path.exists(outputs_root):
        print(f"\nERROR: Outputs directory not found: {outputs_root}")
        sys.exit(1)

    print(f"\nLocal outputs: {outputs_root}")
    print(f"RAP destination: {rap_base_path}")
    print()

    # Create timestamped upload directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    upload_path = f"{rap_base_path}/upload_{timestamp}"

    print(f"Creating upload directory: {upload_path}")
    workspace.new_folder(upload_path, parents=True)
    print()

    start_time = datetime.now()
    total_files = 0

    # Upload connectomes
    if upload_connectomes:
        print("=" * 60)
        print("Uploading connectomes...")
        print("=" * 60)
        step_start = datetime.now()

        connectomes_path = os.path.join(outputs_root, "connectomes")

        # AA connectomes (coarse and fine)
        for subdir in ["coarse", "fine"]:
            local_dir = os.path.join(connectomes_path, subdir)
            if os.path.exists(local_dir):
                remote_dir = f"{upload_path}/connectomes/{subdir}"
                total_files += upload_directory(local_dir, remote_dir)

        # CHA connectomes (hyperalignment outputs)
        ha_dir = os.path.join(connectomes_path, "hyperalignment_output")
        if os.path.exists(ha_dir):
            remote_dir = f"{upload_path}/connectomes/hyperalignment_output"
            total_files += upload_directory(ha_dir, remote_dir)

        duration = (datetime.now() - step_start).total_seconds()
        print(f"  ✓ Connectomes uploaded ({duration/60:.1f} minutes)")
        print()

    # Upload similarity matrices
    if upload_similarity:
        print("=" * 60)
        print("Uploading similarity matrices...")
        print("=" * 60)
        step_start = datetime.now()

        sim_dir = os.path.join(outputs_root, "connectomes", "similarity_matrices")
        if os.path.exists(sim_dir):
            remote_dir = f"{upload_path}/connectomes/similarity_matrices"
            total_files += upload_directory(sim_dir, remote_dir)

            duration = (datetime.now() - step_start).total_seconds()
            print(f"  ✓ Similarity matrices uploaded ({duration/60:.1f} minutes)")
        else:
            print("  ⚠ Similarity matrices not found")
        print()

    # Upload reliability results
    if upload_reliability:
        print("=" * 60)
        print("Uploading reliability results...")
        print("=" * 60)
        step_start = datetime.now()

        rel_dir = os.path.join(outputs_root, "connectomes", "reliability_results")
        if os.path.exists(rel_dir):
            remote_dir = f"{upload_path}/connectomes/reliability_results"
            total_files += upload_directory(rel_dir, remote_dir)

            duration = (datetime.now() - step_start).total_seconds()
            print(f"  ✓ Reliability results uploaded ({duration/60:.1f} minutes)")
        else:
            print("  ⚠ Reliability results not found")
        print()

    # Upload logs
    if upload_logs:
        print("=" * 60)
        print("Uploading logs...")
        print("=" * 60)
        step_start = datetime.now()

        logs_uploaded = False

        # Logs in connectomes directory
        log_dir = os.path.join(outputs_root, "connectomes", "logs")
        if os.path.exists(log_dir):
            remote_dir = f"{upload_path}/connectomes/logs"
            total_files += upload_directory(log_dir, remote_dir)
            logs_uploaded = True

        # Logs in project directory
        project_log_dir = os.path.join(os.path.dirname(os.path.dirname(outputs_root)), "logs")
        if os.path.exists(project_log_dir):
            remote_dir = f"{upload_path}/logs"
            total_files += upload_directory(project_log_dir, remote_dir)
            logs_uploaded = True

        if logs_uploaded:
            duration = (datetime.now() - step_start).total_seconds()
            print(f"  ✓ Logs uploaded ({duration/60:.1f} minutes)")
        else:
            print("  ⚠ No logs found")
        print()

    # Upload parcellation (usually very large)
    if upload_parcellation:
        print("=" * 60)
        print("Uploading parcellation data...")
        print("=" * 60)
        print("  ⚠ Warning: This may be very large and take a long time!")
        step_start = datetime.now()

        parcel_dir = os.path.join(outputs_root, "glasser_ptseries")
        if os.path.exists(parcel_dir):
            remote_dir = f"{upload_path}/glasser_ptseries"
            total_files += upload_directory(parcel_dir, remote_dir)

            duration = (datetime.now() - step_start).total_seconds()
            print(f"  ✓ Parcellation data uploaded ({duration/60:.1f} minutes)")
        else:
            print("  ⚠ Parcellation data not found")
        print()

    # Create summary file
    print("Creating upload summary...")
    summary_content = f"""UK Biobank RAP Pipeline Upload Summary
======================================

Upload Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Local Source: {outputs_root}
RAP Destination: {upload_path}

Files Uploaded:
- Total files: {total_files}
- Connectomes: {upload_connectomes}
- Similarity Matrices: {upload_similarity}
- Reliability Results: {upload_reliability}
- Logs: {upload_logs}
- Parcellation Data: {upload_parcellation}

Upload completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total upload time: {(datetime.now() - start_time).total_seconds() / 60:.1f} minutes
"""

    # Upload summary as file object
    summary_file = dxpy.upload_string(
        summary_content,
        project=dxpy.WORKSPACE_ID,
        folder=upload_path,
        name="upload_summary.txt"
    )

    total_duration = (datetime.now() - start_time).total_seconds()

    print()
    print("=" * 60)
    print("UPLOAD COMPLETE")
    print("=" * 60)
    print()
    print(f"Uploaded {total_files} files to:")
    print(f"  {upload_path}")
    print()
    print(f"Total upload time: {total_duration/60:.1f} minutes")
    print()
    print("To view files on RAP:")
    print(f"  dx ls {upload_path}")
    print()
    print("To download from RAP:")
    print(f"  dx download -r {upload_path}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload hyperalignment pipeline outputs to UK Biobank RAP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload all outputs except parcellation
  python upload_to_rap_python.py \\
      --outputs /home/dnanexus/HBN_ASD_ADHD/data \\
      --destination /my_analysis/results

  # Upload only connectomes and similarity matrices
  python upload_to_rap_python.py \\
      --outputs /home/dnanexus/HBN_ASD_ADHD/data \\
      --destination /results \\
      --no-reliability --no-logs

  # Upload everything including large parcellation data
  python upload_to_rap_python.py \\
      --outputs /home/dnanexus/HBN_ASD_ADHD/data \\
      --destination /complete_results \\
      --include-parcellation
        """
    )

    parser.add_argument(
        "--outputs", "-o",
        default="/home/dnanexus/HBN_ASD_ADHD/data",
        help="Local path to pipeline outputs directory"
    )

    parser.add_argument(
        "--destination", "-d",
        default="/pipeline_outputs",
        help="Base path on RAP platform"
    )

    parser.add_argument(
        "--no-connectomes",
        action="store_true",
        help="Skip uploading connectomes"
    )

    parser.add_argument(
        "--no-similarity",
        action="store_true",
        help="Skip uploading similarity matrices"
    )

    parser.add_argument(
        "--no-reliability",
        action="store_true",
        help="Skip uploading reliability results"
    )

    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Skip uploading logs"
    )

    parser.add_argument(
        "--include-parcellation",
        action="store_true",
        help="Upload parcellation data (usually very large)"
    )

    args = parser.parse_args()

    upload_pipeline_outputs(
        outputs_root=args.outputs,
        rap_base_path=args.destination,
        upload_connectomes=not args.no_connectomes,
        upload_similarity=not args.no_similarity,
        upload_reliability=not args.no_reliability,
        upload_logs=not args.no_logs,
        upload_parcellation=args.include_parcellation
    )
