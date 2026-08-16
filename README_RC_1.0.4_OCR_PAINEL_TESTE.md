# Frota Fácil — laboratório OCR do painel

Versão de teste para validar a leitura automática da quilometragem em fotos de painéis.

## O que foi adicionado

- Nova tela **Teste OCR painel** no menu lateral.
- Upload JPG/JPEG/PNG/WEBP.
- Seleção opcional de um veículo para comparar com a KM já cadastrada.
- Pré-processamento da imagem em múltiplas versões (contraste, binarização e inversão).
- Várias tentativas do Tesseract com modos de segmentação diferentes.
- Lista de candidatos numéricos e sugestão da quilometragem mais provável.
- Nível de confiança: alta, média ou baixa.
- A tela é somente laboratório: **não altera a KM do veículo**.

## Arquivos

Substituir:
- `app.py`
- `templates/base.html`
- `static/style.css`

Adicionar:
- `services/odometer_ocr_service.py`
- `templates/ocr_painel_teste.html`

Não há alteração de banco e não há nova dependência Python. A imagem-base do projeto já instala `tesseract-ocr` e o `requirements.txt` já contém `pytesseract` e `Pillow`.

## Teste recomendado

1. Fazer deploy.
2. Abrir **Teste OCR painel**.
3. Selecionar opcionalmente o veículo real.
4. Enviar uma foto do painel.
5. Comparar a sugestão com a quilometragem visível na foto.
6. Testar fotos de veículos diferentes e registrar quais acertam/erram.

Quando o laboratório estiver confiável, a leitura pode ser incorporada ao link público de quilometragem para pré-preencher automaticamente o campo KM, sempre com confirmação humana.
