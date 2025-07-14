"""
Clean Testing Script for NDA Analysis
Main script for running comparative analysis between AI review and HR edits
"""

from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import StrOutputParser
import json
import os
from typing import Tuple
from dotenv import load_dotenv

# Import our custom modules
from NDA_Review_chain import StradaComplianceChain
from NDA_HR_review_chain import NDAComplianceChain
import json
import os
import re
# Load environment variables
load_dotenv()

def create_testing_template():
    """
    Create the prompt template based on the playbook to review the changes
    """

    template = '''
# Persona
You are LexAI, a senior M&A lawyer and diligence analyst with meticulous attention to detail and expertise in contract review.
Your task is to compare two JSON arrays describing proposed edits to an NDA—one produced by an AI reviewer, the other by HR—and produce a concise reconciliation.

# Context
-Each object in the arrays represents a single issue flagged in the NDA (High, Medium or Low priority).
-Keys you may encounter include issue, section, citation, problem, suggested_replacement, change_type, etc.
-Company playbook policies are referenced by number (e.g., "Policy 7").

Your task is to act as a verifier by comparing HR edits against AI-flagged issues to determine the AI's accuracy and coverage.

# Input Format

**AI Review JSON Structure:**
```json
{{
  "High Priority": [
    {{
      "issue": "Short name of the policy violation",
      "citation": "The exact clause text that is problematic",
      "section": "Section number or identifier (e.g., '5.1')",
      "problem": "Explanation of why the clause is problematic",
      "suggested_replacement": "The AI's suggested replacement text"
    }}
  ],
  "Medium Priority": [...],
  "Low Priority": [...]
}}
```

**HR Edits JSON Structure:**
```json
[
  {{
    "issue": "Descriptive title of the issue",
    "Priority": "One of: 'High', 'Medium', or 'Low'",
    "change_type": "One of: 'Addition', 'Deletion', or 'Replacement'",
    "section": "Section number or identifier from the NDA where change occurred",
    "citation": "The original text that was changed or the new text that was added",
    "problem": "Clear explanation of the reason for the change"
  }}
]
```

# Task Instructions

## Analysis Process:
1. **Match Issues**: Compare items between the two JSON arrays using:
   - Primary matching: Issue
   - Secondary matching: Section
   - Tertiary matching: citation text similarity and suggested_replacement
   - Context matching: Case-insensitive and minor wording differences should still count as a match

2. **Categorize All Issues**: Sort every issue from both lists into exactly one of the following buckets:
a)Issues Correctly Identified by the AI – HR adopted the AI's point (fully or partially).
b)Issues Missed by the AI – HR fixed something the AI never flagged.
c)Issues Flagged by the AI but Not Addressed by HR – HR left the AI's point unresolved.


## Output Requirements

Present your findings using the exact format below.

{{
  "Issues Correctly Identified by the AI": [
    {{
      "Issue": "Brief description, e.g., "Return & Destruction of Information clause" ",
      "Section": "[section of the NDA, take it from the AI json] or 'N/A'",
      "Priority": "High, Medium or Low",
      "Analysis":"1-2 sentences comparing what the AI suggested vs. what HR actually did, AI proposed <summary>. HR implemented <summary>."
    }}
  ],
  "Issues Missed by the AI": [
    {{
      "Issue": "Brief description of what HR changed, e.g.,"Deleted ambiguous termination clause" or Uncategorized Change",
      "Section": "[section of the NDA, take it from the HR json or 'N/A'",
      "Priority": "High, Medium or Low",
      "Analysis": "AI did not mention this. HR added/removed <summary>"
    }}
  ],
  "Issues Flagged by AI but Not Addressed by HR": [
    {{
      "Issue": "Brief description, e.g., "Overly broad confidentiality scope" ",
      "Section": "[section of the NDA, take it from the AI JSON] or 'N/A' ",
      "Priority": "High, Medium or Low",
      "Analysis": "1-2 sentences describing the AI's concern and why HR may not have addressed it"
    }}
  ]
}}

AI Review JSON: {ai_review_json}

HR Edits JSON: {hr_edits_json}
    '''

    return PromptTemplate(
        input_variables=["ai_review_json", "hr_edits_json"],
        template=template
    )

