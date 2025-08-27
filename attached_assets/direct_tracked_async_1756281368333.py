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
  * Tracked_changes_tools_clean.RawFinding, clean_findings_with_llm, generate_tracked_changes_document
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
- start_direct_tracked_job(file_bytes: bytes, filename: str, model: str = 'gpt-4o-mini', temperature: float = 0.0)
- render_direct_tracked_status_ui()  # optional convenience UI renderer

Usage example (in your Streamlit app):

    import streamlit as st
    from direct_tracked_async import init_direct_processing_state, start_direct_tracked_job, render_direct_tracked_status_ui

    init_direct_processing_state()

    uploaded = st.file_uploader("Upload NDA (.docx)", type=["docx"]) 
    model = 'gpt-4o-mini'
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
            generate_tracked_changes_document,
        )

        raw: List[RawFinding] = []
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
                fid += 1

        # Read NDA text for the cleaning step
        with open(md_path, 'r', encoding='utf-8') as f:
            nda_text = f.read()

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=72, message='Cleaning findings...')

        cleaned = clean_findings_with_llm(nda_text, raw, {}, model)

        time.sleep(_HEARTBEAT_SEC)
        _set_status(progress=86, message='Generating Word documents...')

        # 5) Generate tracked + clean DOCX
        tracked_path, clean_path = generate_tracked_changes_document(docx_path, cleaned)

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
def start_direct_tracked_job(file_bytes: bytes, filename: str, model: str = 'gpt-4o-mini', temperature: float = 0.0) -> str:
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

    if dp['status'] == 'processing':
        st.progress(dp['progress'])
        st.info(dp['message'])
        st.caption(f"Job: {dp.get('job_id','-')}")
        # Encourage Streamlit to keep the websocket active by re-rendering periodically.
        st.experimental_rerun()  # NOTE: If this is too aggressive, comment out and let outer app rerun naturally.

    elif dp['status'] == 'completed' and dp['results']:
        st.success('✅ Direct tracked changes ready')
        res = dp['results']
        col1, col2 = st.columns(2)
        base = os.path.splitext(res.get('original_filename') or download_prefix)[0]
        with col1:
            st.download_button(
                label='Download Tracked Changes (.docx)',
                data=res['tracked_changes_content'],
                file_name=f"{base}_Tracked.docx",
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            )
        with col2:
            st.download_button(
                label='Download Clean Edited (.docx)',
                data=res['clean_edited_content'],
                file_name=f"{base}_Clean.docx",
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            )

    elif dp['status'] == 'error':
        st.error(dp.get('message') or 'Direct generation failed.')
        if dp.get('error'):
            with st.expander('Show error details'):
                st.code(dp['error'])

    else:
        # idle/no-op — nothing to show until user starts a job
        pass
