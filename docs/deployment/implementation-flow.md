# Fluxo de Implementação (sem revisão por pares)

## Escopo desta fase
- Implementar e estabilizar todas as features combinadas.
- **Fora de escopo por enquanto:** revisão por pares/auditoria independente editorial.

## Entregas já implementadas no código
- Convites de usuário, aceite com definição de senha e reset de senha.
- Perfis administrativos (`admin`, `autor/escritor`) com ajustes de acesso no painel.
- Reset administrativo de 2FA e backup codes para recuperação.
- Inbox de contato no admin com atribuição/encaminhamento/interações.
- Disparo de e-mail em massa (manual), templates e métricas básicas.
- Notificações de publicações por e-mail (imediato e periódico).
- Feed RSS (`/rss.xml` e `/feed/`).
- Audit log com exportação CSV.
- Backups com execução manual/agendada, validação de integridade e histórico.
- Gestão de navegação (menu + rodapé) com configuração no admin.
- Busca global com filtros e exportação CSV.
- Quiz por publicação e página de quiz de estudos.
- Guia de leitura + zoom tipográfico na publicação.
- Fluxo editorial com envio de publicação para aprovação de admin.
- Explorado do admin em tela inicial (ícones/pastas) com zoom.
- Tema claro/escuro no admin e no site.

## Ajustes recentes (rodada atual)
- Tema do site padronizado para `claro/escuro` (sem modo `sistema` no comportamento ativo).
- CSS do explorador do admin limpo para remover variações baseadas em `data-theme="auto"`.
- Cobertura de teste adicionada para RSS (content-type XML + item no feed).

## Ordem de homologação recomendada
1. Acesso e segurança: convite, criação de senha forte, login, 2FA, backup codes, reset de senha.
2. Operação editorial: criação por autor, fila de aprovação, publicação por admin.
3. Comunicação: contato inbox, resposta, atribuição e disparos em massa.
4. Newsletter: inscrição, cancelamento, privacidade e notificações automáticas de publicações.
5. Navegação e leitura: menu/rodapé configuráveis, busca global, zoom e guia de leitura.
6. Continuidade: backup/validação/restore e auditoria de logs.

## Pendências restantes (não-código ou validação manual)
- Revisão visual em desktop real (Chrome/Firefox/Safari).
- Revisão visual em mobile real (Android/iOS).
- Validação com SMTP real e Turnstile com chaves de produção.
- Teste de envio real de campanhas.
- Teste de restauração real de backup em ambiente separado.

## Execução rápida de validação técnica
- Comando único: `python manage.py homologar_ownpaper --keepdb`
- Local do comando: `conteudo/management/commands/homologar_ownpaper.py`
- O comando valida:
  - `check` do Django,
  - migrações pendentes,
  - suíte `conteudo`,
  - smoke de rotas principais (`/`, `/busca/`, `/rss.xml`, `/feed/`, `/account/login/`, `/admin/`).

## Validação guiada de produção
- Comando: `python manage.py validar_producao_ownpaper`
- Local do comando: `conteudo/management/commands/validar_producao_ownpaper.py`
- Cobertura:
  - baseline de segurança (`SECURE_*`, cookies, HSTS, hosts),
  - configuração SMTP (e testes reais opcionais),
  - Turnstile (e validação remota opcional de token),
  - dry-run de restore de backup (arquivo específico ou último disponível),
  - consistência de configurações por site.

## Regra operacional obrigatória para rollout, limpeza e reversão

No OwnPaper, **editar o repositório local não basta**.

Qualquer trabalho que toque:
- templates
- CSS
- JS
- páginas públicas
- publicação
- admin
- estáticos
- Docker
- rollout

deve seguir este fluxo mínimo obrigatório:

1. ajustar os arquivos no workspace local
2. sincronizar no container `web` os arquivos tocados
3. se houver dúvida de divergência, sincronizar o diretório inteiro do bloco afetado
4. executar `python manage.py check`
5. executar `python manage.py collectstatic --clear --noinput` quando houver estáticos
6. reiniciar o serviço `web` quando houver:
   - template
   - JS
   - CSS
   - manifest
   - suspeita de cache em processo
7. validar o runtime real por rota, não só o source

### Regra de sync no container

Ao usar `docker compose cp`, não copie um diretório de topo para um destino
existente com o mesmo nome.

