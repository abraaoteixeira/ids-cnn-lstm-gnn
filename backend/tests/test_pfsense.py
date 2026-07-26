import unittest
from unittest.mock import patch, MagicMock
import json
import subprocess
from backend.app.defense.pfsense import PfSenseBlocker

class TestPfSenseBlocker(unittest.TestCase):
    def setUp(self):
        # Set up different instances for various configuration settings
        self.blocker_ssh_key = PfSenseBlocker(
            host="192.168.100.4",
            user="admin",
            ssh_key_path="/mock/path/id_rsa",
            interface="wan",
            method="ssh"
        )
        self.blocker_ssh_pass = PfSenseBlocker(
            host="192.168.100.4",
            user="admin",
            password="secretpassword",
            interface="wan",
            method="ssh"
        )
        self.blocker_api = PfSenseBlocker(
            host="192.168.100.4",
            user="admin",
            password="secretpassword",
            interface="lan",
            method="api"
        )
        self.blocker_xmlrpc = PfSenseBlocker(
            host="192.168.100.4",
            user="admin",
            password="secretpassword",
            interface="opt1",
            method="xmlrpc"
        )

    @patch("subprocess.run")
    def test_block_ip_ssh_key(self, mock_run):
        mock_run.return_value = MagicMock(stdout="successfully added block\n", stderr="", returncode=0)
        
        result = self.blocker_ssh_key.block_ip("192.168.100.50")
        self.assertTrue(result)
        mock_run.assert_called_once()
        
        cmd = mock_run.call_args[0][0]
        self.assertIn("ssh", cmd)
        self.assertIn("-i", cmd)
        self.assertIn("/mock/path/id_rsa", cmd)
        self.assertIn("admin@192.168.100.4", cmd)
        self.assertIn("easyrule block wan 192.168.100.50", cmd)

    @patch("subprocess.run")
    def test_block_ip_ssh_pass(self, mock_run):
        mock_run.return_value = MagicMock(stdout="successfully added block\n", stderr="", returncode=0)
        
        result = self.blocker_ssh_pass.block_ip("192.168.100.50")
        self.assertTrue(result)
        mock_run.assert_called_once()
        
        kwargs = mock_run.call_args[1]
        self.assertIn("env", kwargs)
        self.assertEqual(kwargs["env"].get("SSHPASS"), "secretpassword")
        
        cmd = mock_run.call_args[0][0]
        self.assertIn("sshpass", cmd)
        self.assertIn("-e", cmd)
        self.assertIn("easyrule block wan 192.168.100.50", cmd)

    @patch("subprocess.run")
    def test_unblock_ip_ssh_key(self, mock_run):
        mock_run.return_value = MagicMock(stdout="1/1 address deleted\n", stderr="", returncode=0)
        
        result = self.blocker_ssh_key.unblock_ip("192.168.100.50")
        self.assertTrue(result)
        mock_run.assert_called_once()
        
        cmd = mock_run.call_args[0][0]
        self.assertIn("pfctl -t EasyRuleBlockwan -T delete 192.168.100.50", cmd)

    @patch("subprocess.run")
    def test_unblock_ip_ssh_key_retry(self, mock_run):
        # Configure side effect where first pfctl call returns non-zero code, but second succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, cmd=["ssh", "..."], stderr="Table not found"),
            MagicMock(stdout="1/1 address deleted\n", stderr="", returncode=0)
        ]
        
        result = self.blocker_ssh_key.unblock_ip("192.168.100.50")
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)
        
        first_cmd = mock_run.call_args_list[0][0][0]
        second_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("pfctl -t EasyRuleBlockwan -T delete 192.168.100.50", first_cmd)
        self.assertIn("pfctl -t EasyRuleBlockWAN -T delete 192.168.100.50", second_cmd)

    @patch("urllib.request.urlopen")
    def test_block_ip_api(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "success", "message": "Alias updated"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.blocker_api.block_ip("192.168.100.60")
        self.assertTrue(result)
        mock_urlopen.assert_called_once()
        
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://192.168.100.4/api/v1/firewall/alias")
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.headers.get("Authorization"), "Basic YWRtaW46c2VjcmV0cGFzc3dvcmQ=")
        
        body = json.loads(req.data.decode('utf-8'))
        self.assertEqual(body["name"], "EasyRuleBlocklan")
        self.assertEqual(body["address"], "192.168.100.60")

    @patch("urllib.request.urlopen")
    def test_unblock_ip_api(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "success", "message": "Address removed"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.blocker_api.unblock_ip("192.168.100.60")
        self.assertTrue(result)
        mock_urlopen.assert_called_once()
        
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.method, "DELETE")
        
        body = json.loads(req.data.decode('utf-8'))
        self.assertEqual(body["name"], "EasyRuleBlocklan")
        self.assertEqual(body["address"], "192.168.100.60")

    @patch("xmlrpc.client.ServerProxy")
    def test_block_ip_xmlrpc(self, mock_server_proxy):
        mock_server = MagicMock()
        mock_server.pfsense.exec_php.return_value = True
        mock_server_proxy.return_value = mock_server
        
        result = self.blocker_xmlrpc.block_ip("192.168.100.70")
        self.assertTrue(result)
        
        mock_server_proxy.assert_called_once()
        conn_str = mock_server_proxy.call_args[0][0]
        self.assertEqual(conn_str, "https://admin:secretpassword@192.168.100.4/xmlrpc.php")
        
        mock_server.pfsense.exec_php.assert_called_once()
        php_code = mock_server.pfsense.exec_php.call_args[0][0]
        self.assertIn("easyrule block opt1 192.168.100.70", php_code)

    @patch("xmlrpc.client.ServerProxy")
    def test_unblock_ip_xmlrpc(self, mock_server_proxy):
        mock_server = MagicMock()
        mock_server.pfsense.exec_php.return_value = True
        mock_server_proxy.return_value = mock_server
        
        result = self.blocker_xmlrpc.unblock_ip("192.168.100.70")
        self.assertTrue(result)
        
        mock_server.pfsense.exec_php.assert_called_once()
        php_code = mock_server.pfsense.exec_php.call_args[0][0]
        self.assertIn("pfctl -t EasyRuleBlockopt1 -T delete 192.168.100.70", php_code)
        self.assertIn("pfctl -t EasyRuleBlockOPT1 -T delete 192.168.100.70", php_code)

    def test_block_ip_invalid_ip(self):
        result = self.blocker_ssh_key.block_ip("1.2.3.4; inject")
        self.assertFalse(result)
        
        result_unblock = self.blocker_ssh_key.unblock_ip("1.2.3.4; inject")
        self.assertFalse(result_unblock)

    def test_block_ip_invalid_interface(self):
        result = self.blocker_ssh_key.block_ip("192.168.100.50", interface="wan; inject")
        self.assertFalse(result)

        result_unblock = self.blocker_ssh_key.unblock_ip("192.168.100.50", interface="wan; inject")
        self.assertFalse(result_unblock)

    @patch("subprocess.run")
    def test_credential_transmission_sshpass(self, mock_run):
        mock_run.return_value = MagicMock(stdout="successfully added block\n", stderr="", returncode=0)
        result = self.blocker_ssh_pass.block_ip("192.168.100.50")
        self.assertTrue(result)
        
        kwargs = mock_run.call_args[1]
        self.assertIn("env", kwargs)
        self.assertEqual(kwargs["env"].get("SSHPASS"), "secretpassword")
        
        cmd = mock_run.call_args[0][0]
        self.assertIn("sshpass", cmd)
        self.assertIn("-e", cmd)
        self.assertNotIn("-p", cmd)

if __name__ == "__main__":
    unittest.main()
