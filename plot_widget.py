"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

Interactive Plot Widget using Plotly
Provides interactive plotting with dual cursors and statistics
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
                             QLabel, QPushButton, QGroupBox, QGridLayout, QFileDialog, QMessageBox, QCheckBox)
from PyQt5.QtCore import Qt, QUrl, pyqtSlot, QObject, QTimer, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from typing import Optional, Tuple
import math_utils
import json
import os
import tempfile
import logging


class WebPage(QWebEnginePage):
    """
    Custom web page to capture console logs from the embedded browser.
    """
    def javaScriptConsoleMessage(self, level, message, line, sourceID):
        """
        Handle JavaScript console messages.
        
        Parameters
        ----------
        level : int
            Log level.
        message : str
            Log message.
        line : int
            Line number.
        sourceID : str
            Source ID.
        """
        # logging.debug(f"JS Console [{level}]: {message} (line {line})")


class CursorBridge(QObject):
    """
    Bridge for communication between JS (Plotly) and Python.
    """
    def __init__(self, parent):
        """
        Initialize the bridge.
        """
        super().__init__(parent)
        self.parent = parent
        self._last_cursor_moved = 2 # Start by moving P1 (alternating)

    @pyqtSlot(float, float)
    def on_click(self, x, y):
        """
        Called when user clicks on the plot.
        
        Parameters
        ----------
        x : float
            X coordinate of the click.
        y : float
            Y coordinate of the click.
        """
        # logging.debug(f"CursorBridge.on_click - x={x}, mode={self.parent.active_cursor_mode}")
        
        # Respect the selected cursor mode
        if self.parent.active_cursor_mode == 'p1':
            self.parent.cursor1_pos = x
        elif self.parent.active_cursor_mode == 'p2':
            self.parent.cursor2_pos = x
        else:
            # 'auto' - alternating behavior
            if self._last_cursor_moved == 1:
                self.parent.cursor2_pos = x
                self._last_cursor_moved = 2
            else:
                self.parent.cursor1_pos = x
                self._last_cursor_moved = 1
        
        # Move cursor in JS for fluidity, then update stats in Python
        self.parent.move_cursors_js()
        # Emit signal so other components (AnalysisTab) update their parameters
        self.parent.cursorsMoved.emit(self.parent.cursor1_pos, self.parent.cursor2_pos)

    @pyqtSlot(float, float)
    def on_move(self, x1, x2):
        """
        Called for real-time updates (during or after movement).
        
        Parameters
        ----------
        x1 : float
            Position of cursor 1.
        x2 : float
            Position of cursor 2.
        """
        self.parent.cursor1_pos = x1
        self.parent.cursor2_pos = x2
        self.parent.update_statistics_only()
        # Emit signal for other components (like AnalysisTab) to react
        self.parent.cursorsMoved.emit(x1, x2)

    @pyqtSlot(str)
    def on_error(self, message):
        """
        Log errors from the JS/Plotly frontend.
        
        Parameters
        ----------
        message : str
            Error message from frontend.
        """
        logging.error(f"FRONTEND ERROR: {message}")

    @pyqtSlot()
    def on_ready(self):
        """
        Signal that the plot has finished rendering.

        Triggers logs or actions once Plotly is fully loaded in the browser.
        """
        # logging.debug(f"Plotly render COMPLETE for {self.parent.dataset_name}")


