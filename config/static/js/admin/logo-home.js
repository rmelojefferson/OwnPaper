(function () {
    var admin = window.OwnPaperAdmin;
    if (!admin) {
        return;
    }
function vincularConfiguracaoLogoHome() {
    var campoProporcao = document.querySelector(
        "#id_menu_home_logo_proporcao, [name='menu_home_logo_proporcao'], [name$='menu_home_logo_proporcao']"
    );
    var campoAjuste = document.querySelector(
        "#id_menu_home_logo_ajuste, [name='menu_home_logo_ajuste'], [name$='menu_home_logo_ajuste']"
    );
    var campoAlturaDesktop = document.querySelector(
        "#id_menu_home_logo_altura_desktop_px, [name='menu_home_logo_altura_desktop_px'], [name$='menu_home_logo_altura_desktop_px']"
    );
    var campoAlturaMobile = document.querySelector(
        "#id_menu_home_logo_altura_mobile_px, [name='menu_home_logo_altura_mobile_px'], [name$='menu_home_logo_altura_mobile_px']"
    );
    if (!campoProporcao || !campoAjuste || !campoAlturaDesktop || !campoAlturaMobile) {
        return;
    }

    var mapaProporcao = {
        "1:1": [1, 1],
        "3:2": [3, 2],
        "4:3": [4, 3],
        "16:9": [16, 9],
        "21:9": [21, 9],
        "12:5": [12, 5],
        "5:1": [5, 1],
    };

    var alvo =
        document.querySelector("[data-op-menu-home-logo-dimensoes]") ||
        document.getElementById("op-menu-home-logo-dimensoes");
    if (!alvo) {
        alvo = document.createElement("div");
        alvo.id = "op-menu-home-logo-dimensoes";
        var linhaCampo =
            campoAlturaMobile.closest(".w-field") ||
            campoAlturaMobile.closest(".field") ||
            campoAlturaMobile.parentElement;
        if (linhaCampo && linhaCampo.parentElement) {
            linhaCampo.insertAdjacentElement("afterend", alvo);
        }
    }
    alvo.className = "op-admin-logo-home-helper";

    function inteiroSeguro(valor, fallback) {
        var numero = parseInt(valor, 10);
        if (Number.isNaN(numero)) {
            return fallback;
        }
        return Math.max(24, Math.min(80, numero));
    }

        function renderizar() {
            var proporcao = campoProporcao.value || "auto";
        var ajuste = campoAjuste.value || "conter";
        var alturaDesktop = inteiroSeguro(campoAlturaDesktop.value, 72);
        var alturaMobile = inteiroSeguro(campoAlturaMobile.value, 50);
        var par = mapaProporcao[proporcao];

            if (!par) {
                alvo.replaceChildren(
                    criarTextoHelper('strong', 'Dimensão recomendada'),
                    criarTextoHelper('span', 'Com a proporção original do arquivo, a largura acompanha a própria imagem.'),
                    criarLinhaComCode('Desktop: ', alturaDesktop + 'px', ' de altura máxima.'),
                    criarLinhaComCode('Mobile: ', alturaMobile + 'px', ' de altura máxima.'),
                    criarLinhaComCode('Modo atual: ', ajuste === "preencher" ? "preencher área" : "manter proporção", '.')
                );
                return;
            }

            var larguraDesktop = Math.round((alturaDesktop * par[0]) / par[1]);
            var larguraMobile = Math.round((alturaMobile * par[0]) / par[1]);
            alvo.replaceChildren(
                criarTextoHelper('strong', 'Dimensão recomendada para preencher o botão da home'),
                criarLinhaComCode('Desktop: ', alturaDesktop + ' x ' + larguraDesktop + ' px', ' (A x L).'),
                criarLinhaComCode('Mobile: ', alturaMobile + ' x ' + larguraMobile + ' px', ' (A x L).'),
                criarLinhaComCode('Modo atual: ', ajuste === "preencher" ? "redimensionar para preencher" : "manter proporção dentro da área", '.')
            );
        }

        function criarTextoHelper(tag, texto) {
            var el = document.createElement(tag);
            el.textContent = texto;
            return el;
        }

        function criarLinhaComCode(prefixo, codigo, sufixo) {
            var linha = document.createElement('span');
            linha.appendChild(document.createTextNode(prefixo));
            var code = document.createElement('code');
            code.textContent = codigo;
            linha.appendChild(code);
            linha.appendChild(document.createTextNode(sufixo || ''));
            return linha;
        }

    if (campoProporcao.dataset.opLogoHomeBound !== "1") {
        [campoProporcao, campoAjuste, campoAlturaDesktop, campoAlturaMobile].forEach(function (campo) {
            campo.addEventListener("input", renderizar);
            campo.addEventListener("change", renderizar);
        });
        campoProporcao.dataset.opLogoHomeBound = "1";
    }
    renderizar();
}

    admin.registerInit('vincularConfiguracaoLogoHome', vincularConfiguracaoLogoHome);
})();
