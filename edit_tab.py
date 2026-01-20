"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

Edit Tab - HDF5 File Editor
Allows selection and export of HDF5 structure elements
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QTextEdit, QLabel, QFileDialog, QMessageBox, QGroupBox, QSplitter
from PyQt5.QtCore import Qt
import h5_utils
import logging

class EditTab(QWidget):
    """
    Edit tab for selecting and exporting HDF5 elements.

    Provides an interface to select specific groups and datasets from the
    loaded HDF5 file and export them to a new file, optionally adding a comment.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the EditTab.
        """
        super().__init__(parent)
        self.current_file = None
        self.setup_ui()
    
    def setup_ui(self):
        """
        Setup the user interface.

        Constructs the UI including the selection tree, comment area,
        and the export button.
        """
        layout = QVBoxLayout(self)
        
        # Instructions
        info_label = QLabel(
            "Select groups and datasets that you want to export to a new HDF5 file"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 8px; background-color: #e7f3ff; border-radius: 4px;")
        layout.addWidget(info_label)
        
        # Main content splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Tree widget with checkboxes
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("HDF5 Structure (check to select)")
        splitter.addWidget(self.tree_widget)
        
        # Comment section
        comment_group = QGroupBox("File Comment")
        comment_layout = QVBoxLayout()
        
        comment_label = QLabel("Add a comment or description for the new file:")
        comment_layout.addWidget(comment_label)
        
        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("Ex: Filtered data from experiment X...")
        self.comment_text.setMaximumHeight(100)
        comment_layout.addWidget(self.comment_text)
        
        comment_group.setLayout(comment_layout)
        splitter.addWidget(comment_group)
        
        # Set splitter sizes
        splitter.setSizes([500, 150])
        layout.addWidget(splitter)
        
        # Create button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.create_button = QPushButton("Create New HDF5 File")
        self.create_button.setObjectName("successButton")
        self.create_button.setMinimumWidth(200)
        self.create_button.clicked.connect(self.create_new_file)
        self.create_button.setEnabled(False)
        button_layout.addWidget(self.create_button)
        
        layout.addLayout(button_layout)
    
    def load_file(self, filepath: str):
        """
        Load an HDF5 file and populate the tree with checkboxes.

        Parameters
        ----------
        filepath : str
            The absolute path to the HDF5 file.
        """
        self.current_file = filepath
        self.tree_widget.clear()
        self.comment_text.clear()
        
        try:
            # Load file structure
            structure = h5_utils.load_h5_structure(filepath)
            
            # Populate tree with checkboxes
            root = QTreeWidgetItem(self.tree_widget, ["/ (root)"])
            root.setFlags(root.flags() | Qt.ItemIsUserCheckable)
            root.setCheckState(0, Qt.Unchecked)
            root.setData(0, Qt.UserRole, {'path': '/', 'type': 'group'})
            
            # Recursively add items
            if '_children' in structure:
                self._add_tree_items(root, structure['_children'], '')
            
            self.tree_widget.expandToDepth(0)
            self.create_button.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading file: {str(e)}")
            logging.error(f"Error loading file in EditTab: {e}")
    
    def _add_tree_items(self, parent_item: QTreeWidgetItem, structure: dict, parent_path: str):
        """
        Recursively add items to the tree with checkboxes.

        Parameters
        ----------
        parent_item : QTreeWidgetItem
            The parent tree item.
        structure : dict
            The structure dictionary for the current level.
        parent_path : str
            The HDF5 path of the parent item.
        """
        for key, value in structure.items():
            if key.startswith('_'):
                continue
            
            current_path = f"{parent_path}/{key}" if parent_path else key
            
            if isinstance(value, dict) and '_type' in value:
                item_type = value['_type']
                
                # Create label based on type
                if item_type == 'group':
                    label = f"📁 {key}"
                elif item_type == 'dataset':
                    shape_str = str(value.get('_shape', ''))
                    label = f"📊 {key} {shape_str}"
                else:
                    label = key
                
                item = QTreeWidgetItem(parent_item, [label])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Unchecked)
                item.setData(0, Qt.UserRole, {
                    'path': current_path if not current_path.startswith('/') else current_path,
                    'type': item_type
                })
                
                # Recursively add children for groups
                if item_type == 'group' and '_children' in value:
                    self._add_tree_items(item, value['_children'], current_path)
    
    def get_selected_items(self) -> list:
        """
        Get all checked items from the tree, filtering out redundant children.
        
        If a parent is selected, its children are implicitly selected and 
        will be filtered out if they are also explicitly checked (logic depends 
        on copy implementation, but here we gather paths).

        Returns
        -------
        list
            A list of absolute HDF5 paths that are selected.
        """
        selected_paths = []
        
        def traverse_collect(item):
            if item.checkState(0) == Qt.Checked:
                data = item.data(0, Qt.UserRole)
                if data:
                    selected_paths.append(data['path'])
            
            for i in range(item.childCount()):
                traverse_collect(item.child(i))
        
        # Collect all checked
        root = self.tree_widget.topLevelItem(0)
        if root:
            for i in range(root.childCount()):
                traverse_collect(root.child(i))
        
        # Sort by length to easily find parents
        sorted_paths = sorted(selected_paths, key=len)
        filtered = []
        for i, path in enumerate(sorted_paths):
            is_child_of_selected = False
            for prev_path in sorted_paths[:i]:
                if path.startswith(prev_path.rstrip('/') + '/'):
                    is_child_of_selected = True
                    break
            if not is_child_of_selected:
                filtered.append(path)
        
        return filtered
    
    def create_new_file(self):
        """
        Create a new HDF5 file with the selected items.

        Prompts the user for a destination file path and triggers the
        copy process. Handles validation and success/error reporting.
        """
        if not self.current_file:
            return
        
        # Get selected items
        selected_items = self.get_selected_items()
        
        if not selected_items:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select at least one group or dataset to export."
            )
            return
        
        # Get destination file
        dest_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save new HDF5 file",
            "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)"
        )
        
        if not dest_file:
            return
        
        # Add .h5 extension if not present
        if not dest_file.endswith(('.h5', '.hdf5')):
            dest_file += '.h5'
            
        # [SECURITY] Check if destination is the same as the open file
        import os
        if os.path.abspath(dest_file) == os.path.abspath(self.current_file):
            QMessageBox.warning(
                self,
                "File Open",
                "Cannot overwrite the currently open file. Please choose a different name."
            )
            return
        
        # Get comment
        comment = self.comment_text.toPlainText().strip()
        
        # Create the file
        try:
            success = h5_utils.copy_h5_items(
                self.current_file,
                dest_file,
                selected_items,
                comment
            )
            
            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"File created successfully:\n{dest_file}\n\n"
                    f"Exported elements: {len(selected_items)}"
                )
                
                # Optionally clear selections
                self.clear_selections()
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    "Error creating file. Please check permissions and available space."
                )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error creating file:\n{str(e)}"
            )
            logging.error(f"Error creating file: {e}")
    
    def clear_selections(self):
        """
        Clear all checkbox selections in the tree.

        Resets the check state of all items and their children to Qt.Unchecked.
        """
        def clear_item(item):
            item.setCheckState(0, Qt.Unchecked)
            for i in range(item.childCount()):
                clear_item(item.child(i))
        
        root = self.tree_widget.topLevelItem(0)
        if root:
            for i in range(root.childCount()):
                clear_item(root.child(i))
