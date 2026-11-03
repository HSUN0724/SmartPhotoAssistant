"""Smart Photo Assistant 的唯一情境參數資料來源。

攝影建議頁、照片分析與曝光模擬都必須透過這份資料取得參數，
前端不再維護另一份情境設定。
"""

from copy import deepcopy
import math


def shutter_to_seconds(value):
    text = str(value).strip().lower().replace("秒", "").strip()
    if text.endswith("s"):
        return float(text[:-1])
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return float(numerator) / float(denominator)
    return float(text)


def aperture_to_number(value):
    return float(str(value).lower().replace("f/", "").strip())


def calculate_ev(iso, aperture, shutter):
    seconds = shutter_to_seconds(shutter)
    aperture_number = aperture_to_number(aperture)
    return math.log2((aperture_number ** 2) / seconds) - math.log2(float(iso) / 100)


def setting(
    scene_name,
    icon,
    aperture,
    shutter,
    iso,
    white_balance,
    focus_mode,
    exposure_compensation,
    lens,
    tips,
    *,
    iso_range,
    aperture_range,
    shutter_range,
    brighten_priority,
    darken_priority,
    film_simulation,
    suitable,
):
    """建立同時供推薦與曝光模擬使用的完整情境設定。"""
    reference = {
        "iso": int(iso),
        "aperture": aperture_to_number(aperture),
        "shutter": str(shutter),
        "shutter_seconds": shutter_to_seconds(shutter),
    }
    return {
        "scene_name": scene_name,
        "icon": icon,
        "aperture": aperture,
        "shutter": str(shutter),
        "iso": int(iso),
        "white_balance": white_balance,
        "focus_mode": focus_mode,
        "exposure_compensation": exposure_compensation,
        "lens": lens,
        "tips": tips,
        "film_simulation": film_simulation,
        "suitable": list(suitable),
        "exposure": {
            "reference": reference,
            "target_ev": round(calculate_ev(iso, aperture, shutter), 2),
            "ranges": {
                "iso": list(iso_range),
                "aperture": list(aperture_range),
                "shutter_seconds": list(shutter_range),
            },
            "priorities": {
                "brighten": list(brighten_priority),
                "darken": list(darken_priority),
            },
        },
    }


