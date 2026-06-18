(function () {
    function isDesktopSidebar() {
        return window.matchMedia && window.matchMedia("(min-width: 50em)").matches;
    }

    function clearCollapsedCookie() {
        document.cookie = "wagtail_sidebar_collapsed=; Max-Age=0; path=/; SameSite=Lax";
    }

    function keepSidebarExpanded() {
        if (!isDesktopSidebar()) {
            return;
        }
        clearCollapsedCookie();
        var collapsedSidebar = document.querySelector("#wagtail-sidebar .sidebar.sidebar--slim");
        if (!collapsedSidebar) {
            return;
        }
        var toggle = document.querySelector("#wagtail-sidebar .sidebar__collapse-toggle[aria-expanded='false']");
        if (toggle) {
            toggle.click();
        } else {
            collapsedSidebar.classList.remove("sidebar--slim");
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", keepSidebarExpanded);
    } else {
        keepSidebarExpanded();
    }

    if (window.matchMedia) {
        window.matchMedia("(min-width: 50em)").addEventListener("change", keepSidebarExpanded);
    }

    new MutationObserver(keepSidebarExpanded).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "aria-expanded"],
    });
})();
