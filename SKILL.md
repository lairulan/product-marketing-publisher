---
name: product-marketing-publisher
version: 1.0.0
description: 产品营销宣传自动化内容生成与发布工具。支持多品牌管理，自动搜集网络热点素材，AI生成产品软文和种草测评文章（1500-2000字），生成封面图，保存到Obsidian并可一键发布到微信公众号。触发词："产品营销"、"写软文"、"种草文"、"产品推广"、"品牌营销"、"生成营销文章"、"product marketing"。
author: rulanlai
tags: [marketing, content-generation, wechat, obsidian, ai]
---

# Product Marketing Publisher

多品牌产品营销内容自动化生成与发布系统。

## Step -1: 环境依赖预检

执行任何操作前，先验证环境变量：

| 环境变量 | 用途 | 必需 |
|---------|------|------|
| `WECHAT_API_KEY` | 微绿流量宝 API（默认） | 品牌未配置 api_key 时必需 |
| `DOUBAO_API_KEY` | 豆包图片生成 | AI 生成配图/封面时必需 |
| `IMGBB_API_KEY` | IMGBB 图床（本地图片上传） | 使用本地图片配图时必需 |

检测方式：
```bash
echo "WECHAT_API_KEY: $([ -n "$WECHAT_API_KEY" ] && echo '已设置' || echo '未设置')"
echo "DOUBAO_API_KEY: $([ -n "$DOUBAO_API_KEY" ] && echo '已设置' || echo '未设置')"
echo "IMGBB_API_KEY: $([ -n "$IMGBB_API_KEY" ] && echo '已设置' || echo '未设置')"
```

**注意**：品牌 YAML 中可配置 `wechat_api_key` 字段覆盖默认环境变量，实现多账号独立管理。

## Step 0: 品牌选择与确认

### 品牌���置

品牌信息存储在 `references/brands/` 目录下，每个品牌一个 YAML 文件。

读取 `references/brands/` 目录查看已配置品牌。若用户未指定品牌，列出可用品牌供选择。若品牌不存在，按 `references/brand-template.md` 中的模板引导用户创建新配置。

### 默认发布账号

- 公众号：手工暖食小馆
- AppID：`wx4f066f9ca4f1d47a`

用户可在品牌配置中指定其他公众号。

## Step 1: 热点搜索与素材采集

根据品牌配置中的关键词和行业信息，搜集素材：

### 搜索策略

1. **产品相关热点**：`WebSearch` 搜索 "[品牌名] [产品名] [当前日期] 最新"
2. **行业趋势**：`WebSearch` 搜索 "[行业] 趋势 热点 [当前月份]"
3. **竞品动态**：`WebSearch` 搜索品牌配置中的竞品关键词
4. **用户口碑**：`WebSearch` 搜索 "[产品名] 评测 体验 口碑"
5. **场景灵感**：`WebSearch` 搜索 "[产品类别] 使用场景 生活方式"

### 素材筛选原则

- 优先选择 **24小时内** 的新鲜素材
- 排除明显的竞品广告内容
- 保留有数据支撑的行业观点
- 收集 3-5 条用户真实评价或使用场景

## Step 2: 内容生成

### 内容风格选择

支持两种风格，详见 `references/content-styles.md`：

| 风格 | 适用场景 | 字数 |
|------|---------|------|
| **产品软文** | 品牌故事、场景植入、情感共鸣 | 1500-2000字 |
| **种草测评** | 产品体验、横评对比、购买建议 | 1500-2000字 |

用户未指定时，默认使用 **产品软文** 风格。

### 文章生成规范

1. **标题**：吸引力强，15-25字，含产品/品牌关键词
2. **开头**：场景导入或痛点共鸣（100-200字）
3. **正文**：自然植入产品卖点，结合搜集的热点素材
4. **结尾**：引导行动（关注、购买、体验），不硬推
5. **品牌调性**：严格遵循品牌配置中的 `tone`（语气）和 `taboo`（禁忌词）

### Markdown 输出格式

