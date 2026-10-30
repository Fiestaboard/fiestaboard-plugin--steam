"""Load the package under its installed name, using a real FiestaBoard checkout."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CORE = Path(os.environ.get("FIESTABOARD_CORE", ROOT.parent / "FiestaBoard"))
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(ROOT))


def load_plugin():
    spec = importlib.util.spec_from_file_location("steam_plugin", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
