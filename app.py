from flask import Flask, jsonify, render_template, request, url_for
from flask import redirect, session
import os
from fractions import Fraction
from pathlib import Path
from uuid import uuid4
from copy import deepcopy

import piexif
import pymysql
from PIL import Image, ImageOps, UnidentifiedImageError
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db
from database import init_db

from adaptive_recommendation import build_adaptive_recommendation
from analysis import compare_setting, scene_analysis
from ai_analysis import generate_ai_advice, generate_ai_explanation
from exposure import compare_exposure, evaluate_exposure
from recommendations import (
    get_scene_profile,
    list_scene_choices,
    synchronize_reference,
)
from article_scraper import SOURCES, scrape_photography_articles

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
PHOTO_RETENTION_HOURS = 24 # 時限24小時
ALLOWED_EXTENSIONS = {"jpg", "jpeg"}
ANALYSIS_IMAGE_MAX_SIZE = (768, 768)
ANALYSIS_IMAGE_QUALITY = 75

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv(
    "SECRET_KEY",
    "smartphoto-dev-secret"
)
init_db()
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_recommendation(scene):
    """優先讀取 MySQL；未設定或連線失敗時改用內建資料。"""
    base_profile = get_scene_profile(scene)
    if not base_profile:
        return None

    required = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    use_database = os.getenv("USE_DATABASE", "false").lower() == "true"

    if use_database and all(os.getenv(key) for key in required):
        try:
            connection = pymysql.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=2,
                read_timeout=2,
                write_timeout=2,
            )
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT * FROM camera_settings WHERE scene = %s",
                        (scene,),
                    )
                    result = cursor.fetchone()
                    if result:
                        return normalize_recommendation(base_profile, result)
            finally:
                connection.close()
        except pymysql.MySQLError:
            app.logger.warning("資料庫無法連線，已改用內建推薦資料。")

    return normalize_recommendation(base_profile)


def normalize_recommendation(base_profile, database_result=None):
    """以內建完整設定為骨架，相容舊資料庫可覆寫的基本欄位。"""
    normalized = dict(base_profile)
    if database_result:
        editable_fields = {
            "scene_name", "aperture", "shutter", "iso", "white_balance",
            "focus_mode", "exposure_compensation", "lens", "tips",
        }
        for field in editable_fields:
            if database_result.get(field) not in (None, ""):
                normalized[field] = database_result[field]

    compensation = normalized.get("exposure_compensation")

    # 相容舊資料庫可能使用的欄位名稱。
    if database_result and database_result.get("exposure_compensation") in (None, ""):
        for field in ("ev_compensation", "exposureCompensation", "compensation"):
            if database_result.get(field) not in (None, ""):
                compensation = database_result[field]
                break

    if compensation in (None, ""):
        compensation = "0 EV"
    elif isinstance(compensation, (int, float)):
        compensation = f"{compensation:+g} EV" if compensation else "0 EV"

    normalized["exposure_compensation"] = str(compensation)
    return synchronize_reference(normalized)


@app.context_processor
def inject_scene_choices():
    """三個功能頁共用同一份情境清單。"""
    return {"scenes": list_scene_choices()}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def decode_exif_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip("\x00")
    return value


def read_camera_info(path):
    try:
        exif_dict = piexif.load(str(path))
    except (ValueError, piexif.InvalidImageDataError) as exc:
        raise ValueError("照片沒有可讀取的 EXIF 資訊。") from exc

    camera_info = {}
    for ifd_name in ("0th", "Exif"):
        for tag_id, value in exif_dict.get(ifd_name, {}).items():
            tag_data = piexif.TAGS.get(ifd_name, {}).get(tag_id)
            if tag_data:
                camera_info[tag_data["name"]] = decode_exif_value(value)

    if "FNumber" in camera_info:
        numerator, denominator = camera_info["FNumber"]
        camera_info["FNumberText"] = f"f/{numerator / denominator:.1f}"
    else:
        camera_info["FNumberText"] = "未知"

    if "ExposureTime" in camera_info:
        numerator, denominator = camera_info["ExposureTime"]
        camera_info["ExposureTimeText"] = f"{numerator}/{denominator} 秒"
    else:
        camera_info["ExposureTimeText"] = "未知"

    if "FocalLength" in camera_info:
        numerator, denominator = camera_info["FocalLength"]
        camera_info["FocalLengthText"] = f"{numerator / denominator:.0f} mm"
    else:
        camera_info["FocalLengthText"] = "未知"

    # 即使只有部分 EXIF 也保留並顯示；是否足以進行曝光分析，交由
    # upload() 的 has_exif 判斷。部分手機瀏覽器直接拍照時可能只回傳
    # 部分欄位，不能因此把仍可讀取的品牌、型號等資訊全部丟棄。
    return camera_info

