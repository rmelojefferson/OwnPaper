# Papéis, permissões e usuários

OwnPaper usa papéis acumuláveis. Um usuário pode ser admin, autor, revisor e operador ao mesmo tempo, conforme necessidade da instalação.

## Papéis principais

### Admin

Admin tem acesso amplo ao painel.

Responsabilidades:

- gerenciar usuários;
- configurar o site;
- administrar fluxo editorial;
- publicar;
- revisar conteúdo;
- responder ou atribuir mensagens;
- aprovar mídia;
- validar categorias, tags e perguntas;
- acessar logs;
- consultar backups e saúde operacional.

Proteções recomendadas:

- não permitir remover o último admin;
- exigir confirmação extra para remoção de privilégios administrativos;
- registrar auditoria em mudanças sensíveis;
- alertar quando admin revisar publicação não atribuída.

### Autor

Autor cria conteúdo.

Permissões típicas:

- criar publicação;
- editar publicação própria enquanto permitido;
- salvar rascunho;
- solicitar revisão;
- sugerir categorias;
- sugerir tags;
- sugerir perguntas;
- enviar mídia para quarentena.

Publicação direta não deve ser padrão. Deve ser uma permissão extra por usuário.

### Revisor

Revisor avalia conteúdo.

Permissões típicas:

- ver fila de revisão;
- revisar publicações atribuídas;
- revisar conteúdo não atribuído com alerta, se permitido;
- aprovar/rejeitar/solicitar ajustes;
- validar perguntas, categorias e tags;
- aprovar mídia quando habilitado.

O revisor não deve precisar editar a publicação para decidir.

### Operador

Operador atua em relacionamento e operação.

Permissões típicas:

- ver mensagens atribuídas;
- responder contato;
- encaminhar mensagem;
- alterar status de atendimento;
- usar assinatura do sistema.

Admins também podem responder mensagens.

## Papéis acumuláveis

Exemplos:

- admin + revisor;
- autor + revisor;
- autor + operador;
- operador isolado;
- admin completo.

Isso evita perfis rígidos e permite instalações menores com menos usuários.

## Publicação direta por autor

Publicar direto deve ser uma permissão individual.

Quando um autor publica direto:

- admins podem ser notificados;
- logs devem registrar a ação;
- o público deve ver autoria correta;
- atualizações por terceiros devem ser atribuídas corretamente.

## Autoria atribuída por terceiro

Quando um usuário atribui autoria a outro, o sistema pode exigir confirmação.

Estados possíveis:

- pendente;
- confirmada;
- rejeitada.

Ações devem registrar:

- quem atribuiu;
- quando atribuiu;
- quem confirmou/rejeitou;
- quando confirmou/rejeitou;
- se houve intervenção administrativa.

## Coautoria

Coautoria deve ser confirmável para evitar falsa atribuição.

Uma publicação com múltiplos autores precisa preservar ordem, confirmação e histórico.

## Exclusão ou remoção de admin

Regras recomendadas:

- bloquear exclusão do último admin;
- exigir dupla confirmação para remoção sensível quando viável;
- exigir senha/2FA para auto-remoção de privilégio admin;
- registrar auditoria.

## 2FA

2FA é recomendado para usuários administrativos.

O painel inclui:

- configuração de 2FA;
- códigos de backup;
- reforço para ações sensíveis.

## Consentimento administrativo

Usuários do painel devem aceitar termos de uso administrativo.

Esse aceite é separado do consentimento público do site.

## Logs e trilha imutável

Ações sensíveis são registradas em log.

A proteção por hash encadeado permite detectar alterações diretas no banco, embora não impeça alguém com acesso total ao servidor de modificar dados. Para robustez maior, é recomendado exportar logs ou backups para armazenamento externo.
