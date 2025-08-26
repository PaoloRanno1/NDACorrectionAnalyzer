import streamlit as st
import tempfile
import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import subprocess
from datetime import datetime
import traceback
from typing import Dict, List, Tuple, Optional
import threading
import time
import uuid

# Import the analysis modules
try:
    from Clean_testing import TestingChain
except ImportError:
    # Handle import error gracefully
    TestingChain = None
from policies_playbook import display_policies_playbook
from utils import (
    validate_file, 
    extract_metrics_from_analysis, 
    create_comparison_chart,
    format_analysis_results,
    safe_json_loads
)

# Page configuration
st.set_page_config(
    page_title="NDA Analysis Comparison Tool",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App version for cache busting
APP_VERSION = "2.1.0"

def initialize_session_state():
    """Initialize session state variables"""
    # Check for force refresh parameter
    query_params = st.query_params
    if 'refresh' in query_params:
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.query_params.clear()  # Clear query params
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'ai_review_data' not in st.session_state:
        st.session_state.ai_review_data = None
    if 'hr_edits_data' not in st.session_state:
        st.session_state.hr_edits_data = None
    if 'clean_file_content' not in st.session_state:
        st.session_state.clean_file_content = None
    if 'corrected_file_content' not in st.session_state:
        st.session_state.corrected_file_content = None
    if 'analysis_config' not in st.session_state:
        st.session_state.analysis_config = {
            'model': 'gemini-2.5-pro',
            'temperature': 0.0,
            'analysis_mode': 'Full Analysis'
        }
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'clean_review'
    
    # Background processing states
    if 'background_analysis' not in st.session_state:
        st.session_state.background_analysis = {
            'running': False,
            'progress': 0,
            'status': 'idle',
            'results': None,
            'error': None,
            'analysis_id': None,
            'start_time': None,
            'files': {'clean': None, 'corrected': None},
            'config': None
        }

def run_background_analysis(analysis_id, clean_file_content, corrected_file_content, model, temperature, analysis_mode):
    """Run NDA analysis in background thread"""
    try:
        # Update progress
        st.session_state.background_analysis['status'] = 'Initializing analysis...'
        st.session_state.background_analysis['progress'] = 10
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as clean_temp:
            clean_temp.write(clean_file_content)
            clean_temp_path = clean_temp.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as corrected_temp:
            corrected_temp.write(corrected_file_content)
            corrected_temp_path = corrected_temp.name
        
        # Initialize TestingChain
        st.session_state.background_analysis['status'] = 'Setting up analysis chain...'
        st.session_state.background_analysis['progress'] = 20
        
        from playbook_manager import get_current_playbook
        playbook_content = get_current_playbook()
        
        testing_chain = TestingChain(
            model=model,
            temperature=temperature,
            playbook_content=playbook_content
        )
        
        # Run analysis
        st.session_state.background_analysis['status'] = 'Running AI analysis...'
        st.session_state.background_analysis['progress'] = 40
        
        if analysis_mode == "Full Analysis":
            comparison_analysis, comparison_response, ai_review_data, hr_edits_data = testing_chain.analyze_testing(
                clean_temp_path, corrected_temp_path
            )
        else:  # Quick Testing
            # For quick testing, we need to get the AI review first
            st.session_state.background_analysis['status'] = 'Getting AI review...'
            st.session_state.background_analysis['progress'] = 50
            
            from NDA_Review_chain import StradaComplianceChain
            ai_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook_content)
            ai_review_data, _ = ai_chain.analyze_nda(clean_temp_path)
            
            st.session_state.background_analysis['status'] = 'Getting HR edits...'
            st.session_state.background_analysis['progress'] = 70
            
            from NDA_HR_review_chain import NDAComplianceChain
            hr_chain = NDAComplianceChain(model=model, temperature=temperature, playbook_content=playbook_content)
            hr_edits_data, _ = hr_chain.analyze_nda(corrected_temp_path)
            
            st.session_state.background_analysis['status'] = 'Running comparison...'
            st.session_state.background_analysis['progress'] = 85
            
            comparison_analysis = testing_chain.quick_testing(ai_review_data, hr_edits_data)
        
        # Finalize results
        st.session_state.background_analysis['status'] = 'Finalizing results...'
        st.session_state.background_analysis['progress'] = 95
        
        # Store results
        st.session_state.background_analysis['results'] = {
            'comparison_analysis': comparison_analysis,
            'ai_review_data': ai_review_data,
            'hr_edits_data': hr_edits_data
        }
        
        # Clean up temporary files
        os.unlink(clean_temp_path)
        os.unlink(corrected_temp_path)
        
        # Mark as complete
        st.session_state.background_analysis['status'] = 'Analysis complete!'
        st.session_state.background_analysis['progress'] = 100
        st.session_state.background_analysis['running'] = False
        
    except Exception as e:
        st.session_state.background_analysis['error'] = str(e)
        st.session_state.background_analysis['status'] = f'Error: {str(e)}'
        st.session_state.background_analysis['running'] = False
        st.session_state.background_analysis['progress'] = 0

def run_background_single_nda_analysis(analysis_id, file_content, file_extension, model, temperature):
    """Run single NDA analysis in background thread"""
    try:
        # Ensure background analysis is initialized
        if 'background_analysis' not in st.session_state:
            st.session_state.background_analysis = {
                'running': False,
                'progress': 0,
                'status': 'idle',
                'results': None,
                'error': None,
                'analysis_id': None,
                'start_time': None,
                'files': {'clean': None, 'corrected': None},
                'config': None
            }
        
        # Update progress
        st.session_state.background_analysis['status'] = 'Initializing single NDA analysis...'
        st.session_state.background_analysis['progress'] = 10
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=f".{file_extension}") as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Convert DOCX to markdown using Pandoc if needed
        if file_extension == 'docx':
            st.session_state.background_analysis['status'] = 'Converting DOCX to markdown...'
            st.session_state.background_analysis['progress'] = 20
            
            markdown_temp_path = temp_file_path.replace('.docx', '.md')
            try:
                result = subprocess.run([
                    'pandoc', 
                    temp_file_path, 
                    '-o', 
                    markdown_temp_path,
                    '--wrap=none'
                ], capture_output=True, text=True, check=True)
                
                os.unlink(temp_file_path)
                temp_file_path = markdown_temp_path
                
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                st.session_state.background_analysis['error'] = f"Failed to convert DOCX file: {str(e)}"
                st.session_state.background_analysis['running'] = False
                return
        
        # Get current playbook content
        st.session_state.background_analysis['status'] = 'Loading playbook...'
        st.session_state.background_analysis['progress'] = 30
        
        from playbook_manager import get_current_playbook
        playbook_content = get_current_playbook()
        
        # Initialize and run analysis
        st.session_state.background_analysis['status'] = 'Running AI analysis...'
        st.session_state.background_analysis['progress'] = 50
        
        from NDA_Review_chain import StradaComplianceChain
        review_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook_content)
        compliance_report, raw_response = review_chain.analyze_nda(temp_file_path)
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
        # Store results
        st.session_state.background_analysis['status'] = 'Analysis complete!'
        st.session_state.background_analysis['progress'] = 100
        st.session_state.background_analysis['results'] = {
            'compliance_report': compliance_report,
            'raw_response': raw_response
        }
        st.session_state.background_analysis['running'] = False
        
    except Exception as e:
        # Ensure background analysis exists before setting error
        if 'background_analysis' not in st.session_state:
            st.session_state.background_analysis = {
                'running': False,
                'progress': 0,
                'status': 'idle',
                'results': None,
                'error': None,
                'analysis_id': None,
                'start_time': None,
                'files': {'clean': None, 'corrected': None},
                'config': None
            }
        
        st.session_state.background_analysis['error'] = str(e)
        st.session_state.background_analysis['status'] = f'Error: {str(e)}'
        st.session_state.background_analysis['running'] = False
        st.session_state.background_analysis['progress'] = 0

def start_background_analysis(clean_file_content, corrected_file_content, model, temperature, analysis_mode):
    """Start background analysis in a separate thread"""
    analysis_id = str(uuid.uuid4())
    
    # Reset background analysis state
    st.session_state.background_analysis = {
        'running': True,
        'progress': 0,
        'status': 'Starting analysis...',
        'results': None,
        'error': None,
        'analysis_id': analysis_id,
        'start_time': time.time(),
        'files': {'clean': clean_file_content, 'corrected': corrected_file_content},
        'config': {'model': model, 'temperature': temperature, 'analysis_mode': analysis_mode}
    }
    
    # Start background thread
    thread = threading.Thread(
        target=run_background_analysis,
        args=(analysis_id, clean_file_content, corrected_file_content, model, temperature, analysis_mode)
    )
    thread.daemon = True
    thread.start()
    
    return analysis_id

def start_background_single_nda_analysis(file_content, file_extension, model, temperature):
    """Start background single NDA analysis in a separate thread"""
    analysis_id = str(uuid.uuid4())
    
    # Reset background analysis state
    st.session_state.background_analysis = {
        'running': True,
        'progress': 0,
        'status': 'Starting single NDA analysis...',
        'results': None,
        'error': None,
        'analysis_id': analysis_id,
        'start_time': time.time(),
        'files': {'single_nda': file_content},
        'config': {'model': model, 'temperature': temperature, 'analysis_mode': 'single_nda'}
    }
    
    # Start background thread
    thread = threading.Thread(
        target=run_background_single_nda_analysis,
        args=(analysis_id, file_content, file_extension, model, temperature)
    )
    thread.daemon = True
    thread.start()
    
    return analysis_id

def display_login_screen():
    """Display login screen for password protection"""
    st.title("🔐 NDA Analysis Tool Login")
    st.markdown("Please enter the password to access the application.")
    
    with st.form("login_form"):
        password = st.text_input("Password", type="password", placeholder="Enter password")
        login_button = st.form_submit_button("Login")
        
        if login_button:
            if password == "StradaLegal2025":
                st.session_state.authenticated = True
                st.success("Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")

def display_header():
    """Display the application header"""
    # Add logout button in the top right
    col1, col2 = st.columns([6, 1])
    with col1:
        pass  # Empty space
    with col2:
        if st.button("Logout", type="secondary"):
            st.session_state.authenticated = False
            st.rerun()

