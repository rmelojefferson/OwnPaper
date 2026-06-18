(function () {
    var admin = window.OwnPaperAdmin;
    if (!admin) {
        return;
    }
function ajustarCabecalhoSubmenu() {
    var rootStyle = window.getComputedStyle(document.documentElement);
    var largura = (rootStyle.getPropertyValue("--op-admin-sidebar-width") || "").trim() || "280px";
    var linkModeloMenu = document.querySelector(".sidebar-main-menu__list .sidebar-menu-item__link");
    var estiloLinkModelo = linkModeloMenu ? window.getComputedStyle(linkModeloMenu) : null;
    var iconeModeloMenu = linkModeloMenu ? linkModeloMenu.querySelector(".icon--menuitem") : null;
    var estiloIconeModelo = iconeModeloMenu ? window.getComputedStyle(iconeModeloMenu) : null;
    
    function forcarIconeTituloNewsletterEmail(h2) {
        if (!h2) {
            return;
        }
        var titulo = (h2.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
        if (titulo !== "newsletter" && titulo !== "e-mails" && titulo !== "emails") {
            return;
        }
        var svg = h2.querySelector(".icon--submenu-header");
        if (!svg) {
            return;
        }
        var use = svg.querySelector("use");
        if (use) {
            use.setAttribute("href", "#icon-mail");
            use.setAttribute("xlink:href", "#icon-mail");
        }
        var classes = (svg.getAttribute("class") || "")
            .split(/\s+/)
            .filter(function (c) {
                return c && (!/^icon-[a-z0-9-]+$/i.test(c) || /^icon--/i.test(c));
            });
        if (classes.indexOf("icon") === -1) {
            classes.unshift("icon");
        }
        if (classes.indexOf("icon--submenu-header") === -1) {
            classes.push("icon--submenu-header");
        }
        classes.push("icon-mail");
        svg.setAttribute("class", classes.join(" "));
    }

    document.querySelectorAll(".sidebar-sub-menu-panel").forEach(function (panel) {
        panel.style.setProperty("width", largura, "important");
        panel.style.setProperty("min-width", largura, "important");
        panel.style.setProperty("max-width", largura, "important");
        panel.style.setProperty("filter", "none", "important");

        var corTexto =
            (window.getComputedStyle(panel).getPropertyValue("--w-color-text-label-menus-default") || "").trim() ||
            (window.getComputedStyle(panel).color || "").trim() ||
            "inherit";
        var corModelo = estiloLinkModelo ? estiloLinkModelo.color : corTexto;

        var cabecalhos = panel.querySelectorAll(":scope > h2, :scope > [id^='wagtail-sidebar-submenu'][id$='-title']");
        cabecalhos.forEach(function (h2) {
            h2.style.setProperty("display", "flex", "important");
            h2.style.setProperty("flex-direction", "column", "important");
            h2.style.setProperty("align-items", "center", "important");
            h2.style.setProperty("justify-content", "center", "important");
            h2.style.setProperty("text-align", "center", "important");
            h2.style.setProperty("align-self", "stretch", "important");
            h2.style.setProperty("box-sizing", "border-box", "important");
            h2.style.setProperty("width", largura, "important");
            h2.style.setProperty("min-width", largura, "important");
            h2.style.setProperty("max-width", largura, "important");
            h2.style.setProperty("inline-size", largura, "important");
            h2.style.setProperty("margin-inline", "0", "important");
            h2.style.setProperty("padding-inline", "1rem", "important");
            h2.style.setProperty("color", corTexto, "important");
            h2.style.setProperty("font-weight", "600", "important");
            h2.style.setProperty("text-shadow", "none", "important");
            h2.style.setProperty("filter", "none", "important");
            forcarIconeTituloNewsletterEmail(h2);
        });

        panel.querySelectorAll(":scope > ul, :scope > .sidebar-sub-menu-panel__list").forEach(function (lista) {
            lista.style.setProperty("width", largura, "important");
            lista.style.setProperty("min-width", largura, "important");
            lista.style.setProperty("max-width", largura, "important");
            lista.style.setProperty("inline-size", largura, "important");
        });

        panel.querySelectorAll(".icon--submenu-header").forEach(function (icone) {
            icone.style.setProperty("color", corTexto, "important");
            icone.style.setProperty("width", "80px", "important");
            icone.style.setProperty("height", "80px", "important");
            icone.style.setProperty("min-width", "80px", "important");
            icone.style.setProperty("min-height", "80px", "important");
            icone.style.setProperty("max-width", "80px", "important");
            icone.style.setProperty("max-height", "80px", "important");
            icone.style.setProperty("aspect-ratio", "1 / 1", "important");
            icone.style.setProperty("display", "block", "important");
            icone.style.setProperty("inline-size", "80px", "important");
            icone.style.setProperty("block-size", "80px", "important");
            icone.style.setProperty("flex-basis", "80px", "important");
            icone.style.setProperty("transform", "none", "important");
            icone.style.setProperty("filter", "none", "important");
            icone.style.setProperty("text-shadow", "none", "important");
            icone.setAttribute("width", "80");
            icone.setAttribute("height", "80");
            icone.querySelectorAll("path,circle,rect,polygon,line,polyline,ellipse").forEach(function (shape) {
                shape.style.setProperty("fill", "currentColor", "important");
                shape.style.setProperty("stroke", "currentColor", "important");
            });
        });

        panel.querySelectorAll(".sidebar-menu-item__link").forEach(function (link) {
            link.style.setProperty("justify-content", "flex-start", "important");
            link.style.setProperty("text-align", "start", "important");
            link.style.setProperty("color", corModelo, "important");
            link.style.setProperty("text-shadow", "none", "important");
            link.style.setProperty("filter", "none", "important");
            link.style.setProperty("opacity", "1", "important");
            link.style.setProperty("font-smoothing", "auto", "important");
            link.style.setProperty("-webkit-font-smoothing", "auto", "important");
            if (estiloLinkModelo) {
                link.style.setProperty("font-family", estiloLinkModelo.fontFamily, "important");
                link.style.setProperty("font-size", estiloLinkModelo.fontSize, "important");
                link.style.setProperty("font-weight", estiloLinkModelo.fontWeight, "important");
                link.style.setProperty("line-height", estiloLinkModelo.lineHeight, "important");
                link.style.setProperty("letter-spacing", estiloLinkModelo.letterSpacing, "important");
            }
        });

        panel.querySelectorAll(".sidebar-menu-item__link .menuitem, .sidebar-menu-item__link .menuitem-label").forEach(function (texto) {
            texto.style.setProperty("text-align", "start", "important");
            texto.style.setProperty("color", "inherit", "important");
            texto.style.setProperty("text-shadow", "none", "important");
            texto.style.setProperty("filter", "none", "important");
            texto.style.setProperty("opacity", "1", "important");
            texto.style.setProperty("font-smoothing", "auto", "important");
            texto.style.setProperty("-webkit-font-smoothing", "auto", "important");
            if (estiloLinkModelo) {
                texto.style.setProperty("font-family", estiloLinkModelo.fontFamily, "important");
                texto.style.setProperty("font-size", estiloLinkModelo.fontSize, "important");
                texto.style.setProperty("font-weight", estiloLinkModelo.fontWeight, "important");
                texto.style.setProperty("line-height", estiloLinkModelo.lineHeight, "important");
                texto.style.setProperty("letter-spacing", estiloLinkModelo.letterSpacing, "important");
            }
        });

        panel.querySelectorAll(".icon--menuitem").forEach(function (iconeItem) {
            iconeItem.style.setProperty("color", corModelo, "important");
            iconeItem.style.setProperty("text-shadow", "none", "important");
            iconeItem.style.setProperty("filter", "none", "important");
            iconeItem.style.setProperty("opacity", "1", "important");
            if (estiloIconeModelo) {
                iconeItem.style.setProperty("width", estiloIconeModelo.width, "important");
                iconeItem.style.setProperty("height", estiloIconeModelo.height, "important");
                iconeItem.style.setProperty("min-width", estiloIconeModelo.minWidth, "important");
                iconeItem.style.setProperty("min-height", estiloIconeModelo.minHeight, "important");
                iconeItem.style.setProperty("flex-basis", estiloIconeModelo.width, "important");
            }
        });
    });
}

    admin.registerInit('ajustarCabecalhoSubmenu', ajustarCabecalhoSubmenu);
})();
