from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    def load_dotenv(_path: Path) -> bool:
        return False


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == "ArcticCAD-Agent":
            return parent
    return Path.cwd()


PROJECT_ROOT = find_project_root()


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    base_url: str
    api_key: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    projects_dir: Path
    llm: ModelConfig
    vision: ModelConfig
    llm_timeout_seconds: float


def load_app_config() -> AppConfig:
    load_dotenv(PROJECT_ROOT / ".env")
    projects_dir_raw = os.environ.get("CADX_PROJECTS_DIR", "projects")
    projects_dir = Path(projects_dir_raw)
    if not projects_dir.is_absolute():
        projects_dir = PROJECT_ROOT / projects_dir

    return AppConfig(
        project_root=PROJECT_ROOT,
        projects_dir=projects_dir,
        llm=ModelConfig(
            provider=os.environ.get("CADX_LLM_PROVIDER", "deepseek"),
            base_url=os.environ.get("CADX_LLM_BASE_URL", "https://api.deepseek.com"),
            api_key=os.environ.get("CADX_LLM_API_KEY", ""),
            model=os.environ.get("CADX_LLM_MODEL", "deepseek-v4-pro"),
        ),
        vision=ModelConfig(
            provider=os.environ.get("CADX_LLM_VISION_PROVIDER", "siliconflow"),
            base_url=os.environ.get("CADX_LLM_VISION_BASE_URL", "https://api.siliconflow.cn/v1"),
            api_key=os.environ.get("CADX_LLM_VISION_API_KEY", ""),
            model=os.environ.get("CADX_LLM_VISION_MODEL", "Qwen/Qwen3.5-9B"),
        ),
        llm_timeout_seconds=float(os.environ.get("CADX_LLM_TIMEOUT_SECONDS", "1800")),
    )


def masked_status(value: str) -> str:
    return "configured" if value.strip() else "missing"
