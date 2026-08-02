import os, uuid, re, json, hashlib, unicodedata
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from sqlalchemy import inspect, text
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from services.document_reader import extract_text, parse_cnh, parse_crlv
from services.storage_service import StorageService, StorageNotFoundError
from services.contract_service import gerar_numero_contrato, registrar_evento_contrato
from services.contract_state_service import ContractStateService, ContractStateError
from services.vehicle_state_service import VehicleStateService, VehicleStateError
from services.pdf_service import gerar_pdf_contrato
from io import BytesIO
from decimal import Decimal

BASE=Path(__file__).parent; UPLOAD=BASE/'uploads'; UPLOAD.mkdir(exist_ok=True)
storage=StorageService(UPLOAD)
app=Flask(__name__)
app.config['SECRET_KEY']=os.getenv('SECRET_KEY','dev-change-me')
url=os.getenv('DATABASE_URL','sqlite:///'+str(BASE/'frota_facil.db'))
if url.startswith('postgres://'): url=url.replace('postgres://','postgresql://',1)
app.config['SQLALCHEMY_DATABASE_URI']=url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
app.config['SQLALCHEMY_ENGINE_OPTIONS']={
 'pool_pre_ping': True,
 'pool_recycle': 240,
 'pool_timeout': 20,
}
app.config['MAX_CONTENT_LENGTH']=12*1024*1024
db=SQLAlchemy(app); login=LoginManager(app); login.login_view='entrar'

class Tenant(db.Model):
 id=db.Column(db.Integer,primary_key=True); nome=db.Column(db.String(120),nullable=False); cnpj=db.Column(db.String(18)); ativo=db.Column(db.Boolean,default=True)
