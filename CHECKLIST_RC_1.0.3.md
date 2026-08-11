# Checklist — RC 1.0.3

## Antes do deploy
- [ ] Baixar uma cópia da versão atual do GitHub.
- [ ] Confirmar que as variáveis de ambiente do Render não serão alteradas.
- [ ] Enviar os arquivos da RC ao GitHub.
- [ ] Fazer Manual Deploy no Render.

## Teste 1 — manutenção futura por data
- [ ] Cadastre uma manutenção com próxima data para daqui a 3 dias.
- [ ] Deixe `Alertar quantos dias antes` em 7.
- [ ] Abra Dashboard.
- [ ] Deve aparecer alerta amarelo de manutenção próxima.

## Teste 2 — manutenção vencida por data
- [ ] Use uma próxima data igual a hoje ou anterior (em ambiente de teste).
- [ ] Abra a Central de Alertas.
- [ ] Deve aparecer alerta vermelho.

## Teste 3 — manutenção por km
- [ ] Veículo atual: exemplo 10.000 km.
- [ ] Próxima manutenção: 10.400 km.
- [ ] Antecedência: 500 km.
- [ ] Deve aparecer alerta amarelo.
- [ ] Atualize o veículo para 10.401 km.
- [ ] Deve passar para vermelho automaticamente.

## Teste 4 — troca de óleo
- [ ] Configure troca de óleo.
- [ ] Envie uma nova leitura próxima do limite.
- [ ] Confirme alerta na Central e Dashboard.

## Regressão
- [ ] Cadastro de motorista/CNH.
- [ ] Cadastro de veículo/CRLV.
- [ ] Geração de contrato.
- [ ] Envio por WhatsApp Web.
- [ ] Link público do contrato.
- [ ] Assinatura eletrônica atual.
- [ ] Foto do painel e atualização de km.
