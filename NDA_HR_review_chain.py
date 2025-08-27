"""
NDA Compliance Check Module - Clean Version
Analyzes NDAs with tracked changes against Strada's playbook
"""

from langchain.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import StrOutputParser
from pydantic import BaseModel, Field
from typing import List
import json
import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ComplianceFlag(BaseModel):
    """Data model for compliance change analysis"""
    issue: str = Field(description="The compliance issue identified")
    priority: str = Field(description="High, Medium, or Low priority")
    change_type: str = Field(description="Addition, Replacement, or Deletion")
    section: str = Field(description="Section of the NDA")
    citation: str = Field(description="Exact excerpt from NDA or 'Not Found'")
    problem: str = Field(description="Why it violates the playbook")


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


def create_NDA_compliance_check_template(playbook_content: str = None):
    """
    Create the prompt template based on the playbook to review the changes
    
    Args:
        playbook_content (str, optional): Custom playbook content. If None, uses default.
    """

    template = """
# Role and Goal

You are an expert legal compliance analyst AI, specializing in contract review. Your sole purpose is to analyze a Non-Disclosure Agreement (NDA) that has been modified, check the changes against Strada's internal NDA Playbook, and report any deviations in a structured JSON format.

# Context

You will be given a markdown file (`.md`) of an NDA. This document has been reviewed by an HR representative who has marked their changes as follows:

-**Additions**: Text added by HR is enclosed in double plus signs and quotes, like this: `++this text was added++`.

-**Removals**: Text removed by HR is enclosed in double minus signs and quotes, like this: `--this text was removed--`.

Your analysis MUST be based *exclusively* on the provided "Strada's NDA Playbook". This playbook is the single source of truth for determining if a change is compliant or not.

---

<<START OF PLAYBOOK>>

{playbook_content}

<<END OF PLAYBOOK>>

---

# Step-by-Step Instructions
1. **Parse the Document**: Carefully read the uploaded markdown file. Identify every instance of an addition (`++...++`) and a removal (`--...--`).

2. **Identify and Group Changes**: Scan the document to find all additions (++...++) and removals (--...--). Crucially, you must group related changes. A single logical change often consists of a removal immediately followed by an addition (a "replacement"). If you see a --...-- block directly adjacent to a ++...++ block within the same sentence or clause, you must treat them as one single change event.
A change can be one of three types:
a) Addition: A standalone ++...++ block.
b) Deletion: A standalone --...-- block.
c) Replacement: A --...-- block and a ++...++ block that work together to modify a piece of text.

3. **Analyze Each Logical Change**: For each logical change (whether it's an addition, deletion, or replacement), perform the following analysis:

a. **Identify Context**: Note the surrounding text and the section number (e.g., "1.", "2. (a)") where the change occurred.

b. **Classify against Playbook**: Compare the change to the rules in the "Strada's NDA Playbook". Determine which policy (e.g., "POLICY 4: Non-Solicitation of Employees") the change relates to.

c. **Handle Uncategorized Changes**: If a change does not directly relate to any policy in the playbook, flag it as an "Uncategorized Change".

4. **Construct JSON Output**: For each logical change identified in Step 2, create a single JSON object. The final output must be a single, valid JSON array containing all these objects.

# Output Specification
- The output MUST be JSON
- Each object in the array represents one identified logical change and must follow this exact structure:
{{
      "issue": "Descriptive title of the issue (e.g., 'Violation of High Priority Policy 1', 'Correction aligning with Medium Priority Policy 12', 'Uncategorized Change')",
      "Priority": "High, Medium, or Low [depending on the policy]",
      "change_type": "The type of change, which must be one of: 'Addition', 'Deletion', or 'Replacement'",
      "section": "The section number or identifier from the NDA where the change occurred (e.g., '1.', '2.(a)'). Use 'N/A' if there is no numbering.",
      "citation": "A string representing the change. For 'Replacements', show both the removed and added text, clearly indicating which is which (e.g., 'Original: ... New: ...'). For single additions or deletions, show the relevant text. Always include enough surrounding text for context (10-40 words).",
      "problem": "A clear and concise explanation of the logical change. If it's a replacement, explain both what was wrong with the original text and how the new text addresses it according to the playbook. For uncategorized changes, describe the nature of the change and what the HR did."
}}

## Example:
NDA text input:
"In this letter, "Affiliates" of a party means:

(a) its group undertakings; (b) its officers, employees, consultants, advisers,

++shareholders, potential syndicate members,++"

Expected JSON output:
{{
 "issue": "Compliance with High Priority Policy 2",
 "Priority": "High",
 "change_type": "Addition",
 "section": "N/A",
 "citation": "Context: '...employees, consultants, advisers, ++shareholders, potential syndicate members++'",
 "problem": "The definition of 'Representatives' was expanded to include 'shareholders, potential syndicate members'. This is a positive change that aligns with High Priority Policy 2, which requires a broad definition of who can receive confidential information."
}}

## 5. Corrected NDA to analyze:
{nda_text}

## 6. FINAL INSTRUCTION:
Analyze the above NDA and provide your report in the required JSON format.
"""

    # Use default playbook if none provided
    if playbook_content is None:
        from playbook_manager import get_current_playbook
        playbook_content = get_current_playbook()

    return PromptTemplate(
        input_variables=["nda_text", "playbook_content"],
        template=template,
        partial_variables={"playbook_content": playbook_content}
    )

