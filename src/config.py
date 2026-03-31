"""VideoHunter 全局配置."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 路径 ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
TMP_DIR = PROJECT_ROOT / "tmp"

# ── B站凭证 ──────────────────────────────────────────
BILIBILI_SESSDATA: str = os.getenv("BILIBILI_SESSDATA", "")

# ── 搜索 ─────────────────────────────────────────────
SEARCH_LIMIT: int = int(os.getenv("SEARCH_LIMIT", "5"))

# ── 归档策略 ─────────────────────────────────────────
KEEP_FULL_TEXT: bool = os.getenv("KEEP_FULL_TEXT", "true").lower() in {
	"1", "true", "yes", "y", "on"
}

AUTO_ADD_IDEA_TIME: bool = os.getenv("AUTO_ADD_IDEA_TIME", "true").lower() in {
	"1", "true", "yes", "y", "on"
}

# ── Whisper 转写 ─────────────────────────────────────
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
