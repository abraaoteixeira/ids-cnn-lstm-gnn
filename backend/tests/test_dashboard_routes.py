import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import os

# Set environment variables for testing before importing the app
os.environ["PFSENSE_ENABLED"] = "True"
os.environ["PFSENSE_HOST"] = "192.168.100.4"
os.environ["PFSENSE_USER"] = "admin"
os.environ["PFSENSE_PASS"] = "secret"
os.environ["PFSENSE_METHOD"] = "ssh"

from dashboard_api_v2 import app

class TestDashboardDefenseRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("backend.app.defense.pfsense.PfSenseBlocker.block_ip")
    def test_manual_block_endpoint(self, mock_block):
        mock_block.return_value = True
        
        response = self.client.post(
            "/api/defense/block",
            json={"ip": "1.2.3.4", "interface": "wan"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "success",
            "message": "IP 1.2.3.4 blocked successfully on pfSense."
        })
        mock_block.assert_called_once_with("1.2.3.4", "wan")

    @patch("backend.app.defense.pfsense.PfSenseBlocker.unblock_ip")
    def test_manual_unblock_endpoint(self, mock_unblock):
        mock_unblock.return_value = True
        
        response = self.client.post(
            "/api/defense/unblock",
            json={"ip": "1.2.3.4"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "success",
            "message": "IP 1.2.3.4 unblocked successfully on pfSense."
        })
        mock_unblock.assert_called_once_with("1.2.3.4", None)

    @patch("backend.app.defense.pfsense.PfSenseBlocker.block_ip")
    def test_manual_block_disabled(self, mock_block):
        # Temporarily disable pfSense integration
        import dashboard_api_v2
        dashboard_api_v2.PFSENSE_ENABLED = False
        
        try:
            response = self.client.post(
                "/api/defense/block",
                json={"ip": "1.2.3.4"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "status": "error",
                "message": "pfSense integration is disabled."
            })
            mock_block.assert_not_called()
        finally:
            dashboard_api_v2.PFSENSE_ENABLED = True

if __name__ == "__main__":
    unittest.main()
