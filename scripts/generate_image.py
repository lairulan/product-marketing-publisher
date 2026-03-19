#!/usr/bin/env python3
"""
产品营销 - 图片生成脚本
调用中央 generate-image 技能（AI Gateway + IMGBB）
保留本地图片库 + URL缓存 + 产品别名映射
"""

import os
import sys
import json
import argparse
import subprocess
import re
import time
import random
import base64
import tempfile

# 中央生图脚本路径
CENTRAL_SCRIPT = os.path.expanduser("~/.claude/skills/generate-image/scripts/generate_image.py")

# 本地图片库配置
DEFAULT_IMAGE_LIBRARY = "/Users/rulanlai/Desktop/向日癸手工食品2026.2.13 近半年图片"

# 预上传 URL 映射文件
URL_MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "image_url_mapping.json")

# IMGBB
IMGBB_API_URL = "https://api.imgbb.com/1/upload"

# 产品别名映射
PRODUCT_ALIASES = {
    "姜糖茶": ["姜茶"], "姜糖": ["姜茶"], "姜茶": ["姜茶"],
    "山楂六物膏": ["山楂六物膏", "六物"], "山楂膏": ["山楂六物膏"],
    "川贝枇杷膏": ["川贝枇杷膏"], "枇杷膏": ["川贝枇杷膏"],
    "柠檬膏": ["柠檬膏", "川贝陈皮柠檬膏", "西洋参柠檬膏"],
    "川贝陈皮柠檬膏": ["川贝陈皮柠檬膏"], "西洋参柠檬膏": ["西洋参柠檬膏"],
    "月禧膏": ["月禧膏"],
    "黑芝麻丸": ["芝麻丸"], "芝麻丸": ["芝麻丸"],
    "阿胶糕": ["阿胶糕"], "阿胶": ["阿胶糕"],
    "秋梨膏": ["秋梨膏", "川贝雪梨膏"], "雪梨膏": ["川贝雪梨膏"],
    "秘制牛肉酱": ["牛肉酱"], "牛肉酱": ["牛肉酱"],
    "麻辣毛毛鱼": ["毛毛鱼"], "毛毛鱼": ["毛毛鱼"],
    "黄豆酱": ["黄豆酱"],
    "脆辣木瓜丝": ["木瓜丝"], "木瓜丝": ["木瓜丝"],
    "雪花酥": ["雪花酥"], "蛋黄酥": ["蛋黄酥"],
    "广式蛋黄月饼": ["月饼"], "月饼": ["月饼"],
    "牛轧饼": ["牛扎饼"], "牛扎饼": ["牛扎饼"],
    "太妃糖": ["海盐太妃糖"], "海盐太妃糖": ["海盐太妃糖"],
    "糯米船": ["杏仁片船", "坚果船"],
    "凤梨酥": ["凤梨酥"], "绿豆糕": ["绿豆糕"],
    "奶枣": ["奶枣"], "海苔肉松蛋卷": ["海苔肉松蛋卷"],
    "烘焙": ["雪花酥", "蛋黄酥", "凤梨酥"],
    "甜品": ["雪花酥", "海盐太妃糖", "绿豆糕"],
    "养生": ["姜茶", "阿胶糕", "芝麻丸"],
}


