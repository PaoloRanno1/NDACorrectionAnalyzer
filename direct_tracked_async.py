"""
Direct Tracked Changes Generation — Async/background worker for Streamlit on Replit

This module handles the asynchronous generation of tracked changes documents.
It processes NDA files by running AI analysis and automatically accepting all issues,
then generates both tracked changes and clean edited DOCX files.

Session state keys used:
- st.session_state.direct_processing = {
    'status': 'idle'|'processing'|'completed'|'error',
    'progress': int 0..100,
    'message': str,
    'results': {
        'tracked_changes_content': bytes,
        'clean_edited_content': bytes,
        'original_filename': str,
        'compliance_report': dict,
        'processed_findings': list
    } | None,
    'error': str | None,
    'job_id': str | None
  }
"""
from __future__ import annotations

import os
import uuid
import time
import tempfile
import threading
import subprocess
from typing import Dict, Any, List

import streamlit as st

# Heartbeat frequency for UI updates
_HEARTBEAT_SEC = 0.75


def init_direct_processing_state() -> None:
    """Ensure the session state dict exists with default values."""
    if 'direct_processing' not in st.session_state:
        st.session_state.direct_processing = {
            'status': 'idle',         # 'idle'|'processing'|'completed'|'error'
            'progress': 0,            # int 0..100
            'message': 'Idle',
            'results': None,          # dict with bytes when completed
            'error': None,            # str on error
            'job_id': None,           # unique id per run
        }


def _set_status(status: str = None, progress: int = None, message: str = None, **extra) -> None:
    """Update the processing status in session state."""
    try:
        # Initialize if needed
        if 'direct_processing' not in st.session_state:
            init_direct_processing_state()
        
        dp = st.session_state.direct_processing
        if status is not None:
            dp['status'] = status
        if progress is not None:
            dp['progress'] = max(0, min(100, int(progress)))
        if message is not None:
            dp['message'] = message
        for k, v in extra.items():
            dp[k] = v
        
        # Force update the session state
        st.session_state.direct_processing = dp
    except Exception as e:
        # If session state access fails from thread, ignore silently but continue
        import traceback
        print(f"Status update failed (this is normal in threads): {e}")
        print(traceback.format_exc())
        pass