def cleanup_expired_uploads():
    """刪除超過 24 小時、且沒有被使用者永久保存的暫存照片。"""

    cutoff_time = datetime.now() - timedelta(
        hours=PHOTO_RETENTION_HOURS
    )

    # 先取得所有已永久保存的照片檔名
    db = get_db()

    saved_rows = db.execute(
        """
        SELECT filename
        FROM photos
        WHERE saved = 1
          AND retention_mode = 'keep'
        """
    ).fetchall()

    db.close()

    saved_filenames = {
        row["filename"]
        for row in saved_rows
    }

    for file_path in UPLOAD_DIR.iterdir():

        if not file_path.is_file():
            continue

        # -------------------------
        # 判斷這是不是 Gemini 分析縮圖
        # -------------------------
        if file_path.name.endswith("-analysis.jpg"):

            original_stem = file_path.name.removesuffix(
                "-analysis.jpg"
            )

            # 找出對應的原始照片
            related_saved = any(
                Path(filename).stem == original_stem
                for filename in saved_filenames
            )

            # 原圖已永久保存 → 分析縮圖也保留
            if related_saved:
                continue

        else:
            # 原始照片本身已永久保存
            if file_path.name in saved_filenames:
                continue

        try:
            modified_time = datetime.fromtimestamp(
                file_path.stat().st_mtime
            )

            if modified_time < cutoff_time:
                file_path.unlink()

                app.logger.info(
                    "已刪除過期暫存照片：%s",
                    file_path.name,
                )

        except OSError as exc:
            app.logger.warning(
                "清理暫存照片失敗 %s：%s",
                file_path,
                exc,
            )

