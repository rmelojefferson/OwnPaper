(function () {
    var admin = window.OwnPaperAdmin;
    if (!admin) {
        return;
    }
    var esconderCampo = admin.esconderCampo;

function removerDensidadeEContraste() {
    var seletorCampos = [
        "#id_density",
        "#id_contrast",
        "#id_theme-density",
        "#id_theme-contrast",
        "[name='density']",
        "[name='contrast']",
        "[name='theme-density']",
        "[name='theme-contrast']",
        "[name$='-density']",
        "[name$='-contrast']",
        "[name$='density']",
        "[name$='contrast']",
    ].join(",");

    document.querySelectorAll(seletorCampos).forEach(esconderCampo);

    document
        .querySelectorAll("label[for*='density'], label[for*='contrast']")
        .forEach(function (label) {
            var row =
                label.closest(".w-field") ||
                label.closest(".field") ||
                label.parentElement;
            if (row) {
                row.style.display = "none";
            } else {
                label.style.display = "none";
            }
        });
}

    admin.registerInit('removerDensidadeEContraste', removerDensidadeEContraste);
})();
