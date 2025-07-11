"""
Utility functions for the NDA Analysis Comparison Tool
"""

import json
import re
from typing import Dict, List, Any, Optional
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

def validate_file(uploaded_file) -> bool:
    """
    Validate uploaded file format and size
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        bool: True if file is valid, False otherwise
    """
    if uploaded_file is None:
        return False
    
    # Check file extension
    allowed_extensions = ['.md', '.txt', '.pdf', '.docx']
    file_extension = '.' + uploaded_file.name.split('.')[-1].lower()
    
    if file_extension not in allowed_extensions:
        st.error(f"Unsupported file format: {file_extension}")
        return False
    
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB in bytes
    if len(uploaded_file.getvalue()) > max_size:
        st.error("File size exceeds 10MB limit")
        return False
    
    return True

def safe_json_loads(json_str: str) -> Optional[Dict]:
    """
    Safely parse JSON string with error handling
    
    Args:
        json_str: JSON string to parse
        
    Returns:
        Parsed JSON object or None if parsing fails
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

def extract_metrics_from_analysis(comparison_analysis, ai_review_data: Dict, hr_edits_data: List) -> Dict:
    """
    Extract key metrics from analysis results
    
    Args:
        comparison_analysis: JSON object or text analysis comparing AI vs HR
        ai_review_data: AI review JSON data
        hr_edits_data: HR edits JSON data
        
    Returns:
        Dictionary containing extracted metrics
    """
    metrics = {
        'ai_total_issues': 0,
        'hr_total_changes': len(hr_edits_data) if hr_edits_data else 0,
        'correctly_identified': 0,
        'missed_by_ai': 0,
        'not_addressed_by_hr': 0
    }
    
    # Count AI issues
    if ai_review_data:
        red_flags = ai_review_data.get('red_flags', [])
        yellow_flags = ai_review_data.get('yellow_flags', [])
        metrics['ai_total_issues'] = len(red_flags) + len(yellow_flags)
    
    # Extract metrics from comparison analysis
    if comparison_analysis:
        if isinstance(comparison_analysis, dict):
            # New JSON format - extract directly from summary or count arrays
            if 'summary' in comparison_analysis:
                summary = comparison_analysis['summary']
                metrics['correctly_identified'] = summary.get('correctly_identified_count', 0)
                metrics['missed_by_ai'] = summary.get('missed_by_ai_count', 0)
                metrics['not_addressed_by_hr'] = summary.get('not_addressed_by_hr_count', 0)
            else:
                # Count from arrays if summary is missing
                metrics['correctly_identified'] = len(comparison_analysis.get('correctly_identified', []))
                metrics['missed_by_ai'] = len(comparison_analysis.get('missed_by_ai', []))
                metrics['not_addressed_by_hr'] = len(comparison_analysis.get('not_addressed_by_hr', []))
        else:
            # Old text format - use regex parsing
            correctly_identified_section = re.search(
                r'### Issues Correctly Identified by the AI\n(.*?)(?=### |$)', 
                comparison_analysis, 
                re.DOTALL
            )
            if correctly_identified_section:
                content = correctly_identified_section.group(1)
                metrics['correctly_identified'] = len(re.findall(r'- \*\*Issue\*\*:', content))
            
            missed_section = re.search(
                r'### Issues Missed by the AI\n(.*?)(?=### |$)', 
                comparison_analysis, 
                re.DOTALL
            )
            if missed_section:
                content = missed_section.group(1)
                metrics['missed_by_ai'] = len(re.findall(r'- \*\*Issue\*\*:', content))
            
            not_addressed_section = re.search(
                r'### Issues Flagged by AI but Not Addressed by HR\n(.*?)(?=### |$)', 
                comparison_analysis, 
                re.DOTALL
            )
            if not_addressed_section:
                content = not_addressed_section.group(1)
                metrics['not_addressed_by_hr'] = len(re.findall(r'- \*\*Issue\*\*:', content))
    
    return metrics

def create_comparison_chart(metrics: Dict) -> go.Figure:
    """
    Create a comparison chart showing AI vs HR metrics
    
    Args:
        metrics: Dictionary containing metrics
        
    Returns:
        Plotly figure object
    """
    # Create comparison data
    categories = ['AI Issues Flagged', 'HR Changes Made', 'Correctly Identified', 'Missed by AI', 'Not Addressed by HR']
    values = [
        metrics['ai_total_issues'],
        metrics['hr_total_changes'],
        metrics['correctly_identified'],
        metrics['missed_by_ai'],
        metrics['not_addressed_by_hr']
    ]
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#ff9500']
    
    # Create bar chart
    fig = go.Figure(data=[
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=values,
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title='Analysis Comparison Overview',
        xaxis_title='Category',
        yaxis_title='Count',
        height=400,
        showlegend=False
    )
    
    return fig

def format_analysis_results(comparison_analysis: str) -> Dict[str, List[Dict]]:
    """
    Parse and format the comparison analysis text into structured data
    
    Args:
        comparison_analysis: Raw comparison analysis text
        
    Returns:
        Dictionary with categorized analysis results
    """
    results = {
        'correctly_identified': [],
        'missed_by_ai': [],
        'not_addressed_by_hr': []
    }
    
    # Parse correctly identified issues
    correctly_identified_section = re.search(
        r'### Issues Correctly Identified by the AI\n(.*?)(?=### |$)', 
        comparison_analysis, 
        re.DOTALL
    )
    if correctly_identified_section:
        content = correctly_identified_section.group(1)
        results['correctly_identified'] = parse_issue_section(content)
    
    # Parse missed by AI
    missed_section = re.search(
        r'### Issues Missed by the AI\n(.*?)(?=### |$)', 
        comparison_analysis, 
        re.DOTALL
    )
    if missed_section:
        content = missed_section.group(1)
        results['missed_by_ai'] = parse_issue_section(content)
    
    # Parse not addressed by HR
    not_addressed_section = re.search(
        r'### Issues Flagged by AI but Not Addressed by HR\n(.*?)(?=### |$)', 
        comparison_analysis, 
        re.DOTALL
    )
    if not_addressed_section:
        content = not_addressed_section.group(1)
        results['not_addressed_by_hr'] = parse_issue_section(content)
    
    return results

def parse_issue_section(content: str) -> List[Dict]:
    """
    Parse individual issue section into structured data
    
    Args:
        content: Section content to parse
        
    Returns:
        List of issue dictionaries
    """
    issues = []
    
    # Find all issue blocks
    issue_blocks = re.findall(
        r'- \*\*Issue\*\*:\s*(.*?)\n\s*- \*\*Analysis\*\*:\s*(.*?)(?=\n- \*\*Issue\*\*:|$)', 
        content, 
        re.DOTALL
    )
    
    for title, analysis in issue_blocks:
        # Extract section if present
        section_match = re.search(r'\(.*?section\s+(\w+).*?\)', title)
        section = section_match.group(1) if section_match else None
        
        issues.append({
            'title': title.strip(),
            'analysis': analysis.strip(),
            'section': section
        })
    
    return issues

def create_accuracy_pie_chart(metrics: Dict) -> go.Figure:
    """
    Create a pie chart showing AI accuracy breakdown
    
    Args:
        metrics: Dictionary containing metrics
        
    Returns:
        Plotly figure object
    """
    labels = ['Correctly Identified', 'Missed by AI', 'Not Addressed by HR']
    values = [
        metrics['correctly_identified'],
        metrics['missed_by_ai'],
        metrics['not_addressed_by_hr']
    ]
    
    colors = ['#2ca02c', '#d62728', '#ff9500']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker_colors=colors,
        textinfo='label+percent',
        textposition='auto'
    )])
    
    fig.update_layout(
        title='AI Analysis Accuracy Breakdown',
        height=400
    )
    
    return fig

def export_analysis_summary(comparison_analysis: str, ai_review_data: Dict, hr_edits_data: List) -> str:
    """
    Create a summary report for export
    
    Args:
        comparison_analysis: Comparison analysis text
        ai_review_data: AI review data
        hr_edits_data: HR edits data
        
    Returns:
        Formatted summary string
    """
    metrics = extract_metrics_from_analysis(comparison_analysis, ai_review_data, hr_edits_data)
    
    summary = f"""
NDA Analysis Comparison Summary
===============================

Overall Metrics:
- AI Issues Flagged: {metrics['ai_total_issues']}
- HR Changes Made: {metrics['hr_total_changes']}
- Issues Correctly Identified: {metrics['correctly_identified']}
- Issues Missed by AI: {metrics['missed_by_ai']}
- Issues Flagged but Not Addressed: {metrics['not_addressed_by_hr']}

Accuracy Rate: {(metrics['correctly_identified'] / max(metrics['ai_total_issues'], 1)) * 100:.1f}%
Coverage Rate: {((metrics['correctly_identified'] + metrics['missed_by_ai']) / max(metrics['hr_total_changes'], 1)) * 100:.1f}%

Analysis Details:
{comparison_analysis}
"""
    
    return summary