def build_exposure_params(camera_info):
    """把 EXIF 轉成曝光模擬可直接接收的純數值格式。"""
    try:
        aperture_numerator, aperture_denominator = camera_info["FNumber"]
        shutter_numerator, shutter_denominator = camera_info["ExposureTime"]
        shutter_fraction = Fraction(shutter_numerator, shutter_denominator)
        return {
            "iso": int(camera_info["ISOSpeedRatings"]),
            "aperture": round(aperture_numerator / aperture_denominator, 2),
            "shutter": f"{shutter_fraction.numerator}/{shutter_fraction.denominator}",
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def create_analysis_image(source_path):
    """建立給結果頁與 Gemini 使用的小圖，避免手機再次下載原始大圖。"""
    analysis_name = f"{source_path.stem}-analysis.jpg"
    analysis_path = UPLOAD_DIR / analysis_name

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(ANALYSIS_IMAGE_MAX_SIZE, Image.Resampling.LANCZOS)

        if image.mode != "RGB":
            image = image.convert("RGB")

        image.save(
            analysis_path,
            "JPEG",
            quality=ANALYSIS_IMAGE_QUALITY,
            optimize=True,
        )

    return analysis_name, analysis_path


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/recommend")
def recommend():
    return render_template("recommend.html")


@app.route("/exposure")
def exposure():
    return render_template("exposure.html")

@app.route("/api/photo-exif", methods=["POST"])
def photo_exif():
    photo = request.files.get("photo")

    if not photo or not photo.filename:
        return jsonify({
            "success": False,
            "message": "沒有收到照片。"
        }), 400

    if not allowed_file(photo.filename):
        return jsonify({
            "success": False,
            "message": "EXIF 讀取目前只支援 JPG／JPEG 照片。"
        }), 400

    safe_name = secure_filename(photo.filename)

    if not safe_name:
        safe_name = "photo.jpg"

    extension = safe_name.rsplit(".", 1)[1].lower()

    temp_filename = f"exif_{uuid4().hex}.{extension}"
    temp_path = UPLOAD_DIR / temp_filename

    try:
        photo.save(temp_path)

        camera_info = read_camera_info(temp_path) or {}
        exposure_params = build_exposure_params(camera_info)

        if not exposure_params:
            return jsonify({
                "success": True,
                "has_exif": False,
                "message": "這張照片沒有完整的 ISO、光圈或快門 EXIF 資訊。"
            })

        return jsonify({
            "success": True,
            "has_exif": True,
            "filename": temp_filename,
            "params": exposure_params,
            "camera": {
                "make": camera_info.get("Make"),
                "model": camera_info.get("Model"),
                "focal_length": camera_info.get("FocalLengthText"),
            }
        })

    except ValueError:
        return jsonify({
            "success": True,
            "has_exif": False,
            "message": "這張照片沒有可讀取的 EXIF 資訊。"
        })

    except Exception as exc:
        app.logger.exception("曝光模擬讀取 EXIF 失敗：%s", exc)

        return jsonify({
            "success": False,
            "message": "讀取照片 EXIF 時發生錯誤。"
        }), 500

    #finally:
        temp_path.unlink(missing_ok=True)

@app.route("/articles")
def articles():
    article_list, using_fallback = scrape_photography_articles(limit=9)

    return render_template(
        "articles.html",
        articles=article_list,
        using_fallback=using_fallback,
        sources=SOURCES,
    )

@app.route("/upload", methods=["GET", "POST"])
def upload():

    if request.method == "GET":
        return render_template("upload.html")

    # 每次有人上傳照片前，
    # 先清理超過 24 小時的暫存檔
    cleanup_expired_uploads()

    # 手機版提供「直接拍照」與「從相簿選擇」兩個入口；
    # photo 保留給舊版表單相容使用。
    camera_photo = request.files.get("camera_photo")
    gallery_photo = request.files.get("gallery_photo")
    legacy_photo = request.files.get("photo")
    if camera_photo and camera_photo.filename:
        photo = camera_photo
        photo_source = "camera"
    elif gallery_photo and gallery_photo.filename:
        photo = gallery_photo
        photo_source = "gallery"
    else:
        photo = legacy_photo
        photo_source = request.form.get("photo_source", "unknown").strip()
    scene = request.form.get("scene", "").strip()

    if not photo or not photo.filename:
        return render_template(
            "upload.html",
            error="請先選擇一張 JPG 照片。",
        ), 400

    if not allowed_file(photo.filename):
        return render_template(
            "upload.html",
            error="只支援 JPG／JPEG 照片。",
        ), 400

    base_recommendation = get_recommendation(scene)

    if not base_recommendation:
        return render_template(
            "upload.html",
            error=(
                "請選擇拍攝情境。"
                if not scene
                else "找不到所選情境的推薦資料。"
            ),
        ), 400

    safe_name = secure_filename(photo.filename)
    extension = safe_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid4().hex}.{extension}"
    file_path = UPLOAD_DIR / filename

    photo.save(file_path)

    # 先確認上傳的檔案確實是 JPEG，而不只看副檔名。
    try:
        with Image.open(file_path) as image:
            image_format = image.format
            image.verify()

    except (UnidentifiedImageError, OSError):
        file_path.unlink(missing_ok=True)

        return render_template(
            "upload.html",
            error="檔案不是有效的 JPG 照片。",
        ), 400

    if image_format != "JPEG":
        file_path.unlink(missing_ok=True)

        return render_template(
            "upload.html",
            error="照片內容不是 JPG／JPEG 格式，請重新選擇。",
        ), 400

    try:
        analysis_filename, _analysis_path = create_analysis_image(file_path)
    except OSError as exc:
        app.logger.warning("建立分析縮圖失敗：%s", exc)
        analysis_filename = filename

    # 修正二：沒有完整 EXIF 時，不阻止照片上傳
    try:
        camera_info = read_camera_info(file_path) or {}

    except ValueError as exc:
        app.logger.info("照片沒有完整 EXIF：%s", exc)
        camera_info = {}

    required_keys = [
        "ISOSpeedRatings",
        "FNumberText",
        "ExposureTimeText",
    ]

    has_exif = all(
        camera_info.get(key) not in (None, "", "未知", "N/A")
        for key in required_keys
    )

    if has_exif:
        recommendation = build_adaptive_recommendation(
            camera_info=camera_info,
            scene=scene,
            base_profile=base_recommendation,
    )
    else:
        recommendation = base_recommendation

    # 預設結果：供沒有 EXIF 的照片使用
    analysis = []
    scene_result = []
    exposure_diff = None
    meter_position = 50
    exposure_status = "unknown"
    exposure_message = (
        "照片沒有完整拍攝參數，已略過曝光比較；"
        "仍可按下按鈕使用 Gemini 分析照片畫面。"
    )
    if photo_source == "camera":
        exif_notice = (
            "手機直接拍照後，瀏覽器交給網站的 JPG 沒有包含完整的 ISO、"
            "光圈與快門 EXIF。這通常是手機或瀏覽器的隱私處理，系統無法從"
            "照片像素還原真實拍攝參數；你仍可分析畫面，或改從相簿選擇保留"
            "EXIF 的原始 JPG。"
        )
    else:
        exif_notice = (
            "這張照片沒有完整的 ISO、光圈與快門 EXIF，系統會略過參數比較；"
            "你仍可使用 Gemini 分析畫面，或改選保留 EXIF 的原始 JPG。"
        )

    # 修正三：有完整 EXIF 才進行參數與曝光比較
    if has_exif:
        try:
            analysis = compare_setting(
                camera_info,
                recommendation,
            )

            exposure_diff = max(
                -3,
                min(
                    3,
                    compare_exposure(
                        camera_info,
                        recommendation,
                    ),
                ),
            )

            meter_position = (exposure_diff + 3) / 6 * 100

            if exposure_diff < -1:
                exposure_status = "under"
                exposure_message = "曝光不足，建議增加曝光。"

            elif exposure_diff > 1:
                exposure_status = "over"
                exposure_message = "曝光偏亮，建議降低曝光。"

            else:
                exposure_status = "normal"
                exposure_message = "曝光接近推薦設定。"

        except Exception as exc:
            app.logger.warning("EXIF 參數分析失敗：%s", exc)

            analysis = []
            exposure_diff = None
            meter_position = 50
            exposure_status = "unknown"
            exposure_message = "拍攝參數分析失敗，請查看終端機紀錄。"

    # 修正四：寫死的智慧情境分析獨立執行
    # 這裡不會再把 scene_result 設回 None
    if has_exif:
        try:
            scene_result = scene_analysis(
                scene,
                camera_info,
                recommendation,
            ) or []

        except Exception as exc:
            app.logger.warning("智慧情境分析失敗：%s", exc)
            scene_result = []

    # 修正五：上傳照片時不自動呼叫 Gemini
    # Gemini 改由網頁按鈕呼叫 /api/ai-analysis
    ai_advice = None
    ai_error = None

    exposure_params = build_exposure_params(camera_info) if has_exif else None

    photo_analysis_context = {
        "scene": scene,
        "scene_name": recommendation.get("scene_name", scene),
        "has_exif": has_exif,
        "photo_source": photo_source,
        "analysis_image_url": url_for(
            "static",
            filename=f"uploads/{analysis_filename}",
        ),
        "exif_notice": exif_notice if not has_exif else None,
        "camera": {
            "iso": camera_info.get("ISOSpeedRatings", "未知"),
            "aperture": camera_info.get("FNumberText", "未知"),
            "shutter": camera_info.get("ExposureTimeText", "未知"),
            "focal_length": camera_info.get("FocalLengthText", "未知"),
        },

        "exposure_params": exposure_params,

        "adaptive_recommendation": {
        "iso": recommendation.get("iso"),
        "aperture": recommendation.get("aperture"),
        "shutter": recommendation.get("shutter"),
        "adaptive": recommendation.get("adaptive", False),
        "adaptive_reason": recommendation.get("adaptive_reason"),
        },

        "parameter_analysis": list(analysis),
        "scene_analysis": list(scene_result),
        "exposure_diff": (
            round(exposure_diff, 1)
            if exposure_diff is not None
            else None
        ),
        "ai_advice": None,
    }

    return render_template(
        "upload.html",
        filename=filename,
        analysis_filename=analysis_filename,
        camera_info=camera_info,
        recommend=recommendation,
        analysis=analysis,
        scene_result=scene_result,
        has_exif=has_exif,
        photo_source=photo_source,
        exif_notice=exif_notice,
        exposure_diff=(
            round(exposure_diff, 1)
            if exposure_diff is not None
            else None
        ),
        meter_position=meter_position,
        exposure_status=exposure_status,
        exposure_message=exposure_message,
        ai_advice=ai_advice,
        ai_error=ai_error,
        selected_scene=scene,
        photo_analysis_context=photo_analysis_context,
    )