class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,db.ForeignKey('tenant.id'),nullable=False); nome=db.Column(db.String(100)); email=db.Column(db.String(120),unique=True,nullable=False); senha=db.Column(db.String(255)); perfil=db.Column(db.String(30),default='admin'); tenant=db.relationship('Tenant')
class Driver(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); nome=db.Column(db.String(150),nullable=False); cpf=db.Column(db.String(14)); rg=db.Column(db.String(30)); numero_cnh=db.Column(db.String(20)); categoria=db.Column(db.String(5)); data_nascimento=db.Column(db.String(10)); validade_cnh=db.Column(db.String(10)); telefone=db.Column(db.String(30)); email=db.Column(db.String(120)); endereco=db.Column(db.String(250)); logradouro=db.Column(db.String(160)); numero_endereco=db.Column(db.String(20)); complemento=db.Column(db.String(100)); bairro=db.Column(db.String(100)); cidade=db.Column(db.String(100)); uf=db.Column(db.String(2)); cep=db.Column(db.String(10)); status=db.Column(db.String(30),default='Ativo'); criado_em=db.Column(db.DateTime,default=datetime.utcnow)
class Investor(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); nome=db.Column(db.String(150),nullable=False); cpf_cnpj=db.Column(db.String(20)); telefone=db.Column(db.String(30)); email=db.Column(db.String(120)); regra_repasse=db.Column(db.String(30),default='Valor fixo'); observacoes=db.Column(db.Text)
class Vehicle(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); placa=db.Column(db.String(10),nullable=False); renavam=db.Column(db.String(20)); chassi=db.Column(db.String(30)); marca_modelo=db.Column(db.String(150)); ano_fabricacao=db.Column(db.String(4)); ano_modelo=db.Column(db.String(4)); cor=db.Column(db.String(30)); combustivel=db.Column(db.String(100)); km_atual=db.Column(db.Integer,default=0); status=db.Column(db.String(30),default='Disponível'); proprietario_legal=db.Column(db.String(150)); cpf_cnpj_proprietario=db.Column(db.String(20)); investor_id=db.Column(db.Integer,db.ForeignKey('investor.id')); valor_repasse=db.Column(db.Numeric(12,2),default=0); limite_km=db.Column(db.Integer); valor_km_excedente=db.Column(db.Numeric(10,2),default=0); rastreador_id=db.Column(db.String(80)); controlar_oleo=db.Column(db.Boolean,default=False); ultima_troca_oleo_km=db.Column(db.Integer); intervalo_oleo_km=db.Column(db.Integer,default=10000); alerta_oleo_km=db.Column(db.Integer,default=100); current_driver_id=db.Column(db.Integer,db.ForeignKey('driver.id')); current_contract_id=db.Column(db.Integer,db.ForeignKey('contract.id')); status_changed_at=db.Column(db.DateTime); status_reason=db.Column(db.String(255)); investor=db.relationship('Investor'); current_driver=db.relationship('Driver',foreign_keys=[current_driver_id]); current_contract=db.relationship('Contract',foreign_keys=[current_contract_id],post_update=True)
class Odometer(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id')); km=db.Column(db.Integer,nullable=False); origem=db.Column(db.String(40)); data=db.Column(db.DateTime,default=datetime.utcnow); vehicle=db.relationship('Vehicle')
class MileageRequest(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id'),nullable=False); driver_id=db.Column(db.Integer,db.ForeignKey('driver.id'),nullable=False); token=db.Column(db.String(64),unique=True,nullable=False,index=True); status=db.Column(db.String(30),default='Pendente'); expires_at=db.Column(db.DateTime); sent_at=db.Column(db.DateTime,default=datetime.utcnow); submitted_at=db.Column(db.DateTime); km=db.Column(db.Integer); previous_km=db.Column(db.Integer); photo=db.Column(db.String(255)); notes=db.Column(db.Text); vehicle=db.relationship('Vehicle'); driver=db.relationship('Driver')
class ContractTemplate(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); nome=db.Column(db.String(120)); descricao=db.Column(db.String(255)); versao=db.Column(db.Integer,default=1); padrao=db.Column(db.Boolean,default=False); tipo_veiculo=db.Column(db.String(30)); possui_limite_km=db.Column(db.Boolean,default=False); conteudo=db.Column(db.Text); nome_original=db.Column(db.String(255)); gestora_nome=db.Column(db.String(180)); gestora_fantasia=db.Column(db.String(120)); gestora_cnpj=db.Column(db.String(30)); gestora_endereco=db.Column(db.String(255)); parceira_nome=db.Column(db.String(180)); parceira_cnpj=db.Column(db.String(30)); parceira_endereco=db.Column(db.String(255)); ativo=db.Column(db.Boolean,default=True)
class Contract(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 numero_contrato=db.Column(db.String(30),unique=True,index=True)
 driver_id=db.Column(db.Integer,db.ForeignKey('driver.id'))
 vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id'))
 template_id=db.Column(db.Integer,db.ForeignKey('contract_template.id'))
 template_nome=db.Column(db.String(120))
 template_versao=db.Column(db.Integer,default=1)
 versao=db.Column(db.Integer,default=1)
 data_inicio=db.Column(db.String(10))
 hora_inicio=db.Column(db.String(5))
 data_fim=db.Column(db.String(10))
 periodicidade=db.Column(db.String(30))
 dia_vencimento=db.Column(db.String(30))
 valor_locacao=db.Column(db.Numeric(12,2))
 caucao=db.Column(db.Numeric(12,2))
 franquia=db.Column(db.Numeric(12,2))
 limite_km=db.Column(db.Integer)
 valor_km_excedente=db.Column(db.Numeric(10,2))
 multa_atraso_percentual=db.Column(db.Numeric(6,2))
 juros_mes_percentual=db.Column(db.Numeric(6,2))
 indice_correcao=db.Column(db.String(30))
 prazo_bloqueio_horas=db.Column(db.Integer)
 multa_diaria=db.Column(db.Numeric(12,2))
 taxa_adm_multas_percentual=db.Column(db.Numeric(6,2))
 nacionalidade=db.Column(db.String(60))
 estado_civil=db.Column(db.String(60))
 profissao=db.Column(db.String(100))
 cidade_assinatura=db.Column(db.String(100))
 status=db.Column(db.String(30),default='Gerado')
 texto_final=db.Column(db.Text)
 criado_por_id=db.Column(db.Integer,db.ForeignKey('user.id'))
 criado_em=db.Column(db.DateTime,default=datetime.utcnow)
 atualizado_em=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
 assinado_em=db.Column(db.DateTime)
 assinatura_id=db.Column(db.String(120))
 documento_id=db.Column(db.Integer,db.ForeignKey('document.id'))
 arquivo_pdf=db.Column(db.String(255))
 hash_documento=db.Column(db.String(64))
 codigo_publico=db.Column(db.String(24),unique=True,index=True)
 enviado_whatsapp_em=db.Column(db.DateTime)
 visualizado_em=db.Column(db.DateTime)
 gerado_em=db.Column(db.DateTime)
 driver=db.relationship('Driver')
 vehicle=db.relationship('Vehicle',foreign_keys=[vehicle_id])
 template=db.relationship('ContractTemplate')
 criado_por=db.relationship('User')

class ContractEvent(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 contract_id=db.Column(db.Integer,db.ForeignKey('contract.id'),nullable=False,index=True)
 user_id=db.Column(db.Integer,db.ForeignKey('user.id'))
 evento=db.Column(db.String(60),nullable=False)
 descricao=db.Column(db.Text)
 status_anterior=db.Column(db.String(30))
 status_novo=db.Column(db.String(30))
 criado_em=db.Column(db.DateTime,default=datetime.utcnow,index=True)
 user=db.relationship('User')
 contract=db.relationship('Contract',backref=db.backref('eventos',lazy='dynamic',cascade='all, delete-orphan'))

class VehicleEvent(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id'),nullable=False,index=True)
 contract_id=db.Column(db.Integer,db.ForeignKey('contract.id'))
 driver_id=db.Column(db.Integer,db.ForeignKey('driver.id'))
 user_id=db.Column(db.Integer,db.ForeignKey('user.id'))
 evento=db.Column(db.String(60),nullable=False)
 descricao=db.Column(db.Text)
 status_anterior=db.Column(db.String(30))
 status_novo=db.Column(db.String(30))
 criado_em=db.Column(db.DateTime,default=datetime.utcnow,index=True)
 vehicle=db.relationship('Vehicle',foreign_keys=[vehicle_id])
 contract=db.relationship('Contract',foreign_keys=[contract_id])
 driver=db.relationship('Driver',foreign_keys=[driver_id])
 user=db.relationship('User',foreign_keys=[user_id])

class Document(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); tipo=db.Column(db.String(40)); entidade=db.Column(db.String(30)); entidade_id=db.Column(db.Integer); identificador=db.Column(db.String(180),index=True); numero_documento=db.Column(db.String(60),index=True); nome_original=db.Column(db.String(255)); arquivo=db.Column(db.String(255)); hash_sha256=db.Column(db.String(64)); status=db.Column(db.String(20),default='Ativo'); versao=db.Column(db.Integer,default=1); criado_em=db.Column(db.DateTime,default=datetime.utcnow)
class Maintenance(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id')); tipo=db.Column(db.String(100)); data=db.Column(db.String(10)); km=db.Column(db.Integer); custo=db.Column(db.Numeric(12,2)); proxima_km=db.Column(db.Integer); proxima_data=db.Column(db.String(10)); observacoes=db.Column(db.Text); vehicle=db.relationship('Vehicle')
class Alert(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); titulo=db.Column(db.String(150)); mensagem=db.Column(db.Text); nivel=db.Column(db.String(20),default='info'); lido=db.Column(db.Boolean,default=False); criado_em=db.Column(db.DateTime,default=datetime.utcnow)
class Integration(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); tipo=db.Column(db.String(40)); ativo=db.Column(db.Boolean,default=False); configuracao=db.Column(db.Text)
@login.user_loader
def load_user(uid):
 return User.query.options(joinedload(User.tenant)).filter_by(id=int(uid)).first()
def tid(): return current_user.tenant_id


def json_safe(value):
 if value is None or isinstance(value,(str,int,float,bool)):
  return value
 if isinstance(value,(datetime,date)):
  return value.isoformat()
 if isinstance(value,Decimal):
  return str(value)
 return str(value)

def model_rows(model, tenant_id):
 rows=[]
 for item in model.query.filter_by(tenant_id=tenant_id).all():
  rows.append({column.name:json_safe(getattr(item,column.name)) for column in item.__table__.columns})
 return rows

def tenant_backup_payload(tenant_id):
 tenant=Tenant.query.get(tenant_id)
 models=[Driver,Investor,Vehicle,Odometer,MileageRequest,ContractTemplate,Contract,ContractEvent,Document,Maintenance,Alert,Integration]
 return {
  'formato':'frota-facil-tenant-backup-v1',
  'gerado_em_utc':datetime.now(timezone.utc).isoformat(),
  'tenant':{'id':tenant.id,'nome':tenant.nome,'cnpj':tenant.cnpj,'ativo':tenant.ativo},
  'usuarios':model_rows(User,tenant_id),
  'dados':{model.__tablename__:model_rows(model,tenant_id) for model in models},
 }



def limpar_campo_ocr_veiculo(campo, valor):
 valor=(valor or '').strip()
 valor=re.sub(r'\s+',' ',valor)
 if campo=='combustivel':
  # Corrige concatenações comuns do OCR do CRLV, como:
  # ELETRICO/FONTE EXTERNAPARTICULAR
  valor=re.sub(r'(?i)(FONTE EXTERNA)(PARTICULAR|ALUGUEL|OFICIAL|APRENDIZAGEM)$',r'\1',valor)
  valor=re.sub(r'(?i)(ELETRICO)(PARTICULAR|ALUGUEL|OFICIAL|APRENDIZAGEM)$',r'\1',valor)
  return valor[:100]
 limites={
  'placa':10,'renavam':20,'chassi':40,'marca_modelo':120,
  'ano_fabricacao':10,'ano_modelo':10,'cor':40,'status':30,
  'proprietario_legal':180,'cpf_cnpj_proprietario':30,'rastreador_id':80,
 }
 return valor[:limites.get(campo,255)]

def slug_documento(value, fallback='SEM-NOME'):
 value=unicodedata.normalize('NFKD',value or '').encode('ascii','ignore').decode('ascii')
 value=re.sub(r'[^A-Za-z0-9]+','-',value.upper()).strip('-')
 return value[:60] or fallback

def extensao_segura(nome_original):
 ext=Path(nome_original or '').suffix.lower()
 return ext if ext in {'.pdf','.png','.jpg','.jpeg','.webp'} else '.bin'

def identificador_documento(tipo, entidade_id, referencia, ano=None):
 tipo=slug_documento(tipo,'DOC')
 referencia=slug_documento(referencia)
 ano=str(ano or datetime.now().year)
 return f'{tipo}-{int(entidade_id):06d}-{referencia}-{ano}'

def armazenar_documento_cadastro(tipo, entidade, entidade_id, referencia, numero_documento, nome_original, temp_key, mimetype, ano=None):
 """Move o arquivo temporário do OCR para a pasta definitiva e registra no banco."""
 if not temp_key:
  return None
 prefixo=f'{tid()}/temporarios/'
 if not temp_key.startswith(prefixo):
  raise ValueError('Chave temporária inválida.')
 conteudo=storage.download(temp_key)
 identificador=identificador_documento(tipo,entidade_id,referencia,ano)
 ext=extensao_segura(nome_original)
 chave=f'{tid()}/documentos/{entidade.lower()}s/{entidade_id}/{tipo.lower()}/{identificador}{ext}'
 storage.upload(BytesIO(conteudo),chave,mimetype or 'application/octet-stream')
 documento=Document(
  tenant_id=tid(),
  tipo=tipo,
  entidade=entidade,
  entidade_id=entidade_id,
  identificador=identificador,
  numero_documento=(numero_documento or '').strip() or None,
  nome_original=secure_filename(nome_original or f'{identificador}{ext}'),
  arquivo=chave,
  hash_sha256=hashlib.sha256(conteudo).hexdigest(),
  status='Ativo',
 )
 db.session.add(documento)
 storage.delete(temp_key)
 return documento

SAO_PAULO=ZoneInfo("America/Sao_Paulo")

def agora_sao_paulo_naive():
 return datetime.now(SAO_PAULO).replace(tzinfo=None)

def endereco_completo_motorista(driver):
 partes=[]
 if driver.logradouro:
  linha=driver.logradouro
  if driver.numero_endereco: linha+=f", nº {driver.numero_endereco}"
  partes.append(linha)
 if driver.complemento: partes.append(driver.complemento)
 local=", ".join([x for x in [driver.bairro,driver.cidade] if x])
 if driver.uf: local=(local+("/" if local else "")+driver.uf)
 if local: partes.append(local)
 if driver.cep: partes.append(f"CEP {driver.cep}")
 return ", ".join(partes) if partes else (driver.endereco or "A preencher")

def valor_extenso(valor):
 from num2words import num2words
 try: return num2words(Decimal(str(valor or 0)),lang="pt_BR",to="currency")
 except Exception: return "valor não informado"

def normalize_phone(value):
 digits=re.sub(r'\D','',value or '')
 if not digits: return ''
 if digits.startswith('00'): digits=digits[2:]
 if len(digits) in (10,11): digits='55'+digits
 return digits

def active_request(vehicle_id, driver_id):
 return MileageRequest.query.filter_by(tenant_id=tid(),vehicle_id=vehicle_id,driver_id=driver_id,status='Pendente').filter(MileageRequest.expires_at>datetime.utcnow()).order_by(MileageRequest.id.desc()).first()

def oil_status(v):
 if not v.controlar_oleo or v.ultima_troca_oleo_km is None or not v.intervalo_oleo_km:
  return {'state':'off','label':'Não configurado','remaining':None,'next_km':None}
 next_km=v.ultima_troca_oleo_km+v.intervalo_oleo_km
 remaining=next_km-(v.km_atual or 0)
 alert=v.alerta_oleo_km if v.alerta_oleo_km is not None else 100
 if remaining < 0:
  return {'state':'overdue','label':f'Vencida há {abs(remaining):,} km'.replace(',','.'),'remaining':remaining,'next_km':next_km}
 if remaining <= alert:
  return {'state':'warning','label':f'Faltam {remaining:,} km'.replace(',','.'),'remaining':remaining,'next_km':next_km}
 return {'state':'ok','label':f'Faltam {remaining:,} km'.replace(',','.'),'remaining':remaining,'next_km':next_km}

def migrate_schema():
 additions={
  'vehicle':[
   ('controlar_oleo','BOOLEAN DEFAULT FALSE'),('ultima_troca_oleo_km','INTEGER'),
   ('intervalo_oleo_km','INTEGER DEFAULT 10000'),('alerta_oleo_km','INTEGER DEFAULT 100'),
   ('current_driver_id','INTEGER'),('current_contract_id','INTEGER'),('status_changed_at','TIMESTAMP'),('status_reason','VARCHAR(255)'),
  ],
  'driver':[('logradouro','VARCHAR(160)'),('numero_endereco','VARCHAR(20)'),('complemento','VARCHAR(100)'),('bairro','VARCHAR(100)'),('cidade','VARCHAR(100)'),('uf','VARCHAR(2)'),('cep','VARCHAR(10)')],
  'contract_template':[
   ('descricao','VARCHAR(255)'),('versao','INTEGER DEFAULT 1'),('padrao','BOOLEAN DEFAULT FALSE'),
   ('nome_original','VARCHAR(255)'),('gestora_nome','VARCHAR(180)'),('gestora_fantasia','VARCHAR(120)'),
   ('gestora_cnpj','VARCHAR(30)'),('gestora_endereco','VARCHAR(255)'),('parceira_nome','VARCHAR(180)'),
   ('parceira_cnpj','VARCHAR(30)'),('parceira_endereco','VARCHAR(255)'),
  ],
  'contract':[
   ('template_nome','VARCHAR(120)'),('template_versao','INTEGER DEFAULT 1'),('hora_inicio','VARCHAR(5)'),
   ('periodicidade','VARCHAR(30)'),('dia_vencimento','VARCHAR(30)'),('multa_atraso_percentual','NUMERIC(6,2)'),
   ('juros_mes_percentual','NUMERIC(6,2)'),('indice_correcao','VARCHAR(30)'),('prazo_bloqueio_horas','INTEGER'),
   ('multa_diaria','NUMERIC(12,2)'),('taxa_adm_multas_percentual','NUMERIC(6,2)'),('nacionalidade','VARCHAR(60)'),
   ('estado_civil','VARCHAR(60)'),('profissao','VARCHAR(100)'),('cidade_assinatura','VARCHAR(100)'),
   ('numero_contrato','VARCHAR(30)'),('versao','INTEGER DEFAULT 1'),('criado_por_id','INTEGER'),
   ('criado_em','TIMESTAMP'),('atualizado_em','TIMESTAMP'),('assinado_em','TIMESTAMP'),
   ('assinatura_id','VARCHAR(120)'),('documento_id','INTEGER'),('arquivo_pdf','VARCHAR(255)'),('hash_documento','VARCHAR(64)'),('codigo_publico','VARCHAR(24)'),('enviado_whatsapp_em','TIMESTAMP'),('visualizado_em','TIMESTAMP'),('gerado_em','TIMESTAMP'),
  ],
 }
 inspector=inspect(db.engine)
 for table_name,fields in additions.items():
  if table_name not in inspector.get_table_names():
   continue
  columns={c['name'] for c in inspector.get_columns(table_name)}
  for name,definition in fields:
   if name not in columns:
    with db.engine.begin() as conn:
     conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {name} {definition}'))

LOCADRIVERS_TEMPLATE_VERSION=2

def moeda_br(value):
 try:
  n=Decimal(str(value or 0))
 except Exception:
  n=Decimal('0')
 return f'{n:,.2f}'.replace(',','X').replace('.',',').replace('X','.')

def data_br(value):
 try:
  return datetime.strptime(value,'%Y-%m-%d').strftime('%d/%m/%Y')
 except Exception:
  return value or ''

def locadrivers_template_completo():
 return """CONTRATO PARTICULAR DE LOCAÇÃO DE VEÍCULO PARA TRANSPORTE PRIVADO POR APLICATIVO

IDENTIFICAÇÃO DAS PARTES

GESTORA DA LOCAÇÃO: {{gestora_nome}}, nome fantasia {{gestora_fantasia}}, inscrita no CNPJ sob nº {{gestora_cnpj}}, com endereço em {{gestora_endereco}}, doravante denominada GESTORA ou LOCADORA.

PROPRIETÁRIO DO VEÍCULO: {{proprietario_nome}}, CPF/CNPJ nº {{proprietario_documento}}, legítimo proprietário do veículo objeto deste contrato, doravante denominado PROPRIETÁRIO.

PARCEIRA OPERACIONAL: {{parceira_nome}}, inscrita no CNPJ sob nº {{parceira_cnpj}}, com endereço em {{parceira_endereco}}, doravante denominada PARCEIRA OPERACIONAL.

LOCATÁRIO: {{motorista_nome}}, {{nacionalidade}}, {{estado_civil}}, {{profissao}}, RG nº {{motorista_rg}}, CPF nº {{motorista_cpf}}, CNH nº {{motorista_cnh}}, residente e domiciliado em {{motorista_endereco}}, doravante denominado LOCATÁRIO.

As partes acima identificadas têm, entre si, justo e contratado o presente CONTRATO DE LOCAÇÃO DE VEÍCULO, mediante as cláusulas e condições seguintes.

CLÁUSULA 1ª — DO OBJETO

1.1. O presente contrato tem como objeto a locação do seguinte veículo:
Modelo: {{veiculo_modelo}}
Cor: {{veiculo_cor}}
Ano/Modelo: {{veiculo_ano_fabricacao}}/{{veiculo_ano_modelo}}
Placa: {{veiculo_placa}}
Renavam: {{veiculo_renavam}}
Quilometragem inicial: {{km_inicial}} km

CLÁUSULA 2ª — DO VALOR, PAGAMENTO, CAUÇÃO E INADIMPLÊNCIA

2.1. O LOCATÁRIO pagará o valor {{periodicidade_minuscula}} de R$ {{valor_locacao}} ({{valor_locacao_extenso}}), com vencimento toda {{dia_vencimento}}, via PIX ou boleto bancário.

2.2. No ato da assinatura, o LOCATÁRIO pagará caução no valor de R$ {{caucao}} ({{caucao_extenso}}), que poderá ser utilizada para abatimento de débitos contratuais.

2.3. A caução não cobre multas de trânsito, avarias ou danos ao veículo e será devolvida em até 60 (sessenta) dias úteis após o encerramento do contrato, desde que não existam pendências financeiras ou contratuais.

2.4. O atraso no pagamento acarretará multa de {{multa_atraso_percentual}}% sobre o valor em atraso, juros de {{juros_mes_percentual}}% ao mês sobre o saldo devedor e correção monetária pelo índice {{indice_correcao}}.

2.5. O atraso superior a {{prazo_bloqueio_horas}} horas poderá ocasionar bloqueio do veículo, rescisão contratual, retirada imediata do veículo e cobrança de multa diária de R$ {{multa_diaria}}, limitada ao valor FIPE do veículo.

2.6. O LOCATÁRIO autoriza eventual negativação junto aos órgãos de proteção ao crédito em caso de inadimplência, observadas as exigências legais aplicáveis.

CLÁUSULA 3ª — DO PRAZO

3.1. O presente contrato terá vigência de {{prazo_dias}} dias, com início em {{data_inicio_formatada}} às {{hora_inicio}}, e término previsto para {{data_fim_formatada}}, podendo ser prorrogado por acordo entre as partes até o limite máximo de 1 (um) ano.

CLÁUSULA 4ª — DA RESCISÃO

4.1. A rescisão antecipada pelo LOCATÁRIO antes do terceiro mês implicará multa equivalente à caução, no valor de R$ {{caucao}}.

4.2. Após o terceiro mês, o LOCATÁRIO poderá rescindir o contrato mediante aviso prévio de 7 (sete) dias.

4.3. A LOCADORA poderá rescindir o contrato a qualquer momento, devendo o veículo ser devolvido em até 1 (um) dia corrido após a comunicação.

CLÁUSULA 5ª — DAS CONDIÇÕES E DA VISTORIA DO VEÍCULO

5.1. O LOCATÁRIO declara receber o veículo em perfeitas condições de uso, conservação e funcionamento, conforme vistoria anexa, que integra este contrato.

5.2. O LOCATÁRIO obriga-se a enviar toda segunda-feira fotos externas do veículo, foto do painel com a quilometragem e foto da etiqueta de troca de óleo.

CLÁUSULA 6ª — DO USO DO VEÍCULO

6.1. O veículo deverá ser utilizado exclusivamente pelo LOCATÁRIO para transporte privado por aplicativo.

6.2. É expressamente proibido sublocar, ceder, emprestar ou permitir que terceiro conduza o veículo sem autorização; utilizar o veículo fora do Estado de São Paulo; retirar adesivos obrigatórios; ou utilizá-lo para fins ilícitos.

6.3. A quilometragem semanal fica limitada a {{limite_km}} km. A quilometragem excedente será cobrada no valor de R$ {{valor_km_excedente}} por quilômetro.

CLÁUSULA 7ª — DAS MULTAS DE TRÂNSITO

7.1. O LOCATÁRIO será integralmente responsável pelas multas e infrações de trânsito ocorridas durante a vigência da locação, inclusive pela identificação do condutor e pontuação na CNH.

7.2. As multas deverão ser reembolsadas à LOCADORA acrescidas de {{taxa_adm_multas_percentual}}% de taxa administrativa.

CLÁUSULA 8ª — DAS AVARIAS, SINISTROS E DANOS A TERCEIROS

8.1. O LOCATÁRIO responderá integralmente por danos e colisões, arranhões e mau uso, despesas de guincho e prejuízos causados a terceiros durante a vigência deste contrato.

8.2. Em caso de acidente, roubo ou furto, o LOCATÁRIO deverá comunicar imediatamente a LOCADORA e apresentar boletim de ocorrência em até 2 (dois) dias.

CLÁUSULA 9ª — DO SEGURO

9.1. O veículo possui seguro. Em caso de sinistro, o LOCATÁRIO será responsável pelo pagamento da franquia no valor de R$ {{franquia}} ({{franquia_extenso}}), sem prejuízo de outros valores não cobertos pela apólice quando decorrentes de sua responsabilidade.

CLÁUSULA 10ª — DA DEVOLUÇÃO

10.1. O veículo deverá ser devolvido nas mesmas condições em que foi entregue, ressalvado o desgaste natural decorrente do uso regular.

10.2. Havendo danos, o LOCATÁRIO deverá efetuar o pagamento dos reparos em até 3 (três) dias úteis após a apresentação dos orçamentos.

10.3. A não devolução poderá ensejar as medidas judiciais e criminais cabíveis.

CLÁUSULA 11ª — DAS DISPOSIÇÕES GERAIS

11.1. O PROPRIETÁRIO não possui responsabilidade pela gestão da locação, cobranças ou relação contratual operacional com o LOCATÁRIO.

11.2. Eventuais tolerâncias de qualquer das partes não constituem novação, renúncia ou alteração das condições deste contrato.

11.3. Este contrato não poderá ser cedido ou transferido sem autorização expressa e escrita da LOCADORA.

CLÁUSULA 12ª — DO FORO

12.1. Fica eleito o foro da Comarca de São Paulo/SP para dirimir quaisquer controvérsias oriundas deste contrato, com renúncia a qualquer outro, por mais privilegiado que seja.

E, por estarem de acordo, as partes assinam o presente instrumento.

{{cidade_assinatura}}, {{data_assinatura_formatada}}.


________________________________________
{{gestora_nome}}
GESTORA / LOCADORA


________________________________________
{{proprietario_nome}}
PROPRIETÁRIO


________________________________________
{{motorista_nome}}
LOCATÁRIO


________________________________________
{{parceira_nome}}
PARCEIRA OPERACIONAL


________________________________________        ________________________________________
TESTEMUNHA 1 — Nome/CPF                           TESTEMUNHA 2 — Nome/CPF
"""

def ensure_locadrivers_template(tenant_id, force_new_version=False):
 existing=ContractTemplate.query.filter_by(tenant_id=tenant_id,nome='Locadrivers Completo',versao=LOCADRIVERS_TEMPLATE_VERSION).first()
 if existing and not force_new_version:
  return existing
 ContractTemplate.query.filter_by(tenant_id=tenant_id,padrao=True).update({'padrao':False},synchronize_session=False)
 model=ContractTemplate(
  tenant_id=tenant_id,nome='Locadrivers Completo',descricao='Minuta integral Locadrivers com 12 cláusulas e preenchimento automático.',
  versao=LOCADRIVERS_TEMPLATE_VERSION,padrao=True,tipo_veiculo='Todos',possui_limite_km=True,
  conteudo=locadrivers_template_completo(),nome_original='minuta-locadrivers-v2',
  gestora_nome='LCADRIVER CORRETORA DE ALUGUEL DE VEÍCULOS LTDA',gestora_fantasia='LOCADRIVERS',
  gestora_cnpj='64.406.745/0001-38',gestora_endereco='Av. Deputado Emilio Carlos, nº 656, Vila Caldas, Carapicuíba/SP — CEP 06310-160',
  parceira_nome='L.C.DVS CORRETORA DE ALUGUEL DE VEÍCULOS LTDA',parceira_cnpj='48.758.670/0001-06',
  parceira_endereco='Alameda Araguaia, nº 2104, Alphaville Industrial, Barueri/SP — CEP 06455-000',ativo=True,
 )
 db.session.add(model)
 return model

def seed():
 db.create_all()
 migrate_schema()
 # Garante tabela de histórico após migrações e numera contratos antigos.
 db.create_all()
 for contrato in Contract.query.filter(Contract.numero_contrato.is_(None)).order_by(Contract.id).all():
  contrato.numero_contrato=gerar_numero_contrato(contrato.id,contrato.criado_em or datetime.utcnow())
  if contrato.status in (None,'Ativo'):
   contrato.status='Gerado'
  contrato.versao=contrato.versao or 1
 if not Tenant.query.first():
  t=Tenant(nome='Locadora Demonstração'); db.session.add(t); db.session.flush()
  u=User(tenant_id=t.id,nome='Administrador',email='admin@frotafacil.local',senha=generate_password_hash('admin123')); db.session.add(u)
  base='''CONTRATO DE LOCAÇÃO\nLOCATÁRIO: {{motorista_nome}}, CPF {{motorista_cpf}}, CNH {{motorista_cnh}}.\nVEÍCULO: {{veiculo_modelo}}, placa {{veiculo_placa}}, Renavam {{veiculo_renavam}}.\nVALOR: R$ {{valor_locacao}}. CAUÇÃO: R$ {{caucao}}.\nINÍCIO: {{data_inicio}}. TÉRMINO: {{data_fim}}.\nLIMITE DE KM: {{limite_km}}. EXCEDENTE: R$ {{valor_km_excedente}}/km.'''
  db.session.add_all([ContractTemplate(tenant_id=t.id,nome='Combustão com limite',tipo_veiculo='Combustão',possui_limite_km=True,conteudo=base),ContractTemplate(tenant_id=t.id,nome='Elétrico com limite',tipo_veiculo='Elétrico',possui_limite_km=True,conteudo=base+'\nO LOCATÁRIO se responsabiliza pela recarga e uso de equipamentos homologados.')]); db.session.flush()
 # Instala automaticamente a minuta completa v2 para todos os tenants.
 for tenant in Tenant.query.all():
  ensure_locadrivers_template(tenant.id)
 db.session.commit()

@app.route('/criar-conta',methods=['GET','POST'])
def criar_conta():
 if current_user.is_authenticated: return redirect(url_for('dashboard'))
 if request.method=='POST':
  nome=request.form.get('nome','').strip(); empresa=request.form.get('empresa','').strip(); email=request.form.get('email','').strip().lower(); senha=request.form.get('senha','')
  if not nome or not empresa or not email or len(senha)<6:
   flash('Preencha todos os campos. A senha deve ter pelo menos 6 caracteres.','danger')
  elif User.query.filter_by(email=email).first():
   flash('Este e-mail já está cadastrado.','danger')
  else:
   t=Tenant(nome=empresa,ativo=True); db.session.add(t); db.session.flush()
   u=User(tenant_id=t.id,nome=nome,email=email,senha=generate_password_hash(senha),perfil='admin'); db.session.add(u)
   base='''CONTRATO DE LOCAÇÃO\nLOCATÁRIO: {{motorista_nome}}, CPF {{motorista_cpf}}, CNH {{motorista_cnh}}.\nVEÍCULO: {{veiculo_modelo}}, placa {{veiculo_placa}}, Renavam {{veiculo_renavam}}.\nVALOR: R$ {{valor_locacao}}. CAUÇÃO: R$ {{caucao}}.\nINÍCIO: {{data_inicio}}. TÉRMINO: {{data_fim}}.'''
   db.session.add(ContractTemplate(tenant_id=t.id,nome='Modelo básico',tipo_veiculo='Todos',possui_limite_km=False,conteudo=base,versao=1,padrao=False))
   ensure_locadrivers_template(t.id)
   db.session.commit(); login_user(u); flash('Conta criada. Sua base está limpa e pronta para os cadastros.','success'); return redirect(url_for('dashboard'))
 return render_template('criar_conta.html')

@app.route('/entrar',methods=['GET','POST'])
def entrar():
 if request.method=='POST':
  u=User.query.filter_by(email=request.form['email']).first()
  if u and check_password_hash(u.senha,request.form['senha']): login_user(u); return redirect(url_for('dashboard'))
  flash('E-mail ou senha inválidos.','danger')
 return render_template('login.html')
@app.route('/sair')
@login_required
def sair(): logout_user(); return redirect(url_for('entrar'))
@app.route('/')
@login_required
def dashboard():
 vehicles=Vehicle.query.filter_by(tenant_id=tid()).all()
 oil_alerts=[(v,oil_status(v)) for v in vehicles if oil_status(v)['state'] in ('warning','overdue')]
 system_alerts=Alert.query.filter_by(tenant_id=tid(),lido=False).limit(5).all()
 status_counts={status:0 for status in ['Disponível','Reservado','Alugado','Devolução','Manutenção','Inativo']}
 for vehicle in vehicles:
  status_counts[vehicle.status or 'Disponível']=status_counts.get(vehicle.status or 'Disponível',0)+1
 cards={
  'veiculos':len(vehicles),'motoristas':Driver.query.filter_by(tenant_id=tid()).count(),
  'contratos':Contract.query.filter(Contract.tenant_id==tid(),Contract.status.in_(['Rascunho','Gerado','Enviado','Visualizado','Assinado','Ativo'])).count(),
  'alertas':len(oil_alerts)+Alert.query.filter_by(tenant_id=tid(),lido=False).count(),
  'disponiveis':status_counts.get('Disponível',0),'reservados':status_counts.get('Reservado',0),
  'alugados':status_counts.get('Alugado',0),'manutencao':status_counts.get('Manutenção',0),
 }
 return render_template('dashboard.html',cards=cards,veiculos=sorted(vehicles,key=lambda v:v.id,reverse=True)[:6],alertas=system_alerts,oil_alerts=oil_alerts[:8],oil_status=oil_status)

@app.route('/motoristas',methods=['GET','POST'])
@login_required
def motoristas():
 if request.method=='POST':
  d=Driver(tenant_id=tid(),**{k:request.form.get(k) for k in ['nome','cpf','rg','numero_cnh','categoria','data_nascimento','validade_cnh','telefone','email','endereco','logradouro','numero_endereco','complemento','bairro','cidade','uf','cep','status']})
  db.session.add(d)
  try:
   db.session.flush()
   armazenar_documento_cadastro(
    tipo='CNH',
    entidade='Motorista',
    entidade_id=d.id,
    referencia=d.nome,
    numero_documento=d.numero_cnh,
    nome_original=request.form.get('_documento_nome'),
    temp_key=request.form.get('_documento_temp_key'),
    mimetype=request.form.get('_documento_mimetype'),
    ano=(d.validade_cnh or '')[-4:] if d.validade_cnh else None,
   )
   db.session.commit()
  except Exception:
   db.session.rollback()
   app.logger.exception('Falha ao cadastrar motorista e armazenar CNH')
   flash('Não foi possível concluir o cadastro e armazenar a CNH. Tente novamente.','danger')
   return redirect(url_for('motoristas'))
  flash('Motorista cadastrado e CNH armazenada automaticamente.','success')
  return redirect(url_for('motoristas'))
 return render_template('motoristas.html',items=Driver.query.filter_by(tenant_id=tid()).order_by(Driver.nome))
@app.route('/motoristas/importar',methods=['POST'])
@login_required
def importar_motorista():
 f=request.files.get('arquivo')
 if not f:
  flash('Selecione um arquivo.','danger')
  return redirect(url_for('motoristas'))

 nome_original=secure_filename(f.filename or 'cnh')
 mimetype=f.mimetype or 'application/octet-stream'
 conteudo=f.read()
 temp_key=f'{tid()}/temporarios/{uuid.uuid4().hex}_{nome_original}'
 try:
  storage.upload(BytesIO(conteudo),temp_key,mimetype)
  # Libera a conexão durante o OCR.
  db.session.remove()
  arquivo_ocr=FileStorage(stream=BytesIO(conteudo),filename=nome_original,content_type=mimetype)
  texto=extract_text(arquivo_ocr, document_type='cnh')
  dados=parse_cnh(texto)
  return render_template('confirmar_motorista.html',dados=dados,documento_temp_key=temp_key,documento_nome=nome_original,documento_mimetype=mimetype)
 except Exception as exc:
  try: storage.delete(temp_key)
  except Exception: pass
  app.logger.exception('Falha ao processar CNH')
  flash(f'Não foi possível processar a CNH: {exc}','danger')
  return redirect(url_for('motoristas'))
 finally:
  db.session.remove()
@app.route('/motoristas/excluir/<int:id>',methods=['POST'])
@login_required
def excluir_motorista(id):
 x=Driver.query.filter_by(id=id,tenant_id=tid()).first_or_404(); db.session.delete(x); db.session.commit(); return redirect(url_for('motoristas'))

@app.route('/investidores',methods=['GET','POST'])
@login_required
def investidores():
 if request.method=='POST':
  x=Investor(tenant_id=tid(),nome=request.form['nome'],cpf_cnpj=request.form.get('cpf_cnpj'),telefone=request.form.get('telefone'),email=request.form.get('email'),regra_repasse=request.form.get('regra_repasse'),observacoes=request.form.get('observacoes')); db.session.add(x); db.session.commit(); flash('Investidor cadastrado.','success'); return redirect(url_for('investidores'))
 return render_template('investidores.html',items=Investor.query.filter_by(tenant_id=tid()).order_by(Investor.nome))

@app.route('/veiculos',methods=['GET','POST'])
@login_required
def veiculos():
 if request.method=='POST':
  campos_veiculo=['placa','renavam','chassi','marca_modelo','ano_fabricacao','ano_modelo','cor','combustivel','status','proprietario_legal','cpf_cnpj_proprietario','rastreador_id']
  vals={k:limpar_campo_ocr_veiculo(k,request.form.get(k)) for k in campos_veiculo}
  v=Vehicle(tenant_id=tid(),**vals,km_atual=int(request.form.get('km_atual') or 0),investor_id=request.form.get('investor_id') or None,valor_repasse=request.form.get('valor_repasse') or 0,limite_km=request.form.get('limite_km') or None,valor_km_excedente=request.form.get('valor_km_excedente') or 0,controlar_oleo=bool(request.form.get('controlar_oleo')),ultima_troca_oleo_km=request.form.get('ultima_troca_oleo_km') or None,intervalo_oleo_km=request.form.get('intervalo_oleo_km') or 10000,alerta_oleo_km=request.form.get('alerta_oleo_km') or 100)
  db.session.add(v)
  try:
   db.session.flush()
   db.session.add(Odometer(tenant_id=tid(),vehicle_id=v.id,km=v.km_atual,origem='Cadastro'))
   armazenar_documento_cadastro(
    tipo='CRLV',
    entidade='Veículo',
    entidade_id=v.id,
    referencia=v.placa,
    numero_documento=v.renavam,
    nome_original=request.form.get('_documento_nome'),
    temp_key=request.form.get('_documento_temp_key'),
    mimetype=request.form.get('_documento_mimetype'),
    ano=v.ano_modelo,
   )
   db.session.commit()
  except Exception:
   db.session.rollback()
   app.logger.exception('Falha ao cadastrar veículo e armazenar CRLV')
   flash('Não foi possível concluir o cadastro e armazenar o CRLV. Tente novamente.','danger')
   return redirect(url_for('veiculos'))
  flash('Veículo cadastrado e CRLV armazenado automaticamente.','success')
  return redirect(url_for('veiculos'))
 return render_template('veiculos.html',items=Vehicle.query.filter_by(tenant_id=tid()).order_by(Vehicle.placa),investidores=Investor.query.filter_by(tenant_id=tid()).all(),motoristas=Driver.query.filter_by(tenant_id=tid(),status='Ativo').order_by(Driver.nome).all(),oil_status=oil_status)
@app.route('/veiculos/importar',methods=['POST'])
@login_required
def importar_veiculo():
 f=request.files.get('arquivo')
 if not f or not f.filename:
  flash('Selecione um arquivo.','danger')
  return redirect(url_for('veiculos'))
 nome_original=secure_filename(f.filename or 'crlv')
 mimetype=f.mimetype or 'application/octet-stream'
 conteudo=f.read()
 temp_key=f'{tid()}/temporarios/{uuid.uuid4().hex}_{nome_original}'
 try:
  storage.upload(BytesIO(conteudo),temp_key,mimetype)
  arquivo_ocr=FileStorage(stream=BytesIO(conteudo),filename=nome_original,content_type=mimetype)
  dados=parse_crlv(extract_text(arquivo_ocr))
  return render_template('confirmar_veiculo.html',dados=dados,investidores=Investor.query.filter_by(tenant_id=tid()).all(),documento_temp_key=temp_key,documento_nome=nome_original,documento_mimetype=mimetype)
 except Exception as exc:
  try: storage.delete(temp_key)
  except Exception: pass
  app.logger.exception('Falha ao processar CRLV')
  flash(f'Não foi possível processar o CRLV: {exc}','danger')
  return redirect(url_for('veiculos'))

@app.route('/veiculos/<int:id>/editar',methods=['GET','POST'])
@login_required
def editar_veiculo(id):
 v=Vehicle.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if request.method=='POST':
  for campo in ['placa','renavam','chassi','marca_modelo','ano_fabricacao','ano_modelo','cor','combustivel','status','proprietario_legal','cpf_cnpj_proprietario','rastreador_id']:
   setattr(v,campo,request.form.get(campo))
  v.investor_id=request.form.get('investor_id') or None
  v.valor_repasse=request.form.get('valor_repasse') or 0
  v.limite_km=request.form.get('limite_km') or None
  v.valor_km_excedente=request.form.get('valor_km_excedente') or 0
  v.controlar_oleo=bool(request.form.get('controlar_oleo'))
  v.ultima_troca_oleo_km=request.form.get('ultima_troca_oleo_km') or None
  v.intervalo_oleo_km=request.form.get('intervalo_oleo_km') or 10000
  v.alerta_oleo_km=request.form.get('alerta_oleo_km') or 100
  db.session.commit()
  flash('Veículo atualizado com sucesso.','success')
  return redirect(url_for('veiculos'))
 return render_template('editar_veiculo.html',v=v,investidores=Investor.query.filter_by(tenant_id=tid()).order_by(Investor.nome).all())

@app.route('/veiculos/<int:id>/excluir',methods=['POST'])
@login_required
def excluir_veiculo(id):
 v=Vehicle.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if v.status in ('Reservado','Alugado','Devolução') or Contract.query.filter(Contract.tenant_id==tid(),Contract.vehicle_id==v.id,Contract.status.in_(['Rascunho','Gerado','Enviado','Visualizado','Assinado','Ativo'])).first():
  flash('Não é possível excluir um veículo reservado, alugado ou com contrato vigente.','danger')
  return redirect(url_for('veiculos'))
 contratos=Contract.query.filter_by(tenant_id=tid(),vehicle_id=v.id).count()
 if contratos:
  flash('Este veículo possui contrato(s) vinculado(s) e não pode ser excluído. Altere o status para Vendido ou Inativo para preservar o histórico.','danger')
  return redirect(url_for('veiculos'))

 # Remove as fotos de quilometragem antes dos registros.
 # Fotos novas ficam no Cloudflare R2; nomes antigos sem "/" continuam
 # compatíveis com o armazenamento local usado anteriormente.
 solicitacoes=MileageRequest.query.filter_by(tenant_id=tid(),vehicle_id=v.id).all()
 for solicitacao in solicitacoes:
  if not solicitacao.photo:
   continue
  try:
   if '/' in solicitacao.photo:
    storage.delete(solicitacao.photo)
   else:
    foto=UPLOAD/str(solicitacao.tenant_id)/'odometros'/solicitacao.photo
    if foto.exists():
     foto.unlink()
  except Exception:
   app.logger.warning('Não foi possível remover a foto %s',solicitacao.photo)

 # Remove dados operacionais dependentes do veículo.
 MileageRequest.query.filter_by(tenant_id=tid(),vehicle_id=v.id).delete(synchronize_session=False)
 Odometer.query.filter_by(tenant_id=tid(),vehicle_id=v.id).delete(synchronize_session=False)
 Maintenance.query.filter_by(tenant_id=tid(),vehicle_id=v.id).delete(synchronize_session=False)
 documentos=Document.query.filter_by(tenant_id=tid(),entidade='veiculo',entidade_id=v.id).all()
 for documento in documentos:
  if documento.arquivo:
   try:
    storage.delete(documento.arquivo)
   except Exception:
    app.logger.warning('Não foi possível remover o documento %s',documento.arquivo)
  db.session.delete(documento)
 db.session.delete(v)
 db.session.commit()
 flash('Veículo excluído com sucesso.','success')
 return redirect(url_for('veiculos'))

@app.route('/veiculos/<int:id>/km',methods=['POST'])
@login_required
def atualizar_km(id):
 v=Vehicle.query.filter_by(id=id,tenant_id=tid()).first_or_404(); km=int(request.form['km']); v.km_atual=km; db.session.add(Odometer(tenant_id=tid(),vehicle_id=v.id,km=km,origem=request.form.get('origem','Manual'))); db.session.commit(); flash('Quilometragem atualizada.','success'); return redirect(url_for('veiculos'))

@app.route('/veiculos/<int:id>/oleo',methods=['POST'])
@login_required
def configurar_oleo(id):
 v=Vehicle.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 v.controlar_oleo=bool(request.form.get('controlar_oleo'))
 v.ultima_troca_oleo_km=int(request.form['ultima_troca_oleo_km']) if request.form.get('ultima_troca_oleo_km') else None
 v.intervalo_oleo_km=int(request.form.get('intervalo_oleo_km') or 10000)
 v.alerta_oleo_km=int(request.form.get('alerta_oleo_km') or 100)
 db.session.commit(); flash('Plano de troca de óleo atualizado.','success'); return redirect(url_for('veiculos'))

@app.route('/veiculos/<int:id>/solicitar-km',methods=['POST'])
@login_required
def solicitar_km(id):
 v=Vehicle.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 d=Driver.query.filter_by(id=request.form.get('driver_id'),tenant_id=tid()).first_or_404()
 telefone=normalize_phone(d.telefone)
 if not telefone:
  flash('Cadastre um telefone/WhatsApp válido para o motorista.','danger'); return redirect(url_for('veiculos'))
 req=active_request(v.id,d.id)
 if not req:
  req=MileageRequest(tenant_id=tid(),vehicle_id=v.id,driver_id=d.id,token=uuid.uuid4().hex+uuid.uuid4().hex,expires_at=datetime.utcnow()+timedelta(days=7),previous_km=v.km_atual)
  db.session.add(req); db.session.commit()
 link=url_for('registrar_quilometragem_publica',token=req.token,_external=True)
 mensagem=f'Olá, {d.nome}! Precisamos da quilometragem atual do veículo {v.placa}. Abra o link, tire uma foto do painel e informe o km: {link}'
 from urllib.parse import quote
 return redirect(f'https://wa.me/{telefone}?text={quote(mensagem)}')

@app.route('/km/<token>',methods=['GET','POST'])
def registrar_quilometragem_publica(token):
 req=MileageRequest.query.options(joinedload(MileageRequest.vehicle),joinedload(MileageRequest.driver)).filter_by(token=token).first_or_404()
 if req.status=='Concluído': return render_template('quilometragem_sucesso.html',req=req,ja_enviado=True)
 if req.expires_at and req.expires_at<datetime.utcnow():
  return render_template('quilometragem_publica.html',req=req,expirado=True),410
 if request.method=='POST':
  try: km=int(request.form.get('km',''))
  except ValueError:
   flash('Informe uma quilometragem válida.','danger'); return render_template('quilometragem_publica.html',req=req,expirado=False)
  if km < (req.vehicle.km_atual or 0):
   flash(f'A quilometragem não pode ser menor que a última leitura ({req.vehicle.km_atual:,} km).','danger'); return render_template('quilometragem_publica.html',req=req,expirado=False)
  foto=request.files.get('foto')
  if not foto or not foto.filename:
   flash('A foto do painel é obrigatória.','danger'); return render_template('quilometragem_publica.html',req=req,expirado=False)
  ext=Path(secure_filename(foto.filename)).suffix.lower()
  if ext not in ('.jpg','.jpeg','.png','.webp'):
   flash('Envie uma foto JPG, PNG ou WEBP.','danger'); return render_template('quilometragem_publica.html',req=req,expirado=False)
  chave=f'{req.tenant_id}/odometros/{uuid.uuid4().hex}{ext}'
  try:
   storage.upload(foto.stream,chave,foto.mimetype)
   req.km=km
   req.photo=chave
   req.notes=request.form.get('observacoes')
   req.status='Concluído'
   req.submitted_at=datetime.utcnow()
   req.vehicle.km_atual=km
   db.session.add(Odometer(tenant_id=req.tenant_id,vehicle_id=req.vehicle_id,km=km,origem='Motorista via link'))
   db.session.commit()
  except Exception:
   db.session.rollback()
   app.logger.exception('Falha ao armazenar foto do painel')
   try:
    storage.delete(chave)
   except Exception:
    pass
   flash('Não foi possível armazenar a foto do painel. Tente novamente.','danger')
   return render_template('quilometragem_publica.html',req=req,expirado=False)
  return redirect(url_for('registrar_quilometragem_publica',token=token))
 return render_template('quilometragem_publica.html',req=req,expirado=False)

@app.route('/quilometragens')
@login_required
def quilometragens():
 items=MileageRequest.query.options(joinedload(MileageRequest.vehicle),joinedload(MileageRequest.driver)).filter_by(tenant_id=tid()).order_by(MileageRequest.id.desc()).all()
 return render_template('quilometragens.html',items=items)

@app.route('/quilometragens/<int:id>/foto')
@login_required
def foto_quilometragem(id):
 req=MileageRequest.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if not req.photo:
  abort(404)

 # Compatibilidade com fotos antigas salvas localmente antes do R2.
 if '/' not in req.photo:
  return send_from_directory(UPLOAD/str(tid())/'odometros',req.photo)

 try:
  conteudo=storage.download(req.photo)
 except StorageNotFoundError:
  abort(404)
 except Exception:
  app.logger.exception('Falha ao baixar foto de quilometragem %s',req.id)
  abort(503)

 extensao=Path(req.photo).suffix.lower()
 mimetypes={
  '.jpg':'image/jpeg',
  '.jpeg':'image/jpeg',
  '.png':'image/png',
  '.webp':'image/webp',
 }
 return send_file(
  BytesIO(conteudo),
  mimetype=mimetypes.get(extensao,'application/octet-stream'),
  download_name=f'painel_{req.vehicle_id}_{req.id}{extensao}',
  as_attachment=False,
 )

def gerar_codigo_publico_contrato():
 for _ in range(10):
  codigo='FF-'+uuid.uuid4().hex[:4].upper()+'-'+uuid.uuid4().hex[:4].upper()+'-'+uuid.uuid4().hex[:4].upper()
  if not Contract.query.filter_by(codigo_publico=codigo).first():
   return codigo
 raise RuntimeError('Não foi possível gerar código público único.')

def garantir_codigo_publico_contrato(contrato):
 """Garante código público para contratos antigos criados antes da Sprint 0.9.2C."""
 if contrato.codigo_publico:
  return contrato.codigo_publico
 contrato.codigo_publico=gerar_codigo_publico_contrato()
 db.session.flush()
 return contrato.codigo_publico


def telefone_whatsapp(valor):
 digits=re.sub(r'\D','',valor or '')
 if len(digits) in (10,11): digits='55'+digits
 return digits

@app.route('/veiculos/<int:id>/historico')
@login_required
def historico_veiculo(id):
 v=Vehicle.query.options(joinedload(Vehicle.current_driver),joinedload(Vehicle.current_contract)).filter_by(id=id,tenant_id=tid()).first_or_404()
 eventos=VehicleEvent.query.options(joinedload(VehicleEvent.user),joinedload(VehicleEvent.contract),joinedload(VehicleEvent.driver)).filter_by(tenant_id=tid(),vehicle_id=v.id).order_by(VehicleEvent.criado_em.desc()).all()
 return render_template('veiculo_historico.html',v=v,eventos=eventos)

@app.route('/contratos',methods=['GET','POST'])
@login_required
def contratos():
 if request.method=='POST':
  d=Driver.query.filter_by(id=request.form['driver_id'],tenant_id=tid()).first_or_404()
  v=Vehicle.query.filter_by(id=request.form['vehicle_id'],tenant_id=tid()).first_or_404()
  t=ContractTemplate.query.filter_by(id=request.form['template_id'],tenant_id=tid(),ativo=True).first_or_404()
  data_inicio=request.form.get('data_inicio','')
  data_fim=request.form.get('data_fim','')
  try:
   prazo_dias=(datetime.strptime(data_fim,'%Y-%m-%d')-datetime.strptime(data_inicio,'%Y-%m-%d')).days
  except Exception:
   prazo_dias=90
  proprietario_nome=v.proprietario_legal or (v.investor.nome if v.investor else 'A preencher')
  proprietario_documento=v.cpf_cnpj_proprietario or (v.investor.cpf_cnpj if v.investor else 'A preencher')
  valor_locacao=request.form.get('valor_locacao') or 0
  caucao=request.form.get('caucao') or 0
  franquia=request.form.get('franquia') or 0
  valor_km=request.form.get('valor_km_excedente') or 0
  periodicidade=request.form.get('periodicidade','Semanal')
  repl={
   'gestora_nome':t.gestora_nome or '', 'gestora_fantasia':t.gestora_fantasia or '', 'gestora_cnpj':t.gestora_cnpj or '', 'gestora_endereco':t.gestora_endereco or '',
   'parceira_nome':t.parceira_nome or '', 'parceira_cnpj':t.parceira_cnpj or '', 'parceira_endereco':t.parceira_endereco or '',
   'proprietario_nome':proprietario_nome,'proprietario_documento':proprietario_documento,
   'motorista_nome':d.nome,'motorista_cpf':d.cpf or 'A preencher','motorista_rg':d.rg or 'A preencher','motorista_cnh':d.numero_cnh or 'A preencher','motorista_endereco':endereco_completo_motorista(d),
   'nacionalidade':request.form.get('nacionalidade') or 'brasileiro','estado_civil':request.form.get('estado_civil') or 'solteiro','profissao':request.form.get('profissao') or 'motorista',
   'veiculo_modelo':v.marca_modelo or 'A preencher','veiculo_cor':v.cor or 'A preencher','veiculo_ano_fabricacao':v.ano_fabricacao or 'A preencher','veiculo_ano_modelo':v.ano_modelo or 'A preencher',
   'veiculo_placa':v.placa or 'A preencher','veiculo_renavam':v.renavam or 'A preencher','km_inicial':v.km_atual or 0,
   'periodicidade':periodicidade,'periodicidade_minuscula':periodicidade.lower(),'dia_vencimento':request.form.get('dia_vencimento','segunda-feira'),
   'valor_locacao':moeda_br(valor_locacao),'valor_locacao_extenso':valor_extenso(valor_locacao),'caucao':moeda_br(caucao),'caucao_extenso':valor_extenso(caucao),
   'franquia':moeda_br(franquia),'franquia_extenso':valor_extenso(franquia),'limite_km':request.form.get('limite_km') or '','valor_km_excedente':moeda_br(valor_km),
   'multa_atraso_percentual':request.form.get('multa_atraso_percentual') or '6','juros_mes_percentual':request.form.get('juros_mes_percentual') or '1','indice_correcao':request.form.get('indice_correcao') or 'IGPM',
   'prazo_bloqueio_horas':request.form.get('prazo_bloqueio_horas') or '48','multa_diaria':moeda_br(request.form.get('multa_diaria') or 500),'taxa_adm_multas_percentual':request.form.get('taxa_adm_multas_percentual') or '20',
   'data_inicio_formatada':data_br(data_inicio),'hora_inicio':request.form.get('hora_inicio') or '09:00','data_fim_formatada':data_br(data_fim),'prazo_dias':prazo_dias,
   'cidade_assinatura':request.form.get('cidade_assinatura') or 'Carapicuíba/SP','data_assinatura_formatada':data_br(data_inicio),
  }
  # Regra operacional: um veículo só pode ter um contrato vigente por vez.
  conflito=Contract.query.filter(Contract.tenant_id==tid(),Contract.vehicle_id==v.id,Contract.status.in_(['Rascunho','Gerado','Enviado','Visualizado','Assinado','Ativo'])).first()
  if conflito or v.status not in ('Disponível',None,''):
   flash(f'O veículo {v.placa} não está disponível para um novo contrato.','danger')
   return redirect(url_for('contratos'))
  # O número definitivo depende do ID; primeiro preservamos um marcador no texto.
  repl['numero_contrato']='{{numero_contrato}}'
  texto_final=t.conteudo or ''
  for key,value in repl.items():
   texto_final=texto_final.replace('{{'+key+'}}',str(value))
  c=Contract(
   tenant_id=tid(),driver_id=d.id,vehicle_id=v.id,template_id=t.id,template_nome=t.nome,template_versao=t.versao or 1,
   data_inicio=data_inicio,hora_inicio=repl['hora_inicio'],data_fim=data_fim,periodicidade=periodicidade,dia_vencimento=repl['dia_vencimento'],
   valor_locacao=valor_locacao,caucao=caucao,franquia=franquia,limite_km=request.form.get('limite_km') or None,valor_km_excedente=valor_km,
   multa_atraso_percentual=request.form.get('multa_atraso_percentual') or 6,juros_mes_percentual=request.form.get('juros_mes_percentual') or 1,
   indice_correcao=repl['indice_correcao'],prazo_bloqueio_horas=request.form.get('prazo_bloqueio_horas') or 48,multa_diaria=request.form.get('multa_diaria') or 500,
   taxa_adm_multas_percentual=request.form.get('taxa_adm_multas_percentual') or 20,nacionalidade=repl['nacionalidade'],estado_civil=repl['estado_civil'],
   profissao=repl['profissao'],cidade_assinatura=repl['cidade_assinatura'],texto_final=texto_final,
   status='Gerado',versao=1,criado_por_id=current_user.id,criado_em=agora_sao_paulo_naive(),codigo_publico=gerar_codigo_publico_contrato(),
  )
  db.session.add(c)
  db.session.flush()
  c.numero_contrato=gerar_numero_contrato(c.id,c.criado_em)
  c.texto_final=(c.texto_final or '').replace('{{numero_contrato}}',c.numero_contrato)
  if not c.limite_km:
   c.texto_final=c.texto_final.replace('6.3. A quilometragem semanal fica limitada a  km. A quilometragem excedente será cobrada no valor de R$ '+moeda_br(c.valor_km_excedente)+' por quilômetro.','6.3. Não há limite semanal de quilometragem neste contrato.')
  codigo_publico=garantir_codigo_publico_contrato(c)
  pdf_bytes=gerar_pdf_contrato(c.numero_contrato,c.texto_final,codigo_publico=codigo_publico,url_validacao=url_for('validar_contrato_publico',codigo=codigo_publico,_external=True))
  chave_pdf=f'{tid()}/documentos/contratos/{c.numero_contrato}.pdf'
  storage.upload(BytesIO(pdf_bytes),chave_pdf,'application/pdf')
  hash_pdf=hashlib.sha256(pdf_bytes).hexdigest()
  doc=Document(tenant_id=tid(),tipo='Contrato',entidade='Contrato',entidade_id=c.id,identificador=c.numero_contrato,numero_documento=c.numero_contrato,nome_original=f'{c.numero_contrato}.pdf',arquivo=chave_pdf,hash_sha256=hash_pdf,status='Ativo',versao=c.versao or 1,criado_em=agora_sao_paulo_naive())
  db.session.add(doc); db.session.flush()
  c.documento_id=doc.id; c.arquivo_pdf=chave_pdf; c.hash_documento=hash_pdf; c.gerado_em=agora_sao_paulo_naive()
  registrar_evento_contrato(
   db.session,ContractEvent,tenant_id=tid(),contract_id=c.id,user_id=current_user.id,
   evento='CONTRATO_GERADO',descricao=f'Contrato {c.numero_contrato} gerado com o modelo {c.template_nome} v{c.template_versao}.',
   status_novo='Gerado'
  )
  try:
   VehicleStateService(db.session,VehicleEvent).reserve(
    vehicle=v,contract=c,driver=d,user_id=current_user.id,
    reason=f'Reservado pelo contrato {c.numero_contrato}.',now=agora_sao_paulo_naive()
   )
   db.session.commit()
  except (VehicleStateError,ContractStateError) as exc:
   db.session.rollback()
   flash(str(exc),'danger')
   return redirect(url_for('contratos'))
  flash(f'Contrato {c.numero_contrato} gerado; veículo {v.placa} reservado.','success')
  return redirect(url_for('contrato_detalhe',id=c.id))
 hoje=date.today(); fim=hoje+timedelta(days=90)
 q=(request.args.get('q') or '').strip()
 consulta=Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle)).filter(Contract.tenant_id==tid())
 if q:
  termo=f'%{q}%'
  consulta=consulta.join(Driver,Contract.driver_id==Driver.id).join(Vehicle,Contract.vehicle_id==Vehicle.id).filter(db.or_(
   Contract.numero_contrato.ilike(termo),Contract.status.ilike(termo),Driver.nome.ilike(termo),Driver.cpf.ilike(termo),
   Driver.numero_cnh.ilike(termo),Vehicle.placa.ilike(termo),Vehicle.marca_modelo.ilike(termo),Vehicle.renavam.ilike(termo)
  ))
 return render_template('contratos.html',items=consulta.order_by(Contract.id.desc()).all(),motoristas=Driver.query.filter_by(tenant_id=tid()).all(),veiculos=Vehicle.query.filter_by(tenant_id=tid(),status='Disponível').order_by(Vehicle.placa).all(),modelos=ContractTemplate.query.filter_by(tenant_id=tid(),ativo=True).order_by(ContractTemplate.padrao.desc(),ContractTemplate.id.desc()).all(),hoje=hoje.isoformat(),fim_padrao=fim.isoformat(),q=q)

@app.route('/contratos/<int:id>')
@login_required
def contrato_detalhe(id):
 c=Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle),joinedload(Contract.criado_por)).filter_by(id=id,tenant_id=tid()).first_or_404()
 eventos=ContractEvent.query.options(joinedload(ContractEvent.user)).filter_by(tenant_id=tid(),contract_id=c.id).order_by(ContractEvent.criado_em.desc()).all()
 documento=Document.query.filter_by(id=c.documento_id,tenant_id=tid()).first() if c.documento_id else None
 return render_template('contrato_detalhe.html',c=c,eventos=eventos,documento=documento)

@app.route('/contratos/<int:id>/status',methods=['POST'])
@login_required
def contrato_status(id):
 c=Contract.query.options(joinedload(Contract.vehicle),joinedload(Contract.driver)).filter_by(id=id,tenant_id=tid()).first_or_404()
 novo=(request.form.get('status') or '').strip()
 vehicle_destination=(request.form.get('vehicle_destination') or 'Disponível').strip()
 try:
  service=ContractStateService(db.session,ContractEvent,VehicleEvent)
  service.transition(
   contract=c,new_status=novo,user_id=current_user.id,now=agora_sao_paulo_naive(),
   vehicle_destination=vehicle_destination,
  )
  db.session.commit()
 except (ContractStateError,VehicleStateError) as exc:
  db.session.rollback()
  flash(str(exc),'danger')
  return redirect(url_for('contrato_detalhe',id=id))
 flash(f'Status do contrato {c.numero_contrato} atualizado para {novo}.','success')
 return redirect(url_for('contrato_detalhe',id=id))


@app.route('/contratos/<int:id>/gerar-pdf',methods=['POST'])
@login_required
def gerar_pdf_contrato_existente(id):
 c=Contract.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if c.arquivo_pdf and c.documento_id:
  flash('O PDF deste contrato já está armazenado.','info')
  return redirect(url_for('contrato_detalhe',id=id))
 chave_pdf=f'{tid()}/documentos/contratos/{c.numero_contrato}.pdf'
 try:
  codigo_publico=garantir_codigo_publico_contrato(c)
  pdf_bytes=gerar_pdf_contrato(c.numero_contrato,c.texto_final,codigo_publico=codigo_publico,url_validacao=url_for('validar_contrato_publico',codigo=codigo_publico,_external=True))
  storage.upload(BytesIO(pdf_bytes),chave_pdf,'application/pdf')
  hash_pdf=hashlib.sha256(pdf_bytes).hexdigest()
  doc=Document(tenant_id=tid(),tipo='Contrato',entidade='Contrato',entidade_id=c.id,identificador=c.numero_contrato,numero_documento=c.numero_contrato,nome_original=f'{c.numero_contrato}.pdf',arquivo=chave_pdf,hash_sha256=hash_pdf,status='Ativo',versao=c.versao or 1,criado_em=agora_sao_paulo_naive())
  db.session.add(doc); db.session.flush()
  c.documento_id=doc.id; c.arquivo_pdf=chave_pdf; c.hash_documento=hash_pdf; c.gerado_em=agora_sao_paulo_naive()
  registrar_evento_contrato(db.session,ContractEvent,tenant_id=tid(),contract_id=c.id,user_id=current_user.id,evento='PDF_ARMAZENADO',descricao=f'PDF do contrato {c.numero_contrato} armazenado no Cloudflare R2.',status_novo=c.status)
  db.session.commit()
  flash('PDF gerado e enviado para a Central de Documentos.','success')
 except Exception:
  db.session.rollback()
  try: storage.delete(chave_pdf)
  except Exception: pass
  app.logger.exception('Falha ao gerar PDF do contrato %s',c.id)
  flash('Não foi possível gerar e armazenar o PDF.','danger')
 return redirect(url_for('contrato_detalhe',id=id))

@app.route('/contratos/<int:id>/pdf')
@login_required
def contrato_pdf(id):
 c=Contract.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if not c.arquivo_pdf: abort(404)
 try: conteudo=storage.download(c.arquivo_pdf)
 except StorageNotFoundError: abort(404)
 return send_file(BytesIO(conteudo),as_attachment=True,download_name=f'{c.numero_contrato}.pdf',mimetype='application/pdf')

@app.route('/contratos/<int:id>/texto')
@login_required
def contrato_texto(id):
 c=Contract.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 return send_file(BytesIO((c.texto_final or '').encode('utf-8')),as_attachment=True,download_name=f'{c.numero_contrato or ("contrato_"+str(c.id))}.txt',mimetype='text/plain; charset=utf-8')

@app.route('/contratos/<int:id>/whatsapp')
@login_required
def contrato_whatsapp(id):
 c=Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle)).filter_by(id=id,tenant_id=tid()).first_or_404()
 if not c.arquivo_pdf:
  flash('Gere e armazene o PDF antes de enviá-lo.','warning')
  return redirect(url_for('contrato_detalhe',id=id))
 telefone=telefone_whatsapp(c.driver.telefone)
 if not telefone:
  flash('O motorista não possui telefone válido cadastrado.','danger')
  return redirect(url_for('contrato_detalhe',id=id))
 codigo_publico=garantir_codigo_publico_contrato(c)
 link=url_for('validar_contrato_publico',codigo=codigo_publico,_external=True)
 mensagem=(f'Olá, {c.driver.nome}! Segue o contrato {c.numero_contrato} referente ao veículo '
           f'{c.vehicle.marca_modelo} - placa {c.vehicle.placa}. Acesse para visualizar e validar: {link}')
 c.enviado_whatsapp_em=agora_sao_paulo_naive()
 try:
  if c.status in ('Gerado','Rascunho'):
   ContractStateService(db.session,ContractEvent,VehicleEvent).transition(contract=c,new_status='Enviado',user_id=current_user.id,now=agora_sao_paulo_naive())
  registrar_evento_contrato(db.session,ContractEvent,tenant_id=tid(),contract_id=c.id,user_id=current_user.id,
   evento='WHATSAPP_PREPARADO',descricao=f'Mensagem do contrato {c.numero_contrato} preparada para o WhatsApp de {c.driver.nome}.',status_novo=c.status)
  db.session.commit()
 except (ContractStateError,VehicleStateError) as exc:
  db.session.rollback(); flash(str(exc),'danger'); return redirect(url_for('contrato_detalhe',id=id))
 from urllib.parse import quote
 return redirect(f'https://wa.me/{telefone}?text={quote(mensagem)}')

