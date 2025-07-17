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
    - This comprehensive playbook outlines Strada's policies for NDA review and compliance.
    *Policies are grouped by **High**, **Medium**, or **Low** priority.*
    - Click on "✏️ Edit Playbook" to edit the playbook for future analysis in this session.
    ---
    
    """)
    
    # Golden Rule
    with st.expander("🌟 Golden Rule of NDA Review", expanded=False):
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
        **A. Prohibited Clauses (Must Be Removed)** The NDA must **NOT** contain any of the following:

        - A requirement for Strada to compensate for **indirect, consequential, special, or punitive damages**.
        - A **penalty or liquidated damages clause** that specifies a fixed monetary amount per breach (e.g., €500,000 per infringement). A general damages clause is acceptable.
        - A **non-competition** clause.
        - Any clause that explicitly or implicitly **transfers or licenses intellectual property rights**.

        **B. Restricted Clauses (Must Be Modified)** The following clause is permissible **only if modified** as described:

        - **Clause:** Non-Solicitation of Clients/Customers.
        - **Required Modification:** The clause must be amended to include an exception for pre-existing relationships.

        **Approved Language:**
        - **Liability:** "Liability for a breach of this Agreement shall be limited to proven, direct damages. In no event shall either party be liable for any indirect, consequential, special, punitive, or incidental damages, or for any loss of profits, revenue, or data."
        - **IP:** "No provision in this Agreement shall be construed as granting any license or rights, by implication, estoppel or otherwise, to any intellectual property of either party."
        - **Non-Solicitation of Clients/Customers:** Add: "..except for contacts that were already established in the ordinary course of business."
        """)
    
    with st.expander("POLICY 2: Permitted Recipients (Disclosees)"):
        st.markdown("""
        - **Rule:** The definition of who can receive information ("Representatives") must be broad enough to include Strada's directors, employees, affiliates, shareholders, potential syndicate members, other providers of finance, and professional advisers. Any clause requiring Strada to **act alone** or **prohibiting consortiums must be deleted**.

        - **Approved Language:** "Confidential Information may be disclosed by the Recipient to its affiliates and its and their respective directors, officers, employees, consultants, advisers, shareholders, potential syndicate members, agents, representatives, and other providers of financing (collectively, "Representatives"), who need to know such information for the Purpose, provided that the Recipient shall be responsible for any breach of this Agreement by its Representatives."
        """)
    
    with st.expander("POLICY 3: Return & Destruction of Information"):
        st.markdown("""
        - **Rule:** The NDA must not require the **absolute destruction** of information. It must explicitly permit retention of information stored on **automated backup systems**, contained in **internal work product** ("Secondary Information"), and required for **legal/regulatory compliance**, provided it all remains subject to confidentiality obligations.

        - **Approved Language:** "Upon the Disclosing Party's written request, the Recipient shall return or destroy all Confidential Information. However, this obligation shall not apply to: (i) Confidential Information that the Recipient or its Representatives must retain under any applicable law, rule or regulation, including the rules of a professional body and good corporate governance practice; (ii) Confidential Information and elaborations thereof as have been saved to electronic carriers under automatic archiving or data security procedures; and (iii) reports, notes or other materials prepared by or on behalf of the Recipient which incorporate Confidential Information ('Secondary Information'). Any Confidential Information or Secondary Information that is not returned or destroyed shall remain subject to the confidentiality terms of this Agreement."
        """)
    
    with st.expander("POLICY 4: Non-Solicitation of Employees"):
        st.markdown("""
        - **Rule:** A non-solicitation clause must meet **all** of the following criteria:
          - The term must **not exceed two (2) years**.
          - It must **NOT apply** to Strada's affiliated entities or portfolio companies.
          - It must explicitly exempt hiring individuals who respond to general, non-targeted advertisements or make unsolicited applications. This exemption must apply to all employees, including management.

        - **Approved Language:** "For a period of one/two (1/2) year from the date of this Agreement, the Recipient agrees not to directly solicit for employment any employee of the Disclosing Party with whom the Recipient had material contact in connection with the Purpose. This restriction shall not apply to any of the Recipient's affiliated portfolio companies, nor shall it apply to employees who respond to general public advertisements, make an unsolicited application for employment, are referred by a third-party recruiter who was not instructed to target the Disclosing Party's employees, or whose employment was terminated by the Disclosing Party. An exception for a 'bona fide recruitment campaign' is also acceptable."
        """)
    
    with st.expander("POLICY 5: No-Solicitation of Key Business Relationships"):
        st.markdown("""
        - **Rule:** For a period **not to exceed two (2) years**, the Recipient may agree not to solicit the counterparty's key representatives (e.g., investment managers) with the intent to harm the business relationship. This is a narrow alternative to a prohibited non-solicit of all customers/suppliers.

        - **Note:** If the term in the agreement does not exceed two years, do not flag the clause.
        - **Approved Language:** "For a period of one/two (1/2) year from the date of this Agreement, the Recipient agrees not to solicit any representative or investment manager of the Disclosing Party with whom it had contact in relation to the Purpose, and agrees not to persuade any such representative or investment manager to terminate or adversely alter its relationship with the Disclosing Party."
        """)
    
    st.markdown("---")
    
    # MEDIUM PRIORITY
    st.subheader("🟡 MEDIUM PRIORITY")
    st.markdown("*These policies address important issues that should be resolved when possible.*")
    
    with st.expander("POLICY 6: No-Contact with Stakeholders"):
        st.markdown("""
        - **Rule:** A "no-contact" clause must be narrowly defined and meet **both** of the following criteria:
          - **Scope Limitation:** The restriction must apply **only** to the counterparty's directors, officers, or employees directly involved in the transaction. Any clause restricting contact with customers, suppliers, former employees, lenders, or shareholders must be softened to allow for pre-existing relationships (e.g., "except for contacts that existed already in the ordinary course of business").
          - **Business Exception:** The clause must contain a clear exception for contact made in the **ordinary course of business**, unrelated to the transaction.

        - **Approved Language:** "Without the prior written consent of the Disclosing Party, the Recipient agrees not to contact any directors, officers, or employees of the Disclosing Party in connection with the Purpose. This restriction shall not be breached by any contact made for another purpose than the purpose of evaluating and negotiating the Proposed Transaction."

        - **Rationale:** Overly broad no-contact clauses create significant operational risk. This policy ensures the restriction is tightly focused on its legitimate purpose without hampering normal business operations.
        """)
    
    with st.expander("POLICY 7: No Third-Party Beneficiaries"):
        st.markdown("""
        - **Rule:** The agreement must **not grant enforceable rights** to any entity that is not a signatory to the contract.

        - **Guidance:** Clauses stating that a party's "affiliates" are "third-party beneficiaries" should be deleted. Similarly, any reference to specific legislation granting such rights (e.g., the UK's Contracts (Rights of Third Parties) Act 1999) must be removed to clarify that only the parties to the agreement can enforce its terms.
        """)
    
    with st.expander("POLICY 8: \"No Commitment to Invest\" Clauses"):
        st.markdown("""
        - **Guideline:** This clause is **optional**. If the NDA does not contain a 'No Commitment' clause, it is acceptable and no action is needed. **Do not add one**.

        - **Action:** If the other party's NDA already includes such a clause, it is safe to accept. Ensure the language is similar to the approved text below.

        - **Standard Language (Safe to Accept):** "The parties acknowledge that this Agreement and the exchange of Confidential Information do not create any obligation to enter into any further agreement or transaction, including but not limited to any investment, partnership, or joint venture."
        """)
    
    with st.expander("POLICY 9: Assignment of Agreement"):
        st.markdown("""
        - **Rule:** The NDA must **not prohibit Strada from assigning its rights**. The preferred position is a mutual right for either party to assign the agreement to its affiliates. A silent clause is acceptable; a one-sided restriction is not.

        - **Approved Language:** "Each party may assign or transfer its rights and obligations under this Agreement to any of its affiliates without the prior written consent of the other party."
        """)
    
    with st.expander("POLICY 10: Omission of Redundant Legal Acknowledgements"):
        st.markdown("""
        - **Rule:** The NDA should not contain clauses where a party formally acknowledges existing legal obligations (e.g., under market abuse or insider trading laws).

        - **Guidance:** These clauses are unnecessary as the underlying laws apply regardless of the contract. **Delete any such clauses** to streamline the agreement.
        """)
    
    st.markdown("---")
    
    # LOW PRIORITY
    st.subheader("🟢 LOW PRIORITY")
    st.markdown("*These policies address preferences that should be considered when feasible.*")
    
    with st.expander("POLICY 11: Governing Law & Jurisdiction"):
        st.markdown("""
        - **Preference:** **Belgian law**; exclusive courts of **Antwerp, Belgium**.
        - **Acceptable fall-backs (in order):**
          1. Another European jurisdiction.
        - **Non-European jurisdictions should be flagged**.

        **Approved Language:**
        "This Agreement, and any contractual or non-contractual obligations arising out of or in connection with it, shall be governed by and construed in accordance with the laws of Belgium. Any disputes arising out of or in connection with this Agreement shall be submitted to the exclusive jurisdiction of the competent courts in Antwerp, division Antwerp, Belgium."
        """)
    
    with st.expander("POLICY 12: Confidentiality Term"):
        st.markdown("""
        - **Rule:** The preferred confidentiality term is **two (2) years**. A term of three (3) years is the maximum acceptable length. The term must be explicitly stated.

        - **Approved Language:** "The obligations of confidentiality set out in this letter shall continue in full force and effect until the earlier of: (i) successful completion of the Project; and (ii) the date that is two or three (2 or 3) years from the date of this Agreement. This obligation shall survive the termination or expiration of any other provision of this Agreement."
        """)
    
    with st.expander("POLICY 13: Liability for Representatives"):
        st.markdown("""
        - **Rule:** The NDA should, where possible, limit Strada's liability for breaches by its external Representatives by using an **efforts-based standard** rather than one of strict liability.

        - **Approved Language:** "The Recipient will use its best efforts to procure that each of its Representatives who receives any Confidential Information is aware of and adheres to the terms of this Agreement. The Recipient shall be responsible for any breach of the confidentiality obligations of this Agreement by its Representatives."
        """)
    
    with st.expander("POLICY 14: Definition of Confidential Information"):
        st.markdown("""
        - **Rule:** The definition of "Confidential Information" should include **standard market exceptions** to clarify the scope of the obligations.

        - **Approved Language:** "Confidential Information does not include information that: (a) is or becomes generally available to the public through no breach by Recipient of the confidentiality undertakings hereunder; (b) was in Recipient's lawful possession before receipt from Discloser, without any obligation of confidentiality owed to the Discloser; (c) was received in good faith by Recipient from a third party that is not subject to an obligation of confidentiality owed to Discloser; or (d) was disclosed by Recipient pursuant to the written permission of a duly authorized representative of the Discloser."
        
        **Approved Language:**
        "Without the prior written consent of the Disclosing Party, the Recipient agrees not to contact any directors, officers, or employees of the Disclosing Party in connection with the Purpose. This restriction shall not be breached by contact made for another purpose than evaluating or negotiating the Proposed Transaction."
        """)
    

    
    st.markdown("---")
    
    # Footer
    st.info("""
    **Note:** This playbook is designed to ensure consistency in NDA review processes. 
    Always consult with legal counsel for complex situations or when in doubt about specific provisions.
    """)
    st.markdown("*Last updated: July 2025*")