import re
import json
import os
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
    try:
        # Clean up the response
        response_text = response_text.strip()

        # Try direct parsing first
        if response_text.startswith('{'):
            return json.loads(response_text)

        # Extract JSON from markdown formatting
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Look for JSON object in the text
        obj_start = response_text.find('{')
        obj_end = response_text.rfind('}') + 1
        if obj_start != -1 and obj_end > obj_start:
            json_text = response_text[obj_start:obj_end]
            return json.loads(json_text)

        raise ValueError("No valid JSON found in response")

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON response: {str(e)}\nResponse: {response_text[:500]}...")
    except Exception as e:
        raise Exception(f"Error parsing response: {str(e)}")



class TestingChain:
    """
    Chain for comparing AI review results with HR edits to evaluate AI performance
    """

    def __init__(self, model: str = "gemini-2.5-pro", temperature: float = 0):
        """
        Initialize the testing chain

        Args:
            model (str): LLM model to use
            temperature (float): Temperature for response generation
        """
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=os.environ.get("GOOGLE_API_KEY")
        )
        self.review_chain = StradaComplianceChain()
        self.compliance_chain = NDAComplianceChain()
        self.prompt = create_testing_template()
        self.chain = self._create_chain()

    def _create_chain(self):
        """Create the LangChain chain using LCEL syntax"""
        return self.prompt | self.llm | StrOutputParser()

    def analyze_testing(self, clean_nda_path: str, corrected_nda_path: str) -> Tuple[dict, str, dict, list]:
        """
        Perform comparative analysis between AI review and HR edits

        Args:
            clean_nda_path (str): Path to the original NDA file
            corrected_nda_path (str): Path to the corrected NDA file with tracked changes

        Returns:
            Tuple[dict, str, dict, list]: (comparison_analysis, comparison_response, ai_review_json, hr_edits_json)

        Raises:
            Exception: If analysis fails
        """
        try:
            print("=" * 60)
            print("STARTING COMPARATIVE NDA ANALYSIS")
            print("=" * 60)

            # Step 1: Analyze clean NDA with AI reviewer
            print("📋 Step 1: Analyzing clean NDA with AI reviewer...")
            ai_review_json, ai_response = self.review_chain.analyze_nda(clean_nda_path)
            print("✅ AI review completed")

            # Step 2: Analyze corrected NDA for compliance changes
            print("\n📋 Step 2: Analyzing corrected NDA for compliance changes...")
            hr_edits_json, hr_response = self.compliance_chain.analyze_nda(corrected_nda_path)
            print("✅ HR edits analysis completed")

            # Step 3: Compare AI review vs HR edits
            print("\n📋 Step 3: Running comparison analysis...")
            comparison_response = self.chain.invoke({
                "ai_review_json": json.dumps(ai_review_json, indent=2),
                "hr_edits_json": json.dumps(hr_edits_json, indent=2)
            })
            print("✅ Comparison analysis completed")
            comparison_analysis = parse_compliance_response(comparison_response)
            print("\n" + "=" * 60)
            print("ANALYSIS COMPLETED SUCCESSFULLY!")
            print("=" * 60)

            return comparison_analysis, comparison_response, ai_review_json, hr_edits_json

        except Exception as e:
            print(f"❌ Error during testing analysis: {str(e)}")
            raise
    
    def quick_testing(self, ai_review_json, hr_edits_json):
        print("!!Starting quick testing")
        comparison_response = self.chain.invoke({
            "ai_review_json": json.dumps(ai_review_json, indent=2),
            "hr_edits_json": json.dumps(hr_edits_json, indent=2)
        })
        comparison_analysis = parse_compliance_response(comparison_response)
        return comparison_analysis, comparison_response


    def save_results(self, comparison_analysis: dict, ai_review: dict, hr_edits: list,
                     output_dir: str = "results") -> None:
        """
        Save all analysis results to files

        Args:
            comparison_analysis (dict): The comparative analysis results
            ai_review (dict): AI review results
            hr_edits (list): HR edits analysis
            output_dir (str): Directory to save results
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Save comparison analysis
        with open(f"{output_dir}/comparison_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(comparison_analysis, f, indent=2, ensure_ascii=False)

        # Save AI review
        with open(f"{output_dir}/ai_review.json", 'w', encoding='utf-8') as f:
            json.dump(ai_review, f, indent=2, ensure_ascii=False)

        # Save HR edits
        with open(f"{output_dir}/hr_edits.json", 'w', encoding='utf-8') as f:
            json.dump(hr_edits, f, indent=2, ensure_ascii=False)

        print(f"📁 Results saved to {output_dir}/")