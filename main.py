#!/usr/bin/env python3
"""
VedioHunter CLI — Agent 调用的底层命令行接口。

用法:
  python main.py search <关键词> [--limit N]
  python main.py fetch  <BVID或URL>
  python main.py transcribe <BVID>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def cmd_search(args):
    from src.bilibili_client import cli_search
    print(cli_search(args.keyword, args.limit))


def cmd_fetch(args):
    """获取视频元数据 + 字幕，输出 JSON."""
    import asyncio
    from src.bilibili_client import extract_bvid, fetch_video_info, fetch_subtitle

    bvid = extract_bvid(args.target)
    if not bvid:
        print(json.dumps({"error": f"无法解析 BVID: {args.target}"}, ensure_ascii=False))
        sys.exit(1)

    async def _fetch():
        info = await fetch_video_info(bvid)
        sub = await fetch_subtitle(bvid, info.get("cid"))
        return info, sub

    info, sub = asyncio.run(_fetch())

    result = {
        "meta": info,
        "subtitle": sub,
    }

    # 字幕未找到时标记需要转写
    if not sub.get("found"):
        result["needs_transcribe"] = True

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_transcribe(args):
    """下载音频并转写（CPU）."""
    from src.bilibili_client import extract_bvid
    from src.audio_transcriber import download_and_transcribe

    bvid = extract_bvid(args.target)
    if not bvid:
        print(json.dumps({"error": f"无法解析 BVID: {args.target}"}, ensure_ascii=False))
        sys.exit(1)

    result = download_and_transcribe(bvid)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="VedioHunter CLI")
    sub = parser.add_subparsers(dest="command")

    # search
    p_search = sub.add_parser("search", help="搜索B站视频")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--limit", type=int, default=5, help="结果数量上限")
    p_search.set_defaults(func=cmd_search)

    # fetch
    p_fetch = sub.add_parser("fetch", help="获取视频元数据+字幕")
    p_fetch.add_argument("target", help="BVID 或 B站视频 URL")
    p_fetch.set_defaults(func=cmd_fetch)

    # transcribe
    p_trans = sub.add_parser("transcribe", help="下载音频并转写")
    p_trans.add_argument("target", help="BVID 或 B站视频 URL")
    p_trans.set_defaults(func=cmd_transcribe)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
