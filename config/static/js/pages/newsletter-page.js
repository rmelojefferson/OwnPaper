(function () {
    var ids = [
        "msg-sucesso",
        "msg-confirmado",
        "msg-descadastrado",
        "msg-cancelamento-enviado",
        "msg-cancelamento-email-falhou",
        "msg-privacidade",
        "msg-privacidade-email-falhou",
        "msg-privacidade-confirmacao-exclusao-enviada",
        "msg-privacidade-confirmacao-exclusao-email-falhou",
        "msg-privacidade-exclusao-confirmada",
        "msg-privacidade-exclusao-confirmada-email-falhou",
        "msg-privacidade-token-invalido",
        "msg-privacidade-token-expirado",
        "msg-existente",
        "msg-token-expirado",
        "msg-token-invalido",
        "msg-limite",
        "msg-captcha",
        "msg-email-falhou"
    ];

    setTimeout(function () {
        ids.forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.style.display = "none";
            }
        });

        window.history.replaceState({}, document.title, window.location.pathname);
    }, 5000);
})();
