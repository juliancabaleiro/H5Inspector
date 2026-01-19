"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

View Tab - HDF5 Navigation and Visualization
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,QSplitter, QLabel, QHeaderView, QMenu, QAction,QDialog, QFormLayout, QDialogButtonBox
from PyQt5.QtCore import Qt
import h5_utils
from plot_widget import PlotWidget
import logging

class ViewTab(QWidget):
    """
    View tab for navigating and visualizing HDF5 files.

    Maintains a tree view of the HDF5 structure, a table view for dataset contents,
    and a plot widget for graphical representation.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the ViewTab.
        """
        super().__init__(parent)
        self.current_file = None
        self.setup_ui()
    
    def setup_ui(self):
        """
        Setup the user interface.

        Creates the splitter layout containing the tree view (left) and
        data/plot area (right).
        """
        layout = QVBoxLayout(self)
        
        # Create horizontal splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Tree view
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("HDF5 Structure")
        self.tree_widget.itemClicked.connect(self.on_tree_item_clicked)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.on_context_menu)
        
        # Configure tree for horizontal scrolling and long names
        self.tree_widget.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree_widget.header().setStretchLastSection(False)
        self.tree_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        main_splitter.addWidget(self.tree_widget)
        
        # Right side: Vertical splitter for data display and plot
        right_splitter = QSplitter(Qt.Vertical)
        
        # Data display area (table)
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        right_splitter.addWidget(self.data_table)
        
        # Plot area
        self.plot_widget = PlotWidget()
        right_splitter.addWidget(self.plot_widget)
        
        # Set initial sizes (50-50 split)
        right_splitter.setSizes([300, 400])
        
        main_splitter.addWidget(right_splitter)
        
        # Set splitter sizes (30-70 split)
        main_splitter.setSizes([300, 700])
        
        layout.addWidget(main_splitter)
    
    def load_file(self, filepath: str):
        """
        Load an HDF5 file and populate the tree.

        Parameters
        ----------
        filepath : str
            The absolute path to the HDF5 file.
        """
        self.current_file = filepath
        self.tree_widget.clear()
        self.data_table.clear()
        self.plot_widget.clear_plot()
        
        try:
            # Load file structure
            structure = h5_utils.load_h5_structure(filepath)
            
            # Populate tree
            root = QTreeWidgetItem(self.tree_widget, ["/ (root)"])
            root.setData(0, Qt.UserRole, {'path': '/', 'type': 'group'})
            
            # Add root attributes if any
            if '_root_attrs' in structure and structure['_root_attrs']:
                root.setData(0, Qt.UserRole + 1, structure['_root_attrs'])
            
            # Recursively add items
            if '_children' in structure:
                self._add_tree_items(root, structure['_children'], '')
            
            self.tree_widget.expandToDepth(0)
            
        except Exception as e:
            logging.error(f"Error loading file: {str(e)}")
    
    def _add_tree_items(self, parent_item: QTreeWidgetItem, structure: dict, parent_path: str):
        """
        Recursively add items to the tree.

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
                
                # Create icon/label based on type
                if item_type == 'group':
                    label = f"📁 {key}"
                elif item_type == 'dataset':
                    shape_str = str(value.get('_shape', ''))
                    label = f"📊 {key} {shape_str}"
                else:
                    label = key
                
                item = QTreeWidgetItem(parent_item, [label])
                item.setData(0, Qt.UserRole, {
                    'path': current_path if not current_path.startswith('/') else current_path,
                    'type': item_type,
                    'info': value
                })
                
                # Store attributes
                if '_attrs' in value:
                    item.setData(0, Qt.UserRole + 1, value['_attrs'])
                
                # Recursively add children for groups
                if item_type == 'group' and '_children' in value:
                    self._add_tree_items(item, value['_children'], current_path)
    
    def on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """
        Handle tree item click.

        Parameters
        ----------
        item : QTreeWidgetItem
            The clicked item.
        column : int
            The clicked column index.
        """
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        item_type = data.get('type')
        item_path = data.get('path')
        
        # Clear previous display
        self.data_table.clear()
        
        if item_type == 'group':
            # Display attributes
            self.display_attributes(item)
        elif item_type == 'dataset':
            # Display dataset data
            self.display_dataset(item_path)
            
    def on_context_menu(self, position):
        """
        Handle custom context menu on tree widget.

        Parameters
        ----------
        position : QPoint
            The position where the context menu was requested.
        """
        item = self.tree_widget.itemAt(position)
        if not item:
            return
            
        data = item.data(0, Qt.UserRole)
        if not data or data.get('type') != 'dataset':
            return
            
        menu = QMenu()
        
        # Action to view attributes
        view_attrs_action = QAction("View Attributes", self)
        view_attrs_action.triggered.connect(lambda: self.show_item_attributes(item))
        menu.addAction(view_attrs_action)
        
        menu.addSeparator()
        
        set_x_action = QAction("Use as X-Axis", self)
        set_x_action.triggered.connect(lambda: self.set_dataset_as_x(data.get('path')))
        menu.addAction(set_x_action)
        
        menu.exec_(self.tree_widget.viewport().mapToGlobal(position))
        
    def show_item_attributes(self, item: QTreeWidgetItem):
        """
        Show attributes of the selected item in a dialog.

        Parameters
        ----------
        item : QTreeWidgetItem
            The item whose attributes to show.
        """
        attrs = item.data(0, Qt.UserRole + 1)
        path = item.data(0, Qt.UserRole).get('path', 'Unknown')
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Attributes: {path}")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        if not attrs:
            layout.addWidget(QLabel("This item has no attributes."))
        else:
            table = QTableWidget(len(attrs), 2)
            table.setHorizontalHeaderLabels(["Attribute", "Value"])
            table.setAlternatingRowColors(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
            for i, (key, value) in enumerate(attrs.items()):
                table.setItem(i, 0, QTableWidgetItem(str(key)))
                table.setItem(i, 1, QTableWidgetItem(str(value)))
            
            layout.addWidget(table)
            
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        
        dialog.exec_()
        
    def set_dataset_as_x(self, dataset_path: str):
        """
        Load a dataset and tell PlotWidget to use it as X-axis.

        Parameters
        ----------
        dataset_path : str
            The path to the dataset to use as X-axis.
        """
        if not self.current_file:
            return
            
        try:
            data, columns = h5_utils.get_dataset_data(self.current_file, dataset_path)
            
            # Simple heuristic: if it's 2D, use first column? Or if 1D just use it.
            if len(data.shape) == 1:
                x_series = data
            elif len(data.shape) == 2:
                x_series = data[:, 0] # Use first column
            else:
                logging.debug(f"Dataset {dataset_path} dimension too high for X-axis")
                return
                
            name = dataset_path.split('/')[-1]
            self.plot_widget.set_external_x(x_series, name)
            
        except Exception as e:
            logging.error(f"Error setting X-axis: {e}")
    
    def display_attributes(self, item: QTreeWidgetItem):
        """
        Display attributes in the table.

        Parameters
        ----------
        item : QTreeWidgetItem
            The item whose attributes to display.
        """
        attrs = item.data(0, Qt.UserRole + 1)
        
        if not attrs:
            self.data_table.setRowCount(1)
            self.data_table.setColumnCount(1)
            self.data_table.setItem(0, 0, QTableWidgetItem("No attributes"))
            return
        
        # Setup table
        self.data_table.setRowCount(len(attrs))
        self.data_table.setColumnCount(2)
        self.data_table.setHorizontalHeaderLabels(['Attribute', 'Value'])
        
        # Populate table
        for i, (key, value) in enumerate(attrs.items()):
            self.data_table.setItem(i, 0, QTableWidgetItem(str(key)))
            self.data_table.setItem(i, 1, QTableWidgetItem(str(value)))
        
        # Resize columns to content
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.data_table.horizontalHeader().setStretchLastSection(True)
    
    def display_dataset(self, dataset_path: str):
        """
        Display dataset data and plot.

        Parameters
        ----------
        dataset_path : str
            The path to the dataset to display.
        """
        if not self.current_file:
            return
        
        try:
            # Load dataset data
            data, columns = h5_utils.get_dataset_data(self.current_file, dataset_path)
            # logging.debug(f"ViewTab - Loaded data from {dataset_path}. Shape: {data.shape if data is not None else 'None'}, Columns: {columns}")
            
            # Display in table (limit rows for performance)
            max_rows = 1000
            display_data = data[:max_rows] if len(data) > max_rows else data
            
            # Handle different data shapes
            if len(data.shape) == 1:
                if data.dtype.names:
                    # 1D Structured array (Compound)
                    cols = list(data.dtype.names)
                    self.data_table.setRowCount(len(display_data))
                    self.data_table.setColumnCount(len(cols))
                    self.data_table.setHorizontalHeaderLabels(cols)
                    
                    for i in range(len(display_data)):
                        for j, col in enumerate(cols):
                            self.data_table.setItem(i, j, QTableWidgetItem(str(display_data[i][col])))
                else:
                    # Simple 1D data
                    self.data_table.setRowCount(len(display_data))
                    self.data_table.setColumnCount(2)
                    self.data_table.setHorizontalHeaderLabels(['Index', 'Value'])
                    
                    for i, value in enumerate(display_data):
                        self.data_table.setItem(i, 0, QTableWidgetItem(str(i)))
                        self.data_table.setItem(i, 1, QTableWidgetItem(str(value)))
            
            elif len(data.shape) == 2:
                # 2D data
                rows, cols = display_data.shape
                self.data_table.setRowCount(rows)
                self.data_table.setColumnCount(cols)
                self.data_table.setHorizontalHeaderLabels(columns)
                
                for i in range(rows):
                    for j in range(cols):
                        if data.dtype.names:
                            value = display_data[i][j]
                        else:
                            value = display_data[i, j]
                        self.data_table.setItem(i, j, QTableWidgetItem(str(value)))
            
            else:
                # Higher dimensional data - show info only
                self.data_table.setRowCount(1)
                self.data_table.setColumnCount(1)
                self.data_table.setHorizontalHeaderLabels(['Info'])
                info = f"Shape: {data.shape}, Dtype: {data.dtype}"
                self.data_table.setItem(0, 0, QTableWidgetItem(info))
            
            # Resize columns
            self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            self.data_table.resizeColumnsToContents()
            
            # Update plot if data is plottable
            is_plottable = h5_utils.is_plottable_dataset(self.current_file, dataset_path)
            # logging.debug(f"display_dataset for {dataset_path}, is_plottable={is_plottable}")
            
            if is_plottable:
                dataset_name = dataset_path.split('/')[-1] if '/' in dataset_path else dataset_path
                self.plot_widget.set_data(data, columns, dataset_name)
            else:
                info = f"Non-plottable dataset (Type: {data.dtype}, Dim: {len(data.shape)})"
                self.plot_widget.clear_plot(info)
        
        except Exception as e:
            self.data_table.setRowCount(1)
            self.data_table.setColumnCount(1)
            self.data_table.setItem(0, 0, QTableWidgetItem(f"Error: {str(e)}"))
            self.plot_widget.clear_plot()
            logging.error(f"Error displaying dataset: {e}")