@app.route('/validar/contrato/<codigo>')
def validar_contrato_publico(codigo):
 c=Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle)).filter_by(codigo_publico=codigo).first_or_404()
 if not c.visualizado_em:
  c.visualizado_em=agora_sao_paulo_naive()
  try:
   if c.status in ('Gerado','Enviado'):
    ContractStateService(db.session,ContractEvent,VehicleEvent).transition(contract=c,new_status='Visualizado',user_id=None,now=agora_sao_paulo_naive())
   db.session.commit()
  except (ContractStateError,VehicleStateError):
   db.session.rollback()
 documento=Document.query.filter_by(id=c.documento_id,tenant_id=c.tenant_id).first() if c.documento_id else None
 return render_template('validar_contrato.html',c=c,documento=documento)

@app.route('/modelos-contrato')
@login_required
def modelos_contrato():
 return render_template('modelos_contrato.html',items=ContractTemplate.query.filter_by(tenant_id=tid()).order_by(ContractTemplate.nome,ContractTemplate.versao.desc()).all())

@app.route('/modelos-contrato/locadrivers',methods=['POST'])
@login_required
def instalar_locadrivers():
 model=ensure_locadrivers_template(tid())
 db.session.commit()
 flash(f'Modelo Locadrivers Completo v{model.versao} instalado e definido como padrão.','success')
 return redirect(url_for('modelos_contrato'))