@app.route("/api/ai-analysis", methods=["POST"])
def run_ai_analysis():
    data = request.get_json(silent=True) or {}

    filename = secure_filename(str(data.get("filename", "")))
    scene = str(data.get("scene", "")).strip()
    adaptive_recommendation = data.get("adaptive_recommendation")

    if not filename or not allowed_file(filename):
        return jsonify({"error": "照片檔名不正確。"}), 400

    file_path = UPLOAD_DIR / filename

    if not file_path.is_file():
        return jsonify({"error": "找不到照片，請重新上傳。"}), 404

    analysis_path = UPLOAD_DIR / f"{file_path.stem}-analysis.jpg"
    if not analysis_path.is_file():
        try:
            _analysis_name, analysis_path = create_analysis_image(file_path)
        except OSError as exc:
            app.logger.warning("建立 Gemini 分析縮圖失敗：%s", exc)
            analysis_path = file_path

    recommendation = get_recommendation(scene)

    if not recommendation:
        return jsonify({"error": "找不到所選情境的推薦資料。"}), 400

    recommendation = deepcopy(recommendation)

    if isinstance(adaptive_recommendation, dict):
        adaptive_iso = adaptive_recommendation.get("iso")
        adaptive_aperture = adaptive_recommendation.get("aperture")
        adaptive_shutter = adaptive_recommendation.get("shutter")

        if adaptive_iso is not None:
            recommendation["iso"] = adaptive_iso

        if adaptive_aperture:
            recommendation["aperture"] = str(adaptive_aperture)

        if adaptive_shutter:
            recommendation["shutter"] = str(adaptive_shutter)

        recommendation["adaptive"] = True


    
    try:
        try:
            camera_info = read_camera_info(file_path) or {}
        except Exception as exc :
            app.logger.info("照片沒有完整 EXIF：%s", exc)
            camera_info = {}

        required_parameter_keys = [
            "ISOSpeedRatings",
            "FNumberText",
            "ExposureTimeText",
        ]

        has_exif = all(
            camera_info.get(key) not in (None, "", "未知", "N/A")
            for key in required_parameter_keys
        )

        if has_exif:
            try:
                exposure_diff = max(
                    -3,
                    min(3, compare_exposure(camera_info, recommendation)),
                )
            except Exception:
                exposure_diff = None
        else:
            exposure_diff = None

        advice = generate_ai_advice(
            image_path=analysis_path,
            scene=recommendation.get("scene_name", scene),
            camera_info=camera_info,
            recommendation=recommendation,
            exposure_diff=(
                round(exposure_diff, 1)
                if exposure_diff is not None
                else None
            ),
        )

        return jsonify({"advice": advice})

    except Exception as exc:
        app.logger.warning("Gemini AI 分析失敗：%s", exc)

        return jsonify({
            "error": "AI 分析暫時無法使用，請稍後再試。"
        }), 503

