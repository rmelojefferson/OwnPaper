(function () {
    var tooltip = document.createElement("div");
    tooltip.className = "marcador-tooltip";
    tooltip.hidden = true;
    document.body.appendChild(tooltip);

    function destinoDoLink(link) {
        var href = link.getAttribute("href") || "";

        if (!href.match(/^#(nota|ref)-/)) {
            return null;
        }

        return document.getElementById(href.slice(1));
    }

    function textoLimpo(elemento) {
        if (!elemento) {
            return "";
        }

        return elemento.textContent.replace("↩", "").replace(/\s+/g, " ").trim();
    }

    function posicionarTooltip(evento) {
        var margem = 14;
        var largura = tooltip.offsetWidth;
        var altura = tooltip.offsetHeight;
        var esquerda = evento.clientX + margem;
        var topo = evento.clientY + margem;

        if (esquerda + largura > window.innerWidth - margem) {
            esquerda = window.innerWidth - largura - margem;
        }

        if (topo + altura > window.innerHeight - margem) {
            topo = evento.clientY - altura - margem;
        }

        tooltip.style.left = Math.max(margem, esquerda) + "px";
        tooltip.style.top = Math.max(margem, topo) + "px";
    }

    document.querySelectorAll('sup a[href^="#nota-"], sup a[href^="#ref-"]').forEach(function (link) {
        var destino = destinoDoLink(link);
        var texto = textoLimpo(destino);

        if (!destino || !texto) {
            return;
        }

        link.addEventListener("mouseenter", function (evento) {
            tooltip.textContent = texto;
            tooltip.hidden = false;
            posicionarTooltip(evento);
        });

        link.addEventListener("mousemove", posicionarTooltip);

        link.addEventListener("mouseleave", function () {
            tooltip.hidden = true;
        });

        link.addEventListener("click", function () {
            destino.classList.remove("marcador-destacado");

            setTimeout(function () {
                destino.classList.add("marcador-destacado");
            }, 0);
        });
    });

    document.querySelectorAll(".copiar-link-publicacao").forEach(function (botao) {
        botao.addEventListener("click", function () {
            var textoOriginal = botao.getAttribute("aria-label") || "Copiar link";

            function indicarSucesso() {
                botao.setAttribute("aria-label", "Link copiado");
                botao.title = "Link copiado";

                setTimeout(function () {
                    botao.setAttribute("aria-label", textoOriginal);
                    botao.title = textoOriginal;
                }, 2000);
            }

            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(window.location.href).then(indicarSucesso);
            }
        });
    });

    var artigo = document.querySelector("[data-publicacao-artigo]");
    var botaoAumentar = document.querySelector('[data-fonte-acao="aumentar"]');
    var botaoDiminuir = document.querySelector('[data-fonte-acao="diminuir"]');
    var botaoPadrao = document.querySelector('[data-fonte-acao="padrao"]');
    var niveisFonte = [0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5];
    var indiceFonte = 2;
    var chaveStorage = "ownpaper_publicacao_fonte_escala";

    function aplicarEscalaFonte() {
        if (!artigo) {
            return;
        }

        var escalaAtual = niveisFonte[indiceFonte];
        artigo.style.setProperty("--publicacao-fonte-escala", escalaAtual.toString());

        if (botaoDiminuir) {
            botaoDiminuir.disabled = indiceFonte === 0;
        }

        if (botaoAumentar) {
            botaoAumentar.disabled = indiceFonte === niveisFonte.length - 1;
        }
    }

    function salvarEscalaFonte() {
        try {
            window.localStorage.setItem(chaveStorage, indiceFonte.toString());
        } catch (erro) {
            return;
        }
    }

    function carregarEscalaFonte() {
        try {
            var indiceSalvo = parseInt(window.localStorage.getItem(chaveStorage), 10);

            if (!Number.isNaN(indiceSalvo) && indiceSalvo >= 0 && indiceSalvo < niveisFonte.length) {
                indiceFonte = indiceSalvo;
            }
        } catch (erro) {
            return;
        }
    }

    if (artigo && botaoAumentar && botaoDiminuir && botaoPadrao) {
        carregarEscalaFonte();
        aplicarEscalaFonte();

        botaoAumentar.addEventListener("click", function () {
            if (indiceFonte < niveisFonte.length - 1) {
                indiceFonte += 1;
                aplicarEscalaFonte();
                salvarEscalaFonte();
            }
        });

        botaoDiminuir.addEventListener("click", function () {
            if (indiceFonte > 0) {
                indiceFonte -= 1;
                aplicarEscalaFonte();
                salvarEscalaFonte();
            }
        });

        botaoPadrao.addEventListener("click", function () {
            indiceFonte = 2;
            aplicarEscalaFonte();
            salvarEscalaFonte();
        });
    }
})();