@app.route('/modelos-contrato/novo',methods=['GET','POST'])
@login_required
def novo_modelo_contrato():
 if request.method=='POST':
  return salvar_modelo_contrato(None)
 return render_template('modelo_contrato_form.html',modelo=None)

@app.route('/modelos-contrato/<int:id>/editar',methods=['GET','POST'])
@login_required
def editar_modelo_contrato(id):
 modelo=ContractTemplate.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if request.method=='POST':
  return salvar_modelo_contrato(modelo)
 return render_template('modelo_contrato_form.html',modelo=modelo)

def salvar_modelo_contrato(modelo):
 conteudo=request.form.get('conteudo','').strip()
 arquivo=request.files.get('arquivo')
 nome_original=None
 if arquivo and arquivo.filename:
  nome_original=secure_filename(arquivo.filename)
  if nome_original.lower().endswith('.txt'):
   conteudo=arquivo.read().decode('utf-8',errors='replace')
  elif nome_original.lower().endswith('.pdf'):
   try: conteudo=extract_text(arquivo,document_type='contract')
   except Exception: flash('Não foi possível extrair o PDF. Cole o texto no campo conteúdo.','warning')
 if not conteudo:
  flash('Informe o conteúdo do contrato.','danger')
  return render_template('modelo_contrato_form.html',modelo=modelo)
 versao=(modelo.versao or 1)+1 if modelo else 1
 novo=ContractTemplate(tenant_id=tid(),nome=request.form['nome'].strip(),descricao=request.form.get('descricao'),versao=versao,padrao=bool(request.form.get('padrao')),tipo_veiculo=request.form.get('tipo_veiculo','Todos'),possui_limite_km=bool(request.form.get('possui_limite_km')),conteudo=conteudo,nome_original=nome_original or (modelo.nome_original if modelo else None),gestora_nome=request.form.get('gestora_nome'),gestora_fantasia=request.form.get('gestora_fantasia'),gestora_cnpj=request.form.get('gestora_cnpj'),gestora_endereco=request.form.get('gestora_endereco'),parceira_nome=request.form.get('parceira_nome'),parceira_cnpj=request.form.get('parceira_cnpj'),parceira_endereco=request.form.get('parceira_endereco'),ativo=True)
 if novo.padrao: ContractTemplate.query.filter_by(tenant_id=tid(),padrao=True).update({'padrao':False},synchronize_session=False)
 db.session.add(novo); db.session.commit(); flash('Nova versão do modelo salva.','success')
 return redirect(url_for('modelos_contrato'))

