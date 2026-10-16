/* Private, same-origin notice slide viewer. No third-party document service. */
(() => {
    "use strict";

    const viewer = document.querySelector("[data-notice-preview]");
    if (!viewer) return;

    const stage = viewer.querySelector("[data-preview-stage]");
    const image = viewer.querySelector("[data-preview-image]");
    const message = viewer.querySelector("[data-preview-message]");
    const messageText = viewer.querySelector("[data-preview-message-text]");
    const messageHelp = viewer.querySelector("[data-preview-message-help]");
    const spinner = viewer.querySelector("[data-preview-spinner]");
    const retry = viewer.querySelector("[data-preview-retry]");
    const toolbar = viewer.querySelector("[data-preview-toolbar]");
    const previous = viewer.querySelector("[data-preview-prev]");
    const next = viewer.querySelector("[data-preview-next]");
    const counter = viewer.querySelector("[data-preview-counter]");
    const expand = viewer.querySelector("[data-preview-expand]");
    const expandLabel = viewer.querySelector("[data-preview-expand-label]");
    const maxPolls = 48;
    let pages = 0;
    let currentPage = 0;
    let targetPage = 0;
    let pollCount = 0;
    let pollTimer;
    let preparing = false;
    let paused = false;
    let imageRequest = 0;
    let imageController;
    let imageObjectUrl;
    const jsonControllers = new Set();

    function showMessage(text, { loading = false, help = "", canRetry = false } = {}) {
        messageText.textContent = text;
        messageHelp.textContent = help;
        messageHelp.hidden = !help;
        spinner.hidden = !loading;
        retry.hidden = !canRetry;
        message.hidden = false;
        image.hidden = true;
        stage.setAttribute("aria-busy", String(loading));
    }

    function fail(text) {
        clearTimeout(pollTimer);
        if (targetPage < 1) targetPage = 1;
        previous.disabled = targetPage <= 1;
        next.disabled = targetPage >= pages;
        showMessage(text, {
            help: "원본 다운로드로 자료를 확인하거나 잠시 후 다시 시도해 주세요.",
            canRetry: true,
        });
    }

    async function requestJson(url, options = {}) {
        const controller = new AbortController();
        jsonControllers.add(controller);
        const timeout = setTimeout(() => controller.abort(), 95000);
        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                cache: "no-store",
                headers: { Accept: "application/json", ...options.headers },
                ...options,
                signal: controller.signal,
            });
            if (response.redirected || response.status === 401 || response.status === 403) {
                throw new Error("로그인 상태를 확인한 후 새로고침해 주세요.");
            }
            if (!(response.headers.get("content-type") || "").includes("application/json")) {
                throw new Error("미리보기를 불러오지 못했습니다.");
            }
            const result = await response.json();
            if (!response.ok && !["error", "unavailable", "busy"].includes(result.state)) {
                throw new Error("미리보기를 불러오지 못했습니다.");
            }
            return result;
        } finally {
            clearTimeout(timeout);
            jsonControllers.delete(controller);
        }
    }

    async function showPage(page) {
        if (!Number.isInteger(page) || page < 1 || page > pages) return;
        const url = new URL(viewer.dataset.pageUrl, window.location.origin);
        if (url.origin !== window.location.origin || !/\/0$/.test(url.pathname)) {
            fail("슬라이드 주소를 확인할 수 없습니다.");
            return;
        }
        url.pathname = url.pathname.replace(/\/0$/, `/${page}`);
        const request = ++imageRequest;
        targetPage = page;
        previous.disabled = page === 1;
        next.disabled = page === pages;
        if (imageController) imageController.abort();
        const controller = new AbortController();
        imageController = controller;
        const timeout = setTimeout(() => controller.abort(), 95000);
        let objectUrl;
        showMessage("슬라이드를 불러오는 중입니다.", { loading: true });
        try {
            // Fetch once: assigning this private, no-store URL to two Image
            // elements would otherwise download the same slide twice.
            const response = await fetch(url.href, {
                credentials: "same-origin",
                cache: "no-store",
                headers: { Accept: "image/png" },
                signal: controller.signal,
            });
            if (response.redirected || response.status === 401 || response.status === 403) {
                throw new Error("로그인 상태를 확인한 후 새로고침해 주세요.");
            }
            if (!response.ok || !(response.headers.get("content-type") || "").startsWith("image/png")) {
                throw new Error("슬라이드를 불러오지 못했습니다.");
            }
            const blob = await response.blob();
            if (paused || request !== imageRequest) return;
            objectUrl = URL.createObjectURL(blob);
            const slide = new Image();
            await new Promise((resolve, reject) => {
                slide.onload = resolve;
                slide.onerror = reject;
                slide.src = objectUrl;
            });
            if (paused || request !== imageRequest) return;
            currentPage = page;
            image.src = objectUrl;
            if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
            imageObjectUrl = objectUrl;
            objectUrl = undefined;
            image.alt = `첨부자료 ${page}번째 슬라이드, 전체 ${pages}장`;
            image.hidden = false;
            message.hidden = true;
            stage.setAttribute("aria-busy", "false");
            toolbar.hidden = false;
            expand.hidden = false;
            previous.disabled = page === 1;
            next.disabled = page === pages;
            counter.textContent = `${page} / ${pages}`;
            counter.setAttribute("aria-label", `전체 ${pages}장 중 ${page}번째 슬라이드`);
        } catch (error) {
            if (paused || request !== imageRequest) return;
            fail(error.message && error.message.startsWith("로그인 상태")
                ? error.message : "이 슬라이드를 불러오지 못했습니다.");
        } finally {
            clearTimeout(timeout);
            if (objectUrl) URL.revokeObjectURL(objectUrl);
            if (imageController === controller) imageController = undefined;
        }
    }

    function handleState(result) {
        if (paused) return;
        if (result.state === "ready") {
            const count = Number(result.pages);
            if (!Number.isInteger(count) || count < 1 || count > 100) {
                fail("미리보기의 슬라이드 수를 확인할 수 없습니다.");
                return;
            }
            pages = count;
            showPage(currentPage > 0 && currentPage <= pages ? currentPage : 1);
            return;
        }
        if (["pending", "busy"].includes(result.state)) {
            pollCount += 1;
            if (pollCount >= maxPolls) {
                fail("미리보기 준비에 시간이 걸리고 있습니다.");
                return;
            }
            showMessage(result.message || "슬라이드를 준비하고 있습니다.", {
                loading: true,
                help: "첫 미리보기는 잠시 시간이 걸릴 수 있습니다.",
            });
            pollTimer = setTimeout(loadPreview, 2500);
            return;
        }
        fail(result.message || "이 파일의 미리보기를 준비하지 못했습니다.");
    }

    async function loadPreview() {
        if (paused || preparing) return;
        preparing = true;
        try {
            const status = await requestJson(viewer.dataset.statusUrl);
            if (status.state === "pending") {
                const form = new URLSearchParams({ csrf_token: viewer.dataset.csrfToken });
                const result = await requestJson(viewer.dataset.prepareUrl, {
                    method: "POST",
                    headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
                    body: form.toString(),
                });
                handleState(result);
            } else {
                handleState(status);
            }
        } catch (error) {
            if (paused) return;
            fail(error.name === "AbortError"
                ? "미리보기 준비에 시간이 걸리고 있습니다."
                : error.message && error.message.startsWith("로그인 상태")
                    ? error.message
                    : "미리보기를 불러오지 못했습니다.");
        } finally {
            preparing = false;
        }
    }

    function setExpanded(expanded) {
        viewer.classList.toggle("is-expanded", expanded && !document.fullscreenElement);
        document.documentElement.classList.toggle("notice-preview-expanded", expanded && !document.fullscreenElement);
        expand.setAttribute("aria-pressed", String(expanded));
        expand.setAttribute("aria-label", expanded ? "슬라이드 전체 화면 닫기" : "슬라이드 전체 화면으로 보기");
        expandLabel.textContent = expanded ? "닫기" : "전체 화면";
        if (expanded) viewer.focus();
    }

    async function toggleExpanded() {
        if (document.fullscreenElement === viewer) {
            try {
                await document.exitFullscreen();
            } catch (_) {
                return;
            }
            expand.focus();
        } else if (viewer.classList.contains("is-expanded")) {
            setExpanded(false);
            expand.focus();
        } else if (viewer.requestFullscreen) {
            try {
                await viewer.requestFullscreen();
                setExpanded(true);
            } catch (_) {
                setExpanded(true);
            }
        } else {
            setExpanded(true);
        }
    }

    previous.addEventListener("click", () => showPage(targetPage - 1));
    next.addEventListener("click", () => showPage(targetPage + 1));
    expand.addEventListener("click", toggleExpanded);
    retry.addEventListener("click", () => {
        pollCount = 0;
        showMessage("슬라이드를 준비하고 있습니다.", { loading: true });
        if (pages > 0) showPage(targetPage || 1);
        else loadPreview();
    });
    viewer.addEventListener("keydown", (event) => {
        const isExpanded = viewer.classList.contains("is-expanded") || document.fullscreenElement === viewer;
        if (event.key === "Tab" && isExpanded) {
            const controls = Array.from(viewer.querySelectorAll("button:not(:disabled), a[href]"))
                .filter((control) => control.getClientRects().length > 0);
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && [viewer, first].includes(document.activeElement)) {
                event.preventDefault();
                if (last) last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                if (first) first.focus();
            }
        } else if (event.key === "Escape" && viewer.classList.contains("is-expanded")) {
            setExpanded(false);
            expand.focus();
        } else if (pages > 0 && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            event.preventDefault();
            if (event.key === "ArrowLeft") showPage(targetPage - 1);
            if (event.key === "ArrowRight") showPage(targetPage + 1);
            if (event.key === "Home") showPage(1);
            if (event.key === "End") showPage(pages);
        }
    });
    let wasFullscreen = false;
    document.addEventListener("fullscreenchange", () => {
        const isFullscreen = document.fullscreenElement === viewer;
        setExpanded(isFullscreen);
        if (wasFullscreen && !isFullscreen && !paused) expand.focus();
        wasFullscreen = isFullscreen;
    });
    window.addEventListener("pagehide", () => {
        paused = true;
        clearTimeout(pollTimer);
        imageRequest += 1;
        if (imageController) imageController.abort();
        jsonControllers.forEach((controller) => controller.abort());
        setExpanded(false);
        // Keep the displayed blob alive for the browser's back/forward cache.
        // Superseded images are revoked immediately in showPage().
    });
    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) return;
        paused = false;
        if (image.hidden) {
            if (pages > 0) showPage(targetPage || 1);
            else loadPreview();
        }
    });
    loadPreview();
})();
