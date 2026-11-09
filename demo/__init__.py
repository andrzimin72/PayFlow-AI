"""
Demo Package for PayFlow AI
============================

Provides demonstration scripts and synthetic data generators
for showcasing platform capabilities without external dependencies.

Modules:
    - synthetic_data_generator: Generates realistic financial data
    - demo_terminal: Terminal-based demonstration
    - demo_dashboard: Streamlit dashboard demonstration

Usage:
    # Terminal demo
    python demo_terminal.py
    
    # Streamlit dashboard
    streamlit run demo_dashboard.py

Version: 1.0.0
"""

from demo.synthetic_data_generator import (
    SyntheticDataGenerator,
    generate_demo_data
)

__version__ = "1.0.0"
__author__ = "Andre Zimin"
__license__ = "Apache-2.0"

__all__ = [
    "SyntheticDataGenerator",
    "generate_demo_data",
    "__version__",
    "__author__",
    "__license__",
]
