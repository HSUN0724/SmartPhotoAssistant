# analysis.py
# Smart Photo Assistant 分析模組
from exposure import compare_exposure

def compare_setting(camera_info, recommend):

    analysis = []

    analysis.append(compare_iso(camera_info, recommend))

    analysis.append(compare_aperture(camera_info, recommend))

    analysis.append(compare_shutter(camera_info, recommend))

    diff = compare_exposure(camera_info, recommend)

    analysis.append(exposure_message(diff))

    return analysis

def exposure_message(diff):

    if abs(diff) < 0.3:
        return "曝光正常，與推薦設定相近。"

    elif diff >= 2:
        return f"曝光偏亮（+{diff:.1f} EV），建議降低 ISO、縮小光圈或提高快門速度。"

    elif diff > 0:
        return f"曝光稍亮（+{diff:.1f} EV）。"

    elif diff <= -2:
        return f"曝光不足（{diff:.1f} EV），建議提高 ISO、放大光圈或降低快門速度。"

    else:
        return f"曝光稍暗（{diff:.1f} EV）。"


def compare_iso(camera_info, recommend):

    if "ISOSpeedRatings" not in camera_info:
        return "無法讀取照片 ISO，可能照片沒有完整 EXIF。"

    photo_iso = camera_info["ISOSpeedRatings"]
    recommend_iso = recommend["iso"]

    if photo_iso == recommend_iso:
        return f"ISO：{photo_iso}，與建議值一致。"

    elif photo_iso < recommend_iso:
        return (
            f"ISO：{photo_iso}，低於建議值 {recommend_iso}，"
            "畫質較佳，但照片可能偏暗。"
        )

    else:
        return (
            f"ISO：{photo_iso}，高於建議值 {recommend_iso}，"
            "可能產生較多雜訊。"
        )

def shutter_to_seconds(shutter):

    shutter = shutter.strip().lower()

    # 像 5s、10s
    if shutter.endswith("s"):

        return float(shutter[:-1])

    # 像 1/60
    if "/" in shutter:

        a, b = shutter.split("/")

        return float(a) / float(b)

    # 其他
    return float(shutter)

def compare_shutter(camera_info, recommend):

    if "ExposureTime" not in camera_info:
        return "無法讀取照片快門資訊。"

    photo_shutter = (
        camera_info["ExposureTime"][0] /
        camera_info["ExposureTime"][1]
    )

    recommend_shutter = shutter_to_seconds(
        recommend["shutter"]
    )

    if abs(photo_shutter - recommend_shutter) < 0.001:

        return "快門速度與建議值一致。"

    elif photo_shutter > recommend_shutter:

        return (
            f"快門較慢（{camera_info['ExposureTimeText']}），"
            "進光量較多，但容易因手震或主體移動造成模糊。"
        )

    else:

        return (
            f"快門較快（{camera_info['ExposureTimeText']}），"
            "能凝結動作，但可能需要提高 ISO 或增加光線。"
        )

def compare_aperture(camera_info, recommend):

    if "FNumber" not in camera_info:
        return "無法讀取照片光圈資訊。"

    # EXIF 光圈
    photo_aperture = (
        camera_info["FNumber"][0] /
        camera_info["FNumber"][1]
    )

    # MySQL 光圈，例如 "f/1.8"
    recommend_aperture = float(
        recommend["aperture"].replace("f/", "")
    )

    if abs(photo_aperture - recommend_aperture) < 0.1:
        return (
            f"光圈：f/{photo_aperture:.1f}，與建議值一致。"
        )

    elif photo_aperture < recommend_aperture:

        return (
            f"光圈：f/{photo_aperture:.1f}，"
            f"比建議值 f/{recommend_aperture} 更大，"
            "背景虛化效果更明顯。"
        )

    else:

        return (
            f"光圈：f/{photo_aperture:.1f}，"
            f"比建議值 f/{recommend_aperture} 更小，"
            "景深較深，背景會較清楚。"
        )

