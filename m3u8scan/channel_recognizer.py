#!/usr/bin/env python3
"""
频道识别模块（供 m3u8scan.py 调用）
整合 YOLO 检测 + ROI OCR + 整图 OCR + 关键词匹配 + YOLO类别映射
三种识别路径，按置信度高低合并结果：
  1. YOLO 类别名映射（直接由 best.pt 的 class name 查表得到频道名）
  2. YOLO 框内 ROI OCR + 关键词匹配
  3. 整图 OCR + 关键词匹配

三种路径各自独立产生结果，最终按置信度合并：
  - 只有一个路径有结果 → 采用该结果
  - 多个路径都有结果 → 选置信度最高的
  - 输出时显示三条路径（A/B/C）的详细结果、置信度和合并决策过程
"""

import cv2
import numpy as np
from pathlib import Path
from paddleocr import PaddleOCR
from ultralytics import YOLO

# ==================== 配置 ====================
YOLO_MODEL_PATH = "best.pt"
CONF_THRESHOLD = 0.25
OCR_CONF_THRESHOLD = 0.5
USE_GPU = False
FULL_IMG_MAX_SIZE = 1280
DEBUG_OCR = False
CONF_TIE_EPS = 0.001
FOUR_K_UPGRADE_EPS = 0.02

# ==================== YOLO 类别名 → 标准频道名 映射表 ====================
# 基于 tvlogo_dataset_yolo-3/data.yaml 的 106 个类别
YOLO_CLASS_TO_CHANNEL = {
    # === CCTV ===
    "CCTV1": "CCTV1",
    "CCTV2": "CCTV2",
    "CCTV3": "CCTV3",
    "CCTV4": "CCTV4",
    "CCTV4K": "CCTV4K",
    "CCTV4meizhou": "CCTV4美洲",
    "CCTV4ouzhou": "CCTV4欧洲",
    "CCTV5": "CCTV5",
    "CCTV5_": "CCTV5+",
    "CCTV6": "CCTV6",
    "CCTV7": "CCTV7",
    "CCTV8": "CCTV8",
    "CCTV9": "CCTV9",
    "CCTV10": "CCTV10",
    "CCTV11": "CCTV11",
    "CCTV12": "CCTV12",
    "CCTV13": "CCTV13",
    "CCTV14": "CCTV14",
    "CCTV15": "CCTV15",
    "CCTV16": "CCTV16",
    "CCTV16-4K": "CCTV16-4K",
    "CCTV17": "CCTV17",
    # === CCTV 付费频道 ===
    "CCTVbingqikeji": "CCTV兵器科技",
    "CCTVdianshizhinan": "CCTV电视指南",
    "CCTVdiyijuchang": "CCTV第一剧场",
    "CCTVfengyunjuchang": "CCTV风云剧场",
    "CCTVfengyunyinyue": "CCTV风云音乐",
    "CCTVfengyunzuqiu": "CCTV风云足球",
    "CCTVgaoerfuwangqiu": "CCTV高尔夫网球",
    "CCTVhuaijiujuchang": "CCTV怀旧剧场",
    "CCTVnvxingshishang": "CCTV女性时尚",
    "CCTVshijiedili": "CCTV世界地理",
    "CCTVweishengjiankang": "CCTV卫生健康",
    "CCTVyangshitaiqiu": "CCTV央视台球",
    "CCTVyangshiwenhuajingpin": "CCTV央视文化精品",
    # === CETV ===
    "CETV1": "CETV1",
    "CETV2": "CETV2",
    "CETV3": "CETV3",
    "CETV4": "CETV4",
    "CETVzaoqijiaoyu": "CETV早期教育",
    # === CGTN ===
    "CGTN": "CGTN",
    "CGTNayu": "CGTN阿语",
    "CGTNeyu": "CGTN俄语",
    "CGTNfayu": "CGTN法语",
    "CGTNjilu": "CGTN纪录",
    "CGTNxiyu": "CGTN西语",
    # === 卫视 ===
    "anhuiweishi": "安徽卫视",
    "beijingweishi": "北京卫视",
    "beijingweishi4K": "北京卫视4K",
    "chongqingweishi": "重庆卫视",
    "dongfangweishi": "东方卫视",
    "dongfangweishi4K": "东方卫视4K",
    "dongnanweishi": "东南卫视",
    "gansuweishi": "甘肃卫视",
    "guangdongweishi": "广东卫视",
    "guangdongweishi4K": "广东卫视4K",
    "guangxiweishi": "广西卫视",
    "guizhouweishi": "贵州卫视",
    "hainanweishi": "海南卫视",
    "hebeiweishi": "河北卫视",
    "heilongjiangweishi": "黑龙江卫视",
    "henanweishi": "河南卫视",
    "hubeiweishi": "湖北卫视",
    "hunanweishi": "湖南卫视",
    "hunanweishi4K": "湖南卫视4K",
    "jiangsuweishi": "江苏卫视",
    "jiangsuweishi4K": "江苏卫视4K",
    "jiangxiweishi": "江西卫视",
    "jilinweishi": "吉林卫视",
    "liaoningweishi": "辽宁卫视",
    "neimengguweishi": "内蒙古卫视",
    "ningxiaweishi": "宁夏卫视",
    "qinghaiweishi": "青海卫视",
    "shaanxiweishi": "陕西卫视",
    "shandongweishi": "山东卫视",
    "shandongweishi4K": "山东卫视4K",
    "shanxiweishi": "山西卫视",
    "shenzhenweishi": "深圳卫视",
    "shenzhenweishi4K": "深圳卫视4K",
    "sichuanweishi": "四川卫视",
    "sichuanweishi4K": "四川卫视4K",
    "tianjinweishi": "天津卫视",
    "xinjiangweishi": "新疆卫视",
    "xizangweishi": "西藏卫视",
    "yunnanweishi": "云南卫视",
    "zhejiangweishi": "浙江卫视",
    "zhejiangweishi4K": "浙江卫视4K",
    # === 纪实 / 教育 / 少儿 ===
    "beijingjishi": "北京纪实",
    "shandongjiaoyu": "山东教育",
    "jinyingkatong": "金鹰卡通",
    "kakushaoer": "卡酷少儿",
    "youmankatong": "优漫卡通",
    # === 中央新影 ===
    "zhongyangxinyingfaxianzhilv": "中央新影发现之旅",
    "zhongyangxinyinglaogushi": "中央新影老故事",
    "zhongyangxinyingzhongxuesheng": "中央新影中学生",
    # === 其他频道 ===
    "aiqingxiju": "爱情喜剧",
    "dabodianjing": "哒啵电竞",
    "dabosaishi": "哒啵赛事",
    "dongzuodianying": "动作电影",
    "fengyanjuchang": "烽烟剧场",
    "heimeidianying": "黑莓电影",
    "jiatingjuchang": "家庭剧场",
    "jingcaiqingshao": "睛彩青少",
    "junlvjuchang": "军旅剧场",
    "nongyezhifu": "农业致富",
    "xuanwuweilai": "炫舞未来",
}