def _run_direct_tracked_pipeline(job_id: str, file_bytes: bytes, filename: str, model: str, temperature: float) -> None:
    """
    End-to-end pipeline: DOCX→MD, AI review (auto-accept all issues), cleaning, DOCX generation.
    This mimics the "Review NDA first" workflow but automatically accepts all issues.
    """
    init_direct_processing_state()

    docx_path = md_path = tracked_path = clean_path = None
    try:
        _set_status(status='processing', progress=5, message='Preparing upload...', job_id=job_id, results=None, error=None)

        # 1) Save upload to temp DOCX file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as f:
            f.write(file_bytes)
            docx_path = f.name

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=15, message='Converting DOCX to Markdown...')

        # 2) Convert DOCX to Markdown using pandoc
        try:
            subprocess.run(["pandoc", "-v"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            raise RuntimeError("Pandoc is not available. Please ensure pandoc is installed.") from e

        md_path = docx_path.replace('.docx', '.md')
        subprocess.run(["pandoc", docx_path, "-o", md_path, "--to=markdown", "--wrap=none"], check=True)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=30, message='Running AI compliance analysis...')

        # 3) Run AI analysis using NDA Review chain
        from playbook_manager import get_current_playbook
        from NDA_Review_chain import StradaComplianceChain

        playbook = get_current_playbook()
        review_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook)
        compliance_report, debug_info = review_chain.analyze_nda(md_path)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=50, message='Processing compliance findings...')

        # 4) Flatten all findings and automatically accept them all
        from Tracked_changes_tools_clean import (
            RawFinding,
            clean_findings_with_llm
        )

        # Create RawFinding objects for all issues (auto-accept all)
        raw_findings: List[RawFinding] = []
        finding_id = 1
        
        # Handle both formats: underscore (high_priority) and space (High Priority)
        priority_mappings = [
            ("high_priority", "High Priority"),
            ("medium_priority", "Medium Priority"), 
            ("low_priority", "Low Priority")
        ]
        
        for priority_key, priority_label in priority_mappings:
            # Try both formats
            findings_list = compliance_report.get(priority_key, []) or compliance_report.get(priority_label, [])
            
            if findings_list:
                for finding in findings_list:
                    # Handle both dict and object formats
                    if hasattr(finding, '__dict__'):
                        # Pydantic model object
                        raw_findings.append(
                            RawFinding(
                                id=finding_id,
                                priority=priority_label,
                                section=getattr(finding, 'section', ''),
                                issue=getattr(finding, 'issue', ''),
                                problem=getattr(finding, 'problem', ''),
                                citation=getattr(finding, 'citation', ''),
                                suggested_replacement=getattr(finding, 'suggested_replacement', ''),
                            )
                        )
                    else:
                        # Dictionary format
                        raw_findings.append(
                            RawFinding(
                                id=finding_id,
                                priority=priority_label,
                                section=finding.get('section', ''),
                                issue=finding.get('issue', ''),
                                problem=finding.get('problem', ''),
                                citation=finding.get('citation', ''),
                                suggested_replacement=finding.get('suggested_replacement', ''),
                            )
                        )
                    finding_id += 1

        if not raw_findings:
            _set_status(status='completed', progress=100, message='No compliance issues found. No changes needed.', 
                       results={
                           'tracked_changes_content': file_bytes,  # Return original file
                           'clean_edited_content': file_bytes,     # Return original file
                           'original_filename': filename,
                           'compliance_report': compliance_report,
                           'processed_findings': []
                       })
            return

        # 5) Read NDA text for cleaning
        with open(md_path, 'r', encoding='utf-8') as f:
            nda_text = f.read()

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=70, message='Cleaning and processing findings with AI...')

        # 6) Clean findings with LLM (auto-accept all with empty comments)
        auto_comments = {finding.id: "" for finding in raw_findings}  # Empty comments for all
        cleaned_findings = clean_findings_with_llm(nda_text, raw_findings, auto_comments, model)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=85, message='Generating tracked changes documents...')

        # 7) Generate tracked changes and clean DOCX files
        from Tracked_changes_tools_clean import (
            apply_cleaned_findings_to_docx,
            replace_cleaned_findings_in_docx
        )
        import tempfile
        import shutil
        
        # Generate tracked changes document
        tracked_path = tempfile.mktemp(suffix='_tracked.docx')
        shutil.copy2(docx_path, tracked_path)
        
        apply_cleaned_findings_to_docx(
            input_docx=tracked_path,
            cleaned_findings=cleaned_findings,
            output_docx=tracked_path,
            author="AI Compliance Reviewer"
        )
        
        # Generate clean edited document  
        clean_path = tempfile.mktemp(suffix='_clean.docx')
        shutil.copy2(docx_path, clean_path)
        
        replace_cleaned_findings_in_docx(
            input_docx=clean_path,
            cleaned_findings=cleaned_findings,
            output_docx=clean_path
        )

        # 8) Read generated files
        with open(tracked_path, 'rb') as f:
            tracked_bytes = f.read()
        with open(clean_path, 'rb') as f:
            clean_bytes = f.read()

        time.sleep(_HEARTBEAT_SEC)
        _set_status(status='completed', progress=100, message='Direct generation completed!', 
                   results={
                       'tracked_changes_content': tracked_bytes,
                       'clean_edited_content': clean_bytes,
                       'original_filename': filename,
                       'compliance_report': compliance_report,
                       'processed_findings': [{
                           'id': f.id,
                           'priority': getattr(f, 'priority', 'Unknown Priority'),
                           'section': getattr(f, 'section', ''),
                           'issue': getattr(f, 'issue', ''),
                           'problem': getattr(f, 'problem', ''),
                           'citation': getattr(f, 'citation_clean', getattr(f, 'citation', '')),
                           'suggested_replacement': getattr(f, 'suggested_replacement_clean', getattr(f, 'suggested_replacement', ''))
                       } for f in cleaned_findings]
                   })

    except Exception as e:
        error_msg = f"Direct generation failed: {str(e)}"
        _set_status(status='error', progress=0, message=error_msg, error=str(e))
    finally:
        # Clean up temporary files
        for path in (docx_path, md_path, tracked_path, clean_path):
            try:
                if path and os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass


def start_direct_tracked_job(file_bytes: bytes, filename: str, model: str = 'gemini-2.5-flash', temperature: float = 0.0) -> str:
    """
    Start the background job for direct tracked changes generation.
    Returns a job_id for tracking.
    """
    init_direct_processing_state()

    # Prevent multiple concurrent jobs
    if st.session_state.direct_processing.get('status') == 'processing':
        return st.session_state.direct_processing.get('job_id') or ""

    job_id = str(uuid.uuid4())
    _set_status(status='processing', progress=1, message='Initializing...', job_id=job_id, results=None, error=None)

    # Start background thread
    thread = threading.Thread(
        target=_run_direct_tracked_pipeline,
        args=(job_id, file_bytes, filename, model, temperature),
        daemon=True,
    )
    thread.start()
    return job_id