@app.route('/modelos-contrato/<int:id>/alternar',methods=['POST'])
@login_required
def alternar_modelo_contrato(id):
 modelo=ContractTemplate.query.filter_by(id=id,tenant_id=tid()).first_or_404(); modelo.ativo=not modelo.ativo
 if not modelo.ativo: modelo.padrao=False
 db.session.commit(); return redirect(url_for('modelos_contrato'))

@app.route('/modelos-contrato/<int:id>/padrao',methods=['POST'])
@login_required
def definir_modelo_padrao(id):
 modelo=ContractTemplate.query.filter_by(id=id,tenant_id=tid(),ativo=True).first_or_404()
 ContractTemplate.query.filter_by(tenant_id=tid(),padrao=True).update({'padrao':False},synchronize_session=False); modelo.padrao=True; db.session.commit()
 return redirect(url_for('modelos_contrato'))

@app.route('/documentos',methods=['GET','POST'])
@login_required
def documentos():
 if request.method=='POST':
  f=request.files.get('arquivo')
  if not f or not f.filename:
   flash('Selecione um arquivo.','danger')
   return redirect(url_for('documentos'))
  nome_original=secure_filename(f.filename)
  if not nome_original:
   flash('Nome de arquivo inválido.','danger')
   return redirect(url_for('documentos'))
  chave=f'{tid()}/documentos/{uuid.uuid4().hex}_{nome_original}'
  try:
   conteudo=f.read()
   storage.upload(BytesIO(conteudo),chave,f.mimetype)
   entidade_id=request.form.get('entidade_id') or None
   identificador=identificador_documento(request.form['tipo'],entidade_id or 0,nome_original)
   db.session.add(Document(tenant_id=tid(),tipo=request.form['tipo'],entidade=request.form['entidade'],entidade_id=entidade_id,identificador=identificador,nome_original=nome_original,arquivo=chave,hash_sha256=hashlib.sha256(conteudo).hexdigest(),status='Ativo'))
   db.session.commit()
  except Exception:
   db.session.rollback()
   app.logger.exception('Falha ao armazenar documento')
   try: storage.delete(chave)
   except Exception: pass
   flash('Não foi possível armazenar o documento. Verifique a configuração do Cloudflare R2.','danger')
   return redirect(url_for('documentos'))
  flash('Documento armazenado de forma persistente.','success')
  return redirect(url_for('documentos'))
 q=(request.args.get('q') or '').strip()
 consulta=Document.query.filter_by(tenant_id=tid())
 contratos_relacionados={c.id:c for c in Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle)).filter_by(tenant_id=tid()).all()}
 if q:
  termo=f'%{q}%'
  ids_contratos=[c.id for c in contratos_relacionados.values() if any(q.lower() in (str(v or '').lower()) for v in [c.numero_contrato,c.driver.nome if c.driver else '',c.driver.cpf if c.driver else '',c.vehicle.placa if c.vehicle else '',c.vehicle.marca_modelo if c.vehicle else ''])]
  filtros=[Document.identificador.ilike(termo),Document.numero_documento.ilike(termo),Document.nome_original.ilike(termo),Document.tipo.ilike(termo),Document.entidade.ilike(termo)]
  if ids_contratos: filtros.append(db.and_(Document.entidade=='Contrato',Document.entidade_id.in_(ids_contratos)))
  consulta=consulta.filter(db.or_(*filtros))
 return render_template('documentos.html',items=consulta.order_by(Document.id.desc()).all(),motoristas=Driver.query.filter_by(tenant_id=tid()).all(),veiculos=Vehicle.query.filter_by(tenant_id=tid()).all(),storage_backend=storage.backend_name,q=q,contratos_relacionados=contratos_relacionados)

