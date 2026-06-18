(function () {
    function closestForm(element) {
        while (element && element.tagName !== "FORM") {
            element = element.parentElement;
        }
        return element || null;
    }

    function createButton(label, title, command, value) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "button button-small button-secondary op-email-editor__button";
        button.textContent = label;
        button.title = title;
        button.setAttribute("aria-label", title);
        button.dataset.command = command;
        if (value) {
            button.dataset.value = value;
        }
        return button;
    }

    function normalizeEditorHtml(editor) {
        var html = editor.innerHTML.trim();
        if (!html || html === "<br>") {
            return "";
        }
        return html;
    }

    function insertPlainText(text) {
        if (!text) {
            return;
        }
        if (document.queryCommandSupported && document.queryCommandSupported("insertText")) {
            document.execCommand("insertText", false, text);
            return;
        }
        var selection = window.getSelection();
        if (!selection || !selection.rangeCount) {
            return;
        }
        var range = selection.getRangeAt(0);
        range.deleteContents();
        range.insertNode(document.createTextNode(text));
        range.collapse(false);
    }

    function createEditor(textarea) {
        if (!textarea || textarea.dataset.emailRichtextReady === "1") {
            return;
        }
        textarea.dataset.emailRichtextReady = "1";

        var wrapper = document.createElement("div");
        wrapper.className = "op-email-editor";

        var toolbar = document.createElement("div");
        toolbar.className = "op-email-editor__toolbar";
        toolbar.setAttribute("aria-label", "Ferramentas do editor de e-mail");

        [
            createButton("B", "Negrito", "bold"),
            createButton("I", "Itálico", "italic"),
            createButton("Título", "Título", "formatBlock", "h2"),
            createButton("Texto", "Parágrafo", "formatBlock", "p"),
            createButton("Lista", "Lista com marcadores", "insertUnorderedList"),
            createButton("1. Lista", "Lista numerada", "insertOrderedList"),
            createButton("Link", "Inserir link", "createLink"),
            createButton("Desfazer", "Desfazer", "undo"),
        ].forEach(function (button) {
            toolbar.appendChild(button);
        });

        var editor = document.createElement("div");
        editor.className = "op-email-editor__area";
        editor.contentEditable = "true";
        editor.setAttribute("role", "textbox");
        editor.setAttribute("aria-multiline", "true");
        editor.setAttribute("aria-label", textarea.previousElementSibling ? textarea.previousElementSibling.textContent.trim() : "Corpo da mensagem");
        editor.innerHTML = textarea.value || "";

        var help = document.createElement("p");
        help.className = "op-admin-panel__meta op-email-editor__help";
        help.textContent = "Dica: use texto simples e formatação básica. Scripts, atributos inseguros e links perigosos continuam sendo removidos no servidor.";

        wrapper.appendChild(toolbar);
        wrapper.appendChild(editor);
        wrapper.appendChild(help);
        textarea.parentNode.insertBefore(wrapper, textarea);
        textarea.classList.add("op-email-editor__source");

        function syncToTextarea() {
            textarea.value = normalizeEditorHtml(editor);
        }

        toolbar.addEventListener("click", function (event) {
            var button = event.target.closest("[data-command]");
            if (!button) {
                return;
            }
            editor.focus();
            var command = button.dataset.command;
            if (command === "createLink") {
                var url = window.prompt("Informe o link completo, começando com https://, http:// ou mailto:");
                if (!url) {
                    return;
                }
                var normalized = url.trim();
                if (!/^(https?:\/\/|mailto:)/i.test(normalized)) {
                    window.alert("Use apenas links iniciados por https://, http:// ou mailto:");
                    return;
                }
                document.execCommand(command, false, normalized);
            } else {
                document.execCommand(command, false, button.dataset.value || null);
            }
            syncToTextarea();
        });

        editor.addEventListener("input", syncToTextarea);
        editor.addEventListener("blur", syncToTextarea);
        editor.addEventListener("paste", function (event) {
            event.preventDefault();
            var text = "";
            if (event.clipboardData) {
                text = event.clipboardData.getData("text/plain");
            } else if (window.clipboardData) {
                text = window.clipboardData.getData("Text");
            }
            insertPlainText(text);
            syncToTextarea();
        });

        var form = closestForm(textarea);
        if (form) {
            form.addEventListener("submit", syncToTextarea);
        }
        syncToTextarea();
    }

    function init() {
        document.querySelectorAll("textarea[data-email-richtext]").forEach(createEditor);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
