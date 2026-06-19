# Configurações do site e operação

As configurações do site centralizam decisões que afetam o site público, o painel e integrações. O objetivo é evitar alterações espalhadas em locais diferentes e tornar cada seção compreensível para admins.

## Configurações do site

A área `Configurações do site` é dividida por seções.

Seções típicas:

- Identidade e SEO;
- Menu e navegação;
- Navegação do site;
- Tema e aparência;
- Integrações e rastreamento;
- Comunicação e comentários;
- Apoio e doações;
- Operação do site;
- Páginas institucionais.

Cada seção deve explicar o que controla, usar inputs alinhados e evitar campos sem contexto.

## Identidade e SEO

Controla identidade pública e metadados padrão.

Campos comuns:

- nome do site;
- título SEO padrão;
- descrição padrão;
- imagem padrão de compartilhamento;
- favicon;
- e-mail de contato;
- textos de rodapé;
- copyright.

A imagem de compartilhamento e o favicon devem ter preview no painel. Quando o usuário troca a imagem, o preview deve atualizar antes de salvar sempre que possível.

A descrição padrão é usada quando uma página/publicação não define descrição própria para SEO e compartilhamento.

O e-mail de contato pode aparecer publicamente quando a configuração permitir; caso contrário, serve como referência operacional para recebimento/identidade do site.

## Menu e navegação

Controla a navegação pública.

Recursos esperados:

- ativar ou não menu customizado;
- configurar item Início;
- fixar Início como primeiro item;
- configurar grupos e subitens;
- controlar comportamento de submenus;
- ajustar logos/imagens de navegação quando aplicável.

O checkbox `Para menus de site` do Wagtail não deve ser apresentado como se controlasse o menu próprio do OwnPaper quando não estiver ligado a essa lógica.

## Navegação do site

Serve para organizar links institucionais e de rodapé.

Deve ficar claro:

- o que afeta cabeçalho;
- o que afeta rodapé;
- onde editar páginas institucionais;
- como ordenar links.

## Tema e aparência

Controla aparência pública.

Inclui:

- tema padrão;
- cores primária e secundária;
- paleta base;
- ícones sociais;
- opções de logo e visual conforme a instalação.

As cores públicas padrão podem derivar das duas cores principais do painel/admin, garantindo identidade consistente em novas instalações.

## Integrações e rastreamento

Controla analytics e integrações externas.

Campos estruturados são preferíveis a JavaScript livre.

Integrações suportadas/recomendadas:

- Google Search Console verification;
- Meta domain verification;
- Google Analytics ID;
- Google Tag Manager ID;
- Meta Pixel ID;
- Plausible;
- Umami;
- Matomo;
- estatísticas internas;
- Shlink/links curtos.

Scripts externos devem respeitar consentimento de cookies quando aplicável.

## Comunicação e comentários

Controla recursos públicos de relacionamento.

Pode incluir:

- comentários ativos/inativos;
- autoinscrição na newsletter a partir de comentários;
- submissões públicas;
- exigência de ORCID em submissões;
- limite de PDF para submissão.

## Apoio e doações

Controla a página de doações e botões públicos.

Recursos:

- ativar/desativar doações;
- exibir no cabeçalho;
- exibir no rodapé;
- exibir em publicações;
- rótulo do botão;
- título da página;
- texto rich text explicando o motivo do apoio;
- PIX chave;
- PIX QR Code;
- PIX copia e cola;
- Apoia.se;
- Buy Me a Coffee;
- PayPal;
- MercadoPago;
- GitHub Sponsors;
- Bitcoin;
- Ethereum;
- link externo adicional;
- detalhes complementares.

O texto padrão de doação deve vir preenchido em novas instalações, mas editável pelo admin.

## Operação do site

Concentra configurações operacionais.

Pode incluir:

- modo manutenção;
- políticas editoriais;
- bloqueio por ORCID;
- notificações;
- backups;
- relatórios;
- retenção de dados;
- recursos experimentais habilitados/desabilitados.

## Páginas institucionais

Permite vincular páginas públicas importantes:

- Sobre;
- Privacidade;
- Cookies;
- Contato;
- Newsletter;
- Indexador;
- Quiz de estudo;
- Doações.

O vínculo evita depender de URLs fixas no template.

## Saúde operacional

A página de saúde operacional deve ajudar admins a identificar problemas sem acessar o servidor.

Itens úteis:

- status de e-mail;
- status de backups;
- integridade de logs;
- tarefas pendentes;
- mídia pendente;
- erros recentes;
- configurações essenciais faltando.

## Logs de atividade

Logs devem ser consultáveis por admins.

A consulta deve permitir:

- busca;
- filtro por usuário;
- filtro por ação;
- filtro por período;
- exportação;
- validação de integridade por hash.

## Redirecionamentos

Redirecionamentos são úteis quando URLs públicas mudam.

Eles devem ser mantidos quando o projeto usa recursos nativos do Wagtail ou precisa preservar SEO.

## Coleções

Coleções são agrupamentos de mídia/documentos do Wagtail.

Podem ser úteis para:

- organizar arquivos por projeto;
- separar permissões de acesso;
- reduzir mistura de mídia entre áreas;
- controlar acervo em instalações maiores.

Se a instalação não usa permissões por coleção, a área pode ser mantida discreta para evitar confusão.