```markdown
---
title: 文章标题
date: YYYY-MM-DD
brand: 品牌名称
style: soft_article|review
tags: [产品营销, 品牌名, 相关标签]
---

文章正文...

<!-- IMG_PLACEHOLDER: {
  主体: "[产品或场景]",
  动作/状态: "[使用状态]",
  场景/环境: "[环境描述]",
  风格: "生活方式摄影，温暖色调"
} -->
```

在文章的 2-3 个关键位置插入 `IMG_PLACEHOLDER` 占位符。

## Step 3: 封面图与配图生成

使用 `scripts/generate_image.py` 生成图片。支持三级配图来源：

| 优先级 | 来源 | 说明 | 需要 |
|--------|------|------|------|
| 1 | **缓存 URL**（最快） | 从 `references/image_url_mapping.json` 查找已上传的 IMGBB URL | 已运行过批量上传 |
| 2 | **本地图片库** | 从本地实拍照片匹配，上传到 IMGBB 图床 | `IMGBB_API_KEY` |
| 3 | **AI 生成** | 豆包 SeeDream API 生成 | `DOUBAO_API_KEY` |

配图自动按优先级匹配：缓存 URL → 本地扫描上传 → AI 生成。

### 批量上传本地图片（预缓存）

将整个产品图片库批量上传到 IMGBB，生成 URL 映射文件：

```bash
python3 scripts/batch_upload.py [图片库路径]
```

支持断点续传（Ctrl+C 后再次运行自动跳过已上传图片），进度保存到 `references/image_url_mapping.json`。

### 文章配图（本地图片优先）

```bash
python3 scripts/generate_image.py article \
  --file "文章路径.md" \
  --max-images 3 \
  --local-library "/path/to/product-images"
```

仅使用本地图片（不回退 AI）：

```bash
python3 scripts/generate_image.py article \
  --file "文章路径.md" \
  --use-local-only
```

省略 `--local-library` 时使用脚本内置的默认图片库路径。

### 封面图（AI 生成）

```bash
python3 scripts/generate_image.py cover \
  --title "文章标题" \
  --style "warm" \
  --size 2048x2048
```

风格选项：`modern`（现代）、`minimalist`（极简）、`tech`（科技）、`warm`（温暖）、`creative`（创意）

产品营销推荐使用 `warm` 或 `creative`。

### 本地图片库索引

查看本地图片库中已有产品及图片数量：

```bash
python3 scripts/generate_image.py index
```

**重要**：豆包 API 最低要求 3,686,400 像素（约 1920x1920），AI 生成图片尺寸统一使用 `2048x2048`。

自动识别 `IMG_PLACEHOLDER` 占位符并替换为实际图片。

## Step 4: 保存到 Obsidian（可选）

用户要求保存时，保存路径：`~/Documents/Obsidian/产品营销/[品牌名]/YYYY-MM-DD-标题.md`

确保目录存在后写入文件。默认不保存到本地。

## Step 5: 发布到微信公众号（可选）

用户要求发布时执行。使用 `scripts/publish.py`：

```bash
python3 scripts/publish.py publish \
  --appid "wx4f066f9ca4f1d47a" \
  --title "文章标题" \
  --content-file "文章路径.md" \
  --summary "60字以内摘要" \
  --cover "封面图URL" \
  --author "手工暖食小馆" \
  --api-key "品牌配置中的wechat_api_key"
```

**API Key 优先级**：`--api-key` 参数 > `WECHAT_API_KEY` 环境变量。发布时从品牌 YAML 的 `wechat_api_key` 字段读取并传入。

发布前向用户确认：
1. 文章标题
2. 目标公众号
3. 封面图是否满意

## 品牌管理

### 添加新品牌

在 `references/brands/` 下创建 YAML 文件，格式见 `references/brand-template.md`。

### 查看已有品牌

读取 `references/brands/` 目录列出所有 `.yaml` 文件。

### 品牌配置字段说明

见 `references/brand-template.md` 中的详细字段说明。
