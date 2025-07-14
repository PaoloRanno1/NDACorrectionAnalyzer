"""
NDA Reviewer Module - Clean Version
Handles NDA compliance analysis using Strada's internal playbook
"""

from langchain.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
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
    high_priority: List[ComplianceFlag] = Field(description="High priority changes required")
    medium_priority: List[ComplianceFlag] = Field(description="Medium priority changes")
    low_priority: List[ComplianceFlag] = Field(description="Low priority changes")


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
  - Classify the Issue:
    - High Priority: For any violation of Policies 1-5. These are mandatory changes.
    - Medium Priority: For any violation of Policies 6-10. These are preferential changes.
    - Low Priority: For any violation of Policies 11-14. These are optional changes.
  - Extract Precise Citation: Quote the most relevant 10-50 word excerpt from the NDA that demonstrates the problem. If the issue is a missing clause, state "Not Found."
  - Pinpoint the Problem: Clearly explain why the clause (or its absence) violates the specific playbook rule.
  - Propose a Solution: Use as a reference the corresponding Approved Language from the playbook. You must adapt this language to use the specific defined terms you identified in Step 1.

- Final Review & Assembly: Before generating the final output, internally re-verify that each Citation is the most accurate and direct evidence for the identified Problem. Assemble all findings into the required Output Format.

## 4. OUTPUT FORMAT
You MUST respond with ONLY a valid JSON object in this exact format. Within each list (High Priority, Medium Priority, Low Priority), entries must be sorted in ascending order by the section field (e.g., "1)", "2)", "3)", ...). If a section is "N/A", list it after all numbered sections.

