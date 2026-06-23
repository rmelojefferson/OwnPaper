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

        destino.classList.remove("op-publication-highlight");
        void destino.offsetWidth;
        destino.classList.add("op-publication-highlight");
        destino.__highlightTimer = window.setTimeout(function () {
            destino.classList.remove("op-publication-highlight");
            destino.__highlightTimer = null;
        }, 1800);
    }

    var retornoAncoraAtual = null;

    function removerRetornoAncora() {
        if (retornoAncoraAtual && retornoAncoraAtual.parentNode) {
            retornoAncoraAtual.parentNode.removeChild(retornoAncoraAtual);
        }
        retornoAncoraAtual = null;
    }

    function inserirRetornoAncora(bloco, linkOrigem) {
        if (!bloco || !linkOrigem) {
            return;
        }
        removerRetornoAncora();
        var retorno = document.createElement("a");
        retorno.href = "#";
        retorno.className = "ancora-retorno-publicacao";
        retorno.setAttribute("aria-label", "Voltar ao link da âncora");
        retorno.textContent = "↩";
        retorno.addEventListener("click", function (event) {
            event.preventDefault();
            rolarEDestacar(linkOrigem, linkOrigem, "center");
            limparHashDaUrl();
            removerRetornoAncora();
        });
        bloco.appendChild(document.createTextNode(" "));
        bloco.appendChild(retorno);
        retornoAncoraAtual = retorno;
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

        if (!destino) {
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
            rolarEDestacar(bloco, bloco, "center");
            inserirRetornoAncora(bloco, link);
            limparHashDaUrl();
        });
    });

    function destacarHashAtual() {
        var hash = window.location.hash || "";

        if (!hash || hash.match(/^#(nota|ref)(-|src-)/)) {
            return;
        }

        var destino = document.getElementById(hash.slice(1));

        if (!destino) {
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

    document.querySelectorAll(".copiar-link-publicacao").forEach(function (botao) {
        botao.addEventListener("click", function () {
            var textoOriginal = botao.getAttribute("aria-label") || "Copiar link";
            var textoCopiado = botao.getAttribute("data-label-copiado") || "Link copiado";
            var urlDestino = botao.getAttribute("data-short-url") || window.location.href;

            function indicarSucesso() {
                botao.setAttribute("aria-label", textoCopiado);
                botao.title = textoCopiado;

                setTimeout(function () {
                    botao.setAttribute("aria-label", textoOriginal);
                    botao.title = textoOriginal;
                }, 2000);
            }

            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(urlDestino).then(indicarSucesso);
            }
        });
    });

    var artigo = document.querySelector("[data-publicacao-artigo]");
    var controleLeituraPrincipal = document.querySelector(".publicacao-barra-acoes .controles-leitura");
    var niveisFonte = [0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5];
    var indiceFonte = 2;
    var chaveStorage = "ownpaper_publicacao_fonte_escala";
    var botoesFonteRegistrados = new WeakSet();

    function botoesFonte(acao) {
        return Array.prototype.slice.call(
            document.querySelectorAll('[data-fonte-acao="' + acao + '"]')
        );
    }

    function aplicarEscalaFonte() {
        if (!artigo) {
            return;
        }

        var escalaAtual = niveisFonte[indiceFonte];
        artigo.style.setProperty("--publicacao-fonte-escala", escalaAtual.toString());
        document.documentElement.style.setProperty("--publicacao-fonte-escala", escalaAtual.toString());

        botoesFonte("diminuir").forEach(function (botao) {
            botao.disabled = indiceFonte === 0;
        });
        botoesFonte("aumentar").forEach(function (botao) {
            botao.disabled = indiceFonte === niveisFonte.length - 1;
        });
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

    function registrarBotaoFonte(botao) {
        if (!botao || botoesFonteRegistrados.has(botao)) {
            return;
        }
        botoesFonteRegistrados.add(botao);
        botao.addEventListener("click", function () {
            var acao = botao.getAttribute("data-fonte-acao");
            if (acao === "aumentar" && indiceFonte < niveisFonte.length - 1) {
                indiceFonte += 1;
            } else if (acao === "diminuir" && indiceFonte > 0) {
                indiceFonte -= 1;
            } else if (acao === "padrao") {
                indiceFonte = 2;
            } else {
                return;
            }
            aplicarEscalaFonte();
            salvarEscalaFonte();
        });
    }

    function garantirControlesLeituraFlutuantes() {
        if (!controleLeituraPrincipal || document.querySelector(".controles-leitura-flutuante")) {
            return;
        }
        var clone = controleLeituraPrincipal.cloneNode(true);
        clone.querySelectorAll(".publicacao-idiomas-manual").forEach(function (grupoIdiomas) {
            grupoIdiomas.remove();
        });
        clone.classList.add("controles-leitura-flutuante");
        clone.setAttribute("aria-hidden", "true");
        document.body.appendChild(clone);

        clone.querySelectorAll("[data-fonte-acao]").forEach(registrarBotaoFonte);

        function posicionarClone() {
            var alvoTexto = document.querySelector(".corpo") || artigo;
            if (!alvoTexto) {
                return;
            }
            var rect = alvoTexto.getBoundingClientRect();
            var largura = clone.offsetWidth || 48;
            var esquerda = Math.max(10, rect.left - largura - 14);
            clone.style.left = esquerda + "px";
        }

        if ("IntersectionObserver" in window) {
            var observer = new IntersectionObserver(
                function (entries) {
                    entries.forEach(function (entry) {
                        var mostrar = !entry.isIntersecting && window.innerWidth > 980;
                        clone.classList.toggle("visivel", mostrar);
                        if (mostrar) {
                            posicionarClone();
                        }
                    });
                },
                { threshold: 0.2 }
            );
            observer.observe(controleLeituraPrincipal);
            window.addEventListener("resize", function () {
                if (window.innerWidth <= 980) {
                    clone.classList.remove("visivel");
                    return;
                }
                posicionarClone();
            });
            window.addEventListener("scroll", function () {
                if (clone.classList.contains("visivel")) {
                    posicionarClone();
                }
            }, { passive: true });
        }
    }

    if (artigo) {
        carregarEscalaFonte();
        aplicarEscalaFonte();
        botoesFonte("aumentar").forEach(registrarBotaoFonte);
        botoesFonte("diminuir").forEach(registrarBotaoFonte);
        botoesFonte("padrao").forEach(registrarBotaoFonte);
        garantirControlesLeituraFlutuantes();
    }

    var ratingBox = document.querySelector("[data-rating-stars]");
    var ratingInput = document.querySelector("[data-rating-input]");
    var ratingLabel = document.querySelector("[data-rating-label]");
    var ratingVotesLabel = document.querySelector("[data-rating-votes-label]");

    function aplicarRatingVisual(valor) {
        if (!ratingBox) {
            return;
        }

        var nota = parseFloat(valor || "0");
        if (isNaN(nota)) {
            nota = 0;
        }

        ratingBox.querySelectorAll("[data-rating-star]").forEach(function (star, index) {
            var preenchida = star.querySelector(".avaliacao-estrela-preenchida");
            var numero = index + 1;
            var percentual = 0;

            if (nota >= numero) {
                percentual = 100;
            } else if (nota >= numero - 0.5) {
                percentual = 50;
            }

            if (preenchida) {
                preenchida.style.clipPath = "inset(0 " + (100 - percentual) + "% 0 0)";
            }
        });

        if (ratingLabel && nota > 0) {
            ratingLabel.textContent = nota.toFixed(1) + "/5";
        }
    }

    if (ratingBox && ratingInput) {
        var valorAtual = parseFloat(ratingBox.getAttribute("data-current") || "0");
        var valorPersistido = valorAtual || 0;
        var mediaAtual = parseFloat(ratingBox.getAttribute("data-average") || "0") || 0;
        var totalAvaliacoes = parseInt(ratingBox.getAttribute("data-votes") || "0", 10) || 0;
        var valorBase = valorAtual || mediaAtual || 0;

        function atualizarResumoVotos() {
            if (!ratingVotesLabel) {
                return;
            }

            if (totalAvaliacoes <= 0) {
                ratingVotesLabel.textContent = ratingVotesLabel.getAttribute("data-zero-label") || "";
                return;
            }

            var sufixo = totalAvaliacoes === 1
                ? (ratingVotesLabel.getAttribute("data-singular-label") || "")
                : (ratingVotesLabel.getAttribute("data-plural-label") || "");
            ratingVotesLabel.textContent = totalAvaliacoes + " " + sufixo;
        }

        function atualizarMediaOtimista() {
            var novoValor = parseFloat(ratingInput.value || "0");
            if (!novoValor || isNaN(novoValor)) {
                return;
            }

            var somaAnterior = mediaAtual * totalAvaliacoes;
            var novoTotal = totalAvaliacoes;

            if (valorPersistido > 0) {
                somaAnterior -= valorPersistido;
            } else {
                novoTotal += 1;
            }

            var novaMedia = novoTotal > 0 ? (somaAnterior + novoValor) / novoTotal : novoValor;

            totalAvaliacoes = novoTotal;
            mediaAtual = novaMedia;
            valorPersistido = novoValor;
            valorBase = novaMedia;

            ratingBox.setAttribute("data-current", novoValor.toFixed(1));
            ratingBox.setAttribute("data-average", novaMedia.toFixed(1));
            ratingBox.setAttribute("data-votes", String(novoTotal));
            atualizarResumoVotos();
            aplicarRatingVisual(novaMedia);
        }

        aplicarRatingVisual(valorBase);
        atualizarResumoVotos();

        ratingBox.querySelectorAll("[data-rating-star]").forEach(function (star, index) {
            function valorDoEvento(event) {
                var rect = star.getBoundingClientRect();
                var posicao = event.clientX - rect.left;
                var metade = posicao <= rect.width / 2 ? 0.5 : 1;
                return index + metade;
            }

            star.addEventListener("mousemove", function (event) {
                aplicarRatingVisual(valorDoEvento(event));
            });

            star.addEventListener("click", function (event) {
                var valor = valorDoEvento(event);
                ratingInput.value = valor.toFixed(1);
                ratingBox.setAttribute("data-current", valor.toFixed(1));
                aplicarRatingVisual(valor);
            });
        });

        ratingBox.addEventListener("mouseleave", function () {
            var atual = parseFloat(ratingBox.getAttribute("data-current") || "0");
            aplicarRatingVisual(atual || valorBase);
        });

        var ratingForm = ratingBox.closest("form");
        if (ratingForm) {
            ratingForm.addEventListener("submit", function () {
                atualizarMediaOtimista();
            });
        }
    }

    function liberarCheckboxPrivacidade(container) {
        if (!container) {
            return;
        }
        var checkbox = container.querySelector("[data-privacy-checkbox]");
        if (!checkbox || !checkbox.disabled) {
            return;
        }
        checkbox.disabled = false;
        var label = checkbox.closest("[aria-disabled]");
        if (label) {
            label.setAttribute("aria-disabled", "false");
        }
        var usernameInput = container.querySelector("[data-username-input]");
        if (usernameInput) {
            usernameInput.dispatchEvent(new Event("input"));
        }
    }

    function revisarScrollboxPrivacidade(scrollbox) {
        if (!scrollbox) {
            return;
        }
        if (scrollbox.offsetParent === null || scrollbox.closest("[hidden]")) {
            return;
        }
        var container = scrollbox.closest("form, .card, .comentario-popup-card, body");
        if (!container) {
            return;
        }
        if (scrollbox.scrollHeight <= scrollbox.clientHeight + 4) {
            liberarCheckboxPrivacidade(container);
            return;
        }
        if (scrollbox.scrollTop + scrollbox.clientHeight >= scrollbox.scrollHeight - 4) {
            liberarCheckboxPrivacidade(container);
        }
    }

    function ativarAceitePrivacidadeEscalonado(contexto) {
        var raiz = contexto || document;
        raiz.querySelectorAll("[data-privacy-scrollbox]").forEach(function (scrollbox) {
            if (!scrollbox.hasAttribute("data-privacy-scrollbox-bound")) {
                scrollbox.setAttribute("data-privacy-scrollbox-bound", "1");
                scrollbox.addEventListener("scroll", function () {
                    revisarScrollboxPrivacidade(scrollbox);
                }, { passive: true });
            }
            revisarScrollboxPrivacidade(scrollbox);
        });
    }

    function ativarValidacaoUsernameAoVivo() {
        document.querySelectorAll("[data-username-input]").forEach(function (input) {
            if (input.hasAttribute("data-username-bound")) {
                return;
            }
            input.setAttribute("data-username-bound", "1");
            var container = input.closest("form, .card, .comentario-popup-card, body");
            var status = container ? container.querySelector("[data-username-status]") : null;
            var submit = container ? container.querySelector("[data-submit-finalizar]") : null;
            var endpoint = input.getAttribute("data-username-check-url") || "";
            var timer = null;
            var requestId = 0;

            if (!status || !endpoint) {
                return;
            }

            function atualizarSubmit(disponivel) {
                if (!submit) {
                    return;
                }
                var bloqueadoPrivacidade = !!(container && container.querySelector("[data-privacy-checkbox][disabled]"));
                submit.disabled = bloqueadoPrivacidade || !disponivel;
            }

            function renderizar(payload) {
                status.textContent = payload.message || "";
                status.className = "comentario-username-status" + (payload.available ? " ok" : payload.normalized ? " erro" : "");
                status.dataset.available = payload.available ? "true" : "false";
                if (payload.normalized && input.value.trim() !== payload.normalized) {
                    status.textContent += " Será normalizado como @" + payload.normalized;
                }
                atualizarSubmit(!!payload.available);
            }

            input.addEventListener("input", function () {
                clearTimeout(timer);
                timer = setTimeout(function () {
                    var raw = input.value.trim();
                    if (!raw) {
                        renderizar({ available: false, normalized: "", message: "Informe um nome de usuário." });
                        return;
                    }
                    var current = ++requestId;
                    fetch(endpoint + "?username=" + encodeURIComponent(raw), {
                        headers: { "X-Requested-With": "XMLHttpRequest" }
                    })
                        .then(function (response) { return response.json(); })
                        .then(function (payload) {
                            if (current !== requestId) {
                                return;
                            }
                            renderizar(payload);
                        })
                        .catch(function () {
                            if (current !== requestId) {
                                return;
                            }
                            renderizar({ available: false, normalized: "", message: "Não foi possível validar o nome de usuário agora." });
                        });
                }, 220);
            });

            if (input.value.trim()) {
                input.dispatchEvent(new Event("input"));
            } else {
                atualizarSubmit(false);
            }
        });
    }

    ativarAceitePrivacidadeEscalonado();
    ativarValidacaoUsernameAoVivo();

})();
