# 自动扫描 m3u8 频道并通过台标识别频道名工具

本工具集用于从 m3u8 地址列表中自动扫描可播放的流媒体地址，并通过电视台标识别模型自动确定频道名称。支持多线程扫描、分辨率探测、台标识别（YOLO + OCR 混合）等功能。

---

## 一、文件结构

```
m3u8scan/
├── m3u8scan.py                 # 主程序：扫描 m3u8 URL，输出可用的流地址
├── channel_recognizer.py       # 核心识别模块：YOLO + 区域 OCR + 全图 OCR 三路对比识别台标
├── tv_channel_hybrid.py        # 混合识别脚本（YOLO + OCR，带命令行接口）
├── yolo_ocr_recognizer.py      # 早期实验版混合识别（参考用）
├── hybrid_recognizer.py        # 实验：YOLO 定位 + 透明台标特征匹配（ORB）
├── oldscan.py                  # 旧版主程序实验代码
├── test_scan.py                # 主程序实验代码
├── testocr.py                  # 单图识别测试（YOLO + 整图 OCR）
├── auto_label.py               # 自动标注脚本
├── fix_all_labels.py           # 修正标注文件
├── generate_preview.py         # 生成标注预览图
├── convert_to_yolo_structure.py# 转换为 YOLO 标准数据集
├── merge_tvlogo_dataset.py     # 合并多频道 classes.txt
└── build_tvlogo_dataset.py     # 批量截图脚本
```

---

## 二、环境依赖

### 2.1 系统要求
- Ubuntu 22.04 / 24.04（推荐）或 Windows WSL2 / macOS
- Python 3.9 及以上
- 建议使用 NVIDIA GPU（用于训练，扫描识别仅需 CPU）

### 2.2 安装依赖库
```bash
pip install opencv-python ultralytics paddleocr paddlepaddle requests
```

### 2.3 模型文件准备
- 训练好的台标检测模型：`runs/detect/exp_fast/weights/best.pt`（请自行训练或使用提供的模型）更多关于训练模型的内容参考`YOLO_Training_Guide.md`
- 将模型文件放在项目根目录下，并在 `channel_recognizer.py` 中配置 `YOLO_MODEL_PATH`。

---

## 三、主程序：m3u8scan.py

### 3.1 功能
- 解析 URL 模板中的数值区间（例如 `(1-100)`），生成待扫描的 m3u8 地址列表。
- 多线程探测每个地址是否可访问，并可选择探测分辨率与帧率、截图并进行台标识别。
- 将可用的流地址及识别到的频道信息输出到文件，支持纯文本（.txt）和 M3U 播放列表（.m3u/.m3u8）两种格式。

### 3.2 命令行参数
```
usage: m3u8scan.py [-h] [--step STEP] [--threads THREADS] [--output OUTPUT] [--no-probe] [url_pattern]

positional arguments:
  url_pattern         URL模板，支持区间格式：(1-100)
                      默认 http://example.com/hls/(1-100)/index.m3u8

options:
  -h, --help          显示帮助
  --step STEP         区间步长，默认1
  --threads THREADS   最大线程数，默认20
  --output OUTPUT     输出文件名，可支持.m3u/.m3u8格式，根据扩展名决定输出格式，默认playlist.txt （txt格式）
  --no-probe          仅检测URL可访问，跳过分辨率/帧率探测、截图、频道识别，默认False
```

### 3.3 输出格式

#### 当输出文件扩展名为 `.txt` 时（默认）
每行格式为：
```
频道名[分辨率_帧率],URL
```
示例：
```
CCTV1[1920x1080_50FPS],http://example.com/hls/1/index.m3u8
CCTV2[1920x1080_50FPS],http://example.com/hls/2/index.m3u8
```

#### 当输出文件扩展名为 `.m3u` 或 `.m3u8` 时
生成标准的 M3U 播放列表文件，支持在 Kodi、VLC、TVHeadend 等播放器中直接使用。
```
#EXTM3U
#EXTINF:-1 tvg-name="CCTV1" tvg-logo="https://gcore.jsdelivr.net/gh/taksssss/tv/icon/CCTV1.png",CCTV1[1920x1080_50FPS]
http://example.com/hls/1/index.m3u8
#EXTINF:-1 tvg-name="CCTV2" tvg-logo="https://gcore.jsdelivr.net/gh/taksssss/tv/icon/CCTV2.png",CCTV2[1920x1080_50FPS]
http://example.com/hls/2/index.m3u8
```
- `tvg-name`：频道名称
- `tvg-logo`：可选的频道图标 URL（由程序根据频道名自动生成）
- 备注字段显示分辨率与帧率信息

### 3.4 使用示例
```bash
# 扫描默认 URL 模板，输出 text 格式（默认）
python3 m3u8scan.py

# 自定义模板，步长2，10个线程，输出 M3U 播放列表
python3 m3u8scan.py "http://example.com/hls/(1-50)/index.m3u8" --step 2 --threads 10 --output live.m3u8

# 仅检测连通性，不探测分辨率、不截图、不识别频道（快速扫描）
python3 m3u8scan.py --no-probe
```

### 3.5 工作流程详解
1. 根据 URL 模板生成所有候选地址。
2. 多线程探测每个地址是否可访问（HTTP HEAD 或 GET）。
3. 对于可访问的地址（`--no-probe` 未启用时）：
   - 使用 FFmpeg/ffprobe 探测分辨率与帧率。
   - 截取一帧图像。
   - 调用 `channel_recognizer.py` 中的台标识别模块获取频道名称。
