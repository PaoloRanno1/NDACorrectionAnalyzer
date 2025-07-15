"""
Results Manager Module
Handles saving and loading of NDA testing results
"""

import os
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
import plotly.io as pio

# Results storage directory
RESULTS_DIR = "saved_results"

def ensure_results_directory():
    """Create results directory if it doesn't exist"""
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

def generate_result_id(nda_name: str) -> str:
    """Generate a unique result ID based on NDA name and timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = nda_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return f"{safe_name}_{timestamp}"

def save_testing_results(
    nda_name: str,
    comparison_analysis: dict,
    ai_review_data: dict,
    hr_edits_data: list,
    executive_summary_fig: go.Figure,
    model_used: str,
    temperature: float,
    analysis_mode: str
) -> str:
    """
    Save complete testing results to disk
    
    Args:
        nda_name: Name of the NDA tested
        comparison_analysis: Comparison analysis results
        ai_review_data: AI review results
        hr_edits_data: HR edits data
        executive_summary_fig: Plotly figure for executive summary
        model_used: AI model used for analysis
        temperature: Temperature setting used
        analysis_mode: Analysis mode used
        
    Returns:
        str: Result ID for the saved results
    """
    ensure_results_directory()
    
    result_id = generate_result_id(nda_name)
    result_dir = os.path.join(RESULTS_DIR, result_id)
    os.makedirs(result_dir, exist_ok=True)
    
    # Save metadata
    metadata = {
        "result_id": result_id,
        "nda_name": nda_name,
        "timestamp": datetime.now().isoformat(),
        "model_used": model_used,
        "temperature": temperature,
        "analysis_mode": analysis_mode,
        "ai_issues_count": len(ai_review_data.get("high_priority", [])) + 
                          len(ai_review_data.get("medium_priority", [])) + 
                          len(ai_review_data.get("low_priority", [])),
        "hr_edits_count": len(hr_edits_data)
    }
    
    with open(os.path.join(result_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Save analysis results
    analysis_data = {
        "comparison_analysis": comparison_analysis,
        "ai_review_data": ai_review_data,
        "hr_edits_data": hr_edits_data
    }
    
    with open(os.path.join(result_dir, "analysis_results.json"), "w") as f:
        json.dump(analysis_data, f, indent=2)
    
    # Save executive summary plot as HTML and PNG
    executive_summary_fig.write_html(os.path.join(result_dir, "executive_summary.html"))
    executive_summary_fig.write_image(os.path.join(result_dir, "executive_summary.png"))
    
    # Save the plotly figure object for later use
    with open(os.path.join(result_dir, "executive_summary_fig.pkl"), "wb") as f:
        pickle.dump(executive_summary_fig, f)
    
    return result_id

def get_saved_results() -> List[Dict]:
    """
    Get list of all saved results with metadata
    
    Returns:
        List of result metadata dictionaries
    """
    ensure_results_directory()
    
    results = []
    if not os.path.exists(RESULTS_DIR):
        return results
    
    for result_dir in os.listdir(RESULTS_DIR):
        metadata_path = os.path.join(RESULTS_DIR, result_dir, "metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    results.append(metadata)
            except Exception as e:
                print(f"Error loading metadata for {result_dir}: {e}")
                continue
    
    # Sort by timestamp (newest first)
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results

def load_saved_result(result_id: str) -> Optional[Tuple[Dict, Dict, List, go.Figure]]:
    """
    Load a saved testing result
    
    Args:
        result_id: ID of the result to load
        
    Returns:
        Tuple of (comparison_analysis, ai_review_data, hr_edits_data, executive_summary_fig)
        or None if not found
    """
    result_dir = os.path.join(RESULTS_DIR, result_id)
    
    if not os.path.exists(result_dir):
        return None
    
    try:
        # Load analysis results
        with open(os.path.join(result_dir, "analysis_results.json"), "r") as f:
            analysis_data = json.load(f)
        
        # Load executive summary figure
        with open(os.path.join(result_dir, "executive_summary_fig.pkl"), "rb") as f:
            executive_summary_fig = pickle.load(f)
        
        return (
            analysis_data["comparison_analysis"],
            analysis_data["ai_review_data"], 
            analysis_data["hr_edits_data"],
            executive_summary_fig
        )
    except Exception as e:
        print(f"Error loading result {result_id}: {e}")
        return None

def delete_saved_result(result_id: str) -> bool:
    """
    Delete a saved result
    
    Args:
        result_id: ID of the result to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    result_dir = os.path.join(RESULTS_DIR, result_id)
    
    if not os.path.exists(result_dir):
        return False
    
    try:
        import shutil
        shutil.rmtree(result_dir)
        return True
    except Exception as e:
        print(f"Error deleting result {result_id}: {e}")
        return False

def get_results_summary() -> Dict:
    """
    Get summary statistics of all saved results
    
    Returns:
        Dictionary with summary statistics
    """
    results = get_saved_results()
    
    if not results:
        return {
            "total_results": 0,
            "total_ndas": 0,
            "most_recent": None,
            "models_used": [],
            "avg_ai_issues": 0,
            "avg_hr_edits": 0
        }
    
    # Calculate statistics
    total_results = len(results)
    unique_ndas = len(set(r["nda_name"] for r in results))
    most_recent = results[0] if results else None
    models_used = list(set(r["model_used"] for r in results))
    
    avg_ai_issues = sum(r.get("ai_issues_count", 0) for r in results) / len(results)
    avg_hr_edits = sum(r.get("hr_edits_count", 0) for r in results) / len(results)
    
    return {
        "total_results": total_results,
        "total_ndas": unique_ndas,
        "most_recent": most_recent,
        "models_used": models_used,
        "avg_ai_issues": round(avg_ai_issues, 1),
        "avg_hr_edits": round(avg_hr_edits, 1)
    }