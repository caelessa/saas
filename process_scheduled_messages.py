"""Worker simples para Cron Job (Render) / tarefa agendada (Azure).

Executar, por exemplo, a cada 15 minutos:
    python process_scheduled_messages.py
"""
from app import app, processar_mensagens_agendadas

if __name__ == '__main__':
    with app.app_context():
        total = processar_mensagens_agendadas(None, limit=1000)
        print(f'Frota Fácil: {total} mensagem(ns) agendada(s) processada(s).')
