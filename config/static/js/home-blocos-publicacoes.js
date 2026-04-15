(function () {
        var carrossel = document.getElementById("home-carrossel");
        var slides = document.querySelectorAll("#home-carrossel .home-carrossel-slide");
        var botaoAnterior = document.getElementById("home-carrossel-anterior");
        var botaoProximo = document.getElementById("home-carrossel-proximo");

        if (carrossel && slides.length > 1 && botaoAnterior && botaoProximo) {
            var indiceAtual = 0;
            var intervaloAutoplay = null;
            var tempoSegundos = parseInt(carrossel.getAttribute("data-tempo") || "0", 10);

            function atualizarCarrossel() {
                slides.forEach(function (slide, indice) {
                    if (indice === indiceAtual) {
                        slide.classList.add("ativo");
                    } else {
                        slide.classList.remove("ativo");
                    }
                });
            }

            function iniciarAutoplay() {
                if (tempoSegundos > 0) {
                    intervaloAutoplay = setInterval(function () {
                        indiceAtual = (indiceAtual + 1) % slides.length;
                        atualizarCarrossel();
                    }, tempoSegundos * 1000);
                }
            }

            function reiniciarAutoplay() {
                if (intervaloAutoplay) {
                    clearInterval(intervaloAutoplay);
                    intervaloAutoplay = null;
                }

                iniciarAutoplay();
            }

            botaoAnterior.addEventListener("click", function () {
                indiceAtual = (indiceAtual - 1 + slides.length) % slides.length;
                atualizarCarrossel();
                reiniciarAutoplay();
            });

            botaoProximo.addEventListener("click", function () {
                indiceAtual = (indiceAtual + 1) % slides.length;
                atualizarCarrossel();
                reiniciarAutoplay();
            });

            iniciarAutoplay();
        }

        var listaUltimas = document.getElementById("home-lista-ultimas-publicacoes");
        var itensUltimas = listaUltimas ? Array.prototype.slice.call(
            listaUltimas.querySelectorAll("[data-home-ultima-item]")
        ) : [];

        if (itensUltimas.length) {
            var quantidadeVisivel = parseInt(listaUltimas.getAttribute("data-quantidade-inicial") || "5", 10);
            var lote = 5;
            var observer = null;

            function atualizarObservador() {
                if (observer) {
                    observer.disconnect();
                }

                if (quantidadeVisivel >= itensUltimas.length) {
                    return;
                }

                var indiceGatilho = Math.max(0, quantidadeVisivel - 2);
                var alvo = itensUltimas[indiceGatilho];

                if (!alvo) {
                    return;
                }

                observer = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            var novoLimite = Math.min(quantidadeVisivel + lote, itensUltimas.length);

                            for (var i = quantidadeVisivel; i < novoLimite; i++) {
                                itensUltimas[i].hidden = false;
                            }

                            quantidadeVisivel = novoLimite;
                            atualizarObservador();
                        }
                    });
                }, {
                    rootMargin: "200px 0px"
                });

                observer.observe(alvo);
            }

            atualizarObservador();
        }
    })();
