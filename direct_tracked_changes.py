"""
Extracted direct tracked changes generation logic for reuse in email workflows.
"""

import os
import tempfile
import subprocess
import shutil
from typing import Dict, List, Tuple, Optional

def generate_direct_tracked_changes(
    docx_content: bytes, 
    model: str = "gemini-2.5-flash", 
    temperature: float = 0.0
) -> Tuple[Optional[bytes], Optional[bytes], Dict]:
    """
    Generate tracked changes and clean edited documents from a DOCX file.
    
    Args:
        docx_content: Raw bytes of the DOCX file
        model: AI model to use for analysis
        temperature: Temperature setting for AI analysis
        
    Returns:
        Tuple of (tracked_changes_docx, clean_edited_docx, analysis_results)
        where analysis_results contains summary information
    """
    
    # Write content to temporary file
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as temp_file:
        temp_file.write(docx_content)
        temp_file_path = temp_file.name
    
    try:
        # Convert DOCX to markdown for analysis
        converted_path = temp_file_path.replace('.docx', '.md')
        result = subprocess.run([
            'pandoc', temp_file_path, '-o', converted_path, '--to=markdown'
        ], capture_output=True, text=True, check=True)
        
        # Run analysis
        from playbook_manager import get_current_playbook
        from NDA_Review_chain import StradaComplianceChain
        
        playbook_content = get_current_playbook()
        review_chain = StradaComplianceChain(model=model, temperature=temperature, playbook_content=playbook_content)
        compliance_report, raw_response = review_chain.analyze_nda(converted_path)
        
        if not compliance_report:
            raise Exception("Failed to get analysis results from AI")
        
        # Auto-select all findings
        high_priority = compliance_report.get('High Priority', [])
        medium_priority = compliance_report.get('Medium Priority', [])
        low_priority = compliance_report.get('Low Priority', [])
        
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
        
        total_issues = len(high_priority) + len(medium_priority) + len(low_priority)
        
        if total_issues == 0:
            # Return original document if no issues found
            with open(temp_file_path, 'rb') as f:
                original_content = f.read()
            return original_content, original_content, {
                'high_priority': 0,
                'medium_priority': 0, 
                'low_priority': 0,
                'total_issues': 0,
                'message': 'No compliance issues found! Your NDA appears to be fully compliant.'
            }
        
        # Process findings
        from Tracked_changes_tools_clean import (
            apply_cleaned_findings_to_docx, 
            clean_findings_with_llm, 
            flatten_findings, 
            select_findings,
            CleanedFinding,
            replace_cleaned_findings_in_docx,
            RawFinding
        )
        
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
                model
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
        
        clean_changes_applied = replace_cleaned_findings_in_docx(
            input_docx=clean_temp_path,
            cleaned_findings=cleaned_findings,
            output_docx=clean_temp_path
        )
        
        # Read the generated files
        with open(tracked_temp_path, 'rb') as f:
            tracked_docx = f.read()
        
        with open(clean_temp_path, 'rb') as f:
            clean_docx = f.read()
        
        # Cleanup temp files
        os.unlink(tracked_temp_path)
        os.unlink(clean_temp_path)
        
        analysis_results = {
            'high_priority': len(high_priority),
            'medium_priority': len(medium_priority),
            'low_priority': len(low_priority),
            'total_issues': total_issues,
            'message': f'Successfully processed {total_issues} compliance issues.'
        }
        
        return tracked_docx, clean_docx, analysis_results
        
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to convert DOCX file with pandoc: {e.stderr}")
    except FileNotFoundError:
        raise Exception("Pandoc is not installed. Cannot process DOCX files.")
    except Exception as e:
        raise Exception(f"Failed to process document: {str(e)}")
    finally:
        # Always cleanup temp files
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        if 'converted_path' in locals() and os.path.exists(converted_path):
            os.unlink(converted_path)