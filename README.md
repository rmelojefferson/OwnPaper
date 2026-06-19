# OwnPaper

<p align="center">
  <img src="docs/assets/brand/ownpaper-logo-wordmark.svg" alt="OwnPaper" width="720">
</p>

OwnPaper é um CMS editorial self-hosted desenvolvido sobre [Django](https://www.djangoproject.com/) e [Wagtail](https://wagtail.org/).

O projeto foi criado para operar uma publicação independente com site público, painel administrativo baseado no Wagtail, fluxo editorial, revisão, perguntas reutilizáveis de quiz, quarentena de mídia, newsletter, comentários, inbox de contato, doações, controles de privacidade, estatísticas internas, backups, logs de auditoria e implantação via Docker.

Este projeto foi desenvolvido em conjunto com OpenAI Codex. O código deve ser revisado, testado e operado por quem for instalar ou manter a aplicação.

## Posição de Manutenção

OwnPaper é open source, mas não está planejado como um produto genérico com manutenção contínua garantida.

O mantenedor original pretende focar em recursos, correções e ajustes operacionais necessários para as instalações do OwnPaper que ele próprio utilizar. Se outra pessoa, comunidade ou organização quiser evoluir o projeto em outra direção, o caminho recomendado é criar um fork e manter essa versão de forma independente.

Contribuições podem ser úteis, mas não há garantia de prazo de resposta, calendário de releases ou suporte de longo prazo.

## Licença

OwnPaper é distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).

A licença MIT foi escolhida por ser permissiva e facilitar uso, modificação, distribuição, instalações privadas e forks.

As dependências de terceiros mantêm suas próprias licenças. Consulte [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Stack Principal

- Python 3.12
- Django 5.2 LTS
- Wagtail 7.4
- PostgreSQL 16
- Gunicorn
- WhiteNoise
- ClamAV para varredura de arquivos enviados
- Docker Compose como caminho padrão de instalação
- MkDocs Material para documentação do projeto

## Funcionalidades Atuais

- Painel administrativo baseado no Wagtail e adaptado ao fluxo editorial do OwnPaper.
- Site público com home, publicações, autores, categorias, tags, busca, RSS e página de apoio/doações.
- Publicações com controle de autoria, atribuição de atualização, notas, referências, créditos, blocos de quiz e exportação em PDF.
- Fluxo editorial com atribuição de revisores, aprovações, rejeições, comentários e histórico de auditoria.
- Catálogo de perguntas reutilizáveis de quiz.
- Quarentena de mídia para imagens, PDFs e vídeos, com sanitização e aprovação.
- Inbox de contato com atribuição, resposta, encaminhamento, assinaturas e regras de visibilidade por operador/admin.
- Newsletter com inscrição, templates, importador CSV e notificações de publicações.
- Estatísticas internas com retenção limitada e recomendação de analytics externos para análises profundas.
- Integrações opcionais com Plausible, Umami, Matomo e Shlink.
- Fluxos de privacidade e consentimento para usuários públicos e usuários do painel.
- Logs de auditoria encadeados por hash para evidência de adulteração em nível de aplicação.
- Backups gerenciados pelo backend, com suporte a armazenamento local e externo.
- Autenticação em dois fatores para acesso ao painel administrativo.

## Estrutura do Projeto

```text
config/      Configurações Django, URLs, middlewares, templates e arquivos estáticos
conteudo/    Aplicação principal de conteúdo/editorial
home/        Aplicação da página inicial Wagtail
docs/        Documentação MkDocs
```

## Início Rápido com Docker

Copie o arquivo de ambiente de exemplo:

```bash
cp .env.example .env
```

Construa e suba os serviços:

```bash
docker compose up -d --build
```

Crie o primeiro usuário administrador:

```bash
docker compose exec web python manage.py createsuperuser
```

Prepare o site Wagtail inicial e as configurações padrão:

```bash
docker compose exec web python manage.py bootstrap_ownpaper
```

Acesse a aplicação:

```text
http://localhost:8000/
```

Painel administrativo:

```text
http://localhost:8000/admin/
```

## Demo Local

O GitHub Pages hospeda apenas documentação estática. Como o OwnPaper depende de Django, Wagtail, PostgreSQL, autenticação e serviços de backend, a demo real do site público e do painel administrativo deve ser executada localmente ou em um servidor próprio.

Para uma demonstração local mínima:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py bootstrap_ownpaper
docker compose exec web python manage.py createsuperuser
```

Depois acesse:

```text
Site público: http://localhost:8000/
Painel admin: http://localhost:8000/admin/
```

A documentação publicada no GitHub Pages explica os fluxos principais e a instalação.

## Base de Produção

Use `.env.production.example` como ponto de partida para produção:

```bash
cp .env.production.example .env
```

Antes de publicar em produção, configure pelo menos:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- credenciais do banco de dados
- domínio público e configurações de HTTPS/reverse proxy
- SMTP
- chaves Turnstile, se formulários públicos estiverem ativos
- ClamAV
- backups
- volumes de mídia/estáticos
- processo de criação do primeiro admin

O entrypoint do container pode aguardar o PostgreSQL, rodar migrações, coletar arquivos estáticos e executar rotinas de bootstrap. Essas ações são controladas por variáveis de ambiente documentadas em `docs/deployment/configuration.md`.

## Comandos de Validação

Execute antes de publicar, empacotar ou alterar uma instalação:

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py collectstatic --noinput --dry-run
docker compose exec -T web python manage.py test --keepdb
docker compose exec -T web python manage.py homologar_ownpaper
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
docker compose exec -T web python manage.py verificar_integridade_logs
```

## Documentação

A documentação do OwnPaper usa MkDocs e fica em `docs/`.

Documentação publicada:

```text
https://rmelojefferson.github.io/OwnPaper/
```

Tour visual:

```text
https://rmelojefferson.github.io/OwnPaper/visual-tour/
```

Instale as dependências de documentação:

```bash
python -m venv .venv-docs
. .venv-docs/bin/activate
pip install -r docs/requirements.txt
```

Rode localmente:

```bash
mkdocs serve
```

Gere o build estático:

```bash
mkdocs build
```

O diretório gerado `site/` é ignorado pelo Git.

## Publicação no GitHub

Este repositório está preparado para publicação normal no GitHub.

Para configurar um repositório remoto novo:

```bash
git remote add origin git@github.com:SEU_USUARIO_OU_ORG/OwnPaper.git
git push -u origin main
```

A documentação pode ser publicada com MkDocs em uma branch `gh-pages`:

```bash
mkdocs gh-deploy --clean
```

## Aviso de Segurança

OwnPaper inclui vários controles de segurança, mas é uma aplicação self-hosted. Quem instala continua responsável por segurança do servidor, HTTPS, reputação SMTP, armazenamento de backups, credenciais, atualização de sistema/container e monitoramento de produção.

Consulte [SECURITY.md](SECURITY.md) e `docs/deployment/homologacao-checklist.md` antes de usar em produção.

## Aviso Legal e Licenças

O inventário de dependências/licenças neste repositório é um apoio técnico de compliance, não um parecer jurídico. Antes de redistribuir imagens de container ou oferecer o OwnPaper comercialmente, revise licenças de terceiros, pacotes de sistema e imagens usadas conforme seu modelo de distribuição.
