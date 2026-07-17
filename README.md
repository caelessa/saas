# Frota Fácil SaaS — Fundação 0.1

Base multiempresa para gestão de locadoras.

## Funcionalidades entregues
- Login e isolamento por empresa (tenant)
- Dashboard
- Motoristas e importação de CNH-e por texto/OCR
- Veículos e importação de CRLV-e por texto/OCR
- Quilometragem e histórico
- Investidores e regras de repasse
- Contratos inteligentes por modelo (elétrico/combustão e limite de km)
- Central de documentos com download
- Manutenções
- Estrutura para rastreador, Serpro/Senatran, WhatsApp e assinatura eletrônica

## Acesso inicial
- E-mail: `admin@frotafacil.local`
- Senha: `admin123`

Troque o usuário e a senha antes de uso real.

## Render + Neon
1. Crie um banco PostgreSQL no Neon.
2. No Render, adicione `DATABASE_URL` e cole a connection string do Neon.
3. Adicione `SECRET_KEY` com uma chave longa e aleatória.
4. Build: `pip install -r requirements.txt`
5. Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120`

## Observação sobre OCR
A leitura direta de PDF é tentada primeiro. Se o PDF for imagem, o sistema tenta OCR local. No Render, o executável Tesseract pode precisar ser instalado por Docker ou o OCR deve ser movido para uma API externa. O sistema continua funcionando mesmo sem OCR, permitindo conferência e cadastro manual.

## Próximas etapas de produção
- Migrações com Alembic
- CSRF em todos os formulários
- Recuperação de senha e MFA
- Armazenamento em Cloudflare R2/Azure Blob/S3
- Auditoria e trilha de alterações
- Cobrança SaaS e planos
- APIs reais de rastreamento, WhatsApp e Senatran
- Assinatura eletrônica
- Testes automatizados e LGPD


## OCR no Render
Esta versão usa Docker porque o Tesseract é uma dependência do sistema operacional.
No Render, crie um novo Web Service escolhendo **Language: Docker**.
Mantenha DATABASE_URL e SECRET_KEY nas variáveis de ambiente.
O arquivo apt-packages.txt não é usado pelo runtime Python nativo do Render.
