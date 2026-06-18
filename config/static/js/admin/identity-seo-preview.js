(function () {
    "use strict";

    function ready(callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback, { once: true });
            return;
        }
        callback();
    }

    function extrairUrlDeBackground(valor) {
        if (!valor) {
            return "";
        }
        var match = valor.match(/url\((['"]?)(.*?)\1\)/);
        return match ? match[2] : "";
    }

    function imagemValida(img) {
        if (!img || !img.getAttribute("src")) {
            return false;
        }
        var src = img.getAttribute("src");
        if (src.indexOf("data:image/svg") === 0) {
            return false;
        }
        return true;
    }

    function encontrarImagemDoCampo(field) {
        var imagens = Array.prototype.slice.call(field.querySelectorAll("img[src]"))
            .filter(imagemValida);

        if (imagens.length) {
            var img = imagens[imagens.length - 1];
            return {
                src: img.getAttribute("src"),
                alt: img.getAttribute("alt") || ""
            };
        }

        var elementosComBackground = Array.prototype.slice.call(
            field.querySelectorAll("[style*='background-image']")
        );
        for (var i = elementosComBackground.length - 1; i >= 0; i -= 1) {
            var url = extrairUrlDeBackground(elementosComBackground[i].style.backgroundImage);
            if (url) {
                return {
                    src: url,
                    alt: ""
                };
            }
        }

        return null;
    }

    function campoTemValor(field) {
        return Boolean(valorSelecionado(field));
    }

    function valorSelecionado(field) {
        var controles = field.querySelectorAll("input[name], select[name]");
        var controleComValor = Array.prototype.find.call(controles, function (controle) {
            return Boolean(controle.value);
        });
        return controleComValor ? controleComValor.value : "";
    }

    function buscarPreview(card, imageId) {
        var template = card.getAttribute("data-preview-url-template");
        if (!template || !imageId) {
            return Promise.resolve(null);
        }

        var spec = card.getAttribute("data-preview-spec") || "fill-320x180";
        var url = template.replace(/\/0\/(?:\?|$)/, "/" + encodeURIComponent(imageId) + "/");
        url += (url.indexOf("?") === -1 ? "?" : "&") + "spec=" + encodeURIComponent(spec);

        return window.fetch(url, {
            credentials: "same-origin",
            headers: {
                "Accept": "application/json"
            }
        }).then(function (response) {
            if (!response.ok) {
                return null;
            }
            return response.json();
        }).then(function (payload) {
            if (!payload || !payload.url) {
                return null;
            }
            return {
                src: payload.url,
                alt: payload.title || ""
            };
        }).catch(function () {
            return null;
        });
    }

    function campoTemValorLegado(field) {
        var controles = field.querySelectorAll("input[name], select[name]");
        return Array.prototype.some.call(controles, function (controle) {
            return Boolean(controle.value);
        });
    }

    function renderizarPreview(target, imagem) {
        target.textContent = "";

        if (!imagem || !imagem.src) {
            var vazio = document.createElement("span");
            vazio.textContent = target.getAttribute("data-empty-text") || "Nenhuma imagem selecionada.";
            target.appendChild(vazio);
            return;
        }

        var img = document.createElement("img");
        img.src = imagem.src;
        img.alt = imagem.alt || "Imagem selecionada";
        target.appendChild(img);
    }

    function iniciarCard(card) {
        var field = card.querySelector("[data-ownpaper-image-preview-field]");
        var target = card.querySelector("[data-ownpaper-image-preview-target]");
        if (!field || !target) {
            return;
        }

        var usuarioInteragiu = false;
        var agendado = false;

        function atualizar() {
            agendado = false;
            var imageId = valorSelecionado(field);

            if (imageId) {
                buscarPreview(card, imageId).then(function (imagemEndpoint) {
                    if (imagemEndpoint) {
                        renderizarPreview(target, imagemEndpoint);
                        return;
                    }

                    var imagemDom = encontrarImagemDoCampo(field);
                    if (imagemDom) {
                        renderizarPreview(target, imagemDom);
                    }
                });
                return;
            }

            var imagem = encontrarImagemDoCampo(field);
            if (imagem) {
                renderizarPreview(target, imagem);
                return;
            }

            if (!campoTemValorLegado(field)) {
                renderizarPreview(target, null);
            }
        }

        function agendarAtualizacao() {
            if (!usuarioInteragiu || agendado) {
                return;
            }
            agendado = true;
            window.setTimeout(atualizar, 80);
        }

        field.addEventListener("click", function () {
            usuarioInteragiu = true;
            window.setTimeout(atualizar, 400);
        }, true);

        field.addEventListener("change", function () {
            usuarioInteragiu = true;
            agendarAtualizacao();
        }, true);

        document.addEventListener("wagtail:chosen", function () {
            usuarioInteragiu = true;
            agendarAtualizacao();
        });

        if (window.MutationObserver) {
            var observer = new MutationObserver(agendarAtualizacao);
            observer.observe(field, {
                attributes: true,
                attributeFilter: ["src", "style", "class", "value"],
                childList: true,
                subtree: true
            });
        }
    }

    ready(function () {
        var cards = document.querySelectorAll("[data-ownpaper-image-preview-card]");
        Array.prototype.forEach.call(cards, iniciarCard);
    });
}());