4. 根据输出文件扩展名，生成对应格式的结果文件。

---

## 四、核心识别模块：channel_recognizer.py

### 4.1 功能
- 独立运行，对单张截图或视频帧进行台标识别。
- 同时执行**YOLO 检测分类**、**YOLO 框内 OCR**、**整图 OCR** 三条路径，输出对比结果，便于判断最佳识别结果，最终频道名称取置信度最高的。

### 4.2 配置
编辑 `channel_recognizer.py` 中的以下参数：
```python
YOLO_MODEL_PATH = "runs/detect/exp_fast/weights/best.pt"   # 模型路径
CONF_THRESHOLD = 0.25                                      # YOLO 置信度阈值
OCR_CONF_THRESHOLD = 0.5                                   # OCR 文本置信度阈值
```

### 4.3 使用方式
```bash
python channel_recognizer.py 图片路径.jpg
```

### 4.4 输出示例
```
==================================================
📷 频道识别 - 三条路径结果:
  路径A (YOLO类别): CCTV8  置信度: 0.775
  路径B (ROI OCR):  CCTV1  置信度: 0.999
  路径C (整图 OCR):  CCTV1  置信度: 0.988
  📊 有效路径数: 3
     - ROI_OCR: 'CCTV1' (置信度: 0.999)
     - 整图OCR: 'CCTV1' (置信度: 0.988)
     - YOLO类别: 'CCTV8' (置信度: 0.775)
  ⚡ 选择置信度最高: 'CCTV1' (ROI_OCR, 0.999)
  📋 备选结果: 'CCTV1'(整图OCR 0.988), 'CCTV8'(YOLO类别 0.775)
  🎯 最终频道: CCTV1 (方法: ROI_OCR, 置信度: 0.999)
==================================================
```

---

## 五、集成到自动扫描流程

### 5.1 典型工作流
1. 使用 `m3u8scan.py` 扫描出可用的流地址。
2. 对于每个流地址，通过 `ffmpeg` 截取一帧画面，保存为临时图片。
3. 调用 `channel_recognizer.py`（或封装其识别函数）获取频道名称。
4. 将结果与流地址关联，输出最终的频道-地址映射表。

### 5.2 快速集成脚本示例
```python
import subprocess
from channel_recognizer import recognize_tv_channel

def get_channel_from_stream(url):
    # 1. 截图
    subprocess.run(f"ffmpeg -i '{url}' -frames:v 1 -y frame.jpg", shell=True)
    # 2. 识别台标
    result = recognize_tv_channel("frame.jpg")
    return result.get("final_channel", "未知")
```

---

## 六、辅助工具说明

| 脚本文件 | 用途 |
|---------|------|
| `tv_channel_hybrid.py` | 命令行混合识别工具，支持 `--full-only` 参数 |
| `yolo_ocr_recognizer.py` | 实验性混合识别，包含详细预处理 |
| `hybrid_recognizer.py` | YOLO 定位 + 透明台标特征匹配（ORB） |
| `testocr.py` | 简单测试单个图片 YOLO + 整图OCR 效果 |
| `auto_label.py` | 用已有模型自动生成标注文件 |
| `fix_all_labels.py` | 根据 `data.yaml` 修正 class_id 和坐标 |
| `generate_preview.py` | 生成带标注框的预览图片 |
| `convert_to_yolo_structure.py` | 将多频道文件夹转为 YOLO 训练集 |
| `merge_tvlogo_dataset.py` | 合并多个 `classes.txt` 并重新映射，转为 YOLO 训练集 |

---

## 七、常见问题

### 7.1 识别准确率低
- 确保训练模型覆盖了你需要识别的所有频道。
- 调整 `CONF_THRESHOLD` 和 `OCR_CONF_THRESHOLD` 阈值。
- 尝试使用 `hybrid_recognizer.py`（特征匹配）作为备选。

### 7.2 扫描速度慢
- 增加 `--threads` 参数（但不要超过网络或服务器限制）。
- 使用 `--no-probe` 跳过分辨率探测，仅测试连通性。
- 将 `playlist.txt` 作为输入，分批使用 `ffmpeg` 截图。

### 7.3 模型文件丢失
- 重新训练或从备份恢复 `best.pt`。
- 临时使用 `hybrid_recognizer.py` 的特征匹配模式（只需透明台标图片）。

### 7.4 依赖库安装失败
- 对于 `paddleocr` 和 `paddlepaddle`，建议使用 conda 环境安装稳定版本。
- 使用 `pip install paddlepaddle==2.6.1 paddleocr==2.7.3` 等特定版本。

---

## 八、扩展与自定义

- **增加新的频道**：收集截图 → 标注 → 增量训练（基于已有 `best.pt` 微调）。
- **更换识别后端**：修改 `channel_recognizer.py` 中的 `recognize_tv_channel` 函数，替换为其他模型。
- **批量处理**：编写 shell 脚本循环调用 `m3u8scan.py` 和识别模块。

---

## 九、许可证与致谢

本工具集基于开源技术构建，包括：
- Ultralytics YOLOv8
- PaddleOCR
- OpenCV
- FFmpeg

感谢所有开源贡献者。

---

**文档版本**：2.0  
**最后更新**：2026-05-03  
**维护者**：Vitter

如需更多帮助，请参考项目内的 `README.md` 或联系维护者。
