"""
Unit Test - Mock Pipeline Verification
Verifies that individual agent nodes execute correctly without hitting actual live APIs.
Ensures LangGraph pipeline structure matches requirements.
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from core.state import AgentState
from core.models import Opportunity, AgentDecision, ScanMetadata
from datetime import datetime

class TestMockPipeline(unittest.TestCase):
    
    def setUp(self):
        self.state: AgentState = {
            "scan_id": "test-scan-123",
            "user_preferences": {
                "resume": "Experienced Python programmer with AI experience",
                "profile": {
                    "skills": ["python", "ai", "machine learning"],
                    "experience_level": "Intermediate",
                    "interests": ["hackathons", "open source"]
                }
            },
            "search_plan": None,
            "raw_opportunities": [],
            "extracted_opportunities": [],
            "deduplicated_opportunities": [],
            "duplicates_removed": 0,
            "classified_opportunities": [],
            "enriched_opportunities": [],
            "ranked_opportunities": [],
            "agent_logs": [],
            "hunter_context": {},
            "scan_metadata": ScanMetadata(scan_id="test-scan-123"),
            "progress_messages": [],
            "errors": []
        }

    @patch('core.llm.get_llm')
    @patch('core.llm.rate_limited_invoke')
    def test_evaluator_node_mock(self, mock_invoke, mock_get_llm):
        """Verify the Evaluator Agent evaluates and ranks opportunities correctly."""
        # 1. Setup mock LLM response
        mock_invoke.return_value = '{"match_score": 90, "match_reason": "Perfect match for your Python and AI skills."}'
        
        # 2. Setup mock opportunity
        opp = Opportunity(
            title="AI Hackathon 2026",
            organization="Google",
            category="Hackathon",
            description="Build cool agents using Gemini Pro",
            required_skills=["python", "ai"],
            location="Remote",
            source="devfolio",
            url="https://google.com/hackathon",
            score=80.0
        )
        self.state["ranked_opportunities"] = [opp]
        
        # 3. Run evaluator node
        from agents.agent_08_evaluator import run_evaluator
        result = run_evaluator(self.state)
        
        # 4. Assert results
        self.assertIn("ranked_opportunities", result)
        self.assertEqual(len(result["ranked_opportunities"]), 1)
        
        evaluated_opp = result["ranked_opportunities"][0]
        self.assertEqual(evaluated_opp.match_score, 90.0)
        self.assertEqual(evaluated_opp.match_reason, "Perfect match for your Python and AI skills.")
        self.assertGreater(evaluated_opp.score, 80.0) # check boost logic
        
        self.assertIn("agent_logs", result)
        self.assertEqual(len(result["agent_logs"]), 1)
        self.assertEqual(result["agent_logs"][0].agent_name, "Evaluator Agent")

if __name__ == "__main__":
    unittest.main()
