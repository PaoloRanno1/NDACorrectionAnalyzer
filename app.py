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
            'model': 'gemini-2.5-flash',
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
        st.title("⚖️ NDA Analysis Comparison Tool")
    with col2:
        if st.button("Logout", type="secondary"):
            st.session_state.authenticated = False
            st.rerun()
    
    st.markdown("""
    This tool compares AI-generated NDA reviews against HR corrections to evaluate AI 
    performance in legal document analysis. Upload your clean NDA and HR-corrected 
    version to get started.
    
    ### 📋 Application Features
    
    **🔬 NDA Testing Tab**: Compare AI performance against HR edits
    - Upload a clean NDA document and an HR-corrected version
    - Get detailed comparison analysis with accuracy metrics
    - View structured tables showing correctly identified issues, missed flags, and false positives
    - Export results as JSON or text summaries
    
    **📋 Policies Playbook Tab**: Reference NDA compliance policies
    - Browse all 14 NDA policies organized by Red Flag (mandatory) and Yellow Flag (preferential) categories
    - Filter policies by type for quick reference
    - Expandable sections with detailed policy descriptions and approved language
    
    **⚖️ Clean NDA Review Tab**: Analyze individual NDA documents
    - Upload any single NDA document for AI compliance analysis
    - Get structured red flag and yellow flag issues with descriptions
    - Export compliance reports in multiple formats
    
    ### 📄 File Format Requirements
    
    **Clean NDA File**: Upload the original, unmodified NDA document (PDF, DOCX, TXT, or MD format)
    
    **Corrected NDA File**: Upload the HR-edited version with tracked changes using these markers:
    - `++text++` for additions made by HR
    - `--text--` for deletions made by HR
    
    Example: `Information may be made available to ++directors and++ employees within your organisation`
    """)