class PlotWidget(QWidget):
    """
    Interactive plot widget with Plotly integration.
    
    Provides capabilities for plotting 1D/2D data, interacting with cursors,
    calculating statistics, and exporting data.
    """
    
    # Signals
    cursorsMoved = pyqtSignal(float, float)
    rangeChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        """
        Initialize the PlotWidget.
        
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget, by default None.
        """
        super().__init__(parent)
        self.data = None
        self.columns = []
        self.cursor1_pos = None
        self.cursor2_pos = None
        self.dataset_name = ""
        self.current_x_series = None # For stats calculation
        self.current_y_series = None
        self.active_cursor_mode = 'off' # 'p1', 'p2', 'auto', or 'off'
        self.x_axis_type = 'linear' # 'linear' or 'log'
        self.plot_style = 'line' # 'line' or 'stem'
        
        # Set up QWebChannel for JS-Python communication
        self.channel = QWebChannel()
        self.bridge = CursorBridge(self)
        self.channel.registerObject("bridge", self.bridge)
        
        self.setup_ui()
        self.plot_view.setPage(WebPage(self.plot_view))
        self.plot_view.page().setWebChannel(self.channel)
        
        # Initialize with a welcome message
        self.plot_view.setHtml("<div style='display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;'><h3>Select a dataset to plot</h3></div>")
    
    def setup_ui(self):
        """
        Setup the user interface.
        
        Creates controls for axis selection, cursor modes, export button,
        the web view for the plot, and the statistics panel.
        """
        layout = QVBoxLayout(self)
        
        # Axis selection controls
        self.controls_layout = QHBoxLayout()
        
        self.x_axis_label = QLabel("X Axis:")
        self.controls_layout.addWidget(self.x_axis_label)
        self.x_axis_combo = QComboBox()
        self.x_axis_combo.currentIndexChanged.connect(self.update_plot)
        self.controls_layout.addWidget(self.x_axis_combo)
        
        self.y_axis_label = QLabel("Y Axis:")
        self.controls_layout.addWidget(self.y_axis_label)
        self.y_axis_combo = QComboBox()
        self.y_axis_combo.currentIndexChanged.connect(self.update_plot)
        self.controls_layout.addWidget(self.y_axis_combo)
        
        self.controls_layout.addSpacing(20)
        
        # Cursor selection buttons
        self.controls_layout.addWidget(QLabel("Cursors:"))
        
        base_style = """
            QPushButton { 
                padding: 5px 12px; 
                font-size: 9pt; 
                border: 2px solid #DCDDE1;
                border-radius: 5px;
                background-color: white;
                color: #57606f;
            }
            QPushButton:hover { background-color: #F1F2F6; }
        """
        
        style_c1 = base_style + """
            QPushButton:checked { 
                background-color: #ff7675; 
                border-color: #d63031;
                color: white;
                font-weight: bold;
            }
        """
        style_c2 = base_style + """
            QPushButton:checked { 
                background-color: #55efc4; 
                border-color: #00b894;
                color: #2d3436;
                font-weight: bold;
            }
        """
        style_auto = base_style + """
            QPushButton:checked { 
                background-color: #74b9ff; 
                border-color: #0984e3;
                color: white;
                font-weight: bold;
            }
        """
        style_off = base_style + """
            QPushButton:checked { 
                background-color: #b2bec3; 
                border-color: #636e72;
                color: white;
                font-weight: bold;
            }
        """
        
        self.btn_p1 = QPushButton("Cursor 1")
        self.btn_p1.setCheckable(True)
        self.btn_p1.setStyleSheet(style_c1)
        self.btn_p1.clicked.connect(lambda: self.set_cursor_mode('p1'))
        
        self.btn_p2 = QPushButton("Cursor 2")
        self.btn_p2.setCheckable(True)
        self.btn_p2.setStyleSheet(style_c2)
        self.btn_p2.clicked.connect(lambda: self.set_cursor_mode('p2'))
        
        self.btn_auto = QPushButton("Auto")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setChecked(False) # Unchecked by default
        self.btn_auto.setStyleSheet(style_auto)
        self.btn_auto.clicked.connect(lambda: self.set_cursor_mode('auto'))
        
        self.btn_off = QPushButton("Off")
        self.btn_off.setCheckable(True)
        self.btn_off.setChecked(True) # Checked by default
        self.btn_off.setStyleSheet(style_off)
        self.btn_off.clicked.connect(lambda: self.set_cursor_mode('off'))
        
        self.controls_layout.addWidget(self.btn_p1)
        self.controls_layout.addWidget(self.btn_p2)
        self.controls_layout.addWidget(self.btn_auto)
        self.controls_layout.addWidget(self.btn_off)
        
        self.controls_layout.addStretch()
        
        # Export button
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setObjectName("successButton")
        self.export_btn.clicked.connect(self.export_to_csv)
        self.export_btn.setEnabled(False)
        self.controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(self.controls_layout)
        
        # New: Plot Limit Inputs (End %)
        self.frag_layout = QHBoxLayout()
        self.frag_layout.addWidget(QLabel("Plot Range: 0% to"))
        
        from PyQt5.QtWidgets import QLineEdit
        
        # End Input
        self.end_input = QLineEdit("50")
        self.end_input.setFixedWidth(60)
        self.end_input.setStyleSheet("font-size: 10pt; font-weight: bold;")
        self.end_input.setPlaceholderText("100")
        self.end_input.editingFinished.connect(self.update_plot)
        self.end_input.textChanged.connect(self.validate_range_ui) # Immediate feedback
        self.frag_layout.addWidget(self.end_input)
        
        self.frag_layout.addWidget(QLabel("%"))
        self.frag_layout.addStretch()
        
        layout.addLayout(self.frag_layout)


        # Plotly web view
        self.plot_view = QWebEngineView()
        self.plot_view.setMinimumHeight(400)
        # Set a white background to match Plotly and verify visibility
        self.plot_view.setStyleSheet("background-color: white;")
        layout.addWidget(self.plot_view, stretch=3)
        
        # Statistics group
        stats_group = QGroupBox("Statistics (between cursors)")
        stats_layout = QGridLayout()
        
        # Labels for statistics
        self.stats_labels = {}
        stats = ['Average', 'RMS', 'Pk-Pk', 'Max', 'Min', 'Std Dev']
        for i, stat in enumerate(stats):
            label = QLabel(f"{stat}:")
            label.setStyleSheet("font-weight: bold;")
            value = QLabel("---")
            value.setObjectName(f"stat_{stat.lower().replace(' ', '_')}")
            
            stats_layout.addWidget(label, i // 3, (i % 3) * 2)
            stats_layout.addWidget(value, i // 3, (i % 3) * 2 + 1)
            
            self.stats_labels[stat] = value
        
        stats_group.setLayout(stats_layout)
        self.stats_group = stats_group
        layout.addWidget(self.stats_group, stretch=1)

    def validate_range_ui(self):
        """
        Provide immediate visual feedback for range inputs.

        Checks the validity of the percentage input in the UI and applies
        error styles (red background) if the values are out of bounds.
        """
        try:
            e_txt = self.end_input.text().strip().replace(',', '.').replace('%', '')
            e = float(e_txt) if e_txt else 100.0
            
            error_style = "font-size: 10pt; font-weight: bold; background-color: #fab1a0; border: 2px solid #e17055;"
            normal_style = "font-size: 10pt; font-weight: bold; background-color: white; border: 1px solid #DCDDE1;"
            
            e_valid = 0 < e <= 100
            
            self.end_input.setStyleSheet(normal_style if e_valid else error_style)
        except ValueError:
            pass
    
    def set_data(self, data: np.ndarray, columns: list, dataset_name: str = "", x_axis_type: str = 'linear', plot_style: str = 'line'):
        """
        Set data for plotting.
        
        Parameters
        ----------
        data : np.ndarray
            The dataset to plot.
        columns : list
            List of column names for the dataset.
        dataset_name : str, optional
            Name of the dataset, by default "".
        x_axis_type : str, optional
            Type of X axis ('linear' or 'log'), by default 'linear'.
        plot_style : str, optional
            Style of plot ('line' or 'stem'), by default 'line'.
        """
        if data is None:
            # logging.debug(f"set_data called with None for {dataset_name}")
            self.clear_plot("No data to display (None)")
            return
            
        # logging.debug(f"set_data called for dataset: {dataset_name}")
        # logging.debug(f"Data shape: {data.shape}, dtype: {data.dtype}")
        
        self.data = data
        self.dataset_name = dataset_name
        self.x_axis_type = x_axis_type
        self.plot_style = plot_style
        
        # Block signals to avoid multiple update_plot calls during setup
        self.x_axis_combo.blockSignals(True)
        self.y_axis_combo.blockSignals(True)
        
        try:
            self.x_axis_combo.clear()
            self.y_axis_combo.clear()
            
            # Determine available columns
            if data.dtype.names:
                # Structured array (Compound type) - use field names
                self.columns = list(data.dtype.names)
            elif len(data.shape) == 1:
                # Simple 1D array
                self.columns = ['Value']
            elif len(data.shape) == 2:
                # Simple 2D array
                if not columns or len(columns) != data.shape[1]:
                    self.columns = [f'Col_{i}' for i in range(data.shape[1])]
                else:
                    self.columns = columns
            else:
                self.columns = []
            
            # Always add Index option
            axis_options = ['Index'] + self.columns
            self.x_axis_combo.addItems(axis_options)
            self.y_axis_combo.addItems(axis_options)
            
            # [SMART DEFAULT SELECTION]
            x_idx = 0 # Default to Index
            y_idx = 1 # Default to first data column (Index is 0)
            
            # Look for Frequency for X
            for i, col in enumerate(axis_options):
                if "freq" in col.lower():
                    x_idx = i
                    break
            
            # Look for Magnitude or Value or Column_0 for Y
            y_candidates = ["magnitude", "mag", "value", "column_0", "val"]
            found_y = False
            for cand in y_candidates:
                for i, col in enumerate(axis_options):
                    if i == x_idx: continue # Don't select the same as X
                    if cand in col.lower():
                        y_idx = i
                        found_y = True
                        break
                if found_y: break
            
            if len(axis_options) > x_idx:
                self.x_axis_combo.setCurrentIndex(x_idx)
            if len(axis_options) > y_idx:
                self.y_axis_combo.setCurrentIndex(y_idx)
            
            # If we had an external X selected, keep it if possible
            if getattr(self, 'external_x_name', None):
                idx = self.x_axis_combo.findText(f"External: {self.external_x_name}")
                if idx >= 0:
                    self.x_axis_combo.setCurrentIndex(idx)
                    
        finally:
            self.x_axis_combo.blockSignals(False)
            self.y_axis_combo.blockSignals(False)
        
        # Initial cursor setup if needed
        if self.cursor1_pos is None or self.cursor2_pos is None:
            self.cursor1_pos = 0.0
            self.cursor2_pos = 1.0
            
        self.export_btn.setEnabled(len(self.columns) > 0)
        try:
            # Auto-calculate display limits based on data size (Performance)
            if self.data is not None:
                # Assuming simple 1D or 2D structure length
                point_count = len(self.data)
                self.auto_calc_limit(point_count)
            
            # logging.debug(f"Triggering update_plot for {dataset_name}")
            self.update_plot()
        except Exception as e:
            logging.error(f"CRITICAL ERROR in set_data invoking update_plot: {e}")
            import traceback
            traceback.print_exc()

    def set_external_x(self, data: np.ndarray, name: str):
        """
        Set an external dataset to be used as X-axis.
        
        Parameters
        ----------
        data : np.ndarray
            Data to use for X-axis.
        name : str
            Name of the external dataset.
        """
        self.external_x_data = data
        self.external_x_name = name
        
        # Update combo box
        self.x_axis_combo.blockSignals(True)
        try:
            # Check if already exists
            idx = self.x_axis_combo.findText(f"External: {name}")
            if idx < 0:
                self.x_axis_combo.addItem(f"External: {name}")
                idx = self.x_axis_combo.count() - 1
            self.x_axis_combo.setCurrentIndex(idx)
        finally:
            self.x_axis_combo.blockSignals(False)
        self.update_plot()

    def set_cursor_mode(self, mode):
        """
        Set the active cursor mode and update button states.
        
        Parameters
        ----------
        mode : str
            One of 'p1', 'p2', 'auto', 'off'.
        """
        self.active_cursor_mode = mode
        self.btn_p1.setChecked(mode == 'p1')
        self.btn_p2.setChecked(mode == 'p2')
        self.btn_auto.setChecked(mode == 'auto')
        self.btn_off.setChecked(mode == 'off')
        
        # Immediate JS update to hide/show cursors
        if mode == 'off':
            self.plot_view.page().runJavaScript("hideCursorsJS(true);")
        else:
            self.plot_view.page().runJavaScript("hideCursorsJS(false);")
            self.move_cursors_js()
            
        self.update_statistics_only()
        # Emit signal to inform AnalysisTab that parameters need update (e.g. following mode change)
        self.cursorsMoved.emit(self.cursor1_pos if self.cursor1_pos is not None else 0.0, 
                               self.cursor2_pos if self.cursor2_pos is not None else 0.0)
        # logging.debug(f"Active cursor mode set to {mode}")

    def set_axis_selectors_visible(self, visible: bool):
        """
        Show or hide the default X/Y axis selectors and labels.
        
        Parameters
        ----------
        visible : bool
            True to show, False to hide.
        """
        self.x_axis_label.setVisible(visible)
        self.x_axis_combo.setVisible(visible)
        self.y_axis_label.setVisible(visible)
        self.y_axis_combo.setVisible(visible)

    def set_stats_visible(self, visible: bool):
        """
        Show or hide the statistics panel.
        
        Parameters
        ----------
        visible : bool
            True to show, False to hide.
        """
        self.stats_group.setVisible(visible)

    def get_column_data(self, column_name: str) -> np.ndarray:
        """
        Extract data for a specific column name.
        
        Parameters
        ----------
        column_name : str
            Name of the column to retrieve.
            
        Returns
        -------
        np.ndarray
            Data array for the requested column.
        """
        if column_name == 'Index':
            if self.data is not None:
                return np.arange(len(self.data))
            return np.array([0])
            
        if column_name.startswith("External: "):
            return self.external_x_data
            
        try:
            val = None
            # Handle 1D array
            if len(self.data.shape) == 1:
                if column_name == 'Value' or column_name == self.columns[0]:
                    val = self.data
            # Handle 2D array
            elif len(self.data.shape) == 2:
                try:
                    col_idx = self.columns.index(column_name)
                    val = self.data[:, col_idx]
                except (ValueError, IndexError):
                    pass
            
            if val is not None:
                return val.astype(float)
                
        except Exception as e:
            logging.error(f"Error getting column data for {column_name}: {e}")
            
        return np.array([0.0])
    
    def auto_calc_limit(self, total_points: int):
        """
        Auto-calculate start/end % to keep points within a safe limit.

        Adjusts the 'end_input' percentage to ensure the plotted data stays 
        below a predefined threshold for performance reasons.

        Parameters
        ----------
        total_points : int
            Total number of data points in the series.
        """
        # No auto-limit for FFT/Stem style
        if self.plot_style == 'stem':
            return

        SAFE_LIMIT = 10000
        if total_points <= SAFE_LIMIT:
            self.end_input.setText("50")
        else:
            pct_needed = (SAFE_LIMIT / total_points) * 100.0
            final_pct = min(50.0, pct_needed)
            self.end_input.setText(f"{final_pct:.2f}")

    def update_plot(self):
        """
        Redraw the plot with current axis and data.

        Gathers the current column selections, slices the data according to the
        range settings, applies log/linear scaling, and generates the Plotly
        HTML for display in the QWebEngineView.
        """
        # Prepare data for plotting
        x_col = self.x_axis_combo.currentText()
        y_col = self.y_axis_combo.currentText()
        
        # logging.debug(f"update_plot - X='{x_col}', Y='{y_col}'")
        
        if not x_col or not y_col:
            # logging.debug(f"update_plot - missing axis")
            return
            
        x_data = self.get_column_data(x_col)
        y_data = self.get_column_data(y_col)
        
        if x_data is None or y_data is None or len(x_data) == 0:
            # logging.debug(f"update_plot - no data series")
            return
            
        # Store for statistics calculation
        self.current_x_series = x_data
        self.current_y_series = y_data
        
        # Initialize cursors if not set or out of bounds
        try:
            x_min_data = np.nanmin(x_data)
            x_max_data = np.nanmax(x_data)
            if np.isnan(x_min_data) or np.isnan(x_max_data) or x_min_data == x_max_data:
                self.cursor1_pos = 0.0
                self.cursor2_pos = 1.0
            else:
                # Initialize cursors to 10% and 90% of range if not set
                if self.cursor1_pos is None:
                    self.cursor1_pos = float(x_min_data + (x_max_data - x_min_data) * 0.1)
                if self.cursor2_pos is None:
                    self.cursor2_pos = float(x_min_data + (x_max_data - x_min_data) * 0.9)
                
                # Boundary check - if cursors are way out of current data range, reset them
                if self.cursor1_pos < x_min_data - (x_max_data - x_min_data)*2 or \
                   self.cursor1_pos > x_max_data + (x_max_data - x_min_data)*2:
                    self.cursor1_pos = float(x_min_data + (x_max_data - x_min_data) * 0.1)
                if self.cursor2_pos < x_min_data - (x_max_data - x_min_data)*2 or \
                   self.cursor2_pos > x_max_data + (x_max_data - x_min_data)*2:
                    self.cursor2_pos = float(x_min_data + (x_max_data - x_min_data) * 0.9)
        except (ValueError, TypeError):
            self.cursor1_pos = 0.0
            self.cursor2_pos = 1.0
        
        # FRAGMENT VIEW (End % only, start always 0%)
        start_pct = 0.0
        
        # Helper to parse and styling
        def parse_input(line_edit, default_val):
            # Strip whitespace and common units/symbols
            txt = line_edit.text().strip().replace(',', '.').replace('%', '').replace(' ', '')
            try:
                if not txt: return default_val
                val = float(txt)
                return val
            except ValueError:
                logging.error(f"Failed to parse input '{txt}' for percentage, using default {default_val}")
                return default_val

        end_pct = parse_input(self.end_input, 50.0)
            
        # Clamp and ensure validity
        end_pct = max(0.1, min(100.0, end_pct))
            
        # Calculate indices based on percentage of TOTAL points
        total_len = len(x_data)
        
        # Round to nearest integer index with safety margin
        idx_start = 0
        idx_end = int(max(1, min(total_len, total_len * (end_pct / 100.0))))
        
        # Final UI Feedback for invalid ranges before plotting
        error_style = "font-size: 10pt; font-weight: bold; background-color: #fab1a0; border: 2px solid #e17055;"
        normal_style = "font-size: 10pt; font-weight: bold; background-color: white; border: 1px solid #DCDDE1;"
        
        if end_pct <= 0 or end_pct > 100:
            self.end_input.setStyleSheet(error_style)
        else:
            self.end_input.setStyleSheet(normal_style)

        # SLICE THE DATA FRESH (No Truncation)
        x_plot = x_data[idx_start:idx_end]
        y_plot = y_data[idx_start:idx_end]

        # Emit that range has changed
        self.rangeChanged.emit()
        
        title = self.dataset_name or f"{y_col} vs {x_col}"
        if start_pct > 0 or end_pct < 100:
            title += f" (Range: {start_pct:.2f}% - {end_pct:.2f}%)"
            
        # Filter valid data for Log X if needed (Global filter)
        if self.x_axis_type == 'log':
             valid_mask = (x_plot > 0) & np.isfinite(x_plot)
             if np.any(valid_mask):
                 x_p_list = x_plot[valid_mask].tolist()
                 y_p_list = y_plot[valid_mask].tolist()
                 # Re-assign x_plot as well for range calculations later
                 x_plot = x_plot[valid_mask]
                 y_plot = y_plot[valid_mask]
             else:
                 # Fallback if everything is <= 0
                 x_p_list, y_p_list = [], []
        else:
             # Fast numeric conversion for linear
             x_p_list = x_plot.tolist()
             y_p_list = y_plot.tolist()

        num_points = len(x_p_list)
        if num_points == 0:
            self.plot_view.setHtml("<div style='display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;'><h3>No valid data points to plot</h3></div>")
            return

        # Create the plot configuration
        config = {
            'responsive': True, 
            'displaylogo': False, 
            'scrollZoom': True,
            'editable': False, # Manual dragging is more fluid
            'modeBarButtonsToRemove': ['lasso2d']
        }
        
        # Build traces based on style
        data_traces = []
        
        if self.plot_style == 'stem':
            # Adaptive Strategy:
            # If few points, show pretty Stems (Lines + Markers).
            POINT_THRESHOLD_STEM = 5000 
            
            num_points = len(x_p_list)

            if num_points <= POINT_THRESHOLD_STEM:
                # LOW DENSITY: Draw actual Stems using SVG (scatter)
                try:
                    full_min = np.nanmin(self.current_y_series) if self.current_y_series is not None else 0
                    if np.isnan(full_min): full_min = 0
                    base_y = full_min if full_min < 0 else 0
                except: base_y = 0
                
                stem_x = []
                stem_y = []
                for x, y in zip(x_p_list, y_p_list):
                    if x is not None and y is not None:
                        stem_x.extend([x, x, None])
                        stem_y.extend([base_y, y, None])
                
                data_traces.append({
                    'x': stem_x,
                    'y': stem_y,
                    'type': 'scatter', 
                    'mode': 'lines',
                    'line': {'color': '#2E86DE', 'width': 1.5},
                    'hoverinfo': 'skip',
                    'name': 'Stems'
                })
                
                data_traces.append({
                    'x': x_p_list,
                    'y': y_p_list,
                    'type': 'scatter',
                    'mode': 'markers',
                    'marker': {'size': 6, 'symbol': 'circle', 'color': '#2E86DE'},
                    'name': 'Data',
                    'hovertemplate': f'<b>{x_col}</b>: %{{x}}<br><b>{y_col}</b>: %{{y}}<extra></extra>'
                })
            
            else:
                # HIGH DENSITY: STILL USE STEMS, but move to ScatterGL for performance.
                try:
                    full_min = np.nanmin(self.current_y_series) if self.current_y_series is not None else 0
                    if np.isnan(full_min): full_min = 0
                    base_y = full_min if full_min < 0 else 0
                except: base_y = 0
                
                stem_x = []
                stem_y = []
                # Construct stem geometry
                for x, y in zip(x_p_list, y_p_list):
                    if x is not None and y is not None:
                        stem_x.extend([x, x, None])
                        stem_y.extend([base_y, y, None])

                data_traces.append({
                    'x': stem_x,
                    'y': stem_y,
                    'type': 'scattergl', # WebGL for Stems
                    'mode': 'lines',     
                    'line': {'color': '#2E86DE', 'width': 1}, # Thinner lines for density
                    'name': 'Stems',
                    'hoverinfo': 'skip'
                })
                
                data_traces.append({
                    'x': x_p_list,
                    'y': y_p_list,
                    'type': 'scattergl', # WebGL for Markers
                    'mode': 'markers',     
                    'marker': {'size': 5, 'symbol': 'circle', 'color': '#2E86DE'},
                    'name': 'Data',
                    'hovertemplate': f'<b>{x_col}</b>: %{{x}}<br><b>{y_col}</b>: %{{y}}<extra></extra>'
                })
            
        else:
            # Standard Line + Markers (View Tab Style)
            # Use scattergl for performance
            data_traces.append({
                'x': x_p_list,
                'y': y_p_list,
                'type': 'scattergl',
                'mode': 'lines+markers' if len(x_p_list) < 5000 else 'lines',
                'line': {'color': '#2E86DE', 'width': 1.5},
                'marker': {'size': 4, 'symbol': 'circle', 'color': '#2E86DE'},
                'name': 'Data',
                'hovertemplate': f'<b>{x_col}</b>: %{{x}}<br><b>{y_col}</b>: %{{y}}<extra></extra>'
            })
        
        # Add cursor lines and shaded region as SHAPES
        # Ensure cursor positions are valid for JSON (replace NaN/None with 0 for shapes)
        def safe_coord(v):
            if v is None or not np.isfinite(v): return 0.0
            return float(v)
 
        c1 = safe_coord(self.cursor1_pos)
        c2 = safe_coord(self.cursor2_pos)
        min_x_cursor = min(c1, c2)
        max_x_cursor = max(c1, c2)
        
        # Initial visibility based on mode
        cursor_opacity = 0 if self.active_cursor_mode == 'off' else 1
        fill_opacity = 0 if self.active_cursor_mode == 'off' else 0.2
 
        shapes = [
            # 0: P1 Line
            {
                'type': 'line', 'xref': 'x', 'yref': 'paper',
                'x0': c1, 'y0': 0, 'x1': c1, 'y1': 1,
                'line': {'color': 'red', 'width': 2, 'dash': 'dash'},
                'opacity': cursor_opacity
            },
            # 1: P2 Line
            {
                'type': 'line', 'xref': 'x', 'yref': 'paper',
                'x0': c2, 'y0': 0, 'x1': c2, 'y1': 1,
                'line': {'color': 'green', 'width': 2, 'dash': 'dash'},
                'opacity': cursor_opacity
            },
            # 2: Shaded Area
            {
                'type': 'rect', 'xref': 'x', 'yref': 'paper',
                'x0': min_x_cursor, 'y0': 0, 'x1': max_x_cursor, 'y1': 1,
                'fillcolor': 'rgba(46, 134, 222, 0.2)', 'opacity': fill_opacity, 'line': {'width': 0}, 'layer': 'below'
            }
        ]
 
        data_json = json.dumps(data_traces)
        
        xaxis_config = {
            'title': {'text': x_col}, 
            'gridcolor': '#ECF0F1', 
            'showgrid': True,
            'rangeslider': {'visible': False}
        }
        
        if self.x_axis_type == 'log':
            # Log scale requires explicit range in log10 for better stability
            xaxis_config['type'] = 'log'
            try:
                # x_plot is already filtered for > 0 at this point (Global filter)
                if len(x_plot) > 0:
                    x_min_val = np.nanmin(x_plot)
                    x_max_val = np.nanmax(x_plot)
                    
                    if x_min_val > 0 and x_max_val > x_min_val:
                        l_min = np.log10(x_min_val)
                        l_max = np.log10(x_max_val)
                        l_span = l_max - l_min
                        xaxis_config['autorange'] = False
                        # Set manual range (Plotly Log scale uses log10 units for the 'range' array)
                        xaxis_config['range'] = [float(l_min - l_span*0.01), float(l_max + l_span*0.01)]
                    else:
                         xaxis_config['autorange'] = True
                else:
                    xaxis_config['autorange'] = True
            except:
                xaxis_config['autorange'] = True
        else:
            xaxis_config['type'] = 'linear'
            xaxis_config['autorange'] = True
 
        layout_json = json.dumps({
            'title': {'text': title, 'font': {'size': 14, 'color': '#2C3E50'}},
            'xaxis': xaxis_config,
            'yaxis': {'title': {'text': y_col}, 'gridcolor': '#ECF0F1', 'showgrid': True},
            'margin': {'l': 60, 'r': 30, 't': 60, 'b': 60},
            'plot_bgcolor': 'white',
            'paper_bgcolor': 'white',
            'hovermode': 'x',
            'showlegend': True,
            'shapes': shapes,
            'height': None
        })
 
        # Build the HTML
        template = """
 <!DOCTYPE html>
 <html>
 <head>
     <meta charset="utf-8" />
     <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
     <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
     <style>
         body, html { margin: 0; padding: 0; height: 100%; width: 100%; overflow: hidden; background: white; user-select: none; }
         #plot-area { height: 100%; width: 100%; }
         /* Style to show the cursor is draggable */
         .cursor-hover { cursor: ew-resize !important; }
     </style>
     <script>
         (function() {
             try {
                 var original = CSSStyleSheet.prototype.insertRule;
                 CSSStyleSheet.prototype.insertRule = function(rule, index) {
                     try { return original.call(this, rule, index); } catch (e) { return 0; }
                 };
             } catch(e) {}
         })();
         
         var bridge;
         new QWebChannel(qt.webChannelTransport, function(channel) {
             bridge = channel.objects.bridge;
         });
 
         var activeCursor = null; 
 
         function updateCursorsJS(x1, x2) {
             var plotDiv = document.getElementById('plot-area');
             if (!plotDiv || !plotDiv._fullLayout) return;
             var min_x = Math.min(x1, x2);
             var max_x = Math.max(x1, x2);
             Plotly.relayout(plotDiv, {
                 'shapes[0].x0': x1, 'shapes[0].x1': x1,
                 'shapes[1].x0': x2, 'shapes[1].x1': x2,
                 'shapes[2].x0': min_x, 'shapes[2].x1': max_x
             });
         }
 
         function hideCursorsJS(hide) {
             var plotDiv = document.getElementById('plot-area');
             if (!plotDiv || !plotDiv._fullLayout) return;
             var opacity = hide ? 0 : 1;
             var fillOpacity = hide ? 0 : 0.2;
             Plotly.relayout(plotDiv, {
                 'shapes[0].opacity': opacity,
                 'shapes[1].opacity': opacity,
                 'shapes[2].opacity': fillOpacity
             });
         }
 
         window.addEventListener('load', function() {
             try {
                 window.onerror = function(msg, url, line) {
                     if (bridge) bridge.on_error("JS Error: " + msg + " at line " + line);
                 };
 
                 var data = DATA_JSON_PLACEHOLDER;
                 var layout = LAYOUT_JSON_PLACEHOLDER;
                 var config = CONFIG_JSON_PLACEHOLDER;
                 var plotDiv = document.getElementById('plot-area');
                 
                 Plotly.newPlot(plotDiv, data, layout, config).then(function() {
                     if (bridge) bridge.on_ready();
                 }).catch(function(err) {
                     if (bridge) bridge.on_error("Plotly Error: " + err.message);
                 });
                 
                 plotDiv.addEventListener('mousedown', function(evt) {
                     if (evt.button !== 0) return;
                     var fullLayout = plotDiv._fullLayout;
                     var xaxis = fullLayout.xaxis;
                     var rect = plotDiv.getBoundingClientRect();
                     var xPixel = evt.clientX - rect.left - fullLayout.margin.l;
                     
                     var p1Data = plotDiv.layout.shapes[0].x0;
                     var p2Data = plotDiv.layout.shapes[1].x0;
                     var p1Pixel = xaxis.c2p(p1Data);
                     var p2Pixel = xaxis.c2p(p2Data);
                     
                     var threshold = 15; // Grab threshold in pixels
                     if (Math.abs(xPixel - p1Pixel) < threshold) {
                         activeCursor = 0;
                         evt.preventDefault();
                     } else if (Math.abs(xPixel - p2Pixel) < threshold) {
                         activeCursor = 1;
                         evt.preventDefault();
                     } else if (xPixel >= 0 && xPixel <= xaxis._length) {
                         var xData = xaxis.p2c(xPixel);
                         if (bridge) bridge.on_click(xData, 0);
                     }
                 });
 
                 window.addEventListener('mousemove', function(evt) {
                     var fullLayout = plotDiv._fullLayout;
                     if (!fullLayout) return;
                     var xaxis = fullLayout.xaxis;
                     var rect = plotDiv.getBoundingClientRect();
                     var xPixel = evt.clientX - rect.left - fullLayout.margin.l;
                     
                     if (activeCursor === null) {
                         // Update mouse cursor style when near a line
                         var p1Data = plotDiv.layout.shapes[0].x0;
                         var p2Data = plotDiv.layout.shapes[1].x0;
                         var p1Pixel = xaxis.c2p(p1Data);
                         var p2Pixel = xaxis.c2p(p2Data);
                         
                         var threshold = 15; // Grab threshold in pixels
                         if (Math.abs(xPixel - p1Pixel) < threshold || Math.abs(xPixel - p2Pixel) < threshold) {
                             plotDiv.classList.add('cursor-hover');
                         } else {
                             plotDiv.classList.remove('cursor-hover');
                         }
                         return;
                     }
                     
                     xPixel = Math.max(0, Math.min(xPixel, xaxis._length));
                     var xData = xaxis.p2c(xPixel);
                     
                     var x1 = activeCursor === 0 ? xData : plotDiv.layout.shapes[0].x0;
                     var x2 = activeCursor === 1 ? xData : plotDiv.layout.shapes[1].x0;
                     var min_x = Math.min(x1, x2);
                     var max_x = Math.max(x1, x2);
                     
                     var update = {};
                     update['shapes['+activeCursor+'].x0'] = xData;
                     update['shapes['+activeCursor+'].x1'] = xData;
                     update['shapes[2].x0'] = min_x;
                     update['shapes[2].x1'] = max_x;
                     
                     Plotly.relayout(plotDiv, update);
                     if (bridge) bridge.on_move(x1, x2);
                 });
 
                 window.addEventListener('mouseup', function() { 
                     activeCursor = null; 
                 });
                 
                 window.addEventListener('resize', function() { Plotly.Plots.resize(plotDiv); });
             } catch(e) { console.error(e); }
         });
     </script>
 </head>
 <body><div id="plot-area"></div></body>
 </html>
 """
        html = template.replace("DATA_JSON_PLACEHOLDER", data_json)\
                       .replace("LAYOUT_JSON_PLACEHOLDER", layout_json)\
                       .replace("CONFIG_JSON_PLACEHOLDER", json.dumps(config))
                       
        # Inject a timestamp comment to force QWebEngine to treat it as new content
        import time
        html += f"<!-- force_refresh: {time.time()} -->"
 
        # logging.debug(f"setHtml called. Content size: {len(html)/1024:.1f} KB")
        self.plot_view.setHtml(html)
        
        # Save data for fast stats calculation
        self.current_x_series = x_data
        self.current_y_series = y_data
        
        self.update_statistics_only()

    def move_cursors_js(self):
        """Update cursor positions in JS without reloading the whole page."""
        if self.cursor1_pos is None or self.cursor2_pos is None:
            return
            
        js = f"updateCursorsJS({self.cursor1_pos}, {self.cursor2_pos});"
        self.plot_view.page().runJavaScript(js)
        self.update_statistics_only()

    def update_statistics_only(self):
        """Update only the statistics labels."""
        if self.current_x_series is not None and self.current_y_series is not None:
            self.update_statistics(self.current_x_series, self.current_y_series)
    
    def update_statistics(self, x_data: np.ndarray, y_data: np.ndarray):
        """
        Calculate and update statistics between cursors (or full dataset).
        
        Parameters
        ----------
        x_data : np.ndarray
            X data.
        y_data : np.ndarray
            Y data.
        """
        if self.active_cursor_mode == 'off':
            y_selected = y_data
        else:
            if self.cursor1_pos is None or self.cursor2_pos is None:
                return
            try:
                min_x = min(self.cursor1_pos, self.cursor2_pos)
                max_x = max(self.cursor1_pos, self.cursor2_pos)
                # Use a small epsilon for robust float comparison
                epsilon = 1e-12
                mask = (x_data >= min_x - epsilon) & (x_data <= max_x + epsilon)
                y_selected = y_data[mask]
                
                # Diagnostic logging
                # logging.debug(f"Stats range [{min_x:.4g}, {max_x:.4g}], Points in range: {len(y_selected)}/{len(y_data)}")
                if len(y_selected) > 0:
                    pass
                    # logging.debug(f"Calculated Max: {np.nanmax(y_selected):.6g}, Min: {np.nanmin(y_selected):.6g}")
            except Exception as e:
                logging.error(f"Error filtering stats data: {e}")
                return
        
        try:
            if len(y_selected) == 0:
                for label in self.stats_labels.values():
                    label.setText("---")
                return
                
            stats = math_utils.calculate_statistics(y_selected)
            
            # Update labels
            for name, value in stats.items():
                if name in self.stats_labels:
                    label = self.stats_labels[name]
                    if np.isnan(value) or np.isinf(value):
                        label.setText("---")
                    else:
                        label.setText(f"{value:.6g}")
        except Exception as e:
            logging.error(f"Error calculating stats: {e}")
            for label in self.stats_labels.values():
                label.setText("Error")
    
    def export_to_csv(self):
        """Export data to CSV file."""
        if self.data is None:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return
        
        try:
            # Determine which rows to export
            if self.active_cursor_mode != 'off' and self.cursor1_pos is not None and self.cursor2_pos is not None:
                # Use current X axis to define the range
                x_col = self.x_axis_combo.currentText()
                x_data = self.get_column_data(x_col)
                
                min_x = min(self.cursor1_pos, self.cursor2_pos)
                max_x = max(self.cursor1_pos, self.cursor2_pos)
                mask = (x_data >= min_x) & (x_data <= max_x)
                
                export_data = self.data[mask]
            else:
                # Export everything
                export_data = self.data
            
            # Create DataFrame
            if export_data.dtype.names:
                df = pd.DataFrame(export_data)
            else:
                if len(export_data.shape) == 1:
                    df = pd.DataFrame(export_data, columns=['Value'])
                else:
                    df = pd.DataFrame(export_data, columns=self.columns)
            
            df.to_csv(filename, index=False)
            logging.info(f"Data exported to {filename} ({len(df)} rows)")
            QMessageBox.information(self, "Export Success", f"Successfully exported {len(df)} rows to:\n{filename}")
            
        except Exception as e:
            logging.error(f"Error exporting CSV: {str(e)}")
            QMessageBox.critical(self, "Export Error", f"Failed to export CSV:\n{str(e)}")
    
    def clear_plot(self, message: str = ""):
        """
        Clear the current plot with an optional message.
        
        Parameters
        ----------
        message : str, optional
            Message to display, by default "".
        """
        self.data = None
        self.columns = []
        self.cursor1_pos = None
        self.cursor2_pos = None
        self.x_axis_combo.blockSignals(True)
        self.x_axis_combo.clear()
        self.y_axis_combo.clear()
        self.x_axis_combo.blockSignals(False)
        
        # Clear the plot view with an optional message
        if message:
            content = f"<div style='display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; color:#666;'><h3>{message}</h3></div>"
        else:
            content = ""
            
        self.plot_view.setHtml(content)
        
        for label in self.stats_labels.values():
            label.setText("---")
        
        self.export_btn.setEnabled(False)
