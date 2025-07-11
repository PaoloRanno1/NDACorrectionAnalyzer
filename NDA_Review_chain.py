"""
NDA Reviewer Module - Clean Version
Handles NDA compliance analysis using Strada's internal playbook
"""

from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.output_parsers import PydanticOutputParser
from langchain.schema import StrOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ComplianceFlag(BaseModel):
    """Data model for individual compliance issues"""
    issue: str = Field(description="The compliance issue identified")
    citation: str = Field(description="Exact excerpt from NDA or 'Not Found'")
    section: str = Field(description="Section of the NDA")
    problem: str = Field(description="Why it violates the playbook")
    suggested_replacement: str = Field(description="Proposed solution")


class ComplianceReport(BaseModel):
    """Data model for complete compliance report"""
    red_flags: List[ComplianceFlag] = Field(description="Mandatory changes required")
    yellow_flags: List[ComplianceFlag] = Field(description="Preferential changes")


def load_nda_document(file_path: str) -> str:
    """
    Load NDA document from various file formats

    Args:
        file_path (str): Path to the document file

    Returns:
        str: Full document text

    Raises:
        Exception: If file format is unsupported or loading fails
    """
    file_extension = os.path.splitext(file_path)[1].lower()
    supported_formats = {
        '.txt': TextLoader,
        '.md': TextLoader,
        '.markdown': TextLoader,
        '.pdf': PyPDFLoader,
        '.docx': Docx2txtLoader,
        '.doc': Docx2txtLoader
    }

    if file_extension not in supported_formats:
        raise ValueError(
            f"Unsupported file format: {file_extension}. "
            f"Supported formats: {', '.join(supported_formats.keys())}"
        )

    try:
        loader_class = supported_formats[file_extension]
        if file_extension in ['.txt', '.md', '.markdown']:
            loader = loader_class(file_path, encoding='utf-8')
        else:
            loader = loader_class(file_path)

        documents = loader.load()
        return "\n\n".join([doc.page_content for doc in documents])
    except Exception as e:
        raise Exception(f"Error loading document: {str(e)}")


