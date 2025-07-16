"""
Playbook Manager Module
Handles dynamic playbook content for NDA analysis
"""

import streamlit as st

# Default playbook content
DEFAULT_PLAYBOOK = """# Strada's NDA Playbook  
*Policies are grouped by **High**, **Medium**, or **Low** priority.*

---

## Golden Rule of NDA Review  

As a guiding principle, **Strada prefers concise and focused NDAs**.  
Every clause introduces a potential obligation or restriction; fewer clauses mean **greater operational freedom** and **lower contractual risk**.  
When reviewing, **question whether each clause is truly necessary**.  
If language is problematic, soften it where possible—outright deletion is a last resort.  
Conversely, **never add extra clauses** (e.g., a "No Commitment" clause) just because we like them; the fewer promises we make, the better.

---

## HIGH PRIORITY  

### **POLICY 1: Handling of Unacceptable Clauses**  

**A. Prohibited Clauses (Must Be Removed)**  
- Any requirement for Strada to pay **indirect, consequential, special, or punitive damages**.  
- Any **penalty or liquidated-damages** clause specifying a fixed sum per breach (e.g., €50 000).  References to specific monetary amounts must always be deleted.
- **Non-competition** clauses.  
- Clauses that **transfer or license intellectual-property rights**.
**B. Restricted Clause (Must Be Modified)**  
- **Non-Solicitation of Clients/Customers** → add an exception for pre-existing relationships.
**Approved Language**  
- **Liability:** “Liability for a breach of this Agreement shall be limited to proven, direct damages. In no event shall either party be liable for any indirect, consequential, special, punitive, or incidental damages, or for any loss of profits, revenue, or data.”  
- **IP:** “No provision in this Agreement shall be construed as granting any license or rights, by implication, estoppel, or otherwise, to any intellectual property of either party.”  
- **Non-Solicitation of Clients/Customers:** “… except for contacts that were already established in the ordinary course of business.”

---

### **POLICY 2: Permitted Recipients (Disclosees)**  
- **Rule:** The definition of who can receive information
  ("Representatives") must be broad enough to include Strada's
  directors, employees, affiliates, shareholders, potential syndicate
  members, other providers of finance, and professional advisers. Any
  clause requiring Strada to **act alone** or **prohibiting consortiums
  must be deleted**.

- **Approved Language:** "Confidential Information may be disclosed by
  the Recipient to its affiliates and its and their respective
  directors, officers, employees, consultants, advisers, shareholders,
  potential syndicate members, agents, representatives, and other
  providers of financing (collectively, "Representatives"), who need
  to know such information for the Purpose, provided that the Recipient
  shall be responsible for any breach of this Agreement by its
  Representatives."

---

### **POLICY 3: Return & Destruction of Information**  
- **Rule:** The NDA must not require the **absolute destruction** of
  information. It must explicitly permit retention of information stored
  on **automated backup systems**, contained in **internal work
  product** ("Secondary Information"), and required for
  **legal/regulatory compliance**, provided it all remains subject to
  confidentiality obligations.

- **Approved Language:** "Upon the Disclosing Party's written request,
  the Recipient shall return or destroy all Confidential Information.
  However, this obligation shall not apply to: (i) Confidential
  Information that the Recipient or its Representatives must retain
  under any applicable law, rule or regulation, including the rules of a
  professional body and good corporate governance practice; (ii)
  Confidential Information and elaborations thereof as have been saved
  to electronic carriers under automatic archiving or data security
  procedures; and (iii) reports, notes or other materials prepared by or
  on behalf of the Recipient which incorporate Confidential Information
  ('Secondary Information'). Any Confidential Information or Secondary
  Information that is not returned or destroyed shall remain subject to
  the confidentiality terms of this Agreement."

---

### **POLICY 4: Non-Solicitation of Employees**  
- **Rule:** A non-solicitation clause must meet **all** of the following
  criteria:

  - The term must **not exceed two (2) years**.

  - It must **NOT apply** to Strada's affiliated entities or portfolio
    companies.

  - It must explicitly exempt hiring individuals who respond to general,
    non-targeted advertisements or make unsolicited applications. This
    exemption must apply to all employees, including management.

- **Approved Language:** "For a period of one/two (1/2) year from the
  date of this Agreement, the Recipient agrees not to directly solicit
  for employment any employee of the Disclosing Party with whom the
  Recipient had material contact in connection with the Purpose. This
  restriction shall not apply to any of the Recipient's affiliated
  portfolio companies, nor shall it apply to employees who respond to
  general public advertisements, make an unsolicited application for
  employment, are referred by a third-party recruiter who was not
  instructed to target the Disclosing Party's employees, or whose
  employment was terminated by the Disclosing Party. An exception for a
  'bona fide recruitment campaign' is also acceptable."

---

### **POLICY 5: No-Solicitation of Key Business Relationships**  
- **Rule:** For a period **not to exceed two (2) years**, the Recipient
  may agree not to solicit the counterparty's key representatives
  (e.g., investment managers) with the intent to harm the business
  relationship. This is a narrow alternative to a prohibited non-solicit
  of all customers/suppliers.

- **Note:** If the term in the agreement does not exceed two years, do
  not flag the clause.
- **Approved Language:** "For a period of one/two (1/2) year from the
  date of this Agreement, the Recipient agrees not to solicit any
  representative or investment manager of the Disclosing Party with whom
  it had contact in relation to the Purpose, and agrees not to persuade
  any such representative or investment manager to terminate or
  adversely alter its relationship with the Disclosing Party."
---

## MEDIUM PRIORITY  

### **POLICY 6: No-Contact with Stakeholders**  
- **Rule:** A "no-contact" clause must be narrowly defined and meet
  **both** of the following criteria:

  - **Scope Limitation:** The restriction must apply **only** to the
    counterparty's directors, officers, or employees directly involved
    in the transaction. Any clause restricting contact with customers,
    suppliers, former employees, lenders, or shareholders must be
    softened to allow for pre-existing relationships (e.g., "except for
    contacts that existed already in the ordinary course of business").

  - **Business Exception:** The clause must contain a clear exception
    for contact made in the **ordinary course of business**, unrelated
    to the transaction.

- **Approved Language:** "Without the prior written consent of the
  Disclosing Party, the Recipient agrees not to contact any directors,
  officers, or employees of the Disclosing Party in connection with the
  Purpose. This restriction shall not be breached by any contact made
  for another purpose than the purpose of evaluating and negotiating the
  Proposed Transaction."

- **Rationale:** Overly broad no-contact clauses create significant
  operational risk. This policy ensures the restriction is tightly
  focused on its legitimate purpose without hampering normal business
  operations.

---

### **POLICY 7: No Third-Party Beneficiaries**  
- **Rule:** The agreement must **not grant enforceable rights** to any
  entity that is not a signatory to the contract.

- **Guidance:** Clauses stating that a party's "affiliates" are
  "third-party beneficiaries" should be deleted. Similarly, any
  reference to specific legislation granting such rights (e.g., the
  UK's Contracts (Rights of Third Parties) Act 1999) must be removed to
  clarify that only the parties to the agreement can enforce its terms.

---

### **POLICY 8: "No Commitment to Invest" Clauses**  
- **Guideline:** This clause is **optional**. If the NDA does not
  contain a 'No Commitment' clause, it is acceptable and no action is
  needed. **Do not add one**.

- **Action:** If the other party's NDA already includes such a clause,
  it is safe to accept. Ensure the language is similar to the approved
  text below.

- **Standard Language (Safe to Accept):** "The parties acknowledge that
  this Agreement and the exchange of Confidential Information do not
  create any obligation to enter into any further agreement or
  transaction, including but not limited to any investment, partnership,
  or joint venture."

---

### **POLICY 9: Assignment of Agreement**  
- **Rule:** The NDA must **not prohibit Strada from assigning its
  rights**. The preferred position is a mutual right for either party to
  assign the agreement to its affiliates. A silent clause is acceptable;
  a one-sided restriction is not.

- **Approved Language:** "Each party may assign or transfer its rights
  and obligations under this Agreement to any of its affiliates without
  the prior written consent of the other party."

---

### **POLICY 10: Omission of Redundant Legal Acknowledgements**  
- **Rule:** The NDA should not contain clauses where a party formally
  acknowledges existing legal obligations (e.g., under market abuse or
  insider trading laws).

- **Guidance:** These clauses are unnecessary as the underlying laws
  apply regardless of the contract. **Delete any such clauses** to
  streamline the agreement.

---

## LOW PRIORITY  

### **POLICY 11: Governing Law & Jurisdiction**  
- Preference: **Belgian law**; exclusive courts of **Antwerp, Belgium**.  
- Acceptable fall-backs (in order):  
  1. Another European jurisdiction.  
- Non-European jurisdictions should be **flagged**.

**Approved Language**  
"This Agreement, and any contractual or non-contractual obligations arising out of or in connection with it, shall be governed by and construed in accordance with the laws of Belgium. Any disputes arising out of or in connection with this Agreement shall be submitted to the exclusive jurisdiction of the competent courts in Antwerp, division Antwerp, Belgium."

---

### **POLICY 12: Confidentiality Term**  
- **Rule:** The preferred confidentiality term is **two (2) years**. A
  term of three (3) years is the maximum acceptable length. The term
  must be explicitly stated.

- **Approved Language:** "The obligations of confidentiality set out in
  this letter shall continue in full force and effect until the earlier
  of: (i) successful completion of the Project; and (ii) the date that
  is two or three (2 or 3) years from the date of this Agreement. This
  obligation shall survive the termination or expiration of any other
  provision of this Agreement."

---

### **POLICY 13: Liability for Representatives**  
- **Rule:** The NDA should, where possible, limit Strada's liability
  for breaches by its external Representatives by using an
  **efforts-based standard** rather than one of strict liability.

- **Approved Language:** "The Recipient will use its best efforts to
  procure that each of its Representatives who receives any Confidential
  Information is aware of and adheres to the terms of this Agreement.
  The Recipient shall be responsible for any breach of the
  confidentiality obligations of this Agreement by its
  Representatives."

---

### **POLICY 14: Definition of Confidential Information**  
- **Rule:** The definition of "Confidential Information" should
  include **standard market exceptions** to clarify the scope of the
  obligations.

- **Approved Language:** "Confidential Information does not include
  information that: (a) is or becomes generally available to the public
  through no breach by Recipient of the confidentiality undertakings
  hereunder; (b) was in Recipient's lawful possession before receipt
  from Discloser, without any obligation of confidentiality owed to the
  Discloser; (c) was received in good faith by Recipient from a third
  party that is not subject to an obligation of confidentiality owed to
  Discloser; or (d) was disclosed by Recipient pursuant to the written
  permission of a duly authorized representative of the Discloser."
---
"""

