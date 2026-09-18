import sys
from pathlib import Path


def main():
    from streamlit.web import cli as stcli

    app_path = str(Path(__file__).parent / "main.py")
    sys.argv = ["streamlit", "run", app_path]
    sys.exit(stcli.main())