RECOMMENDATIONS = {
    "portrait": setting("人像", "bi-person", "f/2", "1/200", 200, "Auto", "AF-S", "0 EV", "50–85mm", "使用大光圈營造背景虛化，將焦點放在眼睛。", iso_range=(125, 400), aperture_range=(1.2, 2.8), shutter_range=(1/250, 1/125), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="PRO Neg. Std", suitable=("半身人像", "人物特寫", "婚紗", "畢業照")),
    "landscape": setting("風景", "bi-image-alt", "f/8", "1/125", 125, "Daylight", "AF-S", "0 EV", "16–55mm", "使用小光圈增加景深，並確認地平線水平。", iso_range=(125, 125), aperture_range=(8, 11), shutter_range=(1/250, 1/60), brighten_priority=("shutter", "iso", "aperture"), darken_priority=("shutter", "aperture", "iso"), film_simulation="Velvia", suitable=("山景", "森林", "湖泊", "自然風景")),
    "night": setting("夜景", "bi-moon-stars", "f/2.8", "1/15", 1600, "Auto", "AF-S", "0 EV", "16–35mm", "建議使用腳架與自拍倒數，降低手震。", iso_range=(800, 3200), aperture_range=(2, 4), shutter_range=(1/15, 1), brighten_priority=("shutter", "aperture", "iso"), darken_priority=("iso", "shutter", "aperture"), film_simulation="Classic Neg.", suitable=("城市夜景", "夜間街景", "光軌", "月亮")),
    "sport": setting("運動", "bi-trophy", "f/2.8", "1/1000", 800, "Auto", "AF-C", "0 EV", "50–200mm", "使用高速快門、連續對焦與高速連拍。", iso_range=(400, 1600), aperture_range=(2.8, 4), shutter_range=(1/2000, 1/1000), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="PROVIA", suitable=("足球", "籃球", "跑步", "自行車")),
    "sunset": setting("夕陽", "bi-sunset", "f/8", "1/125", 125, "Daylight", "AF-S", "-0.7 EV", "16–55mm", "適度降低曝光，保留天空色彩與高光。", iso_range=(125, 125), aperture_range=(8, 11), shutter_range=(1/250, 1/60), brighten_priority=("shutter", "aperture", "iso"), darken_priority=("shutter", "aperture", "iso"), film_simulation="Velvia", suitable=("夕陽", "晚霞", "海邊日落", "剪影")),
    "sunrise": setting("日出", "bi-sunrise", "f/8", "1/60", 125, "Daylight", "AF-S", "0 EV", "16–55mm", "使用腳架，提早構圖並留意天空亮度變化。", iso_range=(125, 125), aperture_range=(8, 11), shutter_range=(1/125, 1/30), brighten_priority=("shutter", "aperture", "iso"), darken_priority=("shutter", "aperture", "iso"), film_simulation="Velvia", suitable=("日出", "晨光", "晨曦", "雲海")),
    "food": setting("美食", "bi-cup-hot", "f/2.8", "1/100", 200, "Auto", "AF-S", "0 EV", "23–50mm", "利用窗邊自然光，將焦點放在食物主體。", iso_range=(125, 400), aperture_range=(2, 4), shutter_range=(1/125, 1/60), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="ASTIA", suitable=("餐點", "甜點", "飲品", "料理特寫")),
    "macro": setting("微距", "bi-flower1", "f/8", "1/160", 200, "Auto", "MF", "0 EV", "微距鏡頭", "縮小光圈增加景深，必要時使用腳架與手動對焦。", iso_range=(125, 400), aperture_range=(8, 16), shutter_range=(1/250, 1/125), brighten_priority=("iso", "shutter", "aperture"), darken_priority=("shutter", "iso", "aperture"), film_simulation="Velvia", suitable=("花朵", "昆蟲", "飾品", "微小物件")),
    "street": setting("街拍", "bi-signpost-split", "f/4", "1/250", 400, "Auto", "AF-C", "0 EV", "23–35mm", "保持相機隨時可拍，使用連續對焦捕捉瞬間。", iso_range=(125, 800), aperture_range=(2, 5.6), shutter_range=(1/500, 1/250), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="Classic Chrome", suitable=("城市街頭", "人文紀實", "旅行", "日常生活")),
    "pet": setting("寵物", "bi-heart", "f/2.8", "1/500", 400, "Auto", "AF-C", "0 EV", "35–140mm", "使用高速快門並對焦眼睛，可搭配連拍。", iso_range=(200, 800), aperture_range=(2, 4), shutter_range=(1/1000, 1/500), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="ASTIA", suitable=("狗", "貓", "小動物", "寵物生活")),
    "bird": setting("鳥類", "bi-feather", "f/5.6", "1/1000", 800, "Daylight", "AF-C", "0 EV", "300mm 以上", "使用長焦、高速快門與連續對焦追蹤主體。", iso_range=(400, 1600), aperture_range=(4, 5.6), shutter_range=(1/2000, 1/1000), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="PROVIA", suitable=("飛鳥", "水鳥", "野鳥", "鳥類特寫")),
    "wildlife": setting("野生動物", "bi-binoculars", "f/5.6", "1/1000", 800, "Auto", "AF-C", "0 EV", "100–600mm", "保持安全距離，優先確保快門速度。", iso_range=(400, 1600), aperture_range=(4, 5.6), shutter_range=(1/2000, 1/500), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="PROVIA", suitable=("野生動物", "動物園", "生態紀錄", "大型動物")),
    "concert": setting("演唱會", "bi-music-note-beamed", "f/2.8", "1/250", 3200, "Auto", "AF-C", "-0.7 EV", "50–200mm", "避免使用閃光燈，適度降低曝光以保留舞台高光。", iso_range=(1600, 6400), aperture_range=(2, 2.8), shutter_range=(1/500, 1/250), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="Classic Chrome", suitable=("演唱會", "樂團", "舞台", "表演")),
    "fireworks": setting("煙火", "bi-stars", "f/8", "2s", 125, "Daylight", "MF", "0 EV", "16–55mm", "使用 M 模式、腳架、快門線與手動對焦；M 模式下以光圈和快門控制曝光。", iso_range=(125, 125), aperture_range=(8, 11), shutter_range=(1, 4), brighten_priority=("shutter", "aperture", "iso"), darken_priority=("shutter", "aperture", "iso"), film_simulation="PROVIA", suitable=("煙火大會", "長曝光", "光軌", "夜空")),
    "beach": setting("海灘", "bi-umbrella", "f/8", "1/500", 125, "Daylight", "AF-S", "-0.3 EV", "16–80mm", "留意沙灘與浪花高光，避免過曝。", iso_range=(125, 125), aperture_range=(8, 11), shutter_range=(1/1000, 1/250), brighten_priority=("shutter", "aperture", "iso"), darken_priority=("shutter", "aperture", "iso"), film_simulation="Velvia", suitable=("海灘", "海浪", "水上活動", "海岸風景")),
    "mountain": setting("山景", "bi-triangle", "f/8", "1/125", 125, "Daylight", "AF-S", "0 EV", "16–55mm", "使用小光圈增加景深，清晨或黃昏光線更有層次。", iso_range=(125, 125), aperture_range=(8, 11), shutter_range=(1/250, 1/60), brighten_priority=("shutter", "aperture", "iso"), darken_priority=("shutter", "aperture", "iso"), film_simulation="Velvia", suitable=("山脈", "步道", "登山", "遠景")),
    "snow": setting("雪景", "bi-snow", "f/8", "1/500", 200, "Daylight", "AF-S", "+0.7 EV", "16–80mm", "適度增加曝光補償，避免白雪拍成灰色。", iso_range=(125, 400), aperture_range=(8, 11), shutter_range=(1/1000, 1/250), brighten_priority=("shutter", "iso", "aperture"), darken_priority=("shutter", "iso", "aperture"), film_simulation="PROVIA", suitable=("雪景", "雪人", "滑雪", "雪山")),
    "rain": setting("雨天", "bi-cloud-rain", "f/4", "1/250", 800, "Cloudy", "AF-C", "0 EV", "16–55mm", "做好防水保護，利用倒影增加畫面層次。", iso_range=(400, 1600), aperture_range=(2.8, 5.6), shutter_range=(1/500, 1/125), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="Classic Chrome", suitable=("雨景", "雨天街景", "水滴", "倒影")),
    "architecture": setting("建築", "bi-building", "f/8", "1/125", 125, "Auto", "AF-S", "0 EV", "廣角鏡頭", "保持相機水平，留意垂直線與透視變形。", iso_range=(125, 125), aperture_range=(8, 11), shutter_range=(1/250, 1/60), brighten_priority=("shutter", "aperture", "iso"), darken_priority=("shutter", "aperture", "iso"), film_simulation="Classic Chrome", suitable=("建築", "高樓", "古蹟", "地標")),
    "museum": setting("博物館", "bi-bank", "f/2.8", "1/80", 1600, "Auto", "AF-S", "0 EV", "23–50mm", "遵守場館規定，使用大光圈並穩定握持。", iso_range=(800, 3200), aperture_range=(2, 4), shutter_range=(1/125, 1/60), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="ETERNA", suitable=("展覽", "文物", "藝術品", "室內展館")),
    "indoor": setting("室內", "bi-house", "f/2.8", "1/80", 800, "Auto", "AF-S", "0 EV", "23–50mm", "優先利用窗邊自然光，注意混合光源偏色。", iso_range=(400, 1600), aperture_range=(2, 4), shutter_range=(1/125, 1/60), brighten_priority=("aperture", "iso", "shutter"), darken_priority=("shutter", "iso", "aperture"), film_simulation="PRO Neg. Std", suitable=("家居", "辦公室", "教室", "室內生活")),
}


def get_scene_profile(scene_key):
    profile = RECOMMENDATIONS.get(scene_key)
    if not profile:
        return None
    result = deepcopy(profile)
    result["scene_key"] = scene_key
    return result


def list_scene_choices():
    return [
        {
            "key": key,
            "name": profile["scene_name"],
            "icon": profile["icon"],
        }
        for key, profile in RECOMMENDATIONS.items()
    ]


def synchronize_reference(profile):
    """資料庫覆寫代表參數時，讓曝光基準同步更新。"""
    result = deepcopy(profile)
    reference = result["exposure"]["reference"]
    reference["iso"] = int(result["iso"])
    reference["aperture"] = aperture_to_number(result["aperture"])
    reference["shutter"] = str(result["shutter"])
    reference["shutter_seconds"] = shutter_to_seconds(result["shutter"])
    result["exposure"]["target_ev"] = round(
        calculate_ev(result["iso"], result["aperture"], result["shutter"]),
        2,
    )
    return result
