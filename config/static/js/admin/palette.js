(function () {
    var admin = window.OwnPaperAdmin;
    if (!admin) {
        return;
    }
    var normalizarHex = admin.normalizarHex;
    var sugerirCorSecundaria = admin.sugerirCorSecundaria;
    var esconderCampo = admin.esconderCampo;
function vincularSugestaoPaleta() {
    var campoPrimaria = document.querySelector(
        "#id_paleta_cor_1, [name='paleta_cor_1'], [name$='paleta_cor_1']"
    );
    var campoSecundaria = document.querySelector(
        "#id_paleta_cor_2, [name='paleta_cor_2'], [name$='paleta_cor_2']"
    );
    if (!campoPrimaria || !campoSecundaria) {
        return;
    }
    var sincronizandoLigacao = false;

    var familias = [
        ["#1d4ed8", "#2563eb", "#60a5fa", "#93c5fd", "#dbeafe"],
        ["#15803d", "#16a34a", "#4ade80", "#86efac", "#dcfce7"],
        ["#ca8a04", "#eab308", "#facc15", "#fde047", "#fef9c3"],
        ["#9a3412", "#c2410c", "#ea580c", "#fdba74", "#ffedd5"],
        ["#9f1239", "#be123c", "#db2777", "#f472b6", "#fce7f3"],
        ["#6d28d9", "#7c3aed", "#a78bfa", "#c4b5fd", "#ede9fe"],
        ["#78350f", "#92400e", "#b45309", "#d6a36a", "#f3e0c7"],
        ["#475569", "#64748b", "#94a3b8", "#cbd5e1", "#ffffff"],
        ["#000000", "#111827", "#1f2937", "#374151", "#6b7280"],
    ];
    var coresRecentesPadrao = ["#5b6ee1", "#14b8a6", "#f59e0b", "#ef4444", "#db2777", "#8b5cf6", "#94a3b8", "#111827"];

    function uniqueColors(lista, fallback) {
        var out = [];
        (lista || []).forEach(function (cor) {
            var hex = normalizarHex(cor, fallback || '#000000');
            if (out.indexOf(hex) === -1) {
                out.push(hex);
            }
        });
        return out;
    }

    function abrirPickerNativo(input) {
        if (!input) {
            return;
        }
        if (typeof input.showPicker === 'function') {
            input.showPicker();
        } else {
            input.click();
        }
    }

    function buildToneButton(cor, ativa, onClick) {
        var botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'op-admin-palette-tone' + (ativa ? ' is-active' : '');
        botao.style.setProperty('--op-palette-color', cor);
        botao.setAttribute('aria-label', 'Selecionar ' + cor.toUpperCase());
        botao.title = cor.toUpperCase();
        botao.addEventListener('click', function () {
            onClick(cor);
        });
        return botao;
    }

    function melhorarCampoPaleta(campo, tipo, outroCampo) {
        if (!campo || campo.dataset.opPaletaEnhanced === '1') {
            return null;
        }
        campo.dataset.opPaletaEnhanced = '1';
        var padrao = tipo === 'primaria' ? '#0f172a' : '#1d4ed8';
        var atual = normalizarHex(campo.value || padrao, padrao);
        var pendente = atual;
        var coresRecentes = uniqueColors([atual, sugerirCorSecundaria(atual)].concat(coresRecentesPadrao), padrao).slice(0, 8);

        var shell = document.createElement('div');
        shell.className = 'op-admin-palette-shell';
        var toolbar = document.createElement('div');
        toolbar.className = 'op-admin-palette-toolbar';

        var trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'op-admin-palette-trigger';
        trigger.setAttribute('aria-expanded', 'false');
        var triggerSwatch = document.createElement('span');
        triggerSwatch.className = 'op-admin-palette-trigger-swatch';
        var triggerText = document.createElement('span');
        triggerText.className = 'op-admin-palette-trigger-text';
        var triggerStrong = document.createElement('strong');
        triggerStrong.textContent = tipo === 'primaria' ? 'Cor 1' : 'Cor 2';
        var triggerSubtext = document.createElement('span');
        triggerSubtext.textContent = 'Selecionar cor';
        triggerText.appendChild(triggerStrong);
        triggerText.appendChild(triggerSubtext);
        trigger.appendChild(triggerSwatch);
        trigger.appendChild(triggerText);

        var inputHexInline = document.createElement('input');
        inputHexInline.type = 'text';
        inputHexInline.inputMode = 'text';
        inputHexInline.maxLength = 7;
        inputHexInline.placeholder = '#1D4ED8';
        inputHexInline.className = 'op-admin-palette-hex-inline';
        inputHexInline.setAttribute('aria-label', tipo === 'primaria' ? 'Hexadecimal da cor 1' : 'Hexadecimal da cor 2');

        var picker = document.createElement('input');
        picker.type = 'color';
        picker.className = 'op-admin-palette-native-picker';
        picker.tabIndex = -1;

        var panel = document.createElement('div');
        panel.className = 'op-admin-palette-panel';
        var windowEl = document.createElement('div');
        windowEl.className = 'op-admin-palette-window';
        var headerbar = document.createElement('div');
        headerbar.className = 'op-admin-palette-headerbar';
        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'op-admin-palette-action';
        cancelBtn.textContent = 'Cancelar';
        var title = document.createElement('strong');
        title.textContent = 'Paleta';
        var selectBtn = document.createElement('button');
        selectBtn.type = 'button';
        selectBtn.className = 'op-admin-palette-action op-admin-palette-action--primary';
        selectBtn.textContent = 'Selecionar';
        headerbar.appendChild(cancelBtn);
        headerbar.appendChild(title);
        headerbar.appendChild(selectBtn);

        var body = document.createElement('div');
        body.className = 'op-admin-palette-body';
        var paletteArea = document.createElement('div');
        paletteArea.className = 'op-admin-palette-area';
        var mainGrid = document.createElement('div');
        mainGrid.className = 'op-admin-palette-main-grid';
        var customGroup = document.createElement('div');
        customGroup.className = 'op-admin-palette-custom-group';
        var customLabel = document.createElement('span');
        customLabel.className = 'op-admin-palette-custom-label';
        customLabel.textContent = 'Custom';
        var customRow = document.createElement('div');
        customRow.className = 'op-admin-palette-custom-row';
        customGroup.appendChild(customLabel);
        customGroup.appendChild(customRow);
        paletteArea.appendChild(mainGrid);
        paletteArea.appendChild(customGroup);

        body.appendChild(paletteArea);
        windowEl.appendChild(headerbar);
        windowEl.appendChild(body);
        panel.appendChild(windowEl);

        var sugestaoBox = document.createElement('div');
        sugestaoBox.className = 'op-admin-palette-suggestion';
        var sugestaoHead = document.createElement('div');
        sugestaoHead.className = 'op-admin-palette-suggestion-head';
        var sugestaoHeadStrong = document.createElement('strong');
        sugestaoHeadStrong.textContent = tipo === 'primaria' ? 'Sugestão para Cor 2' : 'Sugestão para Cor 1';
        var sugestaoHeadText = document.createElement('span');
        sugestaoHeadText.textContent = 'Baseada na cor aplicada no campo atual.';
        sugestaoHead.appendChild(sugestaoHeadStrong);
        sugestaoHead.appendChild(sugestaoHeadText);
        var sugestaoInfo = document.createElement('div');
        sugestaoInfo.className = 'op-admin-palette-suggestion-info';
        var sugestaoSwatch = document.createElement('span');
        sugestaoSwatch.className = 'op-admin-palette-suggestion-swatch';
        var sugestaoHex = document.createElement('code');
        sugestaoHex.className = 'op-admin-palette-suggestion-hex';
        var sugestaoBotao = document.createElement('button');
        sugestaoBotao.type = 'button';
        sugestaoBotao.className = 'op-admin-palette-suggestion-apply';
        sugestaoBotao.textContent = tipo === 'primaria' ? 'Aplicar na Cor 2' : 'Aplicar na Cor 1';
        sugestaoInfo.appendChild(sugestaoSwatch);
        sugestaoInfo.appendChild(sugestaoHex);
        sugestaoInfo.appendChild(sugestaoBotao);
        sugestaoBox.appendChild(sugestaoHead);
        sugestaoBox.appendChild(sugestaoInfo);

        campo.style.display = 'none';
        toolbar.appendChild(trigger);
        toolbar.appendChild(inputHexInline);
        shell.appendChild(toolbar);
        shell.appendChild(picker);
        shell.appendChild(panel);
        shell.appendChild(sugestaoBox);
        campo.insertAdjacentElement('afterend', shell);

        function renderizarGradePrincipal() {
            mainGrid.replaceChildren();
            familias.forEach(function (familia) {
                var coluna = document.createElement('div');
                coluna.className = 'op-admin-palette-tone-col';
                familia.forEach(function (cor) {
                    coluna.appendChild(buildToneButton(cor, normalizarHex(pendente, atual) === normalizarHex(cor, atual), function (selecionada) {
                        setPendente(selecionada);
                    }));
                });
                mainGrid.appendChild(coluna);
            });
        }

        function renderizarCustom() {
            customRow.replaceChildren();
            var plus = document.createElement('button');
            plus.type = 'button';
            plus.className = 'op-admin-palette-custom-add';
            plus.textContent = '+';
            plus.addEventListener('click', function () {
                abrirPickerNativo(picker);
            });
            customRow.appendChild(plus);
            coresRecentes.slice(0, 8).forEach(function (cor) {
                customRow.appendChild(buildToneButton(cor, normalizarHex(pendente, atual) === normalizarHex(cor, atual), function (selecionada) {
                    setPendente(selecionada);
                }));
            });
        }

        function renderizarTudo() {
            trigger.querySelector('.op-admin-palette-trigger-swatch').style.background = atual;
            trigger.querySelector('.op-admin-palette-trigger-text span').textContent = atual.toUpperCase();
            inputHexInline.value = atual.toUpperCase();
            picker.value = atual;
            renderizarGradePrincipal();
            renderizarCustom();
        }

        function registrarCorRecente(cor) {
            var hex = normalizarHex(cor, atual);
            coresRecentes = uniqueColors([hex].concat(coresRecentes), hex).slice(0, 8);
        }

        function setPendente(valor) {
            pendente = normalizarHex(valor, atual);
            picker.value = pendente;
            renderizarGradePrincipal();
            renderizarCustom();
            atualizarSugestao();
        }

        function aplicarCampo(valor, manual, dispararEventos) {
            var proximo = normalizarHex(valor, atual || padrao);
            var flagAuto = manual === false ? '1' : '0';
            var mudouValor = proximo !== atual;
            var mudouFlag = campo.dataset.opAutoSuggested !== flagAuto;
            atual = proximo;
            pendente = atual;
            campo.value = atual;
            campo.dataset.opAutoSuggested = flagAuto;
            coresRecentes = uniqueColors([atual].concat(coresRecentes), atual).slice(0, 8);
            renderizarTudo();
            if (dispararEventos !== false && (mudouValor || mudouFlag)) {
                campo.dispatchEvent(new Event('input', { bubbles: true }));
                campo.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        function fecharPanel(reverter) {
            panel.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
            if (reverter) {
                pendente = atual;
                renderizarGradePrincipal();
                renderizarCustom();
            }
            atualizarSugestao();
        }

        function abrirPanel() {
            pendente = atual;
            panel.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
            renderizarGradePrincipal();
            renderizarCustom();
            atualizarSugestao();
        }

        function alternarPanel() {
            if (panel.classList.contains('is-open')) {
                fecharPanel(true);
            } else {
                abrirPanel();
            }
        }

        function aplicarHexManual(input) {
            var valor = (input.value || '').trim();
            if (!/^#[0-9a-f]{6}$/i.test(valor)) {
                input.value = atual.toUpperCase();
                return;
            }
            aplicarCampo(valor, true);
        }

        function atualizarSugestao() {
            var baseSugestao = panel.classList.contains('is-open') ? pendente : (campo.value || padrao);
            var sugerida = sugerirCorSecundaria(baseSugestao);
            sugestaoSwatch.style.background = sugerida;
            sugestaoHex.textContent = sugerida.toUpperCase();
            sugestaoBotao.onclick = function () {
                if (sincronizandoLigacao) {
                    return;
                }
                sincronizandoLigacao = true;
                if (outroCampo && outroCampo._opPaletaUI) {
                    outroCampo._opPaletaUI.setValue(sugerida, false, false);
                } else if (outroCampo) {
                    outroCampo.value = sugerida;
                    outroCampo.dataset.opAutoSuggested = '1';
                }
                sincronizandoLigacao = false;
                atualizarLigacao();
            };
            if (outroCampo && (!outroCampo.value || outroCampo.dataset.opAutoSuggested === '1')) {
                if (sincronizandoLigacao) {
                    return;
                }
                sincronizandoLigacao = true;
                if (outroCampo._opPaletaUI) {
                    outroCampo._opPaletaUI.setValue(sugerida, false, false);
                } else {
                    outroCampo.value = sugerida;
                    outroCampo.dataset.opAutoSuggested = '1';
                }
                sincronizandoLigacao = false;
            }
        }

        trigger.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            alternarPanel();
        });
        panel.addEventListener('click', function (event) {
            event.stopPropagation();
        });
        cancelBtn.addEventListener('click', function () {
            fecharPanel(true);
        });
        selectBtn.addEventListener('click', function () {
            aplicarCampo(pendente, true);
            fecharPanel(false);
        });
        inputHexInline.addEventListener('change', function () {
            aplicarHexManual(inputHexInline);
        });
        inputHexInline.addEventListener('blur', function () {
            aplicarHexManual(inputHexInline);
        });
        inputHexInline.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                aplicarHexManual(inputHexInline);
            }
        });
        function tratarPickerCustom(confirmarRecente) {
            if (confirmarRecente) {
                registrarCorRecente(picker.value);
            }
            setPendente(picker.value);
            if (!panel.classList.contains('is-open')) {
                abrirPanel();
            }
        }
        picker.addEventListener('input', function () {
            tratarPickerCustom(false);
        });
        picker.addEventListener('change', function () {
            tratarPickerCustom(true);
        });
        document.addEventListener('click', function (evento) {
            var caminho = typeof evento.composedPath === 'function' ? evento.composedPath() : [];
            if (caminho.indexOf(shell) === -1 && !shell.contains(evento.target)) {
                fecharPanel(true);
            }
        });

        var api = {
            field: campo,
            setValue: function (valor, marcadaComoManual, dispararEventos) {
                aplicarCampo(valor, marcadaComoManual !== false, dispararEventos);
                atualizarSugestao();
            },
            refreshSuggestion: atualizarSugestao,
        };

        campo._opPaletaUI = api;
        renderizarTudo();
        atualizarSugestao();
        return api;
    }

    if (campoPrimaria.dataset.opPaletaLigada === '1' || campoSecundaria.dataset.opPaletaLigada === '1') {
        return;
    }
    campoPrimaria.dataset.opPaletaLigada = '1';
    campoSecundaria.dataset.opPaletaLigada = '1';

    var uiPrimaria = melhorarCampoPaleta(campoPrimaria, 'primaria', campoSecundaria);
    var uiSecundaria = melhorarCampoPaleta(campoSecundaria, 'secundaria', campoPrimaria);

    if (!campoSecundaria.value) {
        campoSecundaria.value = sugerirCorSecundaria(campoPrimaria.value || '#0f172a');
        if (uiSecundaria) {
            uiSecundaria.setValue(campoSecundaria.value, false, false);
        }
        campoSecundaria.dataset.opAutoSuggested = '1';
    }
    if (!campoPrimaria.value) {
        campoPrimaria.value = sugerirCorSecundaria(campoSecundaria.value || '#1d4ed8');
        if (uiPrimaria) {
            uiPrimaria.setValue(campoPrimaria.value, false, false);
        }
        campoPrimaria.dataset.opAutoSuggested = '1';
    }

    function atualizarLigacao() {
        if (sincronizandoLigacao) {
            return;
        }
        if (uiPrimaria) {
            uiPrimaria.refreshSuggestion();
        }
        if (uiSecundaria) {
            uiSecundaria.refreshSuggestion();
        }
    }

    campoPrimaria.addEventListener('input', atualizarLigacao);
    campoPrimaria.addEventListener('change', atualizarLigacao);
    campoSecundaria.addEventListener('input', atualizarLigacao);
    campoSecundaria.addEventListener('change', atualizarLigacao);
    atualizarLigacao();
}

    admin.registerInit('vincularSugestaoPaleta', vincularSugestaoPaleta);
})();