@app.route("/api/delete-photo", methods=["POST"])
def delete_photo():
    data = request.get_json(silent=True) or {}

    filename = secure_filename(
        str(data.get("filename", ""))
    )

    if not filename:
        return jsonify({
            "error": "照片檔名不正確。"
        }), 400

    file_path = UPLOAD_DIR / filename

    analysis_path = (
        UPLOAD_DIR
        / f"{file_path.stem}-analysis.jpg"
    )

    deleted_files = []

    for path in (
        file_path,
        analysis_path,
    ):
        try:
            if path.is_file():
                path.unlink()
                deleted_files.append(path.name)

        except OSError as exc:
            app.logger.warning(
                "刪除照片失敗 %s：%s",
                path,
                exc,
            )

            return jsonify({
                "error": "刪除照片時發生錯誤。"
            }), 500

    return jsonify({
        "success": True,
        "deleted": deleted_files,
    })


@app.route("/api/test")
def test():
    return jsonify({"name": "Hsun", "camera": "Canon"})


@app.route("/api/recommend/<scene>")
def recommend_api(scene):
    result = get_recommendation(scene)
    if not result:
        return jsonify({"error": "找不到此情境"}), 404
    return jsonify(result)


@app.route("/api/scenes")
def scenes_api():
    """供前端確認情境清單，內容仍來自 recommendations.py。"""
    return jsonify({"scenes": list_scene_choices()})


