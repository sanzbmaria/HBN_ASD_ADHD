#!/usr/bin/env python

import os
import sys
import tempfile

# Set up temp directory
TMPDIR = tempfile.gettempdir()
os.environ['TMPDIR'] = TMPDIR
os.environ['TEMP'] = TMPDIR
os.environ['TMP'] = TMPDIR

# Suppress warnings
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'
import warnings
warnings.filterwarnings("ignore")

import numpy as np

# Fix numpy deprecations
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int

import glob
import time
import multiprocessing as mp
from scipy.stats import zscore
from mvpa2.algorithms.hyperalignment import Hyperalignment
from mvpa2.datasets import Dataset
from mvpa2.base import debug

# Import configuration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_config import (
    POOL_NUM, N_JOBS, VERTICES_IN_BOUNDS,
    BASE_OUTDIR, PARCELLATION_FILE,
    pool_num, n_jobs
)
import utils

global parcel

NPROC = n_jobs
glasser_atlas = utils.get_glasser_atlas_file()


def prep_cnx(args):
    if len(args) == 2:
        subject, split = args
        fn = train_connectome_dir + '/{a}_split_{split}_connectome_parcel_{i:03d}.npy'.format(
            a=subject, split=split, i=parcel)
    else:
        subject = args
        fn = train_connectome_dir + '/{a}_full_connectome_parcel_{i:03d}.npy'.format(
            a=subject, i=parcel)

    d = np.nan_to_num(zscore(np.load(fn)))
    ds_train = Dataset(d)
    ds_train.sa['targets'] = np.arange(1, 360)
    ds_train.fa['seeds'] = np.where(glasser_atlas == parcel)[0]
    return ds_train


def prep_dtseries(subject, split=None):
    d = utils.subj_dtseries_to_npy(subject, z=True, parcel=parcel)
    if split is not None:
        half = d.shape[0] // 2
        start = split * half
        tpts_in_bounds = np.arange(start, start + half)
        d = d[tpts_in_bounds]
    return zscore(d, axis=0)


def apply_mappers(args):
    data_out_fn, mapper_out_fn, subject, mapper, split = args
    dtseries = prep_dtseries(subject, split=split)
    aligned = zscore((np.asmatrix(dtseries) * mapper._proj).A, axis=0)
    np.save(data_out_fn, aligned)
    np.save(mapper_out_fn, mapper._proj)


def apply_mappers_split(args):
    data_out_fn, mapper_fn, subject, mapper0, mapper1 = args
    dtseries0 = prep_dtseries(subject, split=0)
    dtseries1 = prep_dtseries(subject, split=1)
    aligned0 = zscore((np.asmatrix(dtseries0) * mapper0._proj).A, axis=0)
    aligned1 = zscore((np.asmatrix(dtseries1) * mapper1._proj).A, axis=0)
    np.save(data_out_fn + '0.npy', aligned0)
    np.save(data_out_fn + '1.npy', aligned1)
    np.save(mapper_fn + '0.npy', mapper0._proj)
    np.save(mapper_fn + '1.npy', mapper1._proj)


def drive_hyperalignment_full():
    pool = mp.Pool(pool_num)
    train_cnx = pool.map(prep_cnx, train_subjects)
    print("training hyperalignment")
    ha = Hyperalignment(nproc=NPROC, joblib_backend='multiprocessing')
    debug.active += ['HPAL']
    ha(train_cnx)
    t1 = time.time() - t0
    print('---------finished training @ {x}-----------'.format(x=t1))
    print('---------aligning and saving full timeseries -----------')
    test_cnx = pool.map(prep_cnx, test_subjects)
    mappers = ha(test_cnx)
    data_fns = [os.path.join(aligned_dir, '{s}_aligned_dtseries.npy'.format(s=s))
                for s in test_subjects]
    mapper_fns = [os.path.join(mapper_dir, '{s}_trained_mapper.npy'.format(s=s))
                  for s in test_subjects]
    iterable = zip(data_fns, mapper_fns, test_subjects, mappers,
                   [None] * len(mappers))
    pool.map(apply_mappers, iterable)
    pool.close()
    pool.join()
    t2 = time.time() - t1
    print('--------- finished aligning full timeseries @ {x}-----------'.format(x=t2))


def drive_hyperalignment_split():
    pool = mp.Pool(pool_num)
    train_cnx = pool.map(prep_cnx, train_subjects)
    print("training hyperalignment")
    ha = Hyperalignment(nproc=NPROC, joblib_backend='multiprocessing')
    debug.active += ['HPAL']
    ha(train_cnx)
    t1 = time.time() - t0
    print('---------finished training @ {x}-----------'.format(x=t1))

    iterable0 = [(subject, 0) for subject in test_subjects]
    iterable1 = [(subject, 1) for subject in test_subjects]
    test_cnx0 = pool.map(prep_cnx, iterable0)
    mappers0 = ha(test_cnx0)
    test_cnx1 = pool.map(prep_cnx, iterable1)
    mappers1 = ha(test_cnx1)

    data_fns = [os.path.join(aligned_dir, '{s}_aligned_dtseries_split'.format(s=s))
                for s in test_subjects]
    mapper_fns = [os.path.join(mapper_dir, '{s}_trained_mapper_split'.format(s=s))
                  for s in test_subjects]
    iterable = zip(data_fns, mapper_fns, test_subjects, mappers0, mappers1)
    pool.map(apply_mappers_split, iterable)
    pool.close()
    pool.join()
    t3 = time.time() - t1
    print('--------- finished aligning half timeseries @ {x}-----------'.format(x=t3))


if __name__ == '__main__':
    t0 = time.time()
    parcel = int(sys.argv[1])

    train_connectome_dir = os.path.join(BASE_OUTDIR, 'fine', 'parcel_{i:03d}'.format(i=parcel))
    mapper_dir = os.path.join(BASE_OUTDIR, 'hyperalignment_output', 'mappers',
                              'parcel_{i:03d}'.format(i=parcel))
    aligned_dir = os.path.join(BASE_OUTDIR, 'hyperalignment_output', 'aligned_timeseries',
                               'parcel_{i:03d}'.format(i=parcel))

    train_subjects = utils.get_HA_train_subjects()
    twin_subjects = utils.load_twin_subjects()
    unrelated_subjects = utils.get_reliability_subjects()

    test_subjects = list(set(twin_subjects + unrelated_subjects))

    print("{x} test subjects".format(x=len(test_subjects)))

    for dn in [aligned_dir, mapper_dir]:
        if not os.path.isdir(dn):
            os.makedirs(dn)
            print('made ', dn)

    drive_hyperalignment_split()
    print("Finished hyperalignment in splits")
    drive_hyperalignment_full()
    print("Finished hyperalignment full")
