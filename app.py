import os, uuid, re, json, hashlib, unicodedata, base64, binascii
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
from services.signature_service import SignatureService, SignatureValidationError
from services.communication_service import CommunicationService, CommunicationError
from services.signature_provider_service import SignatureProviderService, SignatureProviderError
from services.alert_service import sync_operational_alerts, maintenance_indicator
from services.maintenance_notification_service import maintenance_message, reminder_datetime
from services.odometer_ocr_service import read_odometer
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
app.config['MAX_CONTENT_LENGTH']=120*1024*1024
db=SQLAlchemy(app); login=LoginManager(app); login.login_view='entrar'

SAO_PAULO_TZ=ZoneInfo('America/Sao_Paulo')

def _as_sao_paulo(value):
 if not value:
  return None
 if isinstance(value,date) and not isinstance(value,datetime):
  return value
 if value.tzinfo is None:
  value=value.replace(tzinfo=timezone.utc)
 return value.astimezone(SAO_PAULO_TZ)

@app.template_filter('sp_datetime')
def sp_datetime(value,fmt='%d/%m/%Y %H:%M'):
 local=_as_sao_paulo(value)
 return local.strftime(fmt) if local else '-'


class Tenant(db.Model):
 id=db.Column(db.Integer,primary_key=True); nome=db.Column(db.String(120),nullable=False); cnpj=db.Column(db.String(18)); ativo=db.Column(db.Boolean,default=True); conferir_km_motorista=db.Column(db.Boolean,default=False)
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
 arquivo_pdf_assinado=db.Column(db.String(255))
 hash_documento_assinado=db.Column(db.String(64))
 documento_assinado_id=db.Column(db.Integer)
 codigo_publico=db.Column(db.String(24),unique=True,index=True)
 enviado_whatsapp_em=db.Column(db.DateTime)
 visualizado_em=db.Column(db.DateTime)
 gerado_em=db.Column(db.DateTime)
 clicksign_envelope_id=db.Column(db.String(80),index=True)
 clicksign_document_id=db.Column(db.String(80))
 clicksign_signer_id=db.Column(db.String(80))
 clicksign_status=db.Column(db.String(30))
 clicksign_sent_at=db.Column(db.DateTime)
 driver=db.relationship('Driver')
 vehicle=db.relationship('Vehicle',foreign_keys=[vehicle_id])
 template=db.relationship('ContractTemplate')
 criado_por=db.relationship('User')

