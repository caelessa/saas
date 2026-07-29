# Hotfix FileStorage no OCR

## Problema
`extract_text()` espera um objeto com os atributos `filename` e `content_type`.
A versão anterior enviava apenas `BytesIO`, que não possui `filename`.

## Correção
O conteúdo em memória agora é encapsulado em:

```python
FileStorage(
    stream=BytesIO(conteudo),
    filename=nome_original,
    content_type=mimetype,
)
```

A correção foi aplicada tanto à importação da CNH quanto do CRLV.
