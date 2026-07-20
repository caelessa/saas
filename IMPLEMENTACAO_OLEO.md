# Manutenção preventiva — troca de óleo

## O que foi implementado
- Campos por veículo: controle ativo, km da última troca, intervalo e margem de alerta.
- Próxima troca calculada automaticamente.
- Status normal, próximo ou vencido na lista de veículos.
- Alertas no dashboard.
- Recalculo automático ao receber uma nova quilometragem pelo link/WhatsApp ou por atualização manual.
- Migração automática das novas colunas sem apagar dados existentes.

## Teste sugerido
1. Abra **Veículos**.
2. Em um veículo existente, clique em **Configurar** na coluna Troca de óleo.
3. Marque **Ativar**.
4. Informe última troca `80000`, intervalo `10000` e alerta `100`.
5. Atualize a quilometragem para `89920`: aparecerá **Faltam 80 km**.
6. Atualize para `90150`: aparecerá **Vencida há 150 km**.