def display_file_upload_section():
    """Display file upload section with test NDA selection"""
    st.header("📁 NDA Selection")
    
    # Import test database functions
    from test_database import get_test_nda_list, get_test_nda_paths, create_file_objects_from_paths
    import os
    
    # Test NDA selection or custom upload
    test_mode = st.radio(
        "Choose your testing method:",
        ["Select from Test Database", "Upload Custom Files"],
        help="Use pre-loaded test NDAs for consistent testing or upload your own files"
    )
    
    clean_file = None
    corrected_file = None
    
    if test_mode == "Select from Test Database":
        st.subheader("📊 Test NDA Database")
        
        # Get available test NDAs
        test_nda_list = get_test_nda_list()
        
        if test_nda_list:
            selected_nda = st.selectbox(
                "Select a test NDA:",
                [""] + test_nda_list,
                help="Choose from pre-loaded test NDAs for consistent analysis"
            )
            
            if selected_nda:
                # Get file paths
                paths = get_test_nda_paths(selected_nda)
                if paths:
                    clean_path, corrected_path = paths
                    clean_file, corrected_file = create_file_objects_from_paths(clean_path, corrected_path)
                    
                    # Store selected NDA name for saving results
                    st.session_state.selected_test_nda = selected_nda
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.success(f"✅ Clean NDA: {os.path.basename(clean_path)}")
                    with col2:
                        st.success(f"✅ Corrected NDA: {os.path.basename(corrected_path)}")
                    
                    # Show file info
                    st.info(f"**Selected Test NDA:** {selected_nda}")
            else:
                # Clear selected NDA if nothing is selected
                if hasattr(st.session_state, 'selected_test_nda'):
                    delattr(st.session_state, 'selected_test_nda')
        else:
            st.warning("No test NDAs found in the test_data folder. Please add some test files or use custom upload.")
            st.info("Add files to the `test_data/` folder following the naming convention: `[name]_clean.md` and `[name]_corrected.md`")
    
    else:  # Custom upload mode
        st.subheader("📁 Custom File Upload")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Clean NDA File")
            st.markdown("*Upload the original document*")
            clean_file = st.file_uploader(
                "Choose clean NDA file",
                type=['md', 'txt', 'pdf', 'docx'],
                key="clean_file",
                help="Upload the original NDA document without any modifications"
            )
            
            if clean_file:
                if validate_file(clean_file):
                    st.success(f"✅ File uploaded: {clean_file.name}")
                    
                    # Preview option
                    if st.checkbox("Preview clean file content", key="preview_clean"):
                        try:
                            content = clean_file.getvalue().decode('utf-8')
                            st.text_area("File Preview", content[:1000] + "..." if len(content) > 1000 else content, height=200)
                        except:
                            st.warning("Cannot preview this file type")
                else:
                    st.error("❌ Invalid file format or size")
        
        with col2:
            st.subheader("Corrected NDA File")
            st.markdown("*Upload the document with HR tracked changes*")
            corrected_file = st.file_uploader(
                "Choose corrected NDA file",
                type=['md', 'txt', 'pdf', 'docx'],
                key="corrected_file",
                help="Upload the NDA document with HR corrections and tracked changes"
            )
            
            if corrected_file:
                if validate_file(corrected_file):
                    st.success(f"✅ File uploaded: {corrected_file.name}")
                    
                    # Preview option
                    if st.checkbox("Preview corrected file content", key="preview_corrected"):
                        try:
                            content = corrected_file.getvalue().decode('utf-8')
                            st.text_area("File Preview", content[:1000] + "..." if len(content) > 1000 else content, height=200)
                        except:
                            st.warning("Cannot preview this file type")
                else:
                    st.error("❌ Invalid file format or size")
    
    return clean_file, corrected_file

# Removed run_analysis function - using direct synchronous processing instead

# Removed display_background_analysis_progress function - using synchronous processing instead  # Background analysis is active

def display_executive_summary(comparison_analysis, ai_review_data, hr_edits_data):
    """Display executive summary with metrics and charts"""
    st.header("📊 Executive Summary")
    
    # Extract detailed metrics for stacked chart
    from utils import extract_detailed_metrics_from_analysis
    metrics = extract_detailed_metrics_from_analysis(comparison_analysis, ai_review_data, hr_edits_data)
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "AI Issues Flagged",
            metrics['ai_total_issues'],
            help="Total number of issues identified by AI"
        )
    
    with col2:
        st.metric(
            "HR Changes Made",
            metrics['hr_total_changes'],
            help="Total number of changes made by HR"
        )
    
    with col3:
        st.metric(
            "Correctly Identified",
            metrics['correctly_identified'],
            help="Issues correctly identified by AI"
        )
    
    with col4:
        # Use the accuracy formula: (HR changes made - Missed by AI) / HR changes made
        if metrics['hr_total_changes'] > 0:
            accuracy_rate = ((metrics['hr_total_changes'] - metrics['missed_by_ai']) / metrics['hr_total_changes']) * 100
        else:
            accuracy_rate = 100 if metrics['missed_by_ai'] == 0 else 0
        
        st.metric(
            "AI Accuracy",
            f"{accuracy_rate:.1f}%",
            help="AI accuracy based on missed issues: (HR Changes Made - Missed by AI) / HR Changes Made × 100"
        )
    
    # Create comparison chart
    if metrics['ai_total_issues'] > 0 or metrics['hr_total_changes'] > 0:
        fig = create_comparison_chart(metrics)
        st.plotly_chart(fig, use_container_width=True)

