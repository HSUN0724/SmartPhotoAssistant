# exposure.py
import math


def shutter_to_seconds(shutter):
    value = str(shutter).strip().lower().replace("秒", "").strip()
    if value.endswith("s"):
        return float(value[:-1])
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)

def calculate_ev(aperture, shutter, iso):
    """
    aperture : 光圈值，例如 1.8
    shutter  : 快門秒數，例如 1/60 = 0.0167
    iso      : ISO，例如 250
    """

    return math.log2((aperture ** 2) / shutter) - math.log2(iso / 100)


def calculate_camera_ev(camera):

    aperture = camera["FNumber"][0] / camera["FNumber"][1]

    shutter = camera["ExposureTime"][0]/camera["ExposureTime"][1]

    iso = camera["ISOSpeedRatings"]

    return calculate_ev(aperture, shutter, iso)


def calculate_recommend_ev(recommend):

    aperture = float(recommend["aperture"].replace("f/", ""))

    shutter = shutter_to_seconds(recommend["shutter"])

    iso = recommend["iso"]

    return calculate_ev(aperture, shutter, iso)


def compare_exposure(camera, recommend):

    current = calculate_camera_ev(camera)

    target = calculate_recommend_ev(recommend)


    # 正值代表目前設定比推薦值得到更多曝光，負值代表更少曝光。
    return round(target - current, 1)


def evaluate_exposure(profile, iso, aperture, shutter):
    """以共用情境設定評估曝光量及三項參數是否落在推薦範圍。"""
    iso_value = int(iso)
    aperture_value = float(aperture)
    shutter_seconds = shutter_to_seconds(shutter)
    current_ev = calculate_ev(aperture_value, shutter_seconds, iso_value)
    target_ev = float(profile["exposure"]["target_ev"])
    relative_ev = round(target_ev - current_ev, 1)
    ranges = profile["exposure"]["ranges"]

    checks = {
        "iso": ranges["iso"][0] <= iso_value <= ranges["iso"][1],
        "aperture": ranges["aperture"][0] <= aperture_value <= ranges["aperture"][1],
        "shutter": (
            ranges["shutter_seconds"][0]
            <= shutter_seconds
            <= ranges["shutter_seconds"][1]
        ),
    }

    if relative_ev < -1:
        exposure_status = "under"
    elif relative_ev > 1:
        exposure_status = "over"
    else:
        exposure_status = "normal"

    return {
        "current_ev": round(current_ev, 1),
        "target_ev": round(target_ev, 1),
        "relative_ev": relative_ev,
        "exposure_status": exposure_status,
        "parameter_checks": checks,
        "parameters_suitable": all(checks.values()),
    }

