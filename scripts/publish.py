#!/usr/bin/env python3
"""
微信公众号发布脚本
通过微绿流量宝 API 将文章发布到公众号草稿箱
"""

import os
import sys
import json
import argparse
import subprocess

API_BASE = "https://wx.limyai.com/api/openapi"


def get_api_key(override=None):
    """获取 API Key，优先使用传入的 override 值"""
    api_key = override or os.environ.get("WECHAT_API_KEY")
    if not api_key:
        print(json.dumps({
            "success": False,
            "error": "未提供 API Key（--api-key 参数或 WECHAT_API_KEY 环境变量）",
            "code": "API_KEY_MISSING"
        }, ensure_ascii=False))
        sys.exit(1)
    return api_key


def make_request(endpoint, data=None, api_key_override=None):
    """发送 API 请求"""
    api_key = get_api_key(api_key_override)
    url = f"{API_BASE}/{endpoint}"

    print(json.dumps({
        "debug": "发送请求",
        "url": url,
        "data_keys": list(data.keys()) if data else []
    }, ensure_ascii=False), file=sys.stderr)

    cmd = [
        "curl", "-s", "-X", "POST", url,
        "-H", f"X-API-Key: {api_key}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(data or {}, ensure_ascii=False)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)

        if not response.get("success", False):
            error_obj = response.get('error', {})
            error_msg = error_obj.get('message', str(error_obj)) if isinstance(error_obj, dict) else str(error_obj)
            return {
                "success": False,
                "error": f"微信API返回错误: {error_msg}",
                "code": "WECHAT_API_ERROR",
                "raw_response": response
            }

        return response
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "请求超时", "code": "TIMEOUT"}
    except json.JSONDecodeError:
        return {"success": False, "error": f"响应解析失败: {result.stdout[:500]}", "code": "PARSE_ERROR"}
    except Exception as e:
        return {"success": False, "error": str(e), "code": "UNKNOWN_ERROR"}


def remove_frontmatter(content):
    """移除 Markdown 文件的 YAML frontmatter"""
    if content.startswith('---\n'):
        end_index = content.find('\n---\n', 4)
        if end_index != -1:
            return content[end_index + 5:].lstrip('\n')
    return content


def list_accounts(api_key_override=None):
    """获取公众号列表"""
    result = make_request("wechat-accounts", api_key_override=api_key_override)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def publish_article(args):
    """发布文章到草稿箱"""
    content = args.content
    if args.content_file:
        with open(args.content_file, 'r', encoding='utf-8') as f:
            content = f.read()
        content = remove_frontmatter(content)

    data = {
        "wechatAppid": args.appid,
        "title": args.title,
        "content": content,
        "contentFormat": "markdown"
    }

    if args.summary:
        data["summary"] = args.summary[:60]
    if args.cover:
        data["coverImage"] = args.cover
    if args.author:
        data["author"] = args.author[:10]
    if args.type:
        data["articleType"] = args.type

    result = make_request("wechat-publish", data, api_key_override=args.api_key)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="微信公众号发布工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    list_parser = subparsers.add_parser("list", help="获取公众号列表")
    list_parser.add_argument("--api-key", help="微绿流量宝 API Key（覆盖环境变量）")

    publish_parser = subparsers.add_parser("publish", help="发布文章")
    publish_parser.add_argument("--appid", required=True, help="公众号 AppID")
    publish_parser.add_argument("--title", required=True, help="文章标题")
    publish_parser.add_argument("--content", help="文章内容 (Markdown)")
    publish_parser.add_argument("--content-file", help="从文件读取内容")
    publish_parser.add_argument("--summary", help="文章摘要")
    publish_parser.add_argument("--cover", help="封面图 URL")
    publish_parser.add_argument("--author", help="作者名称")
    publish_parser.add_argument("--type", choices=["news", "newspic"], default="news", help="文章类型")
    publish_parser.add_argument("--api-key", help="微绿流量宝 API Key（覆盖环境变量）")

    args = parser.parse_args()

    if args.command == "list":
        list_accounts(api_key_override=args.api_key)
    elif args.command == "publish":
        publish_article(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