def scene_analysis(scene, camera_info, recommend):

    if scene == "portrait":
        return portrait_analysis(camera_info, recommend)

    elif scene == "food":
        return food_analysis(camera_info, recommend)

    elif scene == "landscape":
        return landscape_analysis(camera_info, recommend)

    elif scene == "night":
        return night_analysis(camera_info, recommend)

    elif scene == "sport":
        return sport_analysis(camera_info, recommend)

    elif scene == "sunset":
        return sunset_analysis(camera_info, recommend)

    elif scene == "sunrise":
        return sunrise_analysis(camera_info, recommend)

    elif scene == "pet":
        return pet_analysis(camera_info, recommend)

    elif scene == "bird":
        return bird_analysis(camera_info, recommend)

    elif scene == "wildlife":
        return wildlife_analysis(camera_info, recommend)

    elif scene == "fireworks":
        return fireworks_analysis(camera_info, recommend)

    elif scene == "architecture":
        return architecture_analysis(camera_info, recommend)

    elif scene == "rain":
        return rain_analysis(camera_info, recommend)

    elif scene == "snow":
        return snow_analysis(camera_info, recommend)

    elif scene == "indoor":
        return indoor_analysis(camera_info, recommend)

    elif scene == "macro":
        return macro_analysis(camera_info, recommend)

    elif scene == "street":
        return street_analysis(camera_info, recommend)

    elif scene == "beach":
        return beach_analysis(camera_info, recommend)

    elif scene == "mountain":
        return mountain_analysis(camera_info, recommend)

    elif scene == "museum":
        return museum_analysis(camera_info, recommend)

    elif scene == "concert":
        return concert_analysis(camera_info, recommend)

    else:
        return ["目前尚未提供此情境分析。"]
    
def portrait_analysis(camera_info, recommend):

    analysis = []

    # ---------- ISO ----------
    photo_iso = camera_info.get("ISOSpeedRatings")

    if photo_iso:

        if photo_iso > recommend["iso"]:

            analysis.append(
                f"ISO {photo_iso} 偏高，若光線充足，可降低至 ISO {recommend['iso']}，讓膚色更乾淨、減少雜訊。"
            )

        elif photo_iso < recommend["iso"]:

            analysis.append(
                "ISO 較低，可保留更多人物細節，畫質表現良好。"
            )

        else:

            analysis.append(
                "ISO 設定符合建議，可兼顧亮度與畫質。"
            )

    # ---------- 光圈 ----------
    if "FNumber" in camera_info:

        photo_aperture = (
            camera_info["FNumber"][0] /
            camera_info["FNumber"][1]
        )

        recommend_aperture = float(
            recommend["aperture"].replace("f/", "")
        )

        if photo_aperture < recommend_aperture:

            analysis.append(
                "使用較大光圈，可營造柔和背景虛化，使人物更加突出。"
            )

        elif abs(photo_aperture - recommend_aperture) < 0.1:

            analysis.append(
                "光圈符合人像建議，可兼顧主體清晰與背景虛化效果。"
            )

        else:

            analysis.append(
                "光圈較小，背景會比較清楚，若希望人物更突出，可放大光圈。"
            )

    # ---------- 快門 ----------
    if "ExposureTime" in camera_info:

        photo_shutter = (
            camera_info["ExposureTime"][0] /
            camera_info["ExposureTime"][1]
        )

        recommend_shutter = shutter_to_seconds(
            recommend["shutter"]
        )

        if photo_shutter > recommend_shutter:

            analysis.append(
                "快門略慢，請提醒被拍攝者保持不動，避免人物因晃動而模糊。"
            )

        elif abs(photo_shutter - recommend_shutter) < 0.001:

            analysis.append(
                "快門速度符合建議，可有效降低人物晃動。"
            )

        else:

            analysis.append(
                "快門較快，可凝結人物動作，但若光線不足，可能需要提高 ISO。"
            )

    # ---------- 人像攝影技巧 ----------
    analysis.append(
        "建議將對焦點放在人物眼睛，能讓整張人像更有神、更具吸引力。"
    )

    return analysis


def food_analysis(camera_info, recommend):

    analysis = []

    # ---------- ISO ----------
    photo_iso = camera_info.get("ISOSpeedRatings")

    if photo_iso:

        if photo_iso > recommend["iso"]:

            analysis.append(
                f"ISO {photo_iso} 略高，若環境光線充足，建議降低至 ISO {recommend['iso']}，可減少雜訊並提升食物細節。"
            )

        elif photo_iso < recommend["iso"]:

            analysis.append(
                "ISO 較低，可保留較好的畫質，適合美食攝影。"
            )

        else:

            analysis.append(
                "ISO 設定符合建議，畫質與亮度取得良好平衡。"
            )

    # ---------- 光圈 ----------
    if "FNumber" in camera_info:

        photo_aperture = (
            camera_info["FNumber"][0] /
            camera_info["FNumber"][1]
        )

        recommend_aperture = float(
            recommend["aperture"].replace("f/", "")
        )

        if photo_aperture < recommend_aperture:

            analysis.append(
                "目前使用較大光圈，可有效突出主餐，但若希望整份料理都清楚，可縮小光圈至 f/2.8～f/4。"
            )

        elif abs(photo_aperture - recommend_aperture) < 0.1:

            analysis.append(
                "光圈設定符合美食攝影建議，可兼顧主體與景深。"
            )

        else:

            analysis.append(
                "光圈較小，整份餐點都會較清楚，但背景虛化效果會降低。"
            )

    # ---------- 快門 ----------
    if "ExposureTime" in camera_info:

        photo_shutter = (
            camera_info["ExposureTime"][0] /
            camera_info["ExposureTime"][1]
        )

        recommend_shutter = shutter_to_seconds(
            recommend["shutter"]
        )

        if photo_shutter > recommend_shutter:

            analysis.append(
                "快門略慢，拍攝靜態食物通常沒有問題，但建議保持手持穩定，以避免照片模糊。"
            )

        elif abs(photo_shutter - recommend_shutter) < 0.001:

            analysis.append(
                "快門速度符合建議，可兼顧亮度與清晰度。"
            )

        else:

            analysis.append(
                "快門較快，可降低手震影響，但若環境較暗，可能需要提高 ISO。"
            )

    # ---------- 美食攝影技巧 ----------
    analysis.append(
        "建議利用窗邊自然光拍攝，可讓食物色彩更加自然，也避免強烈陰影。"
    )

    return analysis