class Signature(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 contract_id=db.Column(db.Integer,db.ForeignKey('contract.id'),nullable=False,unique=True,index=True)
 driver_id=db.Column(db.Integer,db.ForeignKey('driver.id'),nullable=False,index=True)
 status=db.Column(db.String(30),default='Assinada')
 signatario_nome=db.Column(db.String(150),nullable=False)
 cpf_confirmado=db.Column(db.String(14))
 arquivo_assinatura=db.Column(db.String(255),nullable=False)
 hash_assinatura=db.Column(db.String(64),nullable=False)
 hash_documento=db.Column(db.String(64),nullable=False)
 ip=db.Column(db.String(64))
 user_agent=db.Column(db.Text)
 aceite_texto=db.Column(db.Text)
 assinado_em=db.Column(db.DateTime,default=datetime.utcnow,index=True)
 contract=db.relationship('Contract',backref=db.backref('signature',uselist=False,cascade='all, delete-orphan'))
 driver=db.relationship('Driver')

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
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id')); tipo=db.Column(db.String(100)); data=db.Column(db.String(10)); km=db.Column(db.Integer); custo=db.Column(db.Numeric(12,2)); proxima_km=db.Column(db.Integer); proxima_data=db.Column(db.String(10)); proxima_hora=db.Column(db.String(5)); alerta_km_antes=db.Column(db.Integer,default=500); alerta_dias_antes=db.Column(db.Integer,default=7); observacoes=db.Column(db.Text); status=db.Column(db.String(20),default='Ativa',index=True); oficina=db.Column(db.String(160)); notificar_motorista=db.Column(db.Boolean,default=False); lembrete_um_dia=db.Column(db.Boolean,default=True); notificacao_agendamento_id=db.Column(db.Integer); notificacao_lembrete_id=db.Column(db.Integer); concluida_em=db.Column(db.DateTime); concluida_por_id=db.Column(db.Integer,db.ForeignKey('user.id')); vehicle=db.relationship('Vehicle'); concluida_por=db.relationship('User',foreign_keys=[concluida_por_id])
class Inspection(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id'),nullable=False,index=True)
 driver_id=db.Column(db.Integer,db.ForeignKey('driver.id'))
 contract_id=db.Column(db.Integer,db.ForeignKey('contract.id'))
 token=db.Column(db.String(64),unique=True,nullable=False,index=True)
 status=db.Column(db.String(30),default='Pendente',index=True)
 requested_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
 expires_at=db.Column(db.DateTime,index=True)
 started_at=db.Column(db.DateTime)
 submitted_at=db.Column(db.DateTime)
 video_key=db.Column(db.String(255))
 video_mime=db.Column(db.String(80))
 duration_seconds=db.Column(db.Integer)
 brightness_avg=db.Column(db.Numeric(8,2))
 brightness_status=db.Column(db.String(30))
 notes=db.Column(db.Text)
 vehicle=db.relationship('Vehicle',foreign_keys=[vehicle_id])
 driver=db.relationship('Driver',foreign_keys=[driver_id])
 contract=db.relationship('Contract',foreign_keys=[contract_id])

class InspectionAttempt(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 inspection_id=db.Column(db.Integer,db.ForeignKey('inspection.id'),nullable=False,index=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 video_key=db.Column(db.String(255),nullable=False)
 video_mime=db.Column(db.String(80))
 duration_seconds=db.Column(db.Integer)
 brightness_avg=db.Column(db.Numeric(8,2))
 brightness_min=db.Column(db.Numeric(8,2))
 dark_ratio=db.Column(db.Numeric(8,4))
 submitted_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
 decision=db.Column(db.String(30),default='Pendente')
 decision_notes=db.Column(db.Text)
 decided_at=db.Column(db.DateTime)
 inspection=db.relationship('Inspection',backref=db.backref('attempts',lazy=True,order_by='InspectionAttempt.id.desc()'))

class Alert(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); titulo=db.Column(db.String(150)); mensagem=db.Column(db.Text); nivel=db.Column(db.String(20),default='info'); lido=db.Column(db.Boolean,default=False); criado_em=db.Column(db.DateTime,default=datetime.utcnow); source_key=db.Column(db.String(120),index=True); entidade=db.Column(db.String(40)); entidade_id=db.Column(db.Integer); action_url=db.Column(db.String(255)); atualizado_em=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow); resolvido_em=db.Column(db.DateTime)
class Integration(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); tipo=db.Column(db.String(40)); ativo=db.Column(db.Boolean,default=False); configuracao=db.Column(db.Text)

class MessageQueue(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 channel=db.Column(db.String(30),nullable=False,default='whatsapp')
 provider=db.Column(db.String(40),nullable=False,default='whatsapp_web')
 recipient=db.Column(db.String(40),nullable=False,index=True)
 recipient_name=db.Column(db.String(150))
 message_type=db.Column(db.String(50),default='texto')
 body=db.Column(db.Text,nullable=False)
 template_name=db.Column(db.String(120))
 template_parameters=db.Column(db.Text)
 related_entity=db.Column(db.String(40))
 related_entity_id=db.Column(db.Integer)
 status=db.Column(db.String(30),default='PENDENTE',index=True)
 external_id=db.Column(db.String(180),index=True)
 attempts=db.Column(db.Integer,default=0)
 error_message=db.Column(db.Text)
 scheduled_at=db.Column(db.DateTime,index=True)
 sent_at=db.Column(db.DateTime)
 created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
 updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class MessageEvent(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 tenant_id=db.Column(db.Integer,index=True,nullable=False)
 message_id=db.Column(db.Integer,db.ForeignKey('message_queue.id'),nullable=False,index=True)
 event=db.Column(db.String(40),nullable=False)
 description=db.Column(db.Text)
 created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
 message=db.relationship('MessageQueue',backref=db.backref('events',lazy='dynamic',cascade='all, delete-orphan'))
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
 models=[Driver,Investor,Vehicle,Odometer,MileageRequest,ContractTemplate,Contract,ContractEvent,Document,Maintenance,Inspection,Alert,Integration,MessageQueue,MessageEvent]
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



def motorista_atual_veiculo(vehicle):
 # O vínculo gravado pela máquina de estados é a fonte primária.
 if vehicle.current_driver_id and vehicle.current_contract_id and vehicle.status in ('Reservado','Alugado'):
  return Driver.query.filter_by(id=vehicle.current_driver_id,tenant_id=vehicle.tenant_id).first()
 # Fallback para bases antigas que ainda não possuem current_driver_id preenchido.
 contrato=Contract.query.filter(Contract.tenant_id==vehicle.tenant_id,Contract.vehicle_id==vehicle.id,Contract.status.in_(['Gerado','Enviado','Visualizado','Assinado','Ativo'])).order_by(Contract.id.desc()).first()
 return contrato.driver if contrato else None

def criar_mensagem_whatsapp(*, tenant_id, driver, body, message_type, related_entity, related_entity_id, scheduled_at=None, template_name=None, template_parameters=None):
 telefone=normalize_phone(driver.telefone if driver else None)
 if not telefone:
  return None, None, 'Motorista sem telefone/WhatsApp válido.'
 integration=Integration.query.filter_by(tenant_id=tenant_id,tipo='whatsapp').first()
 cfg=CommunicationService.parse_config(integration)
 provider_cfg=(cfg.get('provider') or 'web').lower()
 fila=MessageQueue(
  tenant_id=tenant_id,channel='whatsapp',provider='whatsapp_business' if provider_cfg=='business' else 'whatsapp_web',
  recipient=telefone,recipient_name=driver.nome,message_type=message_type,body=body,template_name=template_name,template_parameters=json.dumps(template_parameters or [],ensure_ascii=False),
  related_entity=related_entity,related_entity_id=related_entity_id,status='AGENDADA' if scheduled_at else 'PENDENTE',
  scheduled_at=scheduled_at,created_at=agora_sao_paulo_naive(),updated_at=agora_sao_paulo_naive(),
 )
 db.session.add(fila); db.session.flush()
 if scheduled_at:
  return fila, None, None
 try:
  result=CommunicationService().send_whatsapp(phone=telefone,message=body,integration=integration,template_name=template_name,template_parameters=template_parameters or [])
  fila.provider=result.provider; fila.status=result.status; fila.external_id=result.external_id; fila.attempts=(fila.attempts or 0)+1
  fila.sent_at=agora_sao_paulo_naive() if result.status=='ENVIADA' else None
  db.session.add(MessageEvent(tenant_id=tenant_id,message_id=fila.id,event=result.status,description='Mensagem processada pelo provedor configurado.',created_at=agora_sao_paulo_naive()))
  return fila, result.redirect_url, None
 except CommunicationError as exc:
  fila.status='FALHA'; fila.error_message=str(exc); fila.attempts=(fila.attempts or 0)+1
  db.session.add(MessageEvent(tenant_id=tenant_id,message_id=fila.id,event='FALHA',description=str(exc),created_at=agora_sao_paulo_naive()))
  return fila, None, str(exc)

def processar_mensagens_agendadas(tenant_id=None, limit=100):
 now=agora_sao_paulo_naive()
 q=MessageQueue.query.filter(MessageQueue.status=='AGENDADA',MessageQueue.scheduled_at.isnot(None),MessageQueue.scheduled_at<=now)
 if tenant_id is not None: q=q.filter(MessageQueue.tenant_id==tenant_id)
 items=q.order_by(MessageQueue.scheduled_at.asc()).limit(limit).all()
 processed=0
 for fila in items:
  integration=Integration.query.filter_by(tenant_id=fila.tenant_id,tipo='whatsapp').first()
  cfg=CommunicationService.parse_config(integration)
  if (cfg.get('provider') or 'web').lower()!='business':
   fila.status='AGUARDANDO_MANUAL'; fila.updated_at=now
   db.session.add(MessageEvent(tenant_id=fila.tenant_id,message_id=fila.id,event='AGUARDANDO_MANUAL',description='WhatsApp Web não permite envio agendado automático.',created_at=now))
   processed+=1; continue
  try:
   try: params=json.loads(fila.template_parameters or '[]')
   except Exception: params=[]
   result=CommunicationService().send_whatsapp(phone=fila.recipient,message=fila.body,integration=integration,template_name=fila.template_name,template_parameters=params)
   fila.provider=result.provider; fila.status=result.status; fila.external_id=result.external_id; fila.attempts=(fila.attempts or 0)+1; fila.sent_at=now; fila.updated_at=now
   db.session.add(MessageEvent(tenant_id=fila.tenant_id,message_id=fila.id,event=result.status,description='Mensagem agendada enviada automaticamente.',created_at=now))
  except CommunicationError as exc:
   fila.status='FALHA'; fila.error_message=str(exc); fila.attempts=(fila.attempts or 0)+1; fila.updated_at=now
   db.session.add(MessageEvent(tenant_id=fila.tenant_id,message_id=fila.id,event='FALHA',description=str(exc),created_at=now))
  processed+=1
 db.session.commit()
 return processed

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

def recalcular_alertas(tenant_id):
 try:
  return sync_operational_alerts(db.session,Alert,Maintenance,Vehicle,tenant_id,'/manutencoes','/veiculos')
 except Exception:
  db.session.rollback()
  app.logger.exception('Falha ao recalcular alertas do tenant %s',tenant_id)
  return []

def migrate_schema():
 additions={
  'tenant':[('conferir_km_motorista','BOOLEAN DEFAULT FALSE')],
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
  'maintenance':[('alerta_km_antes','INTEGER DEFAULT 500'),('alerta_dias_antes','INTEGER DEFAULT 7'),('status',"VARCHAR(20) DEFAULT 'Ativa'"),('oficina','VARCHAR(160)'),('proxima_hora','VARCHAR(5)'),('notificar_motorista','BOOLEAN DEFAULT FALSE'),('lembrete_um_dia','BOOLEAN DEFAULT TRUE'),('notificacao_agendamento_id','INTEGER'),('notificacao_lembrete_id','INTEGER'),('concluida_em','TIMESTAMP'),('concluida_por_id','INTEGER')],
  'alert':[('source_key','VARCHAR(120)'),('entidade','VARCHAR(40)'),('entidade_id','INTEGER'),('action_url','VARCHAR(255)'),('atualizado_em','TIMESTAMP'),('resolvido_em','TIMESTAMP')],
  'message_queue':[('template_parameters','TEXT')],
  'contract':[
   ('template_nome','VARCHAR(120)'),('template_versao','INTEGER DEFAULT 1'),('hora_inicio','VARCHAR(5)'),
   ('periodicidade','VARCHAR(30)'),('dia_vencimento','VARCHAR(30)'),('multa_atraso_percentual','NUMERIC(6,2)'),
   ('juros_mes_percentual','NUMERIC(6,2)'),('indice_correcao','VARCHAR(30)'),('prazo_bloqueio_horas','INTEGER'),
   ('multa_diaria','NUMERIC(12,2)'),('taxa_adm_multas_percentual','NUMERIC(6,2)'),('nacionalidade','VARCHAR(60)'),
   ('estado_civil','VARCHAR(60)'),('profissao','VARCHAR(100)'),('cidade_assinatura','VARCHAR(100)'),
   ('numero_contrato','VARCHAR(30)'),('versao','INTEGER DEFAULT 1'),('criado_por_id','INTEGER'),
   ('criado_em','TIMESTAMP'),('atualizado_em','TIMESTAMP'),('assinado_em','TIMESTAMP'),
   ('assinatura_id','VARCHAR(120)'),('documento_id','INTEGER'),('arquivo_pdf','VARCHAR(255)'),('hash_documento','VARCHAR(64)'),('arquivo_pdf_assinado','VARCHAR(255)'),('hash_documento_assinado','VARCHAR(64)'),('documento_assinado_id','INTEGER'),('codigo_publico','VARCHAR(24)'),('enviado_whatsapp_em','TIMESTAMP'),('visualizado_em','TIMESTAMP'),('gerado_em','TIMESTAMP'),('clicksign_envelope_id','VARCHAR(80)'),('clicksign_document_id','VARCHAR(80)'),('clicksign_signer_id','VARCHAR(80)'),('clicksign_status','VARCHAR(30)'),('clicksign_sent_at','TIMESTAMP'),
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
 recalcular_alertas(tid())
 vehicles=Vehicle.query.filter_by(tenant_id=tid()).all()
 system_alerts=Alert.query.filter(Alert.tenant_id==tid(),Alert.resolvido_em.is_(None)).order_by(Alert.nivel.desc(),Alert.criado_em.desc()).limit(8).all()
 status_counts={status:0 for status in ['Disponível','Reservado','Alugado','Devolução','Manutenção','Inativo']}
 for vehicle in vehicles:
  status_counts[vehicle.status or 'Disponível']=status_counts.get(vehicle.status or 'Disponível',0)+1
 cards={
  'veiculos':len(vehicles),'motoristas':Driver.query.filter_by(tenant_id=tid()).count(),
  'contratos':Contract.query.filter(Contract.tenant_id==tid(),Contract.status.in_(['Rascunho','Gerado','Enviado','Visualizado','Assinado','Ativo'])).count(),
  'alertas':Alert.query.filter(Alert.tenant_id==tid(),Alert.resolvido_em.is_(None)).count(),
  'disponiveis':status_counts.get('Disponível',0),'reservados':status_counts.get('Reservado',0),
  'alugados':status_counts.get('Alugado',0),'manutencao':status_counts.get('Manutenção',0),
 }
 return render_template('dashboard.html',cards=cards,veiculos=sorted(vehicles,key=lambda v:v.id,reverse=True)[:6],alertas=system_alerts,oil_status=oil_status)

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
 v=Vehicle.query.filter_by(id=id,tenant_id=tid()).first_or_404(); km=int(request.form['km']); v.km_atual=km; db.session.add(Odometer(tenant_id=tid(),vehicle_id=v.id,km=km,origem=request.form.get('origem','Manual'))); db.session.commit(); recalcular_alertas(tid()); flash('Quilometragem atualizada e alertas recalculados.','success'); return redirect(url_for('veiculos'))

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
 d=motorista_atual_veiculo(v)
 # Seleção manual permanece como fallback para veículos sem contrato vigente.
 if not d and request.form.get('driver_id'):
  d=Driver.query.filter_by(id=request.form.get('driver_id'),tenant_id=tid()).first()
 if not d:
  flash('Não encontrei motorista vinculado a contrato vigente deste veículo. Selecione um motorista manualmente.','warning')
  return redirect(url_for('veiculos'))
 telefone=normalize_phone(d.telefone)
 if not telefone:
  flash('Cadastre um telefone/WhatsApp válido para o motorista.','danger'); return redirect(url_for('veiculos'))
 req=active_request(v.id,d.id)
 if not req:
  req=MileageRequest(tenant_id=tid(),vehicle_id=v.id,driver_id=d.id,token=uuid.uuid4().hex+uuid.uuid4().hex,expires_at=datetime.utcnow()+timedelta(days=7),previous_km=v.km_atual)
  db.session.add(req); db.session.commit()
 link=url_for('registrar_quilometragem_publica',token=req.token,_external=True)
 mensagem=f'Olá, {d.nome}! Precisamos da quilometragem atual do veículo {v.placa}. Abra o link, tire uma foto do painel e informe o km: {link}'
 integration=Integration.query.filter_by(tenant_id=tid(),tipo='whatsapp').first()
 cfg=CommunicationService.parse_config(integration)
 template_name=(cfg.get('mileage_template_name') or '').strip() or None
 template_params=[d.nome,v.placa,link]
 fila=MessageQueue(
  tenant_id=tid(),channel='whatsapp',provider='whatsapp_web',recipient=telefone,
  recipient_name=d.nome,message_type='solicitacao_km',body=mensagem,template_name=template_name,template_parameters=json.dumps(template_params,ensure_ascii=False),
  related_entity='Veiculo',related_entity_id=v.id,status='PENDENTE',
  created_at=agora_sao_paulo_naive(),updated_at=agora_sao_paulo_naive(),
 )
 db.session.add(fila); db.session.flush()
 try:
  result=CommunicationService().send_whatsapp(phone=telefone,message=mensagem,integration=integration,template_name=template_name,template_language=cfg.get('template_language') or 'pt_BR',template_parameters=template_params)
  fila.provider=result.provider; fila.status=result.status; fila.external_id=result.external_id
  fila.attempts=(fila.attempts or 0)+1; fila.sent_at=agora_sao_paulo_naive() if result.status=='ENVIADA' else None
  db.session.add(MessageEvent(tenant_id=tid(),message_id=fila.id,event=result.status,description='Solicitação de quilometragem processada pelo provedor configurado.',created_at=agora_sao_paulo_naive()))
  db.session.commit()
  if result.redirect_url:
   return redirect(result.redirect_url)
  flash('Solicitação de quilometragem enviada automaticamente pela WhatsApp Business Platform.','success')
  return redirect(url_for('veiculos'))
 except CommunicationError as exc:
  fila.status='FALHA'; fila.error_message=str(exc); fila.attempts=(fila.attempts or 0)+1
  db.session.add(MessageEvent(tenant_id=tid(),message_id=fila.id,event='FALHA',description=str(exc),created_at=agora_sao_paulo_naive()))
  db.session.commit(); flash(str(exc),'danger')
  return redirect(url_for('veiculos'))

@app.route('/km/<token>',methods=['GET','POST'])
def registrar_quilometragem_publica(token):
 req=MileageRequest.query.options(joinedload(MileageRequest.vehicle),joinedload(MileageRequest.driver)).filter_by(token=token).first_or_404()
 if req.status in ('Concluído','Aguardando conferência'): return render_template('quilometragem_sucesso.html',req=req,ja_enviado=True)
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
   req.submitted_at=datetime.utcnow()
   if req.vehicle and req.vehicle.id:
    tenant=Tenant.query.get(req.tenant_id)
   else:
    tenant=None
   if tenant and tenant.conferir_km_motorista:
    req.status='Aguardando conferência'
   else:
    req.status='Concluído'
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
  recalcular_alertas(req.tenant_id)
  return redirect(url_for('registrar_quilometragem_publica',token=token))
 return render_template('quilometragem_publica.html',req=req,expirado=False)

@app.route('/configuracoes/quilometragem',methods=['GET','POST'])
@login_required
def configuracoes_quilometragem():
 tenant=Tenant.query.get_or_404(tid())
 if request.method=='POST':
  tenant.conferir_km_motorista=request.form.get('conferir_km_motorista')=='1'
  db.session.commit()
  flash('Preferência de conferência de quilometragem atualizada.','success')
  return redirect(url_for('configuracoes_quilometragem'))
 return render_template('configuracoes_quilometragem.html',tenant=tenant)

@app.route('/quilometragens/conferencia')
@login_required
def conferencia_quilometragens():
 items=MileageRequest.query.options(joinedload(MileageRequest.vehicle),joinedload(MileageRequest.driver)).filter_by(tenant_id=tid(),status='Aguardando conferência').order_by(MileageRequest.submitted_at.asc()).all()
 return render_template('conferencia_quilometragens.html',items=items)

@app.route('/quilometragens/<int:id>/conferir',methods=['POST'])
@login_required
def conferir_quilometragem(id):
 req=MileageRequest.query.options(joinedload(MileageRequest.vehicle)).filter_by(id=id,tenant_id=tid(),status='Aguardando conferência').first_or_404()
 acao=request.form.get('acao')
 if acao=='rejeitar':
  req.status='Rejeitado'
  req.notes=((req.notes or '')+'\nRejeitado pelo administrador: '+(request.form.get('motivo') or 'Solicitada nova foto.')).strip()
  db.session.commit()
  flash('Leitura rejeitada. Gere uma nova solicitação de KM para o motorista.','success')
  return redirect(url_for('conferencia_quilometragens'))
 try:
  km=int(request.form.get('km') or req.km or 0)
 except ValueError:
  flash('Informe uma quilometragem válida.','danger'); return redirect(url_for('conferencia_quilometragens'))
 if km < (req.previous_km or 0):
  flash(f'A KM confirmada não pode ser menor que a leitura anterior ({req.previous_km:,} km).','danger'); return redirect(url_for('conferencia_quilometragens'))
 req.km=km; req.status='Concluído'; req.vehicle.km_atual=km
 origem='Administrador confirmou KM do motorista' if km==request.form.get('km_original',type=int) else 'Administrador corrigiu KM do motorista'
 db.session.add(Odometer(tenant_id=tid(),vehicle_id=req.vehicle_id,km=km,origem=origem))
 db.session.commit(); recalcular_alertas(tid())
 flash('Quilometragem conferida e veículo atualizado.','success')
 return redirect(url_for('conferencia_quilometragens'))

@app.route('/ferramentas/ocr-painel', methods=['GET','POST'])
@login_required
def ocr_painel_teste():
 resultado=None
 veiculos=Vehicle.query.filter_by(tenant_id=tid()).order_by(Vehicle.placa).all()
 veiculo_id=request.form.get('vehicle_id',type=int) if request.method=='POST' else None
 veiculo=None
 if veiculo_id:
  veiculo=Vehicle.query.filter_by(id=veiculo_id,tenant_id=tid()).first()
 if request.method=='POST':
  foto=request.files.get('foto')
  if not foto or not foto.filename:
   flash('Selecione uma foto do painel.','danger')
  else:
   ext=Path(secure_filename(foto.filename)).suffix.lower()
   if ext not in ('.jpg','.jpeg','.png','.webp'):
    flash('Envie uma foto JPG, PNG ou WEBP.','danger')
   else:
    try:
     data=foto.read()
     if not data:
      raise ValueError('arquivo vazio')
     resultado=read_odometer(data, previous_km=(veiculo.km_atual if veiculo else None))
    except Exception:
     app.logger.exception('Falha no teste OCR do painel')
     flash('Não foi possível processar a imagem. Tente outra foto.','danger')
 return render_template('ocr_painel_teste.html',veiculos=veiculos,veiculo=veiculo,resultado=resultado)

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
 manutencoes_concluidas=Maintenance.query.filter_by(tenant_id=tid(),vehicle_id=v.id,status='Concluída').order_by(Maintenance.concluida_em.desc(),Maintenance.id.desc()).all()
 return render_template('veiculo_historico.html',v=v,eventos=eventos,manutencoes_concluidas=manutencoes_concluidas)

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
 signature_item=_integration('signature')
 signature_cfg=_integration_config(signature_item)
 signature_ready,signature_message=SignatureProviderService.readiness(SignatureProviderService.from_integration(signature_item))
 return render_template('contrato_detalhe.html',c=c,eventos=eventos,documento=documento,signature=c.signature,signature_cfg=signature_cfg,signature_ready=signature_ready,signature_message=signature_message)


@app.route('/integracoes/clicksign/testar',methods=['POST'])
@login_required
def testar_clicksign():
 item=_integration('signature')
 try:
  client=SignatureProviderService.clicksign_client(item)
  ok,message=client.test_connection()
  flash(message,'success' if ok else 'danger')
 except SignatureProviderError as exc:
  flash(str(exc),'danger')
 return redirect(url_for('integracoes'))

@app.route('/contratos/<int:id>/clicksign/enviar',methods=['POST'])
@login_required
def contrato_clicksign_enviar(id):
 c=Contract.query.options(joinedload(Contract.driver)).filter_by(id=id,tenant_id=tid()).first_or_404()
 if not c.arquivo_pdf:
  flash('Gere o PDF do contrato antes de enviá-lo à Clicksign.','danger')
  return redirect(url_for('contrato_detalhe',id=id))
 if c.clicksign_envelope_id:
  flash('Este contrato já possui um envelope Clicksign. Use Atualizar status.','info')
  return redirect(url_for('contrato_detalhe',id=id))
 signer_email=(request.form.get('signer_email') or c.driver.email or '').strip()
 try:
  pdf_bytes=storage.download(c.arquivo_pdf)
  integration=_integration('signature')
  client=SignatureProviderService.clicksign_client(integration)
  result=client.create_signature_flow(
   envelope_name=f'Frota Fácil - {c.numero_contrato}',
   filename=f'{c.numero_contrato}.pdf',pdf_bytes=pdf_bytes,
   signer_name=c.driver.nome,signer_email=signer_email,signer_cpf=c.driver.cpf,
  )
  c.clicksign_envelope_id=result.envelope_id
  c.clicksign_document_id=result.document_id
  c.clicksign_signer_id=result.signer_id
  c.clicksign_status=result.status
  c.clicksign_sent_at=agora_sao_paulo_naive()
  if not c.driver.email and signer_email:
   c.driver.email=signer_email
  registrar_evento_contrato(db.session,ContractEvent,tenant_id=tid(),contract_id=c.id,user_id=current_user.id,
   evento='CLICKSIGN_ENVIADO',descricao=f'Contrato enviado para assinatura pela Clicksign. Envelope {result.envelope_id}.',status_novo=c.status)
  db.session.commit()
  flash(f'Contrato enviado para a Clicksign ({result.status}). Verifique o e-mail do signatário.','success')
 except StorageNotFoundError:
  flash('O PDF oficial não foi encontrado no armazenamento.','danger')
 except SignatureProviderError as exc:
  db.session.rollback(); flash(str(exc),'danger')
 except Exception:
  db.session.rollback(); app.logger.exception('Falha ao enviar contrato à Clicksign'); flash('Falha inesperada ao enviar o contrato à Clicksign.','danger')
 return redirect(url_for('contrato_detalhe',id=id))

@app.route('/contratos/<int:id>/clicksign/status',methods=['POST'])
@login_required
def contrato_clicksign_status(id):
 c=Contract.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if not c.clicksign_envelope_id:
  flash('Este contrato ainda não possui envelope Clicksign.','danger')
  return redirect(url_for('contrato_detalhe',id=id))
 try:
  client=SignatureProviderService.clicksign_client(_integration('signature'))
  body=client.envelope_details(c.clicksign_envelope_id)
  attrs=((body.get('data') or {}).get('attributes') or {}) if isinstance(body,dict) else {}
  status=str(attrs.get('status') or c.clicksign_status or 'desconhecido')
  c.clicksign_status=status
  registrar_evento_contrato(db.session,ContractEvent,tenant_id=tid(),contract_id=c.id,user_id=current_user.id,
   evento='CLICKSIGN_STATUS',descricao=f'Status Clicksign consultado: {status}.',status_novo=c.status)
  # Quando o envelope fecha, consideramos a assinatura externa concluída.
  if status=='closed' and c.status not in ('Assinado','Ativo','Encerrado'):
   now=agora_sao_paulo_naive()
   states=ContractStateService(db.session,ContractEvent,VehicleEvent)
   states.transition(contract=c,new_status='Assinado',user_id=current_user.id,now=now)
   states.transition(contract=c,new_status='Ativo',user_id=current_user.id,now=now)
  db.session.commit(); flash(f'Status Clicksign: {status}.','success')
 except (SignatureProviderError,ContractStateError,VehicleStateError) as exc:
  db.session.rollback(); flash(str(exc),'danger')
 return redirect(url_for('contrato_detalhe',id=id))

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
 usar_assinado=bool(c.arquivo_pdf_assinado) and request.args.get('original')!='1'
 chave=c.arquivo_pdf_assinado if usar_assinado else c.arquivo_pdf
 nome=f'{c.numero_contrato}_ASSINADO.pdf' if usar_assinado else f'{c.numero_contrato}.pdf'
 try: conteudo=storage.download(chave)
 except StorageNotFoundError: abort(404)
 return send_file(BytesIO(conteudo),as_attachment=True,download_name=nome,mimetype='application/pdf')

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
 link=url_for('contrato_publico',codigo=codigo_publico,_external=True)
 mensagem=(f'Olá, {c.driver.nome}! Segue o contrato {c.numero_contrato} referente ao veículo '
           f'{c.vehicle.marca_modelo} - placa {c.vehicle.placa}. Clique no link para visualizar o documento oficial: {link}')
 c.enviado_whatsapp_em=agora_sao_paulo_naive()
 try:
  if c.status in ('Gerado','Rascunho'):
   ContractStateService(db.session,ContractEvent,VehicleEvent).transition(contract=c,new_status='Enviado',user_id=current_user.id,now=agora_sao_paulo_naive())
  registrar_evento_contrato(db.session,ContractEvent,tenant_id=tid(),contract_id=c.id,user_id=current_user.id,
   evento='WHATSAPP_PREPARADO',descricao=f'Mensagem do contrato {c.numero_contrato} preparada para o WhatsApp de {c.driver.nome}.',status_novo=c.status)
  db.session.commit()
 except (ContractStateError,VehicleStateError) as exc:
  db.session.rollback(); flash(str(exc),'danger'); return redirect(url_for('contrato_detalhe',id=id))
 integration=Integration.query.filter_by(tenant_id=tid(),tipo='whatsapp').first()
 fila=MessageQueue(
  tenant_id=tid(),channel='whatsapp',provider='whatsapp_web',recipient=telefone,
  recipient_name=c.driver.nome,message_type='contrato',body=mensagem,
  related_entity='Contrato',related_entity_id=c.id,status='PENDENTE',
  created_at=agora_sao_paulo_naive(),updated_at=agora_sao_paulo_naive(),
 )
 db.session.add(fila); db.session.flush()
 try:
  result=CommunicationService().send_whatsapp(phone=telefone,message=mensagem,integration=integration)
  fila.provider=result.provider; fila.status=result.status; fila.external_id=result.external_id
  fila.attempts=(fila.attempts or 0)+1; fila.sent_at=agora_sao_paulo_naive() if result.status=='ENVIADA' else None
  db.session.add(MessageEvent(tenant_id=tid(),message_id=fila.id,event=result.status,description='Mensagem de contrato processada pelo provedor configurado.',created_at=agora_sao_paulo_naive()))
  db.session.commit()
  if result.redirect_url:
   return redirect(result.redirect_url)
  flash('Contrato enviado automaticamente pela WhatsApp Business Platform.','success')
  return redirect(url_for('contrato_detalhe',id=id))
 except CommunicationError as exc:
  fila.status='FALHA'; fila.error_message=str(exc); fila.attempts=(fila.attempts or 0)+1
  db.session.add(MessageEvent(tenant_id=tid(),message_id=fila.id,event='FALHA',description=str(exc),created_at=agora_sao_paulo_naive()))
  db.session.commit(); flash(str(exc),'danger')
  return redirect(url_for('contrato_detalhe',id=id))

@app.route('/contrato-publico/<codigo>')
def contrato_publico(codigo):
 c=Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle)).filter_by(codigo_publico=codigo).first_or_404()
 if not c.arquivo_pdf:
  abort(404)
 if not c.visualizado_em:
  c.visualizado_em=agora_sao_paulo_naive()
  try:
   if c.status in ('Gerado','Enviado'):
    ContractStateService(db.session,ContractEvent,VehicleEvent).transition(contract=c,new_status='Visualizado',user_id=None,now=agora_sao_paulo_naive())
   registrar_evento_contrato(db.session,ContractEvent,tenant_id=c.tenant_id,contract_id=c.id,user_id=None,
    evento='CONTRATO_PUBLICO_ABERTO',descricao=f'Página pública do contrato {c.numero_contrato} visualizada.',status_novo=c.status)
   db.session.commit()
  except (ContractStateError,VehicleStateError):
   db.session.rollback()
 documento=Document.query.filter_by(id=c.documento_id,tenant_id=c.tenant_id).first() if c.documento_id else None
 return render_template('contrato_publico.html',c=c,documento=documento,signature=c.signature)

@app.route('/contrato-publico/<codigo>/assinar',methods=['POST'])
def assinar_contrato_publico(codigo):
 c=Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle)).filter_by(codigo_publico=codigo).first_or_404()
 if not c.arquivo_pdf or not c.hash_documento:
  flash('O documento oficial ainda não está disponível para assinatura.','danger')
  return redirect(url_for('contrato_publico',codigo=codigo))
 if c.signature or c.status in ('Assinado','Ativo','Encerrado'):
  flash('Este contrato já foi assinado.','success')
  return redirect(url_for('contrato_publico',codigo=codigo))
 assinatura_data=request.form.get('assinatura_data','')
 nome=(request.form.get('signatario_nome') or '').strip()
 cpf=(request.form.get('cpf_confirmado') or '').strip()
 aceite=request.form.get('aceite')=='1'
 try:
  service=SignatureService(storage=storage)
  png_bytes=service.validate_and_decode(assinatura_data)
  service.validate_identity(driver=c.driver,nome=nome,cpf=cpf,aceite=aceite)
  now=agora_sao_paulo_naive()
  key=f'{c.tenant_id}/documentos/assinaturas/{c.numero_contrato}_{uuid.uuid4().hex[:10]}.png'
  storage.upload(BytesIO(png_bytes),key,'image/png')
  assinatura=Signature(
   tenant_id=c.tenant_id,contract_id=c.id,driver_id=c.driver_id,status='Assinada',
   signatario_nome=nome,cpf_confirmado=cpf,arquivo_assinatura=key,
   hash_assinatura=hashlib.sha256(png_bytes).hexdigest(),hash_documento=c.hash_documento,
   ip=service.client_ip(request),user_agent=(request.headers.get('User-Agent') or '')[:1000],
   aceite_texto='Declaro que li integralmente e concordo com o contrato apresentado.',assinado_em=now,
  )
  db.session.add(assinatura)
  db.session.flush()
  c.assinatura_id=str(assinatura.id)

  # Gera uma segunda versão do documento contendo a assinatura visual.
  # O PDF original permanece preservado para auditoria.
  assinado_em_br=now.strftime('%d/%m/%Y %H:%M')
  pdf_assinado=gerar_pdf_contrato(
   c.numero_contrato,c.texto_final,codigo_publico=c.codigo_publico,
   url_validacao=url_for('validar_contrato_publico',codigo=c.codigo_publico,_external=True),
   assinatura_png=png_bytes,
   assinatura_info={'nome':nome,'cpf':cpf,'assinado_em':assinado_em_br,'codigo':c.codigo_publico,'hash_assinatura':hashlib.sha256(png_bytes).hexdigest()},
  )
  chave_pdf_assinado=f'{c.tenant_id}/documentos/contratos/{c.numero_contrato}_ASSINADO.pdf'
  storage.upload(BytesIO(pdf_assinado),chave_pdf_assinado,'application/pdf')
  hash_pdf_assinado=hashlib.sha256(pdf_assinado).hexdigest()
  doc_assinado=Document(
   tenant_id=c.tenant_id,tipo='Contrato Assinado',entidade='Contrato',entidade_id=c.id,
   identificador=f'{c.numero_contrato} - Assinado',numero_documento=c.numero_contrato,
   nome_original=f'{c.numero_contrato}_ASSINADO.pdf',arquivo=chave_pdf_assinado,hash_sha256=hash_pdf_assinado,
   status='Ativo',versao=(c.versao or 1),criado_em=now,
  )
  db.session.add(doc_assinado); db.session.flush()
  c.arquivo_pdf_assinado=chave_pdf_assinado
  c.hash_documento_assinado=hash_pdf_assinado
  c.documento_assinado_id=doc_assinado.id

  states=ContractStateService(db.session,ContractEvent,VehicleEvent)
  states.transition(contract=c,new_status='Assinado',user_id=None,now=now)
  states.transition(contract=c,new_status='Ativo',user_id=None,now=now)
  registrar_evento_contrato(db.session,ContractEvent,tenant_id=c.tenant_id,contract_id=c.id,user_id=None,
   evento='ASSINATURA_ELETRONICA',descricao=f'Contrato assinado eletronicamente por {nome}. IP registrado: {assinatura.ip or "não informado"}.',
   status_anterior='Visualizado',status_novo='Ativo').criado_em=now
  db.session.commit()
 except (SignatureValidationError,ContractStateError,VehicleStateError) as exc:
  db.session.rollback()
  try:
   if 'key' in locals(): storage.delete(key)
   if 'chave_pdf_assinado' in locals(): storage.delete(chave_pdf_assinado)
  except Exception: pass
  flash(str(exc),'danger')
  return redirect(url_for('contrato_publico',codigo=codigo))
 except Exception:
  db.session.rollback()
  try:
   if 'key' in locals(): storage.delete(key)
   if 'chave_pdf_assinado' in locals(): storage.delete(chave_pdf_assinado)
  except Exception: pass
  app.logger.exception('Falha ao assinar contrato público')
  flash('Não foi possível concluir a assinatura. Tente novamente.','danger')
  return redirect(url_for('contrato_publico',codigo=codigo))
 return redirect(url_for('contrato_publico',codigo=codigo,assinado='1'))

@app.route('/contrato-publico/<codigo>/pdf')
def contrato_publico_pdf(codigo):
 c=Contract.query.filter_by(codigo_publico=codigo).first_or_404()
 if not c.arquivo_pdf:
  abort(404)
 chave=c.arquivo_pdf_assinado or c.arquivo_pdf
 nome=f'{c.numero_contrato}_ASSINADO.pdf' if c.arquivo_pdf_assinado else f'{c.numero_contrato}.pdf'
 try:
  conteudo=storage.download(chave)
 except StorageNotFoundError:
  abort(404)
 download=request.args.get('download')=='1'
 disposition='attachment' if download else 'inline'
 response=send_file(BytesIO(conteudo),as_attachment=download,download_name=nome,mimetype='application/pdf',max_age=0)
 response.headers['Content-Disposition']=f'{disposition}; filename="{nome}"'
 response.headers['X-Content-Type-Options']='nosniff'
 response.headers['Cache-Control']='private, no-store, max-age=0'
 return response

@app.route('/validar/contrato/<codigo>')
def validar_contrato_publico(codigo):
 # Compatibilidade: links antigos enviados pelo WhatsApp apontavam diretamente
 # para esta rota. Sem o parâmetro ?verificar=1, eles agora abrem a página
 # pública completa do contrato em vez de mostrar apenas a autenticação.
 c=Contract.query.filter_by(codigo_publico=codigo).first_or_404()
 if request.args.get('verificar') != '1':
  return redirect(url_for('contrato_publico',codigo=c.codigo_publico))
 c=Contract.query.options(joinedload(Contract.driver),joinedload(Contract.vehicle)).filter_by(id=c.id).first_or_404()
 documento=Document.query.filter_by(id=c.documento_id,tenant_id=c.tenant_id).first() if c.documento_id else None
 return render_template('validar_contrato.html',c=c,documento=documento)

@app.route('/contrato/<codigo>')
def contrato_publico_alias(codigo):
 # Alias curto e estável para compartilhamento externo.
 return redirect(url_for('contrato_publico',codigo=codigo))

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
  custo_txt=(request.form.get('custo') or '').strip()
  try:
   custo=Decimal(custo_txt.replace('.','').replace(',','.')) if custo_txt else Decimal('0')
  except Exception:
   flash('Custo inválido. Use, por exemplo, 350,00.','danger'); return redirect(url_for('manutencoes'))
  situacao=(request.form.get('situacao') or 'Agendada').strip()
  ja_realizada=(situacao == 'Realizada')
  m=Maintenance(
   tenant_id=tid(),vehicle_id=request.form['vehicle_id'],tipo=request.form['tipo'],
   data=request.form.get('data'),km=request.form.get('km') or None,custo=custo,
   proxima_km=request.form.get('proxima_km') or None,proxima_data=request.form.get('proxima_data'),proxima_hora=(request.form.get('proxima_hora') or '').strip() or None,
   alerta_km_antes=request.form.get('alerta_km_antes') or 500,
   alerta_dias_antes=request.form.get('alerta_dias_antes') or 7,
   observacoes=request.form.get('observacoes'),oficina=(request.form.get('oficina') or '').strip() or None,
   notificar_motorista=(False if ja_realizada else bool(request.form.get('notificar_motorista'))),lembrete_um_dia=(False if ja_realizada else bool(request.form.get('lembrete_um_dia'))),
   status=('Concluída' if ja_realizada else 'Ativa'),
   concluida_em=(datetime.utcnow() if ja_realizada else None),
   concluida_por_id=(current_user.id if ja_realizada else None),
  )
  db.session.add(m); db.session.flush()
  redirect_whatsapp=None
  notification_warning=None
  if ja_realizada and (m.proxima_km or m.proxima_data):
   prox=Maintenance(tenant_id=tid(),vehicle_id=m.vehicle_id,tipo=m.tipo,status='Ativa',proxima_km=m.proxima_km,proxima_data=m.proxima_data,proxima_hora=m.proxima_hora,alerta_km_antes=m.alerta_km_antes or 500,alerta_dias_antes=m.alerta_dias_antes or 7,observacoes='Próximo ciclo criado a partir de manutenção histórica.',oficina=m.oficina,notificar_motorista=False,lembrete_um_dia=False)
   db.session.add(prox)
   m.proxima_km=None; m.proxima_data=None; m.proxima_hora=None
  if ja_realizada:
   v=Vehicle.query.filter_by(id=m.vehicle_id,tenant_id=tid()).first()
   descricao=f"{m.tipo or 'Manutenção'} cadastrada como já realizada"
   if m.data: descricao+=f" em {data_br(m.data)}"
   if m.km is not None: descricao+=f" com {int(m.km):,} km".replace(',','.')
   if m.custo: descricao+=f". Custo R$ {m.custo:.2f}".replace('.',',')
   if m.oficina: descricao+=f". Oficina: {m.oficina}"
   if v:
    db.session.add(VehicleEvent(tenant_id=tid(),vehicle_id=v.id,user_id=current_user.id,evento='Manutenção histórica',descricao=descricao,status_anterior=v.status,status_novo=v.status))
  if (not ja_realizada) and m.notificar_motorista:
   v=Vehicle.query.filter_by(id=m.vehicle_id,tenant_id=tid()).first()
   d=motorista_atual_veiculo(v) if v else None
   if not d:
    notification_warning='Manutenção salva, mas não há motorista vinculado a contrato vigente para receber o WhatsApp.'
   else:
    integration=Integration.query.filter_by(tenant_id=tid(),tipo='whatsapp').first()
    cfg=CommunicationService.parse_config(integration)
    template_name=(cfg.get('maintenance_template_name') or '').strip() or None
    params=[d.nome,v.marca_modelo or 'Veículo',v.placa,m.tipo or 'Manutenção',data_br(m.proxima_data) if m.proxima_data else 'a definir',m.proxima_hora or 'a definir']
    body=maintenance_message(driver_name=d.nome,vehicle=v,maintenance=m,reminder=False)
    fila,redirect_whatsapp,err=criar_mensagem_whatsapp(tenant_id=tid(),driver=d,body=body,message_type='manutencao_agendada',related_entity='Manutencao',related_entity_id=m.id,template_name=template_name,template_parameters=params)
    if fila: m.notificacao_agendamento_id=fila.id
    if err: notification_warning='Manutenção salva, mas o envio imediato falhou: '+err
    if m.lembrete_um_dia and m.proxima_data:
     reminder_at=reminder_datetime(m)
     if reminder_at and reminder_at>agora_sao_paulo_naive():
      reminder_template=(cfg.get('maintenance_reminder_template_name') or template_name or '').strip() or None
      reminder_body=maintenance_message(driver_name=d.nome,vehicle=v,maintenance=m,reminder=True)
      rfila,_,_=criar_mensagem_whatsapp(tenant_id=tid(),driver=d,body=reminder_body,message_type='lembrete_manutencao',related_entity='Manutencao',related_entity_id=m.id,scheduled_at=reminder_at,template_name=reminder_template,template_parameters=params)
      if rfila: m.notificacao_lembrete_id=rfila.id
  db.session.commit()
  recalcular_alertas(tid())
  flash(('Manutenção já realizada registrada no histórico do veículo.' if ja_realizada else 'Manutenção registrada e monitoramento de alertas ativado.'),'success')
  if notification_warning: flash(notification_warning,'warning')
  if redirect_whatsapp:
   return redirect(redirect_whatsapp)
  return redirect(url_for('manutencoes'))
 # Processa automaticamente a fila vencida quando o gestor acessa o módulo; em produção o mesmo serviço pode ser chamado por cron.
 try: processar_mensagens_agendadas(tid(),limit=50)
 except Exception: app.logger.exception('Falha ao processar lembretes agendados')
 recalcular_alertas(tid())
 items=Maintenance.query.filter_by(tenant_id=tid()).order_by(Maintenance.id.desc()).all()
 alerts=Alert.query.filter(Alert.tenant_id==tid(),Alert.resolvido_em.is_(None),Alert.entidade=='Manutenção').order_by(Alert.criado_em.desc()).all()
 hoje_sp=datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
 return render_template('manutencoes.html',items=items,veiculos=Vehicle.query.filter_by(tenant_id=tid()).all(),alertas=alerts,maintenance_indicator=maintenance_indicator,hoje_sp=hoje_sp)

@app.route('/manutencoes/<int:id>/concluir',methods=['POST'])
@login_required
def concluir_manutencao(id):
 m=Maintenance.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if (m.status or 'Ativa') == 'Concluída':
  flash('Esta manutenção já foi concluída.','info')
  return redirect(url_for('manutencoes') + f'#manutencao-{m.id}')

 v=Vehicle.query.filter_by(id=m.vehicle_id,tenant_id=tid()).first_or_404()
 data_realizada=(request.form.get('data_realizada') or datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()).strip()
 km_realizada=request.form.get('km_realizada') or v.km_atual or None
 custo_txt=(request.form.get('custo_realizado') or '').strip()
 try:
  custo_realizado=Decimal(custo_txt.replace('.','').replace(',','.')) if custo_txt else (m.custo or Decimal('0'))
 except Exception:
  flash('Custo inválido. Use, por exemplo, 350,00.','danger')
  return redirect(url_for('manutencoes') + f'#manutencao-{m.id}')

 oficina=(request.form.get('oficina') or '').strip()
 obs_conclusao=(request.form.get('observacoes_conclusao') or '').strip()
 m.data=data_realizada
 m.km=int(km_realizada) if km_realizada not in (None,'') else None
 m.custo=custo_realizado
 m.oficina=oficina or m.oficina
 if obs_conclusao:
  m.observacoes=((m.observacoes + '\n') if m.observacoes else '') + 'Conclusão: ' + obs_conclusao
 m.status='Concluída'
 m.concluida_em=datetime.utcnow()
 m.concluida_por_id=current_user.id

 # A previsão antiga pertence à manutenção concluída e não deve continuar gerando alerta.
 m.proxima_km=None
 m.proxima_data=None

 descricao=f"{m.tipo or 'Manutenção'} concluída em {data_realizada}"
 if m.km is not None:
  descricao+=f" com {m.km:,} km".replace(',','.')
 if custo_realizado:
  descricao+=f". Custo R$ {custo_realizado:.2f}".replace('.',',')
 if oficina:
  descricao+=f". Oficina: {oficina}"
 if obs_conclusao:
  descricao+=f". {obs_conclusao}"
 db.session.add(VehicleEvent(tenant_id=tid(),vehicle_id=v.id,user_id=current_user.id,evento='Manutenção concluída',descricao=descricao,status_anterior=v.status,status_novo=v.status))

 # Se o usuário informar uma nova previsão, cria um novo ciclo sem apagar o histórico.
 nova_km=request.form.get('nova_proxima_km') or None
 nova_data=(request.form.get('nova_proxima_data') or '').strip() or None
 if nova_km or nova_data:
  prox=Maintenance(
   tenant_id=tid(),vehicle_id=v.id,tipo=m.tipo,status='Ativa',
   proxima_km=int(nova_km) if nova_km else None,proxima_data=nova_data,proxima_hora=(request.form.get('nova_proxima_hora') or m.proxima_hora or '').strip() or None,
   alerta_km_antes=request.form.get('novo_alerta_km_antes') or m.alerta_km_antes or 500,
   alerta_dias_antes=request.form.get('novo_alerta_dias_antes') or m.alerta_dias_antes or 7,
   observacoes='Gerada automaticamente após conclusão da manutenção anterior.',
   notificar_motorista=m.notificar_motorista,lembrete_um_dia=m.lembrete_um_dia,
  )
  db.session.add(prox)

 db.session.commit()
 recalcular_alertas(tid())
 flash('Manutenção concluída e registrada no histórico do veículo.','success')
 return redirect(url_for('manutencoes') + f'#manutencao-{m.id}')

@app.route('/vistorias',methods=['GET','POST'])
@login_required
def vistorias():
 if request.method=='POST':
  v=Vehicle.query.filter_by(id=request.form.get('vehicle_id'),tenant_id=tid()).first_or_404()
  d=motorista_atual_veiculo(v)
  c=v.current_contract if v.current_contract and v.current_contract.tenant_id==tid() else None
  if not d:
   flash('O veículo precisa ter motorista vinculado a um contrato vigente para gerar a vistoria.','warning')
   return redirect(url_for('vistorias'))
  token=uuid.uuid4().hex+uuid.uuid4().hex[:8]
  expira_horas=int(request.form.get('expira_horas') or 48)
  item=Inspection(tenant_id=tid(),vehicle_id=v.id,driver_id=d.id,contract_id=(c.id if c else None),token=token,status='Pendente',expires_at=datetime.utcnow()+timedelta(hours=max(1,min(expira_horas,168))))
  db.session.add(item); db.session.commit()
  link=url_for('vistoria_publica',token=item.token,_external=True)
  flash('Solicitação de vistoria criada. Link: '+link,'success')
  return redirect(url_for('vistorias'))
 items=Inspection.query.filter_by(tenant_id=tid()).order_by(Inspection.id.desc()).all()
 veiculos=Vehicle.query.filter_by(tenant_id=tid()).order_by(Vehicle.placa).all()
 return render_template('vistorias.html',items=items,veiculos=veiculos)

@app.route('/vistorias/<int:id>/aprovar',methods=['POST'])
@login_required
def aprovar_vistoria(id):
 item=Inspection.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if not item.video_key:
  flash('A vistoria ainda não possui vídeo.','warning'); return redirect(url_for('vistorias'))
 item.status='Aprovada'
 tentativa=InspectionAttempt.query.filter_by(inspection_id=item.id,tenant_id=tid(),decision='Pendente').order_by(InspectionAttempt.id.desc()).first()
 if not tentativa and item.video_key:
  tentativa=InspectionAttempt(inspection_id=item.id,tenant_id=item.tenant_id,video_key=item.video_key,video_mime=item.video_mime,duration_seconds=item.duration_seconds,brightness_avg=item.brightness_avg,submitted_at=item.submitted_at or datetime.utcnow(),decision='Pendente')
  db.session.add(tentativa)
 if tentativa:
  tentativa.decision='Aprovada'; tentativa.decided_at=datetime.utcnow()
 db.session.commit()
 flash('Vistoria aprovada.','success'); return redirect(url_for('vistorias'))

@app.route('/vistorias/<int:id>/rejeitar',methods=['POST'])
@login_required
def rejeitar_vistoria(id):
 item=Inspection.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 item.status='Regravar'; item.notes=(request.form.get('motivo') or 'Nova gravação solicitada pelo administrador.').strip()
 tentativa=InspectionAttempt.query.filter_by(inspection_id=item.id,tenant_id=tid(),decision='Pendente').order_by(InspectionAttempt.id.desc()).first()
 if not tentativa and item.video_key:
  tentativa=InspectionAttempt(inspection_id=item.id,tenant_id=item.tenant_id,video_key=item.video_key,video_mime=item.video_mime,duration_seconds=item.duration_seconds,brightness_avg=item.brightness_avg,submitted_at=item.submitted_at or datetime.utcnow(),decision='Pendente')
  db.session.add(tentativa)
 if tentativa:
  tentativa.decision='Regravar'; tentativa.decision_notes=item.notes; tentativa.decided_at=datetime.utcnow()
 item.token=uuid.uuid4().hex+uuid.uuid4().hex[:8]
 item.expires_at=datetime.utcnow()+timedelta(hours=48)
 db.session.commit()
 flash('Vistoria rejeitada. Um novo link foi gerado para regravação.','warning'); return redirect(url_for('vistorias'))

@app.route('/vistorias/<int:id>/video')
@login_required
def vistoria_video(id):
 item=Inspection.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 if not item.video_key: abort(404)
 try: conteudo=storage.download(item.video_key)
 except StorageNotFoundError: abort(404)
 return send_file(BytesIO(conteudo),mimetype=item.video_mime or 'video/webm',download_name=f'vistoria-{item.id}.webm',conditional=True)

@app.route('/vistorias/<int:id>/tentativas/<int:attempt_id>/video')
@login_required
def vistoria_tentativa_video(id,attempt_id):
 item=Inspection.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 tentativa=InspectionAttempt.query.filter_by(id=attempt_id,inspection_id=item.id,tenant_id=tid()).first_or_404()
 try: conteudo=storage.download(tentativa.video_key)
 except StorageNotFoundError: abort(404)
 return send_file(BytesIO(conteudo),mimetype=tentativa.video_mime or 'video/webm',download_name=f'vistoria-{item.id}-tentativa-{tentativa.id}.webm',conditional=True)

@app.route('/vistoria/<token>')
def vistoria_publica(token):
 item=Inspection.query.filter_by(token=token).first_or_404()
 if item.expires_at and item.expires_at < datetime.utcnow():
  return render_template('vistoria_publica.html',item=item,expired=True),410
 if item.status in ('Aprovada','Recebida') and item.video_key:
  return render_template('vistoria_publica.html',item=item,done=True)
 return render_template('vistoria_publica.html',item=item)

@app.route('/vistoria/<token>/upload',methods=['POST'])
def vistoria_upload(token):
 item=Inspection.query.filter_by(token=token).first_or_404()
 if item.expires_at and item.expires_at < datetime.utcnow():
  return {'ok':False,'error':'Link expirado.'},410
 video=request.files.get('video')
 if not video:
  return {'ok':False,'error':'Vídeo não recebido.'},400
 mime=(video.mimetype or '').lower()
 if not (mime.startswith('video/webm') or mime.startswith('video/mp4') or mime.startswith('video/quicktime')):
  return {'ok':False,'error':'Formato de vídeo não suportado.'},400
 try: brilho=float(request.form.get('brightness_avg') or 0)
 except Exception: brilho=0
 try: brilho_min=float(request.form.get('brightness_min') or brilho)
 except Exception: brilho_min=brilho
 try: dark_ratio=float(request.form.get('dark_ratio') or 0)
 except Exception: dark_ratio=0
 try: sample_count=max(0,int(float(request.form.get('brightness_samples') or 0)))
 except Exception: sample_count=0
 try: duracao=max(0,int(float(request.form.get('duration_seconds') or 0)))
 except Exception: duracao=0
 if duracao < 15:
  return {'ok':False,'error':'A vistoria ficou muito curta. Grave o veículo seguindo todas as etapas.'},400
 # Avalia o vídeo ao longo de toda a gravação, e não apenas por uma amostra isolada.
 if sample_count < 5 or brilho < 45 or dark_ratio > 0.35:
  return {'ok':False,'error':'Iluminação insuficiente durante parte relevante do vídeo. Grave novamente em local bem iluminado.'},400
 ext='.mp4' if ('mp4' in mime or 'quicktime' in mime) else '.webm'
 chave=f"{item.tenant_id}/vistorias/{item.vehicle_id}/{datetime.utcnow().strftime('%Y/%m')}/{uuid.uuid4().hex}{ext}"
 try:
  storage.upload(video.stream,chave,mime)
 except Exception:
  app.logger.exception('Falha ao armazenar vídeo da vistoria %s',item.id)
  return {'ok':False,'error':'Não foi possível armazenar o vídeo. Tente novamente.'},503
 item.video_key=chave; item.video_mime=mime; item.duration_seconds=duracao; item.brightness_avg=Decimal(str(round(brilho,2))); item.brightness_status='Adequada'; item.submitted_at=datetime.utcnow(); item.status='Recebida'; item.notes=None
 tentativa=InspectionAttempt(inspection_id=item.id,tenant_id=item.tenant_id,video_key=chave,video_mime=mime,duration_seconds=duracao,brightness_avg=Decimal(str(round(brilho,2))),brightness_min=Decimal(str(round(brilho_min,2))),dark_ratio=Decimal(str(round(dark_ratio,4))),submitted_at=item.submitted_at,decision='Pendente')
 db.session.add(tentativa)
 db.session.add(VehicleEvent(tenant_id=item.tenant_id,vehicle_id=item.vehicle_id,contract_id=item.contract_id,driver_id=item.driver_id,evento='Vistoria em vídeo recebida',descricao=f'Vídeo gravado pelo link de vistoria #{item.id}; duração {duracao}s; luminosidade média {brilho:.1f}; trechos escuros {dark_ratio*100:.0f}%. Aguardando aprovação.'))
 db.session.commit()
 return {'ok':True,'message':'Vistoria enviada com sucesso.'}

@app.route('/alertas')
@login_required
def alertas():
 recalcular_alertas(tid())
 nivel=(request.args.get('nivel') or '').strip()
 q=Alert.query.filter(Alert.tenant_id==tid(),Alert.resolvido_em.is_(None))
 if nivel in ('danger','warning','info'):
  q=q.filter(Alert.nivel==nivel)
 items=q.order_by(Alert.criado_em.desc()).all()
 return render_template('alertas.html',items=items,nivel=nivel)

@app.route('/alertas/<int:id>/abrir')
@login_required
def alerta_abrir(id):
 a=Alert.query.filter_by(id=id,tenant_id=tid()).first_or_404()

 # O destino é resolvido pela entidade do alerta, evitando links genéricos.
 if a.entidade == 'Manutenção' and a.entidade_id:
  m=Maintenance.query.filter_by(id=a.entidade_id,tenant_id=tid()).first()
  if m:
   return redirect(url_for('manutencoes') + f'#manutencao-{m.id}')

 if a.entidade == 'Veículo' and a.entidade_id:
  v=Vehicle.query.filter_by(id=a.entidade_id,tenant_id=tid()).first()
  if v:
   return redirect(url_for('editar_veiculo',id=v.id) + '#troca-oleo')

 if a.entidade == 'Contrato' and a.entidade_id:
  c=Contract.query.filter_by(id=a.entidade_id,tenant_id=tid()).first()
  if c:
   return redirect(url_for('contrato_detalhe',id=c.id))

 # Fallback para alertas antigos ou integrações futuras.
 if a.action_url:
  return redirect(a.action_url)
 return redirect(url_for('alertas'))

@app.route('/alertas/<int:id>/whatsapp-motorista',methods=['POST'])
@login_required
def alerta_whatsapp_motorista(id):
 a=Alert.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 v=None; m=None
 if a.entidade=='Manutenção':
  m=Maintenance.query.filter_by(id=a.entidade_id,tenant_id=tid()).first()
  v=m.vehicle if m else None
 elif a.entidade=='Veículo':
  v=Vehicle.query.filter_by(id=a.entidade_id,tenant_id=tid()).first()
 if not v:
  flash('Este alerta não possui veículo associado.','warning'); return redirect(url_for('alertas'))
 d=motorista_atual_veiculo(v)
 if not d:
  flash('O veículo não possui motorista vinculado a contrato vigente.','warning'); return redirect(url_for('alertas'))
 if m:
  body=maintenance_message(driver_name=d.nome,vehicle=v,maintenance=m,reminder=False)
  msg_type='alerta_manutencao'
 else:
  body=f'Olá, {d.nome}! A locadora identificou um alerta no veículo {v.marca_modelo or "Veículo"} — {v.placa}: {a.titulo}. {a.mensagem}'
  msg_type='alerta_veiculo'
 integration=Integration.query.filter_by(tenant_id=tid(),tipo='whatsapp').first()
 cfg=CommunicationService.parse_config(integration)
 template_name=(cfg.get('maintenance_template_name') or '').strip() or None
 params=[d.nome,v.marca_modelo or 'Veículo',v.placa,a.titulo,a.mensagem]
 fila,redirect_url,err=criar_mensagem_whatsapp(tenant_id=tid(),driver=d,body=body,message_type=msg_type,related_entity=a.entidade or 'Alerta',related_entity_id=a.entidade_id or a.id,template_name=template_name,template_parameters=params)
 db.session.commit()
 if err: flash('Não foi possível enviar o alerta: '+err,'danger')
 elif redirect_url: return redirect(redirect_url)
 else: flash('Alerta enviado ao motorista pelo WhatsApp Business.','success')
 return redirect(url_for('alertas'))

@app.route('/alertas/<int:id>/lido',methods=['POST'])
@login_required
def alerta_lido(id):
 a=Alert.query.filter_by(id=id,tenant_id=tid()).first_or_404()
 a.lido=True; db.session.commit()
 return redirect(request.referrer or url_for('alertas'))

@app.route('/alertas/atualizar',methods=['POST'])
@login_required
def atualizar_alertas():
 recalcular_alertas(tid())
 flash('Alertas atualizados.','success')
 return redirect(request.referrer or url_for('alertas'))

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

def _integration(tipo):
 return Integration.query.filter_by(tenant_id=tid(),tipo=tipo).first()

def _integration_config(item):
 if not item or not item.configuracao:
  return {}
 try:
  value=json.loads(item.configuracao)
  return value if isinstance(value,dict) else {}
 except Exception:
  return {}

def _whatsapp_verify_token_valido(token):
 token=(token or '').strip()
 if not token:
  return False
 global_token=(os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN') or '').strip()
 if global_token and token == global_token:
  return True
 # Compatibilidade com a configuração atual por locadora.
 for item in Integration.query.filter_by(tipo='whatsapp').all():
  cfg=_integration_config(item)
  if (cfg.get('verify_token') or '').strip() == token:
   return True
 return False


def _whatsapp_status_rank(status):
 return {'PENDENTE':0,'ACEITA_META':1,'ENVIADA':2,'ENTREGUE':3,'LIDA':4}.get((status or '').upper(),-1)


def _whatsapp_error_description(status_item):
 errors=status_item.get('errors') or []
 partes=[]
 for erro in errors:
  if not isinstance(erro,dict):
   continue
  code=erro.get('code')
  title=erro.get('title') or erro.get('message')
  detalhe=((erro.get('error_data') or {}).get('details') if isinstance(erro.get('error_data'),dict) else None)
  trecho=' / '.join(str(v) for v in (code,title,detalhe) if v not in (None,''))
  if trecho:
   partes.append(trecho)
 return ' | '.join(partes)


@app.route('/webhooks/whatsapp',methods=['GET','POST'])
def whatsapp_webhook():
 # GET: verificação do callback feita pela Meta.
 if request.method=='GET':
  mode=(request.args.get('hub.mode') or '').strip()
  token=(request.args.get('hub.verify_token') or '').strip()
  challenge=request.args.get('hub.challenge') or ''
  if mode == 'subscribe' and _whatsapp_verify_token_valido(token):
   return challenge,200,{'Content-Type':'text/plain; charset=utf-8'}
  abort(403)

 payload=request.get_json(silent=True) or {}
 try:
  for entry in payload.get('entry') or []:
   for change in entry.get('changes') or []:
    value=change.get('value') or {}
    metadata=value.get('metadata') or {}
    phone_number_id=str(metadata.get('phone_number_id') or '')
    for st in value.get('statuses') or []:
     external_id=str(st.get('id') or '')
     meta_status=(st.get('status') or '').lower()
     recipient_id=str(st.get('recipient_id') or '')
     status_map={'sent':'ENVIADA','delivered':'ENTREGUE','read':'LIDA','failed':'FALHA'}
     novo=status_map.get(meta_status)
     if not external_id or not novo:
      continue
     fila=MessageQueue.query.filter_by(external_id=external_id).order_by(MessageQueue.id.desc()).first()
     if not fila:
      app.logger.warning('Webhook WhatsApp sem mensagem local correspondente: %s',external_id)
      continue

     erro=_whatsapp_error_description(st)
     meta_ts=str(st.get('timestamp') or '')
     descricao=(
      f'Status Meta: {meta_status} | destinatário: {recipient_id or fila.recipient} | '
      f'phone_number_id: {phone_number_id or "-"} | timestamp Meta: {meta_ts or "-"}'
     )
     if erro:
      descricao += f' | erro: {erro}'

     # Registra todos os eventos, mesmo quando chegam fora de ordem.
     db.session.add(MessageEvent(
      tenant_id=fila.tenant_id,message_id=fila.id,event=novo,
      description=descricao,created_at=agora_sao_paulo_naive()
     ))

     atual=(fila.status or '').upper()
     if novo == 'FALHA':
      # Não rebaixa uma mensagem que a Meta já confirmou como entregue/lida.
      if _whatsapp_status_rank(atual) < _whatsapp_status_rank('ENTREGUE'):
       fila.status='FALHA'
       fila.error_message=erro or 'A Meta informou falha na entrega.'
     elif _whatsapp_status_rank(novo) > _whatsapp_status_rank(atual):
      fila.status=novo
      if novo == 'ENVIADA' and not fila.sent_at:
       fila.sent_at=agora_sao_paulo_naive()
      if novo in ('ENTREGUE','LIDA'):
       fila.error_message=None
     fila.updated_at=agora_sao_paulo_naive()
  db.session.commit()
 except Exception:
  db.session.rollback()
  app.logger.exception('Falha ao processar webhook do WhatsApp')
  # Retorna 200 para evitar tempestade de retries por erro interno inesperado.
  return {'ok':False},200
 return {'ok':True},200


@app.route('/integracoes',methods=['GET','POST'])
@login_required
def integracoes():
 if request.method=='POST':
  section=request.form.get('section')
  if section=='whatsapp':
   item=_integration('whatsapp') or Integration(tenant_id=tid(),tipo='whatsapp')
   provider=request.form.get('provider','web')
   cfg={
    'provider':provider,
    'phone_number_id':request.form.get('phone_number_id','').strip(),
    'business_account_id':request.form.get('business_account_id','').strip(),
    'access_token':request.form.get('access_token','').strip(),
    'verify_token':request.form.get('verify_token','').strip(),
    'graph_version':request.form.get('graph_version','v23.0').strip() or 'v23.0',
    'test_template_name':request.form.get('test_template_name','').strip(),
    'contract_template_name':request.form.get('contract_template_name','').strip(),
    'mileage_template_name':request.form.get('mileage_template_name','').strip(),
    'maintenance_template_name':request.form.get('maintenance_template_name','').strip(),
    'maintenance_reminder_template_name':request.form.get('maintenance_reminder_template_name','').strip(),
    'template_language':request.form.get('template_language','pt_BR').strip() or 'pt_BR',
   }
   item.ativo=(provider=='business')
   item.configuracao=json.dumps(cfg,ensure_ascii=False)
   db.session.add(item); db.session.commit(); flash('Configuração do WhatsApp salva.','success')
  elif section=='signature':
   item=_integration('signature') or Integration(tenant_id=tid(),tipo='signature')
   provider=request.form.get('signature_provider','local')
   cfg={'provider':provider}
   if provider=='clicksign':
    cfg.update({'api_token':request.form.get('clicksign_api_token','').strip(),'workspace_key':request.form.get('clicksign_workspace_key','').strip(),'environment':request.form.get('clicksign_environment','sandbox')})
   elif provider=='docusign':
    cfg.update({'account_id':request.form.get('docusign_account_id','').strip(),'integration_key':request.form.get('docusign_integration_key','').strip(),'environment':request.form.get('docusign_environment','demo')})
   item.ativo=(provider!='local')
   item.configuracao=json.dumps(cfg,ensure_ascii=False)
   db.session.add(item); db.session.commit(); flash('Provedor de assinatura salvo.','success')
  return redirect(url_for('integracoes'))
 whatsapp_item=_integration('whatsapp'); signature_item=_integration('signature')
 whatsapp_cfg=_integration_config(whatsapp_item); signature_cfg=_integration_config(signature_item)
 signature_ready,signature_message=SignatureProviderService.readiness(SignatureProviderService.from_integration(signature_item))
 recentes=MessageQueue.query.filter_by(tenant_id=tid()).order_by(MessageQueue.id.desc()).limit(20).all()
 for mensagem_recente in recentes:
  ultimo_evento=MessageEvent.query.filter_by(tenant_id=tid(),message_id=mensagem_recente.id).order_by(MessageEvent.id.desc()).first()
  mensagem_recente.diagnostico=(ultimo_evento.description if ultimo_evento else None)
 return render_template('integracoes.html',whatsapp=whatsapp_item,whatsapp_cfg=whatsapp_cfg,signature=signature_item,signature_cfg=signature_cfg,signature_ready=signature_ready,signature_message=signature_message,recentes=recentes,whatsapp_webhook_url=url_for('whatsapp_webhook',_external=True))

@app.route('/automacoes/processar-mensagens',methods=['POST'])
@login_required
def processar_mensagens_manual():
 quantidade=processar_mensagens_agendadas(tid(),limit=200)
 flash(f'{quantidade} mensagem(ns) agendada(s) processada(s).','success')
 return redirect(url_for('integracoes'))

@app.route('/jobs/processar-mensagens',methods=['GET','POST'])
def processar_mensagens_job():
 token=(request.args.get('token') or request.headers.get('X-Automation-Token') or '').strip()
 expected=(os.getenv('AUTOMATION_JOB_TOKEN') or '').strip()
 if not expected or token != expected:
  abort(403)
 quantidade=processar_mensagens_agendadas(None,limit=500)
 return {'ok':True,'processadas':quantidade,'executado_em':agora_sao_paulo_naive().isoformat()}

@app.route('/integracoes/whatsapp/testar',methods=['POST'])
@login_required
def testar_whatsapp_business():
 item=_integration('whatsapp')
 cfg=_integration_config(item)
 telefone_informado=(request.form.get('telefone') or '').strip()
 telefone=normalize_phone(telefone_informado)
 if not telefone:
  flash('Informe um telefone para o teste.','danger'); return redirect(url_for('integracoes'))
 mensagem='Teste de integração enviado pelo Frota Fácil.'
 # Template dedicado ao teste. Mantém fallback para configurações já existentes.
 template_teste=(cfg.get('test_template_name') or cfg.get('mileage_template_name') or cfg.get('contract_template_name') or '').strip() or None
 idioma=(cfg.get('template_language') or 'pt_BR').strip() or 'pt_BR'
 fila=MessageQueue(tenant_id=tid(),channel='whatsapp',provider='whatsapp_business',recipient=telefone,recipient_name='Teste',message_type='teste',body=mensagem,template_name=template_teste,status='PENDENTE',created_at=agora_sao_paulo_naive(),updated_at=agora_sao_paulo_naive())
 db.session.add(fila); db.session.flush()
 try:
  result=CommunicationService().send_whatsapp(phone=telefone,message=mensagem,integration=item,template_name=template_teste,template_language=idioma)
  body=result.response_payload if isinstance(result.response_payload,dict) else {}
  contato=(body.get('contacts') or [{}])[0] if body.get('contacts') else {}
  mensagem_meta=(body.get('messages') or [{}])[0] if body.get('messages') else {}
  meta_input=str(contato.get('input') or '')
  meta_wa_id=str(contato.get('wa_id') or '')
  meta_message_id=str(mensagem_meta.get('id') or result.external_id or '')
  diagnostico=(
   f'Destino digitado: {telefone_informado or "-"} | '
   f'Destino normalizado/enviado: {telefone} | '
   f'Meta input: {meta_input or "não retornado"} | '
   f'Meta wa_id: {meta_wa_id or "não retornado"} | '
   f'Message ID: {meta_message_id or "não retornado"} | '
   f'Template: {template_teste or "texto livre"} | Idioma: {idioma}'
  )
  fila.provider=result.provider; fila.status=result.status; fila.external_id=result.external_id; fila.attempts=1; fila.sent_at=agora_sao_paulo_naive() if result.status=='ENVIADA' else None
  db.session.add(MessageEvent(tenant_id=tid(),message_id=fila.id,event=result.status,description=diagnostico,created_at=agora_sao_paulo_naive()))
  db.session.commit()
  flash(f'Teste aceito pela Meta para {telefone}. wa_id reconhecido: {meta_wa_id or "não retornado"}. Aguarde o webhook para confirmar entrega.','success')
 except CommunicationError as exc:
  fila.status='FALHA'; fila.error_message=str(exc); fila.attempts=1
  diagnostico=f'Destino digitado: {telefone_informado or "-"} | Destino normalizado/enviado: {telefone} | Template: {template_teste or "texto livre"} | Erro Meta: {exc}'
  db.session.add(MessageEvent(tenant_id=tid(),message_id=fila.id,event='FALHA',description=diagnostico,created_at=agora_sao_paulo_naive()))
  db.session.commit(); flash(str(exc),'danger')
 return redirect(url_for('integracoes'))

with app.app_context(): seed()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=True)
