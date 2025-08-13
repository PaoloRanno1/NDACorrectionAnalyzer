#%%
import os
import NDA_Review_chain
from dotenv import load_dotenv
load_dotenv()
import warnings
warnings.filterwarnings("ignore")
import Tracked_changes_tools_clean as Tr_clean

#%% md
# # Step 1 get AI NDA Review
#%%
review_chain = NDA_Review_chain.StradaComplianceChain()
md_path="NDAs md/project_stern_clean.md"
#%%
compliance_report, response = review_chain.analyze_nda(md_path)
#%% md
# # Step 2 Post processing of the compliance_report output
#%%
flatten_findings = Tr_clean.flatten_findings(compliance_report)
# Select only the findings that I want to keep
selected_findings=Tr_clean.apply_edit_spec(flatten_findings,{"accept":[4]})

#%% md
# # Step 3
# Get a cleaner version of the selected findings
# Note: Works only with docx files as input
#%%
docx_path="NDAs md/NDA Project Stern clean.docx"
nda_text=Tr_clean.extract_text(docx_path)
guidance = {
} # Not adding any guidance
cleaned = Tr_clean.clean_findings_with_llm(
    nda_text=nda_text,
    findings=selected_findings,
    additional_info_by_id=guidance,
    model="gemini-2.5-pro",  # or "gemini-2.5-flash" for speed
)
#%% md
# # Step 4
# - Output Track changes docx file
# - Output edited docx file
#%%
count = Tr_clean.apply_cleaned_findings_to_docx(docx_path, cleaned, "AI_Reviewed_PrjStern.docx")
#%%
n = Tr_clean.replace_cleaned_findings_in_docx(
    input_docx="NDAs md/NDA Project Stern clean.docx",
    cleaned_findings=cleaned,
    output_docx="AI_edited_Stern.docx",
    ignore_case=False,
    skip_if_same=True,
)
#%%
