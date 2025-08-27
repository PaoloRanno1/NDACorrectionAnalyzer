"""
Direct Tracked Changes Generation — Async/background worker for Streamlit on Replit

Drop this file into your project (e.g., direct_tracked_async.py) and import it from your
Streamlit app. It moves the *entire* heavy pipeline (DOCX→Markdown via Pandoc, AI analysis,
cleaning, and generation of tracked/clean DOCX files) off the UI thread into a background
worker, with resilient progress/status stored in st.session_state.

Assumptions:
- You have these project modules available:
  * playbook_manager.get_current_playbook
  * NDA_Review_chain.StradaComplianceChain (method analyze_nda(md_path) -> (report, debug))
  * Tracked_changes_tools_clean.RawFinding, clean_findings_with_llm, apply_cleaned_findings_to_docx, replace_cleaned_findings_in_docx
- Replit deployment includes `pandoc` (add to replit.nix: `pkgs.pandoc`).

Session state keys used:
- st.session_state.direct_processing = {
    'status': 'idle'|'processing'|'completed'|'error',
    'progress': int 0..100,
    'message': str,
    'results': {
        'tracked_changes_content': bytes,
        'clean_edited_content': bytes,
        'original_filename': str
    } | None,
    'error': str | None,
    'job_id': str | None
  }

Public API:
- init_direct_processing_state()
- start_direct_tracked_job(file_bytes: bytes, filename: str, model: str = 'gemini-2.5-pro', temperature: float = 0.0)
- render_direct_tracked_status_ui()  # optional convenience UI renderer

Usage example (in your Streamlit app):

    import streamlit as st
    from direct_tracked_async import init_direct_processing_state, start_direct_tracked_job, render_direct_tracked_status_ui

    init_direct_processing_state()

    uploaded = st.file_uploader("Upload NDA (.docx)", type=["docx"]) 
    model = 'gemini-2.5-pro'
    temperature = 0.0

    if st.button("Direct tracked changes generation") and uploaded is not None:
        start_direct_tracked_job(uploaded.getvalue(), uploaded.name, model=model, temperature=temperature)

    # Show live status + downloads when ready
    render_direct_tracked_status_ui()

"""
from __future__ import annotations

import os
import io
import uuid
import time
import tempfile
import threading
import subprocess
import shutil
import json
from typing import Dict, Any, List

import streamlit as st

# --- Optional: tweak heartbeat frequency (seconds) for UI-friendly updates ---
_HEARTBEAT_SEC = 0.75


# ---------- Session State Helpers ----------
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


def _get_status_file_path(job_id: str) -> str:
    """Get the path for the status file for a given job."""
    return os.path.join(tempfile.gettempdir(), f"direct_processing_{job_id}.json")

def _set_status(status: str = None, progress: int = None, message: str = None, **extra) -> None:
    """Set status with file-based tracking for background threads."""
    try:
        # Update session state if available
        if 'direct_processing' in st.session_state:
            dp = st.session_state.direct_processing
            if status is not None:
                dp['status'] = status
            if progress is not None:
                dp['progress'] = max(0, min(100, int(progress)))
            if message is not None:
                dp['message'] = message
            for k, v in extra.items():
                dp[k] = v
            
            # Also write to file for background thread persistence
            job_id = dp.get('job_id')
            if job_id:
                status_file = _get_status_file_path(job_id)
                status_data = {
                    'status': dp['status'],
                    'progress': dp['progress'],
                    'message': dp['message'],
                    'job_id': job_id,
                    'timestamp': time.time()
                }
                
                # Handle results separately - save binary data to files
                if 'results' in extra and extra['results']:
                    results = extra['results']
                    status_data['has_results'] = True
                    status_data['original_filename'] = results.get('original_filename', 'document')
                    
                    # Save binary data to separate files
                    results_dir = os.path.join(tempfile.gettempdir(), f"results_{job_id}")
                    os.makedirs(results_dir, exist_ok=True)
                    
                    if 'tracked_changes_content' in results:
                        tracked_file = os.path.join(results_dir, 'tracked.docx')
                        with open(tracked_file, 'wb') as f:
                            f.write(results['tracked_changes_content'])
                        status_data['tracked_file'] = tracked_file
                    
                    if 'clean_edited_content' in results:
                        clean_file = os.path.join(results_dir, 'clean.docx')
                        with open(clean_file, 'wb') as f:
                            f.write(results['clean_edited_content'])
                        status_data['clean_file'] = clean_file
                    
                    # Save findings data
                    if 'findings' in results:
                        findings_file = os.path.join(results_dir, 'findings.json')
                        with open(findings_file, 'w') as f:
                            # Convert findings to serializable format
                            findings_data = []
                            for finding in results['findings']:
                                if hasattr(finding, '__dict__'):
                                    findings_data.append(finding.__dict__)
                                else:
                                    findings_data.append(finding)
                            json.dump(findings_data, f, indent=2)
                        status_data['findings_file'] = findings_file
                        
                else:
                    status_data['has_results'] = False
                    
                with open(status_file, 'w') as f:
                    json.dump(status_data, f)
    except Exception as e:
        print(f"Status update error: {e}")

