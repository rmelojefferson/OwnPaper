# Painel administrativo

O painel administrativo do OwnPaper é baseado no Wagtail e adiciona telas próprias para operação editorial, comunicação, segurança, estatísticas, backups e configurações do site. A lógica preserva a estrutura do Wagtail quando ela é útil e cria páginas dedicadas quando o fluxo padrão ficaria confuso para a operação do projeto.

## Objetivo do painel

O painel concentra:

- criação e edição de publicações;
- revisão editorial e atribuição de revisores;
- controle de autoria e confirmação de coautoria;
- catálogo reutilizável de perguntas de quiz;
- quarentena, sanitização e aprovação de mídia;
- comentários e mensagens de contato;
- newsletter, disparos de e-mail e templates;
- indexador por CSV;
- estatísticas operacionais;
- logs, backup, saúde e integridade;
- configurações do site público;
- gestão de usuários, papéis e permissões.

## Página inicial do admin

A home administrativa funciona como painel de acesso rápido.

Ela reúne:

- busca global administrativa;
- visão rápida de páginas, imagens, documentos e conta;
- cards de acesso para conteúdo, relacionamento, campanhas, configurações e fluxo editorial;
- alertas operacionais, como mensagens pendentes, comentários e itens de revisão;
- indicadores resumidos do site.

No desktop, a home prioriza acesso rápido e leitura em cards. No mobile, o painel é adaptado para ações essenciais, com aviso de que a administração completa é recomendada em desktop.

## Sidebar

A sidebar agrupa as áreas por contexto operacional.

Editorial:

- Publicações;
- Páginas;
- Perguntas do quiz;
- Mídias pendentes;
- Imagens;
- Documentos;
- Categorias e Tags.

Operação:

- Contato;
- Comentários;
- Newsletter e e-mails;
- Indexador;
- Estatísticas;
- Saúde operacional;
- Backups;
- Logs.

Administração:

- Configurações do site;
- Fluxo editorial;
- Usuários;
- Redirecionamentos e demais itens administrativos mantidos quando fazem sentido para a instalação.

Itens nativos do Wagtail que poderiam confundir a operação do OwnPaper podem ser ocultados quando são redundantes com os fluxos próprios do projeto.

## Busca global do painel

A busca global foi criada para substituir buscas soltas e inconsistentes no admin.

Ela permite localizar resultados administrativos em áreas como:

- publicações;
- páginas;
- autores;
- perguntas de quiz;
- categorias;
- tags;
- mensagens;
- comentários;
- newsletter;
- indexador;
- documentos e imagens, conforme a integração disponível.

Os filtros permitem restringir por tipo e por vínculo com o usuário autenticado.

A opção `Vinculados ao meu usuário` deve retornar itens ligados diretamente ao usuário, como autoria, responsabilidade, revisão atribuída, envio ou relacionamento operacional. Ela não deve ser confundida com busca pública do site.

## Publicações no painel

A página `Publicações` substitui o caminho genérico do Wagtail para listar conteúdo editorial com filtros mais úteis ao projeto.

Ela inclui:

- busca textual;
- filtro por período;
- filtro por categoria;
- filtro por autor;
- filtro por status editorial;
- coluna de publicação;
- coluna de atualização;
- acesso direto ao editor pelo título;
- acesso ao fluxo editorial da publicação;
- botão de nova publicação.

O objetivo é evitar que o operador precise navegar pela árvore de páginas para tarefas editoriais rotineiras.

## Minha conta

A área `Minha conta` concentra:

- perfil;
- senha;
- 2FA;
- códigos de backup;
- notificações;
- tema e zoom;
- aceite dos termos administrativos, quando aplicável.

As seções devem abrir colapsadas por padrão para evitar uma página longa e visualmente pesada.

## Zoom administrativo

O zoom foi movido para `Minha conta > Tema e Zoom`, evitando botões flutuantes sobre o painel.

Essa preferência é por usuário e serve para melhorar leitura em telas diferentes sem quebrar o layout global.

## Logs administrativos

Ações relevantes do painel são registradas em auditoria.

Exemplos:

- alteração de publicação;
- decisão editorial;
- alteração de autoria;
- envio e aprovação de mídia;
- ações de contato;
- disparos de e-mail;
- exportações;
- backup;
- alterações sensíveis de configuração;
- upload temporário de documentação enquanto a página existir.

A trilha de logs usa hash encadeado para detectar adulterações.

Validação manual:

```bash
docker compose exec -T web python manage.py verificar_integridade_logs
```

## Backups

O painel pode exibir histórico e relatórios de backup, mas a restauração completa deve ser tratada no backend/servidor, não por upload livre no admin.

O desenho recomendado é:

- backup completo executado por tarefa administrativa ou agendada;
- relatório enviado por e-mail, sem anexar o backup;
- armazenamento externo opcional via WebDAV configurado por ambiente;
- download temporário protegido quando a instalação não tiver armazenamento externo;
- documentação clara de restore via servidor.

## Mobile

O painel possui ajustes para telas pequenas, mas a administração completa continua sendo uma experiência desktop-first.

No mobile, devem ser priorizados:

- leitura de alertas;
- acesso rápido;
- tarefas simples;
- ausência de cortes horizontais;
- evitar sidebar fixa cobrindo conteúdo.

## Padrão visual

As páginas próprias devem seguir o padrão visual do Wagtail e do conjunto administrativo já validado, evitando estilos isolados que destoem entre áreas.

Ao criar novas telas, reutilize:

- cards administrativos;
- botões do padrão do painel;
- filtros com altura consistente;
- datepicker padronizado;
- checkboxes simples;
- espaçamentos já aprovados.
