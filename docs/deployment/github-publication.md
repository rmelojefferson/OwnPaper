# Publicação no GitHub

Este roteiro publica o OwnPaper como repositório aberto.

## Antes de publicar

Verifique que o repositório não contém dados privados:

```bash
git status --short
rg -n "senha|password|secret|token|api_key|smtp|private key|BEGIN RSA|BEGIN OPENSSH" . --glob '!docs/**' --glob '!README.md' --glob '!*.example' --glob '!.git/**'
```

Confirme que arquivos reais de ambiente, backups e mídias estão ignorados:

```bash
git check-ignore .env .env.production 2>/dev/null || true
git check-ignore site/ node_modules/ __pycache__/ 2>/dev/null || true
```

## Autenticação GitHub

Quando for efetivamente publicar, faça login:

```bash
gh auth login
```

Se o login precisar ser feito por mim no ambiente de trabalho, informe a URL do repositório ou a organização/usuário destino antes.

## Criar remoto e enviar

Depois de criar um repositório vazio no GitHub:

```bash
git remote add origin git@github.com:SEU_USUARIO_OU_ORG/OwnPaper.git
git push -u origin main
```

## Documentação no GitHub Pages

A documentação usa MkDocs. Para compilação local:

```bash
python -m venv .venv-docs
. .venv-docs/bin/activate
pip install -r docs/requirements.txt
mkdocs build
```

O diretório `site/` não deve ser commitado.

## Texto recomendado para descrição pública

OwnPaper é um CMS editorial auto-hospedado baseado em Django e Wagtail, desenvolvido em conjunto com OpenAI Codex. O projeto é aberto sob licença MIT, mas sua manutenção contínua não é garantida; o mantenedor original prioriza recursos e correções necessárias para suas próprias instalações. Para continuidade independente, crie um fork.