def call_central_generate(prompt, upload_imgbb=True, output=None, retry=3):
    """调用中央生图脚本"""
    cmd = [
        sys.executable, CENTRAL_SCRIPT,
        prompt,
        "--json",
        "--retry", str(retry)
    ]
    if upload_imgbb:
        cmd.append("--upload-imgbb")
    if output:
        cmd.extend(["--output", output])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        stdout = result.stdout.strip()
        if not stdout:
            return {"success": False, "error": f"中央脚本无输出. stderr: {result.stderr[:500]}"}

        lines = stdout.split('\n')
        json_lines = []
        for line in reversed(lines):
            json_lines.insert(0, line)
            if line.strip().startswith('{'):
                break

        return json.loads('\n'.join(json_lines))
    except json.JSONDecodeError:
        return {"success": False, "error": "JSON 解析失败"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "生图超时", "code": "TIMEOUT"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def load_url_mapping():
    """加载预上传 URL 映射"""
    if not os.path.exists(URL_MAPPING_FILE):
        return {}
    try:
        with open(URL_MAPPING_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        product_urls = {}
        for path, info in raw.items():
            product = info.get("product", "")
            url = info.get("url", "")
            if product and url:
                product_urls.setdefault(product, []).append(url)
        return product_urls
    except Exception:
        return {}


def match_product(keyword, index):
    """从索引中模糊匹配产品"""
    if keyword in index:
        return index[keyword]
    if keyword in PRODUCT_ALIASES:
        for folder_key in PRODUCT_ALIASES[keyword]:
            if folder_key in index:
                return index[folder_key]
    for idx_key, images in index.items():
        if keyword in idx_key or idx_key in keyword:
            return images
    keyword_chars = set(keyword)
    best_match, best_score = None, 0
    for idx_key, images in index.items():
        common = keyword_chars & set(idx_key)
        score = len(common) / max(len(keyword_chars), len(set(idx_key)))
        if score > best_score and score >= 0.5:
            best_score = score
            best_match = images
    return best_match


def upload_to_imgbb(image_path):
    """上传本地图片到 IMGBB"""
    api_key = os.environ.get("IMGBB_API_KEY")
    if not api_key:
        return {"success": False, "error": "IMGBB_API_KEY 未设置"}

    if not os.path.isfile(image_path):
        return {"success": False, "error": f"文件不存在: {image_path}"}

    tmp_file = None
    try:
        with open(image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('ascii')

        tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.b64', delete=False)
        tmp_file.write(image_base64)
        tmp_file.close()

        cmd = [
            "curl", "-s", "-X", "POST", IMGBB_API_URL,
            "-F", f"key={api_key}",
            "-F", f"image=<{tmp_file.name}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        response = json.loads(result.stdout)

        if response.get("data", {}).get("url"):
            return {"success": True, "url": response["data"]["url"], "source": "imgbb"}

        return {"success": False, "error": f"IMGBB 上传失败: {str(response)[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if tmp_file and os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)


def index_local_images(library_path=None):
    """扫描本地图片库"""
    library_path = library_path or DEFAULT_IMAGE_LIBRARY
    if not os.path.isdir(library_path):
        return {"success": False, "index": {}}

    index = {}
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

    for item in os.listdir(library_path):
        item_path = os.path.join(library_path, item)
        if item.startswith('.') or not os.path.isdir(item_path):
            continue
        images = []
        for root, dirs, files in os.walk(item_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    images.append(os.path.join(root, file))
        if images:
            index[item] = images

    for alias, folder_keys in PRODUCT_ALIASES.items():
        if alias in index:
            continue
        for fk in folder_keys:
            for idx_key, imgs in index.items():
                if fk in idx_key or idx_key in fk:
                    index.setdefault(alias, []).extend(imgs)
                    break
    for key in index:
        index[key] = list(set(index[key]))

    return {"success": True, "index": index}


def generate_and_upload(prompt, retry=3, retry_delay=3, size="2048x2048"):
    """生成图片并上传（通过中央脚本）"""
    result = call_central_generate(prompt, upload_imgbb=True, retry=retry)
    if result.get("success"):
        return {
            "success": True,
            "url": result.get("imgbb_url") or result.get("url"),
            "display_url": result.get("imgbb_url") or result.get("url"),
            "prompt": prompt,
            "source": result.get("source", "ai-gateway")
        }
    return result


def generate_article_images(markdown_file, max_images=3, retry=3, retry_delay=3, size="2048x2048",
                            local_library=None, use_local_only=False):
    """为文章生成配图（三级优先级：缓存URL → 本地图片+IMGBB → AI生成+IMGBB）"""
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()

    placeholder_pattern = r'<!--\s*IMG_PLACEHOLDER:\s*\{([^}]+)\}\s*-->'
    placeholders = list(re.finditer(placeholder_pattern, content))

    if not placeholders:
        return {"success": False, "error": "未找到占位符", "code": "NO_PLACEHOLDERS"}

    url_mapping = load_url_mapping()
    local_index = None
    if local_library or use_local_only:
        idx_result = index_local_images(local_library)
        if idx_result.get("success"):
            local_index = idx_result["index"]

    generated_images = []

    for idx, match in enumerate(placeholders[:max_images]):
        placeholder_text = match.group(1)
        try:
            parts = {}
            for item in placeholder_text.split(','):
                if ':' in item:
                    key, value = item.split(':', 1)
                    parts[key.strip()] = value.strip().strip('"\'')
        except Exception:
            parts = {}

        image_url = None
        source = "ai"

        product_keywords = [parts.get(k, '') for k in ['主体', '产品', '名称'] if parts.get(k)]

        # 优先级 1: URL 缓存
        if url_mapping and product_keywords:
            for kw in product_keywords:
                urls = match_product(kw, url_mapping)
                if urls:
                    image_url = random.choice(urls)
                    source = "cached"
                    break

        # 优先级 2: 本地图片 + IMGBB
        if not image_url and local_index:
            for kw in product_keywords:
                images = match_product(kw, local_index)
                if images:
                    matched = random.choice(images)
                    upload_result = upload_to_imgbb(matched)
                    if upload_result.get("success"):
                        image_url = upload_result["url"]
                        source = "local"
                    break

        # 优先级 3: AI 生成 + IMGBB
        if not image_url and not use_local_only:
            prompt_parts = []
            for k, label in [('主体', 'Main subject'), ('动作/状态', 'Action'), ('场景/环境', 'Environment'), ('风格', 'Style')]:
                if k in parts:
                    prompt_parts.append(f"{label}: {parts[k]}")

            prompt = f"Professional product lifestyle photography. {', '.join(prompt_parts)}. Ultra high quality, 8K resolution, photorealistic, clean composition, warm and inviting atmosphere. NO text, NO Chinese characters, NO watermarks."
            gen_result = generate_and_upload(prompt, retry=retry)
            if gen_result.get("success"):
                image_url = gen_result["url"]
                source = gen_result.get("source", "ai-gateway")

        if image_url:
            generated_images.append({"placeholder": match.group(0), "image_url": image_url, "position": match.start(), "source": source})

        if idx < min(len(placeholders), max_images) - 1:
            time.sleep(1)

    if generated_images:
        for img in reversed(generated_images):
            content = content.replace(img['placeholder'], f"\n\n![产品配图]({img['image_url']})\n\n")

        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return {
            "success": True, "file": markdown_file, "images_generated": len(generated_images),
            "cached_urls_used": sum(1 for i in generated_images if i['source'] == 'cached'),
            "local_images_used": sum(1 for i in generated_images if i['source'] == 'local'),
            "ai_images_generated": sum(1 for i in generated_images if i['source'] not in ('cached', 'local')),
            "images": generated_images
        }
    return {"success": False, "error": "所有配图生成失败", "code": "ALL_FAILED"}


def main():
    parser = argparse.ArgumentParser(description="产品营销图片生成工具（中央引擎）")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    gen_parser = subparsers.add_parser("generate")
    gen_parser.add_argument("--prompt", "-p", required=True)
    gen_parser.add_argument("--retry", type=int, default=3)
    gen_parser.add_argument("--size", default="2048x2048")

    article_parser = subparsers.add_parser("article")
    article_parser.add_argument("--file", "-f", required=True)
    article_parser.add_argument("--max-images", "-n", type=int, default=3)
    article_parser.add_argument("--retry", type=int, default=3)
    article_parser.add_argument("--size", default="2048x2048")
    article_parser.add_argument("--local-library", "-l", default=None)
    article_parser.add_argument("--use-local-only", action="store_true")

    cover_parser = subparsers.add_parser("cover")
    cover_parser.add_argument("--title", "-t", required=True)
    cover_parser.add_argument("--style", "-s", default="warm", choices=["modern", "minimalist", "tech", "warm", "creative"])
    cover_parser.add_argument("--retry", type=int, default=3)
    cover_parser.add_argument("--size", default="2048x2048")

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--library", "-l", default=None)

    args = parser.parse_args()

    if args.command == "index":
        result = index_local_images(args.library)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "generate":
        result = generate_and_upload(args.prompt, retry=args.retry)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "article":
        result = generate_article_images(args.file, max_images=args.max_images, retry=args.retry, local_library=args.local_library, use_local_only=args.use_local_only)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "cover":
        style_prompts = {
            "modern": "professional magazine cover, modern aesthetic, vibrant elegant colors",
            "minimalist": "minimalist style, negative space, elegant simplicity",
            "tech": "futuristic technology, neon gradients, digital art style",
            "warm": "warm golden hour lighting, soft gradient background, inviting atmosphere, cozy vibe, pastel tones",
            "creative": "artistic creative, vibrant colors, modern illustration"
        }
        style_desc = style_prompts.get(args.style, style_prompts["warm"])
        prompt = f"Professional cover image for product marketing article: '{args.title}'. Ultra high quality, 8K. {style_desc}. NO text, NO Chinese characters, NO typography. Suitable for WeChat Official Account cover."
        result = generate_and_upload(prompt, retry=args.retry)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
