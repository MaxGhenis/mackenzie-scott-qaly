"""GiveWell-style QALY cost-effectiveness model of MacKenzie Scott's giving."""
from .model import Results, load_params, run

__all__ = ["Results", "load_params", "run"]
__version__ = "0.1.0"
