from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class AuditResult:
    url: str
    final_url: str
    status_code: int
    response_time_ms: int
    page_size_kb: float
    title: Optional[str]
    meta_description: Optional[str]
    has_viewport: bool
    has_canonical: bool
    has_open_graph: bool
    has_schema: bool
    has_sitemap: bool
    has_robots: bool
    footer_year: Optional[int]
    stale_footer: bool
    detected_platform: Optional[str]
    https_enabled: bool
    opportunity_score: int
    issues: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return asdict(self)
