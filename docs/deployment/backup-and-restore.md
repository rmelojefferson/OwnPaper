# Backups e restauração

Backups são parte crítica da operação do OwnPaper. O projeto separa relatório operacional no painel de restauração real no servidor para reduzir risco de exposição.

## O que deve entrar no backup completo

Um backup completo deve incluir:

- banco de dados;
- mídia pública;
- documentos;
- vídeos locais, se usados;
- configurações persistidas;
- logs relevantes;
- arquivos necessários para restauração da instalação;
- checksums;
- manifesto do backup.

Credenciais de ambiente devem ser tratadas com cuidado e não devem ser expostas em relatórios enviados por e-mail.

## Relatório por e-mail

O sistema pode enviar relatório semanal de backup.

O relatório deve conter:

- status;
- data/hora;
- caminho do arquivo no servidor;
- tamanho;
- checksum;
- erro, se houver.

O relatório não deve anexar o backup completo por padrão.

## Download temporário

Quando a instalação não tiver armazenamento externo, pode haver link temporário protegido para baixar o backup.

Regras recomendadas:

- link com token forte;
- expiração curta;
- autenticação reforçada;
- 2FA quando disponível;
- download isolado do restante do sistema;
- auditoria;
- remoção automática após expiração;
- não listar diretórios.

## WebDAV externo

WebDAV é um protocolo para enviar arquivos para um armazenamento remoto compatível.

No OwnPaper, ele serve para copiar backups para outro local, fora do servidor principal.

Configurações sensíveis devem ficar em variáveis de ambiente/backend, não em campos editáveis por qualquer admin do painel.

Exemplos de variáveis:

```env
OWNPAPER_BACKUP_WEBDAV_ENABLED=true
OWNPAPER_BACKUP_WEBDAV_URL=https://backup.example.com/remote.php/dav/files/usuario/ownpaper/
OWNPAPER_BACKUP_WEBDAV_USERNAME=usuario-backup
OWNPAPER_BACKUP_WEBDAV_PASSWORD=senha-forte
```

## Retenção

Retenção define por quanto tempo backups antigos são mantidos.

Exemplo:

- manter backups diários por 7 dias;
- manter backups semanais por 8 semanas;
- manter backups mensais por 12 meses.

A política depende do espaço disponível e do risco operacional.

## Restore

A restauração completa deve ser feita no servidor.

Fluxo recomendado:

1. parar a aplicação;
2. preservar cópia do estado atual;
3. restaurar banco;
4. restaurar mídia;
5. conferir permissões de arquivos;
6. rodar migrações se necessário;
7. executar checks de integridade;
8. subir aplicação;
9. validar painel e site público;
10. registrar o procedimento.

## Teste de restore

Backups sem teste de restauração não devem ser considerados confiáveis.

Homologação mínima:

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py verificar_integridade_logs
```

Além disso, teste real de restore deve ser feito em ambiente separado.
