console.log("=== recommend.js TEST ===");
document.addEventListener("DOMContentLoaded", () => {
    const sceneSelect = document.getElementById("scene");
    const recommendButton = document.getElementById("recommend-button");
    const result = document.getElementById("result");
    const contextCard = document.getElementById("analysis-context-card");
    const contextSummary = document.getElementById("analysis-context-summary");
    const contextList = document.getElementById("analysis-context-list");
    const query = new URLSearchParams(window.location.search);
    let currentProfile = null;
    let analysisContext = null;

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

    function loadAnalysisContext() {
        if (query.get("from") !== "analysis") {
            return;
        }
        try {
            analysisContext = JSON.parse(sessionStorage.getItem("spaPhotoAnalysis") || "null");
        } catch (_error) {
            analysisContext = null;
        }
        if (!analysisContext || typeof analysisContext !== "object") {
            return;
        }

        const camera = analysisContext.camera || {};
        contextSummary.textContent = analysisContext.has_exif
            ? `照片參數：ISO ${camera.iso}、${camera.aperture}、${camera.shutter}`
            : (analysisContext.exif_notice
                || "照片沒有完整 EXIF，已帶入所選拍攝情境與畫面分析摘要。");

        const items = [
            ...(analysisContext.parameter_analysis || []),
            ...(analysisContext.scene_analysis || []),
            ...(analysisContext.ai_advice ? [`AI 照片分析：${analysisContext.ai_advice}`] : []),
        ].slice(0, 5);
        contextList.replaceChildren();
        items.forEach((item) => {
            const li = document.createElement("li");
            setIconText(li, "bi-check2-circle", item);
            contextList.appendChild(li);
        });
        if (!items.length) {
            const li = document.createElement("li");
            setIconText(li, "bi-info-circle", "已接收拍攝情境，請取得對應建議。");
            contextList.appendChild(li);
        }
        contextCard.hidden = false;
    }

    function photoExposureParams() {
        if (!analysisContext?.has_exif) {
            return null;
        }

        const normalized = analysisContext.exposure_params || {};
        const camera = analysisContext.camera || {};
        const isoMatch = String(normalized.iso ?? camera.iso ?? "").match(/[\d.]+/);
        const apertureMatch = String(normalized.aperture ?? camera.aperture ?? "").match(/[\d.]+/);
        const shutter = String(normalized.shutter ?? camera.shutter ?? "")
            .toLowerCase()
            .replace("秒", "")
            .replace(/s$/, "")
            .trim();
        const iso = isoMatch ? Number(isoMatch[0]) : Number.NaN;
        const aperture = apertureMatch ? Number(apertureMatch[0]) : Number.NaN;
        const shutterParts = shutter.split("/");
        const shutterSeconds = shutterParts.length === 2
            ? Number(shutterParts[0]) / Number(shutterParts[1])
            : Number(shutter);

        if (!Number.isFinite(iso) || iso <= 0
            || !Number.isFinite(aperture) || aperture <= 0
            || !Number.isFinite(shutterSeconds) || shutterSeconds <= 0) {
            return null;
        }
        return { iso: String(iso), aperture: String(aperture), shutter };
    }

    function exposureUrl(profile) {
        const photoParams = photoExposureParams();
        const selectedParams = photoParams || {
            iso: String(profile.iso),
            aperture: String(profile.exposure.reference.aperture),
            shutter: profile.shutter,
        };
        const params = new URLSearchParams({
            scene: profile.scene_key,
            ...selectedParams,
            source: analysisContext ? "analysis" : "recommendation",
            parameter_source: photoParams ? "photo" : "recommendation",
        });
        if (analysisContext?.analysis_image_url) {
            params.set("photo", analysisContext.analysis_image_url);
        }
        return `/exposure?${params.toString()}`;
    }

    function renderProfile(profile) {
        const suitable = (profile.suitable || [])
            .map((item) => `<span class="context-chip">${escapeHTML(item)}</span>`)
            .join("");
        const photoParams = photoExposureParams();
        const exposureButtonIcon = photoParams ? "bi-camera" : "bi-brightness-high";
        const exposureButtonLabel = photoParams
            ? "將照片原始參數帶入曝光模擬"
            : "將推薦參數帶入曝光模擬";
        result.innerHTML = `
            <section class="card shadow mt-4 fade-in">
                <div class="card-header card-header-accent">
                    <i class="bi ${escapeHTML(profile.icon)}" aria-hidden="true"></i>
                    ${escapeHTML(profile.scene_name)}推薦設定
                </div>
                <div class="card-body">
                    <div class="info-grid compact">
                        <div><span>ISO</span><strong>${escapeHTML(profile.iso)}</strong></div>
                        <div><span>光圈</span><strong>${escapeHTML(profile.aperture)}</strong></div>
                        <div><span>快門</span><strong>${escapeHTML(profile.shutter)}</strong></div>
                        <div><span>白平衡</span><strong>${escapeHTML(profile.white_balance)}</strong></div>
                        <div><span>對焦模式</span><strong>${escapeHTML(profile.focus_mode)}</strong></div>
                        <div><span>曝光補償</span><strong>${escapeHTML(profile.exposure_compensation)}</strong></div>
                        <div><span>底片模擬</span><strong>${escapeHTML(profile.film_simulation)}</strong></div>
                        <div><span>建議鏡頭</span><strong>${escapeHTML(profile.lens)}</strong></div>
                    </div>
                    <div class="alert alert-warning mt-3 mb-0"><i class="bi bi-lightbulb" aria-hidden="true"></i> ${escapeHTML(profile.tips)}</div>
                    <div class="context-chips mt-3">${suitable}</div>
                </div>
            </section>
            <section class="card ai-card mt-4 fade-in">
                <div class="card-header"><i class="bi bi-robot" aria-hidden="true"></i> AI 自然語言解釋</div>
                <div class="card-body">
                    <p class="text-secondary">AI 會解釋這組固定參數的用途與取捨，不會自行更改數值。</p>
                    <button id="recommend-ai-button" class="btn btn-primary" type="button"><i class="bi bi-robot" aria-hidden="true"></i> 產生 AI 解釋</button>
                    <div id="recommend-ai-result" class="mt-3" aria-live="polite"></div>
                </div>
            </section>
            <div class="d-grid mt-4">
                <a id="to-exposure-button" class="btn btn-success btn-lg" href="${exposureUrl(profile)}">
                    <i class="bi ${exposureButtonIcon}" aria-hidden="true"></i> ${exposureButtonLabel}
                </a>
            </div>
        `;
        document.getElementById("recommend-ai-button")?.addEventListener("click", requestAiExplanation);
    }

    async function requestAiExplanation() {
        const button = document.getElementById("recommend-ai-button");
        const output = document.getElementById("recommend-ai-result");
        button.disabled = true;
        setIconText(button, "bi-hourglass-split", "正在整理說明…");
        output.className = "analysis-status mt-3";
        output.textContent = "正在根據共用參數與照片分析產生解釋…";
        try {
            console.log("AI 按鈕 try 有進來");

            console.log(
                "送給 AI 的 Adaptive Recommendation：",
                analysisContext?.adaptive_recommendation
            );

            const response = await fetch("/api/ai-explanation", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    type: "recommendation",
                    scene: currentProfile.scene_key,
                    analysis_context: analysisContext || {},
                    adaptive_recommendation:
                        analysisContext?.adaptive_recommendation || null,
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "無法產生解釋。");
            }
            output.className = "alert alert-info mt-3";
            output.textContent = data.explanation;
            setIconText(
                button,
                "bi-arrow-clockwise",
                data.source === "gemini" ? "重新產生 AI 解釋" : "重新產生解釋",
            );
        } catch (error) {
            output.className = "alert alert-warning mt-3";
            setIconText(output, "bi-exclamation-triangle", error.message);
            setIconText(button, "bi-arrow-clockwise", "再試一次");
        } finally {
            button.disabled = false;
        }
    }

    async function recommendSetting() {
        const scene = sceneSelect.value;
        if (!scene) {
            currentProfile = null;
            recommendButton.disabled = true;
            result.innerHTML = "<div class='alert alert-warning mt-4'>請先選擇拍攝情境。</div>";
            return;
        }
        recommendButton.disabled = true;
        result.innerHTML = "<div class='alert alert-info mt-4'>正在讀取共用情境參數…</div>";
        try {
            const response = await fetch(`/api/recommend/${encodeURIComponent(scene)}`);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "查詢失敗。");
            }
            currentProfile = data;
            renderProfile(data);
        } catch (error) {
            result.innerHTML = `<div class='alert alert-danger mt-4'>${escapeHTML(error.message)}</div>`;
        } finally {
            recommendButton.disabled = false;
        }
    }

    loadAnalysisContext();
    const contextScene = query.get("scene") || analysisContext?.scene;
    if (contextScene && sceneSelect.querySelector(`option[value="${CSS.escape(contextScene)}"]`)) {
        sceneSelect.value = contextScene;
    }

    recommendButton.addEventListener("click", recommendSetting);
    sceneSelect.addEventListener("change", () => {
        recommendButton.disabled = !sceneSelect.value;
        if (sceneSelect.value) {
            recommendSetting();
        }
    });
    recommendButton.disabled = !sceneSelect.value;
    if (sceneSelect.value && (query.has("scene") || query.get("from") === "analysis")) {
        recommendSetting();
    }
});