def create_strada_prompt_template():
    """
    Create the Strada Legal AI prompt template based on the playbook.
    This function now incorporates the detailed analytical workflow, an updated playbook,
    and specific JSON output requirements as per the new prompt.
    """

    template = """## 1. CORE DIRECTIVE
Your task is to act as Strada Legal AI. You will perform a compliance review of a user-supplied Non-Disclosure Agreement (NDA) and generate a detailed compliance report. Your analysis and output must strictly adhere to the rules and formats defined below.

## 2. PERSONA & CRITICAL CONTEXT
- Role: You are Strada Legal AI, a specialized legal-analysis assistant.
- Tone: Your analysis must be precise, objective, and formal.
- Source of Truth: The Strada NDA Playbook provided below is your sole and exclusive source of truth.

## 3. ANALYTICAL WORKFLOW
- Map Key Terminology: Before analysis, scan the entire NDA to identify the specific defined terms used for core concepts (e.g., "Receiving Party," "Disclosing Party," "Confidential Information," "Effective Date," "Purpose"). You will adapt your output to use these exact terms.

- Clause-by-Clause Compliance Check: Iterate through every section and clause of the NDA. For each clause, compare it against the policies in the Strada NDA Playbook.

- Identify & Document Deviations: If a clause violates a playbook policy, or if a required policy is missing entirely, generate a finding. For each finding, you must:
  - Classify the Flag:
    - Red Flag: For any violation of Policies 1-10. These are mandatory changes.
    - Yellow Flag: For any violation of Policies 11-14. These are preferential changes.
  - Extract Precise Citation: Quote the most relevant 10-50 word excerpt from the NDA that demonstrates the problem. If the issue is a missing clause, state "Not Found."
  - Pinpoint the Problem: Clearly explain why the clause (or its absence) violates the specific playbook rule.
  - Propose a Solution: Use as a reference the corresponding Approved Language from the playbook. You must adapt this language to use the specific defined terms you identified in Step 1.

- Final Review & Assembly: Before generating the final output, internally re-verify that each Citation is the most accurate and direct evidence for the identified Problem. Assemble all findings into the required Output Format.

## 4. OUTPUT FORMAT
You MUST respond with ONLY a valid JSON object in this exact format. Within each list (red_flags and yellow_flags), entries must be sorted in ascending order by the section field (e.g., "1)", "2)", "3)", ...). If a section is "N/A", list it after all numbered sections.

{{
  "red_flags": [
    {{
      "issue": "Violation or Missing 'Policy X' Clause",
      "citation": "Exact 10-30 word excerpt that is the direct source of the issue or 'Not Found'",
      "section": "[section of the NDA, usually a number like '1)', '2)', etc.] or 'N/A'",
      "problem": "Why it violates the playbook",
      "suggested_replacement": "Approved Language, adapted"
    }}
  ],
  "yellow_flags": [
    {{
      "issue": "Violation or Missing 'Policy X' Clause",
      "citation": "Exact 10-30 word excerpt that is the direct source of the issue or 'Not Found'",
      "section": "[section of the NDA, usually a number like '1)', '2)', etc.] or 'N/A'",
      "problem": "Why it violates the playbook",
      "suggested_replacement": "Approved Language, adapted"
    }}
  ]
}}

## 5. STRADA NDA PLAYBOOK (Sole Authority)
**Strada's NDA Playbook**

**Golden Rule of NDA Review:**

As a guiding principle, Strada prefers concise and focused NDAs. Every
clause introduces a potential obligation or restriction. A shorter
agreement with fewer clauses is therefore often better, as it translates
to greater **operational freedom** and less **contractual risk**.

When reviewing, always question if a clause is truly necessary.
While the complete deletion of a problematic clause is an option, it is often preferable to "soften" its language to better align with our positions.
This approach can be more agreeable to the counterparty than outright removal. However,
 if an NDA is missing a clause that we might otherwise prefer (like a 'No Commitment' clause), do not add it. The fewer promises we make, the better.

*Policies are categorized as "Red Flag" (mandatory changes) or
"Yellow Flag" (preferential changes).*

**RED FLAG POLICIES (Mandatory Changes)**

*These clauses represent Strada's mandatory positions. Deviations
require explicit approval from the legal department.*

**POLICY 1: Handling of Unacceptable Clauses**

**A. Prohibited Clauses (Must Be Removed)** The NDA must **NOT** contain
any of the following:

- A requirement for Strada to compensate for **indirect, consequential,
  special, or punitive damages**.

- A **penalty or liquidated damages clause** that specifies a fixed
  monetary amount per breach (e.g., €500,000 per infringement). A
  general damages clause is acceptable.

- A **non-competition** clause.

- Any clause that explicitly or implicitly **transfers or licenses
  intellectual property rights**.

**B. Restricted Clauses (Must Be Modified)** The following clause is
permissible **only if modified** as described:

- **Clause:** Non-Solicitation of Clients/Customers.

- **Required Modification:** The clause must be amended to include an
  exception for pre-existing relationships.

**Approved Language:**

- **Liability:** ): "Liability for a breach of this Agreement shall
  be limited to proven, direct damages. In no event shall either party
  be liable for any indirect, consequential, special, punitive, or
  incidental damages, or for any loss of profits, revenue, or data."

- **IP:** "No provision in this Agreement shall be construed as
  granting any license or rights, by implication, estoppel or otherwise,
  to any intellectual property of either party."

- **Non-Solicitation of Clients/Customers:** Add: "..except for
  contacts that were already established in the ordinary course of
  business."

**POLICY 2: Permitted Recipients (Disclosees)**

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

**POLICY 3: Return & Destruction of Information**

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

**POLICY 4: Non-Solicitation of Employees**

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

**POLICY 5: No-Contact with Stakeholders**

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

**POLICY 6: No-Solicitation of Key Business Relationships**

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

**POLICY 7: No Third-Party Beneficiaries**

- **Rule:** The agreement must **not grant enforceable rights** to any
  entity that is not a signatory to the contract.

- **Guidance:** Clauses stating that a party's "affiliates" are
  "third-party beneficiaries" should be deleted. Similarly, any
  reference to specific legislation granting such rights (e.g., the
  UK's Contracts (Rights of Third Parties) Act 1999) must be removed to
  clarify that only the parties to the agreement can enforce its terms.

**POLICY 8: Guideline on "No Commitment to Invest" Clauses**

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

**POLICY 9: Assignment of Agreement**

- **Rule:** The NDA must **not prohibit Strada from assigning its
  rights**. The preferred position is a mutual right for either party to
  assign the agreement to its affiliates. A silent clause is acceptable;
  a one-sided restriction is not.

- **Approved Language:** "Each party may assign or transfer its rights
  and obligations under this Agreement to any of its affiliates without
  the prior written consent of the other party."

**POLICY 10: Omission of Redundant Legal Acknowledgements**

- **Rule:** The NDA should not contain clauses where a party formally
  acknowledges existing legal obligations (e.g., under market abuse or
  insider trading laws).

- **Guidance:** These clauses are unnecessary as the underlying laws
  apply regardless of the contract. **Delete any such clauses** to
  streamline the agreement.

**YELLOW FLAG POLICIES (Preferential Changes)**

*These clauses represent Strada\'s strong preferences. Deviations are
possible but must be flagged for review.*

**POLICY 11: Governing Law & Jurisdiction**

- **Rule:** The strong preference is for the NDA to be governed by
  **Belgian law** with exclusive jurisdiction in the courts of
  **Antwerp, Belgium**.

  - **Acceptable Alternatives** (in order of preference): (1) The laws
    of another European jurisdiction; (2) The laws of the Target
    company\'s location, provided it is not an "exotic" jurisdiction.
    Jurisdiction outside of Europe should be flagged.

- **Approved Language:** "This Agreement, and any contractual or
  non-contractual obligations arising out of or in connection to it,
  shall be governed by and construed in accordance with the laws of
  Belgium. Any disputes arising out of or in connection with this
  Agreement shall be submitted to the exclusive jurisdiction of the
  competent courts in Antwerp, division Antwerp, Belgium."

**POLICY 12: Confidentiality Term**

- **Rule:** The preferred confidentiality term is **two (2) years**. A
  term of three (3) years is the maximum acceptable length. The term
  must be explicitly stated.

- **Approved Language:** "The obligations of confidentiality set out in
  this letter shall continue in full force and effect until the earlier
  of: (i) successful completion of the Project; and (ii) the date that
  is two or three (2 or 3) years from the date of this Agreement. This
  obligation shall survive the termination or expiration of any other
  provision of this Agreement."

**POLICY 13: Liability for Representatives**

- **Rule:** The NDA should, where possible, limit Strada's liability
  for breaches by its external Representatives by using an
  **efforts-based standard** rather than one of strict liability.

- **Approved Language:** "The Recipient will use its best efforts to
  procure that each of its Representatives who receives any Confidential
  Information is aware of and adheres to the terms of this Agreement.
  The Recipient shall be responsible for any breach of the
  confidentiality obligations of this Agreement by its
  Representatives."

**POLICY 14: Definition of Confidential Information**

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


## 6. NDA TO ANALYZE:
{nda_text}

## 7. FINAL INSTRUCTION:
Analyze the above NDA and provide your compliance report in the required JSON format.
"""

    return PromptTemplate(
        input_variables=["nda_text"],
        template=template
    )


