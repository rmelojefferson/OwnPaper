# Painel administrativo

O painel OwnPaper estende o Wagtail com páginas administrativas próprias e mantém o padrão visual do painel sempre que possível.

## Áreas principais

- Publicações;
- Páginas;
- Perguntas do quiz;
- Mídias pendentes;
- Imagens;
- Documentos;
- Categorias e tags;
- Contato/inbox;
- Newsletter e e-mails;
- Indexador;
- Estatísticas;
- Fluxo editorial;
- Backups;
- Saúde operacional;
- Logs de atividade;
- Configurações do site;
- Usuários.

## Busca global do painel

A busca administrativa centraliza resultados internos e permite filtrar por tipo e vínculo com o usuário.

Use “Vinculados ao meu usuário” para restringir resultados ligados diretamente à conta autenticada.

## Conta do usuário

A área “Minha conta” concentra:

- dados de perfil;
- senha e 2FA;
- preferências de tema e zoom;
- notificações;
- códigos de backup.

## Mobile

O painel funciona em telas pequenas para ações essenciais, mas a recomendação operacional é usar desktop para administração completa.

## Logs

Ações sensíveis geram auditoria. A trilha de logs usa hash encadeado para detectar adulterações.

Validação:

```bash
docker compose exec -T web python manage.py verificar_integridade_logs
```
