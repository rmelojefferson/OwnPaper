(function () {
    function initHomeCarousel() {
        var carrossel = document.getElementById("home-carrossel");
        if (!carrossel) return;
        if (carrossel.dataset.jsReady === "1") return;
        carrossel.dataset.jsReady = "1";

        var slides = Array.prototype.slice.call(
            carrossel.querySelectorAll(".home-carrossel-slide")
        );
        var botaoAnterior = document.getElementById("home-carrossel-anterior");
        var botaoProximo = document.getElementById("home-carrossel-proximo");

        if (!slides.length) return;

        var indiceAtual = 0;
        var autoplayTimer = null;
        var tempoSegundos = parseInt(carrossel.getAttribute("data-tempo") || "0", 10);

        function atualizarCarrossel() {
            slides.forEach(function (slide, indice) {
                slide.classList.toggle("ativo", indice === indiceAtual);
            });
        }

        function irPara(indice) {
            indiceAtual = (indice + slides.length) % slides.length;
            atualizarCarrossel();
        }

        function proximoSlide() {
            irPara(indiceAtual + 1);
        }

        function slideAnterior() {
            irPara(indiceAtual - 1);
        }

        function pararAutoplay() {
            if (!autoplayTimer) return;
            clearInterval(autoplayTimer);
            autoplayTimer = null;
        }

        function iniciarAutoplay() {
            if (!(tempoSegundos > 0) || slides.length <= 1) return;
            autoplayTimer = setInterval(function () {
                proximoSlide();
            }, tempoSegundos * 1000);
        }

        function reiniciarAutoplay() {
            pararAutoplay();
            iniciarAutoplay();
        }

        if (botaoAnterior) {
            botaoAnterior.addEventListener("click", function (evento) {
                evento.preventDefault();
                evento.stopPropagation();
                slideAnterior();
                reiniciarAutoplay();
            });
        }

        if (botaoProximo) {
            botaoProximo.addEventListener("click", function (evento) {
                evento.preventDefault();
                evento.stopPropagation();
                proximoSlide();
                reiniciarAutoplay();
            });
        }

        carrossel.querySelectorAll(".home-carrossel-link").forEach(function (link) {
            link.setAttribute("draggable", "false");
        });

        carrossel.addEventListener("dragstart", function (evento) {
            evento.preventDefault();
        });

        atualizarCarrossel();
        iniciarAutoplay();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initHomeCarousel, { once: true });
    } else {
        initHomeCarousel();
    }
})();
