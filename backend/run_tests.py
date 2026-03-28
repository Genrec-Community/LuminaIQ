#!/usr/bin/env python
"""
Test runner script for LuminaIQ backend.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py unit         # Run only unit tests
    python run_tests.py integration  # Run only integration tests
    python run_tests.py -v           # Verbose output
"""

import sys
import subprocess


def run_tests(args=None):
    """Run pytest with the given arguments."""
    cmd = [sys.executable, "-m", "pytest"]
    
    if args:
        # Parse custom arguments
        if "unit" in args:
            cmd.extend(["-m", "unit"])
        elif "integration" in args:
            cmd.extend(["-m", "integration"])
        
        if "-v" in args or "--verbose" in args:
            cmd.append("-v")
        
        # Add any other arguments
        for arg in args:
            if arg not in ["unit", "integration", "-v", "--verbose"]:
                cmd.append(arg)
    
    # Run pytest
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=".")
    
    return result.returncode


if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else None
    exit_code = run_tests(args)
    sys.exit(exit_code)
