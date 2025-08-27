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


def create_strada_prompt_template(playbook_content: str = None):
    """
    Create the Strada Legal AI prompt template based on the playbook.
    This function now incorporates the detailed analytical workflow, an updated playbook,
    and specific JSON output requirements as per the new prompt.
    
    Args:
        playbook_content (str, optional): Custom playbook content. If None, uses default.
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
Regarding the suggested_replacement field, always write it in the language of the NDA.
Regarding the problem field, always write it in the language of the NDA.

{{
  "High Priority": [
    {{
      "issue": "Violation or Missing 'Policy X' Clause",
      "citation": "Exact 10-30 word excerpt that is the direct source of the issue or 'Not Found'",
      "section": "[section of the NDA, usually a number like '1)', '2)', etc.] or 'N/A'",
      "problem": "Why it violates the playbook,Always write in the language of the NDA.",
      "suggested_replacement": "Approved Language, adapted. Always write in the language of the NDA."
    }}
  ],
  "Medium Priority": [
    {{
      "issue": "Violation or Missing 'Policy X' Clause",
      "citation": "Exact 10-30 word excerpt that is the direct source of the issue or 'Not Found'",
      "section": "[section of the NDA, usually a number like '1)', '2)', etc.] or 'N/A'",
      "problem": "Why it violates the playbook,Always write in the language of the NDA.",
      "suggested_replacement": "Approved Language, adapted.Always write in the language of the NDA."
    }}
  ],
  "Low Priority": [
    {{
      "issue": "Violation or Missing 'Policy X' Clause",
      "citation": "Exact 10-30 word excerpt that is the direct source of the issue or 'Not Found'",
      "section": "[section of the NDA, usually a number like '1)', '2)', etc.] or 'N/A'",
      "problem": "Why it violates the playbook,Always write in the language of the NDA.",
      "suggested_replacement": "Approved Language, adapted.Always write in the language of the NDA."
    }}
  ]
}}

## 5. STRADA NDA PLAYBOOK (Sole Authority)
{playbook_content}

## 6. NDA TO ANALYZE:
{nda_text}

## 7. FINAL INSTRUCTION:
Analyze the above NDA and provide your compliance report in the required JSON format.
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

    def __init__(self, model: str = "gemini-2.5-pro", temperature: float = 0, playbook_content: str = None):
        """
        Initialize the compliance analysis chain

        Args:
            model (str): LLM model to use
            temperature (float): Temperature for response generation
            playbook_content (str, optional): Custom playbook content
        """
        self.llm = setup_gemini_llm(model, temperature)
        self.prompt = create_strada_prompt_template(playbook_content)
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

            # Use basic timeout with threading instead of signal (which doesn't work in Streamlit)
            import threading
            import time
            
            # Create a simple timeout mechanism
            response = None
            error = None
            
            def api_call():
                nonlocal response, error
                try:
                    response = self.chain.invoke({"nda_text": nda_text})
                except Exception as e:
                    error = e
            
            # Start the API call in a thread
            thread = threading.Thread(target=api_call)
            thread.daemon = True
            thread.start()
            thread.join(timeout=60)  # 60 second timeout
            
            if thread.is_alive():
                # Timeout occurred
                raise Exception("Google Gemini API call timed out (60s). The API may be overloaded. Please try again later.")
            elif error:
                # API call failed
                error_msg = str(error)
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "overloaded" in error_msg:
                    raise Exception(f"Google Gemini API is temporarily overloaded: {error_msg}")
                else:
                    raise Exception(f"API call failed: {error_msg}")
            elif response is None:
                # No response received
                raise Exception("API call failed: No response received")

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