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
    
    # Calculate AI accuracy using the formula: (HR changes made - Missed by AI) / HR changes made
    if metrics['hr_total_changes'] > 0:
        metrics['ai_accuracy_percentage'] = ((metrics['hr_total_changes'] - metrics['missed_by_ai']) / metrics['hr_total_changes']) * 100
    else:
        metrics['ai_accuracy_percentage'] = 100 if metrics['missed_by_ai'] == 0 else 0
    
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

def extract_detailed_comparison_data(comparison_analysis: str, ai_review_data: Dict, hr_edits_data: List) -> Dict:
    """
    Extract detailed comparison data for table display
    
    Args:
        comparison_analysis: Comparison analysis text
        ai_review_data: AI review data
        hr_edits_data: HR edits data
        
    Returns:
        Dictionary containing detailed comparison tables data
    """
    try:
        # Parse comparison analysis if it's a string
        if isinstance(comparison_analysis, str):
            parsed_analysis = format_analysis_results(comparison_analysis)
        else:
            parsed_analysis = comparison_analysis
        
        # Extract AI correctly identified flags
        correctly_identified = []
        if 'correctly_identified' in parsed_analysis:
            for match in parsed_analysis['correctly_identified']:
                correctly_identified.append({
                    'flag': match.get('title', match.get('issue', 'Unknown issue')),
                    'description': match.get('analysis', match.get('problem', 'No description available'))
                })
        
        # Extract missed flags by AI
        missed_flags = []
        if 'missed_by_ai' in parsed_analysis:
            for missed in parsed_analysis['missed_by_ai']:
                missed_flags.append({
                    'flag': missed.get('title', missed.get('issue', 'Unknown issue')),
                    'description': missed.get('analysis', missed.get('problem', 'No description available'))
                })
        
        # Extract AI false positives (flagged by AI but not addressed by HR)
        false_positives = []
        if 'not_addressed_by_hr' in parsed_analysis:
            for fp in parsed_analysis['not_addressed_by_hr']:
                false_positives.append({
                    'flag': fp.get('title', fp.get('issue', 'Unknown issue')),
                    'description': fp.get('analysis', fp.get('problem', 'No description available'))
                })
        
        # If parsing fails, try to extract from raw data
        if not correctly_identified and not missed_flags and not false_positives:
            # Fallback: extract from AI and HR data directly
            ai_issues = []
            if ai_review_data and isinstance(ai_review_data, dict):
                red_flags = ai_review_data.get('red_flags', [])
                yellow_flags = ai_review_data.get('yellow_flags', [])
                for flag in red_flags + yellow_flags:
                    ai_issues.append({
                        'flag': flag.get('issue', 'Unknown issue'),
                        'description': flag.get('problem', 'No description available')
                    })
            
            hr_issues = []
            if hr_edits_data and isinstance(hr_edits_data, list):
                for edit in hr_edits_data:
                    hr_issues.append({
                        'flag': edit.get('issue', 'Unknown issue'),
                        'description': edit.get('problem', 'No description available')
                    })
            
            # Simple matching based on issue text similarity
            correctly_identified = []
            missed_flags = []
            false_positives = []
            
            ai_issue_texts = [item['flag'].lower() for item in ai_issues]
            hr_issue_texts = [item['flag'].lower() for item in hr_issues]
            
            # Find matches
            for ai_item in ai_issues:
                ai_text = ai_item['flag'].lower()
                if any(ai_text in hr_text or hr_text in ai_text for hr_text in hr_issue_texts):
                    correctly_identified.append(ai_item)
                else:
                    false_positives.append(ai_item)
            
            # Find missed issues
            for hr_item in hr_issues:
                hr_text = hr_item['flag'].lower()
                if not any(hr_text in ai_text or ai_text in hr_text for ai_text in ai_issue_texts):
                    missed_flags.append(hr_item)
        
        return {
            'correctly_identified': correctly_identified,
            'missed_flags': missed_flags,
            'false_positives': false_positives
        }
        
    except Exception as e:
        print(f"Error extracting detailed comparison data: {e}")
        return {
            'correctly_identified': [],
            'missed_flags': [],
            'false_positives': []
        }

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

AI Accuracy Rate: {((max(metrics['hr_total_changes'], 1) - metrics['missed_by_ai']) / max(metrics['hr_total_changes'], 1)) * 100:.1f}%
Coverage Rate: {((metrics['correctly_identified'] + metrics['missed_by_ai']) / max(metrics['hr_total_changes'], 1)) * 100:.1f}%

Analysis Details:
{comparison_analysis}
"""
    
    return summary
