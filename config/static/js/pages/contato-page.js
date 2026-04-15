(function () {
    var mensagemSucesso = document.getElementById("mensagem-sucesso-contato");
    var mensagemLimite = document.getElementById("mensagem-limite-contato");
    var mensagemCaptcha = document.getElementById("mensagem-captcha-contato");

    function limparMensagem(elemento, params) {
        if (!elemento) {
            return;
        }

        setTimeout(function () {
            elemento.style.display = "none";

            var url = new URL(window.location.href);
            params.forEach(function (param) {
                url.searchParams.delete(param);
            });
            window.history.replaceState({}, document.title, url.pathname + url.search);
        }, 4000);
    }

    limparMensagem(mensagemSucesso, ["enviado", "email_falhou"]);
    limparMensagem(mensagemLimite, ["limite"]);
    limparMensagem(mensagemCaptcha, ["captcha"]);
})();
