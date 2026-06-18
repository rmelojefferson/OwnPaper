# Feature Backlog

## Branding e experiência no admin (Wagtail)
- Estilizar telas de login e de cadastro/validação de token 2FA.
- Melhorar visual geral do painel administrativo (layout, tipografia e espaçamentos).
- Permitir personalização de logo e favicon do ambiente administrativo.
- Criar logo SVG próprio (inspirado na linguagem do Wagtail) após envio de briefing detalhado.
- Revisar consistência visual entre telas públicas e administrativas.

## Quiz por publicação
- Habilitar/desabilitar quiz por publicação.
- Exibir uma pergunta por vez.
- Resultado final com total de acertos.
- Opção de refazer apenas as questões erradas.
- Sem limite máximo de perguntas por publicação.

## Banco de questões e página de estudos
- Centralizar perguntas em banco reutilizável.
- Nova página de "Grande Quiz" para estudos.
- Filtro por temas (sugestão: tags) e opção "todas".
- Página conectada nas configurações do site para habilitar/aparecer no menu.

## Busca global do site
- Barra de busca única no site inteiro.
- Resultados unificados com filtros avançados.

## Inbox de contato no admin (atendimento interno)
- Tela de caixa de entrada para mensagens de contato recebidas.
- Responder e-mails diretamente pelo admin (sem sair para webmail).
- Atribuir cada solicitação a admin/autor-escritor responsável.
- Encaminhar solicitações para outro responsável com histórico interno.
- Estados de atendimento (novo, em andamento, respondido, arquivado).

## Disparo de e-mails para usuários (admin)
- Compositor manual de e-mail para disparo em massa por admins.
- Segmentação inicial: todos os usuários, apenas admins, apenas autores/escritores.
- Registro de histórico de campanhas e métricas básicas de envio.
- Permissão exclusiva para administradores.

## Notificações de novas publicações por e-mail
- Opção 1: envio imediato quando houver nova publicação.
- Opção 2: envio consolidado por período (diário/semanal/personalizado).
- Janela de corte baseada na data/hora do último envio bem-sucedido.
- Configuração no painel para habilitar/desabilitar cada estratégia.
- Modelo de e-mail com "últimas publicações" e links públicos.

## Importação de inscritos da newsletter via CSV
- Disponibilizar modelo CSV para download no admin.
- Permitir upload/importação em lote de inscritos para a newsletter.
- Validar formato de e-mail e registrar linhas inválidas com relatório.
- Deduplicar por e-mail (não recriar inscrito já existente).
- Permitir definir status inicial do inscrito importado (ativo/inativo).

## Gestão unificada de navegação (menu + rodapé)
- Criar área única no painel para configurar menu principal e rodapé com a mesma lógica.
- Permitir ordenar itens de rodapé por drag-and-drop.
- Permitir escolher quais links aparecem no rodapé (Contato, Sobre, Privacidade, Cookies, Newsletter, Indexador e links customizados).
- Manter campos de texto superior/inferior do rodapé com link opcional.

## 2FA: códigos de recuperação e reset administrativo
- Gerar códigos de recuperação (ex.: 10 códigos de uso único) ao configurar 2FA.
- Permitir regenerar códigos de recuperação sob demanda.
- Criar ação de reset de 2FA no admin para casos de perda de dispositivo.
- Registrar evento de segurança para cada reset/regeneração.

## Auditoria e logs de atividade
- Criar trilha de auditoria completa: usuário, ação, alvo, timestamp, IP e diff quando aplicável.
- Exibir logs filtráveis no painel (por usuário, tipo de ação e período).
- Incluir referência estável do usuário no log (ID interno + username).
- Permitir exportar logs em CSV por período.

## Backups CSV por e-mail (logs/relatórios)
- Campo no painel para e-mail de destino de backups/relatórios.
- Agendamento com opções de período (diário, semanal, mensal e personalizado).
- Envio de arquivos CSV compactos por e-mail para períodos curtos.
- Política de retenção e histórico de envios no painel.

## Backup do banco e portabilidade
- Implementar rotina de backup do banco de publicações (snapshot completo).
- Permitir exportar e restaurar backup via painel/comando.
- Padronizar formato portável para migração entre ambientes/plataformas.
- Documentar estratégia de versionamento de schema + dados para migrações seguras.

