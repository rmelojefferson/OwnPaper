# Papéis e permissões

OwnPaper usa papéis acumuláveis. Um usuário pode ter mais de uma função.

## Papéis

### Admin

- acesso total ao painel;
- gerencia usuários, configurações, fluxo editorial, inbox, backups e logs;
- pode revisar conteúdo não atribuído, com alerta;
- não deve remover o último admin;
- ações sensíveis devem ser auditadas.

### Autor

- cria e edita publicações dentro das regras configuradas;
- pode sugerir categorias, tags e perguntas;
- pode solicitar revisão;
- publicação direta depende de permissão específica.

### Revisor

- revisa publicações atribuídas;
- pode revisar publicações não atribuídas com alerta;
- valida perguntas, categorias e tags conforme fluxo editorial;
- não deve aprovar o próprio conteúdo salvo regra/admin.

### Operador

- focado em inbox/contato e operação;
- pode responder mensagens atribuídas;
- admins também podem responder mensagens.

## Autoria

Quando uma publicação atribui autoria a outro usuário, a atribuição pode exigir confirmação do usuário atribuído. A resolução manual por admin deve gerar alerta e auditoria.

## Logs

Mudanças relevantes devem ser registradas. Os logs são append-only no painel e protegidos por hash encadeado para detecção de adulteração.
