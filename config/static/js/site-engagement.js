(function () {
    function getCookie(name) {
        var prefix = name + "=";
        return document.cookie.split(";").map(function (part) {
            return part.trim();
        }).filter(function (part) {
            return part.indexOf(prefix) === 0;
        }).map(function (part) {
            return decodeURIComponent(part.slice(prefix.length));
        })[0] || "";
    }

    if (getCookie("ownpaper_cookie_consent") !== "all") {
        return;
    }
    if (navigator.doNotTrack === "1" || window.doNotTrack === "1") {
        return;
    }

    var endpoint = "/estatisticas/tempo/";
    var sessionKey = "ownpaper_engagement_session";
    var startedKey = "ownpaper_engagement_started";
    var sessionId = sessionStorage.getItem(sessionKey);
    if (!sessionId) {
        sessionId = (window.crypto && crypto.randomUUID)
            ? crypto.randomUUID()
            : String(Date.now()) + "-" + Math.random().toString(16).slice(2);
        sessionStorage.setItem(sessionKey, sessionId);
    }

    var startedAt = sessionStorage.getItem(startedKey);
    if (!startedAt) {
        startedAt = new Date().toISOString();
        sessionStorage.setItem(startedKey, startedAt);
    }

    var pageStarted = Date.now();
    var lastSent = 0;

    function payload() {
        return JSON.stringify({
            session_id: sessionId,
            started_at: startedAt,
            path: window.location.pathname,
            duration_seconds: Math.max(0, Math.round((Date.now() - pageStarted) / 1000))
        });
    }

    function send(force) {
        var now = Date.now();
        if (!force && now - lastSent < 15000) {
            return;
        }
        lastSent = now;
        var body = payload();
        if (navigator.sendBeacon) {
            var blob = new Blob([body], { type: "application/json" });
            navigator.sendBeacon(endpoint, blob);
            return;
        }
        fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: body,
            credentials: "same-origin",
            keepalive: true
        }).catch(function () {});
    }

    window.setInterval(function () {
        if (document.visibilityState === "visible") {
            send(false);
        }
    }, 30000);

    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "hidden") {
            send(true);
        }
    });
    window.addEventListener("pagehide", function () {
        send(true);
    });
    window.addEventListener("beforeunload", function () {
        send(true);
    });

    window.setTimeout(function () {
        send(false);
    }, 5000);
})();
