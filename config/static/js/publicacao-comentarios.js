(function () {
    var root = document.querySelector("[data-comentarios-root]");
    var popup = document.querySelector("[data-comentario-popup]");
    var replyButtons = Array.prototype.slice.call(document.querySelectorAll("[data-comentario-reply]"));

    if (!root && !popup && !replyButtons.length) {
        return;
    }

    var pageId = root ? (root.getAttribute("data-comentario-page-id") || "publicacao") : "publicacao";
    var successUrl = root ? (root.getAttribute("data-comentario-success-url") || window.location.pathname) : window.location.pathname;
    var draft = document.querySelector("[data-comentario-rascunho]");
    var draftKey = "ownpaper-comment-draft-" + pageId;
    var replyKey = "ownpaper-comment-reply-" + pageId;
    var draftLogado = document.querySelector("#comentario-texto");
    var draftAtivo = draftLogado || draft;
    var aberturas = Array.prototype.slice.call(document.querySelectorAll("[data-comentario-popup-open]"));
    var fechar = popup ? popup.querySelector("[data-comentario-popup-close]") : null;
    var steps = popup ? Array.prototype.slice.call(popup.querySelectorAll("[data-comentario-step]")) : [];
    var paineis = popup ? Array.prototype.slice.call(popup.querySelectorAll("[data-comentario-painel]")) : [];
    var formLogado = document.querySelector('form[action$="/comentarios/enviar/"]');
    var formPublico = document.querySelector(".comentario-form-publico");
    var formLogadoPlaceholder = document.querySelector("[data-comentario-form-placeholder]");
    var formPublicoPlaceholder = document.querySelector("[data-comentario-form-publico-placeholder]");
    var activeReplyButton = null;

    function limparQueryComentario() {
        if (!window.history || !window.history.replaceState) return;
        try {
            var url = new URL(window.location.href);
            if (!url.searchParams.has("comentario")) return;
            url.searchParams.delete("comentario");
            var destino = url.pathname + (url.searchParams.toString() ? ("?" + url.searchParams.toString()) : "") + url.hash;
            window.history.replaceState({}, "", destino);
        } catch (err) {}
    }

    function liberarCheckboxPrivacidade(container) {
        if (!container) return;
        var checkbox = container.querySelector("[data-privacy-checkbox]");
        if (!checkbox || !checkbox.disabled) return;
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
        if (!scrollbox) return;
        if (scrollbox.offsetParent === null || scrollbox.closest("[hidden]")) return;
        var container = scrollbox.closest("form, .card, .comentario-popup-card, body");
        if (!container) return;
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

    function ativarValidacaoUsernameAoVivo(contexto) {
        var raiz = contexto || document;
        raiz.querySelectorAll("[data-username-input]").forEach(function (input) {
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
                if (!submit) return;
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
                            if (current !== requestId) return;
                            renderizar(payload);
                        })
                        .catch(function () {
                            if (current !== requestId) return;
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

    function mostrarPainel(nome) {
        if (!popup) return;
        if (["login", "cadastro", "codigo"].indexOf(nome) === -1) {
            nome = "login";
        }
        paineis.forEach(function (painel) {
            painel.hidden = painel.getAttribute("data-comentario-painel") !== nome;
        });
        popup.setAttribute("data-state", nome);
        window.setTimeout(function () {
            ativarAceitePrivacidadeEscalonado(popup);
            ativarValidacaoUsernameAoVivo(popup);
        }, 0);
    }

    function openPopup(nome) {
        if (!popup) return;
        popup.hidden = false;
        popup.setAttribute("data-open", "1");
        document.body.classList.add("comentario-popup-open");
        mostrarPainel(nome || popup.getAttribute("data-state") || "login");
    }

    function closePopup() {
        if (!popup) return;
        popup.hidden = true;
        popup.removeAttribute("data-open");
        document.body.classList.remove("comentario-popup-open");
    }

    function finalizarOAuthComentario(redirectUrl) {
        closePopup();
        try {
            var destino = new URL(redirectUrl || successUrl, window.location.origin);
            window.location.replace(destino.toString());
        } catch (err) {
            window.location.replace(successUrl);
        }
    }

    function consumirBeaconOAuth() {
        try {
            var raw = window.localStorage.getItem("ownpaper-comment-oauth-success");
            if (!raw) return false;
            var data = JSON.parse(raw);
            window.localStorage.removeItem("ownpaper-comment-oauth-success");
            if (!data || !data.redirectUrl) return false;
            finalizarOAuthComentario(data.redirectUrl);
            return true;
        } catch (err) {
            return false;
        }
    }

    function moverBlocoRespostaParaOrigem() {
        if (formLogado && formLogadoPlaceholder) {
            formLogadoPlaceholder.parentNode.insertBefore(formLogado, formLogadoPlaceholder);
        }
        if (formPublico && formPublicoPlaceholder) {
            formPublicoPlaceholder.parentNode.insertBefore(formPublico, formPublicoPlaceholder);
        }
    }

    function moverBlocoRespostaParaComentario(id) {
        var slot = id ? document.querySelector("#comentario-" + id + " [data-comentario-inline-slot]") : null;
        if (!slot) {
            moverBlocoRespostaParaOrigem();
            return;
        }
        if (formLogado) {
            slot.appendChild(formLogado);
        }
        if (formPublico) {
            slot.appendChild(formPublico);
        }
    }

    function atualizarReplyContexto(id, autor) {
        document.querySelectorAll("[data-comentario-pai]").forEach(function (input) {
            input.value = id || "";
        });
        moverBlocoRespostaParaComentario(id);
        document.querySelectorAll("[data-comentario-reply-contexto]").forEach(function (box) {
            var texto = box.querySelector("[data-comentario-reply-texto]");
            if (!id) {
                box.hidden = true;
                if (texto) texto.textContent = "";
                return;
            }
            box.hidden = false;
            if (texto) {
                texto.textContent = "Respondendo a " + (autor || "");
            }
        });
        document.querySelectorAll("[data-comentario-reply-cancel-action]").forEach(function (botao) {
            botao.hidden = !id;
        });
    }

    function restaurarBotoesResposta() {
        document.querySelectorAll("[data-comentario-reply]").forEach(function (botao) {
            var label = botao.getAttribute("data-label-reply");
            if (label) {
                botao.textContent = label;
            }
            botao.classList.remove("is-cancel");
        });
        activeReplyButton = null;
    }

    function limparReplyContexto() {
        restaurarBotoesResposta();
        atualizarReplyContexto("", "");
        if (!window.localStorage) return;
        try {
            window.localStorage.removeItem(replyKey);
        } catch (err) {}
    }

    if (draftAtivo && window.localStorage) {
        try {
            var savedDraft = window.localStorage.getItem(draftKey);
            if (savedDraft && !draftAtivo.value) {
                draftAtivo.value = savedDraft;
            }
            draftAtivo.addEventListener("input", function () {
                window.localStorage.setItem(draftKey, draftAtivo.value || "");
            });
        } catch (err) {}
    }

    Array.prototype.slice.call(document.querySelectorAll('form[action$="/comentarios/enviar/"]')).forEach(function (form) {
        form.addEventListener("submit", function () {
            if (!window.localStorage) return;
            try {
                window.localStorage.removeItem(draftKey);
                window.localStorage.removeItem(replyKey);
            } catch (err) {}
        });
    });

    aberturas.forEach(function (abrir) {
        abrir.addEventListener("click", function () {
            openPopup("login");
        });
    });

    if (fechar) {
        fechar.addEventListener("click", closePopup);
    }

    if (popup) {
        popup.addEventListener("click", function (event) {
            if (event.target === popup) {
                closePopup();
            }
        });
        popup.querySelectorAll("[data-oauth-popup]").forEach(function (link) {
            link.addEventListener("click", function (event) {
                event.preventDefault();
                var href = link.getAttribute("href");
                if (!href) return;
                var win = window.open(href, "ownpaper-oauth-comment", "width=540,height=700,scrollbars=yes,resizable=yes");
                if (win) {
                    win.focus();
                } else {
                    window.location.href = href;
                }
            });
        });
    }

    steps.forEach(function (btn) {
        btn.addEventListener("click", function () {
            mostrarPainel(btn.getAttribute("data-comentario-step"));
        });
    });

    replyButtons.forEach(function (botao) {
        botao.addEventListener("click", function () {
            var id = botao.getAttribute("data-comentario-reply") || "";
            var autor = botao.getAttribute("data-comentario-author") || "";
            var paiAtual = document.querySelector("[data-comentario-pai]");
            var sameButton = activeReplyButton === botao && paiAtual && paiAtual.value === id;
            if (sameButton) {
                limparReplyContexto();
                return;
            }
            restaurarBotoesResposta();
            activeReplyButton = botao;
            botao.classList.add("is-cancel");
            botao.textContent = botao.getAttribute("data-label-cancel") || botao.textContent;
            atualizarReplyContexto(id, autor);
            if (window.localStorage) {
                try {
                    window.localStorage.setItem(replyKey, JSON.stringify({ id: id, autor: autor }));
                } catch (err) {}
            }
            var alvo = (formLogado && formLogado.querySelector("#comentario-texto")) || (formPublico && formPublico.querySelector("#comentario-texto-publico"));
            if (alvo) {
                alvo.focus();
                alvo.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });
    });

    document.querySelectorAll("[data-comentario-reply-cancel]").forEach(function (botao) {
        botao.addEventListener("click", limparReplyContexto);
    });

    document.querySelectorAll("[data-comentario-reply-cancel-action]").forEach(function (botao) {
        botao.addEventListener("click", limparReplyContexto);
    });

    window.addEventListener("message", function (event) {
        if (event.origin !== window.location.origin) return;
        var data = event.data || {};
        if (data.type !== "ownpaper-comment-oauth-success") return;
        finalizarOAuthComentario(data.redirectUrl);
    });

    window.addEventListener("storage", function (event) {
        if (event.key !== "ownpaper-comment-oauth-success" || !event.newValue) return;
        consumirBeaconOAuth();
    });

    window.addEventListener("focus", consumirBeaconOAuth);
    consumirBeaconOAuth();

    if (window.localStorage) {
        try {
            var replySaved = window.localStorage.getItem(replyKey);
            if (replySaved) {
                var data = JSON.parse(replySaved);
                var savedButton = data && data.id ? document.querySelector('[data-comentario-reply="' + data.id + '"]') : null;
                if (savedButton) {
                    activeReplyButton = savedButton;
                    savedButton.classList.add("is-cancel");
                    savedButton.textContent = savedButton.getAttribute("data-label-cancel") || savedButton.textContent;
                }
                atualizarReplyContexto((data && data.id) || "", (data && data.autor) || "");
            }
        } catch (err) {}
    }

    window.setTimeout(function () {
        document.querySelectorAll("[data-auto-hide-success]").forEach(function (mensagem) {
            mensagem.hidden = true;
        });
        limparQueryComentario();
    }, 6000);

    ativarAceitePrivacidadeEscalonado(document);
    ativarValidacaoUsernameAoVivo(document);

    if (popup && popup.hasAttribute("data-open")) {
        openPopup(popup.getAttribute("data-state") || "login");
        limparQueryComentario();
    } else if (popup) {
        mostrarPainel("login");
    }
})();
