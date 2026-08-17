# Frota Fácil RC 1.0.5.2 — Hotfix Sair

## Alterar no GitHub
Substituir somente:
- `static/style.css`

## Correção
O link **Sair** já existia no `templates/base.html`, mas em monitores com pouca altura o menu lateral ocupava toda a área e empurrava o bloco do usuário/logout para fora da tela.

Este hotfix torna o menu central rolável e mantém o bloco do usuário + **Sair** sempre visível no rodapé da barra lateral.

Não altera banco, rotas, integrações, KM ou demais funcionalidades.