def get_current_playbook():
    """
    Get the current playbook content from session state or default
    
    Returns:
        str: Current playbook content
    """
    if 'custom_playbook' not in st.session_state:
        st.session_state.custom_playbook = DEFAULT_PLAYBOOK
    return st.session_state.custom_playbook

def update_playbook(new_content):
    """
    Update the playbook content in session state
    
    Args:
        new_content (str): New playbook content
    """
    st.session_state.custom_playbook = new_content

def reset_playbook():
    """Reset playbook to default content"""
    st.session_state.custom_playbook = DEFAULT_PLAYBOOK

def display_editable_playbook():
    """Display the editable playbook interface"""
    # Header with back button
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.header("✏️ Edit Playbook")
    
    with col2:
        if st.button("⬅️ Back to Policies", key="back_to_policies", use_container_width=True):
            st.session_state.current_page = "policies"
            st.rerun()
    
    st.markdown("""
    **Customize the NDA Analysis Playbook**
    
    This playbook is used by both the AI reviewer and HR compliance checker. 
    Any changes you make here will be applied to all future analyses.
    """)
    
    # Get current playbook
    current_playbook = get_current_playbook()
    
    # Display editor
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Text area for editing
        edited_playbook = st.text_area(
            "Edit Playbook Content (Markdown Format)",
            value=current_playbook,
            height=600,
            key="playbook_editor"
        )
    
    with col2:
        st.markdown("**Actions:**")
        
        # Save button
        if st.button("💾 Save Changes", use_container_width=True):
            update_playbook(edited_playbook)
            st.success("✅ Playbook updated successfully!")
            st.rerun()
        
        # Reset button
        if st.button("🔄 Reset to Default", use_container_width=True):
            reset_playbook()
            st.success("✅ Playbook reset to default!")
            st.rerun()
        
        # Preview button
        if st.button("👁️ Preview Changes", use_container_width=True):
            st.session_state.preview_playbook = True
    
    # Show preview if requested
    if st.session_state.get('preview_playbook', False):
        st.markdown("---")
        st.subheader("📖 Preview")
        st.markdown(edited_playbook)
        
        if st.button("❌ Close Preview"):
            st.session_state.preview_playbook = False
            st.rerun()
    
    # Show current status
    st.markdown("---")
    st.info(f"**Current Status:** {'Custom playbook active' if current_playbook != DEFAULT_PLAYBOOK else 'Using default playbook'}")
    
    # Character count
    st.caption(f"Content length: {len(edited_playbook)} characters")