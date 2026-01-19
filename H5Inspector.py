"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

H5Inspector
General structure
"""
import os
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTabWidget,QFileDialog, QMessageBox, QLabel, QStatusBar
from view_tab import ViewTab
from edit_tab import EditTab
from analysis_tab import AnalysisTab

import logging

# Configure logging to show only errors
logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')

class H5Inspector(QMainWindow):
    """
    Main application window for H5Inspector.

    Manages the main UI components tab for view, Analysis, Edit.
    """

    def __init__(self):
        """
        Initialize the H5Inspector application.
        """
        super().__init__()
        self.current_file = None
        self.setup_ui()
        self.load_stylesheet()
    
    def setup_ui(self):
        """
        Setup the user interface components.
        - Creates the main window layout, file selection area, tab widget,
        and status bar.
        """
        self.setWindowTitle("H5Inspector")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # File path section
        file_layout = QHBoxLayout()
        
        path_label = QLabel("HDF5 File:")
        path_label.setStyleSheet("font-weight: bold;")
        file_layout.addWidget(path_label)
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select an HDF5 file or enter path...")
        self.path_edit.returnPressed.connect(self.load_file)
        file_layout.addWidget(self.path_edit)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_btn)
        
        main_layout.addLayout(file_layout)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.view_tab = ViewTab()
        self.edit_tab = EditTab()
        self.analysis_tab = AnalysisTab()
        
        self.tab_widget.addTab(self.view_tab, "📊 View")
        self.tab_widget.addTab(self.analysis_tab, "📈 Analysis")
        self.tab_widget.addTab(self.edit_tab, "✏️ Edit")
        
        main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Load an HDF5 file to start.")
    
    def load_stylesheet(self):
        """
        Load and apply the custom stylesheet from 'styles.qss'.

        - Attempts to find and load the CSS file located in the same directory
        as the script. 
        - Logs a warning or error if the file cannot be loaded.
        """
        try:
            # Get the directory of the current script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            qss_path = os.path.join(script_dir, 'styles.qss')
            
            if os.path.exists(qss_path):
                with open(qss_path, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                    self.setStyleSheet(stylesheet)
            else:
                logging.warning(f"Stylesheet not found at {qss_path}")
        except Exception as e:
            logging.error(f"Error loading stylesheet: {str(e)}")
    
    def browse_file(self):
        """
        Open a file dialog to select an HDF5 file.

        Updates the path edit field and triggers file loading if a file
        is selected.
        """
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select HDF5 file",
            "",
            "HDF5 Files (*.h5 *.hdf5 *.he5);;All Files (*)"
        )
        
        if filepath:
            self.path_edit.setText(filepath)
            self.load_file()
    
    def load_file(self):
        """
        Load the selected HDF5 file into all application tabs.

        - Validates the file path and propagates the file path to View,
        Edit, and Analysis tabs. 
        - Handles errors during loading.
        """
        filepath = self.path_edit.text().strip()
        
        if not filepath:
            QMessageBox.warning(
                self,
                "File not selected",
                "Please select or enter the path to an HDF5 file."
            )
            return
        
        if not os.path.exists(filepath):
            QMessageBox.critical(
                self,
                "Error",
                f"The file does not exist:\n{filepath}"
            )
            return
        
        try:
            self.current_file = filepath
            
            # Load file in all tabs
            self.view_tab.load_file(filepath)
            self.edit_tab.load_file(filepath)
            self.analysis_tab.load_file(filepath)
            
            # Update status bar
            filename = os.path.basename(filepath)
            self.status_bar.showMessage(f"File loaded: {filename}")
            
            # Update window title
            self.setWindowTitle(f"H5Inspector - {filename}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error loading file:\n{str(e)}"
            )
            self.status_bar.showMessage("Error uploading file.")
            logging.error(f"Error loading file: {e}")

if __name__ == '__main__':
    pass
