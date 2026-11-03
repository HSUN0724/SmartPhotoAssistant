document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("photo-upload-form");
    const cameraInput = document.getElementById("camera-photo");
    const galleryInput = document.getElementById("gallery-photo");
    const photoSourceInput = document.getElementById("photo-source");
    const sceneSelect = document.getElementById("scene-select");
    const previewSection = document.getElementById("photo-preview-section");
    const previewImage = document.getElementById("photo-preview");
    const previewName = document.getElementById("photo-preview-name");
    const submitButton = document.getElementById("upload-submit");
    const submitText = document.getElementById("upload-submit-text");
    const loadingPanel = document.getElementById("upload-loading");
    const loadingText = document.getElementById("upload-loading-text");
    const compressionResult = document.getElementById("compression-result");
    const directPhotoExifNotice = document.getElementById("direct-photo-exif-notice");
    const sceneChoiceError = document.getElementById("scene-choice-error");
    const contextScript = document.getElementById("photo-analysis-context");
    const continueButton = document.getElementById("continue-to-recommend");

    const MAX_UPLOAD_EDGE = 1920;
    const JPEG_QUALITY = 0.82;
    const COMPRESSION_THRESHOLD = 1.5 * 1024 * 1024;

    let selectedInput = null;
    let previewUrl = null;
    let submitting = false;
    let analysisContext = null;

    if (contextScript) {
        try {
            analysisContext = JSON.parse(contextScript.textContent);
            sessionStorage.setItem("spaPhotoAnalysis", JSON.stringify(analysisContext));
        } catch (error) {
            console.warn("無法保存照片分析摘要。", error);
        }
    }

    function formatMegabytes(bytes) {
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    function setIconText(element, iconClass, text) {
        const icon = document.createElement("i");
        icon.className = `bi ${iconClass}`;
        icon.setAttribute("aria-hidden", "true");
        element.replaceChildren(icon, document.createTextNode(` ${text}`));
    }

    function updateSubmitState() {
        submitButton.disabled = !selectedInput
            || !selectedInput.files.length
            || !sceneSelect.value
            || submitting;
    }

    async function checkDirectPhotoExif(file) {
        directPhotoExifNotice.hidden = true;
        if (selectedInput !== cameraInput || file.type !== "image/jpeg") {
            return;
        }
        try {
            const header = await file.slice(0, Math.min(file.size, 128 * 1024)).arrayBuffer();
            directPhotoExifNotice.hidden = Boolean(extractExifSegment(header));
        } catch (error) {
            console.warn("無法在上傳前檢查 EXIF。", error);
        }
    }

    function showPreview(input, otherInput, source) {
        const file = input.files && input.files[0];

        if (!file) {
            return;
        }

        selectedInput = input;
        photoSourceInput.value = source;
        otherInput.value = "";
        document.getElementById("upload-choice-error").hidden = true;
        compressionResult.hidden = true;

        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }

        previewUrl = URL.createObjectURL(file);
        previewImage.src = previewUrl;
        previewImage.alt = `準備上傳的照片：${file.name}`;
        previewName.textContent = `${file.name}（${formatMegabytes(file.size)}）`;
        previewSection.hidden = false;
        updateSubmitState();
        checkDirectPhotoExif(file);
        previewSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function extractExifSegment(arrayBuffer) {
        const bytes = new Uint8Array(arrayBuffer);

        if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) {
            return null;
        }

        let offset = 2;
        while (offset + 4 < bytes.length && bytes[offset] === 0xff) {
            const marker = bytes[offset + 1];

            if (marker === 0xda || marker === 0xd9) {
                break;
            }

            const segmentLength = (bytes[offset + 2] << 8) | bytes[offset + 3];
            const segmentEnd = offset + 2 + segmentLength;

            if (segmentLength < 2 || segmentEnd > bytes.length) {
                break;
            }

            const isExif = marker === 0xe1
                && bytes[offset + 4] === 0x45
                && bytes[offset + 5] === 0x78
                && bytes[offset + 6] === 0x69
                && bytes[offset + 7] === 0x66
                && bytes[offset + 8] === 0x00
                && bytes[offset + 9] === 0x00;

            if (isExif) {
                return bytes.slice(offset, segmentEnd);
            }

            offset = segmentEnd;
        }

        return null;
    }

    function setExifOrientationToNormal(exifSegment) {
        if (!exifSegment || exifSegment.length < 18) {
            return exifSegment;
        }

        const patched = exifSegment.slice();
        const view = new DataView(patched.buffer, patched.byteOffset, patched.byteLength);
        const tiffStart = 10;
        const byteOrder = String.fromCharCode(patched[tiffStart], patched[tiffStart + 1]);
        const littleEndian = byteOrder === "II";

        if (!littleEndian && byteOrder !== "MM") {
            return patched;
        }

        try {
            const firstIfdOffset = view.getUint32(tiffStart + 4, littleEndian);
            const ifdStart = tiffStart + firstIfdOffset;
            const entryCount = view.getUint16(ifdStart, littleEndian);

            for (let index = 0; index < entryCount; index += 1) {
                const entryOffset = ifdStart + 2 + index * 12;
                if (entryOffset + 12 > patched.length) {
                    break;
                }

                if (view.getUint16(entryOffset, littleEndian) === 0x0112) {
                    view.setUint16(entryOffset + 8, 1, littleEndian);
                    view.setUint16(entryOffset + 10, 0, littleEndian);
                    break;
                }
            }
        } catch (_error) {
            return exifSegment;
        }

        return patched;
    }

    function insertExifSegment(jpegBuffer, exifSegment) {
        if (!exifSegment) {
            return new Uint8Array(jpegBuffer);
        }

        const jpeg = new Uint8Array(jpegBuffer);
        const combined = new Uint8Array(jpeg.length + exifSegment.length);
        combined.set(jpeg.slice(0, 2), 0);
        combined.set(exifSegment, 2);
        combined.set(jpeg.slice(2), 2 + exifSegment.length);
        return combined;
    }

    async function loadBitmap(file) {
        if ("createImageBitmap" in window) {
            return window.createImageBitmap(file, { imageOrientation: "from-image" });
        }

        const objectUrl = URL.createObjectURL(file);
        try {
            const image = new Image();
            image.src = objectUrl;
            await image.decode();
            return image;
        } finally {
            URL.revokeObjectURL(objectUrl);
        }
    }

    async function compressJpeg(file) {
        if (file.type !== "image/jpeg" || file.size <= COMPRESSION_THRESHOLD) {
            return file;
        }

        const originalBuffer = await file.arrayBuffer();
        const exifSegment = setExifOrientationToNormal(extractExifSegment(originalBuffer));
        const bitmap = await loadBitmap(file);
        const scale = Math.min(1, MAX_UPLOAD_EDGE / Math.max(bitmap.width, bitmap.height));
        const width = Math.max(1, Math.round(bitmap.width * scale));
        const height = Math.max(1, Math.round(bitmap.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        canvas.getContext("2d", { alpha: false }).drawImage(bitmap, 0, 0, width, height);

        if (typeof bitmap.close === "function") {
            bitmap.close();
        }

        const compressedBlob = await new Promise((resolve, reject) => {
            canvas.toBlob(
                (blob) => blob ? resolve(blob) : reject(new Error("照片壓縮失敗。")),
                "image/jpeg",
                JPEG_QUALITY,
            );
        });

        const compressedBuffer = await compressedBlob.arrayBuffer();
        const jpegWithExif = insertExifSegment(compressedBuffer, exifSegment);
        return new File([jpegWithExif], file.name, {
            type: "image/jpeg",
            lastModified: file.lastModified,
        });
    }

    function replaceSelectedFile(file) {
        if (!("DataTransfer" in window)) {
            return false;
        }

        const transfer = new DataTransfer();
        transfer.items.add(file);
        selectedInput.files = transfer.files;
        return true;
    }

    cameraInput?.addEventListener("change", () => showPreview(cameraInput, galleryInput, "camera"));
    galleryInput?.addEventListener("change", () => showPreview(galleryInput, cameraInput, "gallery"));
    sceneSelect?.addEventListener("change", () => {
        sceneChoiceError.hidden = Boolean(sceneSelect.value);
        updateSubmitState();
    });

    form?.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (submitting) {
            return;
        }

        if (!selectedInput || !selectedInput.files.length) {
            document.getElementById("upload-choice-error").hidden = false;
            return;
        }
        if (!sceneSelect.value) {
            sceneChoiceError.hidden = false;
            sceneSelect.focus();
            return;
        }

        submitting = true;
        submitButton.disabled = true;
        submitText.textContent = "正在準備照片…";
        loadingText.textContent = "正在縮小照片並保留 EXIF…";
        loadingPanel.hidden = false;

        const originalFile = selectedInput.files[0];
        try {
            const uploadFile = await compressJpeg(originalFile);

            if (uploadFile !== originalFile && replaceSelectedFile(uploadFile)) {
                compressionResult.textContent = `已由 ${formatMegabytes(originalFile.size)} 縮小為 ${formatMegabytes(uploadFile.size)}`;
                compressionResult.hidden = false;
            }
        } catch (error) {
            console.warn("手機端壓縮失敗，改為上傳原始照片。", error);
        }

        submitText.textContent = "正在上傳並讀取參數…";
        loadingText.textContent = "照片正在傳送至電腦，請不要關閉頁面…";
        HTMLFormElement.prototype.submit.call(form);
    });

    const meterPosition = document.getElementById("meter-position");
    const meterArrow = document.getElementById("meter-arrow");

    if (meterPosition && meterArrow) {
        window.setTimeout(() => {
            meterArrow.style.left = `${meterPosition.value}%`;
        }, 300);
    }

    const aiButton = document.getElementById("ai-analysis-button");
    const aiResult = document.getElementById("ai-analysis-result");

    aiButton?.addEventListener("click", async () => {
        aiButton.disabled = true;
        setIconText(aiButton, "bi-hourglass-split", "AI 分析中，請稍候…");
        aiResult.className = "analysis-status mt-3 ai-loading";

        let elapsedSeconds = 0;
        aiResult.textContent = "Gemini 正在分析較小的照片副本…";
        const progressTimer = window.setInterval(() => {
            elapsedSeconds += 1;
            aiResult.textContent = `Gemini 正在分析照片與拍攝參數… ${elapsedSeconds} 秒`;
        }, 1000);

        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 60000);

        try {
            const response = await fetch("/api/ai-analysis", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filename: aiButton.dataset.filename,
                    scene: aiButton.dataset.scene,
                }),
                signal: controller.signal,
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "AI 分析失敗。");
            }

            aiResult.className = "alert alert-info mt-3 fade-in";
            aiResult.textContent = data.advice;
            setIconText(aiButton, "bi-arrow-clockwise", "重新產生 AI 攝影建議");
            if (analysisContext) {
                analysisContext.ai_advice = data.advice;
                try {
                    sessionStorage.setItem("spaPhotoAnalysis", JSON.stringify(analysisContext));
                } catch (_error) {
                    // 瀏覽器停用工作階段儲存時，頁面原功能仍可使用。
                }
            }
        } catch (error) {
            const message = error.name === "AbortError"
                ? "AI 分析超過 60 秒，請檢查網路後再試一次。"
                : error.message;
            aiResult.className = "alert alert-warning mt-3";
            setIconText(aiResult, "bi-exclamation-triangle", message);
            setIconText(aiButton, "bi-robot", "再試一次");
        } finally {
            window.clearInterval(progressTimer);
            window.clearTimeout(timeout);
            aiButton.disabled = false;
        }
    });

    const savePhotoButton =
        document.getElementById("save-photo-button");

    const savePhotoResult =
        document.getElementById("save-photo-result");

    savePhotoButton?.addEventListener("click", async () => {
        savePhotoButton.disabled = true;

        try {
            const response = await fetch("/api/save-photo", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    filename: savePhotoButton.dataset.filename
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "照片保存失敗。"
                );
            }

            savePhotoResult.className =
                "alert alert-success mt-2";

            savePhotoResult.textContent =
                data.message || "照片已保存到我的照片。";

            savePhotoButton.textContent =
                "已保存";

            savePhotoButton.disabled = true;

        } catch (error) {
            savePhotoResult.className =
                "alert alert-warning mt-2";

            savePhotoResult.textContent =
                error.message;

            savePhotoButton.disabled = false;
        }
    });

    const deletePhotoButton =
        document.getElementById("delete-photo-button");

    const deletePhotoResult =
        document.getElementById("delete-photo-result");

    deletePhotoButton?.addEventListener("click", async () => {
        const confirmed = window.confirm(
            "確定要立即刪除這張照片嗎？\n刪除後將無法再用這張照片進行 AI 分析或後續攝影流程。"
        );

        if (!confirmed) {
            return;
        }

        deletePhotoButton.disabled = true;

        try {
            const response = await fetch("/api/delete-photo", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    filename: deletePhotoButton.dataset.filename
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "照片刪除失敗。"
                );
            }

            deletePhotoResult.className =
                "alert alert-success mt-3";

            deletePhotoResult.textContent =
                "照片與 AI 分析縮圖已刪除。";

            deletePhotoButton.hidden = true;

            if (aiButton) {
                aiButton.disabled = true;
                aiButton.hidden = true;
            }

            if (continueButton) {
                continueButton.disabled = true;
                continueButton.hidden = true;
            }

        } catch (error) {
            deletePhotoResult.className =
                "alert alert-warning mt-3";

            deletePhotoResult.textContent =
                error.message;

            deletePhotoButton.disabled = false;
        }
    });


    continueButton?.addEventListener("click", () => {
        if (analysisContext) {
            try {
                sessionStorage.setItem("spaPhotoAnalysis", JSON.stringify(analysisContext));
            } catch (_error) {
                // 即使無法儲存，仍可只帶入情境。
            }
        }
        const params = new URLSearchParams({
            scene: continueButton.dataset.scene,
            from: "analysis",
        });
        window.location.href = `/recommend?${params.toString()}`;
    });
});
