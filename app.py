import streamlit as st
import tempfile
import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import traceback
from typing import Dict, List, Tuple, Optional

# Import the analysis modules
from Clean_testing import TestingChain
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
            'temperature': 0.1,
            'analysis_mode': 'Full Analysis'
        }

def display_header():
    """Display the application header"""
    st.title("⚖️ NDA Analysis Comparison Tool")
    st.markdown("""
    This tool compares AI-generated NDA reviews against HR corrections to evaluate AI performance in legal document analysis.
    Upload your clean NDA and HR-corrected version to get started.
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
        accuracy = (metrics['correctly_identified'] / max(metrics['ai_total_issues'], 1)) * 100
        st.metric(
            "AI Accuracy",
            f"{accuracy:.1f}%",
            help="Percentage of AI-flagged issues that were addressed by HR"
        )
    
    # Create comparison chart
    if metrics['ai_total_issues'] > 0 or metrics['hr_total_changes'] > 0:
        fig = create_comparison_chart(metrics)
        st.plotly_chart(fig, use_container_width=True)

def display_detailed_comparison(comparison_analysis):
    """Display detailed comparison results"""
    st.header("🔍 Detailed Comparison")
    
    if not comparison_analysis or comparison_analysis.strip() == "":
        st.warning("No comparison analysis data available.")
        return
    
    # Parse the comparison analysis
    formatted_results = format_analysis_results(comparison_analysis)
    
    # Check if parsing found any structured data
    has_structured_data = any(len(items) > 0 for items in formatted_results.values())
    
    if has_structured_data:
        # Display structured results
        for category, items in formatted_results.items():
            if items:
                if category == "correctly_identified":
                    st.subheader("✅ Issues Correctly Identified by AI")
                    color = "green"
                elif category == "missed_by_ai":
                    st.subheader("❌ Issues Missed by AI")
                    color = "red"
                elif category == "not_addressed_by_hr":
                    st.subheader("⚠️ Issues Flagged by AI but Not Addressed by HR")
                    color = "orange"
                
                for idx, item in enumerate(items):
                    with st.expander(f"{item['title']}", expanded=False):
                        st.markdown(f"**Analysis:** {item['analysis']}")
                        if item.get('section'):
                            st.markdown(f"**Section:** {item['section']}")
    else:
        # Fallback: Display raw comparison analysis with better formatting
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
        st.download_button(
            label="📄 Download Comparison Analysis",
            data=comparison_analysis,
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

def main():
    """Main application function"""
    initialize_session_state()
    display_header()
    
    # Sidebar configuration
    model, temperature, analysis_mode = display_sidebar()
    
    # File upload section
    clean_file, corrected_file = display_file_upload_section()
    
    # Analysis section
    st.header("🔬 Analysis Configuration")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(f"**Model:** {model} | **Temperature:** {temperature} | **Mode:** {analysis_mode}")
    
    with col2:
        run_analysis_button = st.button(
            "🚀 Run Analysis",
            disabled=not (clean_file and corrected_file),
            use_container_width=True
        )
    
    # Run analysis when button is clicked
    if run_analysis_button and clean_file and corrected_file:
        with st.spinner("Running analysis... This may take a few minutes."):
            comparison_analysis, ai_review_data, hr_edits_data = run_analysis(
                clean_file, corrected_file, model, temperature, analysis_mode
            )
            
            if comparison_analysis:
                # Store results in session state
                st.session_state.analysis_results = comparison_analysis
                st.session_state.ai_review_data = ai_review_data
                st.session_state.hr_edits_data = hr_edits_data
                
                st.success("🎉 Analysis completed successfully!")
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

if __name__ == "__main__":
    main()