def landscape_analysis(camera_info, recommend):

    analysis = []

    # ---------- ISO ----------
    photo_iso = camera_info.get("ISOSpeedRatings")

    if photo_iso:

        if photo_iso > recommend["iso"]:

            analysis.append(
                f"ISO {photo_iso} 偏高，風景攝影建議降低至 ISO {recommend['iso']}，可保留更多細節與色彩。"
            )

        else:

            analysis.append(
                "ISO 設定良好，可獲得乾淨且細緻的畫質。"
            )

    # ---------- 光圈 ----------
    if "FNumber" in camera_info:

        photo_aperture = (
            camera_info["FNumber"][0] /
            camera_info["FNumber"][1]
        )

        recommend_aperture = float(
            recommend["aperture"].replace("f/", "")
        )

        if photo_aperture < recommend_aperture:

            analysis.append(
                "光圈偏大，景深較淺，遠近景物可能無法同時清晰，建議縮小光圈。"
            )

        elif abs(photo_aperture - recommend_aperture) < 0.1:

            analysis.append(
                "光圈符合風景攝影建議，可兼顧前景與遠景清晰度。"
            )

        else:

            analysis.append(
                "使用較小光圈，可增加景深，讓整體畫面更清晰。"
            )

    # ---------- 快門 ----------
    if "ExposureTime" in camera_info:

        photo_shutter = (
            camera_info["ExposureTime"][0] /
            camera_info["ExposureTime"][1]
        )

        recommend_shutter = shutter_to_seconds(
            recommend["shutter"]
        )

        if photo_shutter > recommend_shutter:

            analysis.append(
                "快門較慢，若使用腳架可進一步降低 ISO，提高畫質。"
            )

        else:

            analysis.append(
                "快門速度適中，可降低手震造成的模糊。"
            )

    # ---------- 風景攝影技巧 ----------
    analysis.append(
        "建議開啟相機水平儀，保持地平線水平，畫面會更加穩定。"
    )

    analysis.append(
        "黃金時段（日出、日落）拍攝，可獲得更柔和自然的光線。"
    )

    return analysis    

def night_analysis(camera_info, recommend):

    analysis = []

    photo_iso = camera_info.get("ISOSpeedRatings")

    if photo_iso:

        if photo_iso < recommend["iso"]:

            analysis.append(
                "ISO 較低，夜景可能偏暗，可適度提高 ISO 增加亮度。"
            )

        elif photo_iso > recommend["iso"]:

            analysis.append(
                "ISO 偏高，夜景雜訊可能增加，若有腳架可降低 ISO。"
            )

        else:

            analysis.append(
                "ISO 設定符合夜景拍攝建議。"
            )

    analysis.append(
        "建議使用腳架拍攝，避免長時間曝光造成模糊。"
    )

    analysis.append(
        "可使用 2 秒自拍或遙控快門降低震動。"
    )

    return analysis

def sport_analysis(camera_info, recommend):

    analysis = []

    if "ExposureTime" in camera_info:

        photo_shutter = (
            camera_info["ExposureTime"][0] /
            camera_info["ExposureTime"][1]
        )

        if photo_shutter > 1/500:

            analysis.append(
                "快門較慢，快速移動的主體可能產生模糊。"
            )

        else:

            analysis.append(
                "快門速度足夠，可有效凝結動作。"
            )

    analysis.append(
        "建議使用 AF-C（連續對焦）追蹤移動中的主體。"
    )

    analysis.append(
        "可開啟高速連拍，提高成功率。"
    )

    return analysis

