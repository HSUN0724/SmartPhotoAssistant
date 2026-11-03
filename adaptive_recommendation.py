import math
from copy import deepcopy

from recommendations import shutter_to_seconds

ISO_STEPS = [
    125,
    160,
    200,
    250,
    320,
    400,
    500,
    640,
    800,
    1000,
    1250,
    1600,
    2000,
    2500,
    3200,
    4000,
    5000,
    6400,
    8000,
    10000,
    12800,
]


def read_exif_values(camera_info):
    """從 EXIF 取得可運算的曝光三要素。"""

    try:
        iso = int(camera_info["ISOSpeedRatings"])

        aperture = (
            camera_info["FNumber"][0]
            / camera_info["FNumber"][1]
        )

        shutter = (
            camera_info["ExposureTime"][0]
            / camera_info["ExposureTime"][1]
        )

        return {
            "iso": iso,
            "aperture": aperture,
            "shutter_seconds": shutter,
        }

    except (
        KeyError,
        TypeError,
        ValueError,
        ZeroDivisionError,
    ):
        return None


def calculate_exposure_value(iso, aperture, shutter_seconds):
    """
    計算曝光值。

    數值主要用來比較參數組合的相對曝光，
    而不是判斷照片絕對亮度。
    """

    return (
        math.log2((aperture ** 2) / shutter_seconds)
        - math.log2(iso / 100)
    )


def seconds_to_shutter_text(seconds):
    """把秒數轉成人類容易閱讀的快門格式。"""

    if seconds >= 1:
        if float(seconds).is_integer():
            return f"{int(seconds)}s"

        return f"{seconds:.1f}s"

    denominator = round(1 / seconds)

    return f"1/{denominator}"


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def recommend_iso_for_exposure(
    original_ev,
    aperture,
    shutter_seconds,
    minimum_iso,
    maximum_iso,
):
    """
    在光圈與快門確定後，
    計算維持原照片曝光量所需要的 ISO。
    """

    iso = (
        100
        * (aperture ** 2)
        / shutter_seconds
        / (2 ** original_ev)
    )

    iso = clamp(
        iso,
        minimum_iso,
        maximum_iso,
    )

    valid_iso_values = [
        value
        for value in ISO_STEPS
        if minimum_iso <= value <= maximum_iso
    ]

    if not valid_iso_values:
        return int(round(iso))

    return min(
        valid_iso_values,
        key=lambda value: abs(value - iso),
    )


def build_adaptive_recommendation(
    camera_info,
    scene,
    base_profile,
):
    """
    根據：
    1. 原始 EXIF
    2. 場景需求
    3. 原照片曝光量

    動態建立推薦參數。

    第一版策略：
    - 場景決定主要攝影需求
    - 優先調整快門
    - ISO 自動補償曝光
    - 光圈暫時保留原照片設定
    """

    original = read_exif_values(camera_info)

    if not original:
        return deepcopy(base_profile)

    recommendation = deepcopy(base_profile)

    original_iso = original["iso"]
    original_aperture = original["aperture"]
    original_shutter = original["shutter_seconds"]

    original_ev = calculate_exposure_value(
        original_iso,
        original_aperture,
        original_shutter,
    )

   

    # --------------------------------
    # 從 recommendations.py 的場景 Profile
    # 取得情境建議快門
    # --------------------------------

    try:
        reference_shutter = (
            base_profile["exposure"]["reference"]["shutter"]
        )

        minimum_shutter = shutter_to_seconds(
            reference_shutter
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        minimum_shutter = original_shutter


    # 原照片如果已經比情境建議快門更快，
    # 就保留原本較快的快門。
    recommended_shutter = min(
        original_shutter,
        minimum_shutter,
    )

    # --------------------------------
    # 第一版先保留原始光圈
    # --------------------------------

    recommended_aperture = original_aperture

    # --------------------------------
    # 讀取場景 ISO 範圍
    # --------------------------------

    iso_range = (
        base_profile
        .get("exposure", {})
        .get("ranges", {})
        .get("iso", [125, 6400])
    )

    minimum_iso = int(iso_range[0])

    # 不讓 adaptive 第一版被舊場景 ISO 上限卡死。
    maximum_iso = max(
        int(iso_range[-1]),
        original_iso,
        6400,
    )

    # --------------------------------
    # ISO 補償快門改變造成的曝光差
    # --------------------------------

    recommended_iso = recommend_iso_for_exposure(
        original_ev,
        recommended_aperture,
        recommended_shutter,
        minimum_iso,
        maximum_iso,
    )

    recommendation["iso"] = recommended_iso
    recommendation["aperture"] = (
        f"f/{recommended_aperture:.1f}"
    )
    recommendation["shutter"] = (
        seconds_to_shutter_text(
            recommended_shutter
        )
    )

    # --------------------------------
    # 同步 exposure.reference
    # 避免其他模組仍使用舊的固定情境參數
    # --------------------------------

    exposure = recommendation.setdefault(
        "exposure",
        {}
    )

    reference = exposure.setdefault(
        "reference",
        {}
    )

    reference["iso"] = recommended_iso
    reference["aperture"] = recommended_aperture
    reference["shutter"] = seconds_to_shutter_text(
        recommended_shutter
    )
    reference["shutter_seconds"] = recommended_shutter

    # 同步 Adaptive 推薦後的 EV
    exposure["target_ev"] = (
        calculate_exposure_value(
            recommended_iso,
            recommended_aperture,
            recommended_shutter,
        )
    )

    recommendation["adaptive"] = True

    recommendation["adaptive_reason"] = (
        "推薦參數以原照片 EXIF 為基礎，"
        "先依拍攝情境調整快門，再以 ISO 補償曝光差異。"
    )

    recommendation["original_settings"] = {
        "iso": original_iso,
        "aperture": original_aperture,
        "shutter_seconds": original_shutter,
        "shutter": seconds_to_shutter_text(
            original_shutter
        ),
    }

    return recommendation