# ==================== OCR 关键词映射表 ====================
CHANNEL_KEYWORDS = {
    "cctv": "CCTV",
    "cctv1": "CCTV1", "cctv1综合": "CCTV1", "cctv综合": "CCTV1",
    "cctv2": "CCTV2", "cctv财经": "CCTV2", "cctv2财经": "CCTV2",
    "cctv3": "CCTV3", "cctv综艺": "CCTV3", "cctv3综艺": "CCTV3",
    "cctv4": "CCTV4", "cctv中文国际": "CCTV4", "cctv4中文国际": "CCTV4",
    "cctv5": "CCTV5", "cctv体育": "CCTV5", "cctv5体育": "CCTV5",
    "cctv5+": "CCTV5+", "cctv体育赛事": "CCTV5+", "cctv5体育赛事": "CCTV5+",  "cctv5+体育赛事": "CCTV5+", "体育赛事": "CCTV5+",
    "cctv6": "CCTV6", "cctv电影": "CCTV6", "cctv6电影": "CCTV6",
    "cctv7": "CCTV7", "cctv国防军事": "CCTV7", "cctv7国防军事": "CCTV7", "cctv7国防": "CCTV7",
    "cctv8": "CCTV8", "cctv电视剧": "CCTV8", "cctv8电视剧": "CCTV8",
    "cctv9": "CCTV9", "cctv纪录": "CCTV9", "cctv9纪录": "CCTV9",
    "cctv10": "CCTV10", "cctv科教": "CCTV10", "cctv10科教": "CCTV10",
    "cctv11": "CCTV11", "cctv戏曲": "CCTV11", "cctv11戏曲": "CCTV11",
    "cctv12": "CCTV12", "cctv社会与法":"CCTV12", "cctv12社会与法":"CCTV12", 
    "cctv13":"CCTV13", "cctv新闻":"CCTV13", "cctv13新闻":"CCTV13",
    "cctv14": "CCTV14", "cctv少儿": "CCTV14", "cctv14少儿": "CCTV14",
    "cctv15": "CCTV15", "cctv音乐": "CCTV15", "cctv15音乐": "CCTV15",
    "cctv16": "CCTV16", "cctv奥林匹克": "CCTV16", "cctv16奥林匹克": "CCTV16", "cctv16奥林匹克4k": "CCTV16-4K", "4kcctv16": "CCTV16-4K",
    "cctv17": "CCTV17", "cctv农业农村": "CCTV17", "cctv17农业农村": "CCTV17",
    "风云足球": "CCTV风云足球", "风云音乐": "CCTV风云音乐", "第一剧场": "CCTV第一剧场",
    "风云剧场": "CCTV风云剧场", "怀旧剧场": "CCTV怀旧剧场", "世界地理": "CCTV世界地理",
    "女性时尚": "CCTV女性时尚", "央视文化精品": "CCTV央视文化精品",
    "央视台球": "CCTV央视台球", "高尔夫网球": "CCTV高尔夫网球", "高尔夫·网球": "CCTV高尔夫网球",
    "兵器科技": "CCTV兵器科技", "卫生健康": "CCTV卫生健康", "电视指南": "CCTV电视指南",
    "cetv1": "CETV1", "cetv": "CETV", "cetv2": "CETV2", "空中课堂": "CETV2",
    "cetv3": "CETV3", "cetv4": "CETV4", "智慧教育": "CETV4",
    "cetv早教": "CETV早教", "早期教育": "CETV早教",
    "cgtn": "CGTN", "cgtn英语": "CGTN", "cgtn新闻": "CGTN",
    "cgtnesp": "CGTN西语", "cgtnfran": "CGTN法语", "cgtna": "CGTN阿语",
    "cgtnpycc": "CGTN俄语", "cgtndocumentary": "CGTN纪录", "documentary": "CGTN纪录",
    "中学生": "中央新影中学生", "老故事": "中央新影老故事",
    "发现之旅": "中央新影发现之旅",
    # 卫视频道
    "安徽卫视": "安徽卫视", 
    "北京卫视": "北京卫视", "北京卫视4k": "北京卫视4K", "brtv北京卫视": "北京卫视", "brtv超高清": "北京卫视4K", "4kbrtv": "北京卫视4K",
    "东方卫视": "东方卫视", "东方卫视4k": "东方卫视4K", 
    "湖南卫视": "湖南卫视", "湖南卫视4k": "湖南卫视4K", 
    "江苏卫视": "江苏卫视", "江苏卫视4k": "江苏卫视4K", "江苏卫视超高清": "江苏卫视4K", 
    "浙江卫视4k": "浙江卫视4K", "浙江卫视4k超高清": "浙江卫视4K", "浙江卫视超高清": "浙江卫视4K", "浙江卫视": "浙江卫视", 
    "山东卫视": "山东卫视", "山东卫视4k": "山东卫视4K", "山东卫视4k超高清": "山东卫视4K", "山东卫视超高清": "山东卫视4K", 
    "广东卫视": "广东卫视", "广东卫视4k": "广东卫视4K", "广东卫视超高清": "广东卫视4K", 
    "四川卫视": "四川卫视", "四川卫视4k": "四川卫视4K", "四川卫视14k": "四川卫视4K",  "四川卫视|": "四川卫视4K", "四川卫视超高清": "四川卫视4K",
    "深圳卫视": "深圳卫视", "深圳卫视4k": "深圳卫视4K", "4k深圳卫视": "深圳卫视4K", "深圳卫视超高清": "深圳卫视4K",
    "天津卫视": "天津卫视", "河北卫视": "河北卫视", "山西卫视": "山西卫视",
    "辽宁卫视": "辽宁卫视", "吉林卫视": "吉林卫视", "黑龙江卫视": "黑龙江卫视",
    "内蒙古卫视": "内蒙古卫视", "陕西卫视": "陕西卫视", "甘肃卫视": "甘肃卫视",
    "青海卫视": "青海卫视", "宁夏卫视": "宁夏卫视", "新疆卫视": "新疆卫视",
    "西藏卫视": "西藏卫视", "云南卫视": "云南卫视", "贵州卫视": "贵州卫视",
    "广西卫视": "广西卫视", "海南卫视": "海南卫视", "重庆卫视": "重庆卫视",
    "河南卫视": "河南卫视", "湖北卫视": "湖北卫视", "江西卫视": "江西卫视",
    "东南卫视": "东南卫视",
    "金鹰卡通": "金鹰卡通", "KAKU": "卡酷少儿",
    "纪实": "纪实", "教育台": "教育台",
    "爱情喜剧": "爱情喜剧",
    "动作电影": "动作电影",
    "军旅剧场": "军旅剧场",
    "家庭剧场": "家庭剧场",
    "烽烟剧场": "烽烟剧场",
    "农业致富": "农业致富",
    "黑莓电影": "黑莓电影",
    "炫舞未来": "炫舞未来",
    "哒啵赛事": "哒啵赛事",
    "哒啵电竞": "哒啵电竞",
    "睛彩青少": "睛彩青少",
    "BRTV纪实科教": "北京纪实科教",
    "山东教育": "山东教育",
    "中文国际欧洲": "CCTV4欧洲",
    "中文国际美洲": "CCTV4美洲",
}

