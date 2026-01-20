"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

Analysis Tab - HDF5 Signal Analysis (FFT)
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QSplitter, QLabel, QGroupBox, QCheckBox, QLineEdit, QComboBox, QFormLayout, QGridLayout
from PyQt5.QtCore import Qt
import h5_utils
from plot_widget import PlotWidget
import numpy as np
import math_utils
import logging

class AnalysisTab(QWidget):
    """
    Analysis tab for signal processing (FFT).
    """
    
    def __init__(self, parent=None):
        """
        Initialize the AnalysisTab.
        """
        super().__init__(parent)
        self.current_file = None
        self.cached_fft_results = None # Initialize cache
        self.setup_ui()
    
    def setup_ui(self):
        """
        Setup the user interface.
        """
        layout = QVBoxLayout(self)
        
        # Splitter for structure and analysis area
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Tree view (Shared logic with ViewTab)
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("HDF5 Structure")
        self.tree_widget.itemClicked.connect(self.on_tree_item_clicked)
        main_splitter.addWidget(self.tree_widget)
        
        # Right side: FFT Area
        analysis_area = QWidget()
        analysis_layout = QVBoxLayout(analysis_area)
        
        # Controls for FFT
        controls_group = QGroupBox("FFT Configuration")
        controls_layout = QHBoxLayout()
        
        form_layout = QFormLayout()
        
        # Sampling Frequency
        self.fs_input = QLineEdit("1000.0")
        self.fs_input.setPlaceholderText("Fs (kHz)")
        self.fs_input.textChanged.connect(self.update_fft_plot)
        form_layout.addRow("Sampling Freq (kHz):", self.fs_input)
        
        # Window
        self.window_combo = QComboBox()
        self.window_combo.addItems(["Rectangular", "Hann", "Hamming", "Blackman", "Gabor"])
        self.window_combo.currentIndexChanged.connect(self.update_fft_plot)
        form_layout.addRow("Window:", self.window_combo)
        
        # Signal Source (Logic remains, but it's moved to the plot bar below)
        self.signal_source_combo = QComboBox()
        self.signal_source_combo.currentIndexChanged.connect(self.update_fft_plot)

        # Y-Axis View (Renamed to Y axis unit)
        self.y_axis_view_combo = QComboBox()
        self.y_axis_view_combo.addItems(["Magnitude", "Magnitude (dB)", "Phase"])
        self.y_axis_view_combo.currentIndexChanged.connect(self.update_fft_plot_view_only)
        form_layout.addRow("Y axis unit:", self.y_axis_view_combo)
        
        controls_layout.addLayout(form_layout)
        
        # Log-X
        self.log_x_check = QCheckBox("Logarithmic Scale (X)")
        self.log_x_check.stateChanged.connect(self.update_fft_plot)
        controls_layout.addWidget(self.log_x_check)
        
        # X Axis mode selector (Frequency vs Index)
        self.x_axis_mode_combo = QComboBox()
        self.x_axis_mode_combo.addItems(["Frequency", "Index"])
        self.x_axis_mode_combo.currentIndexChanged.connect(self.update_fft_plot)
        
        controls_group.setLayout(controls_layout)
        analysis_layout.addWidget(controls_group)

        # Parameters Panel (Renamed from Peak Detection)
        self.params_group = QGroupBox("Analysis Parameters")
        params_layout = QGridLayout()
        
        params_layout.addWidget(QLabel("Peak Frequency:"), 0, 0)
        self.peak_freq_val = QLabel("---")
        self.peak_freq_val.setStyleSheet("font-weight: bold; color: #d63031;")
        params_layout.addWidget(self.peak_freq_val, 0, 1)
        
        params_layout.addWidget(QLabel("Peak Magnitude:"), 0, 2)
        self.peak_mag_val = QLabel("---")
        self.peak_mag_val.setStyleSheet("font-weight: bold; color: #d63031;")
        params_layout.addWidget(self.peak_mag_val, 0, 3)

        params_layout.addWidget(QLabel("THD (%):"), 1, 0)
        self.thd_val = QLabel("---")
        self.thd_val.setStyleSheet("font-weight: bold; color: #0984e3;")
        params_layout.addWidget(self.thd_val, 1, 1)
        
        self.params_group.setLayout(params_layout)
        analysis_layout.addWidget(self.params_group)
        
        # Plot area (defaults to Magnitude)
        plot_container = QWidget()
        plot_container_layout = QVBoxLayout(plot_container)
        
        # Plot widget for FFT
        self.fft_plot = PlotWidget()
        self.fft_plot.set_stats_visible(False) # Hide redundant statistics panel
        self.fft_plot.set_axis_selectors_visible(False) # Hide default X/Y selectors
        
        # Insert our X/Y Axis selectors into the plot controls
        self.fft_plot.controls_layout.insertWidget(0, QLabel("X axis:"))
        self.fft_plot.controls_layout.insertWidget(1, self.x_axis_mode_combo)
        self.fft_plot.controls_layout.insertSpacing(2, 10)
        self.fft_plot.controls_layout.insertWidget(3, QLabel("Y Axis:"))
        self.fft_plot.controls_layout.insertWidget(4, self.signal_source_combo)
        self.fft_plot.controls_layout.insertSpacing(5, 20)

        # Connect cursor movements and range changes to parameter updates
        self.fft_plot.cursorsMoved.connect(self.on_cursors_moved)
        self.fft_plot.rangeChanged.connect(lambda: self.update_fft_parameters())
        plot_container_layout.addWidget(self.fft_plot)
        
        analysis_layout.addWidget(plot_container)
        
        main_splitter.addWidget(analysis_area)
        main_splitter.setSizes([250, 750])
        
        layout.addWidget(main_splitter)
        
        self.last_selected_dataset = None

    def load_file(self, filepath: str):
        """
        Load file structure into the tree.

        Parameters
        ----------
        filepath : str
            The absolute path to the HDF5 file to load.
        """
        self.current_file = filepath
        self.tree_widget.clear()
        self.fft_plot.clear_plot()
        self.last_selected_dataset = None
        
        try:
            structure = h5_utils.load_h5_structure(filepath)
            root = QTreeWidgetItem(self.tree_widget, ["/ (root)"])
            root.setData(0, Qt.UserRole, {'path': '/', 'type': 'group'})
            if '_children' in structure:
                self._add_tree_items(root, structure['_children'], '')
            self.tree_widget.expandToDepth(0)
        except Exception as e:
            logging.error(f"Error loading file in Analysis: {e}")

    def _add_tree_items(self, parent_item, structure, parent_path):
        """
        Recursive helper to populate the tree widget.

        Parameters
        ----------
        parent_item : QTreeWidgetItem
            The parent item in the tree to attach children to.
        structure : dict
            The dictionary representing the folder structure.
        parent_path : str
            The path of the parent node in the HDF5 file.
        """
        for key, value in structure.items():
            if key.startswith('_'): continue
            current_path = f"{parent_path}/{key}" if parent_path else key
            item_type = value.get('_type')
            label = f"📁 {key}" if item_type == 'group' else f"📊 {key} {value.get('_shape', '')}"
            item = QTreeWidgetItem(parent_item, [label])
            item.setData(0, Qt.UserRole, {'path': current_path, 'type': item_type})
            if item_type == 'group' and '_children' in value:
                self._add_tree_items(item, value['_children'], current_path)

    def on_tree_item_clicked(self, item, column):
        """
        Handle click events on the tree widget items.

        Parameters
        ----------
        item : QTreeWidgetItem
            The item that was clicked.
        column : int
            The column index that was clicked.
        """
        data = item.data(0, Qt.UserRole)
        if not data or data.get('type') != 'dataset':
            return
        
        self.last_selected_dataset = data.get('path')
        
        # Update signal source options
        self.signal_source_combo.blockSignals(True)
        try:
            self.signal_source_combo.clear()
            # Get info to know columns without loading everything
            info = h5_utils.get_dataset_info(self.current_file, self.last_selected_dataset)
            if info and 'shape' in info:
                shape = info['shape']
                if len(shape) == 1:
                    self.signal_source_combo.addItem("Signal (1D)", 0)
                elif len(shape) == 2:
                    # Try to get labels
                    data_temp, columns = h5_utils.get_dataset_data(self.current_file, self.last_selected_dataset)
                    for i, col in enumerate(columns):
                        self.signal_source_combo.addItem(col, i)
        finally:
            self.signal_source_combo.blockSignals(False)
            
        self.update_fft_plot()
        
    def update_fft_plot_view_only(self):
        """
        Update only the Y-axis displayed in the plot without recalculating FFT.

        Synchronizes the PlotWidget's Y-axis selection with the AnalysisTab's
        unit selector.
        """
        if not self.last_selected_dataset or not self.cached_fft_results:
            return
            
        # Column mapping based on set_data call in update_fft_plot
        # 0: Freq, 1: Mag, 2: Mag (dB), 3: Phase
        view_mode = self.y_axis_view_combo.currentText()
        if "dB" in view_mode:
            self.fft_plot.y_axis_combo.setCurrentText("Magnitude (dB)")
        elif "Phase" in view_mode:
            self.fft_plot.y_axis_combo.setCurrentText("Phase")
        else:
            self.fft_plot.y_axis_combo.setCurrentText("Magnitude")

    def on_cursors_moved(self, x1, x2):
        """
        Update FFT parameters when cursors move.

        Parameters
        ----------
        x1 : float
            Position of the first cursor.
        x2 : float
            Position of the second cursor.
        """
        # We only update parameters (Peak, THD) based on the selection
        # No need for full plot reload (update_fft_plot) for performance
        self.update_fft_parameters(c1=x1, c2=x2)

    def update_fft_plot(self):
        """
        Calculate and plot the FFT of the selected dataset.

        Reads the sampling frequency and other configuration from UI,
        performs the FFT calculation using math_utils, updates the cached results,
        and triggers a full plot update in the PlotWidget.
        """
        if not self.last_selected_dataset or not self.current_file:
            return
            
        try:
            # Parse Fs in kHz
            try:
                fs_khz = float(self.fs_input.text())
                if fs_khz <= 0: fs_khz = 1000.0
                fs = fs_khz * 1e3 # Convert to Hz for calculation
            except ValueError:
                fs_khz = 1000.0
                fs = 1e3
                
                
            data, columns = h5_utils.get_dataset_data(self.current_file, self.last_selected_dataset)
            
            # Select column based on combo
            col_idx = self.signal_source_combo.currentData()
            if col_idx is None: col_idx = 0
            
            if len(data.shape) == 1:
                self.current_signal = data
            elif len(data.shape) == 2:
                # Ensure index is within bounds
                if col_idx < data.shape[1]:
                    self.current_signal = data[:, col_idx]
                else:
                    self.current_signal = data[:, 0]
            else:
                self.fft_plot.clear_plot("Dataset dimensionality too high for FFT")
                return

            # Perform FFT on FULL signal for the main plot
            window_name = self.window_combo.currentText()
            results = math_utils.calculate_fft(self.current_signal, fs, window_name)
            
            if results is None:
                return
                
            # Cache results
            self.cached_fft_results = results # Cache for parameter updates
            freqs, magnitude, phase, mag_db, thd = results
            
            # Determine X data and labels
            x_mode = self.x_axis_mode_combo.currentText()
            if x_mode == "Index":
                x_data = np.arange(len(magnitude))
                x_label = "Index"
            else:
                x_data = freqs / 1e3 # kHz
                x_label = "Frequency (kHz)"
            
            # Plot FFT
            fft_data = np.column_stack((x_data, magnitude, mag_db, phase))
            
            # Determine X-axis type (linear or log)
            x_scale = 'log' if self.log_x_check.isChecked() else 'linear'
            
            # Reset Plot Range to 50% for new FFT calculation
            if hasattr(self.fft_plot, 'end_input'):
                self.fft_plot.end_input.blockSignals(True)
                self.fft_plot.end_input.setText("50")
                self.fft_plot.end_input.blockSignals(False)
            
            self.fft_plot.set_data(
                fft_data, 
                [x_label, "Magnitude", "Magnitude (dB)", "Phase"], 
                f"FFT: {self.last_selected_dataset}",
                x_axis_type=x_scale,
                plot_style='stem'
            )
            
            # Set the requested Y-axis view
            self.update_fft_plot_view_only()

            # Sync parameters (Peak, THD) to current cursors immediately
            self.on_cursors_moved(self.fft_plot.cursor1_pos, self.fft_plot.cursor2_pos)
            
            # Update parameters (Peak, THD)
            self.update_fft_parameters()
            
        except Exception as e:
            logging.error(f"Error calculating FFT: {e}")
            self.fft_plot.clear_plot(f"FFT Error: {str(e)}")

    def update_fft_parameters(self, c1=None, c2=None):
        """
        Update Peak Frequency, Magnitude and THD labels.

        Calculates peak and THD based on the selected frequency range (if cursors
        are active) or the specified visual range, using the cached FFT results.

        Parameters
        ----------
        c1 : float, optional
            Position of cursor 1, by default None (uses current widget value).
        c2 : float, optional
            Position of cursor 2, by default None (uses current widget value).
        """
        if not hasattr(self, 'cached_fft_results') or self.cached_fft_results is None:
            return
            
        try:
            freqs, magnitude, phase, mag_db, thd = self.cached_fft_results
            
            # Use provided cursors or fall back to widget's current state
            if c1 is None: c1 = self.fft_plot.cursor1_pos
            if c2 is None: c2 = self.fft_plot.cursor2_pos
            
            # Determine range from cursors or visual view
            x_mode = self.x_axis_mode_combo.currentText()
            cursors_active = (self.fft_plot.active_cursor_mode != 'off') and (c1 is not None) and (c2 is not None)
            
            use_subrange = cursors_active
            
            if cursors_active:
                # Determine X vector for masking from cursors
                if x_mode == "Index":
                    x_vec = np.arange(len(magnitude))
                    f_min, f_max = min(c1, c2), max(c1, c2)
                else:
                    x_vec = freqs
                    f_min = min(c1, c2) * 1e3 # Convert kHz back to Hz
                    f_max = max(c1, c2) * 1e3
            else:
                # Fallback to visual range if it's not the full 100%
                try:
                    e_pct = float(self.fft_plot.end_input.text().replace('%', '') or 100)
                    if e_pct < 99.99:
                        use_subrange = True
                        if x_mode == "Index":
                            x_vec = np.arange(len(magnitude))
                            f_min = 0
                            f_max = (e_pct / 100.0) * len(magnitude)
                        else:
                            x_vec = freqs
                            f_min = 0
                            f_max = (e_pct / 100.0) * freqs[-1]
                    else:
                        use_subrange = False
                except:
                    use_subrange = False

            if use_subrange:
                mask = (x_vec >= f_min) & (x_vec <= f_max)
                
                if np.any(mask):
                    sel_freqs = freqs[mask]
                    sel_mag = magnitude[mask]
                    peak_f, peak_m = math_utils.find_peak(sel_freqs, sel_mag)
                    
                    # Recalculate THD with this peak as fundamental
                    # Use FULL arrays to ensure harmonics outside the cursor range are included
                    current_thd = math_utils.calculate_thd(magnitude, freqs, fundamental_freq=peak_f)
                else:
                    peak_f, peak_m = 0, 0
                    current_thd = 0.0
            else:
                # No cursors - use full spectrum
                peak_f, peak_m = math_utils.find_peak(freqs, magnitude)
                current_thd = thd # Default full spectrum THD

            # Update labels
            if x_mode == "Index":
                # Find peak index
                peak_idx = np.argmin(np.abs(freqs - peak_f))
                self.peak_freq_val.setText(f"Idx: {peak_idx}")
            else:
                self.peak_freq_val.setText(f"{peak_f/1e3:.4f} kHz")
            self.peak_mag_val.setText(f"{peak_m:.4g}")
            self.thd_val.setText(f"{current_thd:.2f} %")
            
        except Exception as e:
            logging.error(f"Error updating FFT parameters: {e}")
