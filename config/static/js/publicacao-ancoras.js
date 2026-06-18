(function () {
    function limparHashDaUrl() {
        if (!window.history || !window.history.replaceState) {
            return;
        }
        try {
            window.history.replaceState({}, "", window.location.pathname + window.location.search);
        } catch (err) {}
    }

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

    function destacarDestino(destino) {
        if (!destino) {
            return;
        }

        if (destino.__highlightTimer) {
            window.clearTimeout(destino.__highlightTimer);
            destino.__highlightTimer = null;
        }

        destino.style.transition = "none";
        destino.style.background = document.documentElement.getAttribute("data-theme") === "escuro"
            ? "color-mix(in srgb, var(--op-accent, #93c5fd) 46%, transparent)"
            : "color-mix(in srgb, var(--op-accent, #1d4ed8) 28%, transparent)";

        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () {
                destino.style.transition = "background 1.5s ease";
                destino.style.background = "transparent";
                destino.__highlightTimer = window.setTimeout(function () {
                    destino.style.transition = "";
                    destino.style.background = "";
                    destino.__highlightTimer = null;
                }, 1500);
            });
        });
    }

    function rolarEDestacar(destinoRolagem, destinoDestaque, bloco) {
        if (!destinoRolagem) {
            return;
        }

        destinoRolagem.scrollIntoView({ behavior: "smooth", block: bloco || "start" });

        var destinoFinal = destinoDestaque || destinoRolagem;
        var topoAnterior = null;
        var tentativas = 0;

        function aguardarFimDaRolagem() {
            if (!destinoFinal || !destinoFinal.getBoundingClientRect) {
                return;
            }

            var topoAtual = Math.round(destinoFinal.getBoundingClientRect().top);

            if (topoAnterior !== null && Math.abs(topoAtual - topoAnterior) <= 1) {
                destacarDestino(destinoFinal);
                return;
            }

            topoAnterior = topoAtual;
            tentativas += 1;

            if (tentativas >= 24) {
                destacarDestino(destinoFinal);
                return;
            }

            window.requestAnimationFrame(aguardarFimDaRolagem);
        }

        window.requestAnimationFrame(aguardarFimDaRolagem);
    }

    function blocoVisualDoMarcador(destino) {
        if (!destino || !destino.closest) {
            return destino;
        }

        var bloco = destino.closest(
            ".corpo p, .corpo li, .corpo blockquote, .corpo h2, .corpo h3, .corpo h4, .corpo h5, .corpo h6, .resumo p"
        );

        return bloco || destino;
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

        link.addEventListener("click", function (event) {
            event.preventDefault();
            rolarEDestacar(destino, destino, "start");
            limparHashDaUrl();
        });
    });

    document.querySelectorAll('a[href^="#nota-src-"], a[href^="#ref-src-"]').forEach(function (link) {
        link.addEventListener("click", function (event) {
            var href = link.getAttribute("href") || "";
            var destino = document.getElementById(href.slice(1));
            event.preventDefault();
            rolarEDestacar(destino, blocoVisualDoMarcador(destino), "center");
            limparHashDaUrl();
        });
    });

    function destinoAncoraInterna(link) {
        var href = link.getAttribute("href") || "";

        if (!href.match(/^#[^#]/) || href.match(/^#(nota|ref)(-|src-)/)) {
            return null;
        }

        var destino = document.getElementById(href.slice(1));

        if (!destino || !destino.classList || !destino.classList.contains("ancora-interna-publicacao")) {
            return null;
        }

        return destino;
    }

    document.querySelectorAll('a[href^="#"]').forEach(function (link) {
        var destino = destinoAncoraInterna(link);

        if (!destino) {
            return;
        }

        link.addEventListener("click", function (event) {
            event.preventDefault();
            var bloco = blocoVisualDoMarcador(destino);
            rolarEDestacar(bloco, bloco, "start");
            limparHashDaUrl();
        });
    });

    function destacarHashAtual() {
        var hash = window.location.hash || "";

        if (!hash || hash.match(/^#(nota|ref)(-|src-)/)) {
            return;
        }

        var destino = document.getElementById(hash.slice(1));

        if (!destino || !destino.classList || !destino.classList.contains("ancora-interna-publicacao")) {
            return;
        }

        destacarDestino(blocoVisualDoMarcador(destino));
        limparHashDaUrl();
    }

    window.addEventListener("hashchange", destacarHashAtual);
    destacarHashAtual();

    document.querySelectorAll('a[href="#comentarios-titulo"]').forEach(function (link) {
        link.addEventListener("click", function (event) {
            var destino = document.getElementById("comentarios-titulo");
            if (!destino) {
                return;
            }
            event.preventDefault();
            rolarEDestacar(destino, destino, "start");
            limparHashDaUrl();
        });
    });
})();
