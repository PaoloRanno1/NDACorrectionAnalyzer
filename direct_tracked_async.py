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


def _set_status(status: str = None, progress: int = None, message: str = None, **extra) -> None:
    dp = st.session_state.direct_processing
    if status is not None:
        dp['status'] = status
    if progress is not None:
        dp['progress'] = max(0, min(100, int(progress)))
    if message is not None:
        dp['message'] = message
    for k, v in extra.items():
        dp[k] = v


# ---------- Heavy Pipeline Worker (runs in a thread) ----------
def _run_direct_tracked_pipeline(job_id: str, file_bytes: bytes, filename: str, model: str, temperature: float) -> None:
    """End-to-end heavy job: DOCX→MD, AI review, cleaning, DOCX generation.
    Writes progress + results into st.session_state.direct_processing.
    """
    init_direct_processing_state()

    docx_path = md_path = tracked_path = clean_path = None
    try:
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

        # 2) DOCX → Markdown
        md_path = docx_path.replace('.docx', '.md')
        subprocess.run(["pandoc", docx_path, "-o", md_path, "--to=markdown", "--wrap=none"], check=True)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=40, message='Running AI compliance analysis...')

        # 3) AI analysis using your chain
        from playbook_manager import get_current_playbook  # project-specific
        from NDA_Review_chain import StradaComplianceChain  # project-specific

        playbook = get_current_playbook()
        review_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook)
        compliance_report, _debug = review_chain.analyze_nda(md_path)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=58, message='Preparing findings for cleaning...')

        # 4) Flatten findings and clean them via LLM
        from Tracked_changes_tools_clean import (
            RawFinding,
            clean_findings_with_llm,
            CleanedFinding,
            apply_cleaned_findings_to_docx,
            replace_cleaned_findings_in_docx
        )

        raw: List[RawFinding] = []
        additional_info_by_id = {}
        fid = 1
        for priority in ["High Priority", "Medium Priority", "Low Priority"]:
            for it in compliance_report.get(priority, []) or []:
                raw.append(
                    RawFinding(
                        id=fid,
                        priority=priority,
                        section=it.get('section', ''),
                        issue=it.get('issue', ''),
                        problem=it.get('problem', ''),
                        citation=it.get('citation', ''),
                        suggested_replacement=it.get('suggested_replacement', ''),
                    )
                )
                additional_info_by_id[fid] = "Auto-selected for direct tracked changes generation"
                fid += 1

        # Read NDA text for the cleaning step
        with open(md_path, 'r', encoding='utf-8') as f:
            nda_text = f.read()

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=72, message='Cleaning findings with AI...')

        try:
            cleaned = clean_findings_with_llm(nda_text, raw, additional_info_by_id, model)
        except Exception as e:
            # Create basic cleaned findings as fallback
            cleaned = []
            for raw_finding in raw:
                cleaned_finding = CleanedFinding(
                    id=raw_finding.id,
                    citation_clean=raw_finding.citation,
                    suggested_replacement_clean=raw_finding.suggested_replacement
                )
                cleaned.append(cleaned_finding)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=86, message='Generating Word documents...')

        # 5) Generate tracked + clean DOCX using the actual functions
        # Generate tracked changes document
        tracked_path = tempfile.mktemp(suffix='_tracked.docx')
        shutil.copy2(docx_path, tracked_path)
        
        changes_applied = apply_cleaned_findings_to_docx(
            input_docx=tracked_path,
            cleaned_findings=cleaned,
            output_docx=tracked_path,
            author="AI Compliance Reviewer"
        )
        
        # Generate clean edited document  
        clean_path = tempfile.mktemp(suffix='_clean.docx')
        shutil.copy2(docx_path, clean_path)
        
        clean_changes_applied = replace_cleaned_findings_in_docx(
            input_docx=clean_path,
            cleaned_findings=cleaned,
            output_docx=clean_path
        )

        with open(tracked_path, 'rb') as f:
            tracked_bytes = f.read()
        with open(clean_path, 'rb') as f:
            clean_bytes = f.read()

        results = {
            'tracked_changes_content': tracked_bytes,
            'clean_edited_content': clean_bytes,
            'original_filename': filename,
        }
        time.sleep(_HEARTBEAT_SEC)
        _set_status(status='completed', progress=100, message='Done!', results=results)

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

    elif dp['status'] == 'completed' and dp.get('results'):
        st.success('✅ Documents generated successfully!')
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
        # Unknown state - show debug info
        st.warning(f"Unknown processing state: {dp['status']}")
        if st.button("🔄 Reset", key="reset_unknown_state"):
            _set_status(status='idle', progress=0, message='Idle', results=None, error=None, job_id=None)
            st.rerun()