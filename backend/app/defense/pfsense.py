import os
import subprocess
import logging
import urllib.request
import urllib.parse
import json
import xmlrpc.client
import ssl
import ipaddress
import re
from typing import Optional

logger = logging.getLogger("SPECTRE_PFSENSE")

class PfSenseBlocker:
    """
    PfSenseBlocker handles blocking and unblocking malicious IPs on a pfSense gateway.
    It supports SSH, API, and XML-RPC integration methods.
    """
    def __init__(
        self,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
        interface: Optional[str] = None,
        method: Optional[str] = None,
    ):
        # Load configurations, prioritizing arguments, falling back to environment variables
        self.host = host or os.getenv("PFSENSE_HOST", "")
        self.user = user or os.getenv("PFSENSE_USER", "")
        self.password = password or os.getenv("PFSENSE_PASS", "")
        self.ssh_key_path = ssh_key_path or os.getenv("PFSENSE_SSH_KEY_PATH", "")
        self.interface = interface or os.getenv("PFSENSE_INTERFACE", "wan")
        self.method = (method or os.getenv("PFSENSE_METHOD", "ssh")).lower()

    def block_ip(self, ip: str, interface: Optional[str] = None) -> bool:
        """
        Blocks an IP on pfSense.
        """
        if not ip:
            logger.error("IP is required for blocking.")
            return False

        try:
            ipaddress.ip_address(ip)
        except ValueError as e:
            logger.error(f"Invalid IP address format: {ip}. Error: {e}")
            return False

        if not self.host:
            logger.error("PfSense host is not configured.")
            return False

        if interface is None:
            interface = self.interface

        if not interface or not re.match(r"^[a-zA-Z0-9_]+$", interface):
            logger.error(f"Invalid interface name: {interface}. Only alphanumeric and underscores allowed.")
            return False

        logger.info(f"Blocking IP: {ip} on interface: {interface} using method: {self.method}")

        try:
            if self.method == "ssh":
                return self._block_ip_ssh(ip, interface)
            elif self.method == "api":
                return self._block_ip_api(ip, interface)
            elif self.method == "xmlrpc":
                return self._block_ip_xmlrpc(ip, interface)
            else:
                logger.error(f"Unsupported block method: {self.method}")
                return False
        except Exception as e:
            logger.error(f"Error blocking IP {ip} using {self.method}: {e}", exc_info=True)
            return False

    def unblock_ip(self, ip: str, interface: Optional[str] = None) -> bool:
        """
        Unblocks an IP on pfSense.
        """
        if not ip:
            logger.error("IP is required for unblocking.")
            return False

        try:
            ipaddress.ip_address(ip)
        except ValueError as e:
            logger.error(f"Invalid IP address format: {ip}. Error: {e}")
            return False

        if not self.host:
            logger.error("PfSense host is not configured.")
            return False

        if interface is None:
            interface = self.interface

        if not interface or not re.match(r"^[a-zA-Z0-9_]+$", interface):
            logger.error(f"Invalid interface name: {interface}. Only alphanumeric and underscores allowed.")
            return False

        logger.info(f"Unblocking IP: {ip} on interface: {interface} using method: {self.method}")

        try:
            if self.method == "ssh":
                return self._unblock_ip_ssh(ip, interface)
            elif self.method == "api":
                return self._unblock_ip_api(ip, interface)
            elif self.method == "xmlrpc":
                return self._unblock_ip_xmlrpc(ip, interface)
            else:
                logger.error(f"Unsupported unblock method: {self.method}")
                return False
        except Exception as e:
            logger.error(f"Error unblocking IP {ip} using {self.method}: {e}", exc_info=True)
            return False

    def _block_ip_ssh(self, ip: str, interface: str) -> bool:
        # Construct command for easyrule block
        cmd = []
        run_env = os.environ.copy()
        if self.password and not self.ssh_key_path:
            # If password auth is used, use sshpass if present, otherwise fallback to regular ssh
            cmd = ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
            run_env["SSHPASS"] = self.password
        else:
            cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
            if self.ssh_key_path:
                cmd.extend(["-i", self.ssh_key_path])

        cmd.extend([f"{self.user}@{self.host}" if self.user else self.host, f"easyrule block {interface} {ip}"])
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=run_env, capture_output=True, text=True, timeout=15, check=True)
        logger.info(f"SSH block completed. Output: {result.stdout.strip()}")
        return True

    def _unblock_ip_ssh(self, ip: str, interface: str) -> bool:
        # Run easyrule unblock or custom pfctl command via SSH
        # Easyrule block adds IPs to the EasyRuleBlock<Interface> table.
        # We can remove it via pfctl: pfctl -t EasyRuleBlock{interface} -T delete {ip}
        table_name = f"EasyRuleBlock{interface}"
        cmd_str = f"pfctl -t {table_name} -T delete {ip}"
        
        cmd = []
        run_env = os.environ.copy()
        if self.password and not self.ssh_key_path:
            cmd = ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
            run_env["SSHPASS"] = self.password
        else:
            cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
            if self.ssh_key_path:
                cmd.extend(["-i", self.ssh_key_path])

        cmd.extend([f"{self.user}@{self.host}" if self.user else self.host, cmd_str])
        
        try:
            logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, env=run_env, capture_output=True, text=True, timeout=15, check=True)
            logger.info(f"SSH unblock completed. Output: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            # Let's try capitalized table name just in case (e.g. EasyRuleBlockWAN)
            table_name_upper = f"EasyRuleBlock{interface.upper()}"
            cmd_str_upper = f"pfctl -t {table_name_upper} -T delete {ip}"
            
            cmd_upper = cmd.copy()
            cmd_upper[-1] = cmd_str_upper
            
            logger.debug(f"First attempt failed. Retrying with upper interface: {' '.join(cmd_upper)}")
            result = subprocess.run(cmd_upper, env=run_env, capture_output=True, text=True, timeout=15, check=True)
            logger.info(f"SSH unblock (upper table) completed. Output: {result.stdout.strip()}")
            return True

    def _block_ip_api(self, ip: str, interface: str) -> bool:
        url = f"https://{self.host}/api/v1/firewall/alias"
        payload = {
            "name": f"EasyRuleBlock{interface}",
            "address": ip,
            "detail": "Blocked by SPECTRE GRID IDS",
            "type": "host"
        }
        return self._send_api_request(url, payload, method="POST")

    def _unblock_ip_api(self, ip: str, interface: str) -> bool:
        url = f"https://{self.host}/api/v1/firewall/alias"
        payload = {
            "name": f"EasyRuleBlock{interface}",
            "address": ip
        }
        return self._send_api_request(url, payload, method="DELETE")

    def _send_api_request(self, url: str, payload: dict, method: str) -> bool:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        
        if self.user and self.password:
            import base64
            auth_str = f"{self.user}:{self.password}"
            auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            req.add_header("Authorization", f"Basic {auth_b64}")

        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            res_data = response.read().decode('utf-8')
            logger.info(f"API request successful. Response: {res_data}")
            return response.status in (200, 201, 204)

    def _block_ip_xmlrpc(self, ip: str, interface: str) -> bool:
        url = f"https://{self.host}/xmlrpc.php"
        ctx = ssl._create_unverified_context()
        
        class SafeTransport(xmlrpc.client.SafeTransport):
            def __init__(self, context, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.context = context
            def make_connection(self, host):
                conn = super().make_connection(host)
                conn._context = self.context
                return conn
                
        transport = SafeTransport(context=ctx)
        proxy_url = f"https://{self.user}:{self.password}@{self.host}/xmlrpc.php" if self.user and self.password else url
        server = xmlrpc.client.ServerProxy(proxy_url, transport=transport)
        
        php_code = f"mwexec('/usr/local/bin/easyrule block {interface} {ip}');"
        res = server.pfsense.exec_php(php_code)
        logger.info(f"XMLRPC block executed. Result: {res}")
        return True

    def _unblock_ip_xmlrpc(self, ip: str, interface: str) -> bool:
        url = f"https://{self.host}/xmlrpc.php"
        ctx = ssl._create_unverified_context()
        
        class SafeTransport(xmlrpc.client.SafeTransport):
            def __init__(self, context, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.context = context
            def make_connection(self, host):
                conn = super().make_connection(host)
                conn._context = self.context
                return conn
                
        transport = SafeTransport(context=ctx)
        proxy_url = f"https://{self.user}:{self.password}@{self.host}/xmlrpc.php" if self.user and self.password else url
        server = xmlrpc.client.ServerProxy(proxy_url, transport=transport)
        
        php_code = (
            f"mwexec('/sbin/pfctl -t EasyRuleBlock{interface} -T delete {ip}'); "
            f"mwexec('/sbin/pfctl -t EasyRuleBlock{interface.upper()} -T delete {ip}');"
        )
        res = server.pfsense.exec_php(php_code)
        logger.info(f"XMLRPC unblock executed. Result: {res}")
        return True