@app.route('/documentos/<int:id>/baixar')
@login_required
def baixar_documento(id):
 d=Document.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 try:
  conteudo=storage.download(d.arquivo)
 except StorageNotFoundError:
  abort(404)
 except Exception:
  app.logger.exception('Falha ao baixar documento %s',d.id)
  abort(503)
 return send_file(BytesIO(conteudo),as_attachment=True,download_name=d.nome_original,mimetype='application/octet-stream')

@app.route('/documentos/<int:id>/excluir',methods=['POST'])
@login_required
def excluir_documento(id):
 d=Document.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 try:
  storage.delete(d.arquivo)
  db.session.delete(d)
  db.session.commit()
  flash('Documento excluído.','success')
 except Exception:
  db.session.rollback()
  app.logger.exception('Falha ao excluir documento %s',d.id)
  flash('Não foi possível excluir o documento.','danger')
 return redirect(url_for('documentos'))

@app.route('/manutencoes',methods=['GET','POST'])
@login_required
def manutencoes():
 if request.method=='POST':
  m=Maintenance(tenant_id=tid(),vehicle_id=request.form['vehicle_id'],tipo=request.form['tipo'],data=request.form.get('data'),km=request.form.get('km') or None,custo=request.form.get('custo') or 0,proxima_km=request.form.get('proxima_km') or None,proxima_data=request.form.get('proxima_data'),observacoes=request.form.get('observacoes')); db.session.add(m); db.session.commit(); flash('Manutenção registrada.','success'); return redirect(url_for('manutencoes'))
 return render_template('manutencoes.html',items=Maintenance.query.filter_by(tenant_id=tid()).order_by(Maintenance.id.desc()),veiculos=Vehicle.query.filter_by(tenant_id=tid()).all())

