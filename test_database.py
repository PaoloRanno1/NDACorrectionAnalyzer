"""
Test Database Manager
Manages the collection of test NDAs for consistent testing
"""

import os
import glob
from typing import List, Dict, Tuple, Optional

def get_available_test_ndas() -> Dict[str, Dict[str, str]]:
    """
    Get all available test NDAs from the test_data directory
    
    Returns:
        Dict mapping NDA names to their file paths
        Format: {
            "Project Octagon": {
                "clean": "test_data/project_octagon_clean.md",
                "corrected": "test_data/project_octagon_corrected.md"
            }
        }
    """
    test_data_dir = "test_data"
    test_ndas = {}
    
    if not os.path.exists(test_data_dir):
        return test_ndas
    
    # Find all clean files
    clean_files = glob.glob(os.path.join(test_data_dir, "*_clean.md"))
    
    for clean_file in clean_files:
        # Extract the project name
        filename = os.path.basename(clean_file)
        project_name = filename.replace("_clean.md", "")
        
        # Look for corresponding corrected file
        corrected_file = os.path.join(test_data_dir, f"{project_name}_corrected.md")
        
        if os.path.exists(corrected_file):
            # Convert project name to display format
            display_name = project_name.replace("_", " ").title()
            
            test_ndas[display_name] = {
                "clean": clean_file,
                "corrected": corrected_file
            }
    
    return test_ndas

def get_test_nda_list() -> List[str]:
    """
    Get a list of available test NDA names for dropdown selection
    
    Returns:
        List of test NDA display names
    """
    test_ndas = get_available_test_ndas()
    return list(test_ndas.keys())

def get_test_nda_paths(nda_name: str) -> Optional[Tuple[str, str]]:
    """
    Get the file paths for a specific test NDA
    
    Args:
        nda_name: Display name of the test NDA
        
    Returns:
        Tuple of (clean_path, corrected_path) or None if not found
    """
    test_ndas = get_available_test_ndas()
    
    if nda_name in test_ndas:
        return (test_ndas[nda_name]["clean"], test_ndas[nda_name]["corrected"])
    
    return None

def create_file_objects_from_paths(clean_path: str, corrected_path: str):
    """
    Create file-like objects from file paths for compatibility with existing upload system
    
    Args:
        clean_path: Path to clean NDA file
        corrected_path: Path to corrected NDA file
        
    Returns:
        Tuple of file-like objects (clean_file, corrected_file)
    """
    class FileWrapper:
        def __init__(self, file_path: str):
            self.name = os.path.basename(file_path)
            self.file_path = file_path
            
        def getvalue(self):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return f.read().encode('utf-8')
                
        def read(self):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return f.read()
    
    return FileWrapper(clean_path), FileWrapper(corrected_path)