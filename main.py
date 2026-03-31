#!/usr/bin/env python3
"""
VideoHunter CLI — Agent 调用的底层命令行接口。

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


def cmd_list_candidates(args):
    """从搜索结果 URL 列出当页候选，并默认标记前 N 条为选中。"""
    from src.batch.candidate_preview import build_search_url_preview

    result = asyncio.run(
        build_search_url_preview(
            search_url=args.url,
            default_top_n=args.default_top,
            limit=args.limit,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_batch_process(args):
    """按可复用批处理引擎处理一个搜索结果 URL 的当页视频。"""
    from src.batch_processor import run_search_url_batch

    result = asyncio.run(
        run_search_url_batch(
            search_url=args.url,
            topic=args.topic,
            selected_arg=args.selected,
            skip_existing=(not args.reprocess),
            default_top_n=args.default_top,
            limit=args.limit,
            include_full_text=args.include_full_text,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="VideoHunter CLI")
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

    # list-candidates
    p_list = sub.add_parser("list-candidates", help="列出搜索URL当页候选，默认勾选前N条")
    p_list.add_argument("url", help="B站搜索结果 URL")
    p_list.add_argument("--default-top", type=int, default=10, help="默认勾选前N条")
    p_list.add_argument("--limit", type=int, default=50, help="当页最多拉取多少条候选")
    p_list.set_defaults(func=cmd_list_candidates)

    # batch-process
    p_batch = sub.add_parser("batch-process", help="按选中集合批量处理搜索URL当页视频")
    p_batch.add_argument("url", help="B站搜索结果 URL")
    p_batch.add_argument("--topic", required=True, help="归档主题名（必填）")
    p_batch.add_argument("--selected", default=None, help="序号或BVID列表，如 '1,2,5' 或 'BVxxx,BVyyy'")
    p_batch.add_argument("--default-top", type=int, default=10, help="未指定 --selected 时默认勾选前N条")
    p_batch.add_argument("--limit", type=int, default=50, help="当页最多拉取多少条候选")
    p_batch.add_argument("--reprocess", action="store_true", help="重新处理已归档视频")
    group = p_batch.add_mutually_exclusive_group()
    group.add_argument("--full-text", dest="include_full_text", action="store_true", help="归档中保留完整文本")
    group.add_argument("--no-full-text", dest="include_full_text", action="store_false", help="归档中省略完整文本")
    p_batch.set_defaults(include_full_text=None)
    p_batch.set_defaults(func=cmd_batch_process)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