def build_recommendation_fallback(profile, analysis_context):
    message = (
        f"{profile['scene_name']}以 {profile['shutter']} 控制動態、"
        f"{profile['aperture']} 控制景深，再用 ISO {profile['iso']} 補足亮度。"
        f"{profile['tips']}"
    )
    analysis_items = sanitize_context_items(analysis_context)
    if analysis_items:
        message = f"照片分析指出：{str(analysis_items[0])}。{message}"
    return message[:240]


def sanitize_context_items(analysis_context):
    if not isinstance(analysis_context, dict):
        return []
    raw_items = []
    for field in ("parameter_analysis", "scene_analysis"):
        values = analysis_context.get(field, [])
        if isinstance(values, list):
            raw_items.extend(values)
    if analysis_context.get("ai_advice"):
        raw_items.append(f"AI 照片分析：{analysis_context['ai_advice']}")
    return [str(item)[:300] for item in raw_items[:5]]


def build_exposure_fallback(profile, evaluation):
    relative_ev = evaluation["relative_ev"]
    if relative_ev < -1:
        exposure_text = f"目前比情境基準少約 {abs(relative_ev):.1f} EV，畫面可能偏暗。"
    elif relative_ev > 1:
        exposure_text = f"目前比情境基準多約 {relative_ev:.1f} EV，畫面可能偏亮。"
    else:
        exposure_text = "目前曝光量接近情境基準。"

    checks = evaluation["parameter_checks"]
    labels = {"iso": "ISO", "aperture": "光圈", "shutter": "快門"}
    unsuitable = [labels[key] for key, valid in checks.items() if not valid]
    if unsuitable:
        suitability_text = f"但{'、'.join(unsuitable)}不在此情境建議範圍，仍可能影響畫質或拍攝效果。"
    else:
        suitability_text = "ISO、光圈與快門也都在建議範圍內。"
    return f"{exposure_text}{suitability_text}{profile['tips']}"


@app.route("/api/ai-explanation", methods=["POST"])
def ai_explanation_api():
    """讓 AI 解釋程式結論；AI 失效時回傳內建自然語言說明。"""
    data = request.get_json(silent=True) or {}
    explanation_type = str(data.get("type", "")).strip()
    scene = str(data.get("scene", "")).strip()
    base_profile = get_recommendation(scene)

    if explanation_type not in {"recommendation", "exposure"}:
        return jsonify({"error": "解釋類型不正確。"}), 400
    if not base_profile:
        return jsonify({"error": "找不到所選情境。"}), 404
    profile = deepcopy(base_profile)

    analysis_context = data.get("analysis_context")
    if not isinstance(analysis_context, dict):
        analysis_context = {}

    # -----------------------------
    # 接收 Adaptive Recommendation
    # -----------------------------

    adaptive_recommendation = data.get(
        "adaptive_recommendation"
    )

    if isinstance(
        adaptive_recommendation,
        dict
    ):
        adaptive_iso = (
            adaptive_recommendation.get("iso")
        )

        adaptive_aperture = (
            adaptive_recommendation.get("aperture")
        )

        adaptive_shutter = (
            adaptive_recommendation.get("shutter")
        )

        if adaptive_iso is not None:
            profile["iso"] = adaptive_iso

        if adaptive_aperture:
            profile["aperture"] = str(
            adaptive_aperture
        )

        if adaptive_shutter:
            profile["shutter"] = str(
            adaptive_shutter
        )

        profile["adaptive"] = True    

    if explanation_type == "recommendation":
        fallback = build_recommendation_fallback(profile, analysis_context)
        facts = (
            f"代表設定：ISO {profile['iso']}、{profile['aperture']}、{profile['shutter']}；"
            f"白平衡 {profile['white_balance']}；對焦 {profile['focus_mode']}；"
            f"曝光補償 {profile['exposure_compensation']}；技巧：{profile['tips']}。"
        )
        context_items = sanitize_context_items(analysis_context)
        if context_items:
            facts += " 照片分析摘要：" + "；".join(map(str, context_items))
    else:
        try:
            evaluation = evaluate_exposure(
                profile,
                data.get("iso"),
                data.get("aperture"),
                data.get("shutter"),
            )
        except (TypeError, ValueError, ZeroDivisionError):
            return jsonify({"error": "曝光參數格式不正確。"}), 400

        fallback = build_exposure_fallback(profile, evaluation)
        facts = (
            f"目前 ISO {data.get('iso')}、f/{data.get('aperture')}、快門 {data.get('shutter')}；"
            f"目前 EV {evaluation['current_ev']}；基準 EV {evaluation['target_ev']}；"
            f"相對曝光差 {evaluation['relative_ev']} EV；"
            f"曝光狀態 {evaluation['exposure_status']}；"
            f"參數範圍檢查 {evaluation['parameter_checks']}；技巧：{profile['tips']}。"
        )

    try:
        explanation = generate_ai_explanation(
            explanation_type=explanation_type,
            scene=profile["scene_name"],
            facts=facts,
        )
        return jsonify({"explanation": explanation, "source": "gemini"})
    except Exception as exc:
        app.logger.info("Gemini 自然語言解釋暫時無法使用：%s", exc)
        return jsonify({"explanation": fallback, "source": "built-in"})


