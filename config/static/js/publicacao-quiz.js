(function () {
    var root = document.querySelector("[data-quiz-publicacao]");
    if (!root) return;

    var perguntas = Array.prototype.slice.call(root.querySelectorAll("[data-quiz-pergunta]"));
    if (!perguntas.length) return;

    var idx = 0;
    var respostas = perguntas.map(function () {
        return { correta: null, selecionadas: [], pulada: false };
    });

    var btnAnterior = root.querySelector("[data-quiz-anterior]");
    var btnPular = root.querySelector("[data-quiz-pular]");
    var btnProximo = root.querySelector("[data-quiz-proximo]");
    var btnFinalizar = root.querySelector("[data-quiz-finalizar]");
    var btnRefazer = root.querySelector("[data-quiz-refazer]");
    var resultado = root.querySelector("[data-quiz-resultado]");
    var finishAnytime = root.getAttribute("data-quiz-finish-anytime") === "1";
    var msgCorrect = root.getAttribute("data-msg-correct") || "Resposta correta.";
    var msgWrong = root.getAttribute("data-msg-wrong") || "Resposta incorreta.";
    var msgResultPrefix = root.getAttribute("data-msg-result-prefix") || "Você acertou";
    var msgResultMid = root.getAttribute("data-msg-result-mid") || "de";
    var msgResultAnswered = root.getAttribute("data-msg-result-answered") || "respondidas";
    var msgResultAnsweredOnly = root.getAttribute("data-msg-result-answered-only") || "perguntas respondidas";
    var msgResultCorrect = root.getAttribute("data-msg-result-correct") || "corretas";
    var msgResultWrong = root.getAttribute("data-msg-result-wrong") || "erradas";
    var msgResultSkipped = root.getAttribute("data-msg-result-skipped") || "puladas";
    var msgResultAverage = root.getAttribute("data-msg-result-average") || "média";
    var msgHistoryCorrect = root.getAttribute("data-msg-history-correct") || msgResultCorrect;
    var msgHistoryWrong = root.getAttribute("data-msg-history-wrong") || msgResultWrong;
    var msgHistorySkipped = root.getAttribute("data-msg-history-skipped") || msgResultSkipped;
    var quizContext = root.getAttribute("data-quiz-context") || "";
    var quizPageUrl = root.getAttribute("data-quiz-page-url") || window.location.pathname || "/quiz/";
    var sessionSaveUrl = root.getAttribute("data-quiz-session-save-url") || "";
    var sessionAuthenticated = root.getAttribute("data-quiz-session-authenticated") === "1";
    var answerSaveUrl = root.getAttribute("data-quiz-answer-save-url") || "";
    var answerAuthenticated = root.getAttribute("data-quiz-answer-authenticated") === "1";
    var csrfToken = root.getAttribute("data-quiz-csrf-token") || "";
    var currentThemeFilter = root.getAttribute("data-quiz-current-theme-filter") || "";
    var currentTagFilter = root.getAttribute("data-quiz-current-tag-filter") || "";
    var msgLastCorrect = root.getAttribute("data-msg-last-correct") || "Última resposta: correta";
    var msgLastWrong = root.getAttribute("data-msg-last-wrong") || "Última resposta: errada";

    var currentPublicacoesRoot = document.querySelector("[data-quiz-estudo-publicacoes-atual]");
    var currentPublicacoesList = document.querySelector("[data-quiz-estudo-publicacoes-atual-lista]");
    var reviewRoot = document.querySelector("[data-quiz-estudo-revisao]");
    var reviewThemes = document.querySelector("[data-quiz-estudo-revisao-temas]");
    var reviewThemesList = document.querySelector("[data-quiz-estudo-revisao-temas-lista]");
    var reviewTags = document.querySelector("[data-quiz-estudo-revisao-tags]");
    var reviewTagsList = document.querySelector("[data-quiz-estudo-revisao-tags-lista]");
    var reviewPublicacoes = document.querySelector("[data-quiz-estudo-revisao-publicacoes]");
    var reviewPublicacoesList = document.querySelector("[data-quiz-estudo-revisao-publicacoes-lista]");
    var reviewEmpty = document.querySelector("[data-quiz-estudo-revisao-vazio]");
    var reviewSource = document.querySelector("[data-quiz-estudo-origens-fonte]");
    var historyList = document.querySelector("[data-quiz-historico-lista]");
    var historyEmpty = document.querySelector("[data-quiz-historico-vazio]");
    var historySummary = document.querySelector("[data-quiz-history-summary]");
    var historySummaryWheel = document.querySelector("[data-quiz-history-summary-wheel]");
    var historySummaryPercent = document.querySelector("[data-quiz-history-summary-percent]");
    var historySummaryMeta = document.querySelector("[data-quiz-history-summary-meta]");
    var historySummaryLegend = document.querySelector("[data-quiz-history-summary-legend]");
    var scoreModal = document.querySelector("[data-quiz-score-modal]");
    var scoreWheel = document.querySelector("[data-quiz-score-wheel]");
    var scorePercentual = document.querySelector("[data-quiz-score-percentual]");
    var scoreResumo = document.querySelector("[data-quiz-score-resumo]");
    var scoreLegenda = document.querySelector("[data-quiz-score-legenda]");
    var skippedIndices = new Set();

    function limparPulo(i) {
        if (!respostas[i]) {
            return;
        }
        respostas[i].pulada = false;
        skippedIndices.delete(i);
    }

    function marcarPulo(i) {
        if (!respostas[i]) {
            return;
        }
        respostas[i].pulada = true;
        skippedIndices.add(i);
    }

    function render() {
        perguntas.forEach(function (pergunta, i) {
            pergunta.hidden = i !== idx;
        });
        if (btnAnterior) btnAnterior.disabled = idx <= 0;
        if (btnProximo) btnProximo.hidden = idx >= perguntas.length - 1;
        if (btnFinalizar) btnFinalizar.hidden = !finishAnytime && idx < perguntas.length - 1;
        perguntas.forEach(function (pergunta, i) {
            pergunta.querySelectorAll("[data-quiz-responder]").forEach(function (botao) {
                botao.hidden = i !== idx || respostas[i].correta !== null;
            });
        });
        renderCurrentPublicacoes();
    }

    function marcar(pergunta, correta) {
        var feedback = pergunta.querySelector("[data-quiz-feedback]");
        var explicacao = pergunta.querySelector("[data-quiz-explicacao]");
        if (feedback) {
            feedback.hidden = false;
            feedback.textContent = correta ? msgCorrect : msgWrong;
        }
        if (explicacao) {
            explicacao.hidden = false;
        }
    }

    function atualizarIndicadorUltimaResposta(pergunta, correta) {
        if (!pergunta) {
            return;
        }
        var indicador = pergunta.querySelector("[data-quiz-status-indicator]");
        if (!indicador) {
            return;
        }
        indicador.hidden = false;
        indicador.classList.toggle("is-correct", correta === true);
        indicador.classList.toggle("is-wrong", correta === false);
        indicador.textContent = correta ? msgLastCorrect : msgLastWrong;
        pergunta.setAttribute("data-quiz-last-status", correta ? "correct" : "wrong");
    }

    function salvarRespostaPergunta(pergunta, i) {
        if (!answerAuthenticated || !answerSaveUrl || !window.fetch || !pergunta) {
            return;
        }
        var questionId = parseInt(pergunta.getAttribute("data-quiz-question-id") || "0", 10);
        var questionKind = pergunta.getAttribute("data-quiz-question-kind") || "";
        if (!questionId || !questionKind || respostas[i].correta === null) {
            return;
        }
        try {
            window.fetch(answerSaveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({
                    question_id: questionId,
                    question_kind: questionKind,
                    correta: respostas[i].correta === true,
                    selecionadas: respostas[i].selecionadas || []
                })
            })
                .then(function (response) {
                    if (!response.ok) {
                        return null;
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (!data || !data.ok || !data.answer) {
                        return;
                    }
                    atualizarIndicadorUltimaResposta(pergunta, data.answer.correta === true);
                })
                .catch(function () {});
        } catch (err) {}
    }

    function avaliarPergunta(pergunta, i) {
        var opcoes = Array.prototype.slice.call(pergunta.querySelectorAll("[data-quiz-opcao]"));
        var selecionadas = opcoes
            .filter(function (opcao) {
                return opcao.classList.contains("is-selected");
            })
            .map(function (opcao) {
                return parseInt(opcao.getAttribute("data-quiz-opcao-index") || "0", 10);
            });

        if (!selecionadas.length) {
            return false;
        }

        var corretas = opcoes
            .filter(function (opcao) {
                return opcao.getAttribute("data-correta") === "1";
            })
            .map(function (opcao) {
                return parseInt(opcao.getAttribute("data-quiz-opcao-index") || "0", 10);
            });

        var multi = pergunta.getAttribute("data-quiz-multi") === "1";
        var requireAll = pergunta.getAttribute("data-quiz-require-all") === "1";
        var selecionadasSet = new Set(selecionadas);
        var corretasSet = new Set(corretas);
        var houveIncorreta = selecionadas.some(function (item) { return !corretasSet.has(item); });
        var houveCorreta = selecionadas.some(function (item) { return corretasSet.has(item); });
        var acertou = false;

        if (!multi) {
            acertou = selecionadas.length === 1 && corretasSet.has(selecionadas[0]);
        } else if (requireAll) {
            acertou = !houveIncorreta && selecionadas.length === corretas.length && corretas.every(function (item) { return selecionadasSet.has(item); });
        } else {
            acertou = !houveIncorreta && houveCorreta;
        }

        respostas[i] = { correta: acertou, selecionadas: selecionadas, pulada: false };
        limparPulo(i);
        opcoes.forEach(function (item) {
            item.disabled = true;
        });
        marcar(pergunta, acertou);
        atualizarIndicadorUltimaResposta(pergunta, acertou);
        salvarRespostaPergunta(pergunta, i);
        return true;
    }

    function sourceNodeForIndex(i) {
        var pergunta = perguntas[i];
        if (!pergunta || !reviewSource) {
            return null;
        }
        var key = pergunta.getAttribute("data-quiz-question-key") || "";
        if (!key) {
            return null;
        }
        return reviewSource.querySelector('[data-quiz-question-key="' + key + '"]');
    }

    function renderCurrentPublicacoes() {
        if (!currentPublicacoesRoot || !currentPublicacoesList) {
            return;
        }
        clearNode(currentPublicacoesList);
        var sourceNode = sourceNodeForIndex(idx);
        if (!sourceNode) {
            currentPublicacoesRoot.hidden = true;
            return;
        }
        var publicationCards = Array.prototype.slice.call(sourceNode.querySelectorAll("[data-publication-id]"));
        if (!publicationCards.length) {
            currentPublicacoesRoot.hidden = true;
            return;
        }
        publicationCards.forEach(function (card) {
            currentPublicacoesList.appendChild(card.cloneNode(true));
        });
        currentPublicacoesRoot.hidden = false;
    }

    function clearReview() {
        if (currentPublicacoesRoot) {
            currentPublicacoesRoot.hidden = true;
        }
        if (currentPublicacoesList) {
            clearNode(currentPublicacoesList);
        }
        if (reviewThemesList) {
            clearNode(reviewThemesList);
        }
        if (reviewTagsList) {
            clearNode(reviewTagsList);
        }
        if (reviewPublicacoesList) {
            clearNode(reviewPublicacoesList);
        }
        if (reviewThemes) {
            reviewThemes.hidden = true;
        }
        if (reviewTags) {
            reviewTags.hidden = true;
        }
        if (reviewPublicacoes) {
            reviewPublicacoes.hidden = true;
        }
        if (reviewEmpty) {
            reviewEmpty.hidden = true;
        }
        if (reviewRoot) {
            reviewRoot.hidden = true;
        }
    }

    function renderReview(erradas) {
        if (!reviewRoot || !reviewSource) {
            return;
        }
        clearReview();
        if (!erradas.length) {
            return;
        }

        var themesSeen = new Set();
        var tagsSeen = new Set();
        var hadThemes = false;
        var hadTags = false;
        var hadPublicacoes = false;

        erradas.forEach(function (item) {
            var pergunta = perguntas[item];
            var sourceNode = sourceNodeForIndex(item);
            if (!sourceNode || !pergunta) {
                return;
            }

            var themeNode = sourceNode.querySelector("[data-quiz-theme-label]");
            if (themeNode) {
                var themeText = (themeNode.textContent || "").trim();
                var themeSlug = (themeNode.getAttribute("data-quiz-theme-slug") || "").trim();
                var themeUrl = (themeNode.getAttribute("data-quiz-theme-url") || "").trim();
                var themeKey = themeSlug || themeText;
                if (themeText && !themesSeen.has(themeKey)) {
                    themesSeen.add(themeKey);
                    hadThemes = true;
                    if (reviewThemesList) {
                        var li = document.createElement("li");
                        li.className = "quiz-estudo-revisao-chip-item";
                        if (themeUrl || themeSlug) {
                            var link = document.createElement("a");
                            link.className = "quiz-estudo-revisao-chip quiz-estudo-revisao-chip--categoria";
                            link.href = themeUrl || (quizPageUrl + "?tema=" + encodeURIComponent(themeSlug));
                            link.target = "_blank";
                            link.rel = "noopener noreferrer";
                            link.textContent = themeText;
                            li.appendChild(link);
                        } else {
                            li.textContent = themeText;
                        }
                        reviewThemesList.appendChild(li);
                    }
                }
            }

            Array.prototype.slice.call(sourceNode.querySelectorAll("[data-quiz-tag-label]")).forEach(function (tagNode) {
                var tagText = (tagNode.textContent || "").trim();
                var tagSlug = (tagNode.getAttribute("data-quiz-tag-slug") || "").trim();
                var tagUrl = (tagNode.getAttribute("data-quiz-tag-url") || "").trim();
                var tagKey = tagSlug || tagText;
                if (tagText && !tagsSeen.has(tagKey)) {
                    tagsSeen.add(tagKey);
                    hadTags = true;
                    if (reviewTagsList) {
                        var tagLi = document.createElement("li");
                        tagLi.className = "quiz-estudo-revisao-chip-item";
                        if (tagUrl || tagSlug) {
                            var tagLink = document.createElement("a");
                            tagLink.className = "quiz-estudo-revisao-chip quiz-estudo-revisao-chip--tag";
                            tagLink.href = tagUrl || (quizPageUrl + "?tag=" + encodeURIComponent(tagSlug));
                            tagLink.target = "_blank";
                            tagLink.rel = "noopener noreferrer";
                            tagLink.textContent = tagText;
                            tagLi.appendChild(tagLink);
                        } else {
                            tagLi.textContent = tagText;
                        }
                        reviewTagsList.appendChild(tagLi);
                    }
                }
            });

            var publicationCards = Array.prototype.slice.call(sourceNode.querySelectorAll("[data-publication-id]"));
            if (reviewPublicacoesList) {
                var bloco = document.createElement("section");
                bloco.className = "quiz-estudo-revisao-bloco";
                var perguntaTitulo = document.createElement("p");
                perguntaTitulo.className = "quiz-estudo-revisao-pergunta";
                var questionLabel = "";
                var questionNode = pergunta.querySelector(".quiz-pergunta-texto");
                if (questionNode) {
                    questionLabel = (questionNode.textContent || "").trim();
                }
                perguntaTitulo.textContent = questionLabel;
                bloco.appendChild(perguntaTitulo);

                if (publicationCards.length) {
                    var lista = document.createElement("div");
                    lista.className = "home-lista-publicacoes lista-relacionadas";
                    publicationCards.forEach(function (card) {
                        lista.appendChild(card.cloneNode(true));
                    });
                    bloco.appendChild(lista);
                    hadPublicacoes = true;
                } else {
                    var vazio = document.createElement("p");
                    vazio.className = "quiz-estudo-revisao-publicacoes-vazio";
                    vazio.textContent = root.getAttribute("data-msg-review-publications-empty") || "Nenhuma publicação vinculada a esta pergunta.";
                    bloco.appendChild(vazio);
                }
                reviewPublicacoesList.appendChild(bloco);
            }
        });

        if (reviewThemes) {
            reviewThemes.hidden = !hadThemes;
        }
        if (reviewTags) {
            reviewTags.hidden = !hadTags;
        }
        if (reviewPublicacoes) {
            reviewPublicacoes.hidden = !hadPublicacoes;
        }
        if (reviewEmpty) {
            reviewEmpty.hidden = hadThemes || hadTags || hadPublicacoes;
        }
        reviewRoot.hidden = false;
        if (!reviewRoot.hidden) {
            window.setTimeout(function () {
                try {
                    reviewRoot.scrollIntoView({ behavior: "smooth", block: "start" });
                } catch (err) {
                    reviewRoot.scrollIntoView(true);
                }
            }, 80);
        }
    }

    function sessionPayload(indices, respondidas, acertos, erros, puladas, consideradas, media) {
        var temas = [];
        var tags = [];
        var publicacoes = [];
        var perguntasResumo = [];
        var seenTema = new Set();
        var seenTag = new Set();
        var seenPub = new Set();

        indices.forEach(function (item) {
            var pergunta = perguntas[item];
            var sourceNode = sourceNodeForIndex(item);
            if (!pergunta || !sourceNode) {
                return;
            }
            var textoPergunta = "";
            var questionNode = pergunta.querySelector(".quiz-pergunta-texto");
            if (questionNode) {
                textoPergunta = (questionNode.textContent || "").trim();
            }
            perguntasResumo.push({
                key: pergunta.getAttribute("data-quiz-question-key") || "",
                texto: textoPergunta,
                correta: respostas[item].correta === true ? true : respostas[item].correta === false ? false : null,
                pulada: respostas[item] && respostas[item].correta === null,
            });

            var themeNode = sourceNode.querySelector("[data-quiz-theme-label]");
            if (themeNode) {
                var themeText = (themeNode.textContent || "").trim();
                var themeSlug = (themeNode.getAttribute("data-quiz-theme-slug") || "").trim();
                var themeUrl = (themeNode.getAttribute("data-quiz-theme-url") || "").trim();
                var themeKey = themeSlug || themeText;
                if (themeText && !seenTema.has(themeKey)) {
                    seenTema.add(themeKey);
                    temas.push({ slug: themeSlug, nome: themeText, url: themeUrl });
                }
            }

            Array.prototype.slice.call(sourceNode.querySelectorAll("[data-quiz-tag-label]")).forEach(function (tagNode) {
                var tagText = (tagNode.textContent || "").trim();
                var tagSlug = (tagNode.getAttribute("data-quiz-tag-slug") || "").trim();
                var tagUrl = (tagNode.getAttribute("data-quiz-tag-url") || "").trim();
                var tagKey = tagSlug || tagText;
                if (tagText && !seenTag.has(tagKey)) {
                    seenTag.add(tagKey);
                    tags.push({ slug: tagSlug, nome: tagText, url: tagUrl });
                }
            });

            Array.prototype.slice.call(sourceNode.querySelectorAll("[data-publication-id]")).forEach(function (card) {
                var pubId = (card.getAttribute("data-publication-id") || "").trim();
                var tituloNode = card.querySelector("h3 a");
                var titulo = tituloNode ? (tituloNode.textContent || "").trim() : "";
                var url = tituloNode ? (tituloNode.getAttribute("href") || "") : "";
                if (pubId && !seenPub.has(pubId)) {
                    seenPub.add(pubId);
                    publicacoes.push({ id: pubId, titulo: titulo, url: url, pergunta: textoPergunta });
                }
            });
        });

        return {
            tema_slug: currentThemeFilter,
            tag_slug: currentTagFilter,
            respondidas: respondidas,
            corretas: acertos,
            erradas: erros,
            puladas: puladas.length,
            consideradas: consideradas,
            media: media,
            perguntas: perguntasResumo,
            temas_revisao: temas,
            tags_revisao: tags,
            publicacoes_revisao: publicacoes
        };
    }

    function persistSession(indices, respondidas, acertos, erros, puladas, consideradas, media) {
        if (!sessionAuthenticated || !sessionSaveUrl || !window.fetch) {
            return;
        }
        try {
            window.fetch(sessionSaveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify(sessionPayload(indices, respondidas, acertos, erros, puladas, consideradas, media))
            })
                .then(function (response) {
                    if (!response.ok) {
                        return null;
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (!data || !data.ok || !data.session) {
                        return;
                    }
                    updateHistorySummaryWithSession(data.session);
                    renderSavedHistorySession(data.session);
                })
                .catch(function () {});
        } catch (e) {
        }
    }

    function pluralizePt(count, singular, plural) {
        return Number(count) === 1 ? singular : plural;
    }

    function clearNode(node) {
        if (!node) {
            return;
        }
        while (node.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function buildScoreLegendItem(item) {
        var li = document.createElement("li");
        li.className = item.cls;

        var ponto = document.createElement("span");
        ponto.className = "quiz-score-legenda-ponto";

        var texto = document.createElement("span");
        texto.appendChild(document.createTextNode(item.label + ": "));

        var strong = document.createElement("strong");
        strong.textContent = String(item.count);
        texto.appendChild(strong);
        texto.appendChild(document.createTextNode(" (" + formatPercentForText(item.pct) + "%)"));

        li.appendChild(ponto);
        li.appendChild(texto);
        return li;
    }

    function percentValue(count, total) {
        total = Number(total) || 0;
        if (!total) {
            return 0;
        }
        return (Number(count) || 0) / total * 100;
    }

    function formatPercentForText(value) {
        var numero = Number(value) || 0;
        if (Math.abs(numero - Math.round(numero)) < 0.0001) {
            return String(Math.round(numero));
        }
        return numero.toFixed(2).replace(".", ",");
    }

    function renderHistorySummary(totals) {
        if (!historySummary || !historySummaryWheel || !historySummaryPercent || !historySummaryMeta || !historySummaryLegend) {
            return;
        }
        var totalSessoes = Math.max(parseInt(totals.total_sessoes || 0, 10) || 0, 0);
        var totalCorretas = Math.max(parseInt(totals.total_corretas || 0, 10) || 0, 0);
        var totalErradas = Math.max(parseInt(totals.total_erradas || 0, 10) || 0, 0);
        var totalPuladas = Math.max(parseInt(totals.total_puladas || 0, 10) || 0, 0);
        var totalConsideradas = Math.max(parseInt(totals.total_consideradas || 0, 10) || 0, 0);
        var media = percentValue(totalCorretas, totalConsideradas);
        var pctCorretas = percentValue(totalCorretas, totalConsideradas);
        var pctErradas = percentValue(totalErradas, totalConsideradas);
        var pctPuladas = percentValue(totalPuladas, totalConsideradas);

        historySummary.dataset.totalSessoes = String(totalSessoes);
        historySummary.dataset.totalCorretas = String(totalCorretas);
        historySummary.dataset.totalErradas = String(totalErradas);
        historySummary.dataset.totalPuladas = String(totalPuladas);
        historySummary.dataset.totalConsideradas = String(totalConsideradas);

        historySummaryWheel.style.setProperty(
            "--quiz-score-wheel",
            "conic-gradient(var(--quiz-score-correct, #22c55e) 0 " + pctCorretas +
            "%, var(--quiz-score-wrong, #ef4444) " + pctCorretas + "% " + (pctCorretas + pctErradas) +
            "%, var(--quiz-score-skipped, #f59e0b) " + (pctCorretas + pctErradas) + "% 100%)"
        );
        historySummaryPercent.textContent = formatPercentForText(media) + "%";
        historySummaryMeta.textContent =
            String(totalSessoes) + " " + pluralizePt(totalSessoes, "sessão salva", "sessões salvas") +
            " · " + String(totalConsideradas) + " " + pluralizePt(totalConsideradas, "questão considerada", "questões consideradas");

        clearNode(historySummaryLegend);
        [
            { label: msgHistoryCorrect, count: totalCorretas, pct: pctCorretas, cls: "is-correct" },
            { label: msgHistoryWrong, count: totalErradas, pct: pctErradas, cls: "is-wrong" },
            { label: msgHistorySkipped, count: totalPuladas, pct: pctPuladas, cls: "is-skipped" }
        ].forEach(function (item) {
            historySummaryLegend.appendChild(buildScoreLegendItem(item));
        });
    }

    function updateHistorySummaryWithSession(session) {
        if (!historySummary || !session) {
            return;
        }
        var totalSessoes = (parseInt(historySummary.dataset.totalSessoes || "0", 10) || 0) + 1;
        var totalCorretas = (parseInt(historySummary.dataset.totalCorretas || "0", 10) || 0) + (parseInt(session.corretas || 0, 10) || 0);
        var totalErradas = (parseInt(historySummary.dataset.totalErradas || "0", 10) || 0) + (parseInt(session.erradas || 0, 10) || 0);
        var totalPuladas = (parseInt(historySummary.dataset.totalPuladas || "0", 10) || 0) + (parseInt(session.puladas || 0, 10) || 0);
        var totalConsideradas = (parseInt(historySummary.dataset.totalConsideradas || "0", 10) || 0) + (parseInt(session.consideradas || 0, 10) || 0);
        renderHistorySummary({
            total_sessoes: totalSessoes,
            total_corretas: totalCorretas,
            total_erradas: totalErradas,
            total_puladas: totalPuladas,
            total_consideradas: totalConsideradas
        });
    }

    function renderSavedHistorySession(session) {
        if (!historyList || !session) {
            return;
        }
        if (historyEmpty) {
            historyEmpty.hidden = true;
        }
        var item = document.createElement("article");
        item.className = "quiz-estudo-historico-item";

        var topo = document.createElement("div");
        topo.className = "quiz-estudo-historico-topo";

        var strong = document.createElement("strong");
        strong.textContent = session.finalizado_em || "";
        topo.appendChild(strong);

        var media = document.createElement("span");
        media.textContent = String(session.media_percentual || 0) + "%";
        topo.appendChild(media);

        var barra = document.createElement("div");
        barra.className = "quiz-estudo-historico-barra";
        barra.setAttribute("aria-hidden", "true");
        var barraInner = document.createElement("span");
        barraInner.style.width = String(session.media_percentual || 0) + "%";
        barra.appendChild(barraInner);

        var resumo = document.createElement("p");
        resumo.textContent =
            String(session.corretas || 0) + " " + msgHistoryCorrect +
            " · " + String(session.erradas || 0) + " " + msgHistoryWrong +
            " · " + String(session.puladas || 0) + " " + msgHistorySkipped;

        item.appendChild(topo);
        item.appendChild(barra);
        item.appendChild(resumo);
        historyList.insertBefore(item, historyList.firstChild);
    }

    function abrirScoreModal(acertos, erros, puladas, consideradas, media) {
        if (!scoreModal || !scoreWheel || !scorePercentual || !scoreResumo || !scoreLegenda) {
            return;
        }
        var total = Math.max(consideradas, 1);
        var pctCorretas = percentValue(acertos, total);
        var pctErradas = percentValue(erros, total);
        var pctPuladas = percentValue(puladas, total);
        scoreWheel.style.setProperty(
            "--quiz-score-wheel",
            "conic-gradient(var(--quiz-score-correct, #22c55e) 0 " + pctCorretas +
            "%, var(--quiz-score-wrong, #ef4444) " + pctCorretas + "% " + (pctCorretas + pctErradas) +
            "%, var(--quiz-score-skipped, #f59e0b) " + (pctCorretas + pctErradas) + "% 100%)"
        );
        scorePercentual.textContent = formatPercentForText(media) + "%";
        scoreResumo.textContent = String(consideradas) + " " + msgResultAnsweredOnly;
        clearNode(scoreLegenda);
        [
            { label: msgResultCorrect, count: acertos, pct: pctCorretas, cls: "is-correct" },
            { label: msgResultWrong, count: erros, pct: pctErradas, cls: "is-wrong" },
            { label: msgResultSkipped, count: puladas, pct: pctPuladas, cls: "is-skipped" }
        ].forEach(function (item) {
            scoreLegenda.appendChild(buildScoreLegendItem(item));
        });
        scoreModal.hidden = false;
        document.body.classList.add("comentario-popup-open");
    }

    function fecharScoreModal() {
        if (!scoreModal) {
            return;
        }
        scoreModal.hidden = true;
        document.body.classList.remove("comentario-popup-open");
    }

    function finishQuiz() {
        var currentQuestion = perguntas[idx];
        var maxIndex = idx;
        if (currentQuestion && respostas[idx].correta === null) {
            var hasSelection = currentQuestion.querySelector(".quiz-opcao.is-selected");
            if (hasSelection) {
                if (!avaliarPergunta(currentQuestion, idx)) {
                    return;
                }
            } else if (!finishAnytime) {
                return;
            }
        }

        var respondidas = respostas.filter(function (item, i) {
            return i <= maxIndex && item.correta !== null;
        }).length;
        var acertos = respostas.filter(function (item, i) {
            return i <= maxIndex && item.correta === true;
        }).length;
        var erros = respostas.filter(function (item, i) {
            return i <= maxIndex && item.correta === false;
        }).length;
        var puladas = respostas
            .map(function (item, i) {
                return {
                    pulada: item.correta === null && item.pulada === true,
                    index: i
                };
            })
            .filter(function (item) { return item.index <= maxIndex && item.pulada; })
            .map(function (item) { return item.index; });
        Array.prototype.slice.call(skippedIndices).forEach(function (i) {
            if (puladas.indexOf(i) === -1) {
                skippedIndices.delete(i);
            }
        });
        var recomendadas = respostas
            .map(function (item, i) { return { valor: item.correta, index: i }; })
            .filter(function (item) { return item.valor === false; })
            .map(function (item) { return item.index; })
            .filter(function (i) { return i <= maxIndex; });
        puladas.forEach(function (i) {
            if (recomendadas.indexOf(i) === -1) {
                recomendadas.push(i);
            }
        });
        recomendadas.sort(function (a, b) { return a - b; });
        var sessoesIndices = respostas
            .map(function (item, i) {
                return { item: item, index: i };
            })
            .filter(function (entry) {
                return entry.index <= maxIndex && (entry.item.correta !== null || entry.item.pulada === true);
            })
            .map(function (entry) {
                return entry.index;
            });
        var consideradas = respondidas + puladas.length;
        var media = percentValue(acertos, consideradas);

        if (resultado) {
            if (finishAnytime || quizContext === "pagina-quiz") {
                resultado.hidden = true;
                resultado.textContent = "";
            } else {
                resultado.hidden = false;
                resultado.textContent =
                    msgResultPrefix + " " + acertos + " " + msgResultMid + " " + perguntas.length +
                    " (" + msgResultAnswered + ": " + respondidas + ").";
            }
        }

        if (btnRefazer) {
            btnRefazer.hidden = recomendadas.length === 0;
            btnRefazer.dataset.erradas = JSON.stringify(recomendadas);
        }

        if (currentPublicacoesRoot) {
            currentPublicacoesRoot.hidden = true;
        }
        if (currentPublicacoesList) {
            clearNode(currentPublicacoesList);
        }
        renderReview(recomendadas);
        if (consideradas > 0) {
            persistSession(sessoesIndices, respondidas, acertos, erros, puladas, consideradas, media);
        }
        abrirScoreModal(acertos, erros, puladas.length, consideradas, media);
    }

    perguntas.forEach(function (pergunta, i) {
        var opcoes = Array.prototype.slice.call(pergunta.querySelectorAll("[data-quiz-opcao]"));
        opcoes.forEach(function (opcao) {
            opcao.addEventListener("click", function () {
                if (opcao.disabled) {
                    return;
                }
                var multi = pergunta.getAttribute("data-quiz-multi") === "1";
                if (!multi) {
                    opcoes.forEach(function (item) {
                        item.classList.remove("is-selected");
                    });
                    opcao.classList.add("is-selected");
                    return;
                }
                opcao.classList.toggle("is-selected");

                if (quizContext === "pagina-quiz" && i >= perguntas.length - 1 && !multi) {
                    if (avaliarPergunta(pergunta, i)) {
                        finishQuiz();
                    }
                }
            });
        });

        pergunta.querySelectorAll("[data-quiz-ajuda-toggle]").forEach(function (botao) {
            botao.addEventListener("click", function () {
                var painel = pergunta.querySelector("[data-quiz-ajuda-painel]");
                if (!painel) {
                    return;
                }
                painel.hidden = !painel.hidden;
                botao.classList.toggle("is-active", !painel.hidden);
                botao.setAttribute("aria-expanded", String(!painel.hidden));
            });
        });

        pergunta.querySelectorAll("[data-quiz-responder]").forEach(function (botao) {
            botao.addEventListener("click", function () {
                if (respostas[i].correta !== null) {
                    return;
                }
                if (!avaliarPergunta(pergunta, i)) {
                    return;
                }
                if (i >= perguntas.length - 1) {
                    finishQuiz();
                    return;
                }
                render();
            });
        });
    });

    if (btnAnterior) {
        btnAnterior.addEventListener("click", function () {
            idx = Math.max(0, idx - 1);
            render();
        });
    }

    if (btnProximo) {
        btnProximo.addEventListener("click", function () {
            if (respostas[idx].correta === null) {
                if (!avaliarPergunta(perguntas[idx], idx)) {
                    return;
                }
            }
            if (idx >= perguntas.length - 1) {
                finishQuiz();
                return;
            }
            idx = Math.min(perguntas.length - 1, idx + 1);
            render();
        });
    }

    if (btnPular) {
        btnPular.addEventListener("click", function () {
            if (respostas[idx].correta === null) {
                marcarPulo(idx);
            }
            if (idx >= perguntas.length - 1) {
                finishQuiz();
                return;
            }
            idx = Math.min(perguntas.length - 1, idx + 1);
            render();
        });
    }

    if (btnFinalizar) {
        btnFinalizar.addEventListener("click", function () {
            finishQuiz();
        });
    }

    if (btnRefazer) {
        btnRefazer.addEventListener("click", function () {
            var erradas = [];
            try {
                erradas = JSON.parse(btnRefazer.dataset.erradas || "[]");
            } catch (e) {
                erradas = [];
            }
            if (!erradas.length) return;

            erradas.forEach(function (i) {
                respostas[i] = { correta: null, selecionadas: [], pulada: false };
                limparPulo(i);
                var pergunta = perguntas[i];
                var opcoes = Array.prototype.slice.call(pergunta.querySelectorAll("[data-quiz-opcao]"));
                opcoes.forEach(function (item) {
                    item.disabled = false;
                    item.classList.remove("is-selected");
                });
                var feedback = pergunta.querySelector("[data-quiz-feedback]");
                var explicacao = pergunta.querySelector("[data-quiz-explicacao]");
                if (feedback) {
                    feedback.hidden = true;
                    feedback.textContent = "";
                }
                if (explicacao) {
                    explicacao.hidden = true;
                }
            });

            idx = erradas[0];
            render();
            if (resultado) {
                resultado.hidden = true;
                resultado.textContent = "";
            }
            clearReview();
        });
    }

    if (scoreModal) {
        scoreModal.querySelectorAll("[data-quiz-score-close]").forEach(function (botao) {
            botao.addEventListener("click", fecharScoreModal);
        });
    }

    render();

    function liberarCheckboxPrivacidade(container) {
        if (!container) {
            return;
        }
        var checkbox = container.querySelector("[data-privacy-checkbox]");
        if (!checkbox || !checkbox.disabled) {
            return;
        }
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
        if (!scrollbox) {
            return;
        }
        if (scrollbox.offsetParent === null || scrollbox.closest("[hidden]")) {
            return;
        }
        var container = scrollbox.closest("form, .card, .comentario-popup-card, body");
        if (!container) {
            return;
        }
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
                if (!submit) {
                    return;
                }
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
                            if (current !== requestId) {
                                return;
                            }
                            renderizar(payload);
                        })
                        .catch(function () {
                            if (current !== requestId) {
                                return;
                            }
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

    var loginPopup = document.querySelector("[data-quiz-login-popup]");
    var loginPanels = loginPopup ? loginPopup.querySelectorAll("[data-quiz-login-painel]") : [];
    var loginSteps = loginPopup ? loginPopup.querySelectorAll("[data-quiz-login-step]") : [];

    function showLoginPanel(name) {
        if (!loginPanels.length) return;
        if (["login", "cadastro", "codigo"].indexOf(name) === -1) {
            name = "login";
        }
        loginPanels.forEach(function (panel) {
            panel.hidden = panel.getAttribute("data-quiz-login-painel") !== name;
        });
        if (loginPopup) {
            loginPopup.setAttribute("data-state", name);
        }
        setTimeout(function () {
            ativarAceitePrivacidadeEscalonado(loginPopup || document);
            ativarValidacaoUsernameAoVivo(loginPopup || document);
        }, 0);
    }

    function openLoginPopup(panelName) {
        if (!loginPopup) return;
        loginPopup.hidden = false;
        loginPopup.setAttribute("data-open", "1");
        document.body.classList.add("comentario-popup-open");
        showLoginPanel(panelName || loginPopup.getAttribute("data-state") || "login");
    }

    function closeLoginPopup() {
        if (!loginPopup) return;
        loginPopup.hidden = true;
        loginPopup.removeAttribute("data-open");
        document.body.classList.remove("comentario-popup-open");
    }

    document.querySelectorAll("[data-quiz-login-open]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            openLoginPopup();
        });
    });

    document.querySelectorAll("[data-quiz-login-close]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            closeLoginPopup();
        });
    });

    if (loginPopup) {
        if (loginPopup.hasAttribute("data-open")) {
            openLoginPopup(loginPopup.getAttribute("data-state") || "login");
        }
        loginPopup.addEventListener("click", function (event) {
            if (event.target === loginPopup) {
                closeLoginPopup();
            }
        });
    }

    loginSteps.forEach(function (botao) {
        botao.addEventListener("click", function () {
            showLoginPanel(botao.getAttribute("data-quiz-login-step") || "login");
        });
    });

    ativarAceitePrivacidadeEscalonado(document);
    ativarValidacaoUsernameAoVivo(document);
    renderHistorySummary({
        total_sessoes: historySummary ? historySummary.dataset.totalSessoes : 0,
        total_corretas: historySummary ? historySummary.dataset.totalCorretas : 0,
        total_erradas: historySummary ? historySummary.dataset.totalErradas : 0,
        total_puladas: historySummary ? historySummary.dataset.totalPuladas : 0,
        total_consideradas: historySummary ? historySummary.dataset.totalConsideradas : 0
    });

    document.querySelectorAll("[data-oauth-popup]").forEach(function (link) {
        link.addEventListener("click", function (event) {
            event.preventDefault();
            var href = link.getAttribute("href");
            if (!href) return;
            var win = window.open(
                href,
                "ownpaper-oauth-quiz",
                "width=540,height=700,scrollbars=yes,resizable=yes"
            );
            if (win) {
                win.focus();
            } else {
                window.location.href = href;
            }
        });
    });

    function consumeQuizOauthBeacon() {
        try {
            var raw = window.localStorage.getItem("ownpaper-quiz-oauth-success");
            if (!raw) return;
            window.localStorage.removeItem("ownpaper-quiz-oauth-success");
            var parsed = JSON.parse(raw);
            if (parsed && parsed.redirectUrl) {
                window.location.replace(parsed.redirectUrl);
            }
        } catch (err) {}
    }

    window.addEventListener("message", function (event) {
        if (event.origin !== window.location.origin) {
            return;
        }
        var data = event.data || {};
        if (data.type === "ownpaper-quiz-oauth-success" && data.redirectUrl) {
            closeLoginPopup();
            window.location.replace(data.redirectUrl);
        }
    });

    window.addEventListener("storage", function (event) {
        if (event.key === "ownpaper-quiz-oauth-success") {
            consumeQuizOauthBeacon();
        }
    });

    window.addEventListener("focus", function () {
        consumeQuizOauthBeacon();
    });
})();
