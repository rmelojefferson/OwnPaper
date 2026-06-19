# Política de atualização LTS dos frameworks

OwnPaper segue uma política de usar a linha LTS mais recente para frameworks quando houver versão LTS disponível.

## Base atual

- Django 5.2 LTS.
- Wagtail 7.4 LTS, com patch mínimo 7.4.2.
- Python 3.12 no Docker.

Use a linha Wagtail 7.4.x como base do projeto. Atualizações dentro da linha 7.4 devem ser aplicadas após validação completa, pois tendem a concentrar correções compatíveis com a linha estável/LTS.

## Desenvolvimento local

O `.venv` local antigo usava Python 3.8 e não é mais compatível com a base atual dos frameworks.

Recrie o ambiente local com Python 3.12 antes de usar `manage.py` fora do Docker.

Até lá, execute verificações e migrações pelo Docker.

## Validação obrigatória

Depois de atualizar frameworks, valide:

1. Resolução de dependências e construção da imagem.
2. `makemigrations --check --dry-run`.
3. `manage.py check` com avisos habilitados.
4. Migrações de banco de dados.
5. `collectstatic`.
6. Página inicial pública.
7. Redirecionamento do admin e tela de login com dois fatores.
8. Comando de bootstrap.
9. Configurações do Wagtail, snippets, imagens, importação CSV administrativa e fluxos de newsletter.

## Fontes oficiais

- https://docs.wagtail.org/en/stable/releases/upgrading.html
- https://docs.wagtail.org/en/stable/releases/7.4.html
- https://docs.wagtail.org/en/stable/releases/index.html
- https://docs.djangoproject.com/en/5.2/releases/5.2/
