from pathlib import Path

import yaml

from .models import ICP


def load_icp(path: str | Path) -> ICP:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return ICP.model_validate(data)


def icp_prompt(icp: ICP) -> str:
    lines = [f"Product: {icp.product}", f"Ideal customers: {icp.customers}"]
    if icp.buying_signals:
        lines.append("Buying signals: " + "; ".join(icp.buying_signals))
    if icp.exclude:
        lines.append("Not a fit: " + "; ".join(icp.exclude))
    return "\n".join(lines)