def display_detailed_comparison_tables(comparison_analysis, ai_review_data, hr_edits_data):
    """Display detailed comparison tables matching the reference design"""
    # Remove duplicate header - will be added by caller
    
    import pandas as pd
    
    # Custom CSS for professional table styling
    st.markdown("""
    <style>
    .dataframe {
        border: 1px solid #ddd;
        border-radius: 8px;
        overflow: hidden;
        font-family: 'Arial', sans-serif;
    }
    .dataframe th {
        background-color: #2c3e50;
        color: white;
        font-weight: bold;
        text-align: left;
        padding: 12px;
        border-bottom: 2px solid #34495e;
    }
    .dataframe td {
        padding: 10px;
        border-bottom: 1px solid #ecf0f1;
        vertical-align: top;
    }
    .dataframe tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    .dataframe tr:nth-child(odd) {
        background-color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Extract data from comparison analysis
    correctly_identified = []
    missed_by_ai = []
    not_addressed_by_hr = []
    
    if isinstance(comparison_analysis, dict):
        correctly_identified = comparison_analysis.get('Issues Correctly Identified by the AI', [])
        missed_by_ai = comparison_analysis.get('Issues Missed by the AI', [])
        not_addressed_by_hr = comparison_analysis.get('Issues Flagged by AI but Not Addressed by HR', [])
    
    # Helper function to create table data matching the reference design
    def create_table_data(issues_list):
        table_data = []
        for item in issues_list:
            if isinstance(item, dict):
                # Use exact key names from the JSON structure
                issue = item.get("Issue", "N/A")
                section = item.get("Section", "N/A") 
                priority = item.get("Priority", "N/A")
                analysis = item.get("Analysis", "N/A")
                
                table_data.append({
                    "Issue": issue,
                    "Section": section,
                    "Priority": priority,
                    "Analysis": analysis
                })
        return table_data
    
    # Table 1: Issues Correctly Identified By The AI
    st.markdown("### ✅ Issues Correctly Identified By The AI")
    if correctly_identified:
        table1_data = create_table_data(correctly_identified)
        df1 = pd.DataFrame(table1_data)
        st.dataframe(
            df1, 
            use_container_width=True, 
            hide_index=True,
            height=300,
            column_config={
                "Issue": st.column_config.TextColumn("Issue", width="large"),
                "Section": st.column_config.TextColumn("Section", width="small"),
                "Priority": st.column_config.TextColumn("Priority", width="small"),
                "Analysis": st.column_config.TextColumn("Analysis", width="large")
            }
        )
    else:
        empty_df1 = pd.DataFrame({
            "Issue": ["No issues correctly identified"],
            "Section": ["N/A"], 
            "Priority": ["N/A"],
            "Analysis": ["No matching issues found between AI and HR reviews"]
        })
        st.dataframe(empty_df1, use_container_width=True, hide_index=True, height=100)
    
    # Table 2: Issues Missed By The AI  
    st.markdown("### ❌ Issues Missed By The AI")
    if missed_by_ai:
        table2_data = create_table_data(missed_by_ai)
        df2 = pd.DataFrame(table2_data)
        st.dataframe(
            df2, 
            use_container_width=True, 
            hide_index=True,
            height=300,
            column_config={
                "Issue": st.column_config.TextColumn("Issue", width="large"),
                "Section": st.column_config.TextColumn("Section", width="small"),
                "Priority": st.column_config.TextColumn("Priority", width="small"),
                "Analysis": st.column_config.TextColumn("Analysis", width="large")
            }
        )
    else:
        empty_df2 = pd.DataFrame({
            "Issue": ["No issues missed"],
            "Section": ["N/A"],
            "Priority": ["N/A"], 
            "Analysis": ["AI successfully identified all relevant issues"]
        })
        st.dataframe(empty_df2, use_container_width=True, hide_index=True, height=100)
    
    # Table 3: Issues Flagged By AI But Not Addressed By HR
    st.markdown("### ⚠️ Issues Flagged By AI But Not Addressed By HR")
    if not_addressed_by_hr:
        table3_data = create_table_data(not_addressed_by_hr)
        df3 = pd.DataFrame(table3_data)
        st.dataframe(
            df3, 
            use_container_width=True, 
            hide_index=True,
            height=300,
            column_config={
                "Issue": st.column_config.TextColumn("Issue", width="large"),
                "Section": st.column_config.TextColumn("Section", width="small"),
                "Priority": st.column_config.TextColumn("Priority", width="small"),
                "Analysis": st.column_config.TextColumn("Analysis", width="large")
            }
        )
    else:
        empty_df3 = pd.DataFrame({
            "Issue": ["No additional flags"],
            "Section": ["N/A"],
            "Priority": ["N/A"],
            "Analysis": ["All AI-flagged issues were appropriately addressed by HR"]
        })
        st.dataframe(empty_df3, use_container_width=True, hide_index=True, height=100)

def display_detailed_comparison(comparison_analysis):
    """Display detailed comparison results"""
    # Remove duplicate header - will be added by caller
    
    if not comparison_analysis:
        st.warning("No comparison analysis data available.")
        return
    
    # Check if comparison_analysis is already JSON (new format) or text (old format)
    if isinstance(comparison_analysis, dict):
        # New JSON format
        if comparison_analysis.get("text_fallback"):
            # JSON parsing failed, show text fallback
            st.subheader("📄 Comparison Analysis Results")
            st.markdown(comparison_analysis["text_fallback"])
        else:
            # Display structured JSON results using the correct key names
            categories = [
                ("Issues Correctly Identified by the AI", "✅ Issues Correctly Identified by AI", "green"),
                ("Issues Missed by the AI", "❌ Issues Missed by AI", "red"), 
                ("Issues Flagged by AI but Not Addressed by HR", "⚠️ Issues Flagged by AI but Not Addressed by HR", "orange")
            ]
            
            for category_key, title, color in categories:
                items = comparison_analysis.get(category_key, [])
                if items:
                    st.subheader(title)
                    for idx, item in enumerate(items):
                        with st.expander(f"{item.get('Issue', f'Issue {idx+1}')}", expanded=False):
                            st.markdown(f"**Section:** {item.get('Section', 'N/A')}")
                            st.markdown(f"**Priority:** {item.get('Priority', 'N/A')}")
                            st.markdown(f"**Analysis:** {item.get('Analysis', 'No analysis provided')}")
                else:
                    st.subheader(title)
                    if "Correctly Identified" in category_key:
                        st.info("No issues were correctly identified by the AI.")
                    elif "Missed" in category_key:
                        st.info("The AI did not miss any issues that HR addressed.")
                    elif "Not Addressed" in category_key:
                        st.info("All AI-flagged issues were addressed by HR.")
    else:
        # Old text format - use existing parsing logic
        formatted_results = format_analysis_results(comparison_analysis)
        has_structured_data = any(len(items) > 0 for items in formatted_results.values())
        
        if has_structured_data:
            for category, items in formatted_results.items():
                if items:
                    if category == "correctly_identified":
                        st.subheader("✅ Issues Correctly Identified by AI")
                    elif category == "missed_by_ai":
                        st.subheader("❌ Issues Missed by AI")
                    elif category == "not_addressed_by_hr":
                        st.subheader("⚠️ Issues Flagged by AI but Not Addressed by HR")
                    
                    for idx, item in enumerate(items):
                        with st.expander(f"{item['title']}", expanded=False):
                            st.markdown(f"**Analysis:** {item['analysis']}")
                            if item.get('section'):
                                st.markdown(f"**Section:** {item['section']}")
        else:
            st.subheader("📄 Comparison Analysis Results")
            st.markdown(comparison_analysis)

def display_raw_data_export(comparison_analysis, ai_review_data, hr_edits_data):
    """Display raw data export section"""
    st.header("📥 Raw Data Export")
    
    # Create export data
    export_data = {
        "analysis_timestamp": datetime.now().isoformat(),
        "configuration": st.session_state.analysis_config,
        "comparison_analysis": comparison_analysis,
        "ai_review_results": ai_review_data,
        "hr_edits_analysis": hr_edits_data
    }
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if isinstance(comparison_analysis, dict):
            comparison_data = json.dumps(comparison_analysis, indent=2)
        else:
            comparison_data = str(comparison_analysis)
        
        st.download_button(
            label="📄 Download Comparison Analysis",
            data=comparison_data,
            file_name=f"comparison_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    
    with col2:
        st.download_button(
            label="📊 Download AI Review JSON",
            data=json.dumps(ai_review_data, indent=2),
            file_name=f"ai_review_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    with col3:
        st.download_button(
            label="📋 Download HR Edits JSON",
            data=json.dumps(hr_edits_data, indent=2),
            file_name=f"hr_edits_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    # Complete export
    st.download_button(
        label="📦 Download Complete Analysis Package",
        data=json.dumps(export_data, indent=2),
        file_name=f"complete_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )

def display_json_viewers(ai_review_data, hr_edits_data, comparison_analysis=None):
    """Display JSON data viewers including testing comparison"""
    st.header("📋 Analysis Data")
    
    tab1, tab2, tab3 = st.tabs(["AI Review Results", "HR Edits Analysis", "Testing Comparison"])
    
    with tab1:
        st.subheader("AI Review JSON")
        if ai_review_data:
            st.json(ai_review_data)
        else:
            st.info("No AI review data available")
    
    with tab2:
        st.subheader("HR Edits JSON")
        if hr_edits_data:
            st.json(hr_edits_data)
        else:
            st.info("No HR edits data available")
    
    with tab3:
        st.subheader("Testing Comparison JSON")
        if comparison_analysis:
            st.json(comparison_analysis)
        else:
            st.info("No testing comparison data available")

def display_single_nda_review(model, temperature):
    """Display clean NDA review section as main homepage"""
    # Header with settings and database buttons
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.title("Tracked Changes Document Generation")
    
    with col2:
        if st.button("⚙️ AI Settings", key="clean_review_settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.get('show_settings', False)
            st.rerun()
    
    with col3:
        pass  # Empty space
    
    # Display settings modal if activated
    if st.session_state.get('show_settings', False):
        display_settings_modal()
    
    st.markdown("""
- This version supports tracked changes document generation after AI analysis (it only works for word files).
- Please don't change page when reviewing an NDA, it will stop the review.
""")
    
    # File source selection
    source_type = st.radio(
        "Select NDA source:",
        ["Upload File", "Load from Database"],
        help="Choose whether to upload a new file or select from your existing database"
    )
    
    uploaded_file = None
    
    if source_type == "Upload File":
        # File upload section
        uploaded_file = st.file_uploader(
            "Choose an NDA file to analyze",
            type=['docx', 'pdf', 'txt', 'md'],
            help="Upload the NDA document (DOCX preferred for post-review editing features)",
            key="single_nda_upload"
        )
    else:
        # Database selection
        from test_database import get_all_clean_ndas
        clean_ndas = get_all_clean_ndas()
        
        if clean_ndas:
            selected_nda = st.selectbox(
                "Select NDA from database:",
                list(clean_ndas.keys()),
                help="Choose a clean NDA from your database to analyze"
            )
            
            if selected_nda:
                # Create a file-like object from the database file
                clean_file_path = clean_ndas[selected_nda]
                
                class DatabaseFile:
                    def __init__(self, file_path, name):
                        self.file_path = file_path
                        self.name = name
                    
                    def getvalue(self):
                        with open(self.file_path, 'r', encoding='utf-8') as f:
                            return f.read().encode('utf-8')
                    
                    def read(self):
                        with open(self.file_path, 'r', encoding='utf-8') as f:
                            return f.read().encode('utf-8')
                
                uploaded_file = DatabaseFile(clean_file_path, f"{selected_nda}_clean.md")
                st.success(f"✅ Loaded from database: {selected_nda}")
        else:
            st.info("No NDAs found in database. Upload some NDAs using the Database tab first.")
            st.markdown("👆 Click the 'Database' button above to upload NDAs to your database.")
    
    if uploaded_file:
        if validate_file(uploaded_file):
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            
            # Preview option
            if st.checkbox("Preview file content", key="preview_single"):
                try:
                    content = uploaded_file.getvalue().decode('utf-8')
                    st.text_area("File Preview", content[:1000] + "..." if len(content) > 1000 else content, height=200)
                except:
                    st.warning("Cannot preview this file type")
        else:
            st.error("❌ Invalid file format or size")
            return
    
    # Dual functionality buttons
    if uploaded_file:
        st.markdown("---")
        st.subheader("🎯 Choose Your Workflow")
        
        col1, col2 = st.columns(2)
        
        with col1:
            run_single_analysis = st.button(
                "🔍 Review NDA First",
                disabled=not uploaded_file,
                use_container_width=True,
                key="run_single_analysis",
                help="Get AI analysis first, then optionally generate tracked changes document"
            )
        
        with col2:
            run_direct_tracked_changes = st.button(
                "📝 Direct Tracked Changes Generation",
                disabled=not uploaded_file,
                use_container_width=True,
                key="run_direct_tracked_changes",
                help="Skip review step and directly generate tracked changes document with all identified issues"
            )
            
        # Store button states and file in session state for async processing
        if run_direct_tracked_changes:
            st.session_state.run_direct_tracked_changes = True
            st.session_state.uploaded_file = uploaded_file
            st.session_state.model = model
            st.session_state.temperature = temperature
    else:
        run_single_analysis = False
        run_direct_tracked_changes = False
    
    # Run review directly without background processing
    if run_single_analysis and uploaded_file:
        try:
            with st.spinner("🔄 Analyzing NDA... This may take a few minutes."):
                file_extension = uploaded_file.name.split('.')[-1].lower()
                file_content = uploaded_file.getvalue()
                
                # Write content to temporary file
                import tempfile
                import os
                
                if file_extension in ['docx', 'pdf']:
                    # For binary files (DOCX, PDF), write as binary
                    with tempfile.NamedTemporaryFile(mode='wb', suffix=f'.{file_extension}', delete=False) as temp_file:
                        temp_file.write(file_content)
                        temp_file_path = temp_file.name
                else:
                    # For text files, write as UTF-8
                    with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{file_extension}', delete=False, encoding='utf-8') as temp_file:
                        if isinstance(file_content, bytes):
                            content_str = file_content.decode('utf-8')
                        else:
                            content_str = file_content
                        temp_file.write(content_str)
                        temp_file_path = temp_file.name
                
                # Handle DOCX conversion if needed
                if file_extension == 'docx':
                    try:
                        # Use pandoc to convert DOCX to markdown
                        import subprocess
                        converted_path = temp_file_path.replace('.docx', '.md')
                        
                        # Run pandoc conversion
                        result = subprocess.run([
                            'pandoc', 
                            temp_file_path, 
                            '-o', converted_path,
                            '--to=markdown'
                        ], capture_output=True, text=True, check=True)
                        
                        # Clean up original DOCX file
                        os.unlink(temp_file_path)
                        temp_file_path = converted_path
                        
                    except subprocess.CalledProcessError as e:
                        st.error(f"Failed to convert DOCX file with pandoc: {e.stderr}")
                        st.error("Please try uploading the file as PDF or TXT format instead.")
                        os.unlink(temp_file_path)
                        return
                    except FileNotFoundError:
                        st.error("Pandoc is not installed. Please try uploading the file as PDF or TXT format instead.")
                        os.unlink(temp_file_path)
                        return
                    except Exception as e:
                        st.error(f"Failed to convert DOCX file: {str(e)}")
                        st.error("Please try uploading the file as PDF or TXT format instead.")
                        os.unlink(temp_file_path)
                        return
                
                # Get current playbook content
                from playbook_manager import get_current_playbook
                playbook_content = get_current_playbook()
                
                # Initialize and run analysis
                from NDA_Review_chain import StradaComplianceChain
                review_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook_content)
                compliance_report, raw_response = review_chain.analyze_nda(temp_file_path)
                
                # Clean up temporary file
                os.unlink(temp_file_path)
                
                # Store results
                st.session_state.single_nda_results = compliance_report
                st.session_state.single_nda_raw_response = raw_response
                
                st.success("✅ Analysis complete! Results are ready below.")
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Failed to analyze NDA: {str(e)}")
            st.error("Please check your file and try again.")
            with st.expander("Error Details"):
                st.code(traceback.format_exc())
    
    # Async Direct Tracked Changes Generation
    if st.session_state.get('run_direct_tracked_changes') or st.session_state.get('direct_processing_status') not in ['idle', None]:
        
        # Initialize session state for async processing
        if 'direct_processing_status' not in st.session_state:
            st.session_state.direct_processing_status = 'idle'
        if 'direct_progress' not in st.session_state:
            st.session_state.direct_progress = 0
        if 'direct_status_message' not in st.session_state:
            st.session_state.direct_status_message = ""
        
        # Clear any previous direct generation results when starting fresh
        if st.session_state.get('run_direct_tracked_changes') and st.session_state.direct_processing_status == 'idle':
            if hasattr(st.session_state, 'direct_generation_results'):
                del st.session_state.direct_generation_results
            if hasattr(st.session_state, 'direct_tracked_docx'):
                del st.session_state.direct_tracked_docx
            if hasattr(st.session_state, 'direct_clean_docx'):
                del st.session_state.direct_clean_docx
            if hasattr(st.session_state, 'direct_generation_complete'):
                del st.session_state.direct_generation_complete
        
        # Handle file upload and validation
        if st.session_state.get('run_direct_tracked_changes'):
            uploaded_file = st.session_state.uploaded_file
            model = st.session_state.model
            temperature = st.session_state.temperature
            
            file_extension = uploaded_file.name.split('.')[-1].lower()
            if file_extension != 'docx':
                st.error("Direct tracked changes generation requires a Word document (.docx file).")
                st.info("Please upload a DOCX file or use the 'Review NDA First' option for other file types.")
                # Reset flag
                st.session_state.run_direct_tracked_changes = False
            else:
                # Start processing
                if st.session_state.direct_processing_status == 'idle':
                    st.session_state.direct_processing_status = 'preparing'
                    st.session_state.direct_progress = 0
                    st.session_state.direct_status_message = "🔄 Step 1/4: Preparing document..."
                    st.session_state.direct_model = model
                    st.session_state.direct_temperature = temperature
                    st.session_state.direct_file_content = uploaded_file.getvalue()
                    st.session_state.run_direct_tracked_changes = False  # Reset flag
                    
                    def background_processing():
                        import time
                        try:
                            # Step 1: Prepare document
                            st.session_state.direct_processing_status = 'converting'
                            st.session_state.direct_progress = 25
                            st.session_state.direct_status_message = "🔄 Step 2/4: Converting document format..."
                            
                            # Write content to temporary file
                            with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as temp_file:
                                temp_file.write(st.session_state.direct_file_content)
                                temp_file_path = temp_file.name
                            
                            # Store original docx content for later Word comparison
                            st.session_state['original_docx_content'] = st.session_state.direct_file_content
                            
                            # Convert DOCX to markdown for analysis
                            try:
                                converted_path = temp_file_path.replace('.docx', '.md')
                                result = subprocess.run([
                                    'pandoc', temp_file_path, '-o', converted_path, '--to=markdown'
                                ], capture_output=True, text=True, check=True)
                            except Exception as e:
                                st.session_state.direct_processing_status = 'error'
                                st.session_state.direct_error = f"Failed to convert DOCX file: {str(e)}"
                                os.unlink(temp_file_path)
                                return
                            
                            # Step 2: AI Analysis
                            st.session_state.direct_processing_status = 'analyzing'
                            st.session_state.direct_progress = 50
                            st.session_state.direct_status_message = "🔄 Step 3/4: Running AI compliance analysis... (This may take several minutes)"
                            
                            # Run analysis
                            from playbook_manager import get_current_playbook
                            from NDA_Review_chain import StradaComplianceChain
                            
                            playbook_content = get_current_playbook()
                            review_chain = StradaComplianceChain(
                                model=st.session_state.direct_model, 
                                temperature=st.session_state.direct_temperature, 
                                playbook_content=playbook_content
                            )
                            compliance_report, raw_response = review_chain.analyze_nda(converted_path)
                            
                            if not compliance_report:
                                st.session_state.direct_processing_status = 'error'
                                st.session_state.direct_error = "Failed to get analysis results."
                                os.unlink(temp_file_path)
                                os.unlink(converted_path)
                                return
                            
                            # Step 3: Document Generation
                            st.session_state.direct_processing_status = 'generating'
                            st.session_state.direct_progress = 75
                            st.session_state.direct_status_message = "🔄 Step 4/4: Generating tracked changes documents..."
                            
                            # Auto-select all findings
                            high_priority = compliance_report.get('High Priority', [])
                            medium_priority = compliance_report.get('Medium Priority', [])
                            low_priority = compliance_report.get('Low Priority', [])
                            
                            total_issues = len(high_priority) + len(medium_priority) + len(low_priority)
                            
                            if total_issues == 0:
                                st.session_state.direct_processing_status = 'complete_no_issues'
                                st.session_state.direct_progress = 100
                                st.session_state.direct_status_message = "✅ No compliance issues found! Your NDA appears to be fully compliant."
                                os.unlink(temp_file_path)
                                os.unlink(converted_path)
                                return
                            
                            selected_findings = {
                                'High Priority': {str(i): finding for i, finding in enumerate(high_priority)},
                                'Medium Priority': {str(i): finding for i, finding in enumerate(medium_priority)},
                                'Low Priority': {str(i): finding for i, finding in enumerate(low_priority)}
                            }
                            
                            selected_comments = {}
                            for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                                selected_comments[priority] = {}
                                for idx in selected_findings[priority].keys():
                                    selected_comments[priority][idx] = "Auto-selected for direct tracked changes generation"
                            
                            try:
                                from Tracked_changes_tools_clean import (
                                    apply_cleaned_findings_to_docx, 
                                    clean_findings_with_llm, 
                                    flatten_findings, 
                                    select_findings,
                                    CleanedFinding,
                                    replace_cleaned_findings_in_docx,
                                    RawFinding
                                )
                                import tempfile
                                import shutil
                                
                                # Flatten all findings into a single list with proper structure
                                raw_findings = []
                                additional_info_by_id = {}
                                finding_id = 1
                                
                                for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                                    for idx, finding in selected_findings[priority].items():
                                        raw_finding = RawFinding(
                                            id=finding_id,
                                            priority=priority,
                                            section=finding.get('section', ''),
                                            issue=finding.get('issue', ''),
                                            problem=finding.get('problem', ''),
                                            citation=finding.get('citation', ''),
                                            suggested_replacement=finding.get('suggested_replacement', '')
                                        )
                                        raw_findings.append(raw_finding)
                                        
                                        # Store additional comment info by ID
                                        comment = selected_comments.get(priority, {}).get(idx, "")
                                        if comment:
                                            additional_info_by_id[finding_id] = comment
                                        
                                        finding_id += 1
                                
                                # Read the original NDA text for context
                                with open(converted_path, 'r', encoding='utf-8') as f:
                                    nda_text = f.read()
                                
                                # Clean all findings at once
                                try:
                                    cleaned_findings = clean_findings_with_llm(
                                        nda_text,
                                        raw_findings,
                                        additional_info_by_id,
                                        st.session_state.direct_model
                                    )
                                except Exception as e:
                                    # Create basic cleaned findings as fallback
                                    cleaned_findings = []
                                    for raw_finding in raw_findings:
                                        cleaned_finding = CleanedFinding(
                                            id=raw_finding.id,
                                            citation_clean=raw_finding.citation,
                                            suggested_replacement_clean=raw_finding.suggested_replacement
                                        )
                                        cleaned_findings.append(cleaned_finding)
                                
                                # Generate tracked changes document
                                tracked_temp_path = tempfile.mktemp(suffix='_tracked.docx')
                                shutil.copy2(temp_file_path, tracked_temp_path)
                                
                                changes_applied = apply_cleaned_findings_to_docx(
                                    input_docx=tracked_temp_path,
                                    cleaned_findings=cleaned_findings,
                                    output_docx=tracked_temp_path,
                                    author="AI Compliance Reviewer"
                                )
                                
                                # Generate clean edited document  
                                clean_temp_path = tempfile.mktemp(suffix='_clean.docx')
                                shutil.copy2(temp_file_path, clean_temp_path)
                                
                                replace_cleaned_findings_in_docx(
                                    input_docx=clean_temp_path,
                                    cleaned_findings=cleaned_findings,
                                    output_docx=clean_temp_path
                                )
                                
                                # Read the generated documents
                                with open(tracked_temp_path, 'rb') as f:
                                    tracked_docx = f.read()
                                with open(clean_temp_path, 'rb') as f:
                                    clean_docx = f.read()
                                
                                # Clean up temp files
                                os.unlink(tracked_temp_path)
                                os.unlink(clean_temp_path)
                                os.unlink(temp_file_path)
                                os.unlink(converted_path)
                                
                                # Store results in session state
                                st.session_state.direct_tracked_docx = tracked_docx
                                st.session_state.direct_clean_docx = clean_docx
                                st.session_state.direct_generation_results = {
                                    'high_priority': high_priority,
                                    'medium_priority': medium_priority,
                                    'low_priority': low_priority,
                                    'total_issues': total_issues
                                }
                                
                                # Mark as complete
                                st.session_state.direct_processing_status = 'complete'
                                st.session_state.direct_progress = 100
                                st.session_state.direct_status_message = "✅ Analysis and document generation completed successfully!"
                                
                            except Exception as e:
                                st.session_state.direct_processing_status = 'error'
                                st.session_state.direct_error = f"Failed to generate documents: {str(e)}"
                                # Clean up any temp files
                                try:
                                    os.unlink(temp_file_path)
                                    os.unlink(converted_path)
                                except:
                                    pass
                        
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed during processing: {str(e)}"
                    
                    # Start the background thread
                    import threading
                    thread = threading.Thread(target=background_processing, daemon=True)
                    thread.start()
                    st.rerun()
        
        # Display processing status and results
        st.markdown("---")
        st.subheader("🚀 Direct Tracked Changes Generation")
        
        # Show progress bar and status
        if st.session_state.direct_processing_status in ['preparing', 'converting', 'analyzing', 'generating']:
            progress_container = st.empty()
            status_container = st.empty()
            
            with progress_container.container():
                progress_bar = st.progress(st.session_state.get('direct_progress', 0))
                
            with status_container:
                st.info(st.session_state.get('direct_status_message', 'Processing...'))
            
            # Auto-refresh every 2 seconds during processing
            import time
            time.sleep(2)
            st.rerun()
        
        # Show completion status
        elif st.session_state.direct_processing_status == 'complete':
            st.success("✅ Analysis and document generation completed successfully!")
            
            # Display results
            results = st.session_state.direct_generation_results
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("High Priority", len(results['high_priority']))
            with col2:
                st.metric("Medium Priority", len(results['medium_priority']))
            with col3:
                st.metric("Low Priority", len(results['low_priority']))
            
            st.markdown("---")
            st.subheader("Download Generated Documents")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download Tracked Changes Document",
                    data=st.session_state.direct_tracked_docx,
                    file_name=f"NDA_TrackedChanges_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_tracked"
                )
            
            with col2:
                st.download_button(
                    label="Download Clean Edited Document",
                    data=st.session_state.direct_clean_docx,
                    file_name=f"NDA_CleanEdited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_clean"
                )
            
            # Show what was processed
            with st.expander("Issues Processed (Click to expand)"):
                def display_issues(issues, priority_name):
                    if issues:
                        st.write(f"**{priority_name} Issues:**")
                        for i, issue in enumerate(issues):
                            with st.container():
                                st.markdown(f"**{i+1}. {issue.get('issue', 'Compliance Issue')}**")
                                if issue.get('section'):
                                    st.write(f"📍 **Section:** {issue.get('section')}")
                                if issue.get('problem'):
                                    st.write(f"⚠️ **Problem:** {issue.get('problem')}")
                                if issue.get('citation'):
                                    st.write(f"📄 **Citation:** {issue.get('citation')}")
                                if issue.get('suggested_replacement'):
                                    st.write(f"✏️ **Suggested Replacement:** {issue.get('suggested_replacement')}")
                                st.markdown("---")
                
                display_issues(results['high_priority'], "High Priority")
                display_issues(results['medium_priority'], "Medium Priority")
                display_issues(results['low_priority'], "Low Priority")
            
            # Reset button to start over
            if st.button("🔄 Start New Analysis", key="reset_direct"):
                st.session_state.direct_processing_status = 'idle'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = ""
                if hasattr(st.session_state, 'direct_generation_results'):
                    del st.session_state.direct_generation_results
                if hasattr(st.session_state, 'direct_tracked_docx'):
                    del st.session_state.direct_tracked_docx
                if hasattr(st.session_state, 'direct_clean_docx'):
                    del st.session_state.direct_clean_docx
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'complete_no_issues':
            st.success("✅ No compliance issues found! Your NDA appears to be fully compliant.")
            
            # Reset button
            if st.button("🔄 Analyze Another Document", key="reset_direct_no_issues"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'error':
            st.error(f"❌ Processing failed: {st.session_state.get('direct_error', 'Unknown error')}")
            with st.expander("Error Details"):
                st.code(st.session_state.get('direct_error', 'Unknown error'))
            
            # Reset button
            if st.button("🔄 Try Again", key="reset_direct_error"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
    
    # Legacy code section - this will be disabled with elif False:
    elif False:
        # Initialize session state for async processing
        if 'direct_processing_status' not in st.session_state:
            st.session_state.direct_processing_status = 'idle'
        if 'direct_progress' not in st.session_state:
            st.session_state.direct_progress = 0
        if 'direct_status_message' not in st.session_state:
            st.session_state.direct_status_message = ""
        
        # Clear any previous direct generation results when starting fresh
        if st.session_state.direct_processing_status == 'idle':
            if hasattr(st.session_state, 'direct_generation_results'):
                del st.session_state.direct_generation_results
            if hasattr(st.session_state, 'direct_tracked_docx'):
                del st.session_state.direct_tracked_docx
            if hasattr(st.session_state, 'direct_clean_docx'):
                del st.session_state.direct_clean_docx
            if hasattr(st.session_state, 'direct_generation_complete'):
                del st.session_state.direct_generation_complete
                
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension != 'docx':
            st.error("Direct tracked changes generation requires a Word document (.docx file).")
            st.info("Please upload a DOCX file or use the 'Review NDA First' option for other file types.")
        else:
            # Start processing
            if st.session_state.direct_processing_status == 'idle':
                st.session_state.direct_processing_status = 'preparing'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = "🔄 Step 1/4: Preparing document..."
                st.session_state.direct_model = model
                st.session_state.direct_temperature = temperature
                st.session_state.direct_file_content = uploaded_file.getvalue()
                
                # Start background processing
                import threading
                import tempfile
                import os
                import subprocess
                import traceback
                from datetime import datetime
                
                def background_processing():
                    try:
                        # Step 1: Prepare document
                        st.session_state.direct_processing_status = 'converting'
                        st.session_state.direct_progress = 25
                        st.session_state.direct_status_message = "🔄 Step 2/4: Converting document format..."
                        
                        # Write content to temporary file
                        with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as temp_file:
                            temp_file.write(st.session_state.direct_file_content)
                            temp_file_path = temp_file.name
                        
                        # Store original docx content for later Word comparison
                        st.session_state['original_docx_content'] = st.session_state.direct_file_content
                        
                        # Convert DOCX to markdown for analysis
                        try:
                            converted_path = temp_file_path.replace('.docx', '.md')
                            result = subprocess.run([
                                'pandoc', temp_file_path, '-o', converted_path, '--to=markdown'
                            ], capture_output=True, text=True, check=True)
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to convert DOCX file: {str(e)}"
                            os.unlink(temp_file_path)
                            return
                        
                        # Step 2: AI Analysis
                        st.session_state.direct_processing_status = 'analyzing'
                        st.session_state.direct_progress = 50
                        st.session_state.direct_status_message = "🔄 Step 3/4: Running AI compliance analysis... (This may take several minutes)"
                        
                        # Run analysis
                        from playbook_manager import get_current_playbook
                        from NDA_Review_chain import StradaComplianceChain
                        
                        playbook_content = get_current_playbook()
                        review_chain = StradaComplianceChain(
                            model=st.session_state.direct_model, 
                            temperature=st.session_state.direct_temperature, 
                            playbook_content=playbook_content
                        )
                        compliance_report, raw_response = review_chain.analyze_nda(converted_path)
                        
                        if not compliance_report:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = "Failed to get analysis results."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        # Step 3: Document Generation
                        st.session_state.direct_processing_status = 'generating'
                        st.session_state.direct_progress = 75
                        st.session_state.direct_status_message = "🔄 Step 4/4: Generating tracked changes documents..."
                        
                        # Auto-select all findings
                        high_priority = compliance_report.get('High Priority', [])
                        medium_priority = compliance_report.get('Medium Priority', [])
                        low_priority = compliance_report.get('Low Priority', [])
                        
                        total_issues = len(high_priority) + len(medium_priority) + len(low_priority)
                        
                        if total_issues == 0:
                            st.session_state.direct_processing_status = 'complete_no_issues'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ No compliance issues found! Your NDA appears to be fully compliant."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        selected_findings = {
                            'High Priority': {str(i): finding for i, finding in enumerate(high_priority)},
                            'Medium Priority': {str(i): finding for i, finding in enumerate(medium_priority)},
                            'Low Priority': {str(i): finding for i, finding in enumerate(low_priority)}
                        }
                        
                        selected_comments = {}
                        for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                            selected_comments[priority] = {}
                            for idx in selected_findings[priority].keys():
                                selected_comments[priority][idx] = "Auto-selected for direct tracked changes generation"
                        
                        try:
                            from Tracked_changes_tools_clean import (
                                apply_cleaned_findings_to_docx, 
                                clean_findings_with_llm, 
                                flatten_findings, 
                                select_findings,
                                CleanedFinding,
                                replace_cleaned_findings_in_docx,
                                RawFinding
                            )
                            import tempfile
                            import shutil
                            
                            # Flatten all findings into a single list with proper structure
                            raw_findings = []
                            additional_info_by_id = {}
                            finding_id = 1
                            
                            for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                                for idx, finding in selected_findings[priority].items():
                                    raw_finding = RawFinding(
                                        id=finding_id,
                                        priority=priority,
                                        section=finding.get('section', ''),
                                        issue=finding.get('issue', ''),
                                        problem=finding.get('problem', ''),
                                        citation=finding.get('citation', ''),
                                        suggested_replacement=finding.get('suggested_replacement', '')
                                    )
                                    raw_findings.append(raw_finding)
                                    
                                    # Store additional comment info by ID
                                    comment = selected_comments.get(priority, {}).get(idx, "")
                                    if comment:
                                        additional_info_by_id[finding_id] = comment
                                    
                                    finding_id += 1
                            
                            # Read the original NDA text for context
                            with open(converted_path, 'r', encoding='utf-8') as f:
                                nda_text = f.read()
                            
                            # Clean all findings at once
                            try:
                                cleaned_findings = clean_findings_with_llm(
                                    nda_text,
                                    raw_findings,
                                    additional_info_by_id,
                                    st.session_state.direct_model
                                )
                            except Exception as e:
                                # Create basic cleaned findings as fallback
                                cleaned_findings = []
                                for raw_finding in raw_findings:
                                    cleaned_finding = CleanedFinding(
                                        id=raw_finding.id,
                                        citation_clean=raw_finding.citation,
                                        suggested_replacement_clean=raw_finding.suggested_replacement
                                    )
                                    cleaned_findings.append(cleaned_finding)
                            
                            # Generate tracked changes document
                            tracked_temp_path = tempfile.mktemp(suffix='_tracked.docx')
                            shutil.copy2(temp_file_path, tracked_temp_path)
                            
                            changes_applied = apply_cleaned_findings_to_docx(
                                input_docx=tracked_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=tracked_temp_path,
                                author="AI Compliance Reviewer"
                            )
                            
                            # Generate clean edited document  
                            clean_temp_path = tempfile.mktemp(suffix='_clean.docx')
                            shutil.copy2(temp_file_path, clean_temp_path)
                            
                            replace_cleaned_findings_in_docx(
                                input_docx=clean_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=clean_temp_path
                            )
                            
                            # Read the generated documents
                            with open(tracked_temp_path, 'rb') as f:
                                tracked_docx = f.read()
                            with open(clean_temp_path, 'rb') as f:
                                clean_docx = f.read()
                            
                            # Clean up temp files
                            os.unlink(tracked_temp_path)
                            os.unlink(clean_temp_path)
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            
                            # Store results in session state
                            st.session_state.direct_tracked_docx = tracked_docx
                            st.session_state.direct_clean_docx = clean_docx
                            st.session_state.direct_generation_results = {
                                'high_priority': high_priority,
                                'medium_priority': medium_priority,
                                'low_priority': low_priority,
                                'total_issues': total_issues
                            }
                            
                            # Mark as complete
                            st.session_state.direct_processing_status = 'complete'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ Analysis and document generation completed successfully!"
                            
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to generate documents: {str(e)}"
                            # Clean up any temp files
                            try:
                                os.unlink(temp_file_path)
                                os.unlink(converted_path)
                            except:
                                pass
                    
                    except Exception as e:
                        st.session_state.direct_processing_status = 'error'
                        st.session_state.direct_error = f"Failed during processing: {str(e)}"
                
                # Start the background thread
                import threading
                thread = threading.Thread(target=background_processing, daemon=True)
                thread.start()
                st.rerun()
        st.markdown("---")
        st.subheader("🚀 Direct Tracked Changes Generation")
        
        # Show progress bar and status
        if st.session_state.direct_processing_status in ['preparing', 'converting', 'analyzing', 'generating']:
            progress_container = st.empty()
            status_container = st.empty()
            
            with progress_container.container():
                progress_bar = st.progress(st.session_state.get('direct_progress', 0))
                
            with status_container:
                st.info(st.session_state.get('direct_status_message', 'Processing...'))
            
            # Auto-refresh every 2 seconds during processing
            import time
            time.sleep(2)
            st.rerun()
        
        # Show completion status
        elif st.session_state.direct_processing_status == 'complete':
            st.success("✅ Analysis and document generation completed successfully!")
            
            # Display results
            results = st.session_state.direct_generation_results
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("High Priority", len(results['high_priority']))
            with col2:
                st.metric("Medium Priority", len(results['medium_priority']))
            with col3:
                st.metric("Low Priority", len(results['low_priority']))
            
            st.markdown("---")
            st.subheader("Download Generated Documents")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download Tracked Changes Document",
                    data=st.session_state.direct_tracked_docx,
                    file_name=f"NDA_TrackedChanges_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_tracked"
                )
            
            with col2:
                st.download_button(
                    label="Download Clean Edited Document",
                    data=st.session_state.direct_clean_docx,
                    file_name=f"NDA_CleanEdited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_clean"
                )
            
            # Show what was processed
            with st.expander("Issues Processed (Click to expand)"):
                def display_issues(issues, priority_name):
                    if issues:
                        st.write(f"**{priority_name} Issues:**")
                        for i, issue in enumerate(issues):
                            with st.container():
                                st.markdown(f"**{i+1}. {issue.get('issue', 'Compliance Issue')}**")
                                if issue.get('section'):
                                    st.write(f"📍 **Section:** {issue.get('section')}")
                                if issue.get('problem'):
                                    st.write(f"⚠️ **Problem:** {issue.get('problem')}")
                                if issue.get('citation'):
                                    st.write(f"📄 **Citation:** {issue.get('citation')}")
                                if issue.get('suggested_replacement'):
                                    st.write(f"✏️ **Suggested Replacement:** {issue.get('suggested_replacement')}")
                                st.markdown("---")
                
                display_issues(results['high_priority'], "High Priority")
                display_issues(results['medium_priority'], "Medium Priority")
                display_issues(results['low_priority'], "Low Priority")
            
            # Reset button to start over
            if st.button("🔄 Start New Analysis", key="reset_direct"):
                st.session_state.direct_processing_status = 'idle'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = ""
                if hasattr(st.session_state, 'direct_generation_results'):
                    del st.session_state.direct_generation_results
                if hasattr(st.session_state, 'direct_tracked_docx'):
                    del st.session_state.direct_tracked_docx
                if hasattr(st.session_state, 'direct_clean_docx'):
                    del st.session_state.direct_clean_docx
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'complete_no_issues':
            st.success("✅ No compliance issues found! Your NDA appears to be fully compliant.")
            
            # Reset button
            if st.button("🔄 Analyze Another Document", key="reset_direct_no_issues"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'error':
            st.error(f"❌ Processing failed: {st.session_state.get('direct_error', 'Unknown error')}")
            with st.expander("Error Details"):
                st.code(st.session_state.get('direct_error', 'Unknown error'))
            
            # Reset button
            if st.button("🔄 Try Again", key="reset_direct_error"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
    
    # Legacy code section - this will be disabled with elif False:
    elif False:
        # Initialize session state for async processing
        if 'direct_processing_status' not in st.session_state:
            st.session_state.direct_processing_status = 'idle'
        if 'direct_progress' not in st.session_state:
            st.session_state.direct_progress = 0
        if 'direct_status_message' not in st.session_state:
            st.session_state.direct_status_message = ""
        
        # Clear any previous direct generation results when starting fresh
        if st.session_state.direct_processing_status == 'idle':
            if hasattr(st.session_state, 'direct_generation_results'):
                del st.session_state.direct_generation_results
            if hasattr(st.session_state, 'direct_tracked_docx'):
                del st.session_state.direct_tracked_docx
            if hasattr(st.session_state, 'direct_clean_docx'):
                del st.session_state.direct_clean_docx
            if hasattr(st.session_state, 'direct_generation_complete'):
                del st.session_state.direct_generation_complete
                
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension != 'docx':
            st.error("Direct tracked changes generation requires a Word document (.docx file).")
            st.info("Please upload a DOCX file or use the 'Review NDA First' option for other file types.")
        else:
            # Start processing
            if st.session_state.direct_processing_status == 'idle':
                st.session_state.direct_processing_status = 'preparing'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = "🔄 Step 1/4: Preparing document..."
                st.session_state.direct_model = model
                st.session_state.direct_temperature = temperature
                st.session_state.direct_file_content = uploaded_file.getvalue()
                
                # Start background processing
                import threading
                import tempfile
                import os
                import subprocess
                import traceback
                from datetime import datetime
                
                def background_processing():
                    try:
                        # Step 1: Prepare document
                        st.session_state.direct_processing_status = 'converting'
                        st.session_state.direct_progress = 25
                        st.session_state.direct_status_message = "🔄 Step 2/4: Converting document format..."
                        
                        # Write content to temporary file
                        with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as temp_file:
                            temp_file.write(st.session_state.direct_file_content)
                            temp_file_path = temp_file.name
                        
                        # Store original docx content for later Word comparison
                        st.session_state['original_docx_content'] = st.session_state.direct_file_content
                        
                        # Convert DOCX to markdown for analysis
                        try:
                            converted_path = temp_file_path.replace('.docx', '.md')
                            result = subprocess.run([
                                'pandoc', temp_file_path, '-o', converted_path, '--to=markdown'
                            ], capture_output=True, text=True, check=True)
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to convert DOCX file: {str(e)}"
                            os.unlink(temp_file_path)
                            return
                        
                        # Step 2: AI Analysis
                        st.session_state.direct_processing_status = 'analyzing'
                        st.session_state.direct_progress = 50
                        st.session_state.direct_status_message = "🔄 Step 3/4: Running AI compliance analysis... (This may take several minutes)"
                        
                        # Run analysis
                        from playbook_manager import get_current_playbook
                        from NDA_Review_chain import StradaComplianceChain
                        
                        playbook_content = get_current_playbook()
                        review_chain = StradaComplianceChain(
                            model=st.session_state.direct_model, 
                            temperature=st.session_state.direct_temperature, 
                            playbook_content=playbook_content
                        )
                        compliance_report, raw_response = review_chain.analyze_nda(converted_path)
                        
                        if not compliance_report:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = "Failed to get analysis results."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        # Step 3: Document Generation
                        st.session_state.direct_processing_status = 'generating'
                        st.session_state.direct_progress = 75
                        st.session_state.direct_status_message = "🔄 Step 4/4: Generating tracked changes documents..."
                        
                        # Auto-select all findings
                        high_priority = compliance_report.get('High Priority', [])
                        medium_priority = compliance_report.get('Medium Priority', [])
                        low_priority = compliance_report.get('Low Priority', [])
                        
                        total_issues = len(high_priority) + len(medium_priority) + len(low_priority)
                        
                        if total_issues == 0:
                            st.session_state.direct_processing_status = 'complete_no_issues'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ No compliance issues found! Your NDA appears to be fully compliant."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        selected_findings = {
                            'High Priority': {str(i): finding for i, finding in enumerate(high_priority)},
                            'Medium Priority': {str(i): finding for i, finding in enumerate(medium_priority)},
                            'Low Priority': {str(i): finding for i, finding in enumerate(low_priority)}
                        }
                        
                        selected_comments = {}
                        for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                            selected_comments[priority] = {}
                            for idx in selected_findings[priority].keys():
                                selected_comments[priority][idx] = "Auto-selected for direct tracked changes generation"
                        
                        try:
                            from Tracked_changes_tools_clean import (
                                apply_cleaned_findings_to_docx, 
                                clean_findings_with_llm, 
                                flatten_findings, 
                                select_findings,
                                CleanedFinding,
                                replace_cleaned_findings_in_docx,
                                RawFinding
                            )
                            import tempfile
                            import shutil
                            
                            # Flatten all findings into a single list with proper structure
                            raw_findings = []
                            additional_info_by_id = {}
                            finding_id = 1
                            
                            for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                                for idx, finding in selected_findings[priority].items():
                                    raw_finding = RawFinding(
                                        id=finding_id,
                                        priority=priority,
                                        section=finding.get('section', ''),
                                        issue=finding.get('issue', ''),
                                        problem=finding.get('problem', ''),
                                        citation=finding.get('citation', ''),
                                        suggested_replacement=finding.get('suggested_replacement', '')
                                    )
                                    raw_findings.append(raw_finding)
                                    
                                    # Store additional comment info by ID
                                    comment = selected_comments.get(priority, {}).get(idx, "")
                                    if comment:
                                        additional_info_by_id[finding_id] = comment
                                    
                                    finding_id += 1
                            
                            # Read the original NDA text for context
                            with open(converted_path, 'r', encoding='utf-8') as f:
                                nda_text = f.read()
                            
                            # Clean all findings at once
                            try:
                                cleaned_findings = clean_findings_with_llm(
                                    nda_text,
                                    raw_findings,
                                    additional_info_by_id,
                                    st.session_state.direct_model
                                )
                            except Exception as e:
                                # Create basic cleaned findings as fallback
                                cleaned_findings = []
                                for raw_finding in raw_findings:
                                    cleaned_finding = CleanedFinding(
                                        id=raw_finding.id,
                                        citation_clean=raw_finding.citation,
                                        suggested_replacement_clean=raw_finding.suggested_replacement
                                    )
                                    cleaned_findings.append(cleaned_finding)
                            
                            # Generate tracked changes document
                            tracked_temp_path = tempfile.mktemp(suffix='_tracked.docx')
                            shutil.copy2(temp_file_path, tracked_temp_path)
                            
                            changes_applied = apply_cleaned_findings_to_docx(
                                input_docx=tracked_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=tracked_temp_path,
                                author="AI Compliance Reviewer"
                            )
                            
                            # Generate clean edited document  
                            clean_temp_path = tempfile.mktemp(suffix='_clean.docx')
                            shutil.copy2(temp_file_path, clean_temp_path)
                            
                            replace_cleaned_findings_in_docx(
                                input_docx=clean_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=clean_temp_path
                            )
                            
                            # Read the generated documents
                            with open(tracked_temp_path, 'rb') as f:
                                tracked_docx = f.read()
                            with open(clean_temp_path, 'rb') as f:
                                clean_docx = f.read()
                            
                            # Clean up temp files
                            os.unlink(tracked_temp_path)
                            os.unlink(clean_temp_path)
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            
                            # Store results in session state
                            st.session_state.direct_tracked_docx = tracked_docx
                            st.session_state.direct_clean_docx = clean_docx
                            st.session_state.direct_generation_results = {
                                'high_priority': high_priority,
                                'medium_priority': medium_priority,
                                'low_priority': low_priority,
                                'total_issues': total_issues
                            }
                            
                            # Mark as complete
                            st.session_state.direct_processing_status = 'complete'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ Analysis and document generation completed successfully!"
                            
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to generate documents: {str(e)}"
                            # Clean up any temp files
                            try:
                                os.unlink(temp_file_path)
                                os.unlink(converted_path)
                            except:
                                pass
                    
                    except Exception as e:
                        st.session_state.direct_processing_status = 'error'
                        st.session_state.direct_error = f"Failed during processing: {str(e)}"
                
                # Start the background thread
                import threading
                thread = threading.Thread(target=background_processing, daemon=True)
                thread.start()
                st.rerun()
                
                # Auto-select all findings
                high_priority = compliance_report.get('High Priority', [])
        # Display processing status and results
        st.markdown("---")
        st.subheader("🚀 Direct Tracked Changes Generation")
        
        # Show progress bar and status
        if st.session_state.direct_processing_status in ['preparing', 'converting', 'analyzing', 'generating']:
            progress_container = st.empty()
            status_container = st.empty()
            
            with progress_container.container():
                progress_bar = st.progress(st.session_state.get('direct_progress', 0))
                
            with status_container:
                st.info(st.session_state.get('direct_status_message', 'Processing...'))
            
            # Auto-refresh every 2 seconds during processing
            import time
            time.sleep(2)
            st.rerun()
        
        # Show completion status
        elif st.session_state.direct_processing_status == 'complete':
            st.success("✅ Analysis and document generation completed successfully!")
            
            # Display results
            results = st.session_state.direct_generation_results
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("High Priority", len(results['high_priority']))
            with col2:
                st.metric("Medium Priority", len(results['medium_priority']))
            with col3:
                st.metric("Low Priority", len(results['low_priority']))
            
            st.markdown("---")
            st.subheader("Download Generated Documents")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download Tracked Changes Document",
                    data=st.session_state.direct_tracked_docx,
                    file_name=f"NDA_TrackedChanges_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_tracked"
                )
            
            with col2:
                st.download_button(
                    label="Download Clean Edited Document",
                    data=st.session_state.direct_clean_docx,
                    file_name=f"NDA_CleanEdited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_clean"
                )
            
            # Show what was processed
            with st.expander("Issues Processed (Click to expand)"):
                def display_issues(issues, priority_name):
                    if issues:
                        st.write(f"**{priority_name} Issues:**")
                        for i, issue in enumerate(issues):
                            with st.container():
                                st.markdown(f"**{i+1}. {issue.get('issue', 'Compliance Issue')}**")
                                if issue.get('section'):
                                    st.write(f"📍 **Section:** {issue.get('section')}")
                                if issue.get('problem'):
                                    st.write(f"⚠️ **Problem:** {issue.get('problem')}")
                                if issue.get('citation'):
                                    st.write(f"📄 **Citation:** {issue.get('citation')}")
                                if issue.get('suggested_replacement'):
                                    st.write(f"✏️ **Suggested Replacement:** {issue.get('suggested_replacement')}")
                                st.markdown("---")
                
                display_issues(results['high_priority'], "High Priority")
                display_issues(results['medium_priority'], "Medium Priority")
                display_issues(results['low_priority'], "Low Priority")
            
            # Reset button to start over
            if st.button("🔄 Start New Analysis", key="reset_direct"):
                st.session_state.direct_processing_status = 'idle'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = ""
                if hasattr(st.session_state, 'direct_generation_results'):
                    del st.session_state.direct_generation_results
                if hasattr(st.session_state, 'direct_tracked_docx'):
                    del st.session_state.direct_tracked_docx
                if hasattr(st.session_state, 'direct_clean_docx'):
                    del st.session_state.direct_clean_docx
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'complete_no_issues':
            st.success("✅ No compliance issues found! Your NDA appears to be fully compliant.")
            
            # Reset button
            if st.button("🔄 Analyze Another Document", key="reset_direct_no_issues"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'error':
            st.error(f"❌ Processing failed: {st.session_state.get('direct_error', 'Unknown error')}")
            with st.expander("Error Details"):
                st.code(st.session_state.get('direct_error', 'Unknown error'))
            
            # Reset button
            if st.button("🔄 Try Again", key="reset_direct_error"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
    
    # Legacy code section - this will be disabled with elif False:
    elif False:
        # Initialize session state for async processing
        if 'direct_processing_status' not in st.session_state:
            st.session_state.direct_processing_status = 'idle'
        if 'direct_progress' not in st.session_state:
            st.session_state.direct_progress = 0
        if 'direct_status_message' not in st.session_state:
            st.session_state.direct_status_message = ""
        
        # Clear any previous direct generation results when starting fresh
        if st.session_state.direct_processing_status == 'idle':
            if hasattr(st.session_state, 'direct_generation_results'):
                del st.session_state.direct_generation_results
            if hasattr(st.session_state, 'direct_tracked_docx'):
                del st.session_state.direct_tracked_docx
            if hasattr(st.session_state, 'direct_clean_docx'):
                del st.session_state.direct_clean_docx
            if hasattr(st.session_state, 'direct_generation_complete'):
                del st.session_state.direct_generation_complete
                
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension != 'docx':
            st.error("Direct tracked changes generation requires a Word document (.docx file).")
            st.info("Please upload a DOCX file or use the 'Review NDA First' option for other file types.")
        else:
            # Start processing
            if st.session_state.direct_processing_status == 'idle':
                st.session_state.direct_processing_status = 'preparing'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = "🔄 Step 1/4: Preparing document..."
                st.session_state.direct_model = model
                st.session_state.direct_temperature = temperature
                st.session_state.direct_file_content = uploaded_file.getvalue()
                
                # Start background processing
                import threading
                import tempfile
                import os
                import subprocess
                import traceback
                from datetime import datetime
                
                def background_processing():
                    try:
                        # Step 1: Prepare document
                        st.session_state.direct_processing_status = 'converting'
                        st.session_state.direct_progress = 25
                        st.session_state.direct_status_message = "🔄 Step 2/4: Converting document format..."
                        
                        # Write content to temporary file
                        with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as temp_file:
                            temp_file.write(st.session_state.direct_file_content)
                            temp_file_path = temp_file.name
                        
                        # Store original docx content for later Word comparison
                        st.session_state['original_docx_content'] = st.session_state.direct_file_content
                        
                        # Convert DOCX to markdown for analysis
                        try:
                            converted_path = temp_file_path.replace('.docx', '.md')
                            result = subprocess.run([
                                'pandoc', temp_file_path, '-o', converted_path, '--to=markdown'
                            ], capture_output=True, text=True, check=True)
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to convert DOCX file: {str(e)}"
                            os.unlink(temp_file_path)
                            return
                        
                        # Step 2: AI Analysis
                        st.session_state.direct_processing_status = 'analyzing'
                        st.session_state.direct_progress = 50
                        st.session_state.direct_status_message = "🔄 Step 3/4: Running AI compliance analysis... (This may take several minutes)"
                        
                        # Run analysis
                        from playbook_manager import get_current_playbook
                        from NDA_Review_chain import StradaComplianceChain
                        
                        playbook_content = get_current_playbook()
                        review_chain = StradaComplianceChain(
                            model=st.session_state.direct_model, 
                            temperature=st.session_state.direct_temperature, 
                            playbook_content=playbook_content
                        )
                        compliance_report, raw_response = review_chain.analyze_nda(converted_path)
                        
                        if not compliance_report:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = "Failed to get analysis results."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        # Step 3: Document Generation
                        st.session_state.direct_processing_status = 'generating'
                        st.session_state.direct_progress = 75
                        st.session_state.direct_status_message = "🔄 Step 4/4: Generating tracked changes documents..."
                        
                        # Auto-select all findings
                        high_priority = compliance_report.get('High Priority', [])
                        medium_priority = compliance_report.get('Medium Priority', [])
                        low_priority = compliance_report.get('Low Priority', [])
                        
                        total_issues = len(high_priority) + len(medium_priority) + len(low_priority)
                        
                        if total_issues == 0:
                            st.session_state.direct_processing_status = 'complete_no_issues'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ No compliance issues found! Your NDA appears to be fully compliant."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        selected_findings = {
                            'High Priority': {str(i): finding for i, finding in enumerate(high_priority)},
                            'Medium Priority': {str(i): finding for i, finding in enumerate(medium_priority)},
                            'Low Priority': {str(i): finding for i, finding in enumerate(low_priority)}
                        }
                        
                        selected_comments = {}
                        for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                            selected_comments[priority] = {}
                            for idx in selected_findings[priority].keys():
                                selected_comments[priority][idx] = "Auto-selected for direct tracked changes generation"
                        
                        try:
                            from Tracked_changes_tools_clean import (
                                apply_cleaned_findings_to_docx, 
                                clean_findings_with_llm, 
                                flatten_findings, 
                                select_findings,
                                CleanedFinding,
                                replace_cleaned_findings_in_docx,
                                RawFinding
                            )
                            import tempfile
                            import shutil
                            
                            # Flatten all findings into a single list with proper structure
                            raw_findings = []
                            additional_info_by_id = {}
                            finding_id = 1
                            
                            for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                                for idx, finding in selected_findings[priority].items():
                                    raw_finding = RawFinding(
                                        id=finding_id,
                                        priority=priority,
                                        section=finding.get('section', ''),
                                        issue=finding.get('issue', ''),
                                        problem=finding.get('problem', ''),
                                        citation=finding.get('citation', ''),
                                        suggested_replacement=finding.get('suggested_replacement', '')
                                    )
                                    raw_findings.append(raw_finding)
                                    
                                    # Store additional comment info by ID
                                    comment = selected_comments.get(priority, {}).get(idx, "")
                                    if comment:
                                        additional_info_by_id[finding_id] = comment
                                    
                                    finding_id += 1
                            
                            # Read the original NDA text for context
                            with open(converted_path, 'r', encoding='utf-8') as f:
                                nda_text = f.read()
                            
                            # Clean all findings at once
                            try:
                                cleaned_findings = clean_findings_with_llm(
                                    nda_text,
                                    raw_findings,
                                    additional_info_by_id,
                                    st.session_state.direct_model
                                )
                            except Exception as e:
                                # Create basic cleaned findings as fallback
                                cleaned_findings = []
                                for raw_finding in raw_findings:
                                    cleaned_finding = CleanedFinding(
                                        id=raw_finding.id,
                                        citation_clean=raw_finding.citation,
                                        suggested_replacement_clean=raw_finding.suggested_replacement
                                    )
                                    cleaned_findings.append(cleaned_finding)
                            
                            # Generate tracked changes document
                            tracked_temp_path = tempfile.mktemp(suffix='_tracked.docx')
                            shutil.copy2(temp_file_path, tracked_temp_path)
                            
                            changes_applied = apply_cleaned_findings_to_docx(
                                input_docx=tracked_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=tracked_temp_path,
                                author="AI Compliance Reviewer"
                            )
                            
                            # Generate clean edited document  
                            clean_temp_path = tempfile.mktemp(suffix='_clean.docx')
                            shutil.copy2(temp_file_path, clean_temp_path)
                            
                            replace_cleaned_findings_in_docx(
                                input_docx=clean_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=clean_temp_path
                            )
                            
                            # Read the generated documents
                            with open(tracked_temp_path, 'rb') as f:
                                tracked_docx = f.read()
                            with open(clean_temp_path, 'rb') as f:
                                clean_docx = f.read()
                            
                            # Clean up temp files
                            os.unlink(tracked_temp_path)
                            os.unlink(clean_temp_path)
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            
                            # Store results in session state
                            st.session_state.direct_tracked_docx = tracked_docx
                            st.session_state.direct_clean_docx = clean_docx
                            st.session_state.direct_generation_results = {
                                'high_priority': high_priority,
                                'medium_priority': medium_priority,
                                'low_priority': low_priority,
                                'total_issues': total_issues
                            }
                            
                            # Mark as complete
                            st.session_state.direct_processing_status = 'complete'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ Analysis and document generation completed successfully!"
                            
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to generate documents: {str(e)}"
                            # Clean up any temp files
                            try:
                                os.unlink(temp_file_path)
                                os.unlink(converted_path)
                            except:
                                pass
                    
                    except Exception as e:
                        st.session_state.direct_processing_status = 'error'
                        st.session_state.direct_error = f"Failed during processing: {str(e)}"
                
                # Start the background thread
                import threading
                thread = threading.Thread(target=background_processing, daemon=True)
                thread.start()
                st.rerun()
        st.markdown("---")
        st.subheader("🚀 Direct Tracked Changes Generation")
        
        # Show progress bar and status
        if st.session_state.direct_processing_status in ['preparing', 'converting', 'analyzing', 'generating']:
            progress_container = st.empty()
            status_container = st.empty()
            
            with progress_container.container():
                progress_bar = st.progress(st.session_state.get('direct_progress', 0))
                
            with status_container:
                st.info(st.session_state.get('direct_status_message', 'Processing...'))
            
            # Auto-refresh every 2 seconds during processing
            import time
            time.sleep(2)
            st.rerun()
        
        # Show completion status
        elif st.session_state.direct_processing_status == 'complete':
            st.success("✅ Analysis and document generation completed successfully!")
            
            # Display results
            results = st.session_state.direct_generation_results
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("High Priority", len(results['high_priority']))
            with col2:
                st.metric("Medium Priority", len(results['medium_priority']))
            with col3:
                st.metric("Low Priority", len(results['low_priority']))
            
            st.markdown("---")
            st.subheader("Download Generated Documents")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download Tracked Changes Document",
                    data=st.session_state.direct_tracked_docx,
                    file_name=f"NDA_TrackedChanges_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_tracked"
                )
            
            with col2:
                st.download_button(
                    label="Download Clean Edited Document",
                    data=st.session_state.direct_clean_docx,
                    file_name=f"NDA_CleanEdited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_clean"
                )
            
            # Show what was processed
            with st.expander("Issues Processed (Click to expand)"):
                def display_issues(issues, priority_name):
                    if issues:
                        st.write(f"**{priority_name} Issues:**")
                        for i, issue in enumerate(issues):
                            with st.container():
                                st.markdown(f"**{i+1}. {issue.get('issue', 'Compliance Issue')}**")
                                if issue.get('section'):
                                    st.write(f"📍 **Section:** {issue.get('section')}")
                                if issue.get('problem'):
                                    st.write(f"⚠️ **Problem:** {issue.get('problem')}")
                                if issue.get('citation'):
                                    st.write(f"📄 **Citation:** {issue.get('citation')}")
                                if issue.get('suggested_replacement'):
                                    st.write(f"✏️ **Suggested Replacement:** {issue.get('suggested_replacement')}")
                                st.markdown("---")
                
                display_issues(results['high_priority'], "High Priority")
                display_issues(results['medium_priority'], "Medium Priority")
                display_issues(results['low_priority'], "Low Priority")
            
            # Reset button to start over
            if st.button("🔄 Start New Analysis", key="reset_direct"):
                st.session_state.direct_processing_status = 'idle'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = ""
                if hasattr(st.session_state, 'direct_generation_results'):
                    del st.session_state.direct_generation_results
                if hasattr(st.session_state, 'direct_tracked_docx'):
                    del st.session_state.direct_tracked_docx
                if hasattr(st.session_state, 'direct_clean_docx'):
                    del st.session_state.direct_clean_docx
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'complete_no_issues':
            st.success("✅ No compliance issues found! Your NDA appears to be fully compliant.")
            
            # Reset button
            if st.button("🔄 Analyze Another Document", key="reset_direct_no_issues"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'error':
            st.error(f"❌ Processing failed: {st.session_state.get('direct_error', 'Unknown error')}")
            with st.expander("Error Details"):
                st.code(st.session_state.get('direct_error', 'Unknown error'))
            
            # Reset button
            if st.button("🔄 Try Again", key="reset_direct_error"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
    
    # Legacy code section - this will be disabled with elif False:
    elif False:
        # Initialize session state for async processing
        if 'direct_processing_status' not in st.session_state:
            st.session_state.direct_processing_status = 'idle'
        if 'direct_progress' not in st.session_state:
            st.session_state.direct_progress = 0
        if 'direct_status_message' not in st.session_state:
            st.session_state.direct_status_message = ""
        
        # Clear any previous direct generation results when starting fresh
        if st.session_state.direct_processing_status == 'idle':
            if hasattr(st.session_state, 'direct_generation_results'):
                del st.session_state.direct_generation_results
            if hasattr(st.session_state, 'direct_tracked_docx'):
                del st.session_state.direct_tracked_docx
            if hasattr(st.session_state, 'direct_clean_docx'):
                del st.session_state.direct_clean_docx
            if hasattr(st.session_state, 'direct_generation_complete'):
                del st.session_state.direct_generation_complete
                
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension != 'docx':
            st.error("Direct tracked changes generation requires a Word document (.docx file).")
            st.info("Please upload a DOCX file or use the 'Review NDA First' option for other file types.")
        else:
            # Start processing
            if st.session_state.direct_processing_status == 'idle':
                st.session_state.direct_processing_status = 'preparing'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = "🔄 Step 1/4: Preparing document..."
                st.session_state.direct_model = model
                st.session_state.direct_temperature = temperature
                st.session_state.direct_file_content = uploaded_file.getvalue()
                
                # Start background processing
                import threading
                import tempfile
                import os
                import subprocess
                import traceback
                from datetime import datetime
                
                def background_processing():
                    try:
                        # Step 1: Prepare document
                        st.session_state.direct_processing_status = 'converting'
                        st.session_state.direct_progress = 25
                        st.session_state.direct_status_message = "🔄 Step 2/4: Converting document format..."
                        
                        # Write content to temporary file
                        with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as temp_file:
                            temp_file.write(st.session_state.direct_file_content)
                            temp_file_path = temp_file.name
                        
                        # Store original docx content for later Word comparison
                        st.session_state['original_docx_content'] = st.session_state.direct_file_content
                        
                        # Convert DOCX to markdown for analysis
                        try:
                            converted_path = temp_file_path.replace('.docx', '.md')
                            result = subprocess.run([
                                'pandoc', temp_file_path, '-o', converted_path, '--to=markdown'
                            ], capture_output=True, text=True, check=True)
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to convert DOCX file: {str(e)}"
                            os.unlink(temp_file_path)
                            return
                        
                        # Step 2: AI Analysis
                        st.session_state.direct_processing_status = 'analyzing'
                        st.session_state.direct_progress = 50
                        st.session_state.direct_status_message = "🔄 Step 3/4: Running AI compliance analysis... (This may take several minutes)"
                        
                        # Run analysis
                        from playbook_manager import get_current_playbook
                        from NDA_Review_chain import StradaComplianceChain
                        
                        playbook_content = get_current_playbook()
                        review_chain = StradaComplianceChain(
                            model=st.session_state.direct_model, 
                            temperature=st.session_state.direct_temperature, 
                            playbook_content=playbook_content
                        )
                        compliance_report, raw_response = review_chain.analyze_nda(converted_path)
                        
                        if not compliance_report:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = "Failed to get analysis results."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        # Step 3: Document Generation
                        st.session_state.direct_processing_status = 'generating'
                        st.session_state.direct_progress = 75
                        st.session_state.direct_status_message = "🔄 Step 4/4: Generating tracked changes documents..."
                        
                        # Auto-select all findings
                        high_priority = compliance_report.get('High Priority', [])
                        medium_priority = compliance_report.get('Medium Priority', [])
                        low_priority = compliance_report.get('Low Priority', [])
                        
                        total_issues = len(high_priority) + len(medium_priority) + len(low_priority)
                        
                        if total_issues == 0:
                            st.session_state.direct_processing_status = 'complete_no_issues'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ No compliance issues found! Your NDA appears to be fully compliant."
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            return
                        
                        selected_findings = {
                            'High Priority': {str(i): finding for i, finding in enumerate(high_priority)},
                            'Medium Priority': {str(i): finding for i, finding in enumerate(medium_priority)},
                            'Low Priority': {str(i): finding for i, finding in enumerate(low_priority)}
                        }
                        
                        selected_comments = {}
                        for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                            selected_comments[priority] = {}
                            for idx in selected_findings[priority].keys():
                                selected_comments[priority][idx] = "Auto-selected for direct tracked changes generation"
                        
                        try:
                            from Tracked_changes_tools_clean import (
                                apply_cleaned_findings_to_docx, 
                                clean_findings_with_llm, 
                                flatten_findings, 
                                select_findings,
                                CleanedFinding,
                                replace_cleaned_findings_in_docx,
                                RawFinding
                            )
                            import tempfile
                            import shutil
                            
                            # Flatten all findings into a single list with proper structure
                            raw_findings = []
                            additional_info_by_id = {}
                            finding_id = 1
                            
                            for priority in ['High Priority', 'Medium Priority', 'Low Priority']:
                                for idx, finding in selected_findings[priority].items():
                                    raw_finding = RawFinding(
                                        id=finding_id,
                                        priority=priority,
                                        section=finding.get('section', ''),
                                        issue=finding.get('issue', ''),
                                        problem=finding.get('problem', ''),
                                        citation=finding.get('citation', ''),
                                        suggested_replacement=finding.get('suggested_replacement', '')
                                    )
                                    raw_findings.append(raw_finding)
                                    
                                    # Store additional comment info by ID
                                    comment = selected_comments.get(priority, {}).get(idx, "")
                                    if comment:
                                        additional_info_by_id[finding_id] = comment
                                    
                                    finding_id += 1
                            
                            # Read the original NDA text for context
                            with open(converted_path, 'r', encoding='utf-8') as f:
                                nda_text = f.read()
                            
                            # Clean all findings at once
                            try:
                                cleaned_findings = clean_findings_with_llm(
                                    nda_text,
                                    raw_findings,
                                    additional_info_by_id,
                                    st.session_state.direct_model
                                )
                            except Exception as e:
                                # Create basic cleaned findings as fallback
                                cleaned_findings = []
                                for raw_finding in raw_findings:
                                    cleaned_finding = CleanedFinding(
                                        id=raw_finding.id,
                                        citation_clean=raw_finding.citation,
                                        suggested_replacement_clean=raw_finding.suggested_replacement
                                    )
                                    cleaned_findings.append(cleaned_finding)
                            
                            # Generate tracked changes document
                            tracked_temp_path = tempfile.mktemp(suffix='_tracked.docx')
                            shutil.copy2(temp_file_path, tracked_temp_path)
                            
                            changes_applied = apply_cleaned_findings_to_docx(
                                input_docx=tracked_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=tracked_temp_path,
                                author="AI Compliance Reviewer"
                            )
                            
                            # Generate clean edited document  
                            clean_temp_path = tempfile.mktemp(suffix='_clean.docx')
                            shutil.copy2(temp_file_path, clean_temp_path)
                            
                            replace_cleaned_findings_in_docx(
                                input_docx=clean_temp_path,
                                cleaned_findings=cleaned_findings,
                                output_docx=clean_temp_path
                            )
                            
                            # Read the generated documents
                            with open(tracked_temp_path, 'rb') as f:
                                tracked_docx = f.read()
                            with open(clean_temp_path, 'rb') as f:
                                clean_docx = f.read()
                            
                            # Clean up temp files
                            os.unlink(tracked_temp_path)
                            os.unlink(clean_temp_path)
                            os.unlink(temp_file_path)
                            os.unlink(converted_path)
                            
                            # Store results in session state
                            st.session_state.direct_tracked_docx = tracked_docx
                            st.session_state.direct_clean_docx = clean_docx
                            st.session_state.direct_generation_results = {
                                'high_priority': high_priority,
                                'medium_priority': medium_priority,
                                'low_priority': low_priority,
                                'total_issues': total_issues
                            }
                            
                            # Mark as complete
                            st.session_state.direct_processing_status = 'complete'
                            st.session_state.direct_progress = 100
                            st.session_state.direct_status_message = "✅ Analysis and document generation completed successfully!"
                            
                        except Exception as e:
                            st.session_state.direct_processing_status = 'error'
                            st.session_state.direct_error = f"Failed to generate documents: {str(e)}"
                            # Clean up any temp files
                            try:
                                os.unlink(temp_file_path)
                                os.unlink(converted_path)
                            except:
                                pass
                    
                    except Exception as e:
                        st.session_state.direct_processing_status = 'error'
                        st.session_state.direct_error = f"Failed during processing: {str(e)}"
                
                # Start the background thread
                import threading
                thread = threading.Thread(target=background_processing, daemon=True)
                thread.start()
                st.rerun()
        
        # Display processing status and results
        st.markdown("---")
        st.subheader("🚀 Direct Tracked Changes Generation")
        
        # Show progress bar and status
        if st.session_state.direct_processing_status in ['preparing', 'converting', 'analyzing', 'generating']:
            progress_container = st.empty()
            status_container = st.empty()
            
            with progress_container.container():
                progress_bar = st.progress(st.session_state.get('direct_progress', 0))
                
            with status_container:
                st.info(st.session_state.get('direct_status_message', 'Processing...'))
            
            # Auto-refresh every 2 seconds during processing
            import time
            time.sleep(2)
            st.rerun()
        
        # Show completion status
        elif st.session_state.direct_processing_status == 'complete':
            st.success("✅ Analysis and document generation completed successfully!")
            
            # Display results
            results = st.session_state.direct_generation_results
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("High Priority", len(results['high_priority']))
            with col2:
                st.metric("Medium Priority", len(results['medium_priority']))
            with col3:
                st.metric("Low Priority", len(results['low_priority']))
            
            st.markdown("---")
            st.subheader("Download Generated Documents")
            
            col1, col2 = st.columns(2)
            with col1:
                from datetime import datetime
                st.download_button(
                    label="Download Tracked Changes Document",
                    data=st.session_state.direct_tracked_docx,
                    file_name=f"NDA_TrackedChanges_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_tracked"
                )
            
            with col2:
                st.download_button(
                    label="Download Clean Edited Document",
                    data=st.session_state.direct_clean_docx,
                    file_name=f"NDA_CleanEdited_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_direct_clean"
                )
            
            # Reset button to start over
            if st.button("🔄 Start New Analysis", key="reset_direct"):
                st.session_state.direct_processing_status = 'idle'
                st.session_state.direct_progress = 0
                st.session_state.direct_status_message = ""
                if hasattr(st.session_state, 'direct_generation_results'):
                    del st.session_state.direct_generation_results
                if hasattr(st.session_state, 'direct_tracked_docx'):
                    del st.session_state.direct_tracked_docx
                if hasattr(st.session_state, 'direct_clean_docx'):
                    del st.session_state.direct_clean_docx
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'complete_no_issues':
            st.success("✅ No compliance issues found! Your NDA appears to be fully compliant.")
            
            # Reset button
            if st.button("🔄 Analyze Another Document", key="reset_direct_no_issues"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()
        
        elif st.session_state.direct_processing_status == 'error':
            st.error(f"❌ Processing failed: {st.session_state.get('direct_error', 'Unknown error')}")
            with st.expander("Error Details"):
                st.code(st.session_state.get('direct_error', 'Unknown error'))
            
            # Reset button
            if st.button("🔄 Try Again", key="reset_direct_error"):
                st.session_state.direct_processing_status = 'idle'
                st.rerun()

def display_nda_review_page():
    """Display the main NDA Review page"""
    st.title("🔍 NDA Compliance Review")
    st.write("Upload an NDA document for AI-powered compliance analysis.")
