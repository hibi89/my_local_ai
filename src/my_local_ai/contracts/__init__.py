"""My Local AI contracts: parsing never grants execution approval."""
from .plan import PlanSpec, canonical_digest
from .task import TaskSpec, safe_path
__all__ = ["PlanSpec", "TaskSpec", "canonical_digest", "safe_path"]
