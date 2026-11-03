// Exposure Simulator V6：所有情境資料只從 /api/recommend/<scene> 取得。
document.addEventListener("DOMContentLoaded", () => {
    const sceneSelect = document.getElementById("scene");
    const isoSelect = document.getElementById("iso");
    const apertureSelect = document.getElementById("aperture");
    const shutterSelect = document.getElementById("shutter");
    const restorePhotoButton = document.getElementById("restore-photo");
    const applyRecommendationButton = document.getElementById("apply-recommendation");
    const aiButton = document.getElementById("exposure-ai-button");
    const aiResult = document.getElementById("exposure-ai-result");
    const simulationPhotoInput = document.getElementById("simulation-photo");
    const clearSimulationPhotoButton = document.getElementById("clear-simulation-photo");
    const simulationPhotoName = document.getElementById("simulation-photo-name");
    const simulationPhotoError = document.getElementById("simulation-photo-error");
    const simulationEmpty = document.getElementById("simulation-empty");
    const simulationComparison = document.getElementById("simulation-comparison");
    const simulationOriginal = document.getElementById("simulation-original");
    const simulationResult = document.getElementById("simulation-result");
    const simulationEV = document.getElementById("simulation-ev");
    const saveSimulationButton =
        document.getElementById("save-simulation-button");

    const saveSimulationResult =
        document.getElementById("save-simulation-result");
    const query = new URLSearchParams(window.location.search);
    let currentProfile = null;
    let originalPhotoParams = null;
    let simulationObjectUrl = null;

    const ISO_VALUES = [64, 80, 100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000, 12800, 25600, 51200];
    const APERTURE_VALUES = [1, 1.2, 1.4, 1.6, 1.8, 2, 2.2, 2.5, 2.8, 3.2, 3.5, 4, 4.5, 5, 5.6, 6.3, 7.1, 8, 9, 10, 11, 13, 14, 16, 18, 20, 22];
    const SHUTTER_VALUES = ["30/1", "15/1", "8/1", "4/1", "2/1", "1/1", "1/2", "1/3", "1/4", "1/5", "1/6", "1/8", "1/10", "1/13", "1/15", "1/20", "1/25", "1/30", "1/40", "1/50", "1/60", "1/80", "1/100", "1/125", "1/160", "1/200", "1/250", "1/320", "1/400", "1/500", "1/640", "1/800", "1/1000", "1/1250", "1/1600", "1/2000", "1/2500", "1/3200", "1/4000", "1/5000", "1/6400", "1/8000"];

    function escapeHTML(value) {
        const element = document.createElement("div");
        element.textContent = value ?? "";
        return element.innerHTML;
    }

    function setIconText(element, iconClass, text) {
        const icon = document.createElement("i");
        icon.className = `bi ${iconClass}`;
        icon.setAttribute("aria-hidden", "true");
        element.replaceChildren(icon, document.createTextNode(` ${text}`));
    }

    function showSimulationError(message) {
        setIconText(simulationPhotoError, "bi-exclamation-triangle", message);
        simulationPhotoError.hidden = false;
    }

    function updatePhotoSimulation(relativeEV = null) {
        if (!simulationResult.hasAttribute("src")) return;
        if (!Number.isFinite(relativeEV)) {
            simulationResult.style.filter = "brightness(1)";
            simulationEV.className = "simulation-ev";
            simulationEV.textContent = "等待選擇情境";
            return;
        }

        const visualEV = Math.max(-3, Math.min(3, relativeEV));
        const brightness = Math.max(0.25, Math.min(3, 2 ** visualEV));
        simulationResult.style.filter = `brightness(${brightness.toFixed(3)})`;
        simulationEV.className = `simulation-ev ${relativeEV < -0.3 ? "is-darker" : relativeEV > 0.3 ? "is-brighter" : "is-balanced"}`;
        simulationEV.textContent = `${relativeEV > 0 ? "+" : ""}${relativeEV.toFixed(1)} EV`;
    }

    function showSimulationPhoto(url, name) {
        simulationPhotoError.hidden = true;
        simulationOriginal.src = url;
        simulationResult.src = url;
        simulationPhotoName.textContent = name || "已載入照片";
        simulationEmpty.hidden = true;
        simulationComparison.hidden = false;
        clearSimulationPhotoButton.hidden = false;
        updatePhotoSimulation();
        if (currentProfile) calculateEV();
    }

    async function readPhotoExif(file) {
        const formData = new FormData();
        formData.append("photo", file);

        try {
            const response = await fetch("/api/photo-exif", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                showSimulationError(
                    data.message || "無法讀取照片 EXIF。"
                );
                return null;
            }

            if (!data.has_exif || !data.params) {
                showSimulationError(
                    data.message || "照片沒有完整 EXIF 資訊。"
                );
                return null;
            }

            return data;

        } catch (error) {
            console.error("EXIF read error:", error);

            showSimulationError(
                "讀取照片 EXIF 失敗，請重新選擇照片。"
            );

            return null;
        }
    }

    function clearSimulationPhoto() {
        if (simulationObjectUrl) {
            URL.revokeObjectURL(simulationObjectUrl);
            simulationObjectUrl = null;
        }
        simulationPhotoInput.value = "";
        simulationOriginal.removeAttribute("src");
        simulationResult.removeAttribute("src");
        simulationResult.style.filter = "brightness(1)";
        simulationPhotoName.textContent = "";
        simulationPhotoError.hidden = true;
        simulationEmpty.hidden = false;
        simulationComparison.hidden = true;
        clearSimulationPhotoButton.hidden = true;
    }

    function parseShutter(value) {
        const text = String(value).trim().toLowerCase().replace("秒", "").trim();
        if (text.endsWith("s")) {
            return Number(text.slice(0, -1));
        }
        const [numerator, denominator = "1"] = text.split("/");
        return Number(numerator) / Number(denominator);
    }

    function formatShutter(value) {
        const seconds = parseShutter(value);
        if (seconds >= 1) {
            return `${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)} 秒`;
        }
        return String(value);
    }

    function populateControls() {
        ISO_VALUES.forEach((value) => {
            const suffix = value < 125 || value > 12800 ? "（擴展）" : value === 125 ? "（標準最低）" : value === 12800 ? "（標準最高）" : "";
            isoSelect.add(new Option(`${value}${suffix}`, String(value)));
        });
        APERTURE_VALUES.forEach((value) => apertureSelect.add(new Option(`f/${value}`, String(value))));
        SHUTTER_VALUES.forEach((value) => shutterSelect.add(new Option(formatShutter(value), value)));
    }

    function setControlsEnabled(enabled) {
        [isoSelect, apertureSelect, shutterSelect].forEach((select) => {
            select.disabled = !enabled;
        });
        restorePhotoButton.disabled = !enabled || !originalPhotoParams;
        applyRecommendationButton.disabled = !enabled;
        aiButton.disabled = !enabled;
    }

    function showNoSceneState() {
        currentProfile = null;
        setControlsEnabled(false);
        document.getElementById("ev-value").textContent = "--";
        document.getElementById("meter-message").className = "fw-bold mt-3 mb-0";
        document.getElementById("meter-message").textContent = "請先選擇拍攝情境";
        document.getElementById("parameter-suitability").textContent = "請先選擇拍攝情境。";
        document.getElementById("recommend-scene").replaceChildren();
        document.getElementById("exposure-advice").textContent = "請先選擇拍攝情境。";
        ["depth-info", "blur-info", "motion-info", "noise-info"].forEach((id) => {
            document.getElementById(id).textContent = "--";
        });
        aiResult.replaceChildren();
        updatePhotoSimulation();
    }

    function selectClosest(select, wanted, parser = Number) {
        const target = parser(wanted);
        if (!Number.isFinite(target)) {
            return false;
        }
        let bestIndex = 0;
        let bestDistance = Number.POSITIVE_INFINITY;
        Array.from(select.options).forEach((option, index) => {
            const distance = Math.abs(parser(option.value) - target);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestIndex = index;
            }
        });
        select.selectedIndex = bestIndex;
        return true;
    }

    function selectOriginal(select, wanted, parser, label) {
        const target = parser(wanted);
        if (!Number.isFinite(target) || target <= 0) {
            return false;
        }
        const existingIndex = Array.from(select.options).findIndex((option) => (
            Math.abs(parser(option.value) - target) < 1e-9
        ));
        if (existingIndex >= 0) {
            select.selectedIndex = existingIndex;
            return true;
        }
        const option = new Option(`${label(wanted)}（照片原始）`, String(wanted));
        select.add(option);
        select.value = String(wanted);
        return true;
    }

    function applyPhotoParams(params) {
        selectOriginal(isoSelect, params.iso, Number, (value) => String(value));
        selectOriginal(apertureSelect, params.aperture, Number, (value) => `f/${value}`);
        selectOriginal(shutterSelect, params.shutter, parseShutter, formatShutter);
    }

    function applyReference(profile) {
        const reference = profile.exposure.reference;
        selectClosest(isoSelect, reference.iso);
        selectClosest(apertureSelect, reference.aperture);
        selectClosest(shutterSelect, reference.shutter, parseShutter);
    }

    function calculateEVValue(iso, aperture, shutterSeconds) {
        return Math.log2((aperture * aperture) / shutterSeconds) - Math.log2(iso / 100);
    }

    function within(value, bounds) {
        return value >= bounds[0] - Number.EPSILON && value <= bounds[1] + Number.EPSILON;
    }

    function parameterChecks(profile, iso, aperture, shutterSeconds) {
        const ranges = profile.exposure.ranges;
        return {
            iso: within(iso, ranges.iso),
            aperture: within(aperture, ranges.aperture),
            shutter: within(shutterSeconds, ranges.shutter_seconds),
        };
    }

    function updateMeter(relativeEV) {
        const clamped = Math.max(-3, Math.min(3, relativeEV));
        document.getElementById("meter-arrow").style.left = `${((clamped + 3) / 6) * 100}%`;
        const message = document.getElementById("meter-message");
        if (relativeEV < -1) {
            message.className = "text-info fw-bold mt-3 mb-0";
            setIconText(message, "bi-moon", `相較情境基準偏暗 ${Math.abs(relativeEV).toFixed(1)} EV`);
        } else if (relativeEV > 1) {
            message.className = "text-warning fw-bold mt-3 mb-0";
            setIconText(message, "bi-sun", `相較情境基準偏亮 ${relativeEV.toFixed(1)} EV`);
        } else {
            message.className = "text-success fw-bold mt-3 mb-0";
            setIconText(message, "bi-check-circle", "曝光量接近情境基準");
        }
    }

    function updateEffects(iso, aperture, shutterSeconds) {
        let depthText = "";
        let blurText = "";
        let motionText = "";
        let noiseText = "";

        // 光圈效果：只表示趨勢，不宣稱是真實景深
        if (aperture <= 2.8) {
            depthText = "偏淺 ↓";
            blurText = "增加 ↑";
        } else if (aperture <= 5.6) {
            depthText = "中等";
            blurText = "中等";
        } else {
            depthText = "偏深 ↑";
            blurText = "減少 ↓";
        }

        // 快門效果
        if (shutterSeconds <= 1 / 500) {
            motionText = "凝結能力高 ↑";
        } else if (shutterSeconds <= 1 / 125) {
            motionText = "凝結能力中等";
        } else if (shutterSeconds <= 1 / 60) {
            motionText = "需注意手震";
        } else {
            motionText = "模糊風險高 ↑";
        }

        // ISO 效果
        if (iso <= 400) {
            noiseText = "噪點風險低";
        } else if (iso <= 1600) {
            noiseText = "噪點風險中等";
        } else if (iso <= 3200) {
            noiseText = "噪點可能增加";
        } else {
            noiseText = "噪點風險較高";
        }

        document.getElementById("depth-info").textContent = depthText;
        document.getElementById("blur-info").textContent = blurText;
        document.getElementById("motion-info").textContent = motionText;
        document.getElementById("noise-info").textContent = noiseText;
    }

    function renderSuitability(checks) {
        const labels = { iso: "ISO", aperture: "光圈", shutter: "快門" };
        const items = Object.entries(checks).map(([key, valid]) => `
            <li class="${valid ? "text-success" : "text-warning"}">
                <i class="bi ${valid ? "bi-check-circle" : "bi-exclamation-triangle"}" aria-hidden="true"></i>
                ${labels[key]}${valid ? "在建議範圍內" : "不在此情境建議範圍"}
            </li>
        `).join("");
        const allValid = Object.values(checks).every(Boolean);
        document.getElementById("parameter-suitability").innerHTML = `
            <p class="fw-bold ${allValid ? "text-success" : "text-warning"}">
                ${allValid ? "這組參數適合目前情境。" : "曝光可能接近，但部分參數不適合目前情境。"}
            </p>
            <ul class="mb-0">${items}</ul>
        `;
    }

    function nextAllowedSetting(profile, direction) {
        const priorities = profile.exposure.priorities[direction];
        const ranges = profile.exposure.ranges;
        const controls = {
            iso: { select: isoSelect, parser: Number, bounds: ranges.iso, brighten: 1, label: "ISO" },
            aperture: { select: apertureSelect, parser: Number, bounds: ranges.aperture, brighten: -1, label: "光圈" },
            shutter: { select: shutterSelect, parser: parseShutter, bounds: ranges.shutter_seconds, brighten: -1, label: "快門" },
        };
        for (const key of priorities) {
            const config = controls[key];
            const step = direction === "brighten" ? config.brighten : -config.brighten;
            for (let index = config.select.selectedIndex + step; index >= 0 && index < config.select.options.length; index += step) {
                const option = config.select.options[index];
                if (within(config.parser(option.value), config.bounds)) {
                    return {
                        label: config.label,
                        current: config.select.options[config.select.selectedIndex].text,
                        next: option.text,
                    };
                }
            }
        }
        return null;
    }

    function formatRange(type, bounds) {
        if (type === "iso") return bounds[0] === bounds[1] ? `${bounds[0]}` : `${bounds[0]}～${bounds[1]}`;
        if (type === "aperture") return bounds[0] === bounds[1] ? `f/${bounds[0]}` : `f/${bounds[0]}～f/${bounds[1]}`;
        return `${formatShutter(secondsToShutter(bounds[0]))}～${formatShutter(secondsToShutter(bounds[1]))}`;
    }

    function secondsToShutter(seconds) {
        if (seconds >= 1) return `${seconds}/1`;
        return `1/${Math.round(1 / seconds)}`;
    }

    function renderAdvice(profile, currentEV, relativeEV) {
        const ranges = profile.exposure.ranges;
        const direction = relativeEV < -1 ? "brighten" : relativeEV > 1 ? "darken" : null;
        const next = direction ? nextAllowedSetting(profile, direction) : null;
        let smartAdvice = "<p class='text-success mb-0'>目前曝光量不需要調整；仍請確認上方參數適用性。</p>";
        if (next) {
            smartAdvice = `<p class="mb-0"><strong>建議優先調整 ${next.label}：</strong>${next.current} → <span class="text-success fw-bold">${next.next}</span></p>`;
        } else if (direction) {
            smartAdvice = "<p class='text-warning mb-0'>可調參數已達此情境推薦範圍，請改善現場光線或依需求取捨。</p>";
        }
        const reference = profile.exposure.reference;
        document.getElementById("exposure-advice").innerHTML = `
            <h5><i class="bi ${escapeHTML(profile.icon)}" aria-hidden="true"></i> ${escapeHTML(profile.scene_name)}</h5>
            <p><strong>目前 EV：</strong>${currentEV.toFixed(1)}　<strong>基準 EV：</strong>${profile.exposure.target_ev.toFixed(1)}　<strong>相對差：</strong>${relativeEV > 0 ? "+" : ""}${relativeEV.toFixed(1)} EV</p>
            <p class="small text-secondary">正數代表目前曝光量較基準多，負數代表較少；這是相對情境基準，不是現場測光。</p>
            <hr>
            <h5>完整基準組合</h5>
            <p>ISO ${reference.iso}、f/${reference.aperture}、${formatShutter(reference.shutter)}</p>
            <h5>建議範圍</h5>
            <p>ISO ${formatRange("iso", ranges.iso)}；光圈 ${formatRange("aperture", ranges.aperture)}；快門 ${formatRange("shutter", ranges.shutter_seconds)}</p>
            <h5>其他設定</h5>
            <p>底片模擬：${escapeHTML(profile.film_simulation)}／白平衡：${escapeHTML(profile.white_balance)}／對焦：${escapeHTML(profile.focus_mode)}／鏡頭：${escapeHTML(profile.lens)}</p>
            <p><strong>曝光補償：</strong>${escapeHTML(profile.exposure_compensation)} <span class="small text-secondary">（目前模擬以 M 模式曝光三角為主，補償值僅提示。）</span></p>
            <div class="alert alert-warning"><i class="bi bi-lightbulb" aria-hidden="true"></i> ${escapeHTML(profile.tips)}</div>
            <h5>智慧調整</h5>${smartAdvice}
        `;
        document.getElementById("recommend-scene").innerHTML = (profile.suitable || [])
            .map((item) => `<span class="context-chip">${escapeHTML(item)}</span>`).join("");
    }

    function buildAdaptiveParams(profile, originalParams) {
        if (!profile || !originalParams) {
            return null;
        }

        const originalIso = Number(originalParams.iso);
        const originalAperture = Number(originalParams.aperture);
        const originalShutter =
            parseShutter(originalParams.shutter);

        if (
            !originalIso ||
            !originalAperture ||
            !originalShutter
        ) {
            return null;
        }

        const reference =
            profile.exposure.reference;

        const recommendedShutter =
            Number(reference.shutter_seconds);

        // 第一版：
        // 保留照片原本光圈
        const recommendedAperture =
            originalAperture;

        // 原照片 EV
        const originalEV =
            calculateEVValue(
                originalIso,
                originalAperture,
                originalShutter
            );

        /*
         * 已知：
         * EV = log2(N² / t) - log2(ISO / 100)
         *
         * 反推維持原曝光所需要的 ISO
         */
        const requiredIso =
            100 *
            (recommendedAperture * recommendedAperture) /
            recommendedShutter /
            (2 ** originalEV);

        // 找到選單中最接近的 ISO
        const recommendedIso =
            ISO_VALUES.reduce((closest, value) => {
                return Math.abs(value - requiredIso)
                    < Math.abs(closest - requiredIso)
                    ? value
                    : closest;
            });

        return {
            iso: String(recommendedIso),
            aperture: String(recommendedAperture),
            shutter: String(reference.shutter)
        };
    }

    function calculateEV() {
        if (!currentProfile) return;
        const iso = Number(isoSelect.value);
        const aperture = Number(apertureSelect.value);
        const shutterSeconds = parseShutter(shutterSelect.value);
        const currentEV = calculateEVValue(iso, aperture, shutterSeconds);
        let relativeEV;
        // 有照片 EXIF：
        // 使用照片原始曝光作為模擬基準
        if (originalPhotoParams) {

            const originalIso =
                Number(originalPhotoParams.iso);

            const originalAperture =
                Number(originalPhotoParams.aperture);

            const originalShutter =
                parseShutter(
                    originalPhotoParams.shutter
                );

            const originalEV =
                calculateEVValue(
                    originalIso,
                    originalAperture,
                    originalShutter
                );

            relativeEV =
                originalEV - currentEV;

            console.log(
                "照片原始 EV：",
                originalEV.toFixed(2)
            );

            console.log(
                "目前模擬 EV：",
                currentEV.toFixed(2)
            );

            console.log(
                "相對曝光差：",
                relativeEV.toFixed(2)
            );

        } else {

            // 沒有照片時：
            // 繼續使用原本情境 target EV
            relativeEV =
                currentProfile.exposure.target_ev
                - currentEV;
        }

        document.getElementById("ev-value").textContent = currentEV.toFixed(1);
        updateMeter(relativeEV);
        updateEffects(iso, aperture, shutterSeconds);
        renderSuitability(parameterChecks(currentProfile, iso, aperture, shutterSeconds));
        renderAdvice(currentProfile, currentEV, relativeEV);
        updatePhotoSimulation(relativeEV);
        aiResult.replaceChildren();
    }

    async function loadScene(scene, { initialParams = null, preserveCurrent = false } = {}) {
        if (!scene) {
            showNoSceneState();
            return;
        }
        setControlsEnabled(false);
        document.getElementById("exposure-advice").textContent = "正在讀取共用情境參數…";
        try {
            const response = await fetch(`/api/recommend/${encodeURIComponent(scene)}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "無法讀取情境設定。");
            currentProfile = data;
            if (initialParams) {
                applyPhotoParams(initialParams);
            } else if (!preserveCurrent) {
                applyReference(data);
            }
            setControlsEnabled(true);
            calculateEV();
        } catch (error) {
            currentProfile = null;
            setControlsEnabled(false);
            document.getElementById("exposure-advice").innerHTML = `<div class="alert alert-danger">${escapeHTML(error.message)}</div>`;
        }
    }

    async function requestAiExplanation() {
        if (!currentProfile) return;
        aiButton.disabled = true;
        setIconText(aiButton, "bi-hourglass-split", "正在整理說明…");
        aiResult.className = "analysis-status mt-3";
        aiResult.textContent = "正在解釋目前曝光與情境參數…";
        try {
            const response = await fetch("/api/ai-explanation", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    type: "exposure",
                    scene: currentProfile.scene_key,
                    iso: isoSelect.value,
                    aperture: apertureSelect.value,
                    shutter: shutterSelect.value,
                }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "無法產生解釋。");
            aiResult.className = "alert alert-info mt-3";
            aiResult.textContent = data.explanation;
            setIconText(
                aiButton,
                "bi-arrow-clockwise",
                data.source === "gemini" ? "重新產生 AI 解釋" : "重新產生解釋",
            );
        } catch (error) {
            aiResult.className = "alert alert-warning mt-3";
            setIconText(aiResult, "bi-exclamation-triangle", error.message);
            setIconText(aiButton, "bi-arrow-clockwise", "再試一次");
        } finally {
            aiButton.disabled = false;
        }
    }

    populateControls();
    showNoSceneState();
    const requestedScene = query.get("scene") || "";
    const hasRequestedScene = requestedScene
        && sceneSelect.querySelector(`option[value="${CSS.escape(requestedScene)}"]`);
    if (hasRequestedScene) {
        sceneSelect.value = requestedScene;
    }
    const transferred = query.has("iso") && query.has("aperture") && query.has("shutter")
        ? { iso: query.get("iso"), aperture: query.get("aperture"), shutter: query.get("shutter") }
        : null;
    const source = query.get("source");
    const parameterSource = query.get("parameter_source");
    if (source === "analysis" && parameterSource === "photo" && transferred) {
        originalPhotoParams = { ...transferred };
        restorePhotoButton.hidden = false;
    }
    if (source) {
        const banner = document.getElementById("flow-source");
        const bannerText = originalPhotoParams
            ? "已帶入照片原始 EXIF 參數；目前情境推薦只作為比較標準。"
            : source === "analysis"
                ? "照片沒有完整 EXIF，目前已帶入此情境的推薦參數。"
                : "已從攝影建議帶入此情境的推薦參數。";
        setIconText(banner, source === "analysis" && !originalPhotoParams ? "bi-info-circle" : "bi-check-circle", bannerText);
        banner.hidden = false;
    }

    sceneSelect.addEventListener("change", () => {
        if (!sceneSelect.value) {
            showNoSceneState();
            return;
        }
        loadScene(sceneSelect.value, { preserveCurrent: Boolean(currentProfile) });
    });
    [isoSelect, apertureSelect, shutterSelect].forEach((select) => select.addEventListener("change", calculateEV));

    simulationPhotoInput.addEventListener("change", async () => {
        const file = simulationPhotoInput.files?.[0];

        if (!file) return;

        const supportedTypes = new Set([
            "image/jpeg",
            "image/png",
            "image/webp"
        ]);

        if (!supportedTypes.has(file.type)) {
            clearSimulationPhoto();

            showSimulationError(
                "請選擇 JPG、PNG 或 WebP 圖片。"
            );

            return;
        }

        // 先顯示照片
        if (simulationObjectUrl) {
            URL.revokeObjectURL(simulationObjectUrl);
        }

        simulationObjectUrl = URL.createObjectURL(file);

        showSimulationPhoto(
            simulationObjectUrl,
            file.name
        );

        // PNG / WebP 可以拿來做畫面預覽，
        // 但目前 EXIF 參數讀取只處理 JPEG。
        if (file.type !== "image/jpeg") {
            originalPhotoParams = null;
            restorePhotoButton.hidden = true;

            showSimulationError(
                "此圖片可進行畫面預覽，但只有 JPG／JPEG 可讀取拍攝 EXIF。"
            );

            return;
        }

        // 讀取照片 EXIF
        const exifData = await readPhotoExif(file);

        if (!exifData) {
            originalPhotoParams = null;
            restorePhotoButton.hidden = true;
            return;
        }

        originalPhotoParams = {
            iso: String(exifData.params.iso),
            aperture: String(exifData.params.aperture),
            shutter: String(exifData.params.shutter),
            filename: exifData.filename
        };

        restorePhotoButton.hidden = false;

        // 情境已選擇時重新計算曝光差
        if (currentProfile) {
            calculateEV();
        }

        console.log(
            "照片原始 EXIF：",
            originalPhotoParams
        );
    });

    clearSimulationPhotoButton.addEventListener("click", clearSimulationPhoto);
    simulationOriginal.addEventListener("error", () => {
        clearSimulationPhoto();
        showSimulationError("照片無法載入，請重新選擇其他圖片。");
    });

    restorePhotoButton.addEventListener("click", () => {
        if (!originalPhotoParams) return;
        applyPhotoParams(originalPhotoParams);
        calculateEV();
    });

    applyRecommendationButton.addEventListener("click", () => {
        if (!currentProfile) return;

        // 有照片 EXIF：
        // 使用照片條件產生動態推薦
        if (originalPhotoParams) {

            const adaptiveParams =
                buildAdaptiveParams(
                    currentProfile,
                    originalPhotoParams
                );

            if (adaptiveParams) {

                applyPhotoParams(
                    adaptiveParams
                );

                console.log(
                    "照片原始參數：",
                    originalPhotoParams
                );

                console.log(
                    "動態推薦參數：",
                    adaptiveParams
                );

                calculateEV();

                return;
            }
        }

        // 沒有照片 EXIF時，
        // 繼續使用原本固定情境推薦
        applyReference(currentProfile);

        calculateEV();
    });

    aiButton.addEventListener("click", requestAiExplanation);

    saveSimulationButton?.addEventListener("click", async () => {
        saveSimulationButton.disabled = true;

        try {


            if (!simulationResult.hasAttribute("src")) {
                throw new Error("目前沒有可儲存的模擬結果。");
            }

            if (!originalPhotoParams?.filename) {
                throw new Error(
                    "找不到照片的伺服器暫存檔名，請重新選擇照片。"
                );
            }

            const canvas = document.createElement("canvas");
            const context = canvas.getContext("2d");

            canvas.width = simulationResult.naturalWidth;
            canvas.height = simulationResult.naturalHeight;

            context.filter =
                simulationResult.style.filter || "brightness(1)";

            context.drawImage(
                simulationResult,
                0,
                0,
                canvas.width,
                canvas.height
            );

            context.filter = "none";

            const simulatedData =
                canvas.toDataURL("image/jpeg", 0.9);

            const response = await fetch("/api/save-simulation", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    filename: originalPhotoParams.filename,
                    simulated_image: simulatedData
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "模擬結果儲存失敗。"
                );
            }

            saveSimulationResult.className =
                "alert alert-success mt-3";

            saveSimulationResult.textContent =
                "曝光模擬結果已儲存到我的照片。";

        } catch (error) {
            saveSimulationResult.className =
                "alert alert-warning mt-3";

            saveSimulationResult.textContent =
                error.message;

        } finally {
            saveSimulationButton.disabled = false;
        }
    });

    const transferredPhoto = query.get("photo");

    if (transferredPhoto) {
        try {
            const photoUrl = new URL(
                transferredPhoto,
                window.location.origin
            );

            if (
                photoUrl.origin === window.location.origin
                && photoUrl.pathname.startsWith("/static/uploads/")
            ) {
                showSimulationPhoto(
                    photoUrl.href,
                    "照片分析圖片"
                );

                // 從照片網址取得 Flask 伺服器中的實際檔名
                const transferredFilename =
                    decodeURIComponent(
                        photoUrl.pathname.split("/").pop()
                    );

                // 照片分析頁若已經帶入 EXIF，
                // 將伺服器檔名一起加入
                if (originalPhotoParams) {
                    originalPhotoParams.filename =
                        transferredFilename;
                }

                console.log(
                    "帶入照片伺服器檔名：",
                    transferredFilename
                );
            }
        } catch (_error) {
            showSimulationError(
                "無法載入照片分析圖片，請手動選擇照片。"
            );
        }
    }

    window.addEventListener("pagehide", () => {
        if (simulationObjectUrl) URL.revokeObjectURL(simulationObjectUrl);
    });

    if (hasRequestedScene) {
        loadScene(sceneSelect.value, {
            initialParams: transferred,
            preserveCurrent: false,
        });
    }
});
