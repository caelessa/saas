# Frota Fácil RC 1.0.9 — Manutenção histórica + Vistoria guiada

Base: RC 1.0.7 Clicksign CPF + correção de menu da RC 1.0.8.

## 1. Manutenção já realizada
Na tela Manutenções existe agora o campo Situação:
- Agendada / futura
- Já realizada / histórico

Quando marcada como já realizada:
- entra diretamente como Concluída;
- registra data, KM, custo, oficina e observações;
- cria evento no histórico do veículo;
- não gera alerta para a execução passada;
- se uma próxima KM/data for informada, cria um novo ciclo ativo para alertas futuros.

## 2. Vistoria por vídeo guiada
Novo módulo `Vistorias`.

Fluxo:
1. Administrador seleciona um veículo com contrato/motorista vigente.
2. O sistema cria link exclusivo com validade configurável.
3. Motorista abre o link no celular e autoriza câmera/microfone.
4. A gravação é feita pelo navegador usando MediaRecorder; não existe campo de upload/galeria.
5. O Frota Fácil conduz sete etapas com texto + voz: frente, lateral direita, traseira, lateral esquerda, pneus/rodas, interior e painel/KM.
6. A luminosidade é amostrada durante a gravação. Vídeos muito escuros são recusados antes do envio.
7. O vídeo é enviado ao backend e armazenado no Cloudflare R2 (quando configurado).
8. Administrador pode visualizar, aprovar ou pedir nova gravação.
9. A entrega entra no histórico operacional do veículo.

## Limitações desta primeira versão
- A validação de iluminação é heurística e pode precisar de calibração com vídeos reais.
- A restrição de “gravado na hora” é aplicada pela interface: o fluxo usa `getUserMedia` + `MediaRecorder` e não oferece input de arquivo. Não é uma prova antifraude absoluta contra manipulação técnica do navegador.
- A análise automática de avarias/partes mostradas fica para uma evolução futura com IA/visão computacional.
- O upload passa pela aplicação Flask; para vídeos maiores, futuramente recomenda-se upload direto assinado para o R2.

## Arquivos alterados
- `app.py`
- `templates/base.html`
- `templates/manutencoes.html`
- `static/help.js`
- `static/style.css`

## Arquivos novos
- `templates/vistorias.html`
- `templates/vistoria_publica.html`

## Banco
A tabela `inspection`/`Inspection` é criada automaticamente pelo SQLAlchemy no startup via `db.create_all()`. Não há SQL manual.

## Teste recomendado
### Manutenção histórica
1. Manutenções > Registrar manutenção.
2. Situação = Já realizada / histórico.
3. Informar data, KM, custo e oficina.
4. Salvar.
5. Abrir histórico do veículo e confirmar o evento.
6. Se informou próxima KM/data, confirmar que um novo ciclo ativo foi criado.

### Vistoria
1. Use veículo com contrato ativo e motorista com telefone.
2. Vistorias > gerar link.
3. Abrir o link no celular.
4. Ativar câmera e iniciar vistoria.
5. Seguir todas as sete orientações.
6. Finalizar e enviar.
7. No admin, abrir Vistorias > Ver vídeo > Aprovar.

O menu lateral da RC 1.0.8 e o botão `Sair` foram preservados.
