"""
Policies Playbook Display Module
Contains the complete NDA policies for display in the application
"""

import streamlit as st

def display_policies_playbook():
    """Display the policies playbook with expandable sections"""
    
    # Header with Edit Playbook button
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.header("📋 Strada's NDA Playbook")
    
    with col2:
        if st.button("✏️ Edit Playbook", key="edit_playbook_access", use_container_width=True):
            st.session_state.current_page = "edit_playbook"
            st.rerun()
    
    st.markdown("""
    This comprehensive playbook outlines Strada's policies for NDA review and compliance.
    *Policies are grouped by **High**, **Medium**, or **Low** priority.*
    """)
    
    # Golden Rule
    with st.expander("🌟 Golden Rule of NDA Review", expanded=True):
        st.markdown("""
        **As a guiding principle, Strada prefers concise and focused NDAs.**
        
        Every clause introduces a potential obligation or restriction; fewer clauses mean 
        **greater operational freedom** and **lower contractual risk**.
        
        When reviewing, **question whether each clause is truly necessary**.
        
        If language is problematic, soften it where possible—outright deletion is a last resort.
        
        Conversely, **never add extra clauses** (e.g., a "No Commitment" clause) just because 
        we like them; the fewer promises we make, the better.
        """)
    
    st.markdown("---")
    
    # HIGH PRIORITY
    st.subheader("🔴 HIGH PRIORITY")
    st.markdown("*These policies address the most critical issues that must be resolved.*")
    
    with st.expander("POLICY 1: Handling of Unacceptable Clauses"):
        st.markdown("""
        **A. Prohibited Clauses (Must Be Removed)**
        - Any requirement for Strada to pay **indirect, consequential, special, or punitive damages**
        - Any **penalty or liquidated-damages** clause specifying a fixed sum per breach (e.g., €50 000). References to specific monetary amounts must always be deleted.
        - **Non-competition** clauses
        - Clauses that **transfer or license intellectual-property rights**
        
        **B. Restricted Clause (Must Be Modified)**
        - **Non-Solicitation of Clients/Customers** → add an exception for pre-existing relationships
        
        **Approved Language:**
        - **Liability:** "Liability for a breach of this Agreement shall be limited to proven, direct damages. In no event shall either party be liable for any indirect, consequential, special, punitive, or incidental damages, or for any loss of profits, revenue, or data."
        - **IP:** "No provision in this Agreement shall be construed as granting any license or rights, by implication, estoppel, or otherwise, to any intellectual property of either party."
        - **Non-Solicitation of Clients/Customers:** "… except for contacts that were already established in the ordinary course of business."
        """)
    
    with st.expander("POLICY 2: Permitted Recipients (Disclosees)"):
        st.markdown("""
        - Definition of "Representatives" must ideally cover our **directors, employees, affiliates, shareholders, potential syndicate members, other finance providers, and professional advisers**
        - Adherence Letters: If potential finance providers or advisers are excluded from the definition of "Disclosees" or "Representatives", we must ensure they sign an Adherence Letter to the NDA before we share information with them
        - Any clause forcing Strada to **act alone** or prohibiting consortiums **must be deleted**
        
        **Approved Language:**
        "Confidential Information may be disclosed by the Recipient to its affiliates and their respective directors, officers, employees, consultants, advisers, shareholders, potential syndicate members, agents, representatives, and other providers of financing (collectively, 'Representatives'), who need to know such information for the Purpose, provided the Recipient remains responsible for any breach of this Agreement by its Representatives."
        """)
    
    with st.expander("POLICY 3: Return & Destruction of Information"):
        st.markdown("""
        - The NDA **must not require absolute destruction**
        - Must allow retention on **automated backups**, in **internal work product** ("Secondary Information"), and for **legal / regulatory compliance**, all subject to confidentiality
        
        **Approved Language:**
        "Upon the Disclosing Party's written request, the Recipient shall return or destroy all Confidential Information. However, this obligation shall not apply to:
        (i) Confidential Information the Recipient or its Representatives must retain under applicable law, rule, or regulation;
        (ii) Confidential Information saved to electronic media under automatic archiving or data-security procedures; and
        (iii) reports, notes, or other materials prepared by or on behalf of the Recipient that incorporate Confidential Information ('Secondary Information').
        Any material not returned or destroyed remains subject to this Agreement's confidentiality obligations."
        """)
    
    with st.expander("POLICY 4: Non-Solicitation of Employees"):
        st.markdown("""
        The clause must:
        - Be for a term of no more than two (2) years
        - **Not** apply to Strada's affiliates or portfolio companies
        - Exempt hires resulting from generalised searches or advertisements and unsolicited applications
        
        **Approved Language:**
        "For a period of one/two (1/2) year(s) from the date of this Agreement, the Recipient agrees not to directly solicit for employment any employee of the Disclosing Party with whom the Recipient had material contact in connection with the Purpose. This restriction shall not apply to any of the Recipient's affiliated portfolio companies, nor to employees who respond to public advertisements, make unsolicited applications, are referred by an unaffiliated recruiter, or whose employment commences more than six (6) months after the date of this Agreement."
        """)
    
    with st.expander("POLICY 5: No-Solicitation of Key Business Relationships"):
        st.markdown("""
        - Term **may not exceed two (2) years**
        - Restriction limited to soliciting the counterparty's **key representatives** (e.g., investment managers)
        - Do **not** flag if the term ≤ 2 years
        
        **Approved Language:**
        "For a period of one/two (1/2) year(s) from the date of this Agreement, the Recipient agrees not to solicit any representative or investment manager of the Disclosing Party with whom it had contact in relation to the Purpose, nor to persuade any such person to terminate or adversely alter their relationship with the Disclosing Party."
        """)
    
    st.markdown("---")
    
    # MEDIUM PRIORITY
    st.subheader("🟡 MEDIUM PRIORITY")
    st.markdown("*These policies address important issues that should be resolved when possible.*")
    
    with st.expander("POLICY 6: No-Contact with Stakeholders"):
        st.markdown("""
        - **Scope Limitation:** Only the counterparty's **directors, officers, or employees directly involved in the transaction**. Broader lists (customers, suppliers, etc.) must allow pre-existing relationships
        - **Business Exception:** Must allow contact in the **ordinary course of business**
        
        **Approved Language:**
        "Without the prior written consent of the Disclosing Party, the Recipient agrees not to contact any directors, officers, or employees of the Disclosing Party in connection with the Purpose. This restriction shall not be breached by contact made for another purpose than evaluating or negotiating the Proposed Transaction."
        """)
    
    with st.expander("POLICY 7: No Third-Party Beneficiaries"):
        st.markdown("""
        - The NDA **must not grant enforceable rights** to non-signatories
        - Delete references to affiliates as beneficiaries or legislation (e.g., UK Contracts (Rights of Third Parties) Act 1999)
        """)
    
    with st.expander("POLICY 8: 'No Commitment to Invest' Clauses"):
        st.markdown("""
        - **Optional**. If absent, **do nothing**
        - If present, ensure language is acceptable:
        
        "The parties acknowledge that this Agreement and the exchange of Confidential Information create no obligation to enter into any further agreement or transaction, including any investment, partnership, or joint venture."
        """)
    
    with st.expander("POLICY 9: Assignment of Agreement"):
        st.markdown("""
        - NDA must **not prohibit Strada from assigning its rights**
        - Ideal: each party may assign to **affiliates**; silence is acceptable; one-sided restriction is not
        
        **Approved Language:**
        "Each party may assign or transfer its rights and obligations under this Agreement to any of its affiliates without the prior written consent of the other party."
        """)
    
    with st.expander("POLICY 10: Omission of Redundant Legal Acknowledgements"):
        st.markdown("""
        - Remove clauses that merely restate pre-existing legal duties (e.g., insider-trading laws)
        - These add no value and clutter the agreement
        """)
    
    st.markdown("---")
    
    # LOW PRIORITY
    st.subheader("🟢 LOW PRIORITY")
    st.markdown("*These policies address preferences that can be addressed if time permits.*")
    
    with st.expander("POLICY 11: Governing Law & Jurisdiction"):
        st.markdown("""
        - Preference: **Belgian law**; exclusive courts of **Antwerp, Belgium**
        - Acceptable fall-backs (in order):
          1. Another European jurisdiction
        - Non-European jurisdictions should be **flagged**
        
        **Approved Language:**
        "This Agreement, and any contractual or non-contractual obligations arising out of or in connection with it, shall be governed by and construed in accordance with the laws of Belgium. Any disputes arising out of or in connection with this Agreement shall be submitted to the exclusive jurisdiction of the competent courts in Antwerp, division Antwerp, Belgium."
        """)
    
    with st.expander("POLICY 12: Confidentiality Term"):
        st.markdown("""
        - Preferred term: **2 years** (maximum **3 years**)
        - Term must be explicit
        
        **Approved Language:**
        "The obligations of confidentiality set out in this letter shall continue in full force and effect until the earlier of: (i) successful completion of the Project; and (ii) the date that is two or three (2 or 3) years from the date of this Agreement. This obligation shall survive the termination or expiration of any other provision of this Agreement."
        """)
    
    with st.expander("POLICY 13: Liability for Representatives"):
        st.markdown("""
        - Aim to limit Strada's liability for Representatives using an **efforts-based standard** (not strict)
        
        **Approved Language:**
        "The Recipient will use its best efforts to procure that each of its Representatives who receives any Confidential Information is aware of and adheres to the terms of this Agreement. The Recipient shall be responsible for any breach of the confidentiality obligations of this Agreement by its Representatives."
        """)
    
    with st.expander("POLICY 14: Definition of Confidential Information"):
        st.markdown("""
        - Definition should include **standard market exceptions**
        
        **Approved Language:**
        "Confidential Information does not include information that:
        (a) is or becomes generally available to the public through no breach by Recipient of the confidentiality undertakings hereunder;
        (b) was in Recipient's lawful possession before receipt from Discloser, without any obligation of confidentiality;
        (c) was received in good faith by Recipient from a third party not under an obligation of confidentiality to Discloser; or
        (d) was disclosed by Recipient with the written permission of an authorized representative of the Discloser."
        """)
    
    st.markdown("---")
    
    # Footer
    st.info("""
    **Note:** This playbook is designed to ensure consistency in NDA review processes. 
    Always consult with legal counsel for complex situations or when in doubt about specific provisions.
    """)
    st.markdown("*Last updated: January 2025*")