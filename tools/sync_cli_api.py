#!/usr/bin/env python3
"""
API-CLI Sync Tool

Scans all API route files to discover endpoints and checks if they have
corresponding CLI commands documented in CLI_REDESIGN.md.

Usage:
    python tools/sync_cli_api.py --check              # Check for missing mappings
    python tools/sync_cli_api.py --report             # Generate detailed report
    python tools/sync_cli_api.py --generate-stubs     # Generate CLI command stubs
"""

import os
import re
import glob
import json
import argparse
from pathlib import Path
from collections import defaultdict


class APIEndpoint:
    """Represents an API endpoint."""
    
    def __init__(self, path, methods, handler, file_path, line_number):
        self.path = path
        self.methods = methods
        self.handler = handler
        self.file_path = file_path
        self.line_number = line_number
        self.cli_command = None
        self.cli_mapped = False
    
    def __repr__(self):
        return f"<APIEndpoint {self.methods} {self.path}>"
    
    def to_dict(self):
        return {
            'path': self.path,
            'methods': self.methods,
            'handler': self.handler,
            'file': self.file_path,
            'line': self.line_number,
            'cli_command': self.cli_command,
            'cli_mapped': self.cli_mapped
        }


class APIDiscovery:
    """Discover all API endpoints in the project."""
    
    def __init__(self, api_root='src/modules/api'):
        self.api_root = api_root
        self.endpoints = []
    
    def discover(self):
        """Scan all Python files in API directory for route decorators."""
        pattern = os.path.join(self.api_root, '**', '*.py')
        files = glob.glob(pattern, recursive=True)
        
        for file_path in files:
            self._scan_file(file_path)
        
        return self.endpoints
    
    def _scan_file(self, file_path):
        """Scan a single file for API routes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return
        
        # Pattern for Flask route decorators
        # Matches: @app.route('/api/path', methods=['POST', 'GET'])
        #          @bp.route('/api/path', methods=['POST'])
        route_pattern = re.compile(
            r"@\w+\.route\s*\(\s*['\"](/api/[^'\"]+)['\"](?:.*?methods\s*=\s*\[([^\]]+)\])?"
        )
        
        for i, line in enumerate(lines, 1):
            match = route_pattern.search(line)
            if match:
                path = match.group(1)
                methods_str = match.group(2) if match.group(2) else 'GET'
                
                # Extract method names
                methods = re.findall(r"['\"](\w+)['\"]", methods_str)
                if not methods:
                    methods = ['GET']
                
                # Get handler function name (next def line)
                handler = None
                for j in range(i, min(i + 5, len(lines))):
                    func_match = re.search(r'def\s+(\w+)\s*\(', lines[j])
                    if func_match:
                        handler = func_match.group(1)
                        break
                
                # Only include endpoints that modify state (POST/PUT/PATCH/DELETE)
                # or are significant GET endpoints
                if any(m in ['POST', 'PUT', 'PATCH', 'DELETE'] for m in methods):
                    endpoint = APIEndpoint(
                        path=path,
                        methods=methods,
                        handler=handler,
                        file_path=file_path,
                        line_number=i
                    )
                    self.endpoints.append(endpoint)
    
    def categorize_endpoints(self):
        """Group endpoints by domain."""
        categories = defaultdict(list)
        
        for endpoint in self.endpoints:
            # Extract domain from path (e.g., /api/player/... -> player)
            parts = endpoint.path.split('/')
            if len(parts) >= 3:
                domain = parts[2]  # /api/DOMAIN/...
                categories[domain].append(endpoint)
            else:
                categories['other'].append(endpoint)
        
        return dict(categories)


class CLIDocParser:
    """Parse CLI_REDESIGN.md to find documented CLI commands."""
    
    def __init__(self, doc_path='docs/CLI_REDESIGN.md'):
        self.doc_path = doc_path
        self.api_cli_mappings = {}
    
    def parse(self):
        """Parse the documentation and extract API-CLI mappings."""
        try:
            with open(self.doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error: Could not read {self.doc_path}: {e}")
            return {}
        
        # Pattern to match mapping tables:
        # | API Endpoint | CLI Command | Example |
        # | POST /api/player/<id>/play | player play | player play -p video |
        
        # Match table rows with API paths
        pattern = re.compile(
            r'\|\s*(?:GET|POST|PUT|PATCH|DELETE)\s+(/api/[^\s|]+)\s*\|\s*`([^`]+)`',
            re.MULTILINE
        )
        
        for match in pattern.finditer(content):
            api_path = match.group(1)
            cli_command = match.group(2).strip()
            
            # Normalize path (replace <param> with actual placeholders)
            normalized_path = re.sub(r'<[^>]+>', '*', api_path)
            
            self.api_cli_mappings[api_path] = cli_command
        
        return self.api_cli_mappings
    
    def find_cli_command(self, api_path):
        """Find CLI command for an API path."""
        # Try exact match first
        if api_path in self.api_cli_mappings:
            return self.api_cli_mappings[api_path]
        
        # Try pattern matching (for parameterized paths)
        api_pattern = re.sub(r'<[^>]+>', '[^/]+', api_path)
        for doc_path, cli_cmd in self.api_cli_mappings.items():
            doc_pattern = re.sub(r'<[^>]+>', '[^/]+', doc_path)
            if re.match(doc_pattern, api_path):
                return cli_cmd
        
        return None


class APICliSyncChecker:
    """Check consistency between API endpoints and CLI commands."""
    
    def __init__(self, api_root='src/modules/api', doc_path='docs/CLI_REDESIGN.md'):
        self.discovery = APIDiscovery(api_root)
        self.doc_parser = CLIDocParser(doc_path)
        self.endpoints = []
        self.mappings = {}
    
    def check(self):
        """Run consistency check."""
        print("🔍 Discovering API endpoints...")
        self.endpoints = self.discovery.discover()
        print(f"   Found {len(self.endpoints)} endpoints\n")
        
        print("📖 Parsing CLI documentation...")
        self.mappings = self.doc_parser.parse()
        print(f"   Found {len(self.mappings)} CLI mappings\n")
        
        print("🔄 Checking API-CLI consistency...")
        
        # Check each endpoint for CLI mapping
        missing = []
        for endpoint in self.endpoints:
            cli_cmd = self.doc_parser.find_cli_command(endpoint.path)
            if cli_cmd:
                endpoint.cli_command = cli_cmd
                endpoint.cli_mapped = True
            else:
                missing.append(endpoint)
        
        return missing
    
    def report(self, missing):
        """Generate report of missing CLI mappings."""
        if not missing:
            print("✅ All API endpoints have CLI mappings!\n")
            return
        
        print(f"❌ Found {len(missing)} API endpoints without CLI mappings:\n")
        
        # Group by category
        categorized = defaultdict(list)
        for endpoint in missing:
            parts = endpoint.path.split('/')
            domain = parts[2] if len(parts) >= 3 else 'other'
            categorized[domain].append(endpoint)
        
        for domain, endpoints in sorted(categorized.items()):
            print(f"\n📦 {domain.upper()} ({len(endpoints)} missing)")
            print("=" * 80)
            for ep in endpoints:
                methods_str = ', '.join(ep.methods)
                print(f"\n  Path:    {ep.path}")
                print(f"  Methods: {methods_str}")
                print(f"  Handler: {ep.handler}")
                print(f"  File:    {ep.file_path}:{ep.line_number}")
                print(f"  Suggest: {self._suggest_cli_command(ep)}")
    
    def _suggest_cli_command(self, endpoint):
        """Suggest a CLI command for an endpoint."""
        path = endpoint.path
        method = endpoint.methods[0] if endpoint.methods else 'GET'
        
        # Parse path to suggest command
        parts = [p for p in path.split('/') if p and p != 'api']
        
        if len(parts) >= 2:
            domain = parts[0]
            action = parts[-1] if parts[-1] not in ['<player_id>', '<clip_id>'] else parts[-2]
            
            # Map HTTP methods to actions
            if method == 'POST':
                if 'add' in action:
                    action = 'add'
                elif 'create' in action:
                    action = 'create'
                elif action in ['enable', 'disable', 'toggle', 'start', 'stop']:
                    pass  # Keep as is
                else:
                    action = 'set'
            elif method == 'DELETE':
                action = 'remove' if 'remove' in action else 'delete'
            elif method == 'PUT' or method == 'PATCH':
                action = 'update'
            
            return f"{domain} {action} [options]"
        
        return "NEEDS MANUAL MAPPING"
    
    def generate_stubs(self, missing):
        """Generate CLI command stub code for missing endpoints."""
        if not missing:
            print("✅ No stubs needed - all endpoints mapped!\n")
            return
        
        print("📝 Generating CLI command stubs...\n")
        
        categorized = defaultdict(list)
        for endpoint in missing:
            parts = endpoint.path.split('/')
            domain = parts[2] if len(parts) >= 3 else 'other'
            categorized[domain].append(endpoint)
        
        for domain, endpoints in sorted(categorized.items()):
            print(f"\n# {domain.upper()} Commands")
            print("=" * 80)
            print(f"# File: src/modules/cli/commands/{domain}.py\n")
            
            for ep in endpoints:
                func_name = ep.handler or 'unknown'
                suggested_cmd = self._suggest_cli_command(ep)
                
                print(f"def cli_{func_name}(args):")
                print(f'    """')
                print(f'    {" ".join(ep.methods)} {ep.path}')
                print(f'    CLI: {suggested_cmd}')
                print(f'    """')
                print(f'    # TODO: Implement CLI command')
                print(f'    # API endpoint: {ep.file_path}:{ep.line_number}')
                print(f'    pass\n')
    
    def export_json(self, output_file='api_cli_report.json'):
        """Export report as JSON."""
        data = {
            'total_endpoints': len(self.endpoints),
            'mapped_endpoints': sum(1 for ep in self.endpoints if ep.cli_mapped),
            'missing_endpoints': sum(1 for ep in self.endpoints if not ep.cli_mapped),
            'endpoints': [ep.to_dict() for ep in self.endpoints]
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n📊 Report exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Check API-CLI consistency and generate reports'
    )
    parser.add_argument(
        '--check', 
        action='store_true',
        help='Check for missing CLI mappings'
    )
    parser.add_argument(
        '--report', 
        action='store_true',
        help='Generate detailed report'
    )
    parser.add_argument(
        '--generate-stubs', 
        action='store_true',
        help='Generate CLI command stubs for missing mappings'
    )
    parser.add_argument(
        '--export-json',
        metavar='FILE',
        help='Export report as JSON'
    )
    parser.add_argument(
        '--api-root',
        default='src/modules/api',
        help='Root directory for API modules (default: src/modules/api)'
    )
    parser.add_argument(
        '--doc-path',
        default='docs/CLI_REDESIGN.md',
        help='Path to CLI redesign documentation (default: docs/CLI_REDESIGN.md)'
    )
    
    args = parser.parse_args()
    
    # If no flags, show help
    if not any([args.check, args.report, args.generate_stubs, args.export_json]):
        parser.print_help()
        return
    
    # Create checker
    checker = APICliSyncChecker(args.api_root, args.doc_path)
    
    # Run check
    missing = checker.check()
    
    # Generate outputs
    if args.check or args.report:
        checker.report(missing)
    
    if args.generate_stubs:
        checker.generate_stubs(missing)
    
    if args.export_json:
        checker.export_json(args.export_json)
    
    # Exit with error code if missing mappings
    if args.check and missing:
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