# =============================================

# 全局模型（延迟加载）
_yolo_model = None
_ocr = None


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        print("[channel_recognizer] 加载 YOLO 模型...")
        _yolo_model = YOLO(YOLO_MODEL_PATH)
    return _yolo_model


def _get_ocr():
    global _ocr
    if _ocr is None:
        print("[channel_recognizer] 加载 PaddleOCR...")
        _ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False, use_gpu=USE_GPU)
    return _ocr


def _preprocess_for_full_ocr(image, max_size=FULL_IMG_MAX_SIZE):
    """整图 OCR 预处理：缩放 + CLAHE"""
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim > max_size:
        ratio = max_size / max_dim
        new_w, new_h = int(w * ratio), int(h * ratio)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def _parse_ocr_result(ocr_result):
    """解析 PaddleOCR 返回，提取包含文本与位置的条目列表"""
    texts = []
    if not ocr_result or not isinstance(ocr_result, list) or len(ocr_result) == 0:
        return texts
    ocr_data = ocr_result[0] if isinstance(ocr_result[0], list) else ocr_result
    for item in ocr_data:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            bbox, text_conf = item
            if isinstance(text_conf, (list, tuple)) and len(text_conf) == 2:
                text, conf = text_conf
            else:
                continue
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = 0.0
            if conf >= OCR_CONF_THRESHOLD and text and isinstance(text, str):
                clean = text.strip().replace(" ", "").lower()
                texts.append({"text": clean, "conf": conf, "bbox": bbox})
    return texts


