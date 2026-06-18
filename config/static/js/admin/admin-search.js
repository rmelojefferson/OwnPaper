(function () {
    "use strict";

    var SEARCH_URL = "/admin/busca/";

    function configureSidebarSearch() {
        var input = document.getElementById("menu-search-q");
        if (!input) {
            return false;
        }

        var form = input.closest("form");
        if (!form) {
            return false;
        }

        form.setAttribute("action", SEARCH_URL);
        form.setAttribute("method", "get");
        input.setAttribute("name", "q");
        input.setAttribute("placeholder", "Buscar no painel");
        input.setAttribute("aria-label", "Buscar no painel");
        return true;
    }

    function init() {
        configureSidebarSearch();

        if (!window.MutationObserver) {
            return;
        }

        var observer = new MutationObserver(function () {
            configureSidebarSearch();
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}());
