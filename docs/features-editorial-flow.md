# Fluxo editorial

O fluxo editorial do OwnPaper controla revisão, atribuição, aprovação, rejeição, solicitações de ajuste, autoria, transparência pública e logs.

## Objetivo

O fluxo existe para evitar que a publicação dependa apenas da permissão bruta do Wagtail.

Ele adiciona regras de operação editorial:

- autores criam e enviam textos;
- revisores avaliam sem precisar editar o texto diretamente;
- admins podem intervir;
- revisões múltiplas são independentes;
- autoria atribuída por terceiro pode exigir confirmação;
- decisões são auditadas.

## Papéis envolvidos

Admin:

- pode ver e decidir tudo;
- pode atribuir revisores;
- pode publicar;
- pode revisar conteúdo não atribuído, com alerta;
- pode resolver conflitos de autoria, com auditoria.

Autor:

- cria publicação;
- salva rascunho;
- solicita revisão;
- responde ajustes;
- só publica direto se tiver permissão específica.

Revisor:

- vê revisões atribuídas;
- pode revisar publicações disponíveis quando permitido;
- aprova, rejeita ou solicita ajustes;
- não deve depender da tela de edição para ler o texto.

Operador:

- não é papel editorial por padrão;
- atua em contato/inbox quando habilitado.

## Estados da publicação

Rascunho:

- texto ainda em trabalho;
- visível apenas no painel;
- autor pode editar conforme permissão.

Em revisão:

- texto enviado para avaliação;
- autor não deve editar livremente por padrão;
- revisores podem ser atribuídos;
- decisões ficam pendentes.

Ajustes solicitados:

- revisor solicitou mudanças;
- autor precisa ajustar ou responder;
- comentários e marcações devem orientar a correção.

Rejeitada:

- conteúdo recusado;
- histórico deve registrar quem rejeitou e por quê.

Agendada:

- aprovada para publicação futura;
- depende de data configurada.

Publicada:

- conteúdo disponível no site público;
- histórico e autoria permanecem preservados.

## Revisores múltiplos

Uma publicação pode exigir mais de um revisor.

Quando houver múltiplos revisores:

- cada revisor possui decisão própria;
- uma aprovação não substitui a decisão dos demais;
- a publicação só avança quando todos os revisores exigidos aprovarem;
- rejeição ou ajustes de qualquer revisor devem impedir publicação automática;
- o histórico deve mostrar cada decisão separadamente.

## Atribuição de revisores

Admins podem:

- atribuir revisores manualmente;
- atribuir aleatoriamente quando a regra estiver disponível;
- atribuir mais de um revisor;
- remover ou substituir revisão quando necessário, mantendo logs.

A atribuição aleatória aproxima o fluxo de revisão por pares e reduz seleção tendenciosa.

## Revisão fora da atribuição

Um revisor pode revisar publicação não atribuída quando a política permitir, mas o sistema deve exibir alerta.

Admin também pode revisar conteúdo não atribuído, com alerta informativo, sem bloqueio.

## Preview editorial

A tela de fluxo editorial deve oferecer preview de leitura da publicação.

Isso evita que o revisor precise abrir o editor de página para ler, reduzindo o risco de alterações indevidas.

O preview deve mostrar:

- título;
- autores;
- resumo;
- corpo;
- categoria e tags;
- notas, créditos e referências;
- mídia vinculada;
- quiz, quando aplicável;
- estado editorial;
- histórico de revisões.

## Comentários de revisão

Comentários devem ser úteis para o autor localizar o problema.

Tipos recomendados:

- comentário geral;
- trecho do texto;
- sugestão;
- pedido de ajuste;
- referência a marcador/âncora.

A melhor experiência é aproximar o comportamento de comentários de editores de texto: comentário associado a trecho ou marcador, com contexto visível.

## Retorno para o autor

Quando há ajustes solicitados, o autor deve conseguir identificar:

- quem solicitou;
- data da solicitação;
- trecho ou referência;
- comentário;
- status da solicitação;
- se a publicação voltou para edição.

## Autoria e coautoria

O fluxo editorial também protege autoria.

Quando um usuário atribui autoria a outro:

- a coautoria pode ficar pendente;
- o usuário atribuído aprova ou rejeita;
- o painel registra quem atribuiu;
- admins podem resolver manualmente quando necessário;
- a publicação pública não deve induzir autoria falsa.

## Notificações

O sistema pode notificar admins quando:

- publicação entra em revisão;
- publicação é publicada por usuário com permissão direta;
- autoria exige confirmação;
- mídia aguarda aprovação;
- comentários ou mensagens aguardam ação.

## Logs e integridade

Toda decisão sensível deve gerar log:

- envio para revisão;
- atribuição de revisor;
- aprovação;
- rejeição;
- solicitação de ajustes;
- publicação;
- agendamento;
- alteração de autoria;
- resolução manual por admin.

Os logs são usados para rastreabilidade operacional e investigação.
