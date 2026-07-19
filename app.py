import os, uuid, re
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from services.document_reader import extract_text, parse_cnh, parse_crlv

BASE=Path(__file__).parent; UPLOAD=BASE/'uploads'; UPLOAD.mkdir(exist_ok=True)
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
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); nome=db.Column(db.String(150),nullable=False); cpf=db.Column(db.String(14)); rg=db.Column(db.String(30)); numero_cnh=db.Column(db.String(20)); categoria=db.Column(db.String(5)); data_nascimento=db.Column(db.String(10)); validade_cnh=db.Column(db.String(10)); telefone=db.Column(db.String(30)); email=db.Column(db.String(120)); endereco=db.Column(db.String(250)); status=db.Column(db.String(30),default='Ativo'); criado_em=db.Column(db.DateTime,default=datetime.utcnow)
class Investor(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); nome=db.Column(db.String(150),nullable=False); cpf_cnpj=db.Column(db.String(20)); telefone=db.Column(db.String(30)); email=db.Column(db.String(120)); regra_repasse=db.Column(db.String(30),default='Valor fixo'); observacoes=db.Column(db.Text)
class Vehicle(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); placa=db.Column(db.String(10),nullable=False); renavam=db.Column(db.String(20)); chassi=db.Column(db.String(30)); marca_modelo=db.Column(db.String(150)); ano_fabricacao=db.Column(db.String(4)); ano_modelo=db.Column(db.String(4)); cor=db.Column(db.String(30)); combustivel=db.Column(db.String(30)); km_atual=db.Column(db.Integer,default=0); status=db.Column(db.String(30),default='Disponível'); proprietario_legal=db.Column(db.String(150)); cpf_cnpj_proprietario=db.Column(db.String(20)); investor_id=db.Column(db.Integer,db.ForeignKey('investor.id')); valor_repasse=db.Column(db.Numeric(12,2),default=0); limite_km=db.Column(db.Integer); valor_km_excedente=db.Column(db.Numeric(10,2),default=0); rastreador_id=db.Column(db.String(80)); investor=db.relationship('Investor')
class Odometer(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id')); km=db.Column(db.Integer,nullable=False); origem=db.Column(db.String(40)); data=db.Column(db.DateTime,default=datetime.utcnow); vehicle=db.relationship('Vehicle')
class MileageRequest(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id'),nullable=False); driver_id=db.Column(db.Integer,db.ForeignKey('driver.id'),nullable=False); token=db.Column(db.String(64),unique=True,nullable=False,index=True); status=db.Column(db.String(30),default='Pendente'); expires_at=db.Column(db.DateTime); sent_at=db.Column(db.DateTime,default=datetime.utcnow); submitted_at=db.Column(db.DateTime); km=db.Column(db.Integer); previous_km=db.Column(db.Integer); photo=db.Column(db.String(255)); notes=db.Column(db.Text); vehicle=db.relationship('Vehicle'); driver=db.relationship('Driver')
class ContractTemplate(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); nome=db.Column(db.String(120)); tipo_veiculo=db.Column(db.String(30)); possui_limite_km=db.Column(db.Boolean,default=False); conteudo=db.Column(db.Text); ativo=db.Column(db.Boolean,default=True)
class Contract(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); driver_id=db.Column(db.Integer,db.ForeignKey('driver.id')); vehicle_id=db.Column(db.Integer,db.ForeignKey('vehicle.id')); template_id=db.Column(db.Integer,db.ForeignKey('contract_template.id')); data_inicio=db.Column(db.String(10)); data_fim=db.Column(db.String(10)); valor_locacao=db.Column(db.Numeric(12,2)); caucao=db.Column(db.Numeric(12,2)); franquia=db.Column(db.Numeric(12,2)); limite_km=db.Column(db.Integer); valor_km_excedente=db.Column(db.Numeric(10,2)); status=db.Column(db.String(30),default='Ativo'); texto_final=db.Column(db.Text); driver=db.relationship('Driver'); vehicle=db.relationship('Vehicle'); template=db.relationship('ContractTemplate')
class Document(db.Model):
 id=db.Column(db.Integer,primary_key=True); tenant_id=db.Column(db.Integer,index=True,nullable=False); tipo=db.Column(db.String(40)); entidade=db.Column(db.String(30)); entidade_id=db.Column(db.Integer); nome_original=db.Column(db.String(255)); arquivo=db.Column(db.String(255)); versao=db.Column(db.Integer,default=1); criado_em=db.Column(db.DateTime,default=datetime.utcnow)
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

def normalize_phone(value):
 digits=re.sub(r'\D','',value or '')
 if not digits: return ''
 if digits.startswith('00'): digits=digits[2:]
 if len(digits) in (10,11): digits='55'+digits
 return digits

def active_request(vehicle_id, driver_id):
 return MileageRequest.query.filter_by(tenant_id=tid(),vehicle_id=vehicle_id,driver_id=driver_id,status='Pendente').filter(MileageRequest.expires_at>datetime.utcnow()).order_by(MileageRequest.id.desc()).first()

def seed():
 db.create_all()
 if not Tenant.query.first():
  t=Tenant(nome='Locadora Demonstração'); db.session.add(t); db.session.flush()
  u=User(tenant_id=t.id,nome='Administrador',email='admin@frotafacil.local',senha=generate_password_hash('admin123')); db.session.add(u)
  base='''CONTRATO DE LOCAÇÃO\nLOCATÁRIO: {{motorista_nome}}, CPF {{motorista_cpf}}, CNH {{motorista_cnh}}.\nVEÍCULO: {{veiculo_modelo}}, placa {{veiculo_placa}}, Renavam {{veiculo_renavam}}.\nVALOR: R$ {{valor_locacao}}. CAUÇÃO: R$ {{caucao}}.\nINÍCIO: {{data_inicio}}. TÉRMINO: {{data_fim}}.\nLIMITE DE KM: {{limite_km}}. EXCEDENTE: R$ {{valor_km_excedente}}/km.'''
  db.session.add_all([ContractTemplate(tenant_id=t.id,nome='Combustão com limite',tipo_veiculo='Combustão',possui_limite_km=True,conteudo=base),ContractTemplate(tenant_id=t.id,nome='Elétrico com limite',tipo_veiculo='Elétrico',possui_limite_km=True,conteudo=base+'\nO LOCATÁRIO se responsabiliza pela recarga e uso de equipamentos homologados.')]); db.session.commit()

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
   db.session.add(ContractTemplate(tenant_id=t.id,nome='Modelo básico',tipo_veiculo='Todos',possui_limite_km=False,conteudo=base))
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
 cards={'veiculos':Vehicle.query.filter_by(tenant_id=tid()).count(),'motoristas':Driver.query.filter_by(tenant_id=tid()).count(),'contratos':Contract.query.filter_by(tenant_id=tid(),status='Ativo').count(),'alertas':Alert.query.filter_by(tenant_id=tid(),lido=False).count()}
 return render_template('dashboard.html',cards=cards,veiculos=Vehicle.query.filter_by(tenant_id=tid()).order_by(Vehicle.id.desc()).limit(6),alertas=Alert.query.filter_by(tenant_id=tid(),lido=False).limit(5))

@app.route('/motoristas',methods=['GET','POST'])
@login_required
def motoristas():
 if request.method=='POST':
  d=Driver(tenant_id=tid(),**{k:request.form.get(k) for k in ['nome','cpf','rg','numero_cnh','categoria','data_nascimento','validade_cnh','telefone','email','endereco','status']}); db.session.add(d); db.session.commit(); flash('Motorista cadastrado.','success'); return redirect(url_for('motoristas'))
 return render_template('motoristas.html',items=Driver.query.filter_by(tenant_id=tid()).order_by(Driver.nome))
@app.route('/motoristas/importar',methods=['POST'])
@login_required
def importar_motorista():
 f=request.files.get('arquivo')
 if not f:
  flash('Selecione um arquivo.','danger')
  return redirect(url_for('motoristas'))

 # Libera qualquer conexão que tenha ficado ociosa enquanto o OCR processa.
 # O usuário e a locadora já foram carregados com joinedload no login loader.
 db.session.remove()
 try:
  texto=extract_text(f, document_type='cnh')
  dados=parse_cnh(texto)
  return render_template('confirmar_motorista.html',dados=dados)
 except Exception as exc:
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
  vals={k:request.form.get(k) for k in ['placa','renavam','chassi','marca_modelo','ano_fabricacao','ano_modelo','cor','combustivel','status','proprietario_legal','cpf_cnpj_proprietario','rastreador_id']}
  v=Vehicle(tenant_id=tid(),**vals,km_atual=int(request.form.get('km_atual') or 0),investor_id=request.form.get('investor_id') or None,valor_repasse=request.form.get('valor_repasse') or 0,limite_km=request.form.get('limite_km') or None,valor_km_excedente=request.form.get('valor_km_excedente') or 0); db.session.add(v); db.session.flush(); db.session.add(Odometer(tenant_id=tid(),vehicle_id=v.id,km=v.km_atual,origem='Cadastro')); db.session.commit(); flash('Veículo cadastrado.','success'); return redirect(url_for('veiculos'))
 return render_template('veiculos.html',items=Vehicle.query.filter_by(tenant_id=tid()).order_by(Vehicle.placa),investidores=Investor.query.filter_by(tenant_id=tid()).all(),motoristas=Driver.query.filter_by(tenant_id=tid(),status='Ativo').order_by(Driver.nome).all())
@app.route('/veiculos/importar',methods=['POST'])
@login_required
def importar_veiculo():
 f=request.files.get('arquivo');
 if not f: flash('Selecione um arquivo.','danger'); return redirect(url_for('veiculos'))
 dados=parse_crlv(extract_text(f)); return render_template('confirmar_veiculo.html',dados=dados,investidores=Investor.query.filter_by(tenant_id=tid()).all())
@app.route('/veiculos/<int:id>/km',methods=['POST'])
@login_required
def atualizar_km(id):
 v=Vehicle.query.filter_by(id=id,tenant_id=tid()).first_or_404(); km=int(request.form['km']); v.km_atual=km; db.session.add(Odometer(tenant_id=tid(),vehicle_id=v.id,km=km,origem=request.form.get('origem','Manual'))); db.session.commit(); flash('Quilometragem atualizada.','success'); return redirect(url_for('veiculos'))

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
  pasta=UPLOAD/str(req.tenant_id)/'odometros'; pasta.mkdir(parents=True,exist_ok=True)
  nome=f'{uuid.uuid4().hex}{ext}'; foto.save(pasta/nome)
  req.km=km; req.photo=nome; req.notes=request.form.get('observacoes'); req.status='Concluído'; req.submitted_at=datetime.utcnow()
  req.vehicle.km_atual=km
  db.session.add(Odometer(tenant_id=req.tenant_id,vehicle_id=req.vehicle_id,km=km,origem='Motorista via link'))
  db.session.commit()
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
 if not req.photo: abort(404)
 return send_from_directory(UPLOAD/str(tid())/'odometros',req.photo)

@app.route('/contratos',methods=['GET','POST'])
@login_required
def contratos():
 if request.method=='POST':
  d=Driver.query.filter_by(id=request.form['driver_id'],tenant_id=tid()).first_or_404(); v=Vehicle.query.filter_by(id=request.form['vehicle_id'],tenant_id=tid()).first_or_404(); t=ContractTemplate.query.filter_by(id=request.form['template_id'],tenant_id=tid()).first_or_404()
  repl={'motorista_nome':d.nome,'motorista_cpf':d.cpf or '','motorista_cnh':d.numero_cnh or '','veiculo_modelo':v.marca_modelo or '','veiculo_placa':v.placa,'veiculo_renavam':v.renavam or '','valor_locacao':request.form.get('valor_locacao',''),'caucao':request.form.get('caucao',''),'data_inicio':request.form.get('data_inicio',''),'data_fim':request.form.get('data_fim',''),'limite_km':request.form.get('limite_km','Sem limite'),'valor_km_excedente':request.form.get('valor_km_excedente','0')}
  texto=t.conteudo
  for k,val in repl.items(): texto=texto.replace('{{'+k+'}}',str(val))
  c=Contract(tenant_id=tid(),driver_id=d.id,vehicle_id=v.id,template_id=t.id,data_inicio=repl['data_inicio'],data_fim=repl['data_fim'],valor_locacao=request.form.get('valor_locacao') or 0,caucao=request.form.get('caucao') or 0,franquia=request.form.get('franquia') or 0,limite_km=request.form.get('limite_km') or None,valor_km_excedente=request.form.get('valor_km_excedente') or 0,texto_final=texto); db.session.add(c); v.status='Alugado'; db.session.commit(); flash('Contrato gerado.','success'); return redirect(url_for('contrato_detalhe',id=c.id))
 return render_template('contratos.html',items=Contract.query.filter_by(tenant_id=tid()).order_by(Contract.id.desc()),motoristas=Driver.query.filter_by(tenant_id=tid()).all(),veiculos=Vehicle.query.filter_by(tenant_id=tid()).all(),modelos=ContractTemplate.query.filter_by(tenant_id=tid(),ativo=True).all())
@app.route('/contratos/<int:id>')
@login_required
def contrato_detalhe(id): return render_template('contrato_detalhe.html',c=Contract.query.filter_by(id=id,tenant_id=tid()).first_or_404())

@app.route('/documentos',methods=['GET','POST'])
@login_required
def documentos():
 if request.method=='POST':
  f=request.files['arquivo']; nome=f'{uuid.uuid4().hex}_{secure_filename(f.filename)}'; pasta=UPLOAD/str(tid()); pasta.mkdir(exist_ok=True); f.save(pasta/nome)
  db.session.add(Document(tenant_id=tid(),tipo=request.form['tipo'],entidade=request.form['entidade'],entidade_id=request.form.get('entidade_id') or None,nome_original=f.filename,arquivo=nome)); db.session.commit(); flash('Documento armazenado.','success'); return redirect(url_for('documentos'))
 return render_template('documentos.html',items=Document.query.filter_by(tenant_id=tid()).order_by(Document.id.desc()),motoristas=Driver.query.filter_by(tenant_id=tid()).all(),veiculos=Vehicle.query.filter_by(tenant_id=tid()).all())
@app.route('/documentos/<int:id>/baixar')
@login_required
def baixar_documento(id):
 d=Document.query.filter_by(id=id,tenant_id=tid()).first_or_404(); return send_from_directory(UPLOAD/str(tid()),d.arquivo,as_attachment=True,download_name=d.nome_original)

@app.route('/manutencoes',methods=['GET','POST'])
@login_required
def manutencoes():
 if request.method=='POST':
  m=Maintenance(tenant_id=tid(),vehicle_id=request.form['vehicle_id'],tipo=request.form['tipo'],data=request.form.get('data'),km=request.form.get('km') or None,custo=request.form.get('custo') or 0,proxima_km=request.form.get('proxima_km') or None,proxima_data=request.form.get('proxima_data'),observacoes=request.form.get('observacoes')); db.session.add(m); db.session.commit(); flash('Manutenção registrada.','success'); return redirect(url_for('manutencoes'))
 return render_template('manutencoes.html',items=Maintenance.query.filter_by(tenant_id=tid()).order_by(Maintenance.id.desc()),veiculos=Vehicle.query.filter_by(tenant_id=tid()).all())
@app.route('/integracoes')
@login_required
def integracoes(): return render_template('integracoes.html')

with app.app_context(): seed()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=True)
