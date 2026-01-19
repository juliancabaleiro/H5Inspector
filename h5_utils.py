"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

HDF5 Utilities Module
Provides functions to manipulateHDF5 files
"""

import h5py
import numpy as np
import re
from typing import Dict, List, Any, Tuple, Optional
import logging


def natural_sort_key(s):
    """
    Key for natural sorting (e.g., wave_1, wave_2, wave_10).
    
    Parameters
    ----------
    s : str
        The string to key.
        
    Returns
    -------
    list
        A list of string and integer parts for sorting.
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def load_h5_structure(filepath: str) -> Dict[str, Any]:
    """
    Load the structure of an HDF5 file without reading data values.
    Returns a nested dictionary representing groups, datasets, and attributes.
    
    Parameters
    ----------
    filepath : str
        Path to the HDF5 file.
        
    Returns
    -------
    dict
        Dictionary with structure information (groups, datasets, attributes).
    
    Raises
    ------
    Exception
        If the file cannot be opened or read.
    """
    
    def build_item_dict(obj):
        """Helper to build dict for a group or dataset"""
        if isinstance(obj, h5py.Group):
            return {
                '_type': 'group',
                '_attrs': dict(obj.attrs),
                '_children': {}
            }
        elif isinstance(obj, h5py.Dataset):
            return {
                '_type': 'dataset',
                '_attrs': dict(obj.attrs),
                '_shape': obj.shape,
                '_dtype': str(obj.dtype)
            }
        return {}
    
    def visit_item(name, obj):
        """Visit each item and add to structure"""
        parts = [p for p in name.split('/') if p]  # Remove empty strings
        
        # Navigate to the correct position in the nested dict
        current = structure['_children']
        for part in parts[:-1]:
            if part not in current:
                current[part] = {
                    '_type': 'group',
                    '_attrs': {},
                    '_children': {}
                }
            # Navigate into the _children of this group
            if '_children' not in current[part]:
                current[part]['_children'] = {}
            current = current[part]['_children']
        
        # Add the current item
        item_name = parts[-1]
        current[item_name] = build_item_dict(obj)
    
    try:
        with h5py.File(filepath, 'r') as f:
            # Initialize structure
            structure = {
                '_root_attrs': dict(f.attrs),
                '_children': {}
            }
            
            # Visit all items
            f.visititems(visit_item)
            
            # Sort children recursively (Natural Sort)
            def sort_structure(node):
                if '_children' in node:
                    sorted_children = {}
                    for key in sorted(node['_children'].keys(), key=natural_sort_key):
                        child = node['_children'][key]
                        sorted_children[key] = child
                        sort_structure(child)
                    node['_children'] = sorted_children
            
            sort_structure(structure)
            
        return structure
    except Exception as e:
        logging.error(f"Error loading HDF5 file: {str(e)}")
        raise Exception(f"Error loading HDF5 file: {str(e)}")


def get_attributes(filepath: str, path: str) -> Dict[str, Any]:
    """
    Get attributes for a specific group or dataset.
    
    Parameters
    ----------
    filepath : str
        Path to the HDF5 file.
    path : str
        Path within the HDF5 file (e.g., '/group1/dataset1').
        
    Returns
    -------
    dict
        Dictionary of attributes.
    """
    try:
        with h5py.File(filepath, 'r') as f:
            if path == '/':
                return dict(f.attrs)
            obj = f[path]
            return dict(obj.attrs)
    except Exception as e:
        logging.error(f"Error getting attributes: {e}")
        return {}


def get_dataset_data(filepath: str, dataset_path: str) -> Tuple[np.ndarray, List[str]]:
    """
    Load data from a specific dataset.
    
    Parameters
    ----------
    filepath : str
        Path to the HDF5 file.
    dataset_path : str
        Path to the dataset within the file.
        
    Returns
    -------
    tuple
        Tuple containing:
        - data array (numpy.ndarray)
        - column names (list of str)
    
    Raises
    ------
    Exception
        If reading fails.
    """
    try:
        with h5py.File(filepath, 'r') as f:
            dataset = f[dataset_path]
            data = dataset[:]
            
            # Helper to decode bytes to string
            def decode_if_bytes(x):
                if isinstance(x, bytes):
                    return x.decode('utf-8', errors='replace')
                return str(x)
            
            # Try to get column names from attributes or generate them
            columns = []
            if 'columns' in dataset.attrs:
                cols_attr = dataset.attrs['columns']
                columns = [decode_if_bytes(c) for c in (cols_attr if hasattr(cols_attr, '__iter__') else [cols_attr])]
            elif 'fields' in dataset.attrs:
                cols_attr = dataset.attrs['fields']
                columns = [decode_if_bytes(c) for c in (cols_attr if hasattr(cols_attr, '__iter__') else [cols_attr])]
            elif dataset.dtype.names:
                columns = list(dataset.dtype.names)
            else:
                # Generate column names based on shape
                if len(data.shape) == 1:
                    columns = ['Value']
                elif len(data.shape) == 2:
                    columns = [f'Column_{i}' for i in range(data.shape[1])]
                else:
                    columns = [f'Dim_{i}' for i in range(data.shape[-1])]
            
            return data, columns
    except Exception as e:
        logging.error(f"Error reading dataset: {str(e)}")
        raise Exception(f"Error reading dataset: {str(e)}")


