"""JSON serialization for GarminDB reports — mirrors presentation/markdown/."""

import dataclasses
import json
from datetime import date, datetime, time, timedelta
from enum import Enum


class ReportEncoder(json.JSONEncoder):
    """Custom JSON encoder for GarminDB report dataclass trees.
    
    Handles: date/datetime → ISO string, time → ISO string,
    timedelta → total_seconds, Enum → .value,
    @dataclass → dict (with computed @property inclusion).
    """

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return obj.total_seconds()
        if isinstance(obj, Enum):
            return obj.value
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            d = dataclasses.asdict(obj)
            # Include computed @property values (e.g. trend_icon, severity_icon, sparkline)
            for attr_name in dir(obj):
                prop = getattr(type(obj), attr_name, None)
                if isinstance(prop, property):
                    try:
                        d[attr_name] = getattr(obj, attr_name)
                    except Exception:
                        pass
            return d
        return super().default(obj)


def render_json(report) -> str:
    """Serialize a report dataclass (Health/Performance/Longitudinal) as JSON."""
    return json.dumps(
        report,
        cls=ReportEncoder,
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )
