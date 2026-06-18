(function () {
    var storageKey = "op_admin_font_scale";
    var minScale = 0.85;
    var maxScale = 1.25;
    var step = 0.05;

    function clamp(value) {
        return Math.min(maxScale, Math.max(minScale, value));
    }

    function readScale() {
        var saved;
        try {
            saved = window.localStorage.getItem(storageKey);
        } catch (error) {
            saved = null;
        }

        var parsed = parseFloat(saved || "1");
        if (Number.isNaN(parsed)) {
            return 1;
        }
        return clamp(parsed);
    }

    function persistScale(scale) {
        try {
            window.localStorage.setItem(storageKey, scale.toFixed(2));
        } catch (error) {
            // LocalStorage can be unavailable in restricted browser modes.
        }
    }

    function applyScale(value, persist) {
        var scale = clamp(value);
        document.documentElement.style.setProperty("--op-admin-font-scale", scale.toFixed(2));
        document.documentElement.style.fontSize = (16 * scale).toFixed(2) + "px";
        if (persist) {
            persistScale(scale);
        }
        updateControls(scale);
        return scale;
    }

    function updateControls(scale) {
        document.querySelectorAll("[data-op-admin-zoom-value]").forEach(function (node) {
            node.textContent = Math.round(scale * 100) + "%";
        });
        document.querySelectorAll("[data-op-admin-zoom='down']").forEach(function (button) {
            button.disabled = scale <= minScale;
        });
        document.querySelectorAll("[data-op-admin-zoom='up']").forEach(function (button) {
            button.disabled = scale >= maxScale;
        });
        document.querySelectorAll("[data-op-admin-zoom='reset']").forEach(function (button) {
            button.disabled = Math.abs(scale - 1) < 0.001;
        });
    }

    var currentScale = applyScale(readScale(), false);

    function initZoomControls() {
        var controls = document.querySelector("[data-op-admin-zoom-controls]");
        if (!controls || controls.dataset.opAdminZoomReady === "true") {
            updateControls(currentScale);
            return;
        }

        controls.dataset.opAdminZoomReady = "true";
        controls.addEventListener("click", function (event) {
            var button = event.target.closest("button[data-op-admin-zoom]");
            if (!button || !controls.contains(button)) {
                return;
            }

            var action = button.getAttribute("data-op-admin-zoom");
            if (action === "down") {
                currentScale = applyScale(currentScale - step, true);
            } else if (action === "up") {
                currentScale = applyScale(currentScale + step, true);
            } else if (action === "reset") {
                currentScale = applyScale(1, true);
            }
        });

        updateControls(currentScale);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initZoomControls);
    } else {
        initZoomControls();
    }
})();
