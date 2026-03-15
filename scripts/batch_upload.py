#!/usr/bin/env python3
"""
批量上传本地产品图片到 IMGBB 图床
支持断点续传，进度保存到 JSON 映射文件
"""

import os
import sys
import json
import base64
import subprocess
import time
import signal

IMGBB_API_URL = "https://api.imgbb.com/1/upload"
DEFAULT_LIBRARY = "/Users/rulanlai/Desktop/向日癸手工食品2026.2.13 近半年图片"
MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "image_url_mapping.json")
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

# 优雅退出
stop_flag = False
def signal_handler(sig, frame):
    global stop_flag
    print("\n收到中断信号，正在保存进度后退出...", file=sys.stderr)
    stop_flag = True
signal.signal(signal.SIGINT, signal_handler)


def load_mapping():
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_mapping(mapping):
    os.makedirs(os.path.dirname(MAPPING_FILE), exist_ok=True)
    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def upload_one(image_path, api_key):
    """上传单张图片到 IMGBB，返回 URL 或 None"""
    import tempfile
    tmp_file = None
    try:
        with open(image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('ascii')

        # 写入临时文件避免 "Argument list too long" 错误
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

        if "data" in response and "url" in response["data"]:
            return response["data"]["url"]

        error = response.get("error", {})
        msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        print(f"  上传失败: {msg}", file=sys.stderr)
        return None

    except subprocess.TimeoutExpired:
        print(f"  上传超时", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  错误: {e}", file=sys.stderr)
        return None
    finally:
        if tmp_file and os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)


def collect_images(library_path):
    """收集所有图片，返回 [(product, filepath), ...]"""
    images = []
    for item in sorted(os.listdir(library_path)):
        item_path = os.path.join(library_path, item)
        if item.startswith('.') or not os.path.isdir(item_path):
            continue
        for root, dirs, files in os.walk(item_path):
            for f in sorted(files):
                if any(f.lower().endswith(ext) for ext in IMAGE_EXTS):
                    images.append((item, os.path.join(root, f)))
    return images


def main():
    api_key = os.environ.get("IMGBB_API_KEY")
    if not api_key:
        print("错误: IMGBB_API_KEY 环境变量未设置", file=sys.stderr)
        sys.exit(1)

    library = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LIBRARY
    if not os.path.isdir(library):
        print(f"错误: 目录不存在 {library}", file=sys.stderr)
        sys.exit(1)

    # 加载已有映射
    mapping = load_mapping()
    print(f"已有映射: {len(mapping)} 张图片", file=sys.stderr)

    # 收集所有图片
    all_images = collect_images(library)
    total = len(all_images)
    print(f"扫描到: {total} 张图片", file=sys.stderr)

    # 过滤已上传的
    to_upload = [(p, fp) for p, fp in all_images if fp not in mapping]
    print(f"待上传: {len(to_upload)} 张 (跳过已上传 {total - len(to_upload)} 张)", file=sys.stderr)

    if not to_upload:
        print("所有图片已上传完毕！")
        print(json.dumps({"success": True, "total": total, "uploaded": 0, "skipped": total}))
        return

    uploaded = 0
    failed = 0
    current_product = ""

    for idx, (product, filepath) in enumerate(to_upload):
        if stop_flag:
            break

        if product != current_product:
            current_product = product
            print(f"\n[{product}]", file=sys.stderr)

        filename = os.path.basename(filepath)
        progress = f"({idx+1}/{len(to_upload)})"
        print(f"  {progress} 上传: {filename}...", end="", file=sys.stderr, flush=True)

        url = upload_one(filepath, api_key)
        if url:
            mapping[filepath] = {
                "url": url,
                "product": product,
                "filename": filename
            }
            uploaded += 1
            print(f" OK", file=sys.stderr)
        else:
            failed += 1
            print(f" FAILED", file=sys.stderr)

        # 每上传 10 张保存一次进度
        if uploaded % 10 == 0:
            save_mapping(mapping)

        # 避免触发速率限制
        time.sleep(0.5)

    # 最终保存
    save_mapping(mapping)

    result = {
        "success": True,
        "total_images": total,
        "newly_uploaded": uploaded,
        "failed": failed,
        "skipped": total - len(to_upload),
        "total_in_mapping": len(mapping),
        "mapping_file": MAPPING_FILE
    }
    if stop_flag:
        result["interrupted"] = True
        result["message"] = "用户中断，进度已保存，再次运行可继续"

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
