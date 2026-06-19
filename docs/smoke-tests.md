# Testes rápidos de fumaça

Execute estas verificações depois de atualizar dependências, alterar Docker ou mudar configurações de implantação.

```bash
export DJANGO_SECRET_KEY=ownpaper-local-test-secret-key-with-enough-length

docker compose build web
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py test conteudo --noinput
docker compose exec -T web python manage.py bootstrap_ownpaper --site-name OwnPaper --hostname localhost --port 80
docker compose exec -T web python manage.py homologar_ownpaper --keepdb
curl -I http://127.0.0.1:${OWNPAPER_HTTP_PORT:-8000}/
curl -I http://127.0.0.1:${OWNPAPER_HTTP_PORT:-8000}/account/login/
```

Resultados esperados:

- `manage.py check` não relata problemas.
- `manage.py test conteudo` passa.
- `manage.py homologar_ownpaper --keepdb` finaliza sem erro.
- O bootstrap conclui sem duplicar registros.
- A página inicial retorna `200 OK`.
- A tela de login com dois fatores retorna `200 OK`.

## Teste rápido opcional do Shlink

Ao validar a pilha opcional de links curtos:

```bash
docker compose --profile shlink up -d
docker compose exec -T web python manage.py check
```

Resultados esperados:

- `web`, `shlink` e `shlink-db` sobem sem bloquear uns aos outros.
- O site continua funcionando mesmo com `shlink_ativo` desativado.
- Quando o Shlink está configurado e habilitado, links de compartilhamento de publicações podem ser encurtados.
- Quando o Shlink está indisponível, o site usa URLs longas sem quebrar as páginas de publicação.