## Pipeline editorial para livro (exportação e edição)
- Exportar publicações selecionadas (ou todas) para formato editável de livro.
- Suportar saída inicial em Markdown/HTML e opção de conversão para DOCX/EPUB/PDF.
- Definir metadados editoriais de livro (ordem de capítulos, capa, prefácio, créditos).
- Avaliar edição de livro na própria plataforma (módulo editorial dedicado).

## Guia de leitura em publicação
- Linha guia que destaca/sublinha a linha sob o cursor do mouse.
- Navegação da linha guia por teclado (setas para cima/baixo).
- Opção de ativar/desativar o recurso na interface de leitura.

## Comentários e avaliação de publicações
- Comentários habilitáveis por publicação e por configuração global.
- Exigir conta autenticada para comentar.
- Opção de identificação reforçada (ex.: verificação por e-mail + vínculo opcional a ORCID) para reduzir perfis falsos.
- Moderação por admin (aprovar, rejeitar, ocultar, bloquear usuário).
- Avaliação por estrelas (1-5) com proteção contra múltiplos votos por conta.
- Exibir média, total de votos e trilha de auditoria de moderação.

## Personalização de cores (painel e site)
- Permitir seleção de 2 a 4 cores base por projeto (hex/paleta).
- Sistema distribuir automaticamente cores no tema claro/escuro.
- Aplicar paleta no painel administrativo e no front do site.
- Manter contraste mínimo e acessibilidade automática.

## Revisão por pares (futuro)
- Estrutura de auditoria independente opcional por projeto.
- Indicação pública de revisão (com/sem revisão e por quem).
- Fluxo opcional para não engessar projetos que não usam revisão.

## Prioridades estratégicas (analisar em breve)
- Criar ambiente de staging espelhando produção para validar mudanças sem risco no site principal.
- Implementar monitoramento/alertas (uptime, erros 500, falhas de e-mail e falhas de backup).
- Definir política LGPD de retenção/anonimização para contatos, newsletter e logs com rotinas automáticas.
- Formalizar checklist de acessibilidade (WCAG) como critério de entrega.
- Fortalecer SEO editorial operacional (metadados obrigatórios, schema.org e canonical).
- Incluir checklist obrigatório no fluxo de publicação antes de liberar conteúdo.
- Documentar plano de continuidade com restore periódico validado.
- Definir decisão de produto sobre revisão por pares (agora, módulo opcional futuro, ou fora do escopo).

## Internacionalização (PT/EN)
- Permitir idioma independente no painel admin e no site público (ex.: admin em PT, site em EN).
- Opção de versão em inglês para textos padrão de interface e mensagens transacionais.
- Base de tradução para menus, rótulos, e-mails e páginas institucionais.
- Estratégia de fallback por idioma e seleção por site/projeto.

## Homologação manual pendente
- Validar UI em desktop real (Chrome, Firefox e Safari).
- Validar UI em mobile real (Android e iOS).
- Validar SMTP real e Turnstile com chaves de produção.
- Validar disparos reais e restore real de backup em ambiente separado.

## Novas pendências registradas (rodada atual)
- Avaliar e escolher encurtador de URL open-source para compartilhamento (comparativo: arquitetura, licença, manutenção e integração).
- Busca avançada de publicações: até 5 termos com operadores `E/OU`, escopo por campo (título/resumo/corpo/tudo) e filtro de idioma (PT/EN/ES).
- Estilização avançada da página de busca e do indexador para o mesmo padrão visual do restante do site.
- Busca multilíngue de alta precisão para instalações específicas: avaliar `PostgreSQL FTS` ou `OpenSearch`, com expansão semântica/indexada e menor dependência de tradução on-demand.
- Agrupar comentários no admin por publicação e facilitar moderação em lote.
- Quiz: comentários por pergunta com opção de resposta por admin/autor e controle de visibilidade pública/privada.
- Traduzir também conteúdo editorial livre (notas de rodapé/referências/comentários) com aviso de tradução automática e fallback seguro.
- Revisar política/base de Cookies para refletir todos os dados coletados no fluxo de comentários autenticados.
