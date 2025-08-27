import asyncio
import streamlit as st
import tempfile
import os
from typing import Optional, Dict, Any
import threading
import time
import uuid

def run_direct_changes_background(analysis_id: str, file_content: bytes, file_name: str, selected_findings: Dict, user_comments: Dict):
    """Run direct tracked changes generation in background thread"""
    try:
        # Update status
        st.session_state.direct_processing_status = 'processing'
        st.session_state.direct_processing_progress = 10
        st.session_state.direct_processing_message = 'Initializing document processing...'
        
        # Import here to avoid circular imports
        from Tracked_changes_tools_clean import (
            apply_cleaned_findings_to_docx, 
            clean_findings_with_llm, 
            CleanedFinding,
            replace_cleaned_findings_in_docx,
            RawFinding
        )
        import shutil
        
        # Create temporary file
        st.session_state.direct_processing_progress = 20
        st.session_state.direct_processing_message = 'Creating temporary files...'
        
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.docx') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Process findings
        st.session_state.direct_processing_progress = 40
        st.session_state.direct_processing_message = 'Processing selected findings...'
        
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
                comment = user_comments.get(f"{priority}_{idx}", "")
                if comment:
                    additional_info_by_id[finding_id] = comment
                
                finding_id += 1
        
        # Clean findings with LLM
        st.session_state.direct_processing_progress = 50
        st.session_state.direct_processing_message = 'Cleaning findings with AI...'
        
        # Need to read the NDA text for context - convert DOCX to markdown first
        import subprocess
        converted_path = temp_file_path.replace('.docx', '.md')
        result = subprocess.run([
            'pandoc', temp_file_path, '-o', converted_path, '--to=markdown'
        ], capture_output=True, text=True, check=True)
        
        # Read the original NDA text for context
        with open(converted_path, 'r', encoding='utf-8') as f:
            nda_text = f.read()
        
        # Clean all findings at once
        try:
            cleaned_findings = clean_findings_with_llm(
                nda_text,
                raw_findings,
                additional_info_by_id,
                "gemini-2.5-pro"  # Use default model
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
        
        # Generate documents
        st.session_state.direct_processing_progress = 70
        st.session_state.direct_processing_message = 'Generating tracked changes document...'
        
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
        
        clean_changes_applied = replace_cleaned_findings_in_docx(
            input_docx=clean_temp_path,
            cleaned_findings=cleaned_findings,
            output_docx=clean_temp_path
        )
        
        # Read generated files
        st.session_state.direct_processing_progress = 90
        st.session_state.direct_processing_message = 'Finalizing documents...'
        
        with open(tracked_temp_path, 'rb') as f:
            tracked_changes_content = f.read()
        
        with open(clean_temp_path, 'rb') as f:
            clean_edited_content = f.read()
        
        # Store results
        st.session_state.direct_processing_results = {
            'tracked_changes_content': tracked_changes_content,
            'clean_edited_content': clean_edited_content,
            'original_filename': file_name
        }
        
        # Cleanup
        os.unlink(temp_file_path)
        os.unlink(converted_path)
        os.unlink(tracked_temp_path)
        os.unlink(clean_temp_path)
        
        # Complete
        st.session_state.direct_processing_status = 'completed'
        st.session_state.direct_processing_progress = 100
        st.session_state.direct_processing_message = 'Document generation completed!'
        
    except Exception as e:
        st.session_state.direct_processing_status = 'error'
        st.session_state.direct_processing_error = str(e)
        st.session_state.direct_processing_message = f'Error: {str(e)}'

def start_direct_changes_background(file_content: bytes, file_name: str, selected_findings: Dict, user_comments: Dict) -> str:
    """Start background direct changes generation"""
    analysis_id = str(uuid.uuid4())
    
    # Initialize processing state
    st.session_state.direct_processing_status = 'processing'
    st.session_state.direct_processing_progress = 0
    st.session_state.direct_processing_message = 'Starting document generation...'
    st.session_state.direct_processing_results = None
    st.session_state.direct_processing_error = None
    st.session_state.direct_processing_id = analysis_id
    
    # Start background thread
    thread = threading.Thread(
        target=run_direct_changes_background,
        args=(analysis_id, file_content, file_name, selected_findings, user_comments)
    )
    thread.daemon = True
    thread.start()
    
    return analysis_id