def _merge_text_by_line(items, y_tol_ratio=0.4):
    """按行合并 OCR 片段，提升长关键词命中率"""
    if not items:
        return []

    def _bbox_stats(bbox):
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        return x_min, x_max, y_min, y_max, (y_min + y_max) / 2.0, (y_max - y_min)

    entries = []
    for item in items:
        if not item.get("bbox"):
            continue
        x_min, x_max, y_min, y_max, y_center, height = _bbox_stats(item["bbox"])
        entries.append({
            "text": item["text"],
            "conf": item["conf"],
            "x_min": x_min,
            "x_max": x_max,
            "y_center": y_center,
            "height": height,
        })

    entries.sort(key=lambda x: (x["y_center"], x["x_min"]))
    groups = []
    for entry in entries:
        placed = False
        for group in groups:
            tol = max(group["avg_height"], entry["height"]) * y_tol_ratio
            if abs(entry["y_center"] - group["y_center"]) <= tol:
                group["items"].append(entry)
                group["y_center"] = sum(i["y_center"] for i in group["items"]) / len(group["items"])
                group["avg_height"] = sum(i["height"] for i in group["items"]) / len(group["items"])
                placed = True
                break
        if not placed:
            groups.append({
                "y_center": entry["y_center"],
                "avg_height": entry["height"],
                "items": [entry],
            })

    merged = []
    for group in groups:
        group["items"].sort(key=lambda x: x["x_min"])
        merged_text = "".join(i["text"] for i in group["items"])
        merged_conf = sum(i["conf"] for i in group["items"]) / len(group["items"])
        if merged_text:
            merged.append((merged_text, merged_conf))
    return merged


