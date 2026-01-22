"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

Interactive Plot Widget using Matplotlib
Provides interactive plotting with dual cursors and statistics
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
                             QLabel, QPushButton, QGroupBox, QGridLayout, QFileDialog, QMessageBox, QCheckBox, QLineEdit)
from PyQt5.QtCore import Qt, pyqtSlot, QObject, QTimer, pyqtSignal
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter
import numpy as np
import pandas as pd
from typing import Optional, Tuple
import math_utils
import logging
import os

class PlotWidget(QWidget):
    """
    Interactive plot widget with Matplotlib integration.
    
    Provides capabilities for plotting 1D/2D data, interacting with cursors,
    calculating statistics, and exporting data.
    """
    
    # Signals for external components
    cursorsMoved = pyqtSignal(float, float) # (p1_pos, p2_pos)
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
        
        # Data storage
        self.data = None
        self.columns = []
        self.dataset_name = ""
        self.current_x_series = None
        self.current_y_series = None
        self.external_x_data = None
        self.external_x_name = ""
        
        # Plot state
        self.x_axis_type = 'linear'
        self.plot_style = 'line'
        self.active_cursor_mode = 'off'
        self.cursor1_pos = None
        self.cursor2_pos = None
        
        # Matplotlib interactive state
        self.dragging_cursor = None # 0 for P1, 1 for P2, None
        self.cursor_pick_threshold = 15 # Pixels
        
        # Color Palette (Consistent with App CSS and Modern Aesthetics)
        self.colors = {
            'main': '#1f77b4',      # Standard Plotly/Matplotlib Blue
            'p1': '#e74c3c',        # Alizarin Red
            'p2': '#27ae60',        # Nephritis Green
            'fill': '#3498db',      # Peter River Blue
            'bg': '#ffffff',
            'grid': '#f1f2f6',
            'text': '#2f3542'
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        """
        Setup the user interface.
        
        Creates controls for axis selection, cursor modes, export button,
        the Matplotlib canvas, and the statistics panel.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top Controls Bar
        self.controls_layout = QHBoxLayout()
        
        # Axis Selection
        self.x_axis_label = QLabel("X Axis:")
        self.x_axis_combo = QComboBox()
        self.x_axis_combo.currentIndexChanged.connect(self.update_plot)
        
        self.y_axis_label = QLabel("Y Axis:")
        self.y_axis_combo = QComboBox()
        self.y_axis_combo.currentIndexChanged.connect(self.update_plot)
        
        self.controls_layout.addWidget(self.x_axis_label)
        self.controls_layout.addWidget(self.x_axis_combo)
        self.controls_layout.addSpacing(10)
        self.controls_layout.addWidget(self.y_axis_label)
        self.controls_layout.addWidget(self.y_axis_combo)
        self.controls_layout.addSpacing(20)
        
        # Plot Range Percentage
        self.range_label = QLabel("Range (%):")
        self.start_input = QLineEdit("0")
        self.start_input.setFixedWidth(65)
        self.start_input.setToolTip("Start %")
        self.start_input.textChanged.connect(self.validate_range_ui)
        self.start_input.returnPressed.connect(self.update_plot)
        
        self.end_input = QLineEdit("100")
        self.end_input.setFixedWidth(65)
        self.end_input.setToolTip("End %")
        self.end_input.textChanged.connect(self.validate_range_ui)
        self.end_input.returnPressed.connect(self.update_plot)
        
        self.controls_layout.addWidget(self.range_label)
        self.controls_layout.addWidget(self.start_input)
        self.controls_layout.addWidget(QLabel("-"))
        self.controls_layout.addWidget(self.end_input)
        self.controls_layout.addSpacing(20)
        
        # Add spacing before cursors section
        self.controls_layout.addSpacing(15)
        
        # Cursor Mode
        self.controls_layout.addWidget(QLabel("Cursors:"))
        
        # Cursor Button Styles - White background with soft colors
        cursor_btn_base_style = """
            QPushButton { 
                background-color: #ffffff; 
                color: #2c3e50;
                border: 2px solid #bdc3c7; 
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover { 
                background-color: #f7f9f9;
                border: 2px solid #95a5a6;
            }
            QPushButton:checked { 
                color: white; 
                border: 2px solid #2c3e50;
                font-weight: bold;
            }
        """
        
        self.btn_p1 = QPushButton("Cursor 1")
        self.btn_p1.setCheckable(True)
        self.btn_p1.setFixedWidth(75)
        self.btn_p1.setStyleSheet(cursor_btn_base_style + "QPushButton:checked { background-color: #e74c3c; }")
        self.btn_p1.clicked.connect(lambda: self.set_cursor_mode('p1'))
        
        self.btn_p2 = QPushButton("Cursor 2")
        self.btn_p2.setCheckable(True)
        self.btn_p2.setFixedWidth(75)
        self.btn_p2.setStyleSheet(cursor_btn_base_style + "QPushButton:checked { background-color: #27ae60; }")
        self.btn_p2.clicked.connect(lambda: self.set_cursor_mode('p2'))
        
        self.btn_auto = QPushButton("Auto")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setFixedWidth(55)
        self.btn_auto.setStyleSheet(cursor_btn_base_style + "QPushButton:checked { background-color: #3498db; }")
        self.btn_auto.clicked.connect(lambda: self.set_cursor_mode('auto'))
        
        self.btn_off = QPushButton("Off")
        self.btn_off.setCheckable(True)
        self.btn_off.setChecked(True)
        self.btn_off.setFixedWidth(50)
        self.btn_off.setStyleSheet(cursor_btn_base_style + "QPushButton:checked { background-color: #34495e; }")
        self.btn_off.clicked.connect(lambda: self.set_cursor_mode('off'))
        
        self.controls_layout.addWidget(self.btn_p1)
        self.controls_layout.addWidget(self.btn_p2)
        self.controls_layout.addWidget(self.btn_auto)
        self.controls_layout.addWidget(self.btn_off)
        
        self.controls_layout.addStretch()
        
        # Export Button - Soft green style
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self.export_to_csv)
        self.export_btn.setEnabled(False)
        export_btn_style = """
            QPushButton {
                background-color: #a9dfbf;
                color: #145a32;
                border: 2px solid #82e0aa;
                border-radius: 4px;
                font-weight: bold;
                padding: 5px 12px;
            }
            QPushButton:hover:enabled {
                background-color: #52be80;
                border: 2px solid #27ae60;
                color: white;
            }
            QPushButton:pressed:enabled {
                background-color: #27ae60;
                border: 2px solid #1e8449;
            }
            QPushButton:disabled {
                background-color: #d5d8dc;
                color: #95a5a6;
                border: 2px solid #bdc3c7;
            }
        """
        self.export_btn.setStyleSheet(export_btn_style)
        self.controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(self.controls_layout)
        
        # Matplotlib Figure and Canvas - Reduced size to prevent label overlap
        self.figure = Figure(figsize=(5, 3.2), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        # Adjust subplot to prevent label cutoff
        self.figure.subplots_adjust(bottom=0.15, top=0.92, left=0.12, right=0.95)
        
        # Initialize cursor lines and fill (hidden) - Thinner lines
        self.line_p1 = self.ax.axvline(0, color=self.colors['p1'], linestyle='--', linewidth=1.0, visible=False, zorder=10)
        self.line_p2 = self.ax.axvline(0, color=self.colors['p2'], linestyle='--', linewidth=1.0, visible=False, zorder=10)
        self.region_fill = self.ax.axvspan(0, 0, color=self.colors['fill'], alpha=0.15, visible=False, zorder=5)
        
        # Toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # Create a container for the canvas to apply styling from QSS if needed
        self.plot_container = QWidget()
        self.plot_container.setObjectName("plotContainer")
        container_layout = QVBoxLayout(self.plot_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.canvas)
        container_layout.addWidget(self.toolbar)
        
        layout.addWidget(self.plot_container)
        
        # Connect Matplotlib events
        self.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        
        # Statistics Panel
        self.stats_group = QGroupBox("Statistics (between cursors)")
        stats_layout = QGridLayout()
        
        self.stats_labels = {}
        row, col = 0, 0
        stat_names = ["Min", "Max", "Mean", "Std Dev", "RMS", "Peak-to-Peak"]
        for name in stat_names:
            stats_layout.addWidget(QLabel(f"{name}:"), row, col)
            label = QLabel("---")
            label.setStyleSheet("font-weight: bold; color: #2C3E50;")
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            stats_layout.addWidget(label, row, col + 1)
            self.stats_labels[name] = label
            col += 2
            if col >= 6:
                col = 0
                row += 1
                
        self.stats_group.setLayout(stats_layout)
        layout.addWidget(self.stats_group)
        
    def validate_range_ui(self):
        """
        Provide immediate visual feedback for range inputs.
        """
        error_style = "font-size: 10pt; font-weight: bold; background-color: #fab1a0; border: 2px solid #e17055;"
        normal_style = "font-size: 10pt; font-weight: bold; background-color: white; border: 1px solid #DCDDE1;"
        
        # Validate Start
        try:
            txt_s = self.start_input.text().strip().replace(',', '.').replace('%', '')
            if not txt_s:
                self.start_input.setStyleSheet(normal_style)
            else:
                 val_s = float(txt_s)
                 if 0 <= val_s < 100:
                     self.start_input.setStyleSheet(normal_style)
                 else:
                     self.start_input.setStyleSheet(error_style)
        except ValueError:
            self.start_input.setStyleSheet(error_style)

        # Validate End
        try:
            txt_e = self.end_input.text().strip().replace(',', '.').replace('%', '')
            if not txt_e:
                self.end_input.setStyleSheet(normal_style)
            else:
                val_e = float(txt_e)
                if 0 < val_e <= 100:
                    self.end_input.setStyleSheet(normal_style)
                else:
                    self.end_input.setStyleSheet(error_style)
        except ValueError:
            self.end_input.setStyleSheet(error_style)

    def set_data(self, data: np.ndarray, columns: list, dataset_name: str = "", x_axis_type: str = 'linear', plot_style: str = 'line'):
        """
        Set data for plotting.
        """
        self.data = data
        self.columns = columns
        self.dataset_name = dataset_name
        self.x_axis_type = x_axis_type
        self.plot_style = plot_style
        
        # Update combo boxes
        self.x_axis_combo.blockSignals(True)
        self.y_axis_combo.blockSignals(True)
        try:
            prev_x = self.x_axis_combo.currentText()
            prev_y = self.y_axis_combo.currentText()
            
            self.x_axis_combo.clear()
            self.y_axis_combo.clear()
            
            # Add 'Index' as default X option
            self.x_axis_combo.addItem("Index")
            
            # Add external X if available
            if self.external_x_data is not None:
                self.x_axis_combo.addItem(f"External: {self.external_x_name}")
            
            self.x_axis_combo.addItems(columns)
            self.y_axis_combo.addItems(columns)
            
            # Restore selections if possible
            if prev_x and self.x_axis_combo.findText(prev_x) >= 0:
                self.x_axis_combo.setCurrentText(prev_x)
            else:
                # Default heuristic
                if len(columns) >= 2:
                    self.x_axis_combo.setCurrentIndex(1) # Likely first data column
                else:
                    self.x_axis_combo.setCurrentIndex(0) # Index
                    
            if prev_y and self.y_axis_combo.findText(prev_y) >= 0:
                self.y_axis_combo.setCurrentText(prev_y)
            else:
                self.y_axis_combo.setCurrentIndex(0)
                    
        finally:
            self.x_axis_combo.blockSignals(False)
            self.y_axis_combo.blockSignals(False)
        
        # Initial cursor setup if needed
        if self.cursor1_pos is None or self.cursor2_pos is None:
            self.cursor1_pos = 0.0
            self.cursor2_pos = 1.0
            
        self.export_btn.setEnabled(len(self.columns) > 0)
        
        # Auto-calculate display limits
        if self.data is not None:
            self.auto_calc_limit(len(self.data))
            
        self.update_plot()

    def set_external_x(self, data: np.ndarray, name: str):
        """
        Set an external dataset to be used as X-axis.
        """
        self.external_x_data = data
        self.external_x_name = name
        
        # Update combo box
        self.x_axis_combo.blockSignals(True)
        try:
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
        """
        self.active_cursor_mode = mode
        self.btn_p1.setChecked(mode == 'p1')
        self.btn_p2.setChecked(mode == 'p2')
        self.btn_auto.setChecked(mode == 'auto')
        self.btn_off.setChecked(mode == 'off')
        
        self.update_cursor_visibility()
        self.update_statistics_only()
        
        # Emit signal
        self.cursorsMoved.emit(self.cursor1_pos if self.cursor1_pos is not None else 0.0, 
                               self.cursor2_pos if self.cursor2_pos is not None else 0.0)

    def update_cursor_visibility(self):
        """Update Matplotlib cursor visibility based on mode."""
        visible = (self.active_cursor_mode != 'off')
        self.line_p1.set_visible(visible)
        self.line_p2.set_visible(visible)
        self.region_fill.set_visible(visible)
        
        if visible:
            self.sync_cursor_visuals()
            
        self.canvas.draw_idle()

    def set_axis_selectors_visible(self, visible: bool):
        """Show or hide the default X/Y axis selectors and labels."""
        self.x_axis_label.setVisible(visible)
        self.x_axis_combo.setVisible(visible)
        self.y_axis_label.setVisible(visible)
        self.y_axis_combo.setVisible(visible)

    def set_stats_visible(self, visible: bool):
        """Show or hide the statistics panel."""
        self.stats_group.setVisible(visible)

    def get_column_data(self, column_name: str) -> np.ndarray:
        """Extract data for a specific column name."""
        if column_name == 'Index':
            if self.data is not None:
                return np.arange(len(self.data))
            return np.array([0])
            
        if column_name.startswith("External: "):
            return self.external_x_data
            
        try:
            val = None
            if len(self.data.shape) == 1:
                if column_name == 'Value' or column_name == self.columns[0]:
                    val = self.data
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
        """Auto-calculate start/end % to keep points within a safe limit."""
        target_points = 50000
        if total_points > target_points:
            pct = (target_points / total_points) * 100.0
            # Ensure at least a small percentage is shown but capped at 100
            pct = max(0.01, min(100.0, pct))
            self.start_input.setText("0")
            self.end_input.setText(f"{pct:.2f}")
        else:
            # Set Full Range by default if within limit
            self.start_input.setText("0")
            self.end_input.setText("100")

    def update_plot(self):
        """Redraw the plot with current axis and data."""
        x_col = self.x_axis_combo.currentText()
        y_col = self.y_axis_combo.currentText()
        
        if not x_col or not y_col:
            return
            
        x_data = self.get_column_data(x_col)
        y_data = self.get_column_data(y_col)
        
        if x_data is None or y_data is None or len(x_data) == 0:
            return
            
        self.current_x_series = x_data
        self.current_y_series = y_data
        
        # Initialize cursors if out of bounds
        try:
            x_min_data = np.nanmin(x_data)
            x_max_data = np.nanmax(x_data)
            if np.isnan(x_min_data) or np.isnan(x_max_data) or x_min_data == x_max_data:
                self.cursor1_pos = 0.0
                self.cursor2_pos = 1.0
            else:
                if self.cursor1_pos is None:
                    self.cursor1_pos = float(x_min_data + (x_max_data - x_min_data) * 0.1)
                if self.cursor2_pos is None:
                    self.cursor2_pos = float(x_min_data + (x_max_data - x_min_data) * 0.9)
                
                # Check bounds
                margin = (x_max_data - x_min_data) * 2
                if self.cursor1_pos < x_min_data - margin or self.cursor1_pos > x_max_data + margin:
                    self.cursor1_pos = float(x_min_data + (x_max_data - x_min_data) * 0.1)
                if self.cursor2_pos < x_min_data - margin or self.cursor2_pos > x_max_data + margin:
                    self.cursor2_pos = float(x_min_data + (x_max_data - x_min_data) * 0.9)
        except:
            self.cursor1_pos = 0.0
            self.cursor2_pos = 1.0

        # Range slicing (Start and End)
        try:
            txt_s = self.start_input.text().strip().replace(',', '.').replace('%', '')
            start_pct = float(txt_s) if txt_s else 0.0
        except ValueError:
            start_pct = 0.0

        try:
            txt_e = self.end_input.text().strip().replace(',', '.').replace('%', '')
            end_pct = float(txt_e) if txt_e else 100.0
        except ValueError:
            end_pct = 100.0
        
        start_pct = max(0.0, min(99.9, start_pct))
        end_pct = max(start_pct + 0.01, min(100.0, end_pct))
        
        total_len = len(x_data)
        idx_start = int(max(0, min(total_len - 1, total_len * (start_pct / 100.0))))
        idx_end = int(max(1, min(total_len, total_len * (end_pct / 100.0))))
        
        # If using logarithmic scale and starting at index 0, skip to index 1 to avoid log(0)
        # This is common for FFT where index 0 is the DC component at 0 Hz
        if self.x_axis_type == 'log' and idx_start == 0 and total_len > 1:
            # Check if x_data[0] is zero or very close to zero
            if x_data[0] <= 1e-10:
                idx_start = 1
        
        if idx_start >= idx_end:
            idx_start = max(0, idx_end - 1)
        
        x_plot = x_data[idx_start:idx_end]
        y_plot = y_data[idx_start:idx_end]

        # Downsampling logic if requested range still has too many points
        target_max_points = 55000 # Slightly more than 50k to allow some margin
        current_points = len(x_plot)
        downsampled = False
        if current_points > target_max_points:
            stride = current_points // 50000
            if stride > 1:
                x_plot = x_plot[::stride]
                y_plot = y_plot[::stride]
                downsampled = True

        self.rangeChanged.emit()
        
        title = self.dataset_name or f"{y_col} vs {x_col}"
        if start_pct > 0 or end_pct < 100:
            title += f" (Range: {start_pct:.2f}% - {end_pct:.2f}%)"
        
        if downsampled:
            title += f" [Downsampled 1:{stride}]"
            
        # Clear main artists but keep our cursors
        self.ax.clear()
        
        # Redraw cursors (hidden or visible) - Thinner lines
        self.line_p1 = self.ax.axvline(self.cursor1_pos, color=self.colors['p1'], linestyle='--', linewidth=1.0, zorder=10)
        self.line_p2 = self.ax.axvline(self.cursor2_pos, color=self.colors['p2'], linestyle='--', linewidth=1.0, zorder=10)
        c_min, c_max = sorted([self.cursor1_pos, self.cursor2_pos])
        self.region_fill = self.ax.axvspan(c_min, c_max, color=self.colors['fill'], alpha=0.15, zorder=5)
        
        self.update_cursor_visibility()

        # Plot data
        color = self.colors['main']
        if self.plot_style == 'stem':
            # Stem plot with markers
            markerline, stemlines, baseline = self.ax.stem(x_plot, y_plot, linefmt=color, markerfmt='o', basefmt=' ')
            plt.setp(markerline, 'markersize', 4, 'color', color)
            plt.setp(stemlines, 'linewidth', 1, 'color', color)
        else:
            # Line plot with markers
            if len(x_plot) < 1000:
                self.ax.plot(x_plot, y_plot, color=color, linewidth=1.5, marker='o', markersize=6)
            else:
                self.ax.plot(x_plot, y_plot, color=color, linewidth=1.0, marker='o', markersize=5)

        self.ax.set_title(title, fontsize=12, color=self.colors['text'], fontweight='bold')
        self.ax.set_xlabel(x_col, fontsize=10, color=self.colors['text'])
        self.ax.set_ylabel(y_col, fontsize=10, color=self.colors['text'])
        self.ax.grid(True, color=self.colors['grid'], linestyle='-', linewidth=0.5)
        self.ax.set_facecolor(self.colors['bg'])
        
        # Apply log scale BEFORE setting limits
        if self.x_axis_type == 'log':
            self.ax.set_xscale('log')
            self.ax.xaxis.set_major_formatter(EngFormatter(unit='', sep=''))
            # For log scale, we need to ensure x values are positive
            # Filter out any zero or negative values for FFT (skip DC component)
            if len(x_plot) > 0:
                positive_mask = x_plot > 0
                if np.any(positive_mask):
                    x_min = np.min(x_plot[positive_mask])
                    x_max = np.max(x_plot[positive_mask])
                    if x_max > x_min and x_min > 0:
                        # Set limits with small margin for better visualization
                        self.ax.set_xlim(x_min * 0.9, x_max * 1.1)
                else:
                    # Fallback if no positive values
                    self.ax.set_xscale('linear')
        else:
            # Linear scale - set limits tightly to data range
            if len(x_plot) > 0:
                x_min, x_max = x_plot[0], x_plot[-1]
                # Add small margin for better visualization
                margin = (x_max - x_min) * 0.02 if x_max > x_min else 0.1
                self.ax.set_xlim(x_min - margin, x_max + margin)
        
        # Auto-scale Y-axis to fit the data with margins
        if len(y_plot) > 0:
            y_finite = y_plot[np.isfinite(y_plot)]
            if len(y_finite) > 0:
                y_min = np.min(y_finite)
                y_max = np.max(y_finite)
                
                # Add 10% margin on each side for better visualization
                if y_max > y_min:
                    y_range = y_max - y_min
                    margin = y_range * 0.1
                    self.ax.set_ylim(y_min - margin, y_max + margin)
                elif y_max == y_min and y_max != 0:
                    # If all values are the same, center around that value
                    self.ax.set_ylim(y_max * 0.9, y_max * 1.1)
                else:
                    # Fallback for zero values
                    self.ax.set_ylim(-0.1, 0.1)
            
        self.sync_cursor_visuals()
        self.canvas.draw()
        self.update_statistics_only()

    def sync_cursor_visuals(self):
        """Update the visual positions of cursor artists on the canvas."""
        if self.cursor1_pos is not None:
            self.line_p1.set_xdata([self.cursor1_pos, self.cursor1_pos])
        if self.cursor2_pos is not None:
            self.line_p2.set_xdata([self.cursor2_pos, self.cursor2_pos])
        if self.cursor1_pos is not None and self.cursor2_pos is not None:
            c_min, c_max = sorted([self.cursor1_pos, self.cursor2_pos])
            
            # Robust update for both Rectangle (modern/specific Matplotlib) and Polygon (standard)
            # axvspan usually creates a Polygon, but can return Rectangle in some versions
            if hasattr(self.region_fill, 'set_width'):
                 # It's a Rectangle
                 self.region_fill.set_x(c_min)
                 self.region_fill.set_width(c_max - c_min)
            else:
                 # It's a Polygon
                self.region_fill.set_xy([
                    [c_min, 0], [c_min, 1],
                    [c_max, 1], [c_max, 0],
                    [c_min, 0]
                ])

    def on_click(self, event):
        """Handle mouse button press for cursor interaction."""
        if event.inaxes != self.ax:
            return
        
        if self.active_cursor_mode == 'off':
            return
            
        # Check if we clicked near a cursor
        # Use display coordinates for better picking
        try:
            # Convert cursor positions to display coordinates
            p1_disp = self.ax.transData.transform((self.cursor1_pos, 0))[0]
            p2_disp = self.ax.transData.transform((self.cursor2_pos, 0))[0]
            click_disp = event.x
            
            threshold = self.cursor_pick_threshold # pixels
            
            dist1 = abs(click_disp - p1_disp)
            dist2 = abs(click_disp - p2_disp)
            
            if dist1 < threshold and dist1 < dist2:
                self.dragging_cursor = 0
            elif dist2 < threshold:
                self.dragging_cursor = 1
            else:
                # If not dragging, maybe move a cursor to click position if in p1/p2 mode
                if self.active_cursor_mode == 'p1':
                    self.cursor1_pos = event.xdata
                    self.dragging_cursor = 0
                elif self.active_cursor_mode == 'p2':
                    self.cursor2_pos = event.xdata
                    self.dragging_cursor = 1
                elif self.active_cursor_mode == 'auto':
                    # Move the nearest one
                    if dist1 < dist2:
                        self.cursor1_pos = event.xdata
                        self.dragging_cursor = 0
                    else:
                        self.cursor2_pos = event.xdata
                        self.dragging_cursor = 1
            
            if self.dragging_cursor is not None:
                self.sync_cursor_visuals()
                self.canvas.draw_idle()
                self.update_statistics_only()
                self.cursorsMoved.emit(self.cursor1_pos, self.cursor2_pos)
        except:
            pass

    def on_mouse_move(self, event):
        """Handle mouse movement for dragging cursors."""
        if self.active_cursor_mode == 'off':
            return
            
        if self.dragging_cursor is not None and event.inaxes == self.ax:
            if self.dragging_cursor == 0:
                self.cursor1_pos = event.xdata
            else:
                self.cursor2_pos = event.xdata
                
            self.sync_cursor_visuals()
            self.canvas.draw_idle()
            self.update_statistics_only()
            self.cursorsMoved.emit(self.cursor1_pos, self.cursor2_pos)
            
        # Update cursor icon
        if event.inaxes == self.ax:
            try:
                p1_disp = self.ax.transData.transform((self.cursor1_pos, 0))[0]
                p2_disp = self.ax.transData.transform((self.cursor2_pos, 0))[0]
                if abs(event.x - p1_disp) < 15 or abs(event.x - p2_disp) < 15:
                    self.setCursor(Qt.SizeHorCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
            except:
                self.setCursor(Qt.ArrowCursor)

    def on_release(self, event):
        """Handle mouse button release."""
        self.dragging_cursor = None

    def update_statistics_only(self):
        """Update only the statistics labels."""
        if self.current_x_series is not None and self.current_y_series is not None:
            self.update_statistics(self.current_x_series, self.current_y_series)
    
    def update_statistics(self, x_data: np.ndarray, y_data: np.ndarray):
        """Calculate and update statistics between cursors."""
        if self.active_cursor_mode == 'off':
            y_selected = y_data
        else:
            if self.cursor1_pos is None or self.cursor2_pos is None:
                return
            try:
                min_x = min(self.cursor1_pos, self.cursor2_pos)
                max_x = max(self.cursor1_pos, self.cursor2_pos)
                mask = (x_data >= min_x) & (x_data <= max_x)
                y_selected = y_data[mask]
            except:
                return
        
        try:
            if len(y_selected) == 0:
                for label in self.stats_labels.values():
                    label.setText("---")
                return
                
            stats = math_utils.calculate_statistics(y_selected)
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
            self, "Export to CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return
        
        try:
            if self.active_cursor_mode != 'off' and self.cursor1_pos is not None and self.cursor2_pos is not None:
                x_col = self.x_axis_combo.currentText()
                x_data = self.get_column_data(x_col)
                min_x = min(self.cursor1_pos, self.cursor2_pos)
                max_x = max(self.cursor1_pos, self.cursor2_pos)
                mask = (x_data >= min_x) & (x_data <= max_x)
                export_data = self.data[mask]
            else:
                export_data = self.data
            
            if export_data.dtype.names:
                df = pd.DataFrame(export_data)
            else:
                if len(export_data.shape) == 1:
                    df = pd.DataFrame(export_data, columns=['Value'])
                else:
                    df = pd.DataFrame(export_data, columns=self.columns)
            
            df.to_csv(filename, index=False)
            QMessageBox.information(self, "Export Success", f"Successfully exported {len(df)} rows to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export CSV:\n{str(e)}")
    
    def clear_plot(self, message: str = ""):
        """Clear the current plot."""
        self.data = None
        self.columns = []
        self.cursor1_pos = None
        self.cursor2_pos = None
        self.x_axis_combo.blockSignals(True)
        self.x_axis_combo.clear()
        self.y_axis_combo.clear()
        self.x_axis_combo.blockSignals(False)
        
        self.ax.clear()
        if message:
            self.ax.text(0.5, 0.5, message, transform=self.ax.transAxes, ha='center', va='center', color='#666')
        self.canvas.draw()
        
        for label in self.stats_labels.values():
            label.setText("---")
        self.export_btn.setEnabled(False)

    def move_cursors_js(self):
        """No longer used, maintained for interface compatibility if needed."""
        self.sync_cursor_visuals()
        self.canvas.draw_idle()
        self.update_statistics_only()