def sunset_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "建議降低曝光約 0.3～1 EV，可保留晚霞色彩層次。"
    )

    analysis.append(
        "白平衡建議使用 Daylight，可保留暖色調。"
    )

    analysis.append(
        "可利用人物剪影增加畫面故事感。"
    )

    return analysis

def sunrise_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "日出光線柔和，可適度增加曝光讓畫面更明亮。"
    )

    analysis.append(
        "建議使用 Daylight 白平衡保留晨曦暖色。"
    )

    analysis.append(
        "可利用逆光拍攝營造夢幻氛圍。"
    )

    return analysis

def pet_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "寵物容易移動，建議快門至少 1/250 秒以上。"
    )

    analysis.append(
        "建議使用 AF-C 持續對焦。"
    )

    analysis.append(
        "可降低拍攝角度，讓照片更有臨場感。"
    )

    return analysis

def bird_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "建議使用高速快門（1/1000 秒以上）凝結飛行畫面。"
    )

    analysis.append(
        "建議搭配長焦鏡頭拍攝。"
    )

    analysis.append(
        "可使用連拍模式，提高成功率。"
    )

    return analysis

def wildlife_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "建議保持安全距離，避免驚擾野生動物。"
    )

    analysis.append(
        "使用長焦鏡頭可拍攝更多細節。"
    )

    analysis.append(
        "可提高 ISO 換取更快的快門速度。"
    )

    return analysis

def fireworks_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "建議 ISO 100，可獲得最佳畫質。"
    )

    analysis.append(
        "建議使用腳架進行長時間曝光。"
    )

    analysis.append(
        "建議手動對焦至無限遠。"
    )

    return analysis

def architecture_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "建議保持相機水平，避免建築物變形。"
    )

    analysis.append(
        "使用較小光圈可增加整體清晰度。"
    )

    analysis.append(
        "廣角鏡頭適合拍攝大型建築。"
    )

    return analysis

def rain_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "建議提高快門速度，可凝結雨滴效果。"
    )

    analysis.append(
        "注意保護相機避免受潮。"
    )

    analysis.append(
        "雨後地面倒影可增加畫面層次。"
    )

    return analysis

def snow_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "雪景容易曝光不足，可增加曝光補償 +0.3～+1 EV。"
    )

    analysis.append(
        "白雪容易欺騙測光，請注意直方圖。"
    )

    analysis.append(
        "建議使用偏光鏡增加天空層次。"
    )

    return analysis

def indoor_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "室內光線較弱，可提高 ISO 或使用較大光圈。"
    )

    analysis.append(
        "若允許，可利用窗邊自然光提升畫質。"
    )

    analysis.append(
        "注意不同光源造成的白平衡偏色。"
    )

    return analysis

def macro_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "微距拍攝景深很淺，建議使用 f/8 左右增加清晰範圍。"
    )

    analysis.append(
        "建議使用腳架提升成功率。"
    )

    analysis.append(
        "對焦請放在主體最重要的位置。"
    )

    return analysis

def street_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "街拍建議使用自然光，捕捉人物最真實的一面。"
    )

    analysis.append(
        "建議快門速度 1/250 秒以上，可避免路人移動造成模糊。"
    )

    analysis.append(
        "可使用廣角或35mm焦段，增加故事感。"
    )

    return analysis

def beach_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "海灘光線通常較強，可適度降低 ISO 提升畫質。"
    )

    analysis.append(
        "建議使用偏光鏡，可降低海面反光並增加天空層次。"
    )

    analysis.append(
        "注意避免沙粒進入鏡頭與相機。"
    )

    return analysis

def mountain_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "山景建議使用較小光圈（f/8～f/11），增加景深。"
    )

    analysis.append(
        "可使用廣角鏡頭呈現山脈的壯闊感。"
    )

    analysis.append(
        "若有雲海，可適度降低曝光保留天空細節。"
    )

    return analysis

def museum_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "博物館通常光線不足，可適度提高 ISO。"
    )

    analysis.append(
        "若館方禁止使用閃光燈，建議使用大光圈拍攝。"
    )

    analysis.append(
        "注意保持相機穩定，避免手震。"
    )

    return analysis

def concert_analysis(camera_info, recommend):

    analysis = []

    analysis.append(
        "演唱會光線變化快速，建議使用 Auto ISO。"
    )

    analysis.append(
        "快門建議 1/250 秒以上，可降低人物晃動。"
    )

    analysis.append(
        "若使用長焦鏡頭，可捕捉歌手表情細節。"
    )

    return analysis