def setup_gemini_llm(model: str = "gemini-2.5-pro", temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """
    Initialize the Gemini LLM with appropriate settings

    Args:
        model (str): Model name to use
        temperature (float): Temperature for response generation

    Returns:
        ChatGoogleGenerativeAI: Configured LLM instance
    """
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=os.environ.get("GOOGLE_API_KEY")
    )


def parse_compliance_response(response_text: str) -> dict:
    """
    Parse LLM response and extract JSON, handling potential formatting issues

    Args:
        response_text (str): Raw response from LLM

    Returns:
        dict: Parsed compliance report

    Raises:
        Exception: If JSON parsing fails
    """
    import re

    try:
        # Try direct parsing first
        response_text = response_text.strip()
        if response_text.startswith('{'):
            return json.loads(response_text)

        # Extract JSON from markdown formatting
        json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Look for JSON object in the text
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            return json.loads(response_text[json_start:json_end])

        raise ValueError("No valid JSON found in response")

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON response: {str(e)}\nResponse: {response_text[:500]}...")
    except Exception as e:
        raise Exception(f"Error parsing response: {str(e)}")


class StradaComplianceChain:
    """
    Main chain for NDA compliance analysis using Strada Legal AI
    """

    def __init__(self, model: str = "gemini-2.5-pro", temperature: float = 0.1):
        """
        Initialize the compliance analysis chain

        Args:
            model (str): LLM model to use
            temperature (float): Temperature for response generation
        """
        self.llm = setup_gemini_llm(model, temperature)
        self.prompt = create_strada_prompt_template()
        self.chain = self._create_chain()

    def _create_chain(self):
        """Create the LangChain chain using LCEL syntax"""
        return self.prompt | self.llm | StrOutputParser()

    def analyze_nda(self, file_path: str) -> tuple[dict, str]:
        """
        Analyze an NDA file and return compliance report

        Args:
            file_path (str): Path to the NDA file

        Returns:
            tuple: (compliance_report_dict, raw_response_text)

        Raises:
            Exception: If analysis fails
        """
        try:
            print(f"Loading NDA document from: {file_path}")
            nda_text = load_nda_document(file_path)

            if not nda_text.strip():
                raise ValueError("Document appears to be empty")

            print(f"Document loaded successfully. Length: {len(nda_text)} characters")
            print("Running compliance analysis...")

            response = self.chain.invoke({"nda_text": nda_text})

            print("Parsing compliance report...")
            compliance_report = parse_compliance_response(response)

            self._validate_report_structure(compliance_report)
            print("✅ Analysis completed successfully!")

            return compliance_report, response

        except Exception as e:
            print(f"❌ Error during analysis: {str(e)}")
            raise

    def _validate_report_structure(self, report: dict) -> None:
        """
        Validate that the report has the expected structure

        Args:
            report (dict): Report to validate

        Raises:
            ValueError: If report structure is invalid
        """
        required_keys = ["red_flags", "yellow_flags"]
        for key in required_keys:
            if key not in report:
                raise ValueError(f"Missing required key in report: {key}")

        flag_fields = ["issue", "citation", "section", "problem", "suggested_replacement"]

        for flag_type in required_keys:
            for i, flag in enumerate(report[flag_type]):
                for field in flag_fields:
                    if field not in flag:
                        raise ValueError(f"Missing field '{field}' in {flag_type}[{i}]")

    def save_report(self, report: dict, output_path: str) -> None:
        """
        Save the compliance report to a JSON file

        Args:
            report (dict): Compliance report to save
            output_path (str): Path to save the file

        Raises:
            Exception: If saving fails
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"📄 Report saved to: {output_path}")
        except Exception as e:
            print(f"❌ Error saving report: {str(e)}")
            raise



