# 品牌配置模板

在 `references/brands/` 目录下创建 `品牌名.yaml` 文件，按以下格式填写：

## 模板

```yaml
# 品牌基础信息
name: "品牌中文名"
name_en: "Brand English Name"
industry: "所属行业（如：食品饮料、美妆护肤、数码科技、家居生活）"
slogan: "品牌口号"

# 产品信息
products:
  - name: "产品名称"
    category: "产品类别"
    price: "价格区间"
    selling_points:
      - "核心卖点1"
      - "核心卖点2"
      - "核心卖点3"
    target_audience: "目标人群"
    usage_scenarios:
      - "使用场景1"
      - "使用场景2"

# 品牌调性
tone: "温暖亲切|专业权威|年轻活力|高端大气|文艺清新"
keywords:
  - "搜索关键词1"
  - "搜索关键词2"
competitors:
  - "竞品名称1"
  - "竞品名称2"

# 内容规范
taboo:
  - "禁忌词1（如竞品贬低语）"
  - "禁忌词2"
preferred_topics:
  - "偏好话题1"
  - "偏好话题2"

# 发布配置（可选，覆盖默认值）
wechat_appid: "wxxxxxxxxxxx"
wechat_author: "公众号显示作者名"

# 图片风格偏好
image_style: "warm"  # modern|minimalist|tech|warm|creative
```

## 示例：食品品牌

```yaml
name: "山野小厨"
name_en: "Mountain Kitchen"
industry: "食品饮料"
slogan: "每一口都是山野的味道"

products:
  - name: "手工辣椒酱"
    category: "调味品"
    price: "39-69元"
    selling_points:
      - "纯手工石臼研磨"
      - "贵州高山辣椒原料"
      - "零添加无防腐剂"
    target_audience: "25-45岁注重健康饮食的都市人群"
    usage_scenarios:
      - "日常佐餐提味"
      - "拌面拌饭神器"
      - "送礼伴手礼"

tone: "温暖亲切"
keywords:
  - "手工辣椒酱"
  - "贵州辣椒"
  - "零添加调味品"
competitors:
  - "老干妈"
  - "虎邦辣酱"

taboo:
  - "最好的"
  - "第一"
  - "绝对"
preferred_topics:
  - "手工匠心"
  - "产地溯源"
  - "健康饮食"

wechat_appid: "wx4f066f9ca4f1d47a"
wechat_author: "手工暖食小馆"
image_style: "warm"
```
