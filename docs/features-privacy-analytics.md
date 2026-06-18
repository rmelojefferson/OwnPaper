# Privacidade, cookies e estatísticas

OwnPaper separa funcionamento essencial de recursos opcionais de rastreamento.

## Cookies essenciais

Usados para sessão, login, CSRF, segurança e preferências mínimas.

## Cookies opcionais

Usados para analytics, pixels, estatísticas internas de permanência e integrações externas que dependam de consentimento.

## Estatísticas internas

A estatística interna foi desenhada como visão rápida operacional, não como substituta de analytics dedicado.

Padrão recomendado:

- eventos brutos: retenção curta, até 3 meses;
- agregados diários: até 12 meses;
- opção de desativar nas configurações do site.

Para análise profunda, use ferramentas externas como Plausible, Umami, Matomo ou analytics do provedor, sempre condicionadas ao consentimento quando aplicável.

## Scripts externos

OwnPaper deve priorizar campos estruturados para integrações conhecidas, evitando que admins insiram JavaScript livre no painel.

## Solicitações de privacidade

Newsletter, comentários e cadastros públicos devem manter trilha para exportação, exclusão e confirmação quando aplicável.

## Usuários do painel

Usuários administrativos precisam aceitar termos do painel. A versão do aceite, IP e user-agent são registrados para auditoria.
