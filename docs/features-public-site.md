# Site público

O site público é a camada de leitura do OwnPaper. Ele usa páginas Wagtail e configurações centralizadas para entregar publicações, páginas institucionais, busca, comentários, quiz, newsletter, contato, indexador e doações.

## Home

A home pode exibir:

- destaques;
- últimas publicações;
- autores;
- datas de publicação e atualização;
- contadores de leitura;
- categorias e tags;
- links para publicações;
- elementos de navegação configuráveis.

No tema escuro e claro, a paleta deve preservar contraste e consistência de títulos, autores e links.

## Cabeçalho

O cabeçalho pode incluir:

- logo;
- menu principal;
- submenus;
- RSS;
- botão `Apoie`, quando habilitado;
- alternância de tema, quando configurada;
- busca pública, quando disponível.

Menus suspensos devem abrir por clique e recolher ao clicar fora.

## Publicações públicas

A página pública de publicação mostra:

- título;
- resumo;
- autores;
- revisores, quando aplicável;
- data de publicação;
- data de atualização;
- usuário responsável pela atualização quando diferente do autor;
- categoria;
- tags;
- imagem principal;
- corpo;
- mídia;
- notas, créditos e referências;
- quiz;
- comentários;
- compartilhamento;
- botão de apoio, quando habilitado.

## Notas e referências em pop-up

Notas, créditos e referências são abertas em modal/pop-up para evitar que o leitor perca o ponto de leitura.

Esse é um diferencial central do projeto.

A experiência deve funcionar em:

- desktop;
- mobile;
- navegação por teclado;
- tema claro e escuro.

## Busca pública

A busca pública pode filtrar conteúdo por:

- termo;
- período;
- categoria;
- tag;
- autor;
- status público, quando aplicável.

Essa busca é separada da busca do painel administrativo.

## Autores

Autores possuem página pública.

Ela pode exibir:

- nome;
- foto;
- mini bio;
- redes sociais;
- papel público, como autor/revisor;
- publicações vinculadas.

Usuários que começaram como autores temporários via submissão pública podem ter perfil completado depois.

## Comentários

Comentários podem ser habilitados ou desabilitados.

Fluxo recomendado:

- visitante envia comentário;
- comentário passa por status pendente, quando moderação está ativa;
- admin/revisor avalia;
- comentário aprovado aparece publicamente;
- consentimento e privacidade são registrados quando necessário.

## Newsletter pública

A página de newsletter permite inscrição e consentimento.

O sistema deve registrar eventos relevantes para auditoria e privacidade.

## Contato

A página de contato envia mensagens para o caixa de entrada administrativo.

Campos devem ser sanitizados e protegidos contra abuso.

## Indexador

O indexador permite carregar e consultar dados por CSV, conforme a instalação.

A importação deve validar conteúdo para evitar colunas perigosas, quebras estruturais ou dados incompatíveis.

## Quiz de estudo

O site pode oferecer uma área de quiz de estudo independente das publicações.

Essa área usa perguntas do catálogo reutilizável.

## Doações e apoio

A página de doações é opcional.

Métodos configuráveis:

- PIX por chave;
- PIX por QR Code;
- Apoia.se;
- Buy Me a Coffee;
- PayPal;
- MercadoPago;
- GitHub Sponsors;
- Bitcoin;
- Ethereum;
- link externo adicional.

O botão `Apoie` pode aparecer no cabeçalho, rodapé e final das publicações, conforme configuração.

## Cookies

A página de cookies explica cookies essenciais e opcionais.

O banner deve permitir aceite ou recusa de cookies opcionais. Recursos de analytics e rastreamento devem respeitar essa escolha.

## Páginas institucionais

Páginas como Sobre, Privacidade, Cookies, Contato, Newsletter e Indexador podem ser vinculadas nas configurações do site.

A navegação institucional deve ser clara e editável pelo admin.

## RSS

O RSS permite acompanhamento externo das publicações.

O botão de RSS pode aparecer próximo ao botão de apoio.
