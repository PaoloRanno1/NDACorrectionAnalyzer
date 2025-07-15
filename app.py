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

# Import the analysis modules
from Clean_testing import TestingChain
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

def initialize_session_state():
    """Initialize session state variables"""
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

def display_sidebar():
    """Display sidebar with configuration options"""
    st.sidebar.header("⚙️ Configuration")
    
    # Model selection
    model_options = ["gemini-2.5-pro", "gemini-2.5-flash"]
    selected_model = st.sidebar.selectbox(
        "Select AI Model",
        model_options,
        index=model_options.index(st.session_state.analysis_config['model'])
    )
    
    # Temperature slider
    temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.analysis_config['temperature'],
        step=0.1,
        help="Lower values make the AI more focused and deterministic"
    )
    
    # Analysis mode
    analysis_modes = ["Full Analysis", "Quick Testing"]
    analysis_mode = st.sidebar.selectbox(
        "Analysis Mode",
        analysis_modes,
        index=analysis_modes.index(st.session_state.analysis_config['analysis_mode'])
    )
    
    # Update session state
    st.session_state.analysis_config.update({
        'model': selected_model,
        'temperature': temperature,
        'analysis_mode': analysis_mode
    })
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Supported Formats")
    st.sidebar.markdown("- Markdown (.md)")
    st.sidebar.markdown("- Text (.txt)")
    st.sidebar.markdown("- PDF (.pdf)")
    st.sidebar.markdown("- Word (.docx)")
    
    return selected_model, temperature, analysis_mode

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

