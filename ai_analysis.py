import os

from google import genai
from PIL import Image


_client = None


def _get_client():
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("找不到 GEMINI_API_KEY")

        _client = genai.Client(
            api_key=api_key
        )

    return _client


def generate_ai_advice(
    image_path,
    scene,
    camera_info,
    recommendation,
    exposure_diff,
):
    client = _get_client()

    prompt = f"""
你是一位專業且友善的攝影教練，請分析這張照片。

拍攝情境：{scene}

照片 EXIF：
- ISO：{camera_info.get("ISOSpeedRatings", "未知")}
- 光圈：{camera_info.get("FNumberText", "未知")}
- 快門：{camera_info.get("ExposureTimeText", "未知")}
- 焦距：{camera_info.get("FocalLengthText", "未知")}

系統推薦設定：
- ISO：{recommendation.get("iso", "未知")}
- 光圈：{recommendation.get("aperture", "未知")}
- 快門：{recommendation.get("shutter", "未知")}
- 曝光補償：{recommendation.get("exposure_compensation", "未知")}

曝光差異：{exposure_diff} EV

請用繁體中文，並嚴格依照以下格式回答：

【照片觀察】
簡短說明照片的主體、光線、構圖與目前拍攝狀況。

【系統方案】
ISO：{recommendation.get("iso", "未知")}
光圈：{recommendation.get("aperture", "未知")}
快門：{recommendation.get("shutter", "未知")}

【AI 參考方案】
如果你認為系統方案已合理，可以沿用相同參數。
如果你認為需要不同設定，可以提出另一組 ISO、光圈、快門。

【差異與取捨】
如果 AI 方案與系統方案不同，請說明差異主要是在改善：
曝光、動態凝結、ISO 噪點、景深、背景虛化、主體突出或畫質中的哪一項。

【下次拍攝建議】
給使用者 1～2 個可以直接實際操作的建議。

重要規則：
1. 系統方案來自 EXIF、場景與 Adaptive Rule Engine。
2. AI 方案是第二意見，不代表一定比系統方案正確。
3. 如果兩套方案不同，必須說明取捨原因。
4. 不要無理由產生新的參數。
5. 如果系統方案已合理，可以直接沿用，不必刻意改數字。
6. 回答控制在 200 字以內。
7. 不要使用 Markdown 表格。
"""

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    with Image.open(image_path) as image:
        response = client.models.generate_content(
            model=model_name,
            contents=[image, prompt],
        )

    if not response.text:
        raise RuntimeError("Gemini 沒有回傳分析內容")

    return response.text.strip()


def generate_ai_explanation(*, explanation_type, scene, facts):
    """只根據程式已計算的事實，產生短篇繁體中文攝影解釋。"""
    client = _get_client()
    type_label = "攝影參數推薦" if explanation_type == "recommendation" else "曝光模擬"
    prompt = f"""
你是一位親切、準確的攝影教練。請解釋以下{type_label}結果。

拍攝情境：{scene}
系統已確認的資料：
{facts}

規則：
1. 只能使用上面的數值與結論，不可自行新增或改寫 ISO、光圈、快門。
2. 說明這組參數為何適合此情境，以及最重要的取捨。
3. 若有照片分析摘要，請把它和建議連結起來。
4. 使用繁體中文、自然段落，控制在 180 字內，不要使用 Markdown 表格。
"""
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    if not response.text:
        raise RuntimeError("Gemini 沒有回傳解釋內容")
    return response.text.strip()
