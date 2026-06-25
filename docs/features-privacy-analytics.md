# Privacidade, cookies e estatísticas

OwnPaper separa recursos essenciais de recursos opcionais de rastreamento e análise. A instalação deve deixar claro o que é coletado, por quanto tempo e com qual finalidade.

## Cookies essenciais

Cookies essenciais são necessários para:

- login;
- sessão;
- proteção CSRF;
- segurança do painel;
- preferências mínimas;
- funcionamento básico do site.

Esses cookies não dependem de aceite opcional quando são estritamente necessários.

## Cookies opcionais

Cookies opcionais podem ser usados para:

- analytics;
- pixels;
- estatísticas internas avançadas;
- integrações externas;
- medição de permanência;
- campanhas.

O visitante deve poder aceitar ou recusar.

## Banner de consentimento

O banner de cookies deve:

- explicar a escolha;
- permitir aceitar;
- permitir recusar;
- manter link para a página de cookies;
- não carregar scripts opcionais antes da decisão;
- permitir mudança posterior quando implementado.

Forçar o aceite não é recomendado. O correto é bloquear recursos opcionais até decisão.

## Página de cookies

A página pública de cookies deve explicar:

- cookies essenciais;
- cookies opcionais;
- analytics internos;
- ferramentas externas configuradas;
- retenção;
- como solicitar informações;
- como alterar preferências.

## Estatísticas internas

As estatísticas internas são um painel de visão rápida, não substituem ferramenta analítica dedicada.

Elas podem incluir:

- leituras totais;
- comentários;
- mensagens;
- usuários;
- publicações;
- média de tempo no site;
- indicadores editoriais;
- indicadores de campanha;
- tendências agregadas.

## Retenção recomendada

Padrão recomendado:

- eventos brutos por até 3 meses;
- agregados diários por até 12 meses;
- opção para desativar estatísticas internas;
- aviso no painel de que análises profundas exigem ferramenta dedicada.

## Eventos brutos

Eventos brutos são registros individuais antes da agregação.

Exemplos:

- visualização de página;
- início de sessão anônima;
- tempo estimado de permanência;
- clique relevante;
- evento de quiz;
- origem/campanha quando permitido.

Eles são úteis para calcular agregados, mas podem crescer muito e ter impacto maior de privacidade. Por isso, a retenção curta é recomendada.

## Agregados

Agregados são dados resumidos.

Exemplos:

- leituras por dia;
- tempo médio por dia;
- comentários por dia;
- mensagens por dia;
- publicações por status;
- envios de newsletter por período.

Agregados reduzem volume e risco, sendo melhores para histórico de médio prazo.

## Códigos personalizados

Integrações externas são feitas por blocos nomeados de HTML, JavaScript ou CSS. O admin escolhe onde cada bloco será inserido:

- cabeçalho/head;
- início do body;
- final do body/rodapé.

Cada bloco pode exigir aceite de cookies opcionais. Use essa opção para analytics, pixels e ferramentas de rastreamento.

Criar, editar ou excluir blocos exige senha atual, 2FA e confirmação explícita de responsabilidade. A ação é registrada em log de auditoria.

## Risco de JavaScript livre

Permitir que admins colem scripts arbitrários cria risco:

- XSS;
- roubo de sessão;
- rastreamento indevido;
- quebra de layout;
- vazamento de dados.

Por isso, OwnPaper deve priorizar campos estruturados e validação de URLs/domínios.

## Solicitações de privacidade

O sistema deve permitir tratar solicitações relacionadas a:

- newsletter;
- comentários;
- cadastro;
- dados do painel quando aplicável;
- exclusão;
- exportação;
- revogação de consentimento.

## Usuários do painel

Usuários administrativos também devem aceitar termos do painel.

O sistema registra:

- versão do termo;
- data/hora;
- IP;
- user-agent;
- usuário.

Isso cria trilha mínima para uso administrativo consciente.