def display_sidebar():
    """Display sidebar with configuration options"""
    st.sidebar.header("⚙️ Configuration")
    
    # Model selection
    model_options = ["gemini-2.5-flash", "gemini-2.5-pro"]
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
    """Display file upload section"""
    st.header("📁 File Upload Section")
    
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
                st.info(f"File size: {len(clean_file.getvalue())} bytes")
                
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
                st.info(f"File size: {len(corrected_file.getvalue())} bytes")
                
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
        
        # Initialize testing chain
        test_chain = TestingChain(model=model, temperature=temperature)
        
        # Create progress placeholder
        progress_placeholder = st.empty()
        
        if analysis_mode == "Full Analysis":
            # Run full analysis
            progress_placeholder.info("🔄 Running AI review on clean NDA...")
            comparison_analysis, ai_review_data, hr_edits_data = test_chain.analyze_testing(
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
    
    # Extract metrics
    metrics = extract_metrics_from_analysis(comparison_analysis, ai_review_data, hr_edits_data)
    
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
    """Display detailed comparison tables as requested"""
    st.subheader("📊 Detailed Comparison Tables")
    
    # Import pandas for this function
    import pandas as pd
    
    # Extract detailed data for tables
    from utils import extract_detailed_comparison_data
    table_data = extract_detailed_comparison_data(comparison_analysis, ai_review_data, hr_edits_data)
    
    # Custom CSS for better table styling
    st.markdown("""
    <style>
    .comparison-table {
        border: 1px solid #ddd;
        border-radius: 8px;
        overflow: hidden;
        margin: 10px 0;
    }
    .table-header {
        background-color: #4a90e2;
        color: white;
        padding: 12px;
        font-weight: bold;
        text-align: center;
        border-bottom: 2px solid #357abd;
    }
    .table-cell {
        padding: 10px;
        border-bottom: 1px solid #eee;
        vertical-align: top;
    }
    .table-row:nth-child(even) {
        background-color: #f9f9f9;
    }
    .table-row:nth-child(odd) {
        background-color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create three columns for the tables
    col1, col2 = st.columns(2)
    
    # Table 1: AI Correctly Identified flags
    with col1:
        st.markdown("### 🟢 AI Correctly Identified Flags")
        correctly_identified = table_data['correctly_identified']
        
        if correctly_identified:
            # Prepare data with proper text wrapping
            table_data_clean = []
            for item in correctly_identified:
                flag_text = item['flag'][:100] + "..." if len(item['flag']) > 100 else item['flag']
                desc_text = item['description'][:200] + "..." if len(item['description']) > 200 else item['description']
                table_data_clean.append({
                    'AI Correctly Identified flags': flag_text,
                    'Description of the flag': desc_text
                })
            
            table_df1 = pd.DataFrame(table_data_clean)
            st.dataframe(
                table_df1, 
                use_container_width=True, 
                hide_index=True,
                height=300,
                column_config={
                    "AI Correctly Identified flags": st.column_config.TextColumn(
                        "AI Correctly Identified flags",
                        width="medium",
                    ),
                    "Description of the flag": st.column_config.TextColumn(
                        "Description of the flag",
                        width="large",
                    )
                }
            )
        else:
            # Show empty table structure with better styling
            empty_df1 = pd.DataFrame({
                'AI Correctly Identified flags': ['No issues correctly identified'], 
                'Description of the flag': ['No matching issues found between AI and HR reviews']
            })
            st.dataframe(empty_df1, use_container_width=True, hide_index=True, height=100)
    
    # Table 2: Missed Flags by the AI
    with col2:
        st.markdown("### 🔴 Missed Flags by the AI")
        missed_flags = table_data['missed_flags']
        
        if missed_flags:
            # Prepare data with proper text wrapping
            table_data_clean = []
            for item in missed_flags:
                flag_text = item['flag'][:100] + "..." if len(item['flag']) > 100 else item['flag']
                desc_text = item['description'][:200] + "..." if len(item['description']) > 200 else item['description']
                table_data_clean.append({
                    'Missed Flags by the AI': flag_text,
                    'Description of the flag': desc_text
                })
            
            table_df2 = pd.DataFrame(table_data_clean)
            st.dataframe(
                table_df2, 
                use_container_width=True, 
                hide_index=True,
                height=300,
                column_config={
                    "Missed Flags by the AI": st.column_config.TextColumn(
                        "Missed Flags by the AI",
                        width="medium",
                    ),
                    "Description of the flag": st.column_config.TextColumn(
                        "Description of the flag",
                        width="large",
                    )
                }
            )
        else:
            # Show empty table structure
            empty_df2 = pd.DataFrame({
                'Missed Flags by the AI': ['No issues missed'], 
                'Description of the flag': ['AI successfully identified all relevant issues']
            })
            st.dataframe(empty_df2, use_container_width=True, hide_index=True, height=100)
    
    # Table 3: Flagged by AI but not addressed by HR (full width)
    st.markdown("### 🟡 Flagged by AI but not addressed by HR")
    false_positives = table_data['false_positives']
    
    if false_positives:
        # Prepare data with proper text wrapping
        table_data_clean = []
        for item in false_positives:
            flag_text = item['flag'][:120] + "..." if len(item['flag']) > 120 else item['flag']
            desc_text = item['description'][:300] + "..." if len(item['description']) > 300 else item['description']
            table_data_clean.append({
                'Flagged by AI but not addressed by HR': flag_text,
                'Description of the flag': desc_text
            })
        
        table_df3 = pd.DataFrame(table_data_clean)
        st.dataframe(
            table_df3, 
            use_container_width=True, 
            hide_index=True,
            height=300,
            column_config={
                "Flagged by AI but not addressed by HR": st.column_config.TextColumn(
                    "Flagged by AI but not addressed by HR",
                    width="medium",
                ),
                "Description of the flag": st.column_config.TextColumn(
                    "Description of the flag",
                    width="large",
                )
            }
        )
    else:
        # Show empty table structure
        empty_df3 = pd.DataFrame({
            'Flagged by AI but not addressed by HR': ['No additional flags'], 
            'Description of the flag': ['All AI-flagged issues were appropriately addressed by HR']
        })
        st.dataframe(empty_df3, use_container_width=True, hide_index=True, height=100)
    
    st.markdown("---")

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
            # Display structured JSON results
            categories = [
                ("correctly_identified", "✅ Issues Correctly Identified by AI", "green"),
                ("missed_by_ai", "❌ Issues Missed by AI", "red"), 
                ("not_addressed_by_hr", "⚠️ Issues Flagged by AI but Not Addressed by HR", "orange")
            ]
            
            for category_key, title, color in categories:
                items = comparison_analysis.get(category_key, [])
                if items:
                    st.subheader(title)
                    for idx, item in enumerate(items):
                        with st.expander(f"{item.get('issue', f'Issue {idx+1}')}", expanded=False):
                            st.markdown(f"**Analysis:** {item.get('analysis', 'No analysis provided')}")
                elif category_key == "correctly_identified":
                    st.subheader(title)
                    st.info("No issues were correctly identified by the AI.")
                elif category_key == "missed_by_ai":
                    st.subheader(title)
                    st.info("The AI did not miss any issues that HR addressed.")
                elif category_key == "not_addressed_by_hr":
                    st.subheader(title)
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

def display_json_viewers(ai_review_data, hr_edits_data):
    """Display JSON data viewers"""
    st.header("📋 Analysis Data")
    
    tab1, tab2 = st.tabs(["AI Review Results", "HR Edits Analysis"])
    
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
            st.info(f"File size: {len(uploaded_file.getvalue())} bytes")
            
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
                
                # Initialize and run analysis
                review_chain = StradaComplianceChain(model=model, temperature=temperature)
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
            red_flags = compliance_report.get('red_flags', [])
            yellow_flags = compliance_report.get('yellow_flags', [])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🔴 Red Flags (Mandatory)", len(red_flags))
            with col2:
                st.metric("🟡 Yellow Flags (Preferential)", len(yellow_flags))
            with col3:
                st.metric("📋 Total Issues", len(red_flags) + len(yellow_flags))
        
        st.markdown("---")
        
        # Detailed results
        st.subheader("🔍 Detailed Review Results")
        
        # Red flags
        if red_flags:
            st.subheader("🔴 Red Flags (Mandatory Changes Required)")
            for idx, flag in enumerate(red_flags):
                with st.expander(f"Red Flag {idx + 1}: {flag.get('issue', 'Compliance Issue')}", expanded=False):
                    st.markdown(f"**Section:** {flag.get('section', 'Not specified')}")
                    st.markdown(f"**Citation:** {flag.get('citation', 'Not provided')}")
                    st.markdown(f"**Problem:** {flag.get('problem', 'Not specified')}")
                    if flag.get('suggested_replacement'):
                        st.markdown(f"**Suggested Replacement:** {flag.get('suggested_replacement')}")
        else:
            st.success("✅ No red flag issues found!")
        
        # Yellow flags
        if yellow_flags:
            st.subheader("🟡 Yellow Flags (Preferential Changes)")
            for idx, flag in enumerate(yellow_flags):
                with st.expander(f"Yellow Flag {idx + 1}: {flag.get('issue', 'Compliance Issue')}", expanded=False):
                    st.markdown(f"**Section:** {flag.get('section', 'Not specified')}")
                    st.markdown(f"**Citation:** {flag.get('citation', 'Not provided')}")
                    st.markdown(f"**Problem:** {flag.get('problem', 'Not specified')}")
                    if flag.get('suggested_replacement'):
                        st.markdown(f"**Suggested Replacement:** {flag.get('suggested_replacement')}")
        else:
            st.success("✅ No yellow flag issues found!")
        
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
- Red Flags (Mandatory): {len(red_flags)}
- Yellow Flags (Preferential): {len(yellow_flags)}
- Total Issues: {len(red_flags) + len(yellow_flags)}

RED FLAGS:
"""
            for idx, flag in enumerate(red_flags):
                summary_text += f"\n{idx + 1}. {flag.get('issue', 'Issue')}\n   Section: {flag.get('section', 'N/A')}\n   Problem: {flag.get('problem', 'N/A')}\n"
            
            summary_text += "\nYELLOW FLAGS:\n"
            for idx, flag in enumerate(yellow_flags):
                summary_text += f"\n{idx + 1}. {flag.get('issue', 'Issue')}\n   Section: {flag.get('section', 'N/A')}\n   Problem: {flag.get('problem', 'N/A')}\n"
            
            st.download_button(
                label="📄 Download Text Summary",
                data=summary_text,
                file_name=f"nda_review_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
        
        # Clear results
        if st.button("🗑️ Clear Results", key="clear_single_results"):
            if hasattr(st.session_state, 'single_nda_results'):
                delattr(st.session_state, 'single_nda_results')
            if hasattr(st.session_state, 'single_nda_raw'):
                delattr(st.session_state, 'single_nda_raw')
            st.rerun()

def main():
    """Main application function"""
    initialize_session_state()
    
    # Check authentication
    if not st.session_state.authenticated:
        display_login_screen()
        return
    
    display_header()
    
    # Sidebar configuration
    model, temperature, analysis_mode = display_sidebar()
    
    # Create main tabs
    tab1, tab2, tab3 = st.tabs(["🔬 NDA Testing", "📋 Policies Playbook", "⚖️ Clean NDA Review"])
    
    with tab1:
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
                st.session_state.hr_edits_data
            )
            
            st.markdown("---")
            
            # Raw Data Export
            display_raw_data_export(
                st.session_state.analysis_results,
                st.session_state.ai_review_data,
                st.session_state.hr_edits_data
            )
            
            # Clear results option
            if st.button("🗑️ Clear Results", key="clear_results"):
                st.session_state.analysis_results = None
                st.session_state.ai_review_data = None
                st.session_state.hr_edits_data = None
                st.rerun()
    
    with tab2:
        # Policies Playbook tab
        display_policies_playbook()
    
    with tab3:
        # Clean NDA Review tab
        display_single_nda_review(model, temperature)

if __name__ == "__main__":
    main()
