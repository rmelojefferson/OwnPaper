# Publicações, notas e referências

O sistema de publicações é o núcleo do OwnPaper. Ele combina o modelo de página do Wagtail com campos editoriais próprios para autoria, revisão, mídia, quiz, notas, créditos, referências, categorias, tags, atualização e confiabilidade pública.

## Estrutura editorial

Uma publicação pode conter:

- título;
- slug;
- resumo;
- corpo em rich text;
- imagem principal;
- autores;
- categoria principal;
- tags;
- data de publicação;
- data de atualização;
- usuário responsável pela última atualização;
- status editorial;
- revisores;
- perguntas de quiz vinculadas;
- notas;
- créditos;
- referências;
- mídia inserida no corpo;
- metadados de SEO;
- configurações de promoção e indexação herdadas do Wagtail quando aplicável.

## Listagem de publicações

A tela administrativa de publicações deve ser o ponto principal para localizar e editar conteúdo editorial.

Ela oferece:

- busca por texto;
- filtro por período;
- filtro por categoria;
- filtro por autor;
- filtro por status;
- acesso ao editor pelo título;
- acesso ao fluxo editorial;
- coluna de atualização;
- botão de nova publicação alinhado ao cabeçalho.

A rota preferencial é `/admin/publicacoes/`.

## Criação e edição

A edição usa o editor do Wagtail com campos próprios do OwnPaper.

O editor deve permitir:

- escrever o corpo em rich text;
- inserir imagens, documentos e vídeos;
- marcar notas e referências;
- vincular quiz reutilizável;
- configurar autoria;
- ajustar categoria e tags;
- enviar para revisão;
- salvar rascunho;
- publicar, quando a permissão permitir.

Se o usuário for apenas revisor, ele não deve depender da tela de edição para avaliar a publicação. A leitura e decisão devem ocorrer no fluxo editorial.

## Autoria

OwnPaper suporta mais de um autor por publicação.

O fluxo de autoria considera:

- autor principal;
- coautores;
- autoria atribuída por terceiro;
- confirmação pendente de coautoria;
- rejeição de atribuição;
- confirmação manual por admin em casos excepcionais;
- auditoria de toda mudança de autoria.

Quando uma publicação é atribuída a um autor que não é o usuário que está editando, a atribuição pode exigir confirmação. Se um admin resolver manualmente, o sistema deve alertar que a publicação ficará temporariamente associada à decisão administrativa até o autor confirmar.

## Atualização por terceiros

Quando uma publicação é atualizada por usuário diferente do autor original, a autoria original deve continuar preservada.

A publicação pública pode exibir quem atualizou o conteúdo, garantindo transparência e evitando falsa atribuição.

## Categorias e tags

Categorias e tags organizam o conteúdo público e administrativo.

O fluxo pode incluir aprovação quando criadas por autores, para evitar taxonomia inconsistente.

Pontos importantes:

- categoria principal identifica o eixo principal da publicação;
- tags permitem agrupamento temático mais granular;
- autores podem sugerir novos termos quando permitido;
- revisores/admins validam termos pendentes;
- filtros administrativos e públicos usam esses dados.

## Notas, créditos e referências

OwnPaper diferencia complementos editoriais para manter leitura limpa e confiável.

Tipos comuns:

- notas explicativas;
- créditos;
- referências bibliográficas ou links;
- complementos vinculados a trechos do texto.

## Marcadores no texto

Marcadores permitem associar um trecho da publicação a uma nota, crédito ou referência.

O comportamento esperado é:

- o marcador aparece no corpo do texto;
- ao clicar ou tocar, o conteúdo complementar abre em pop-up/modal;
- o leitor não precisa sair do ponto de leitura;
- no fim da publicação, os complementos aparecem organizados em seus campos próprios;
- um mesmo complemento pode ser referenciado por mais de um marcador quando necessário.

A ordenação padrão recomendada é a ordem de aparição no texto. O sistema pode oferecer ordenação alternativa por alfabeto ou marcador, desde que preserve corretamente a sequência dos marcadores usados.

## Pop-ups de notas e referências

O diferencial de leitura do OwnPaper é manter notas, créditos e referências acessíveis sem deslocar o leitor.

O modal deve:

- abrir a informação complementar no contexto;
- permitir fechamento claro;
- funcionar em desktop e mobile;
- manter acessibilidade mínima de foco/teclado;
- não carregar HTML arbitrário inseguro;
- preservar a ordem e o vínculo com o marcador.

## Mídia no corpo da publicação

Imagens, documentos e vídeos inseridos no corpo passam pela política de mídia do projeto.

Mesmo quando o upload ocorre dentro do editor da publicação, o arquivo deve entrar em quarentena quando essa regra estiver ativa.

O comportamento esperado é:

- o autor indica onde a mídia será usada;
- o sistema cria uma mídia pendente;
- a publicação pode ser salva sem bloquear o fluxo;
- o local fica marcado como pendente;
- após aprovação, a mídia entra automaticamente no ponto planejado.

## Quiz em publicação

A publicação pode receber perguntas de quiz reutilizáveis.

O autor seleciona perguntas existentes a partir do catálogo, com busca e filtros. As perguntas novas devem ser criadas no painel de perguntas reutilizáveis, passando pelo fluxo de validação quando aplicável.

## Status editorial

Estados usados na publicação:

- rascunho;
- em revisão;
- ajustes solicitados;
- rejeitada;
- agendada, quando houver data futura;
- publicada.

O estado `aprovada` não precisa existir como etapa separada se a aprovação já leva à publicação ou agendamento conforme regra.

## Publicação direta

Autor não deve publicar diretamente por padrão.

A publicação direta deve depender de permissão específica por usuário. Quando alguém publica sem necessidade de aprovação, admins podem ser notificados por e-mail para acompanhamento.

## Revisão pública

Quando uma publicação passa por revisão, ela pode exibir publicamente os revisores vinculados.

A recomendação é mostrar os nomes como links para suas páginas de autor/perfil público, indicando o papel editorial quando aplicável, por exemplo `Autor/Revisor`.

## SEO e compartilhamento

Publicações usam metadados próprios ou herdados das configurações do site.

Elementos esperados:

- título SEO;
- descrição;
- imagem de compartilhamento;
- dados de autor;
- canonical quando aplicável;
- Open Graph/Twitter cards conforme configuração.

## Leitura, comentários e compartilhamento

A página pública da publicação integra:

- contagem de leituras;
- comentários, quando ativos;
- compartilhamento;
- autoria;
- datas;
- tags e categoria;
- quiz, quando configurado;
- notas e referências em modal;
- botão de apoio/doação, quando habilitado.