{{
  "High Priority": [
    {{
      "issue": "Violation or Missing 'Policy X' Clause",
      "citation": "Exact 10-30 word excerpt that is the direct source of the issue or 'Not Found'",
      "section": "[section of the NDA, usually a number like '1)', '2)', etc.] or 'N/A'",
      "problem": "Why it violates the playbook",
      "suggested_replacement": "Approved Language, adapted"
    }}
  ],
  "Medium Priority": [
    {{
      "issue": "Violation or Missing 'Policy X' Clause",
      "citation": "Exact 10-30 word excerpt that is the direct source of the issue or 'Not Found'",
      "section": "[section of the NDA, usually a number like '1)', '2)', etc.] or 'N/A'",
      "problem": "Why it violates the playbook",
      "suggested_replacement": "Approved Language, adapted"
    }}
  ],
  "Low Priority": [
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
# Strada's NDA Playbook  
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
- **Liability:** "Liability for a breach of this Agreement shall be limited to proven, direct damages. In no event shall either party be liable for any indirect, consequential, special, punitive, or incidental damages, or for any loss of profits, revenue, or data."  
- **IP:** "No provision in this Agreement shall be construed as granting any license or rights, by implication, estoppel, or otherwise, to any intellectual property of either party."  
- **Non-Solicitation of Clients/Customers:** "… except for contacts that were already established in the ordinary course of business."
---
### **POLICY 2: Permitted Recipients (Disclosees)**  
- Definition of "Representatives" must ideally cover our **directors, employees, affiliates, shareholders, potential syndicate members, other finance providers, and professional advisers**.  
-Adherence Letters: If potential finance providers or advisers are excluded from the definition of "Disclosees" or "Representatives", we must ensure they sign an Adherence Letter to the NDA before we share information with them.
- Any clause forcing Strada to **act alone** or prohibiting consortiums **must be deleted**.
**Approved Language**  
"Confidential Information may be disclosed by the Recipient to its affiliates and their respective directors, officers, employees, consultants, advisers, shareholders, potential syndicate members, agents, representatives, and other providers of financing (collectively, 'Representatives'), who need to know such information for the Purpose, provided the Recipient remains responsible for any breach of this Agreement by its Representatives."


---

### **POLICY 3: Return & Destruction of Information**  
- The NDA **must not require absolute destruction**.  
- Must allow retention on **automated backups**, in **internal work product** ("Secondary Information"), and for **legal / regulatory compliance**, all subject to confidentiality.
**Approved Language**  
"Upon the Disclosing Party's written request, the Recipient shall return or destroy all Confidential Information. However, this obligation shall not apply to:  
(i) Confidential Information the Recipient or its Representatives must retain under applicable law, rule, or regulation;  
(ii) Confidential Information saved to electronic media under automatic archiving or data-security procedures; and  
(iii) reports, notes, or other materials prepared by or on behalf of the Recipient that incorporate Confidential Information ('Secondary Information').  
Any material not returned or destroyed remains subject to this Agreement's confidentiality obligations."
---
### **POLICY 4: Non-Solicitation of Employees**  
The clause must:  
- Be for a term of no more than two (2) years.
- **Not** apply to Strada's affiliates or portfolio companies.  
- Exempt hires resulting from generalised searches or advertisements and unsolicited applications.
**Approved Language**  
"For a period of one/two (1/2) year(s) from the date of this Agreement, the Recipient agrees not to directly solicit for employment any employee of the Disclosing Party with whom the Recipient had material contact in connection with the Purpose. This restriction shall not apply to any of the Recipient's affiliated portfolio companies, nor to employees who respond to public advertisements, make unsolicited applications, are referred by an unaffiliated recruiter, or whose employment was terminated by the Disclosing Party. An exception for a 'bona fide recruitment campaign' is also acceptable."
---
### **POLICY 5: No-Solicitation of Key Business Relationships**  
- Term **may not exceed two (2) years**.  
- Restriction limited to soliciting the counterparty's **key representatives** (e.g., investment managers).  
- Do **not** flag if the term ≤ 2 years.
**Approved Language**  
"For a period of one/two (1/2) year(s) from the date of this Agreement, the Recipient agrees not to solicit any representative or investment manager of the Disclosing Party with whom it had contact in relation to the Purpose, nor to persuade any such person to terminate or adversely alter their relationship with the Disclosing Party."
---
## MEDIUM PRIORITY  

### **POLICY 6: No-Contact with Stakeholders**  
- **Scope Limitation:** Only the counterparty's **directors, officers, or employees directly involved in the transaction**. Broader lists (customers, suppliers, etc.) must allow pre-existing relationships.  
- **Business Exception:** Must allow contact in the **ordinary course of business**.
**Approved Language**  
"Without the prior written consent of the Disclosing Party, the Recipient agrees not to contact any directors, officers, or employees of the Disclosing Party in connection with the Purpose. This restriction shall not be breached by contact made for another purpose than evaluating or negotiating the Proposed Transaction."
---
### **POLICY 7: No Third-Party Beneficiaries**  
- The NDA **must not grant enforceable rights** to non-signatories.  
- Delete references to affiliates as beneficiaries or legislation (e.g., UK Contracts (Rights of Third Parties) Act 1999).
---
### **POLICY 8: "No Commitment to Invest" Clauses**  
- **Optional**. If absent, **do nothing**.  
- If present, ensure language is acceptable:
> "The parties acknowledge that this Agreement and the exchange of Confidential Information create no obligation to enter into any further agreement or transaction, including any investment, partnership, or joint venture."
---
### **POLICY 9: Assignment of Agreement**  
- NDA must **not prohibit Strada from assigning its rights**.  
- Ideal: each party may assign to **affiliates**; silence is acceptable; one-sided restriction is not.
**Approved Language**  
"Each party may assign or transfer its rights and obligations under this Agreement to any of its affiliates without the prior written consent of the other party."
---
### **POLICY 10: Omission of Redundant Legal Acknowledgements**  
- Remove clauses that merely restate pre-existing legal duties (e.g., insider-trading laws).  
- These add no value and clutter the agreement.

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
- Preferred term: **2 years** (maximum **3 years**).  
- Term must be explicit.
**Approved Language**  
"The obligations of confidentiality set out in this letter shall continue in full force and effect until the earlier of: (i) successful completion of the Project; and (ii) the date that is two or three (2 or 3) years from the date of this Agreement. This obligation shall survive the termination or expiration of any other provision of this Agreement."
---

### **POLICY 13: Liability for Representatives**  

- Aim to limit Strada's liability for Representatives using an **efforts-based standard** (not strict).
**Approved Language**  
"The Recipient will use its best efforts to procure that each of its Representatives who receives any Confidential Information is aware of and adheres to the terms of this Agreement. The Recipient shall be responsible for any breach of the confidentiality obligations of this Agreement by its Representatives."
---
### **POLICY 14: Definition of Confidential Information**  
- Definition should include **standard market exceptions**.
**Approved Language**  
"Confidential Information does not include information that:  
(a) is or becomes generally available to the public through no breach by Recipient of the confidentiality undertakings hereunder;  
(b) was in Recipient's lawful possession before receipt from Discloser, without any obligation of confidentiality;  
(c) was received in good faith by Recipient from a third party not under an obligation of confidentiality to Discloser; or  
(d) was disclosed by Recipient with the written permission of an authorized representative of the Discloser."
---

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
            try:
                compliance_report = parse_compliance_response(response)
            except Exception as parse_error:
                print(f"⚠️ JSON parsing failed: {str(parse_error)}")
                # Return a fallback structure with the raw response
                compliance_report = {
                    "High Priority": [{
                        "issue": "JSON Parsing Error",
                        "citation": "Unable to parse AI response",
                        "section": "Response Processing",
                        "problem": f"The AI response could not be parsed as valid JSON. Raw response: {response[:200]}...",
                        "suggested_replacement": "Please retry the analysis"
                    }],
                    "Medium Priority": [],
                    "Low Priority": []
                }

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
        required_keys = ["High Priority", "Medium Priority", "Low Priority"]
        for key in required_keys:
            if key not in report:
                raise ValueError(f"Missing required key in report: {key}")

            if not isinstance(report[key], list):
                raise ValueError(f"Key {key} must be a list")

            # Validate each item in the list
            for item in report[key]:
                required_item_keys = ["issue", "citation", "section", "problem", "suggested_replacement"]
                for item_key in required_item_keys:
                    if item_key not in item:
                        raise ValueError(f"Missing required key in {key} item: {item_key}")

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