@app.errorhandler(413)
def file_too_large(_error):
    return render_template("upload.html", error="照片超過 10 MB，請縮小後再上傳。"), 413



@app.route("/my-photos")
def my_photos():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = get_db()

    photos = db.execute(
        """
        SELECT
            *,
            datetime(created_at, '+8 hours') AS created_at_local
        FROM photos
        WHERE user_id = ?
          AND saved = 1
        ORDER BY created_at DESC
        """,
        (session["user_id"],),
    ).fetchall()

    db.close()

    return render_template(
        "my_photos.html",
        photos=photos,
    )

@app.route("/my-photos/add", methods=["POST"])
def add_my_photo():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    photo = request.files.get("photo")

    if not photo or not photo.filename:
        return redirect(url_for("my_photos"))

    safe_name = secure_filename(photo.filename)

    if not safe_name.lower().endswith((".jpg", ".jpeg")):
        return redirect(url_for("my_photos"))

    filename = f"{uuid4().hex}_{safe_name}"
    file_path = UPLOAD_DIR / filename

    photo.save(file_path)

    db = get_db()

    db.execute(
        """
        INSERT INTO photos (
            user_id,
            filename,
            retention_mode,
            saved
        )
        VALUES (?, ?, 'keep', 1)
        """,
        (
            session["user_id"],
            filename,
        ),
    )

    db.commit()
    db.close()

    return redirect(url_for("my_photos"))

