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
import NDA_Review_chain
import NDA_HR_review_chain

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
-Each object in the arrays represents a single issue flagged in the NDA (red-flag or yellow-flag).
-Keys you may encounter include issue, section, citation, problem, suggested_replacement, change_type, etc.
-Company playbook policies are referenced by number (e.g., "Policy 7").

Your task is to act as a verifier by comparing HR edits against AI-flagged issues to determine the AI's accuracy and coverage.

# Input Format

**AI Review JSON Structure:**
```json
[
  {{
    "issue": "Short name of the policy violation",
    "citation": "The exact clause text that is problematic",
    "section": "Section number or identifier (e.g., '5.1')",
    "problem": "Explanation of why the clause is problematic",
    "suggested_fix": "The AI's suggested replacement text"
  }}
]
```

**HR Edits JSON Structure:**
```json
[
  {{
    "issue": "Descriptive title of the issue",
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
   - Secondary matching: section
   - Tertiary matching: citation text similarity and suggested_fix
   - Context matching: Case-insensitive and minor wording differences should still count as a match

2. **Categorize All Issues**: Sort every issue from both lists into exactly one of the following buckets:
a)Issues Correctly Identified by the AI – HR adopted the AI's point (fully or substantially).
b)Issues Missed by the AI – HR fixed something the AI never flagged.
c)Issues Flagged by the AI but Not Addressed by HR – HR left the AI's point unresolved.


## Output Requirements

Return your analysis as a JSON object with the following structure:

```json
{{
  "correctly_identified": [
    {{
      "issue": "Brief description with section reference",
      "analysis": "1-2 sentences comparing AI suggestion vs HR implementation"
    }}
  ],
  "missed_by_ai": [
    {{
      "issue": "Brief description of what HR changed with section reference", 
      "analysis": "Explanation of what AI missed and what HR did"
    }}
  ],
  "not_addressed_by_hr": [
    {{
      "issue": "Brief description of AI-flagged issue with section reference",
      "analysis": "AI's concern and why HR may not have addressed it"
    }}
  ],
  "summary": {{
    "total_ai_issues": 0,
    "total_hr_changes": 0,
    "correctly_identified_count": 0,
    "missed_by_ai_count": 0,
    "not_addressed_by_hr_count": 0
  }}
}}
```

**Important**: Return ONLY the JSON object, no additional text or markdown formatting.

# Quality Standards
- Be precise in your matching logic
- Provide clear, concise explanations
- Maintain objectivity in your analysis
- Focus on substantive issues, not minor formatting changes
-Do not invent fixes—only report what the JSON shows.
-Remain neutral and factual.

AI Review JSON: {ai_review_json}

HR Edits JSON: {hr_edits_json}
    '''

    return PromptTemplate(
        input_variables=["ai_review_json", "hr_edits_json"],
        template=template
    )


class TestingChain:
    """
    Chain for comparing AI review results with HR edits to evaluate AI performance
    """

    def __init__(self, model: str = "gemini-2.5-flash", temperature: float = 0.1):
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
        self.review_chain = NDA_Review_chain.StradaComplianceChain()
        self.compliance_chain = NDA_HR_review_chain.NDAComplianceChain()
        self.prompt = create_testing_template()
        self.chain = self._create_chain()

    def _create_chain(self):
        """Create the LangChain chain using LCEL syntax"""
        return self.prompt | self.llm | StrOutputParser()

    def analyze_testing(self, clean_nda_path: str, corrected_nda_path: str) -> Tuple[str, dict, list]:
        """
        Perform comparative analysis between AI review and HR edits

        Args:
            clean_nda_path (str): Path to the original NDA file
            corrected_nda_path (str): Path to the corrected NDA file with tracked changes

        Returns:
            Tuple[str, dict, list]: (comparison_analysis, ai_review_json, hr_edits_json)

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
            
            # Parse JSON response
            try:
                comparison_json = json.loads(comparison_response.strip())
                print("✅ Comparison analysis completed and parsed successfully")
            except json.JSONDecodeError as e:
                print(f"⚠️ Warning: Could not parse comparison response as JSON: {e}")
                print("Falling back to text format")
                comparison_json = {
                    "text_fallback": comparison_response,
                    "correctly_identified": [],
                    "missed_by_ai": [],
                    "not_addressed_by_hr": [],
                    "summary": {
                        "total_ai_issues": len(ai_review_json.get('red_flags', [])) + len(ai_review_json.get('yellow_flags', [])),
                        "total_hr_changes": len(hr_edits_json),
                        "correctly_identified_count": 0,
                        "missed_by_ai_count": 0,
                        "not_addressed_by_hr_count": 0
                    }
                }

            print("\n" + "=" * 60)
            print("ANALYSIS COMPLETED SUCCESSFULLY!")
            print("=" * 60)

            return comparison_json, ai_review_json, hr_edits_json

        except Exception as e:
            print(f"❌ Error during testing analysis: {str(e)}")
            raise
    def quick_testing(self,ai_review_json,hr_edits_json):
        print("!!Staring quick testing")
        comparison_response = self.chain.invoke({
            "ai_review_json": json.dumps(ai_review_json, indent=2),
            "hr_edits_json": json.dumps(hr_edits_json, indent=2)
        })
        return comparison_response

    def save_results(self, comparison_analysis: str, ai_review: dict, hr_edits: list,
                     output_dir: str = "results") -> None:
        """
        Save all analysis results to files

        Args:
            comparison_analysis (str): The comparative analysis text
            ai_review (dict): AI review results
            hr_edits (list): HR edits analysis
            output_dir (str): Directory to save results
        """
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Save comparison analysis
            with open(f"{output_dir}/comparison_analysis.txt", 'w', encoding='utf-8') as f:
                f.write(comparison_analysis)

            # Save AI review results
            with open(f"{output_dir}/ai_review_results.json", 'w', encoding='utf-8') as f:
                json.dump(ai_review, f, indent=2, ensure_ascii=False)

            # Save HR edits analysis
            with open(f"{output_dir}/hr_edits_analysis.json", 'w', encoding='utf-8') as f:
                json.dump(hr_edits, f, indent=2, ensure_ascii=False)

            print(f"📁 All results saved to {output_dir}/ directory")

        except Exception as e:
            print(f"❌ Error saving results: {str(e)}")
            raise