Exemplos proibidos:
- `docker compose cp config web:/app/config`
- `docker compose cp conteudo web:/app/conteudo`
- `docker compose cp home web:/app/home`

Esse padrão aninha o source dentro do destino e cria resíduos como:
- `/app/config/config`
- `/app/conteudo/conteudo`
- `/app/home/home`

Esses resíduos contaminam:
- imports Python
- templates
- `collectstatic`
- runtime servido

Fluxo correto:
1. preferir copiar os arquivos tocados individualmente para o caminho final
2. se precisar copiar um bloco, copiar o conteúdo do diretório, nunca o diretório
   de topo para ele mesmo
3. após qualquer sync amplo, verificar explicitamente se não surgiram diretórios
   aninhados antes de validar a entrega

### Interpretação obrigatória de “limpar”, “reverter” e “não deixar nada antigo”

Quando for pedido:
- limpar
- reverter
- restaurar
- rebuildar
- não deixar nada antigo

isso significa limpar a trilha inteira:

1. workspace local
2. source dentro do container
3. manifest/static buildado
4. processo `web`
5. runtime servido

Não considerar a tarefa encerrada antes desses 5 pontos.

### Anti-padrão proibido

É proibido considerar uma mudança concluída apenas porque:
- o arquivo local mudou
- o git diff parece correto
- o template no repositório parece correto

No OwnPaper, a validação final sempre é:
- asset/runtime real
- rota real
- comportamento real servido pelo `web`

## Segredos de integrações externas
- Para instalações novas, prefira manter segredos fora do banco e do painel.
- Padrão recomendado:
  - `client_id` e `base_url`: podem ficar em variável de ambiente ou no painel
  - `client_secret` e `API key`: preferir variável de ambiente
- Variáveis suportadas pelo runtime:
  - `OWNPAPER_SHLINK_BASE_URL`
  - `OWNPAPER_SHLINK_API_KEY`
  - `OWNPAPER_OAUTH_ORCID_CLIENT_ID`
  - `OWNPAPER_OAUTH_ORCID_CLIENT_SECRET`
  - `OWNPAPER_OAUTH_GITHUB_CLIENT_ID`
  - `OWNPAPER_OAUTH_GITHUB_CLIENT_SECRET`
  - `OWNPAPER_OAUTH_GOOGLE_CLIENT_ID`
  - `OWNPAPER_OAUTH_GOOGLE_CLIENT_SECRET`
  - `OWNPAPER_OAUTH_CODEBERG_CLIENT_ID`
  - `OWNPAPER_OAUTH_CODEBERG_CLIENT_SECRET`
  - `OWNPAPER_OAUTH_CODEBERG_BASE_URL`
  - `OWNPAPER_OAUTH_GITLAB_CLIENT_ID`
  - `OWNPAPER_OAUTH_GITLAB_CLIENT_SECRET`
  - `OWNPAPER_OAUTH_GITLAB_BASE_URL`
- Regra de precedência:
  1. variável de ambiente
  2. valor salvo no painel
- Isso preserva compatibilidade com instalações existentes e evita usar o admin como fonte primária de segredos operacionais.

## Shlink no empacotamento
- O projeto já possui integração funcional com a API do Shlink no runtime.
- O empacotamento agora deve tratar o Shlink como **serviço opcional** da stack.
- O `docker-compose.yml` inclui perfil opcional `shlink`, com:
  - `shlink`
  - `shlink-db`
- O site continua funcionando sem o perfil ativo:
  - se o Shlink estiver desativado ou falhar, os botões usam a URL longa
- Para instalações novas, o caminho recomendado é:
  1. subir `docker compose --profile shlink up -d`
  2. definir `SHLINK_INITIAL_API_KEY`
  3. repetir o valor em `OWNPAPER_SHLINK_API_KEY`
  4. apontar `OWNPAPER_SHLINK_BASE_URL` para a URL interna real do Shlink, por exemplo `http://shlink:8080/go` quando houver `base path`
  5. ativar `shlink_ativo` no painel
- O domínio curto e o HTTPS do Shlink continuam sendo responsabilidade do proxy reverso da instalação.
- Referência operacional:
  - [shlink.md](/root/OwnPaper/docs/deployment/shlink.md)

## Backlog pausado (decisão de produto)
- Revisão por pares (entidades/fluxo/selo público): **pausado** até definição final.