def setup_gemini_llm(model: str = "gemini-2.5-pro", temperature: float = 0) -> ChatGoogleGenerativeAI:
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


def parse_compliance_response(response_text: str) -> list:
    """
    Parse LLM response and extract JSON array, handling potential formatting issues

    Args:
        response_text (str): Raw response from LLM

    Returns:
        list: Parsed compliance changes

    Raises:
        Exception: If JSON parsing fails
    """
    try:
        # Clean up the response
        response_text = response_text.strip()

        # Try direct parsing first
        if response_text.startswith('[') or response_text.startswith('{'):
            return json.loads(response_text)

        # Extract JSON from markdown formatting
        json_match = re.search(r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Look for JSON array in the text
        array_start = response_text.find('[')
        array_end = response_text.rfind(']') + 1
        if array_start != -1 and array_end > array_start:
            json_text = response_text[array_start:array_end]
            return json.loads(json_text)

        # Look for JSON object in the text
        obj_start = response_text.find('{')
        obj_end = response_text.rfind('}') + 1
        if obj_start != -1 and obj_end > obj_start:
            json_text = response_text[obj_start:obj_end]
            parsed = json.loads(json_text)
            return [parsed] if isinstance(parsed, dict) else parsed

        raise ValueError("No valid JSON found in response")

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON response: {str(e)}\nResponse: {response_text[:500]}...")
    except Exception as e:
        raise Exception(f"Error parsing response: {str(e)}")


class NDAComplianceChain:
    """
    Main chain for analyzing NDA changes against compliance requirements
    """

    def __init__(self, model: str = "gemini-2.5-pro", temperature: float = 0, playbook_content: str = None):
        """
        Initialize the compliance analysis chain

        Args:
            model (str): LLM model to use
            temperature (float): Temperature for response generation
            playbook_content (str, optional): Custom playbook content
        """
        self.llm = setup_gemini_llm(model, temperature)
        self.prompt = create_NDA_compliance_check_template(playbook_content)
        self.chain = self._create_chain()

    def _create_chain(self):
        """Create the LangChain chain using LCEL syntax"""
        return self.prompt | self.llm | StrOutputParser()

    def analyze_nda(self, file_path: str) -> tuple[list, str]:
        """
        Analyze an NDA file with tracked changes and return compliance report

        Args:
            file_path (str): Path to the NDA file with tracked changes

        Returns:
            tuple: (compliance_changes_list, raw_response_text)

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
                compliance_report = [{
                    "issue": "JSON Parsing Error",
                    "Priority": "High",
                    "change_type": "Error",
                    "section": "Response Processing",
                    "citation": "Unable to parse AI response",
                    "problem": f"The AI response could not be parsed as valid JSON. Raw response: {response[:200]}..."
                }]

            print("✅ Analysis completed successfully!")
            return compliance_report, response

        except Exception as e:
            print(f"❌ Error during analysis: {str(e)}")
            raise

    def save_report(self, report: list, output_path: str) -> None:
        """
        Save the compliance report to a JSON file

        Args:
            report (list): Compliance report to save
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