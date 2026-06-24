import os
import re
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Optional

class MockHTTPRequestHandler(BaseHTTPRequestHandler):
    mock_dir: str = ""
    mappings: List[Dict[str, Any]] = []

    def log_message(self, format, *args):
        # Silence stdout/stderr logging during test execution to prevent cluttering output
        pass

    def read_post_body(self) -> str:
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return ""
        return self.rfile.read(content_length).decode('utf-8')

    def find_mapping(self, method: str, path: str, body: str) -> Optional[Dict[str, Any]]:
        for mapping in self.mappings:
            # Check HTTP Method
            map_method = mapping.get("method", "GET").upper()
            if map_method != method.upper():
                continue

            # Check Path Pattern (regex)
            path_pattern = mapping.get("path_pattern", "")
            # Ensure query parameters are stripped before matching
            url_path = path.split('?')[0]
            # Ensure pattern is correctly anchored
            anchored_pattern = path_pattern
            if not anchored_pattern.startswith('^'):
                anchored_pattern = '^' + anchored_pattern
            if not anchored_pattern.endswith('$'):
                anchored_pattern = anchored_pattern + '$'

            if not re.search(anchored_pattern, url_path):
                continue

            # Check Body Contains (optional)
            body_contains = mapping.get("body_contains")
            if body_contains and body_contains not in body:
                continue

            return mapping
        return None

    def handle_request(self, method: str):
        body = ""
        if method == "POST":
            body = self.read_post_body()

        mapping = self.find_mapping(method, self.path, body)

        if not mapping:
            # Fallback 404
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Mock not found for {method} {self.path}"}).encode('utf-8'))
            return

        status = mapping.get("status", 200)
        content_type = mapping.get("content_type", "application/json")
        response_file = mapping.get("response_file")

        # Resolve response content
        content = b""
        if response_file:
            full_path = os.path.join(self.mock_dir, response_file)
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    content = f.read()
            else:
                # If file not found in profile, check if we have a default dummy structure
                if "dummy_structure" in response_file or response_file.endswith(".pdb"):
                    content = b"HEADER    DUMMY PROTEIN STRUCTURE FILE FOR TESTING\nATOM      1  CA  ALA A   1      0.000   0.000   0.000  1.00 20.00           C\nTER\nEND\n"
                else:
                    status = 500
                    content = f"Error: Mock response file '{response_file}' not found in profile.".encode('utf-8')
                    content_type = "text/plain"

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        
        # Extra headers
        for h_k, h_v in mapping.get("headers", {}).items():
            self.send_header(h_k, h_v)
            
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")


class MockAPIServer:
    def __init__(self, mock_dir: str, port: int = 8080):
        self.mock_dir = mock_dir
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.mappings: List[Dict[str, Any]] = []
        self._load_mappings()

    def _load_mappings(self):
        mapping_file = os.path.join(self.mock_dir, "mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r") as f:
                    self.mappings = json.load(f)
            except Exception as e:
                self.mappings = []
        else:
            # Fallback default mock mappings
            self.mappings = [
                {
                    "path_pattern": r"/graphql",
                    "method": "POST",
                    "response_file": "opentargets_query.json",
                    "content_type": "application/json"
                },
                {
                    "path_pattern": r"/chembl/api/data/status",
                    "method": "GET",
                    "response_file": "chembl_status.json",
                    "content_type": "application/json"
                },
                {
                    "path_pattern": r"/chembl/api/data/activity",
                    "method": "GET",
                    "response_file": "chembl_activities.json",
                    "content_type": "application/json"
                },
                {
                    "path_pattern": r"/rest/pug/compound",
                    "method": "GET",
                    "response_file": "pubchem_compounds.json",
                    "content_type": "application/json"
                },
                {
                    "path_pattern": r"/api/v2/studies",
                    "method": "GET",
                    "response_file": "clinicaltrials_studies.json",
                    "content_type": "application/json"
                },
                {
                    "path_pattern": r"/drug/event.json",
                    "method": "GET",
                    "response_file": "openfda_events.json",
                    "content_type": "application/json"
                },
                {
                    "path_pattern": r"/files/AF-.*\.pdb",
                    "method": "GET",
                    "response_file": "dummy_structure.pdb",
                    "content_type": "text/plain"
                }
            ]

    def start(self):
        class ConfiguredHandler(MockHTTPRequestHandler):
            mock_dir = self.mock_dir
            mappings = self.mappings

        try:
            self.server = HTTPServer(("127.0.0.1", self.port), ConfiguredHandler)
        except OSError:
            # If port is busy, find a random available port
            self.server = HTTPServer(("127.0.0.1", 0), ConfiguredHandler)

        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread:
            self.thread.join()
            self.thread = None
