(function () {
    function normalizeAccountLabels(root) {
        var scope = root || document;
        scope.querySelectorAll('a[href$="/admin/account/"], a[href$="/admin/account/#"]').forEach(function (link) {
            var textNodes = [];
            var walker = document.createTreeWalker(link, NodeFilter.SHOW_TEXT);
            var node;
            while ((node = walker.nextNode())) {
                if ((node.nodeValue || "").trim()) {
                    textNodes.push(node);
                }
            }

            var changed = false;
            textNodes.forEach(function (textNode) {
                var value = (textNode.nodeValue || "").trim();
                if (value === "Conta" || value === "Account") {
                    textNode.nodeValue = textNode.nodeValue.replace(value, "Minha conta");
                    changed = true;
                }
            });

            if (!changed && (link.textContent || "").trim() === "") {
                link.setAttribute("aria-label", "Minha conta");
            }
        });

        if (window.location.pathname === "/admin/account/") {
            var walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
            var node;
            while ((node = walker.nextNode())) {
                if ((node.nodeValue || "").trim() === "Tema") {
                    node.nodeValue = node.nodeValue.replace("Tema", "Tema e zoom");
                }
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            normalizeAccountLabels(document);
        });
    } else {
        normalizeAccountLabels(document);
    }

    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType === 1) {
                    normalizeAccountLabels(node);
                }
            });
        });
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
})();
