"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

Run H5Inspector application.

A PyQt5 application for viewing and editing HDF5 files.
"""

from H5Inspector import H5Inspector
from PyQt5.QtWidgets import QApplication
import sys

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set application info
    app.setApplicationName("H5Inspector")
    app.setOrganizationName("HDF5 Tools")
    
    # Create and show main window
    window = H5Inspector()
    window.show()
    
    sys.exit(app.exec_())