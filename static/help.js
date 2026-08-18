const FF_HELP=[
['/dashboard','Dashboard','Visão geral da operação. Acompanhe veículos, motoristas, contratos e alertas. Use os cartões e alertas para abrir rapidamente o item que exige atenção.'],
['/motoristas','Motoristas','O cadastro pode ser feito manualmente ou carregando a CNH em PDF. Ao importar a CNH, o Frota Fácil tenta ler e preencher automaticamente os dados encontrados; confira as informações antes de confirmar o cadastro. Depois, mantenha telefone e demais dados atualizados para contratos, solicitações de KM e comunicações pelo WhatsApp.'],
['/veiculos','Veículos','O cadastro pode ser feito manualmente ou carregando o CRLV-e em PDF. Ao importar o CRLV-e, o Frota Fácil tenta ler e preencher automaticamente os dados do veículo; confira as informações antes de salvar. Depois, configure KM, óleo, proprietário/investidor e acompanhe o status do veículo.'],
['/quilometragens/conferencia','Conferência de KM','Quando a conferência estiver ativada, compare a foto com a KM informada. Você pode confirmar, corrigir ou rejeitar e solicitar nova foto. Só após a aprovação a KM oficial é atualizada.'],
['/quilometragens','Quilometragens','Consulte solicitações e histórico de leituras. Gere o link pelo veículo; o motorista envia foto e KM. A aprovação depende da preferência definida pela locadora.'],
['/investidores','Investidores','Cadastre proprietários/investidores e a regra de repasse. Depois associe o investidor ao veículo para apoiar o controle financeiro.'],
['/modelos','Modelos de contrato','Crie modelos flexíveis com marcadores. Ao gerar um contrato, o Frota Fácil substitui os marcadores pelos dados do motorista, veículo e locação.'],
['/contratos','Contratos','Gere e acompanhe contratos. Selecione motorista, veículo e modelo; revise os dados, gere o documento, envie para assinatura e acompanhe o status.'],
['/documentos','Documentos','Central de documentos armazenados. Consulte arquivos de motoristas, veículos e contratos preservando o vínculo com a locadora.'],
['/vistorias','Vistorias','Gere um link exclusivo para o motorista gravar a vistoria na hora pelo celular. O Frota Fácil guia a gravação por voz e etapas, verifica iluminação mínima, armazena o vídeo no Cloudflare R2 e permite ao administrador aprovar ou pedir nova gravação. Não há envio de vídeo pronto pela galeria.'],
['/manutencoes','Manutenções','Registre manutenções realizadas ou futuras. Defina data/KM e alertas. Ao concluir, informe os dados realizados para entrar no histórico e encerrar os alertas relacionados.'],
['/alertas','Alertas','Centralize avisos de manutenção e operação. Marque como lido, abra o item relacionado e resolva a causa do alerta no módulo correspondente.'],
['/integracoes','Integrações','Configure serviços externos, como WhatsApp. Credenciais sensíveis não devem ser publicadas no GitHub. Use o teste da integração antes de ativar automações.'],
['/administracao/armazenamento','Armazenamento','Acompanhe o armazenamento de documentos e fotos da locadora e as configurações relacionadas ao serviço de arquivos.'],
['/configuracoes/quilometragem','Configuração de quilometragem','Escolha se a KM enviada pelo motorista é aceita automaticamente ou se deve passar por conferência do administrador. A preferência é independente para cada locadora.']
];
function ffHelpForPath(){const p=location.pathname;return FF_HELP.find(x=>p===x[0]||p.startsWith(x[0]+'/'))||['','Ajuda do Frota Fácil','Use esta tela para executar a função indicada no título. Consulte a Central de Ajuda para os tutoriais dos módulos principais.'];}
function openFFHelp(){const h=ffHelpForPath();document.getElementById('ffHelpTitle').textContent=h[1];document.getElementById('ffHelpText').textContent=h[2];document.getElementById('ffHelpModal').classList.add('open');}
function closeFFHelp(){document.getElementById('ffHelpModal').classList.remove('open');}
function openFFHelpCenter(){const box=document.getElementById('ffHelpCenterList');box.innerHTML=FF_HELP.map(x=>`<div class="help-item"><strong>${x[1]}</strong><p>${x[2]}</p></div>`).join('');document.getElementById('ffHelpCenter').classList.add('open');}
function closeFFHelpCenter(){document.getElementById('ffHelpCenter').classList.remove('open');}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeFFHelp();closeFFHelpCenter();}});
