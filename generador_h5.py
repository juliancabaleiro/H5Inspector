"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

Script to generate an HDF5 file with two different structures:
1. Separate axis datasets
2. Matrix dataset
"""
import numpy as np
import h5py
from datetime import datetime

#general configuration
name = r"signals_axes_vs_matrix.h5"
fs = 1_000_000          # Hz
f1 = 50                 # Hz
f2 = 1000               # Hz
A1 = 1.0
A2 = 0.3
periods = 2

T = periods / f1        # duración total
N = int(fs * T)

t = np.arange(N) / fs

signal = (
    A1 * np.sin(2 * np.pi * f1 * t) +
    A2 * np.sin(2 * np.pi * f2 * t)
)

#create HDF5 file

with h5py.File(name, "w") as f:

    #individual datasets
    grp_sep = f.create_group("separate_axes")

    dset_t = grp_sep.create_dataset(
        "time",
        data=t,
        dtype="float64"
    )

    dset_s = grp_sep.create_dataset(
        "signal",
        data=signal,
        dtype="float64"
    )

    # Atributos
    dset_t.attrs["units"] = "s"
    dset_t.attrs["fs"] = fs
    dset_t.attrs["description"] = "Time axis"

    dset_s.attrs["units"] = "V"
    dset_s.attrs["fundamental_frequency"] = f1
    dset_s.attrs["secondary_frequency"] = f2
    dset_s.attrs["description"] = "50 Hz + 1 kHz sine wave"
    dset_s.attrs["samples"] = N
    dset_s.attrs["duration_s"] = T

    #matrix signal
    grp_mat = f.create_group("matrix_signal")

    matrix = np.column_stack((t, signal))

    dset_m = grp_mat.create_dataset(
        "data",
        data=matrix,
        dtype="float64"
    )

    dset_m.attrs["columns"] = ["time", "signal"]
    dset_m.attrs["time_units"] = "s"
    dset_m.attrs["signal_units"] = "V"
    dset_m.attrs["fs"] = fs
    dset_m.attrs["fundamental_frequency"] = f1
    dset_m.attrs["secondary_frequency"] = f2
    dset_m.attrs["description"] = "Nx2 matrix: [time, signal]"

    #general attributes
    f.attrs["created"] = datetime.utcnow().isoformat()
    f.attrs["author"] = "Python HDF5 generator"
    f.attrs["note"] = "Comparison between separate axis datasets and matrix dataset"

print("Archivo signals_axes_vs_matrix.h5 creado correctamente")