@app.route('/administracao/armazenamento')
@login_required
def administracao_armazenamento():
 documentos=Document.query.filter_by(tenant_id=tid()).all()
 fotos=MileageRequest.query.options(joinedload(MileageRequest.vehicle)).filter_by(tenant_id=tid(),status='Concluído').filter(MileageRequest.photo.isnot(None)).all()
 referencias=[]
 for documento in documentos:
  referencias.append({'tipo':'Documento','nome':documento.nome_original or documento.arquivo,'chave':documento.arquivo})
 for foto in fotos:
  referencias.append({'tipo':'Foto do painel','nome':f'{foto.vehicle.placa if foto.vehicle else "Veículo"} — leitura #{foto.id}','chave':foto.photo})

 ausentes=[]
 erro_verificacao=None
 try:
  for item in referencias:
   if '/' not in (item['chave'] or ''):
    existe=(UPLOAD/str(tid())/'odometros'/item['chave']).exists()
   else:
    existe=storage.exists(item['chave'])
   if not existe:
    ausentes.append(item)
 except Exception as exc:
  app.logger.exception('Falha na verificação de integridade')
  erro_verificacao=str(exc)

 try:
  conectado=storage.check_connection() if storage.using_r2 else False
  uso=storage.tenant_usage(tid())
 except Exception as exc:
  app.logger.exception('Falha ao consultar armazenamento')
  conectado=False
  uso={'objects':0,'bytes':0}
  if not erro_verificacao:
   erro_verificacao=str(exc)

 backups=[]
 try:
  if storage.using_r2:
   prefix=f'{tid()}/backups/'
   pagina=storage._client.list_objects_v2(Bucket=storage.bucket_name,Prefix=prefix)
   backups=sorted(
    [{'chave':o['Key'],'tamanho':o['Size'],'data':o['LastModified']} for o in pagina.get('Contents',[])],
    key=lambda x:x['data'],reverse=True
   )[:10]
 except Exception:
  app.logger.exception('Falha ao listar backups')

 return render_template('armazenamento.html',storage_backend=storage.backend_name,conectado=conectado,uso=uso,referencias_total=len(referencias),ausentes=ausentes,erro_verificacao=erro_verificacao,backups=backups)

@app.route('/administracao/backup/criar',methods=['POST'])
@login_required
def criar_backup_tenant():
 payload=tenant_backup_payload(tid())
 conteudo=json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8')
 chave=f'{tid()}/backups/backup_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
 try:
  storage.upload(BytesIO(conteudo),chave,'application/json')
  flash('Backup lógico criado no Cloudflare R2.','success')
 except Exception:
  app.logger.exception('Falha ao criar backup')
  flash('Não foi possível criar o backup.','danger')
 return redirect(url_for('administracao_armazenamento'))

@app.route('/administracao/backup/baixar')
@login_required
def baixar_backup_tenant():
 payload=tenant_backup_payload(tid())
 conteudo=json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8')
 nome=f'backup_frota_facil_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
 return send_file(BytesIO(conteudo),as_attachment=True,download_name=nome,mimetype='application/json')

@app.route('/integracoes')
@login_required
def integracoes(): return render_template('integracoes.html')

with app.app_context(): seed()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=True)