def _match_keyword(texts):
    """OCR 关键词匹配"""
    best_channel = None
    best_conf = 0.0
    best_kw_len = 0
    best_is_4k = False
    sorted_kw = sorted(
        (
            (k.replace(" ", "").lower(), v)
            for k, v in CHANNEL_KEYWORDS.items()
        ),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    for text, conf in texts:
        if not text:
            continue
        for keyword, channel in sorted_kw:
            if keyword and keyword in text:
                kw_len = len(keyword)
                is_4k = "4k" in keyword or "超高清" in keyword
                if DEBUG_OCR:
                    print(
                        f"[OCR_MATCH] text='{text}' keyword='{keyword}' "
                        f"channel='{channel}' conf={conf:.3f}"
                    )
                if conf > best_conf + CONF_TIE_EPS:
                    best_conf = conf
                    best_kw_len = kw_len
                    best_channel = channel
                    best_is_4k = is_4k
                elif abs(conf - best_conf) <= CONF_TIE_EPS:
                    if (is_4k and not best_is_4k) or kw_len > best_kw_len:
                        best_conf = conf
                        best_kw_len = kw_len
                        best_channel = channel
                        best_is_4k = is_4k
                elif (not best_is_4k) and is_4k and (best_conf - conf) <= FOUR_K_UPGRADE_EPS:
                    best_conf = conf
                    best_kw_len = kw_len
                    best_channel = channel
                    best_is_4k = is_4k
                break
    if DEBUG_OCR:
        print(
            f"[OCR_MATCH] chosen='{best_channel}' conf={best_conf:.3f} "
            f"kw_len={best_kw_len} is_4k={best_is_4k}"
        )
    return best_channel, best_conf


def _roi_ocr(roi):
    """ROI OCR：对 YOLO 裁剪区域做 OCR + 关键词匹配"""
    if roi.size == 0:
        return None, 0.0
    h, w = roi.shape[:2]
    if w < 100 or h < 50:
        roi = cv2.resize(roi, (w * 2, h * 2), interpolation=cv2.INTER_LINEAR)
    ocr = _get_ocr()
    result = ocr.ocr(roi, cls=True)
    if DEBUG_OCR:
        print("[ROI_OCR] raw:", result)
    items = _parse_ocr_result(result)
    if DEBUG_OCR:
        print("[ROI_OCR] items:", items)
    texts = [(item["text"], item["conf"]) for item in items]
    merged_texts = _merge_text_by_line(items)
    if DEBUG_OCR:
        print("[ROI_OCR] merged:", merged_texts)
    return _match_keyword(texts + merged_texts)


def _full_image_ocr(image):
    """整图 OCR：缩放 + CLAHE + 关键词匹配"""
    proc = _preprocess_for_full_ocr(image)
    ocr = _get_ocr()
    result = ocr.ocr(proc, cls=True)
    if DEBUG_OCR:
        print("[FULL_OCR] raw:", result)
    items = _parse_ocr_result(result)
    if DEBUG_OCR:
        print("[FULL_OCR] items:", items)
    texts = [(item["text"], item["conf"]) for item in items]
    merged_texts = _merge_text_by_line(items)
    if DEBUG_OCR:
        print("[FULL_OCR] merged:", merged_texts)
    return _match_keyword(texts + merged_texts)


def recognize_channel(image_path):
    """
    识别单张截图的频道名称。
    返回：频道名称字符串，识别失败返回 None。
    
    三条识别路径：
      路径A: YOLO 类别名 → YOLO_CLASS_TO_CHANNEL 映射
      路径B: YOLO 框内 ROI OCR + 关键词匹配
      路径C: 整图 OCR + 关键词匹配
    
    合并策略：
      1. 只有一个路径有结果 → 直接使用
      2. 多个路径都有结果 → 选置信度最高的
      3. 都没有结果 → None
    输出时显示三条路径(A/B/C)的详细结果、置信度和合并决策过程
    """
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[channel_recognizer] 无法读取图片: {image_path}")
        return None

    yolo = _get_yolo()
    results = yolo(img, conf=CONF_THRESHOLD)
    boxes = results[0].boxes

    # --- 收集三种路径的结果 ---
    yolo_channel = None       # 路径A：YOLO 类别映射
    yolo_conf = 0.0
    roi_channel = None        # 路径B：ROI OCR
    roi_conf = 0.0
    full_channel = None       # 路径C：整图 OCR
    full_conf = 0.0

    if boxes is not None and len(boxes) > 0:
        best_yolo_box_conf = 0.0
        best_roi_result = (None, 0.0)

        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = yolo.names.get(cls_id, "unknown")

            # 路径A：取置信度最高的 YOLO 类别
            if conf > best_yolo_box_conf:
                best_yolo_box_conf = conf
                mapped = YOLO_CLASS_TO_CHANNEL.get(cls_name)
                if mapped and mapped != "未知频道":
                    yolo_channel = mapped
                    yolo_conf = conf

            # 路径B：每个框做 ROI OCR，取最佳
            roi = img[y1:y2, x1:x2]
            ch, rc = _roi_ocr(roi)
            if ch and rc > best_roi_result[1]:
                best_roi_result = (ch, rc)

        roi_channel, roi_conf = best_roi_result

        # 路径C：无论 ROI OCR 是否有结果，都执行整图 OCR
        full_channel, full_conf = _full_image_ocr(img)
    else:
        # 无 YOLO 框 → 直接整图 OCR
        full_channel, full_conf = _full_image_ocr(img)

    # --- 打印三条路径的详细结果 ---
    print(f"\n{'='*50}")
    print(f"📷 频道识别 - 三条路径结果:")
    print(f"  路径A (YOLO类别): {yolo_channel}  置信度: {yolo_conf:.3f}")
    print(f"  路径B (ROI OCR):  {roi_channel}  置信度: {roi_conf:.3f}")
    print(f"  路径C (整图 OCR):  {full_channel}  置信度: {full_conf:.3f}")

    # --- 收集有效结果 ---
    results_list = [
        ("YOLO类别", yolo_channel, yolo_conf),
        ("ROI_OCR", roi_channel, roi_conf),
        ("整图OCR", full_channel, full_conf),
    ]

    valid_results = [(method, ch, c) for method, ch, c in results_list if ch]

    if not valid_results:
        print(f"  ❌ 三条路径均无结果")
        print(f"{'='*50}\n")
        return None

    # 按置信度从高到低排序，选择最高的
    valid_results.sort(key=lambda x: x[2], reverse=True)
    
    print(f"\n  📊 有效路径数: {len(valid_results)}")
    for method, ch, c in valid_results:
        print(f"     - {method}: '{ch}' (置信度: {c:.3f})")

    # 取置信度最高的（若差距极小，优先更完整/4K版本）
    best_method, best_channel, best_conf = valid_results[0]
    max_conf = valid_results[0][2]
    close_candidates = [r for r in valid_results if max_conf - r[2] <= 0.001]
    if len(close_candidates) > 1:
        def _tie_score(item):
            _, channel, conf = item
            text = channel.lower()
            is_4k = "4k" in text or "超高清" in channel
            return (is_4k, len(channel), conf)

        close_candidates.sort(key=_tie_score, reverse=True)
        best_method, best_channel, best_conf = close_candidates[0]
    
    # 如果有多个结果，显示合并过程
    if len(valid_results) > 1:
        # 检查同频道多路径命中
        same_channel = all(ch == best_channel for _, ch, _ in valid_results)
        if same_channel:
            print(f"  ✅ 所有路径一致: {best_channel}")
        else:
            # 显示备选结果
            alternatives = [r for r in valid_results if r[1] != best_channel or r[0] != best_method]
            print(f"  ⚡ 选择最优结果: '{best_channel}' ({best_method}, {best_conf:.3f})")
            alt_str = ", ".join(f"'{ch}'({m} {c:.3f})" for m, ch, c in alternatives)
            print(f"  📋 备选结果: {alt_str}")

    print(f"  🎯 最终频道: {best_channel} (方法: {best_method}, 置信度: {best_conf:.3f})")
    print(f"{'='*50}\n")
    return best_channel


# ==================== 测试入口 ====================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 channel_recognizer.py <截图路径>")
        sys.exit(1)
    result = recognize_channel(sys.argv[1])
    print(f"\n最终频道: {result}")