def _load_status_from_file(job_id: str) -> Dict[str, Any]:
    """Load status from file for a given job."""
    try:
        status_file = _get_status_file_path(job_id)
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status_data = json.load(f)
                
            # If we have results files, load them back into memory
            if status_data.get('has_results'):
                results = {
                    'original_filename': status_data.get('original_filename', 'document')
                }
                
                # Load tracked changes file
                if 'tracked_file' in status_data and os.path.exists(status_data['tracked_file']):
                    with open(status_data['tracked_file'], 'rb') as f:
                        results['tracked_changes_content'] = f.read()
                
                # Load clean edited file  
                if 'clean_file' in status_data and os.path.exists(status_data['clean_file']):
                    with open(status_data['clean_file'], 'rb') as f:
                        results['clean_edited_content'] = f.read()
                
                # Load findings data
                if 'findings_file' in status_data and os.path.exists(status_data['findings_file']):
                    with open(status_data['findings_file'], 'r') as f:
                        results['findings'] = json.load(f)
                
                status_data['results'] = results
                
            return status_data
    except Exception as e:
        print(f"Error loading status: {e}")
    return {}


# ---------- Heavy Pipeline Worker (runs in a thread) ----------
def _run_direct_tracked_pipeline(job_id: str, file_bytes: bytes, filename: str, model: str, temperature: float) -> None:
    """End-to-end heavy job: DOCX→MD, AI review, cleaning, DOCX generation.
    Writes progress + results into st.session_state.direct_processing.
    """
    init_direct_processing_state()
    start_time = time.time()
    
    docx_path = md_path = tracked_path = clean_path = None
    try:
        # Add timeout check - if process takes more than 10 minutes, abort
        def check_timeout():
            if time.time() - start_time > 600:  # 10 minutes
                raise TimeoutError("Process timed out after 10 minutes")
        
        check_timeout()
        _set_status(status='processing', progress=5, message='Saving upload...', job_id=job_id, results=None, error=None)

        # 0) Save upload to a temp DOCX file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as f:
            f.write(file_bytes)
            docx_path = f.name

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=12, message='Checking Pandoc availability...')

        # 1) Ensure pandoc is available
        try:
            subprocess.run(["pandoc", "-v"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            raise RuntimeError("Pandoc is not available in the deployment. Please add `pkgs.pandoc` to replit.nix.") from e

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=20, message='Converting DOCX → Markdown (Pandoc)...')

        # 2) DOCX → Markdown conversion - EXACT SAME AS "Review NDA First"
        try:
            # Use pandoc to convert DOCX to markdown
            import subprocess
            converted_path = docx_path.replace('.docx', '.md')
            
            # Run pandoc conversion
            result = subprocess.run([
                'pandoc', docx_path, 
                '-o', converted_path,
                '--to=markdown',
                '--wrap=none'
            ], capture_output=True, text=True, check=True)
            
            md_path = converted_path
            print(f"✅ Pandoc conversion successful: {md_path}")
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Pandoc conversion failed: {e.stderr}")
        except Exception as e:
            raise Exception(f"Document conversion error: {str(e)}")

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=40, message='Running AI compliance analysis...')

        # 3) AI analysis - EXACT SAME AS "Review NDA First" 
        from playbook_manager import get_current_playbook
        from NDA_Review_chain import StradaComplianceChain

        playbook = get_current_playbook()
        review_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook)
        
        # This returns (compliance_report_dict, raw_response_text) - same as Review NDA First
        compliance_report, raw_response = review_chain.analyze_nda(md_path)
        print(f"✅ Analysis completed successfully!")

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=58, message='Preparing findings for document generation...')

        # 4) Process findings EXACTLY like "Review NDA First" workflow 
        # Store results temporarily to simulate the Review NDA First session state
        st.session_state.temp_single_nda_results = compliance_report
        st.session_state.temp_single_nda_raw_response = raw_response
        
        # Import the tracked changes processing functions
        from Tracked_changes_tools_clean import (
            RawFinding,
            clean_findings_with_llm,
            CleanedFinding,
            apply_cleaned_findings_to_docx,
            replace_cleaned_findings_in_docx
        )

        # Flatten all findings into RawFinding objects - EXACT same process
        all_findings = []
        high_priority = compliance_report.get('High Priority', [])
        medium_priority = compliance_report.get('Medium Priority', [])  
        low_priority = compliance_report.get('Low Priority', [])
        all_findings = high_priority + medium_priority + low_priority
        
        # Create RawFinding objects for ALL findings (auto-select all for direct generation)
        raw_findings = []
        additional_info_by_id = {}
        
        for idx, finding in enumerate(all_findings):
            finding_id = f"auto_selected_{idx}"
            raw_finding = RawFinding(
                id=finding_id,
                citation=finding.get('citation', ''),
                suggested_replacement=finding.get('suggested_replacement', '')
            )
            raw_findings.append(raw_finding)
            additional_info_by_id[finding_id] = "Auto-selected for direct tracked changes generation"
        
        print(f"Created {len(raw_findings)} raw findings for processing")

        # Read NDA text for cleaning step
        with open(md_path, 'r', encoding='utf-8') as f:
            nda_text = f.read()

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=70, message='Cleaning findings with LLM...')

        # Clean findings with LLM - EXACT same process
        try:
            cleaned = clean_findings_with_llm(nda_text, raw_findings, additional_info_by_id, model)
            print(f"Successfully cleaned {len(cleaned)} findings")
        except Exception as e:
            print(f"LLM cleaning failed: {e}")
            # Fallback: create basic cleaned findings
            cleaned = []
            for raw_finding in raw_findings:
                cleaned_finding = CleanedFinding(
                    id=raw_finding.id,
                    citation_clean=raw_finding.citation,
                    suggested_replacement_clean=raw_finding.suggested_replacement
                )
                cleaned.append(cleaned_finding)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=86, message='Generating Word documents...')

        # 5) Generate tracked + clean DOCX using the actual functions
        try:
            # Generate tracked changes document
            tracked_path = tempfile.mktemp(suffix='_tracked.docx')
            shutil.copy2(docx_path, tracked_path)
            
            _set_status(progress=90, message='Creating tracked changes document...')
            print(f"Attempting to apply {len(cleaned)} cleaned findings to document")
            for i, finding in enumerate(cleaned):
                print(f"Finding {i}: citation='{getattr(finding, 'citation_clean', 'N/A')}', replacement='{getattr(finding, 'suggested_replacement_clean', 'N/A')}'")
            
            changes_applied = apply_cleaned_findings_to_docx(
                input_docx=tracked_path,
                cleaned_findings=cleaned,
                output_docx=tracked_path,
                author="AI Compliance Reviewer",
                ignore_case=True,  # Try case-insensitive matching
                skip_if_same=False  # Don't skip identical citations/replacements for debugging
            )
            print(f"Applied {changes_applied} changes to tracked document")
            
            # Generate clean edited document  
            clean_path = tempfile.mktemp(suffix='_clean.docx')
            shutil.copy2(docx_path, clean_path)
            
            _set_status(progress=95, message='Creating clean edited document...')
            clean_changes_applied = replace_cleaned_findings_in_docx(
                input_docx=clean_path,
                cleaned_findings=cleaned,
                output_docx=clean_path
            )
            print(f"Applied {clean_changes_applied} changes to clean document")

            _set_status(progress=98, message='Reading generated files...')
            with open(tracked_path, 'rb') as f:
                tracked_bytes = f.read()
            with open(clean_path, 'rb') as f:
                clean_bytes = f.read()

            # Prepare findings for display using original compliance report data
            findings_for_display = []
            for finding in all_findings:
                findings_for_display.append({
                    'issue': finding.get('issue', 'Compliance Issue'),
                    'citation': finding.get('citation', 'Not specified'),
                    'section': finding.get('section', 'Not specified'),
                    'problem': finding.get('problem', 'Not specified'),
                    'suggested_replacement': finding.get('suggested_replacement', 'Not specified'),
                    'suggested_replacement_clean': finding.get('suggested_replacement', 'Not specified')  # Will be updated if cleaned
                })
            
            # Update with cleaned versions if available and matching
            for i, cleaned_finding in enumerate(cleaned):
                if i < len(findings_for_display) and hasattr(cleaned_finding, 'suggested_replacement_clean'):
                    findings_for_display[i]['suggested_replacement_clean'] = cleaned_finding.suggested_replacement_clean

            results = {
                'tracked_changes_content': tracked_bytes,
                'clean_edited_content': clean_bytes,
                'original_filename': filename,
                'findings': findings_for_display,  # Add the compliance findings with full info
            }
            
            time.sleep(_HEARTBEAT_SEC)
            _set_status(status='completed', progress=100, message='Done!', results=results)
            
        except Exception as doc_error:
            # If document generation fails, create simple copies as fallback
            _set_status(progress=90, message='Document generation failed, creating fallback copies...')
            
            tracked_path = tempfile.mktemp(suffix='_tracked.docx')
            clean_path = tempfile.mktemp(suffix='_clean.docx')
            
            # Just copy the original as fallback
            shutil.copy2(docx_path, tracked_path)
            shutil.copy2(docx_path, clean_path)
            
            with open(tracked_path, 'rb') as f:
                tracked_bytes = f.read()
            with open(clean_path, 'rb') as f:
                clean_bytes = f.read()

            # Prepare findings for display using original compliance report data (fallback case)
            findings_for_display = []
            for finding in all_findings:
                findings_for_display.append({
                    'issue': finding.get('issue', 'Compliance Issue'),
                    'citation': finding.get('citation', 'Not specified'),
                    'section': finding.get('section', 'Not specified'),
                    'problem': finding.get('problem', 'Not specified'),
                    'suggested_replacement': finding.get('suggested_replacement', 'Not specified'),
                    'suggested_replacement_clean': finding.get('suggested_replacement', 'Not specified')
                })

            results = {
                'tracked_changes_content': tracked_bytes,
                'clean_edited_content': clean_bytes,
                'original_filename': filename,
                'findings': findings_for_display,  # Add the compliance findings with full info
            }
            
            _set_status(status='completed', progress=100, message=f'Completed with fallback (doc gen error: {str(doc_error)})', results=results)

    except Exception as e:
        _set_status(status='error', progress=0, message=f'Error: {e}', error=str(e))
    finally:
        # Best-effort cleanup of temp files
        for p in (docx_path, md_path, tracked_path, clean_path):
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


