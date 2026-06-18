(function () {
    function normalizeValue(value) {
        var text = String(value || "").trim().toLowerCase();
        if (typeof text.normalize === "function") {
            text = text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        }
        return text;
    }

    function setupFilter(root) {
        if (!root) return;
        var input = root.querySelector("[data-taxonomy-filter-input]");
        var list = root.parentElement && root.parentElement.querySelector("[data-taxonomy-filter-list]");
        var items = list ? Array.prototype.slice.call(list.querySelectorAll("[data-taxonomy-filter-item]")) : [];
        if (!input || !items.length) return;

        function applyFilter() {
            var term = normalizeValue(input.value);
            items.forEach(function (item) {
                var value = normalizeValue(item.getAttribute("data-taxonomy-filter-value"));
                item.hidden = !!term && value.indexOf(term) === -1;
            });
        }

        input.addEventListener("input", applyFilter);
        applyFilter();
    }

    function init() {
        Array.prototype.forEach.call(
            document.querySelectorAll("[data-taxonomy-filter-root]"),
            setupFilter
        );
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
}());
