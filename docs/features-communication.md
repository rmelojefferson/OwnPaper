# Comunicação, contato, newsletter e e-mails

OwnPaper centraliza comunicação no painel para reduzir dependência de ferramentas externas em fluxos simples.

## Caixa de entrada de contato

Mensagens enviadas pelo site chegam ao painel de contato.

A listagem inclui:

- busca;
- filtro por status;
- filtro por responsável;
- filtro por período;
- ações de resposta;
- atribuição de responsável;
- histórico da mensagem.

## Permissões do contato

Admins veem todas as mensagens.

Operadores veem mensagens atribuídas a eles.

Usuários não admins só devem ver mensagens vinculadas ao seu usuário, conforme permissões.

A atribuição de responsável deve listar usuários capazes de responder, incluindo operadores e admins.

## Responder e-mail pelo painel

A resposta usa editor rich text simples, não campo cru de HTML.

O objetivo é permitir que usuários escrevam e-mails sem conhecer HTML.

O sistema converte o conteúdo para HTML seguro para envio.

## Encaminhar e-mail

O encaminhamento permite enviar a mensagem para outro destinatário.

O campo de destinatário deve facilitar seleção de e-mails cadastrados de usuários do painel, mas permitir escrita manual quando necessário.

Pode haver opção de incluir a última resposta enviada, quando fizer sentido.

## Assinatura de e-mail

A assinatura padrão deve ser consistente entre usuários.

Modelo recomendado:

- imagem circular do usuário, quando existir;
- logo do site quando o usuário não tiver imagem;
- nome cadastrado do usuário, não apenas username;
- nome do projeto/site.

Assinatura individual pode existir, mas deve respeitar o padrão visual para não criar comunicação despadronizada.

## Monitoramento de respostas

Admins podem configurar monitoramento de respostas por usuário.

Isso permite encaminhar cópias ou alertas de mensagens respondidas por determinado usuário para um e-mail de supervisão.

Essa configuração deve ser auditada.

## Histórico de interações

O histórico exibido em uma mensagem deve ser o histórico daquela mensagem específica.

Ele pode incluir:

- recebimento;
- atribuição;
- alteração de status;
- resposta;
- encaminhamento;
- erro de envio;
- monitoramento.

## Newsletter

A newsletter inclui:

- cadastro público;
- consentimento;
- importação por CSV;
- exportação quando aplicável;
- eventos e histórico;
- solicitações de privacidade;
- modelos;
- disparos.

## Importador CSV

O importador deve validar CSV antes de inserir dados.

Verificações recomendadas:

- extensão CSV;
- colunas esperadas;
- e-mails válidos;
- ausência de colunas perigosas ou inesperadas quando a política exigir;
- conteúdo textual sanitizado;
- isolamento do processamento para evitar quebra do indexador ou banco.

## Modelos de e-mail

Modelos devem usar editor rich text, não HTML cru.

Campos esperados:

- assunto;
- corpo;
- status/uso;
- variáveis permitidas, se existirem;
- preview quando possível.

Imagens no corpo dos e-mails não são habilitadas por padrão, para reduzir peso, problemas de entregabilidade e risco de spam.

## Disparo em massa

O disparo em massa permite enviar e-mails a uma base cadastrada.

O painel deve oferecer:

- editor rich text;
- seleção de público;
- modo imediato ou consolidado;
- período consolidado em dias, como 7, 15, 30 ou 90;
- histórico de envio;
- contagem de enviados e falhas;
- exportação de resultados;
- logs de auditoria.

## Notificações de publicações

Notificações de publicação servem para avisar inscritos sobre novos conteúdos.

Modos possíveis:

- imediato: envio logo após publicação;
- consolidado: resumo em intervalo configurado;
- desativado.

O modo consolidado deve usar períodos compreensíveis em dias.

## Entregabilidade

Configurações de SMTP ficam em ambiente/backend quando envolvem credenciais.

O painel pode exibir status e relatórios, mas não deve expor senha SMTP sem necessidade.

Produção deve configurar SPF, DKIM e DMARC no domínio de envio.
