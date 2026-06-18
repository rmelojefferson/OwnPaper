# Mídia, quarentena e sanitização

Uploads de mídia passam por quarentena para reduzir risco técnico e permitir avaliação editorial do conteúdo.

## Tipos suportados por padrão

- imagens: JPG, PNG e WebP;
- documentos: PDF;
- vídeos: formatos aceitos pela configuração e limite padrão de 500 MB.

SVG não é aceito por padrão.

## Fluxo

1. Usuário envia mídia pelo campo específico ou diretamente dentro da publicação.
2. O arquivo entra como mídia pendente.
3. O sistema valida tipo, tamanho e segurança.
4. ClamAV verifica conteúdo suspeito.
5. Imagens e PDFs passam por sanitização quando aplicável.
6. Admin/revisor avalia preview e aprova ou rejeita.
7. Quando aprovada, a mídia pendente é efetivada no local planejado.

## Por que quarentena também para admin

Mesmo admins podem enviar arquivos comprometidos sem saber. A quarentena mantém a mesma trilha de segurança para todos os uploads.

## Arquivos suspeitos

Se o antivírus ou validação detectar risco, o arquivo não deve ser disponibilizado publicamente. O status e o motivo devem ficar visíveis no painel de mídias pendentes.

## Preview

A avaliação editorial deve usar preview de imagem/PDF/vídeo quando possível, para que aprovação não dependa apenas da sanitização técnica.