def render_direct_tracked_status_ui() -> None:
    """
    Render the status UI for direct tracked changes generation.
    Shows progress, results, or errors based on current status.
    """
    init_direct_processing_state()
    dp = st.session_state.direct_processing

    if dp['status'] == 'processing':
        st.progress(dp['progress'] / 100.0)
        st.info(f"🔄 {dp['message']}")
        
        # Show current progress details
        progress_details = {
            5: "Setting up environment...",
            15: "Converting document format...",
            30: "Analyzing compliance with AI...",
            50: "Processing all compliance findings...",
            70: "Applying AI-powered text improvements...", 
            85: "Generating final documents...",
            100: "Complete!"
        }
        
        current_progress = dp['progress']
        latest_detail = "Initializing..."  # Default value
        for threshold, detail in progress_details.items():
            if current_progress >= threshold:
                latest_detail = detail
        
        st.caption(f"Step: {latest_detail}")
        
        # Show more detailed status
        with st.expander("📋 Progress Details", expanded=False):
            st.write(f"**Job ID:** {dp.get('job_id', 'N/A')}")
            st.write(f"**Progress:** {current_progress}%")
            st.write(f"**Status:** {dp.get('status', 'unknown')}")
            st.write(f"**Message:** {dp.get('message', 'No message')}")
            
            # Show error if any
            if dp.get('error'):
                st.error(f"**Error:** {dp['error']}")
        
        # Show refresh button and cancel option
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh Status", key="refresh_direct_status"):
                st.rerun()
        with col2:
            if st.button("❌ Cancel Process", key="cancel_direct_process"):
                # Reset the process
                st.session_state.direct_processing = {
                    'status': 'idle',
                    'progress': 0,
                    'message': 'Idle',
                    'results': None,
                    'error': None,
                    'job_id': None,
                }
                st.success("Process cancelled. You can start a new one.")
                st.rerun()

    elif dp['status'] == 'completed' and dp['results']:
        st.success('✅ Direct tracked changes generation completed!')
        
        results = dp['results']
        
        # Show processing summary
        if results.get('processed_findings'):
            num_findings = len(results['processed_findings'])
            st.info(f"📋 Processed {num_findings} compliance issues automatically")
        
        # Show download buttons
        col1, col2 = st.columns(2)
        base_name = os.path.splitext(results.get('original_filename', 'NDA'))[0]
        
        with col1:
            st.download_button(
                label='📄 Download Tracked Changes',
                data=results['tracked_changes_content'],
                file_name=f"{base_name}_Tracked_Changes.docx",
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                use_container_width=True
            )
        
        with col2:
            st.download_button(
                label='📄 Download Clean Version',
                data=results['clean_edited_content'],
                file_name=f"{base_name}_Clean_Edited.docx",
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                use_container_width=True
            )
        
        # Show issues processed section
        if results.get('processed_findings'):
            st.markdown("---")
            st.subheader("📋 Issues Processed")
            
            findings = results['processed_findings']
            high_priority = [f for f in findings if f.get('priority') == 'High Priority']
            medium_priority = [f for f in findings if f.get('priority') == 'Medium Priority'] 
            low_priority = [f for f in findings if f.get('priority') == 'Low Priority']
            
            for priority, findings_list, color in [
                ("🔴 High Priority", high_priority, "#ff6b6b"),
                ("🟡 Medium Priority", medium_priority, "#ffcc5c"),
                ("🟢 Low Priority", low_priority, "#81c784")
            ]:
                if findings_list:
                    st.markdown(f"**{priority} ({len(findings_list)} issues)**")
                    for finding in findings_list:
                        with st.container():
                            st.markdown(f"""
                            <div style='background-color: #2a2a2a; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid {color};'>
                                <div style='color: white; font-weight: bold; margin-bottom: 10px;'>
                                    {finding.get('issue', 'Unknown Issue')}
                                </div>
                                <div style='color: {color}; margin-bottom: 8px;'>
                                    📍 <strong>Section:</strong> <span style='color: #cccccc;'>{finding.get('section', 'N/A')}</span>
                                </div>
                                <div style='color: {color}; margin-bottom: 8px;'>
                                    ❌ <strong>Problem:</strong> <span style='color: #cccccc;'>{finding.get('problem', 'N/A')}</span>
                                </div>
                                <div style='color: {color}; margin-bottom: 8px;'>
                                    ✏️ <strong>Suggested Replacement:</strong> <span style='color: #cccccc;'>{finding.get('suggested_replacement', 'N/A')}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
        
        # Clear results button
        if st.button("🔄 Start New Direct Generation", type="secondary"):
            st.session_state.direct_processing = {
                'status': 'idle',
                'progress': 0,
                'message': 'Idle',
                'results': None,
                'error': None,
                'job_id': None,
            }
            st.rerun()

    elif dp['status'] == 'error':
        st.error(f"❌ {dp.get('message', 'Direct generation failed')}")
        
        if dp.get('error'):
            with st.expander("Show error details"):
                st.code(dp['error'])
        
        # Reset button for errors
        if st.button("🔄 Reset and Try Again", type="secondary"):
            st.session_state.direct_processing = {
                'status': 'idle',
                'progress': 0,
                'message': 'Idle',
                'results': None,
                'error': None,
                'job_id': None,
            }
            st.rerun()

    # If idle, don't show anything - let the main UI handle it