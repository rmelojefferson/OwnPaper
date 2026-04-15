(function () {
    var botaoTopo = document.getElementById("botao-topo");

    if (!botaoTopo) {
        return;
    }

    function atualizarVisibilidadeBotaoTopo() {
        if (window.scrollY > 300) {
            botaoTopo.classList.add("visivel");
        } else {
            botaoTopo.classList.remove("visivel");
        }
    }

    botaoTopo.addEventListener("click", function () {
        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
    });

    window.addEventListener("scroll", atualizarVisibilidadeBotaoTopo);
    atualizarVisibilidadeBotaoTopo();
})();
