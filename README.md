<div align="center">
  <img src="assets/logo.png" alt="H5Inspector Banner" width="100%">

  # H5Inspector

  [![Python](https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![PyQt5](https://img.shields.io/badge/PyQt-5-green?style=for-the-badge&logo=qt&logoColor=white)](https://pypi.org/project/PyQt5/)
  [![Plotly](https://img.shields.io/badge/Plotly-Interactive-informational?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com/python/)
  [![License](https://img.shields.io/badge/License-GPLv3-yellow?style=for-the-badge)](LICENSE)

  **A Python-based desktop tool for visualizing, analyzing, and editing HDF5 files.**

</div>

---

## Overview

**H5Inspector** is a desktop application designed to simplify working with HDF5 files.  
It provides an intuitive interface for navigating large datasets, visualizing signals with interactive, scientific-grade tools, and performing spectral analysis (FFT).

---

## Features

### 📊 View (View Tab)
- **Hierarchical Navigation**: Browse groups, datasets, and attributes using a tree view.
- **Data Tables**: Inspect raw values from 1D and 2D datasets.
- **Interactive Plots**:
  - **Plotly (WebGL) engine**
  - Zoom, pan, and auto-scaling
  - **Dual Cursors**: Measurements with statistics (Mean, RMS, Pk-Pk, Std Dev)
  - **Markers**: Precise visualization of individual data points

---

### 📈 Analysis (Analysis Tab)
- **Spectral Analysis (FFT)**: Computes the Fast Fourier Transform.
- **Flexible Configuration**:
  - Sampling frequency
  - Window functions (Hann, Hamming, etc.)
  - Units (linear, dB, phase)
- **Automatic Measurements**:
  - Peak detection
  - THD (Total Harmonic Distortion)

---

### ✏️ Edit and Export (Edit Tab)
- **File Creation**: Export selected datasets or ranges to new HDF5 files.
- **Metadata Editing**: Add comments and attributes to exported files.
- **CSV Export**: Export data to CSV format compatible with Excel and MATLAB.

---

## 🛠 Installation

### Prerequisites
- Python **3.10.11**
- pip
- Visual Studio Code (recommended)

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/tu-usuario/H5Inspector.git
   cd H5Inspector
   ```

2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux / macOS
   venv\Scripts\activate      # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Usage

Run the main application:

```bash
python main.py
```

### Typical Workflow
1. **Load**: Open an `.h5` file from the top toolbar.
2. **Explore**: Select a dataset from the tree view.
3. **Analyze**:
   - Use cursors to measure a region of interest.
   - Switch to the **Analysis** tab to inspect the frequency spectrum.
4. **Export**: Use the **Edit** tab to save processed data to a new file.

---

## 📂 Project Structure

```
H5Inspector/
├── h5inspector.py           # Main application logic
├── main.py                  # Entry point
├── view_tab.py              # Visualization module
├── analysis_tab.py          # FFT analysis module
├── edit_tab.py              # Edit and export module
├── plot_widget.py           # Plot widget (Plotly + WebEngine)
├── h5_utils.py              # Low-level HDF5 utilities
├── math_utils.py            # Mathematical algorithms (FFT, THD)
├── styles.qss               # Application theme (Qt Style Sheet)
└── requirements.txt         # Python dependencies
```
---

## 🧪 Demo Data Generation

### Included Demo File

The repository includes a demo HDF5 file:

- **signals_axes_vs_matrix.h5**

To generate example HDF5 files for testing and demonstration purposes, use:

```bash
python generador_h5.py
```

This script creates demo `.h5` files containing sample signals that can be loaded directly into **H5Inspector** for visualization and analysis.

---

## 📄 License

This project is distributed under the **GNU General Public License v3.0 (GPLv3)**.  
See the `LICENSE` file for details.