def run_analysis(clean_file, corrected_file, model, temperature, analysis_mode):
    """Run the NDA analysis"""
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=f".{clean_file.name.split('.')[-1]}") as clean_temp:
            clean_temp.write(clean_file.getvalue())
            clean_temp_path = clean_temp.name
        
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=f".{corrected_file.name.split('.')[-1]}") as corrected_temp:
            corrected_temp.write(corrected_file.getvalue())
            corrected_temp_path = corrected_temp.name
        
        # Get current playbook content
        from playbook_manager import get_current_playbook
        playbook_content = get_current_playbook()
        
        # Initialize testing chain
        test_chain = TestingChain(model=model, temperature=temperature, playbook_content=playbook_content)
        
        # Create progress placeholder
        progress_placeholder = st.empty()
        
        if analysis_mode == "Full Analysis":
            # Run full analysis
            progress_placeholder.info("🔄 Running AI review on clean NDA...")
            comparison_analysis, comparison_response, ai_review_data, hr_edits_data = test_chain.analyze_testing(
                clean_temp_path, corrected_temp_path
            )
        else:
            # Quick testing mode - would need pre-generated JSON
            st.error("Quick Testing mode requires pre-generated JSON data. Please use Full Analysis mode.")
            return None, None, None
        
        progress_placeholder.success("✅ Analysis completed successfully!")
        
        # Clean up temporary files
        os.unlink(clean_temp_path)
        os.unlink(corrected_temp_path)
        
        return comparison_analysis, ai_review_data, hr_edits_data
        
    except Exception as e:
        st.error(f"❌ Analysis failed: {str(e)}")
        st.error("Please check your API key and try again.")
        st.expander("Error Details").write(traceback.format_exc())
        return None, None, None

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
    st.subheader("📊 Detailed Comparison Tables")
    
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
    st.header("🔍 Detailed Comparison")
    
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
    """Display clean NDA review section"""
    st.header("⚖️ Clean NDA Review")
    st.info("Upload a clean NDA document to get AI compliance analysis based on Strada's policies.")
    
    # File upload
    st.subheader("📄 Upload NDA Document")
    uploaded_file = st.file_uploader(
        "Choose an NDA file",
        type=['pdf', 'docx', 'txt', 'md'],
        help="Upload the NDA document you want to analyze",
        key="single_nda_upload"
    )
    
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
    
    # Review configuration
    st.subheader("🔧 Review Configuration")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(f"**Model:** {model} | **Temperature:** {temperature}")
        st.caption("Model settings are controlled from the sidebar")
    
    with col2:
        run_single_analysis = st.button(
            "🚀 Review NDA",
            disabled=not uploaded_file,
            use_container_width=True,
            key="run_single_analysis"
        )
    
    # Run review
    if run_single_analysis and uploaded_file:
        with st.spinner("Reviewing NDA... This may take a minute."):
            try:
                # Import the NDA Review chain
                from NDA_Review_chain import StradaComplianceChain
                
                file_extension = uploaded_file.name.split('.')[-1].lower()
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=f".{file_extension}") as temp_file:
                    temp_file.write(uploaded_file.getvalue())
                    temp_file_path = temp_file.name
                
                # Convert DOCX to markdown using Pandoc if needed
                if file_extension == 'docx':
                    markdown_temp_path = temp_file_path.replace('.docx', '.md')
                    try:
                        # Use Pandoc to convert DOCX to markdown
                        result = subprocess.run([
                            'pandoc', 
                            temp_file_path, 
                            '-o', 
                            markdown_temp_path,
                            '--wrap=none'  # Prevent line wrapping
                        ], capture_output=True, text=True, check=True)
                        
                        # Clean up original DOCX file and use markdown file
                        os.unlink(temp_file_path)
                        temp_file_path = markdown_temp_path
                        
                        st.info("✅ DOCX file converted to markdown for analysis")
                        
                    except subprocess.CalledProcessError as e:
                        st.error(f"❌ Failed to convert DOCX file: {e}")
                        os.unlink(temp_file_path)
                        return
                    except FileNotFoundError:
                        st.error("❌ Pandoc not found. Please install Pandoc to process DOCX files.")
                        os.unlink(temp_file_path)
                        return
                
                # Get current playbook content
                from playbook_manager import get_current_playbook
                playbook_content = get_current_playbook()
                
                # Initialize and run analysis
                review_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook_content)
                compliance_report, raw_response = review_chain.analyze_nda(temp_file_path)
                
                # Clean up temporary file
                os.unlink(temp_file_path)
                
                # Store results in session state
                st.session_state.single_nda_results = compliance_report
                st.session_state.single_nda_raw = raw_response
                
                st.success("✅ Review completed successfully!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Review failed: {str(e)}")
                st.error("Please check your API key and try again.")
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())
    
    # Display results if available
    if hasattr(st.session_state, 'single_nda_results') and st.session_state.single_nda_results:
        st.markdown("---")
        
        # Results summary
        st.subheader("📊 Review Summary")
        compliance_report = st.session_state.single_nda_results
        
        if compliance_report:
            high_priority = compliance_report.get('High Priority', [])
            medium_priority = compliance_report.get('Medium Priority', [])
            low_priority = compliance_report.get('Low Priority', [])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🔴 High Priority (Mandatory)", len(high_priority))
            with col2:
                st.metric("🟡 Medium Priority (Preferential)", len(medium_priority))
            with col3:
                st.metric("🟢 Low Priority (Optional)", len(low_priority))
        
        st.markdown("---")
        
        # Detailed results
        st.subheader("🔍 Detailed Review Results")
        
        # High priority issues
        if high_priority:
            st.subheader("🔴 High Priority Issues (Mandatory Changes Required)")
            for idx, flag in enumerate(high_priority):
                with st.expander(f"High Priority {idx + 1}: {flag.get('issue', 'Compliance Issue')}", expanded=False):
                    st.markdown(f"**Section:** {flag.get('section', 'Not specified')}")
                    st.markdown(f"**Citation:** {flag.get('citation', 'Not provided')}")
                    st.markdown(f"**Problem:** {flag.get('problem', 'Not specified')}")
                    if flag.get('suggested_replacement'):
                        st.markdown(f"**Suggested Replacement:** {flag.get('suggested_replacement')}")
        else:
            st.success("✅ No high priority issues found!")
        
        # Medium priority issues
        if medium_priority:
            st.subheader("🟡 Medium Priority Issues (Preferential Changes)")
            for idx, flag in enumerate(medium_priority):
                with st.expander(f"Medium Priority {idx + 1}: {flag.get('issue', 'Compliance Issue')}", expanded=False):
                    st.markdown(f"**Section:** {flag.get('section', 'Not specified')}")
                    st.markdown(f"**Citation:** {flag.get('citation', 'Not provided')}")
                    st.markdown(f"**Problem:** {flag.get('problem', 'Not specified')}")
                    if flag.get('suggested_replacement'):
                        st.markdown(f"**Suggested Replacement:** {flag.get('suggested_replacement')}")
        else:
            st.success("✅ No medium priority issues found!")
        
        # Low priority issues
        if low_priority:
            st.subheader("🟢 Low Priority Issues (Optional Changes)")
            for idx, flag in enumerate(low_priority):
                with st.expander(f"Low Priority {idx + 1}: {flag.get('issue', 'Compliance Issue')}", expanded=False):
                    st.markdown(f"**Section:** {flag.get('section', 'Not specified')}")
                    st.markdown(f"**Citation:** {flag.get('citation', 'Not provided')}")
                    st.markdown(f"**Problem:** {flag.get('problem', 'Not specified')}")
                    if flag.get('suggested_replacement'):
                        st.markdown(f"**Suggested Replacement:** {flag.get('suggested_replacement')}")
        else:
            st.success("✅ No low priority issues found!")
        
        st.markdown("---")
        
        # Export options
        st.subheader("📥 Export Results")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📊 Download JSON Report",
                data=json.dumps(compliance_report, indent=2),
                file_name=f"nda_compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with col2:
            # Create summary text
            summary_text = f"""NDA Compliance Review Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY:
- High Priority (Mandatory): {len(high_priority)}
- Medium Priority (Preferential): {len(medium_priority)}
- Low Priority (Optional): {len(low_priority)}
- Total Issues: {len(high_priority) + len(medium_priority) + len(low_priority)}

HIGH PRIORITY:
"""
            for idx, flag in enumerate(high_priority):
                summary_text += f"\n{idx + 1}. {flag.get('issue', 'Issue')}\n   Section: {flag.get('section', 'N/A')}\n   Problem: {flag.get('problem', 'N/A')}\n"
            
            summary_text += "\nMEDIUM PRIORITY:\n"
            for idx, flag in enumerate(medium_priority):
                summary_text += f"\n{idx + 1}. {flag.get('issue', 'Issue')}\n   Section: {flag.get('section', 'N/A')}\n   Problem: {flag.get('problem', 'N/A')}\n"
            
            summary_text += "\nLOW PRIORITY:\n"
            for idx, flag in enumerate(low_priority):
                summary_text += f"\n{idx + 1}. {flag.get('issue', 'Issue')}\n   Section: {flag.get('section', 'N/A')}\n   Problem: {flag.get('problem', 'N/A')}\n"
            
            st.download_button(
                label="📄 Download Text Summary",
                data=summary_text,
                file_name=f"nda_review_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
        
        st.markdown("---")
        
        # JSON Data Viewer
        st.subheader("📋 JSON Data Viewer")
        
        tab1, tab2 = st.tabs(["📊 Analysis Results", "🔍 Raw Response"])
        
        with tab1:
            st.subheader("Analysis Results JSON")
            if compliance_report:
                st.json(compliance_report)
            else:
                st.info("No analysis results available")
        
        with tab2:
            st.subheader("Raw AI Response")
            if hasattr(st.session_state, 'single_nda_raw') and st.session_state.single_nda_raw:
                st.text_area(
                    "Raw Response from AI Model",
                    st.session_state.single_nda_raw,
                    height=300,
                    disabled=True
                )
            else:
                st.info("No raw response available")
        
        st.markdown("---")
        
        # Clear results
        if st.button("🗑️ Clear Results", key="clear_single_results"):
            if hasattr(st.session_state, 'single_nda_results'):
                delattr(st.session_state, 'single_nda_results')
            if hasattr(st.session_state, 'single_nda_raw'):
                delattr(st.session_state, 'single_nda_raw')
            st.rerun()

def display_homepage():
    """Display the homepage with functionality descriptions"""
    st.title("🏠 NDA Analysis Platform")
    
    st.markdown("""
    Welcome to the comprehensive NDA Analysis Platform! This application helps evaluate AI performance 
    in legal document analysis and provides powerful tools for NDA compliance review.
    """)
    
    st.markdown("---")
    
    # Feature cards
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🔬 NDA Testing
        Compare AI-generated NDA reviews against HR corrections to assess accuracy and coverage.
        
        **Key Features:**
        - Upload original and HR-corrected NDA documents
        - Get detailed comparison analysis with accuracy metrics
        - View structured tables showing correctly identified issues, missed flags, and false positives
        - Export results as JSON or text summaries
        """)
        
        if st.button("🔬 Go to NDA Testing", key="nav_testing", use_container_width=True):
            st.session_state.current_page = "testing"
            st.rerun()
    
    with col2:
        st.markdown("""
        ### 📊 Testing Results
        View and manage saved testing results from previous NDA analyses.
        
        **Key Features:**
        - Browse saved test results by project name and date
        - View executive summary charts and detailed comparisons
        - Export results data and manage saved analyses
        - Track AI performance across multiple tests
        """)
        
        if st.button("📊 Go to Testing Results", key="nav_results", use_container_width=True):
            st.session_state.current_page = "results"
            st.rerun()
    
    st.markdown("---")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("""
        ### 📋 Policies Playbook
        Browse and reference the complete NDA compliance policies.
        
        **Key Features:**
        - Browse all 14 NDA policies organized by High, Medium, and Low priority categories
        - Filter policies by type for quick reference
        - Expandable sections with detailed policy descriptions and approved language
        """)
        
        if st.button("📋 Go to Policies Playbook", key="nav_policies", use_container_width=True):
            st.session_state.current_page = "policies"
            st.rerun()
    
    with col4:
        st.markdown("""
        ### ✏️ Edit Playbook
        Customize and modify the NDA analysis policies used by both analysis chains.
        
        **Key Features:**
        - Edit and modify the playbook content used by both analysis chains
        - Preview changes before saving
        - Reset to default policies when needed
        - Real-time application to all future analyses
        """)
        
        if st.button("✏️ Go to Edit Playbook", key="nav_edit", use_container_width=True):
            st.session_state.current_page = "edit"
            st.rerun()
    
    st.markdown("---")
    
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown("""
        ### ⚖️ Clean NDA Review
        Analyze individual NDA documents for compliance issues.
        
        **Key Features:**
        - Upload individual NDA documents for analysis
        - Get detailed compliance reports with priority-based categorization
        - View JSON output and raw AI responses
        - Export results in multiple formats
        """)
        
        if st.button("⚖️ Go to Clean NDA Review", key="nav_clean", use_container_width=True):
            st.session_state.current_page = "clean"
            st.rerun()
    
    st.markdown("---")
    
    # Additional info
    st.markdown("""
    ### 🔧 Configuration
    Use the sidebar to configure:
    - **AI Model**: Choose between Gemini 2.5 Flash or Pro
    - **Temperature**: Control response creativity (0.0 - 1.0)
    - **Analysis Mode**: Select Full Analysis or Quick Testing
    
    ### 📊 About the Priority System
    - **🔴 High Priority (Policies 1-5)**: Mandatory changes required
    - **🟡 Medium Priority (Policies 6-10)**: Preferential changes
    - **🟢 Low Priority (Policies 11-14)**: Optional changes
    """)

def display_navigation():
    """Display navigation bar"""
    st.markdown("---")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        if st.button("🏠 Home", key="nav_home", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()
    
    with col2:
        if st.button("🔬 Testing", key="nav_testing_top", use_container_width=True):
            st.session_state.current_page = "testing"
            st.rerun()
    
    with col3:
        if st.button("📊 Results", key="nav_results_top", use_container_width=True):
            st.session_state.current_page = "results"
            st.rerun()
    
    with col4:
        if st.button("📋 Policies", key="nav_policies_top", use_container_width=True):
            st.session_state.current_page = "policies"
            st.rerun()
    
    with col5:
        if st.button("✏️ Edit", key="nav_edit_top", use_container_width=True):
            st.session_state.current_page = "edit"
            st.rerun()
    
    with col6:
        if st.button("⚖️ Review", key="nav_clean_top", use_container_width=True):
            st.session_state.current_page = "clean"
            st.rerun()

def display_testing_page(model, temperature, analysis_mode):
    """Display the NDA testing page"""
    st.header("🔬 NDA Testing")
    
    # File upload section
    clean_file, corrected_file = display_file_upload_section()
    
    # Analysis section
    st.header("🔬 Testing Configuration")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(f"**Model:** {model} | **Temperature:** {temperature} | **Mode:** {analysis_mode}")
    
    with col2:
        run_analysis_button = st.button(
            "🚀 Run Testing",
            disabled=not (clean_file and corrected_file),
            use_container_width=True
        )
    
    # Run testing when button is clicked
    if run_analysis_button and clean_file and corrected_file:
        with st.spinner("Running testing... This may take a few minutes."):
            comparison_analysis, ai_review_data, hr_edits_data = run_analysis(
                clean_file, corrected_file, model, temperature, analysis_mode
            )
            
            if comparison_analysis:
                # Store results in session state
                st.session_state.analysis_results = comparison_analysis
                st.session_state.ai_review_data = ai_review_data
                st.session_state.hr_edits_data = hr_edits_data
                
                st.success("🎉 Testing completed successfully!")
                st.rerun()
    
    # Display results if available
    if st.session_state.analysis_results:
        st.markdown("---")
        
        # Executive Summary
        display_executive_summary(
            st.session_state.analysis_results,
            st.session_state.ai_review_data,
            st.session_state.hr_edits_data
        )
        
        st.markdown("---")
        
        # Detailed Comparison Tables
        display_detailed_comparison_tables(
            st.session_state.analysis_results,
            st.session_state.ai_review_data,
            st.session_state.hr_edits_data
        )
        
        # Detailed Comparison
        display_detailed_comparison(st.session_state.analysis_results)
        
        st.markdown("---")
        
        # JSON Viewers
        display_json_viewers(
            st.session_state.ai_review_data,
            st.session_state.hr_edits_data,
            st.session_state.analysis_results
        )
        
        st.markdown("---")
        
        # Raw Data Export
        display_raw_data_export(
            st.session_state.analysis_results,
            st.session_state.ai_review_data,
            st.session_state.hr_edits_data
        )
        
        st.markdown("---")
        
        # Save Results Section
        st.subheader("💾 Save Testing Results")
        st.write("Save this analysis for future reference and comparison.")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Get NDA name from file or test selection
            nda_name = "Custom NDA"
            if hasattr(st.session_state, 'selected_test_nda') and st.session_state.selected_test_nda:
                nda_name = st.session_state.selected_test_nda
            elif clean_file and hasattr(clean_file, 'name'):
                nda_name = clean_file.name.replace('.md', '').replace('.txt', '').replace('.pdf', '').replace('.docx', '')
            
            custom_name = st.text_input("Result Name:", value=nda_name, help="Enter a name for this test result")
        
        with col2:
            if st.button("💾 Save Results", key="save_results", use_container_width=True):
                if custom_name:
                    from results_manager import save_testing_results
                    from utils import create_comparison_chart, extract_detailed_metrics_from_analysis
                    
                    # Generate the executive summary chart
                    metrics = extract_detailed_metrics_from_analysis(
                        st.session_state.analysis_results,
                        st.session_state.ai_review_data,
                        st.session_state.hr_edits_data
                    )
                    executive_summary_fig = create_comparison_chart(metrics)
                    
                    # Save the results
                    result_id = save_testing_results(
                        nda_name=custom_name,
                        comparison_analysis=st.session_state.analysis_results,
                        ai_review_data=st.session_state.ai_review_data,
                        hr_edits_data=st.session_state.hr_edits_data,
                        executive_summary_fig=executive_summary_fig,
                        model_used=model,
                        temperature=temperature,
                        analysis_mode=analysis_mode
                    )
                    
                    st.success(f"✅ Results saved successfully! ID: {result_id}")
                    st.info("You can view saved results in the 'Results' tab.")
                else:
                    st.error("Please enter a name for the results.")
        
        st.markdown("---")
        
        # Clear results option
        if st.button("🗑️ Clear Results", key="clear_results"):
            st.session_state.analysis_results = None
            st.session_state.ai_review_data = None
            st.session_state.hr_edits_data = None
            st.rerun()

def display_testing_results_page():
    """Display the testing results page with saved results"""
    st.title("📊 Testing Results")
    
    import json
    import os
    import pandas as pd
    from results_manager import get_saved_results, get_results_summary, load_saved_result, delete_saved_result, get_detailed_analytics
    
    # Get saved results and detailed analytics
    saved_results = get_saved_results()
    results_summary = get_results_summary()
    detailed_analytics = get_detailed_analytics()
    
    if not saved_results:
        st.info("No saved results found. Run some tests and save the results to see them here.")
        return
    
    # Display summary statistics
    st.subheader("📈 Summary Statistics")
    
    # Calculate totals for the metrics
    total_ai_issues = sum(len(issues) for issues in detailed_analytics["ai_issues"].values())
    total_hr_edits = sum(len(edits) for edits in detailed_analytics["hr_edits"].values())
    total_missed = sum(len(missed) for missed in detailed_analytics["missed_by_ai"].values())
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Unique NDAs", results_summary["total_ndas"])
    
    with col2:
        st.metric("Total AI Issues Flagged", total_ai_issues)
    
    with col3:
        st.metric("Total HR Edits", total_hr_edits)
    
    with col4:
        st.metric("Total Issues Missed", total_missed)
    
    st.markdown("---")
    
    # Detailed Analytics Dashboard (only latest result per project)
    st.subheader("🔍 Detailed Analytics Dashboard")
    st.caption("Based on the most recent test result for each unique NDA project")
    
    if detailed_analytics["total_projects"] > 0:
        # Overall accuracy metrics
        st.subheader("🎯 Overall Performance Metrics")
        metrics = detailed_analytics["accuracy_metrics"]
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Overall Accuracy", f"{metrics['overall_accuracy']}%")
        with col2:
            st.metric("Precision", f"{metrics['precision']}%")
        with col3:
            st.metric("Recall", f"{metrics['recall']}%")
        with col4:
            st.metric("Total Projects", detailed_analytics["total_projects"])
        with col5:
            st.metric("Issues Missed", metrics["total_missed"])
        
        # Expandable sections for detailed breakdowns
        with st.expander("🤖 AI Issues Flagged by Priority", expanded=False):
            ai_issues = detailed_analytics["ai_issues"]
            
            # Count summary
            total_ai = sum(len(issues) for issues in ai_issues.values())
            high_count = len(ai_issues["high"])
            medium_count = len(ai_issues["medium"])
            low_count = len(ai_issues["low"])
            
            st.markdown(f"**📊 Total AI Issues Flagged: {total_ai}** (🔴 {high_count} High, 🟡 {medium_count} Medium, 🟢 {low_count} Low)")
            st.markdown("---")
            
            # Group issues by project for cleaner display
            def group_issues_by_project(issues_list):
                project_groups = {}
                for issue in issues_list:
                    project = issue['project']
                    if project not in project_groups:
                        project_groups[project] = []
                    project_groups[project].append(issue)
                return project_groups

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**🔴 High Priority Issues**")
                if ai_issues["high"]:
                    high_projects = group_issues_by_project(ai_issues["high"])
                    for project, issues in high_projects.items():
                        with st.expander(f"{project} ({len(issues)} issues)"):
                            for issue in issues:
                                st.markdown(f"**• {issue['issue'][:80]}...**")
                                st.write(f"  Section: {issue['section']}")
                                st.write(f"  Citation: {issue['citation'][:150]}...")
                                st.write("---")
                else:
                    st.info("No high priority issues flagged")
            
            with col2:
                st.markdown("**🟡 Medium Priority Issues**")
                if ai_issues["medium"]:
                    medium_projects = group_issues_by_project(ai_issues["medium"])
                    for project, issues in medium_projects.items():
                        with st.expander(f"{project} ({len(issues)} issues)"):
                            for issue in issues:
                                st.markdown(f"**• {issue['issue'][:80]}...**")
                                st.write(f"  Section: {issue['section']}")
                                st.write(f"  Citation: {issue['citation'][:150]}...")
                                st.write("---")
                else:
                    st.info("No medium priority issues flagged")
            
            with col3:
                st.markdown("**🟢 Low Priority Issues**")
                if ai_issues["low"]:
                    low_projects = group_issues_by_project(ai_issues["low"])
                    for project, issues in low_projects.items():
                        with st.expander(f"{project} ({len(issues)} issues)"):
                            for issue in issues:
                                st.markdown(f"**• {issue['issue'][:80]}...**")
                                st.write(f"  Section: {issue['section']}")
                                st.write(f"  Citation: {issue['citation'][:150]}...")
                                st.write("---")
                else:
                    st.info("No low priority issues flagged")
        
        with st.expander("👥 HR Edits Made by Priority", expanded=False):
            hr_edits = detailed_analytics["hr_edits"]
            
            # Count summary
            total_hr = sum(len(edits) for edits in hr_edits.values())
            hr_high_count = len(hr_edits["high"])
            hr_medium_count = len(hr_edits["medium"])
            hr_low_count = len(hr_edits["low"])
            
            st.markdown(f"**📊 Total HR Edits Made: {total_hr}** (🔴 {hr_high_count} High, 🟡 {hr_medium_count} Medium, 🟢 {hr_low_count} Low)")
            st.markdown("---")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**🔴 High Priority HR Edits**")
                if hr_edits["high"]:
                    high_hr_projects = group_issues_by_project(hr_edits["high"])
                    for project, edits in high_hr_projects.items():
                        with st.expander(f"{project} ({len(edits)} edits)"):
                            for edit in edits:
                                st.markdown(f"**• {edit['issue'][:80]}...**")
                                st.write(f"  Section: {edit['section']}")
                                st.write(f"  Change Type: {edit['change_type']}")
                                st.write("---")
                else:
                    st.info("No high priority HR edits")
            
            with col2:
                st.markdown("**🟡 Medium Priority HR Edits**")
                if hr_edits["medium"]:
                    medium_hr_projects = group_issues_by_project(hr_edits["medium"])
                    for project, edits in medium_hr_projects.items():
                        with st.expander(f"{project} ({len(edits)} edits)"):
                            for edit in edits:
                                st.markdown(f"**• {edit['issue'][:80]}...**")
                                st.write(f"  Section: {edit['section']}")
                                st.write(f"  Change Type: {edit['change_type']}")
                                st.write("---")
                else:
                    st.info("No medium priority HR edits")
            
            with col3:
                st.markdown("**🟢 Low Priority HR Edits**")
                if hr_edits["low"]:
                    low_hr_projects = group_issues_by_project(hr_edits["low"])
                    for project, edits in low_hr_projects.items():
                        with st.expander(f"{project} ({len(edits)} edits)"):
                            for edit in edits:
                                st.markdown(f"**• {edit['issue'][:80]}...**")
                                st.write(f"  Section: {edit['section']}")
                                st.write(f"  Change Type: {edit['change_type']}")
                                st.write("---")
                else:
                    st.info("No low priority HR edits")
        
        with st.expander("❌ Issues Missed by AI", expanded=False):
            missed_issues = detailed_analytics["missed_by_ai"]
            
            # Count summary
            total_missed = sum(len(missed) for missed in missed_issues.values())
            missed_high_count = len(missed_issues["high"])
            missed_medium_count = len(missed_issues["medium"])
            missed_low_count = len(missed_issues["low"])
            
            st.markdown(f"**📊 Total Issues Missed by AI: {total_missed}** (🔴 {missed_high_count} High, 🟡 {missed_medium_count} Medium, 🟢 {missed_low_count} Low)")
            st.markdown("---")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**🔴 High Priority Missed**")
                if missed_issues["high"]:
                    high_missed_projects = group_issues_by_project(missed_issues["high"])
                    for project, missed in high_missed_projects.items():
                        with st.expander(f"{project} ({len(missed)} missed)"):
                            for issue in missed:
                                st.markdown(f"**• {issue['issue'][:80]}...**")
                                st.write(f"  Section: {issue['section']}")
                                st.write("---")
                else:
                    st.success("No high priority issues missed!")
            
            with col2:
                st.markdown("**🟡 Medium Priority Missed**")
                if missed_issues["medium"]:
                    medium_missed_projects = group_issues_by_project(missed_issues["medium"])
                    for project, missed in medium_missed_projects.items():
                        with st.expander(f"{project} ({len(missed)} missed)"):
                            for issue in missed:
                                st.markdown(f"**• {issue['issue'][:80]}...**")
                                st.write(f"  Section: {issue['section']}")
                                st.write("---")
                else:
                    st.success("No medium priority issues missed!")
            
            with col3:
                st.markdown("**🟢 Low Priority Missed**")
                if missed_issues["low"]:
                    low_missed_projects = group_issues_by_project(missed_issues["low"])
                    for project, missed in low_missed_projects.items():
                        with st.expander(f"{project} ({len(missed)} missed)"):
                            for issue in missed:
                                st.markdown(f"**• {issue['issue'][:80]}...**")
                                st.write(f"  Section: {issue['section']}")
                                st.write("---")
                else:
                    st.success("No low priority issues missed!")
        
        with st.expander("⚠️ False Positives (AI Flagged but HR Didn't Address)", expanded=False):
            false_positives = detailed_analytics["false_positives"]
            
            # Count summary
            total_fp = sum(len(fp) for fp in false_positives.values())
            fp_high_count = len(false_positives["high"])
            fp_medium_count = len(false_positives["medium"])
            fp_low_count = len(false_positives["low"])
            
            st.markdown(f"**📊 Total False Positives: {total_fp}** (🔴 {fp_high_count} High, 🟡 {fp_medium_count} Medium, 🟢 {fp_low_count} Low)")
            st.markdown("---")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**🔴 High Priority False Positives**")
                if false_positives["high"]:
                    high_fp_projects = group_issues_by_project(false_positives["high"])
                    for project, fps in high_fp_projects.items():
                        with st.expander(f"{project} ({len(fps)} false positives)"):
                            for fp in fps:
                                st.markdown(f"**• {fp['issue'][:80]}...**")
                                st.write(f"  Section: {fp['section']}")
                                st.write("---")
                else:
                    st.success("No high priority false positives!")
            
            with col2:
                st.markdown("**🟡 Medium Priority False Positives**")
                if false_positives["medium"]:
                    medium_fp_projects = group_issues_by_project(false_positives["medium"])
                    for project, fps in medium_fp_projects.items():
                        with st.expander(f"{project} ({len(fps)} false positives)"):
                            for fp in fps:
                                st.markdown(f"**• {fp['issue'][:80]}...**")
                                st.write(f"  Section: {fp['section']}")
                                st.write("---")
                else:
                    st.success("No medium priority false positives!")
            
            with col3:
                st.markdown("**🟢 Low Priority False Positives**")
                if false_positives["low"]:
                    low_fp_projects = group_issues_by_project(false_positives["low"])
                    for project, fps in low_fp_projects.items():
                        with st.expander(f"{project} ({len(fps)} false positives)"):
                            for fp in fps:
                                st.markdown(f"**• {fp['issue'][:80]}...**")
                                st.write(f"  Section: {fp['section']}")
                                st.write("---")
                else:
                    st.success("No low priority false positives!")
        
        # Project Breakdown Table
        st.subheader("📋 Project Performance Breakdown")
        if detailed_analytics["project_breakdown"]:
            df = pd.DataFrame(detailed_analytics["project_breakdown"])
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
            
            # Reorder columns for better display
            column_order = ["project", "accuracy", "ai_total", "hr_total", "missed_total", 
                          "false_positives_total", "model_used", "timestamp"]
            df = df[column_order]
            
            # Format the dataframe for display
            df["accuracy"] = df["accuracy"].round(1).astype(str) + "%"
            df.columns = ["Project", "Accuracy", "AI Issues", "HR Edits", "Missed", "False Positives", "Model", "Date"]
            
            st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    
    # Results selection and display
    st.subheader("📋 Saved Results")
    
    # Create dropdown with project names
    result_options = []
    for result in saved_results:
        timestamp = result.get("timestamp", "")
        if timestamp:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = timestamp[:16]
        else:
            formatted_date = "Unknown"
        
        option_text = f"{result['nda_name']} - {formatted_date} ({result['model_used']})"
        result_options.append(option_text)
    
    selected_result_index = st.selectbox(
        "Select a result to view:",
        range(len(result_options)),
        format_func=lambda x: result_options[x] if x < len(result_options) else "",
        help="Choose a saved result to view detailed analysis"
    )
    
    if selected_result_index is not None and selected_result_index < len(saved_results):
        selected_result = saved_results[selected_result_index]
        result_id = selected_result["result_id"]
        
        # Display result metadata
        st.subheader(f"📄 {selected_result['nda_name']}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"**Model:** {selected_result['model_used']}")
            st.info(f"**Temperature:** {selected_result['temperature']}")
        
        with col2:
            st.info(f"**Analysis Mode:** {selected_result['analysis_mode']}")
            st.info(f"**Date:** {selected_result['timestamp'][:16]}")
        
        with col3:
            st.info(f"**AI Issues:** {selected_result['ai_issues_count']}")
            st.info(f"**HR Edits:** {selected_result['hr_edits_count']}")
        
        st.markdown("---")
        
        # Load and display the saved result
        loaded_result = load_saved_result(result_id)
        
        if loaded_result:
            comparison_analysis, ai_review_data, hr_edits_data, executive_summary_fig = loaded_result
            
            # Display executive summary
            st.subheader("📊 Executive Summary")
            st.plotly_chart(executive_summary_fig, use_container_width=True)
            
            st.markdown("---")
            
            # Display detailed comparison tables
            st.subheader("📋 Detailed Comparison Tables")
            display_detailed_comparison_tables(comparison_analysis, ai_review_data, hr_edits_data)
            
            st.markdown("---")
            
            # Display detailed comparison
            st.subheader("🔍 Detailed Analysis")
            display_detailed_comparison(comparison_analysis)
            
            st.markdown("---")
            
            # JSON viewers
            st.subheader("📋 JSON Data")
            display_json_viewers(ai_review_data, hr_edits_data, comparison_analysis)
            
            st.markdown("---")
            
            # Export and delete options
            col1, col2 = st.columns(2)
            
            with col1:
                # Export button
                export_data = {
                    "metadata": selected_result,
                    "comparison_analysis": comparison_analysis,
                    "ai_review_data": ai_review_data,
                    "hr_edits_data": hr_edits_data
                }
                
                st.download_button(
                    label="📥 Download Result Data",
                    data=json.dumps(export_data, indent=2),
                    file_name=f"nda_result_{result_id}.json",
                    mime="application/json"
                )
            
            with col2:
                # Delete button
                if st.button("🗑️ Delete Result", key=f"delete_{result_id}"):
                    if delete_saved_result(result_id):
                        st.success("Result deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to delete result.")
        else:
            st.error("Failed to load the selected result.")
    
    st.markdown("---")
    
    # Bulk operations
    st.subheader("🔧 Bulk Operations")
    
    if st.button("🗑️ Clear All Results", key="clear_all_results"):
        st.warning("This action cannot be undone!")
        if st.button("⚠️ Confirm Delete All", key="confirm_delete_all"):
            import shutil
            if os.path.exists("saved_results"):
                shutil.rmtree("saved_results")
                st.success("All results cleared!")
                st.rerun()

def main():
    """Main application function"""
    initialize_session_state()
    
    # Initialize current page if not set
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "home"
    
    # Check authentication
    if not st.session_state.authenticated:
        display_login_screen()
        return
    
    display_header()
    
    # Sidebar configuration
    model, temperature, analysis_mode = display_sidebar()
    
    # Navigation
    display_navigation()
    
    # Page routing
    if st.session_state.current_page == "home":
        display_homepage()
    elif st.session_state.current_page == "testing":
        display_testing_page(model, temperature, analysis_mode)
    elif st.session_state.current_page == "results":
        display_testing_results_page()
    elif st.session_state.current_page == "policies":
        display_policies_playbook()
    elif st.session_state.current_page == "edit":
        from playbook_manager import display_editable_playbook
        display_editable_playbook()
    elif st.session_state.current_page == "clean":
        display_single_nda_review(model, temperature)

if __name__ == "__main__":
    main()