def get_dataset_info(filepath: str, dataset_path: str) -> Dict[str, Any]:
    """
    Get information about a dataset without loading all data.
    
    Parameters
    ----------
    filepath : str
        Path to the HDF5 file.
    dataset_path : str
        Path to the dataset.
        
    Returns
    -------
    dict
        Dictionary with dataset information (shape, dtype, size, ndim, attrs).
    """
    try:
        with h5py.File(filepath, 'r') as f:
            dataset = f[dataset_path]
            return {
                'shape': dataset.shape,
                'dtype': str(dataset.dtype),
                'size': dataset.size,
                'ndim': dataset.ndim,
                'attrs': dict(dataset.attrs)
            }
    except Exception as e:
        logging.error(f"Error getting dataset info: {e}")
        return {}


def copy_h5_items(source_filepath: str, dest_filepath: str, 
                  items_to_copy: List[str], file_comment: str = "") -> bool:
    """
    Copy selected groups/datasets/attributes to a new HDF5 file.
    
    Parameters
    ----------
    source_filepath : str
        Path to source HDF5 file.
    dest_filepath : str
        Path to destination HDF5 file.
    items_to_copy : list
        List of absolute paths within the source file to copy.
    file_comment : str, optional
        Comment to add to the new file's attributes.
        
    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    import os
    
    # Check if source and destination are the same
    if os.path.abspath(source_filepath) == os.path.abspath(dest_filepath):
        logging.error(f"Error: Source and destination are the same file: {source_filepath}")
        return False

    try:
        # Sort items by path length to process parents before children if possible
        # although Group.copy is recursive, so we should filter redundant children.
        sorted_items = sorted(items_to_copy, key=len)
        
        # Filter redundant items (e.g. if /A is copied, don't copy /A/B separately)
        filtered_items = []
        for i, path in enumerate(sorted_items):
            is_redundant = False
            for parent in sorted_items[:i]:
                # If path starts with parent + '/', it's inside an already copied group
                if path.startswith(parent.rstrip('/') + '/'):
                    is_redundant = True
                    break
            if not is_redundant:
                filtered_items.append(path)

        with h5py.File(source_filepath, 'r') as src:
            with h5py.File(dest_filepath, 'w') as dst:
                # Add file comment as root attribute
                if file_comment:
                    dst.attrs['comment'] = file_comment
                    dst.attrs['description'] = file_comment
                
                # Copy filtered items
                for item_path in filtered_items:
                    if item_path in src:
                        # Ensure path starts with /
                        full_path = item_path if item_path.startswith('/') else '/' + item_path
                        
                        # Create parent hierarchy if needed
                        parts = full_path.split('/')
                        if len(parts) > 2:
                            parent_path = '/'.join(parts[:-1])
                            dst.require_group(parent_path)
                        
                        # Copy the item
                        # name=full_path ensures it ends up in the correct location
                        src.copy(item_path, dst, name=full_path)
                
        return True
    except Exception as e:
        logging.error(f"Error copying HDF5 items: {str(e)}")
        # If we failed, try to remove the potentially corrupted partial file
        try:
            if os.path.exists(dest_filepath):
                os.remove(dest_filepath)
        except:
            pass
        return False


def flatten_structure(structure: Dict, prefix: str = "") -> List[Tuple[str, str, Dict]]:
    """
    Flatten the nested structure into a list for tree display.
    
    Parameters
    ----------
    structure : dict
        Nested structure dictionary from load_h5_structure.
    prefix : str, optional
        Current path prefix, by default "".
        
    Returns
    -------
    list
        List of tuples: (path, type, attributes).
    """
    items = []
    
    for key, value in structure.items():
        if key.startswith('_'):
            continue
            
        current_path = f"{prefix}/{key}" if prefix else key
        
        if isinstance(value, dict):
            if '_type' in value:
                items.append((current_path, value['_type'], value.get('_attrs', {})))
                if '_children' in value:
                    items.extend(flatten_structure(value['_children'], current_path))
            else:
                items.extend(flatten_structure(value, current_path))
    
    return items


def is_plottable_dataset(filepath: str, dataset_path: str) -> bool:
    """
    Check if a dataset can be plotted (1D or 2D numeric data).
    
    Parameters
    ----------
    filepath : str
        Path to the HDF5 file.
    dataset_path : str
        Path to the dataset.
        
    Returns
    -------
    bool
        True if dataset is plottable, False otherwise.
    """
    try:
        info = get_dataset_info(filepath, dataset_path)
        if not info:
            return False
            
        ndim = info['ndim']
        # We can plot almost anything that has 1 or 2 dimensions
        if ndim not in [1, 2]:
            return False
            
        # If it's a structured array, it's likely plottable (contains numeric fields)
        if 'names' in str(info['dtype']):
            return True
            
        # Check if numeric type for simple arrays
        dtype_str = info['dtype'].lower()
        numeric_indicators = ['int', 'float', 'complex', '<i', '>i', '<f', '>f', 'uint']
        is_numeric = any(t in dtype_str for t in numeric_indicators)
        
        return is_numeric
    except:
        return False