@app.route("/my-photos/delete/<int:photo_id>", methods=["POST"])
def delete_my_photo(photo_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = get_db()

    photo = db.execute(
        """
        SELECT *
        FROM photos
        WHERE id = ?
          AND user_id = ?
        """,
        (
            photo_id,
            session["user_id"],
        ),
    ).fetchone()

    if not photo:
        db.close()
        return redirect(url_for("my_photos"))

    filename = photo["filename"]

    file_path = UPLOAD_DIR / filename
    analysis_path = (
        UPLOAD_DIR /
        f"{Path(filename).stem}-analysis.jpg"
    )

    for path in (file_path, analysis_path):
        try:
            if path.is_file():
                path.unlink()
        except OSError as exc:
            app.logger.warning(
                "刪除我的照片失敗 %s：%s",
                path,
                exc,
            )

    db.execute(
        """
        DELETE FROM photos
        WHERE id = ?
          AND user_id = ?
        """,
        (
            photo_id,
            session["user_id"],
        ),
    )

    db.commit()
    db.close()

    return redirect(url_for("my_photos"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password:
        return render_template(
            "register.html",
            error="請完整填寫帳號、Email 與密碼。"
        )

    db = get_db()

    try:
        db.execute(
            """
            INSERT INTO users (
                username,
                email,
                password_hash
            )
            VALUES (?, ?, ?)
            """,
            (
                username,
                email,
                generate_password_hash(password),
            ),
        )

        db.commit()

    except Exception:
        db.close()

        return render_template(
            "register.html",
            error="帳號或 Email 已經被使用。"
        )

    db.close()

    return redirect(url_for("login"))



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    db = get_db()

    user = db.execute(
    """
    SELECT *
    FROM users
    WHERE username = ?
       OR email = ?
    """,
    (
        username,
        username,
    ),
).fetchone()

    db.close()

    if not user or not check_password_hash(
        user["password_hash"],
        password,
    ):
        return render_template(
            "login.html",
            error="帳號或密碼不正確。"
        )

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/api/save-photo", methods=["POST"])
def save_photo():
    if not session.get("user_id"):
        return jsonify({"error": "請先登入。"}), 401

    data = request.get_json(silent=True) or {}
    filename = secure_filename(str(data.get("filename", "")))

    if not filename:
        return jsonify({"error": "照片檔名不正確。"}), 400

    file_path = UPLOAD_DIR / filename

    if not file_path.is_file():
        return jsonify({"error": "找不到照片檔案。"}), 404

    db = get_db()

    existing = db.execute(
        """
        SELECT id
        FROM photos
        WHERE user_id = ?
          AND filename = ?
        """,
        (
            session["user_id"],
            filename,
        ),
    ).fetchone()

    if existing:
        db.close()
        return jsonify({
            "success": True,
            "message": "這張照片已經保存。"
        })

    db.execute(
        """
        INSERT INTO photos (
            user_id,
            filename,
            retention_mode,
            saved
        )
        VALUES (?, ?, 'keep', 1)
        """,
        (
            session["user_id"],
            filename,
        ),
    )

    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "message": "照片已保存到我的照片。"
    })

@app.route("/api/save-simulation", methods=["POST"])
def save_simulation():
    if not session.get("user_id"):
        return jsonify({"error": "請先登入。"}), 401

    data = request.get_json(silent=True) or {}

    filename = secure_filename(
        str(data.get("filename", ""))
    )

    app.logger.info(
    "save_simulation 收到 filename=%s",
    filename,
    )

    simulated_image = data.get("simulated_image", "")

    if not filename:
        return jsonify({"error": "原始照片檔名不正確。"}), 400

    if not simulated_image:
        return jsonify({"error": "沒有收到模擬照片資料。"}), 400

    original_path = UPLOAD_DIR / filename

    if not original_path.is_file():
        return jsonify({"error": "找不到原始照片。"}), 404

    try:
        import base64

        # 前端會傳：
        # data:image/jpeg;base64,xxxxxx
        if "," in simulated_image:
            simulated_image = simulated_image.split(",", 1)[1]

        image_bytes = base64.b64decode(simulated_image)

        simulated_filename = (
            f"{Path(filename).stem}_simulated.jpg"
        )

        simulated_path = (
            UPLOAD_DIR / simulated_filename
        )

        with open(simulated_path, "wb") as file:
            file.write(image_bytes)

        app.logger.info(
            "模擬照片已寫入：%s",
            simulated_path,
        )       

    except Exception as exc:
        app.logger.exception(
            "儲存模擬照片失敗：%s",
            exc,
        )

        return jsonify({
            "error": "模擬照片儲存失敗。"
        }), 500

    db = get_db()

    photo = db.execute(
        """
        SELECT id
        FROM photos
        WHERE user_id = ?
          AND filename = ?
        """,
        (
            session["user_id"],
            filename,
        ),
    ).fetchone()

    if photo:
        db.execute(
            """
            UPDATE photos
            SET simulated_filename = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                simulated_filename,
                photo["id"],
                session["user_id"],
            ),
        )

    else:
        db.execute(
            """
            INSERT INTO photos (
                user_id,
                filename,
                simulated_filename,
                retention_mode,
                saved
            )
            VALUES (?, ?, ?, 'keep', 1)
            """,
            (
                session["user_id"],
                filename,
                simulated_filename,
            ),
        )
    app.logger.info(
        "準備寫入 simulated_filename=%s",
        simulated_filename,
    )
    
    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "simulated_filename": simulated_filename,
        "message": "曝光模擬結果已保存。"
    })

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
