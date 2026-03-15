#!/usr/bin/env python3
"""
产品营销图片生成脚本
使用豆包 (Doubao) SeeDream API 生成产品营销配图和封面图
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
import re
import time
import random

# API 配置
DOUBAO_IMAGE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
DOUBAO_IMAGE_MODEL = "doubao-seedream-4-5-251128"
IMGBB_API_URL = "https://api.imgbb.com/1/upload"

# 本地图片库配置 (注意: 文件夹名是"向日癸"不是"向日葵")
DEFAULT_IMAGE_LIBRARY = "/Users/rulanlai/Desktop/向日癸手工食品2026.2.13 近半年图片"

# 预上传 URL 映射文件（由 batch_upload.py 生成）
URL_MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "image_url_mapping.json")

# 产品别名映射：文章中可能出现的名称 → 本地图片库文件夹名
# 每个 key 是一个可能在文章中出现的关键词，value 是对应的文件夹关键词列表
PRODUCT_ALIASES = {
    # 养生食品
    "姜糖茶": ["姜茶"], "姜糖": ["姜茶"], "姜茶": ["姜茶"],
    "山楂六物膏": ["山楂六物膏", "六物"], "山楂膏": ["山楂六物膏"],
    "川贝枇杷膏": ["川贝枇杷膏"], "枇杷膏": ["川贝枇杷膏"],
    "柠檬膏": ["柠檬膏", "川贝陈皮柠檬膏", "西洋参柠檬膏"],
    "川贝陈皮柠檬膏": ["川贝陈皮柠檬膏"], "西洋参柠檬膏": ["西洋参柠檬膏"],
    "月禧膏": ["月禧膏"],
    "黑芝麻丸": ["芝麻丸"], "芝麻丸": ["芝麻丸"],
    "阿胶糕": ["阿胶糕"], "阿胶": ["阿胶糕"],
    "秋梨膏": ["秋梨膏", "川贝雪梨膏"], "雪梨膏": ["川贝雪梨膏"],
    # 麻辣开味
    "秘制牛肉酱": ["牛肉酱"], "牛肉酱": ["牛肉酱"],
    "麻辣毛毛鱼": ["毛毛鱼"], "毛毛鱼": ["毛毛鱼"],
    "黄豆酱": ["黄豆酱"],
    "脆辣木瓜丝": ["木瓜丝"], "木瓜丝": ["木瓜丝"],
    # 网红烘焙甜品
    "雪花酥": ["雪花酥"], "蛋黄酥": ["蛋黄酥"],
    "广式蛋黄月饼": ["月饼"], "月饼": ["月饼"],
    "牛轧饼": ["牛扎饼"], "牛扎饼": ["牛扎饼"],
    "太妃糖": ["海盐太妃糖"], "海盐太妃糖": ["海盐太妃糖"],
    "糯米船": ["杏仁片船", "坚果船"],
    "凤梨酥": ["凤梨酥"], "绿豆糕": ["绿豆糕"],
    "奶枣": ["奶枣"], "海苔肉松蛋卷": ["海苔肉松蛋卷"],
    # 通用品类关键词
    "烘焙": ["雪花酥", "蛋黄酥", "凤梨酥"],
    "甜品": ["雪花酥", "海盐太妃糖", "绿豆糕"],
    "养生": ["姜茶", "阿胶糕", "芝麻丸"],
}


def get_env_var(name, default=None):
    """获取环境变量"""
    value = os.environ.get(name, default)
    if not value:
        print(json.dumps({
            "success": False,
            "error": f"环境变量 {name} 未设置",
            "code": "ENV_VAR_MISSING"
        }, ensure_ascii=False))
        sys.exit(1)
    return value


def load_url_mapping():
    """加载预上传 URL 映射，返回 product→[url] 索引"""
    if not os.path.exists(URL_MAPPING_FILE):
        return {}

    with open(URL_MAPPING_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    # 按 product 字段分组
    product_urls = {}
    for path, info in raw.items():
        product = info.get("product", "")
        url = info.get("url", "")
        if product and url:
            product_urls.setdefault(product, []).append(url)
    return product_urls


def upload_to_imgbb(image_path):
    """上传本地图片到 IMGBB，返回公网 URL"""
    api_key = os.environ.get("IMGBB_API_KEY")
    if not api_key:
        return {"success": False, "error": "IMGBB_API_KEY 未设置", "code": "API_KEY_MISSING"}

    if not os.path.isfile(image_path):
        return {"success": False, "error": f"文件不存在: {image_path}", "code": "FILE_NOT_FOUND"}

    tmp_file = None
    try:
        import base64

        # 读取图片并转为 base64
        with open(image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('ascii')

        # 写入临时文件避免 "Argument list too long" 错误（大 PNG 文件）
        tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.b64', delete=False)
        tmp_file.write(image_base64)
        tmp_file.close()

        # IMGBB API v1 仅支持 form-data（不支持 JSON）
        cmd = [
            "curl", "-s", "-X", "POST", IMGBB_API_URL,
            "-F", f"key={api_key}",
            "-F", f"image=<{tmp_file.name}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        response = json.loads(result.stdout)

        if "data" in response and "url" in response["data"]:
            return {
                "success": True,
                "url": response["data"]["url"],
                "delete_url": response["data"].get("delete_url", ""),
                "source": "imgbb"
            }

        error_info = response.get("error", {})
        error_msg = error_info.get("message", str(response)) if isinstance(error_info, dict) else str(error_info)
        return {
            "success": False,
            "error": f"IMGBB 上传失败: {error_msg}",
            "code": "IMGBB_UPLOAD_FAILED",
            "response": str(response)[:500]
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "上传超时", "code": "TIMEOUT"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"响应解析失败: {str(e)}", "code": "PARSE_ERROR"}
    except Exception as e:
        return {"success": False, "error": str(e), "code": "UNKNOWN_ERROR"}
    finally:
        if tmp_file and os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)


def match_product(keyword, index):
    """从索引中查找匹配的产品图片列表，支持别名和模糊匹配"""
    # 1. 精确匹配
    if keyword in index:
        return index[keyword]

    # 2. 通过 PRODUCT_ALIASES 别名匹配
    if keyword in PRODUCT_ALIASES:
        for folder_key in PRODUCT_ALIASES[keyword]:
            if folder_key in index:
                return index[folder_key]

    # 3. 子串匹配（keyword 包含 idx_key 或 idx_key 包含 keyword）
    for idx_key, images in index.items():
        if keyword in idx_key or idx_key in keyword:
            return images

    # 4. 单字符模糊匹配（共享字符比例 >= 50%）
    best_match = None
    best_score = 0
    keyword_chars = set(keyword)
    for idx_key, images in index.items():
        idx_chars = set(idx_key)
        common = keyword_chars & idx_chars
        score = len(common) / max(len(keyword_chars), len(idx_chars))
        if score > best_score and score >= 0.5:
            best_score = score
            best_match = images
    return best_match


def index_local_images(library_path=None):
    """扫描本地图片库，建立产品→图片列表映射"""
    library_path = library_path or DEFAULT_IMAGE_LIBRARY

    if not os.path.isdir(library_path):
        return {
            "success": False,
            "error": f"图片库目录不存在: {library_path}",
            "code": "LIBRARY_NOT_FOUND",
            "index": {}
        }

    index = {}
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

    for item in os.listdir(library_path):
        item_path = os.path.join(library_path, item)
        if item.startswith('.') or not os.path.isdir(item_path):
            continue

        product_name = item
        images = []
        for root, dirs, files in os.walk(item_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    images.append(os.path.join(root, file))

        if images:
            index[product_name] = images

    # 通过 PRODUCT_ALIASES 反向注册：为每个别名建立索引入口
    for alias, folder_keys in PRODUCT_ALIASES.items():
        if alias in index:
            continue
        for fk in folder_keys:
            for idx_key, imgs in index.items():
                if fk in idx_key or idx_key in fk:
                    index.setdefault(alias, []).extend(imgs)
                    break

    # 去重
    for key in index:
        index[key] = list(set(index[key]))

    return {
        "success": True,
        "library_path": library_path,
        "total_products": len(index),
        "total_images": sum(len(imgs) for imgs in index.values()),
        "index": index
    }


def get_random_local_image(product_name, index=None):
    """从本地图片库随机获取一张产品图片"""
    if index is None:
        index_result = index_local_images()
        if not index_result.get("success"):
            return None
        index = index_result["index"]

    images = match_product(product_name, index)
    if not images:
        return None
    return random.choice(images)


def generate_image(prompt, retry=3, retry_delay=3, size="2048x2048"):
    """调用豆包图片生成 API（带重试机制）"""
    api_key = get_env_var("DOUBAO_API_KEY")
    last_error = None

    for attempt in range(retry):
        if attempt > 0:
            print(json.dumps({
                "status": "retrying",
                "message": f"重试第 {attempt}/{retry-1} 次...",
                "delay": retry_delay
            }, ensure_ascii=False), file=sys.stderr)
            time.sleep(retry_delay)

        data = {
            "model": DOUBAO_IMAGE_MODEL,
            "prompt": prompt,
            "response_format": "url",
            "size": size,
            "guidance_scale": 3,
            "watermark": False
        }

        try:
            cmd = [
                "curl", "-s", "-X", "POST", DOUBAO_IMAGE_API_URL,
                "-H", f"Authorization: Bearer {api_key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(data, ensure_ascii=False)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            response = json.loads(result.stdout)

            if "error" in response:
                last_error = {
                    "success": False,
                    "error": f"API错误: {response['error'].get('message', str(response['error']))}",
                    "code": "API_ERROR",
                    "attempt": attempt + 1
                }
                print(json.dumps(last_error, ensure_ascii=False), file=sys.stderr)
                continue

            if "data" in response and len(response["data"]) > 0:
                image_url = response["data"][0].get("url")
                if image_url:
                    return {
                        "success": True,
                        "url": image_url,
                        "attempts": attempt + 1,
                        "source": "doubao"
                    }

            last_error = {
                "success": False,
                "error": "未能从响应中提取图片 URL",
                "response": str(response)[:500],
                "attempt": attempt + 1
            }
            print(json.dumps(last_error, ensure_ascii=False), file=sys.stderr)

        except subprocess.TimeoutExpired:
            last_error = {"success": False, "error": "图片生成超时", "code": "TIMEOUT", "attempt": attempt + 1}
            print(json.dumps(last_error, ensure_ascii=False), file=sys.stderr)
        except json.JSONDecodeError as e:
            last_error = {"success": False, "error": f"响应解析失败: {str(e)}", "code": "PARSE_ERROR", "attempt": attempt + 1}
            print(json.dumps(last_error, ensure_ascii=False), file=sys.stderr)
        except Exception as e:
            last_error = {"success": False, "error": str(e), "code": "UNKNOWN_ERROR", "attempt": attempt + 1}
            print(json.dumps(last_error, ensure_ascii=False), file=sys.stderr)

    return last_error if last_error else {"success": False, "error": "图片生成失败", "code": "ALL_RETRIES_FAILED"}


def generate_and_upload(prompt, retry=3, retry_delay=3, size="2048x2048"):
    """生成图片（豆包 API 直接返回 URL）"""
    print(json.dumps({"status": "generating", "message": "正在生成图片...", "prompt": prompt[:100]}, ensure_ascii=False), file=sys.stderr)

    gen_result = generate_image(prompt, retry=retry, retry_delay=retry_delay, size=size)

    if not gen_result.get("success"):
        return gen_result

    print(json.dumps({"status": "completed", "message": "图片生成成功"}, ensure_ascii=False), file=sys.stderr)

    return {
        "success": True,
        "url": gen_result["url"],
        "display_url": gen_result["url"],
        "prompt": prompt,
        "generate_attempts": gen_result.get("attempts", 1),
        "source": "doubao"
    }


def generate_article_images(markdown_file, max_images=3, retry=3, retry_delay=3, size="2048x2048",
                        local_library=None, use_local_only=False):
    """为文章生成配图（支持本地图片或AI生成）"""
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()

    placeholder_pattern = r'<!--\s*IMG_PLACEHOLDER:\s*\{([^}]+)\}\s*-->'
    placeholders = list(re.finditer(placeholder_pattern, content))

    if not placeholders:
        print(json.dumps({"success": False, "error": "未找到 IMG_PLACEHOLDER 占位符"}, ensure_ascii=False))
        return {"success": False, "error": "未找到占位符", "code": "NO_PLACEHOLDERS"}

    print(json.dumps({
        "status": "analyzing",
        "message": f"找到 {len(placeholders)} 个图片占位符"
    }, ensure_ascii=False), file=sys.stderr)

    # 加载预上传 URL 映射（优先使用缓存 URL，无需重新上传）
    url_mapping = load_url_mapping()
    if url_mapping:
        print(json.dumps({
            "status": "url_mapping_loaded",
            "total_products": len(url_mapping),
            "total_urls": sum(len(urls) for urls in url_mapping.values())
        }, ensure_ascii=False), file=sys.stderr)

    # 初始化本地图片索引（仅在没有 URL 映射命中时才需要）
    local_index = None
    if local_library or use_local_only:
        index_result = index_local_images(local_library)
        if index_result.get("success"):
            local_index = index_result["index"]
            print(json.dumps({
                "status": "local_index_loaded",
                "total_products": index_result["total_products"],
                "total_images": index_result["total_images"]
            }, ensure_ascii=False), file=sys.stderr)
        else:
            print(json.dumps({
                "status": "warning",
                "message": f"本地图片索引失败: {index_result.get('error', 'unknown')}"
            }, ensure_ascii=False), file=sys.stderr)
            if use_local_only:
                return {"success": False, "error": "本地图片索引失败", "code": "INDEX_FAILED"}

    generated_images = []

    for idx, match in enumerate(placeholders[:max_images]):
        placeholder_text = match.group(1)
        print(json.dumps({
            "status": "processing",
            "message": f"处理第 {idx+1}/{min(len(placeholders), max_images)} 张配图"
        }, ensure_ascii=False), file=sys.stderr)

        # 解析占位符获取产品关键词
        try:
            parts = {}
            for item in placeholder_text.split(','):
                if ':' in item:
                    key, value = item.split(':', 1)
                    parts[key.strip()] = value.strip().strip('"\'')
        except Exception:
            parts = {}

        # 尝试从本地图片库匹配
        local_image_used = False
        image_url = None

        # 提取产品名称用于匹配
        product_keywords = []
        for key in ['主体', '产品', '名称']:
            if key in parts and parts[key]:
                product_keywords.append(parts[key])

        # 优先级 1: 从预上传 URL 映射中查找（最快，无需网络请求）
        if url_mapping and product_keywords:
            for keyword in product_keywords:
                urls = match_product(keyword, url_mapping)
                if urls:
                    image_url = random.choice(urls)
                    local_image_used = True
                    print(json.dumps({
                        "status": "using_cached_url",
                        "message": f"使用缓存 URL (关键词: {keyword})"
                    }, ensure_ascii=False), file=sys.stderr)
                    break

        # 优先级 2: 从本地图片库扫描并上传
        if not image_url and local_index:
            matched_image = None
            for keyword in product_keywords:
                images = match_product(keyword, local_index)
                if images:
                    matched_image = random.choice(images)
                    break

            if matched_image:
                print(json.dumps({
                    "status": "using_local_image",
                    "message": f"使用本地图片: {matched_image}"
                }, ensure_ascii=False), file=sys.stderr)

                # 上传本地图片到 IMGBB
                upload_result = upload_to_imgbb(matched_image)
                if upload_result.get("success"):
                    image_url = upload_result["url"]
                    local_image_used = True

        # 如果本地图片失败或不使用本地，则 AI 生成
        if not image_url and not use_local_only:
            print(json.dumps({
                "status": "generating_ai_image",
                "message": "AI 生成图片"
            }, ensure_ascii=False), file=sys.stderr)

            prompt_parts = []
            if '主体' in parts:
                prompt_parts.append(f"Main subject: {parts['主体']}")
            if '动作/状态' in parts:
                prompt_parts.append(f"Action/State: {parts['动作/状态']}")
            if '场景/环境' in parts:
                prompt_parts.append(f"Environment: {parts['场景/环境']}")
            if '风格' in parts:
                prompt_parts.append(f"Style: {parts['风格']}")

            prompt = f"Professional product lifestyle photography. {', '.join(prompt_parts)}. Ultra high quality, 8K resolution, photorealistic, clean composition, warm and inviting atmosphere, soft natural lighting, sharp details. Critical constraints: NO text, NO Chinese characters, NO typography, NO watermarks."

            gen_result = generate_and_upload(prompt, retry=retry, retry_delay=retry_delay, size=size)
            if gen_result.get("success"):
                image_url = gen_result["url"]

        if image_url:
            generated_images.append({
                "placeholder": match.group(0),
                "image_url": image_url,
                "position": match.start(),
                "source": "cached" if local_image_used and url_mapping else ("local" if local_image_used else "ai")
            })

        if idx < min(len(placeholders), max_images) - 1:
            time.sleep(1)

    if generated_images:
        for img in reversed(generated_images):
            markdown_img = f"\n\n![产品配图]({img['image_url']})\n\n"
            content = content.replace(img['placeholder'], markdown_img)

        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return {
            "success": True,
            "file": markdown_file,
            "images_generated": len(generated_images),
            "cached_urls_used": sum(1 for img in generated_images if img['source'] == 'cached'),
            "local_images_used": sum(1 for img in generated_images if img['source'] == 'local'),
            "ai_images_generated": sum(1 for img in generated_images if img['source'] == 'ai'),
            "images": generated_images
        }
    else:
        return {"success": False, "error": "所有配图生成失败", "code": "ALL_FAILED"}


def main():
    parser = argparse.ArgumentParser(description="产品营销图片生成工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # generate 命令
    gen_parser = subparsers.add_parser("generate", help="生成图片")
    gen_parser.add_argument("--prompt", "-p", required=True, help="图片描述提示词")
    gen_parser.add_argument("--retry", type=int, default=3, help="失败重试次数")
    gen_parser.add_argument("--retry-delay", type=int, default=3, help="重试延迟秒数")
    gen_parser.add_argument("--size", default="2048x2048", help="图片尺寸")

    # article 命令
    article_parser = subparsers.add_parser("article", help="为文章生成配图")
    article_parser.add_argument("--file", "-f", required=True, help="Markdown 文章文件路径")
    article_parser.add_argument("--max-images", "-n", type=int, default=3, help="最大配图数量")
    article_parser.add_argument("--retry", type=int, default=3, help="失败重试次数")
    article_parser.add_argument("--retry-delay", type=int, default=3, help="重试延迟秒数")
    article_parser.add_argument("--size", default="2048x2048", help="图片尺寸")
    article_parser.add_argument("--local-library", "-l", default=None, help="本地图片库路径")
    article_parser.add_argument("--use-local-only", action="store_true", help="仅使用本地图片，不调用AI生成")

    # cover 命令
    cover_parser = subparsers.add_parser("cover", help="生成封面图")
    cover_parser.add_argument("--title", "-t", required=True, help="文章标题")
    cover_parser.add_argument("--style", "-s", default="warm",
                             choices=["modern", "minimalist", "tech", "warm", "creative"],
                             help="封面风格")
    cover_parser.add_argument("--retry", type=int, default=3, help="失败重试次数")
    cover_parser.add_argument("--retry-delay", type=int, default=3, help="重试延迟秒数")
    cover_parser.add_argument("--size", default="2048x2048", help="图片尺寸")

    # index 命令
    index_parser = subparsers.add_parser("index", help="索引本地图片库")
    index_parser.add_argument("--library", "-l", default=None, help="图片库路径")

    args = parser.parse_args()

    if args.command == "index":
        result = index_local_images(args.library)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "generate":
        result = generate_and_upload(args.prompt, retry=args.retry, retry_delay=args.retry_delay, size=args.size)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "article":
        result = generate_article_images(
            args.file, max_images=args.max_images,
            retry=args.retry, retry_delay=args.retry_delay, size=args.size,
            local_library=args.local_library, use_local_only=args.use_local_only
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "cover":
        style_prompts = {
            "modern": "ultra high quality, 8K, professional magazine cover, clean composition, modern aesthetic, vibrant elegant colors, premium design, photorealistic lighting",
            "minimalist": "ultra high quality, 8K, minimalist style, negative space, elegant simplicity, soft natural lighting, premium feel, zen atmosphere",
            "tech": "ultra high quality, 8K, futuristic technology, neon gradients, digital art style, high tech atmosphere, clean composition",
            "warm": "ultra high quality, 8K, warm golden hour lighting, soft gradient background, inviting atmosphere, cozy vibe, pastel tones, gentle warm aesthetic",
            "creative": "ultra high quality, 8K, artistic creative, vibrant colors, modern illustration, eye-catching composition, bold but tasteful"
        }

        style_desc = style_prompts.get(args.style, style_prompts["warm"])
        prompt = f"Professional cover image for product marketing article: '{args.title}'. {style_desc}. Critical constraints: NO text, NO Chinese characters, NO typography. Suitable for WeChat Official Account cover. Clean, visually striking, horizontal landscape orientation."

        result = generate_and_upload(prompt, retry=args.retry, retry_delay=args.retry_delay, size=args.size)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
