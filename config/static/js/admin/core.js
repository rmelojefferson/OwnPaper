(function () {
    var admin = window.OwnPaperAdmin || (window.OwnPaperAdmin = {});
    admin.inits = admin.inits || [];

    admin.registerInit = function (name, fn) {
        admin.inits.push({ name: name, fn: fn });
        if (typeof admin.scheduleSync === 'function') {
            admin.scheduleSync();
        }
    };
            function normalizarHex(valor, fallback) {
                var texto = (valor || "").trim().toLowerCase();
                if (/^#[0-9a-f]{6}$/.test(texto)) {
                    return texto;
                }
                return fallback.toLowerCase();
            }

            function hexParaRgb(hex) {
                var cor = normalizarHex(hex, "#000000");
                return {
                    r: parseInt(cor.slice(1, 3), 16),
                    g: parseInt(cor.slice(3, 5), 16),
                    b: parseInt(cor.slice(5, 7), 16),
                };
            }

            function rgbParaHex(r, g, b) {
                function clamp(v) {
                    return Math.max(0, Math.min(255, Math.round(v)));
                }
                function part(v) {
                    return clamp(v).toString(16).padStart(2, "0");
                }
                return "#" + part(r) + part(g) + part(b);
            }

            function rgbParaHsl(r, g, b) {
                var rr = r / 255;
                var gg = g / 255;
                var bb = b / 255;
                var max = Math.max(rr, gg, bb);
                var min = Math.min(rr, gg, bb);
                var h = 0;
                var s = 0;
                var l = (max + min) / 2;
                if (max !== min) {
                    var d = max - min;
                    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
                    switch (max) {
                        case rr:
                            h = (gg - bb) / d + (gg < bb ? 6 : 0);
                            break;
                        case gg:
                            h = (bb - rr) / d + 2;
                            break;
                        default:
                            h = (rr - gg) / d + 4;
                            break;
                    }
                    h /= 6;
                }
                return { h: h, s: s, l: l };
            }

            function hslParaRgb(h, s, l) {
                function hue2rgb(p, q, t) {
                    if (t < 0) t += 1;
                    if (t > 1) t -= 1;
                    if (t < 1 / 6) return p + (q - p) * 6 * t;
                    if (t < 1 / 2) return q;
                    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
                    return p;
                }
                var r;
                var g;
                var b;
                if (s === 0) {
                    r = l;
                    g = l;
                    b = l;
                } else {
                    var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
                    var p = 2 * l - q;
                    r = hue2rgb(p, q, h + 1 / 3);
                    g = hue2rgb(p, q, h);
                    b = hue2rgb(p, q, h - 1 / 3);
                }
                return {
                    r: Math.round(r * 255),
                    g: Math.round(g * 255),
                    b: Math.round(b * 255),
                };
            }

            function clamp(v, min, max) {
                return Math.max(min, Math.min(max, v));
            }

            function sugerirCorSecundaria(corPrimaria) {
                var prim = normalizarHex(corPrimaria, "#0f172a");
                var rgb = hexParaRgb(prim);
                var hsl = rgbParaHsl(rgb.r, rgb.g, rgb.b);
                var h = (hsl.h + 38 / 360) % 1;
                var s = clamp(Math.max(0.62, hsl.s + 0.12), 0.62, 0.9);
                var l = hsl.l > 0.58 ? 0.48 : 0.56;
                var out = hslParaRgb(h, s, l);
                return rgbParaHex(out.r, out.g, out.b);
            }

            function esconderCampo(campo) {
                if (!campo) {
                    return;
                }
                var row =
                    campo.closest(".w-field") ||
                    campo.closest(".field") ||
                    campo.closest(".object") ||
                    campo.parentElement;
                if (row) {
                    row.style.display = "none";
                } else {
                    campo.style.display = "none";
                }
                var label = document.querySelector("label[for='" + campo.id + "']");
                if (label) {
                    label.style.display = "none";
                }
            }


            var agendado = false;
            function executarSeguro(nome, fn) {
                try {
                    fn();
                } catch (erro) {
                    console.warn("[OwnPaper admin]", nome, erro);
                }
            }

            function sincronizarUI() {
                agendado = false;
                (admin.inits || []).forEach(function (item) {
                    executarSeguro(item.name, item.fn);
                });
            }

            function agendarSincronizacao() {
                if (agendado) {
                    return;
                }
                agendado = true;
                if (window.requestAnimationFrame) {
                    window.requestAnimationFrame(sincronizarUI);
                } else {
                    setTimeout(sincronizarUI, 16);
                }
            }

            if (document.readyState === "loading") {
                document.addEventListener("DOMContentLoaded", agendarSincronizacao);
            } else {
                agendarSincronizacao();
            }

            var observer = new MutationObserver(agendarSincronizacao);
            observer.observe(document.documentElement, { childList: true, subtree: true });
        
    admin.normalizarHex = normalizarHex;
    admin.hexParaRgb = hexParaRgb;
    admin.rgbParaHex = rgbParaHex;
    admin.rgbParaHsl = rgbParaHsl;
    admin.hslParaRgb = hslParaRgb;
    admin.clamp = clamp;
    admin.sugerirCorSecundaria = sugerirCorSecundaria;
    admin.esconderCampo = esconderCampo;
    admin.safeRun = executarSeguro;
    admin.syncUI = sincronizarUI;
    admin.scheduleSync = agendarSincronizacao;
})();