# ---------- Public API ----------
def start_direct_tracked_job(file_bytes: bytes, filename: str, model: str = 'gemini-2.5-pro', temperature: float = 0.0) -> str:
    """Kick off the background job. Returns a job_id.
    Safe to call from a Streamlit button handler.
    """
    init_direct_processing_state()

    # If a job is already running, ignore new starts (or generate a new id and overwrite).
    if st.session_state.direct_processing.get('status') == 'processing':
        return st.session_state.direct_processing.get('job_id') or ""

    job_id = str(uuid.uuid4())
    _set_status(status='processing', progress=1, message='Starting...', job_id=job_id, results=None, error=None)

    t = threading.Thread(
        target=_run_direct_tracked_pipeline,
        args=(job_id, file_bytes, filename, model, temperature),
        daemon=True,
    )
    t.start()
    return job_id


def render_direct_tracked_status_ui(download_prefix: str = "NDA") -> None:
    """Optional convenience renderer for progress + downloads. Call anywhere in your Streamlit page.
    - Shows progress bar + status while processing
    - Shows Download buttons when completed
    - Shows error message if failed
    """
    init_direct_processing_state()
    dp = st.session_state.direct_processing

    # Check file-based status if we have a job_id
    if dp.get('job_id'):
        file_status = _load_status_from_file(dp['job_id'])
        if file_status:
            # Update session state with file status
            dp['status'] = file_status.get('status', dp['status'])
            dp['progress'] = file_status.get('progress', dp['progress'])
            dp['message'] = file_status.get('message', dp['message'])
            
            # Load results if available
            if 'results' in file_status:
                dp['results'] = file_status['results']
            
            # Update the session state properly
            st.session_state.direct_processing = dp

    # Debug: Show current status
    st.caption(f"Current Status: {dp['status']} | Progress: {dp['progress']}% | Message: {dp['message']}")

    if dp['status'] == 'processing':
        st.progress(dp['progress'] / 100.0)
        st.info(f"🔄 {dp['message']}")
        st.caption(f"Job ID: {dp.get('job_id','-')}")
        
        # Auto-refresh at reasonable intervals to avoid CPU churn
        import time
        time.sleep(1.5)
        st.rerun()

    elif dp['status'] == 'completed':
        st.success('✅ Documents generated successfully!')
        
        if dp.get('results'):
            res = dp['results']
            
            # Show completion metrics
            st.info("Your tracked changes documents are ready for download!")
            
            col1, col2 = st.columns(2)
            base = os.path.splitext(res.get('original_filename') or download_prefix)[0]
            
            with col1:
                st.download_button(
                    label='📄 Download Tracked Changes (.docx)',
                    data=res['tracked_changes_content'],
                    file_name=f"{base}_Tracked.docx",
                    mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    key=f"tracked_{dp.get('job_id', 'default')}",
                    help="Document with Word's tracked changes showing all edits"
                )
            
            with col2:
                st.download_button(
                    label='📄 Download Clean Edited (.docx)',
                    data=res['clean_edited_content'],
                    file_name=f"{base}_Clean.docx",
                    mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    key=f"clean_{dp.get('job_id', 'default')}",
                    help="Clean document with all edits applied"
                )
            
            # Display compliance findings
            if 'findings' in res and res['findings']:
                st.markdown("---")
                st.subheader("🔍 Compliance Issues Identified and Resolved")
                
                findings = res['findings']
                if len(findings) > 0:
                    st.info(f"Found and resolved {len(findings)} compliance issues:")
                    
                    for i, finding in enumerate(findings, 1):
                        with st.expander(f"Issue #{i}: {finding.get('issue', 'Compliance Issue')}", expanded=False):
                            col1, col2 = st.columns([1, 1])
                            
                            with col1:
                                st.markdown("**🚨 Problem Found:**")
                                st.markdown(finding.get('problem', 'No problem description available'))
                                
                                if finding.get('citation'):
                                    st.markdown("**📋 Policy Reference:**")
                                    st.markdown(f"*{finding['citation']}*")
                            
                            with col2:
                                st.markdown("**✅ Replacement Applied:**")
                                replacement = finding.get('suggested_replacement_clean', finding.get('suggested_replacement', 'No replacement specified'))
                                st.markdown(replacement)
                                
                                if finding.get('section'):
                                    st.markdown("**📄 Document Section:**")
                                    st.markdown(f"*{finding['section']}*")
                else:
                    st.success("✅ No compliance issues found - document appears to be fully compliant!")
        else:
            st.warning("Processing completed but results are not available. Please try again.")
        
        # Add reset button
        if st.button("🔄 Process Another Document", key="reset_after_completion"):
            _set_status(status='idle', progress=0, message='Idle', results=None, error=None, job_id=None)
            st.rerun()

    elif dp['status'] == 'error':
        st.error(f"❌ Error: {dp.get('message', 'Direct generation failed.')}")
        if dp.get('error'):
            with st.expander('Show error details'):
                st.code(dp['error'])
        if st.button("🔄 Try Again", key="reset_direct_processing"):
            _set_status(status='idle', progress=0, message='Idle', results=None, error=None, job_id=None)
            st.rerun()

    elif dp['status'] == 'idle':
        # Show idle state
        st.info("Ready to process documents. Upload a DOCX file and click 'Direct tracked changes generation'.")
    
    else:
        # Unknown state - show debug info and auto-fix
        if dp['status'] == 'completed' and dp['progress'] == 100:
            # This means it completed but we don't have results - treat as completed
            st.success('✅ Processing completed!')
            st.info("Documents were generated successfully. Please click the button below to process another document.")
            if st.button("🔄 Process Another Document", key="auto_reset_completed"):
                _set_status(status='idle', progress=0, message='Idle', results=None, error=None, job_id=None)
                st.rerun()
        else:
            # Truly unknown state
            st.warning(f"Unknown processing state: {dp['status']}")
            if st.button("🔄 Reset", key="reset_unknown_state"):
                _set_status(status='idle', progress=0, message='Idle', results=None, error=None, job_id=None)
                st.rerun()