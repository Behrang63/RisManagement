import unittest
from unittest.mock import patch, MagicMock
from Risk_app_v3 import EthicsRiskAnalyzerEngine, DocumentProcessor

class TestEthicsRiskAnalyzer(unittest.TestCase):

    @patch('requests.post')
    def test_query_ollama_success(self, mock_post):
        # Mocking HTTP 200 response from Ollama API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "[{\"risk\": \"Data Privacy\", \"S\": 8, \"O\": 3, \"D\": 4}]"}
        mock_post.return_value = mock_response

        res = EthicsRiskAnalyzerEngine.query_ollama("http://localhost:11434/api/generate", "llama3", "Test prompt")
        self.assertNotIn("ERROR", res)
        self.assertIn("Data Privacy", res)

    def test_document_processor_empty(self):
        text = DocumentProcessor.extract_text(None)
        self.assertEqual(text, "")

if __name__ == '__main__':
    unittest.main()