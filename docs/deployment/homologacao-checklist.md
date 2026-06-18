# Checklist de Homologação

## Status atual (automatizado)

- [x] `python manage.py check` sem erros.
- [x] Migrações sem pendências.
- [x] Suíte `conteudo` passando (`22` testes).
- [x] Rotas públicas principais respondendo sem erro 500.
- [x] Home padrão do admin renderizando com controles de zoom tipográfico (A-/A+ até 120%).
- [x] Ordenação alfabética de menus/submenus do admin validada por teste.
- [x] Fluxos de newsletter/campanhas com tracking cobertos por testes.
- [x] Fluxos de backup/validação cobertos por testes.
- [x] Fluxos de busca/rodapé/menu cobertos por testes de smoke e integração.
- [x] Feed RSS (`/rss.xml`) validado por teste automatizado (status, content-type e item).

## Pontos que dependem de homologação manual (UI/produção)

- [ ] Revisão visual em desktop real (Chrome/Firefox/Safari).
- [ ] Revisão visual em mobile real (Android/iOS).
- [ ] Login + setup 2FA + recuperação de senha em ambiente com SMTP real.
- [ ] Turnstile validado com chaves de produção.
- [ ] Teste de envio real de campanhas e notificações periódicas.
- [ ] Teste de restauração real de backup em ambiente separado.

## Observações

- A navegação lateral padrão do Wagtail foi mantida.
- O ajuste de zoom do admin aplica fonte base da interface e persiste no navegador.
