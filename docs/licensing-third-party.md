# Licenças e terceiros

OwnPaper usa licença MIT para o código próprio do projeto.

As dependências, imagens Docker e bibliotecas de sistema mantêm suas próprias licenças. O inventário técnico principal fica em `THIRD_PARTY_NOTICES.md` na raiz do repositório.

## Pontos principais

- O projeto é construído sobre Django e Wagtail, ambos sob BSD-3-Clause.
- O CSS Bulma está vendorizado com cabeçalho MIT preservado.
- ClamAV roda como serviço separado no Docker Compose e usa GPL-2.0 upstream.
- Shlink é opcional e usa MIT upstream.
- Algumas bibliotecas Python usadas para banco, PDF e renderização possuem licenças LGPL ou BSD-style; seus avisos devem ser preservados.

## Recomendação operacional

Antes de redistribuir imagens Docker prontas, audite também:

- pacotes Debian/Alpine incluídos nas imagens;
- bibliotecas transitivas instaladas pelo `pip`;
- imagens Docker externas utilizadas no Compose;
- assets adicionados por cada instalação, como logos, imagens e fontes.

Este inventário não substitui parecer jurídico.
