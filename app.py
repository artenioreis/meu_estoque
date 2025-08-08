# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from models import db, Fornecedor, Produto, MovimentacaoEstoque, ContaPagar, Cliente, ContaReceber, XmlImportado, User
from datetime import datetime, date, timedelta
from functools import wraps
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
import json
from dateutil.relativedelta import relativedelta
import xml.etree.ElementTree as ET
import os
import shutil

# --- 1. CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'sua-chave-secreta-muito-segura'
db.init_app(app)

# Disponibiliza módulos para os templates
@app.context_processor
def inject_datetime():
    return {'modules': {'datetime': datetime, 'date': date, 'timedelta': timedelta}}

# --- 2. DECORADORES E ROTAS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or 'user_id' not in session:
            session.clear()
            flash('A sua sessão é inválida. Por favor, faça login novamente.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['logged_in'] = True
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))

        if username == 'admin' and password == '17171321':
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(username='admin', email='admin@example.com')
                admin_user.set_password('17171321')
                db.session.add(admin_user)
                db.session.commit()
                flash('Utilizador "admin" padrão criado. Recomenda-se trocar a palavra-passe e o e-mail.', 'info')
            
            session['logged_in'] = True
            session['user_id'] = admin_user.id
            session['username'] = admin_user.username
            return redirect(url_for('index'))
        
        flash('Utilizador ou palavra-passe inválidos.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

# --- ROTAS DE RECUPERAÇÃO DE PALAVRA-PASSE ---
@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            flash('Utilizador encontrado. Por favor, defina a sua nova palavra-passe.', 'info')
            return redirect(url_for('resetar_senha', token=token))
        else:
            flash('O e-mail informado não foi encontrado no sistema.', 'danger')
            return redirect(url_for('recuperar_senha'))
    return render_template('recuperar_senha.html')

@app.route('/resetar_senha/<token>', methods=['GET', 'POST'])
def resetar_senha(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiration < datetime.utcnow():
        flash('O link de recuperação é inválido ou expirou.', 'danger')
        return redirect(url_for('recuperar_senha'))
    if request.method == 'POST':
        password = request.form['password']
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiration = None
        db.session.commit()
        flash('A sua palavra-passe foi redefinida com sucesso!', 'success')
        return redirect(url_for('login'))
    return render_template('resetar_senha.html', token=token)

# --- ROTAS DE GESTÃO DE UTILIZADORES ---
@app.route('/utilizadores')
@login_required
def listar_utilizadores():
    users = User.query.all()
    return render_template('utilizadores.html', users=users)

@app.route('/utilizador/novo', methods=['GET', 'POST'])
@login_required
def adicionar_utilizador():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter(or_(User.username == username, User.email == email)).first():
            flash('Nome de utilizador ou e-mail já existem.', 'danger')
            return redirect(url_for('adicionar_utilizador'))
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Utilizador criado com sucesso!', 'success')
        return redirect(url_for('listar_utilizadores'))
    return render_template('adicionar_utilizador.html')

@app.route('/utilizador/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_utilizador(id):
    user_to_edit = db.session.get(User, id)
    if not user_to_edit:
        flash('Utilizador não encontrado.', 'danger')
        return redirect(url_for('listar_utilizadores'))
    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        if User.query.filter(User.username == new_username, User.id != id).first():
            flash('Este nome de utilizador já está em uso.', 'danger')
            return render_template('editar_utilizador.html', user=user_to_edit)
        if User.query.filter(User.email == new_email, User.id != id).first():
            flash('Este e-mail já está em uso.', 'danger')
            return render_template('editar_utilizador.html', user=user_to_edit)
        user_to_edit.username = new_username
        user_to_edit.email = new_email
        db.session.commit()
        flash('Utilizador atualizado com sucesso!', 'success')
        return redirect(url_for('listar_utilizadores'))
    return render_template('editar_utilizador.html', user=user_to_edit)

@app.route('/utilizador/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_utilizador(id):
    user_to_delete = db.session.get(User, id)
    if not user_to_delete:
        flash('Utilizador não encontrado.', 'danger')
        return redirect(url_for('listar_utilizadores'))
    if user_to_delete.username == 'admin':
        flash('Não é permitido excluir o utilizador administrador principal.', 'danger')
        return redirect(url_for('listar_utilizadores'))
    if user_to_delete.id == session.get('user_id'):
        flash('Não pode excluir o seu próprio utilizador.', 'danger')
        return redirect(url_for('listar_utilizadores'))
    db.session.delete(user_to_delete)
    db.session.commit()
    flash('Utilizador excluído com sucesso!', 'success')
    return redirect(url_for('listar_utilizadores'))

@app.route('/utilizador/trocar_senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        user = db.session.get(User, session['user_id'])
        if not user.check_password(current_password):
            flash('A palavra-passe atual está incorreta.', 'danger')
            return redirect(url_for('trocar_senha'))
        user.set_password(new_password)
        db.session.commit()
        flash('Palavra-passe alterada com sucesso!', 'success')
        return redirect(url_for('index'))
    return render_template('trocar_senha.html')

# --- ROTA PRINCIPAL ---
@app.route('/')
@login_required
def index():
    hoje = date.today()
    amanha = hoje + timedelta(days=1)
    limite_vencimento = hoje + relativedelta(months=+2)
    contas_vencidas = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento < hoje).all()
    contas_vencendo_hoje = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento == hoje).all()
    contas_vencendo_amanha = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento == amanha).all()
    outras_contas_pendentes = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento > amanha).order_by(ContaPagar.data_vencimento.asc()).all()
    produtos_estoque_baixo = Produto.query.filter(Produto.quantidade_estoque <= Produto.estoque_minimo).all()
    produtos_perto_vencer = Produto.query.filter(Produto.data_vencimento != None, Produto.data_vencimento >= hoje, Produto.data_vencimento <= limite_vencimento).order_by(Produto.data_vencimento.asc()).all()
    contas_a_prazo_alertas = ContaReceber.query.filter(ContaReceber.status == 'Em Aberto').order_by(ContaReceber.data_venda.asc()).all()
    return render_template('index.html', produtos_alertas=produtos_estoque_baixo, produtos_perto_vencer=produtos_perto_vencer, contas_vencidas=contas_vencidas, contas_vencendo_hoje=contas_vencendo_hoje, contas_vencendo_amanha=contas_vencendo_amanha, outras_contas_pendentes=outras_contas_pendentes, contas_a_prazo_alertas=contas_a_prazo_alertas)

# --- ROTAS DA API ---
@app.route('/api/dados_graficos')
@login_required
def dados_graficos():
    hoje = date.today()
    sete_dias_atras = hoje - timedelta(days=6)
    produtos_top_estoque = db.session.query(Produto.nome, Produto.quantidade_estoque).order_by(Produto.quantidade_estoque.desc()).limit(5).all()
    contas_por_status = db.session.query(ContaPagar.status, func.count(ContaPagar.id)).group_by(ContaPagar.status).all()
    produtos_mais_vendidos = db.session.query(Produto.nome, func.sum(MovimentacaoEstoque.quantidade).label('total_vendido')).join(Produto).filter(MovimentacaoEstoque.tipo == 'saida', MovimentacaoEstoque.observacao == 'Venda PDV').group_by(Produto.nome).order_by(func.sum(MovimentacaoEstoque.quantidade).desc()).limit(5).all()
    vendas_ultimos_dias = db.session.query(func.strftime('%Y-%m-%d', MovimentacaoEstoque.data).label('dia'), func.sum(MovimentacaoEstoque.quantidade).label('total_quantidade')).filter(MovimentacaoEstoque.tipo == 'saida', MovimentacaoEstoque.observacao == 'Venda PDV', func.date(MovimentacaoEstoque.data) >= sete_dias_atras, func.date(MovimentacaoEstoque.data) <= hoje).group_by(func.strftime('%Y-%m-%d', MovimentacaoEstoque.data)).order_by(func.strftime('%Y-%m-%d', MovimentacaoEstoque.data)).all()
    dias_labels = [(sete_dias_atras + timedelta(days=i)).strftime("%d/%m") for i in range(7)]
    vendas_dict = {dia: int(total) for dia, total in vendas_ultimos_dias}
    vendas_data = [vendas_dict.get((sete_dias_atras + timedelta(days=i)).strftime("%Y-%m-%d"), 0) for i in range(7)]
    dados = {'estoque': {'labels': [p.nome for p in produtos_top_estoque], 'data': [p.quantidade_estoque for p in produtos_top_estoque]}, 'contas_pagar': {'labels': [s[0].capitalize() for s in contas_por_status], 'data': [s[1] for s in contas_por_status]}, 'mais_vendidos': {'labels': [p.nome for p in produtos_mais_vendidos], 'data': [int(p.total_vendido) for p in produtos_mais_vendidos]}, 'vendas_diarias': {'labels': dias_labels, 'data': vendas_data}}
    return jsonify(dados)

@app.route('/api/buscar_produto')
@login_required
def buscar_produto():
    query = request.args.get('q', '')
    produtos = Produto.query.filter(or_(Produto.nome.ilike(f'%{query}%'), Produto.codigo.ilike(f'%{query}%'))).limit(10).all()
    resultado = [{'id': p.id, 'nome': p.nome, 'preco_venda': p.preco_venda} for p in produtos]
    return jsonify(resultado)

@app.route('/api/buscar_cliente')
@login_required
def buscar_cliente():
    query = request.args.get('q', '')
    clientes = Cliente.query.filter(or_(Cliente.nome.ilike(f'%{query}%'), Cliente.telefone.ilike(f'%{query}%'))).limit(10).all()
    resultado = [{'id': c.id, 'nome': c.nome, 'telefone': c.telefone} for c in clientes]
    return jsonify(resultado)

# --- ROTAS DO PDV ---
@app.route('/pdv')
@login_required
def pdv():
    return render_template('pdv.html')

@app.route('/finalizar_venda', methods=['POST'])
@login_required
def finalizar_venda():
    venda_data_str = request.form.get('venda_data')
    cliente_id = request.form.get('cliente_id')
    forma_pagamento = request.form.get('forma_pagamento')
    
    cliente = None
    if cliente_id:
        cliente = db.session.get(Cliente, cliente_id)
    
    if not venda_data_str:
        flash('Nenhum item na venda.', 'warning')
        return redirect(url_for('pdv'))
    
    itens_venda = json.loads(venda_data_str)
    total_venda = sum(item['quantidade'] * item['preco_venda'] for item in itens_venda)

    for item in itens_venda:
        produto = db.session.get(Produto, item['id'])
        if not (produto and produto.quantidade_estoque >= item['quantidade']):
            flash(f'Estoque insuficiente para o produto {produto.nome if produto else "desconhecido"}.', 'danger')
            return redirect(url_for('pdv'))
        produto.quantidade_estoque -= item['quantidade']
        movimento = MovimentacaoEstoque(produto_id=produto.id, tipo='saida', quantidade=item['quantidade'], observacao='Venda PDV', cliente_id=cliente_id)
        db.session.add(movimento)

    if cliente_id:
        if forma_pagamento == 'A Prazo':
            num_parcelas = int(request.form.get('parcelas', 1))
            valor_parcela = round(total_venda / num_parcelas, 2)
            
            for i in range(1, num_parcelas + 1):
                data_vencimento = date.today() + relativedelta(months=+i)
                nova_conta = ContaReceber(
                    cliente_id=cliente_id,
                    valor=valor_parcela,
                    data_venda=date.today(),
                    data_recebimento=data_vencimento,
                    status='Em Aberto',
                    forma_pagamento=f'A Prazo ({i}/{num_parcelas})'
                )
                db.session.add(nova_conta)
        else:
            nova_conta = ContaReceber(
                cliente_id=cliente_id,
                valor=total_venda,
                forma_pagamento=forma_pagamento,
                status='Recebido',
                data_recebimento=date.today()
            )
            db.session.add(nova_conta)

    db.session.commit()
    return render_template('cupom.html', 
                           itens_venda=itens_venda, 
                           total_venda=total_venda, 
                           data_venda=datetime.now(), 
                           cliente=cliente, 
                           forma_pagamento=forma_pagamento,
                           num_parcelas=int(request.form.get('parcelas', 0)))

@app.route('/processar_devolucao', methods=['POST'])
@login_required
def processar_devolucao():
    devolucao_data_str = request.form.get('venda_data')
    cliente_id = request.form.get('cliente_id')
    
    cliente = None
    if cliente_id:
        cliente = db.session.get(Cliente, cliente_id)

    if not devolucao_data_str:
        flash('Nenhum item na devolução.', 'warning')
        return redirect(url_for('pdv'))

    itens_devolucao = json.loads(devolucao_data_str)
    total_devolvido = 0

    for item in itens_devolucao:
        produto = db.session.get(Produto, item['id'])
        if produto:
            produto.quantidade_estoque += item['quantidade']
            movimento = MovimentacaoEstoque(
                produto_id=produto.id, 
                tipo='entrada', 
                quantidade=item['quantidade'], 
                observacao='Devolução PDV',
                cliente_id=cliente_id
            )
            db.session.add(movimento)
            total_devolvido += item['quantidade'] * item['preco_venda']
        else:
            flash(f'Produto com ID {item["id"]} não encontrado.', 'danger')
            return redirect(url_for('pdv'))
            
    db.session.commit()
    
    return render_template('cupom_devolucao.html', 
                           itens_devolucao=itens_devolucao, 
                           total_devolvido=total_devolvido, 
                           data_devolucao=datetime.now(), 
                           cliente=cliente)

# --- ROTAS DE FORNECEDORES ---
@app.route('/fornecedores')
@login_required
def listar_fornecedores():
    search_term = request.args.get('q')
    query = Fornecedor.query
    if search_term:
        query = query.filter(or_(Fornecedor.nome.ilike(f'%{search_term}%'), Fornecedor.cnpj.ilike(f'%{search_term}%')))
    fornecedores = query.order_by(Fornecedor.nome.asc()).all()
    return render_template('fornecedores.html', fornecedores=fornecedores, search_term=search_term)

@app.route('/fornecedor/novo', methods=['GET', 'POST'])
@login_required
def adicionar_fornecedor():
    if request.method == 'POST':
        cnpj = request.form.get('cnpj')
        if cnpj and Fornecedor.query.filter_by(cnpj=cnpj).first():
            flash('Já existe um fornecedor com este CNPJ.', 'danger')
            return render_template('adicionar_fornecedor.html')
        novo_fornecedor = Fornecedor(nome=request.form['nome'], telefone=request.form.get('telefone'), email=request.form.get('email'), cnpj=cnpj)
        db.session.add(novo_fornecedor)
        db.session.commit()
        flash('Fornecedor cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_fornecedores'))
    return render_template('adicionar_fornecedor.html')

@app.route('/fornecedor/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_fornecedor(id):
    fornecedor = db.session.get(Fornecedor, id)
    if request.method == 'POST':
        cnpj = request.form.get('cnpj')
        if cnpj and Fornecedor.query.filter(Fornecedor.cnpj == cnpj, Fornecedor.id != id).first():
            flash('Já existe outro fornecedor com este CNPJ.', 'danger')
            return render_template('editar_fornecedor.html', fornecedor=fornecedor)
        fornecedor.nome = request.form['nome']
        fornecedor.telefone = request.form.get('telefone')
        fornecedor.email = request.form.get('email')
        fornecedor.cnpj = cnpj
        db.session.commit()
        flash('Fornecedor atualizado com sucesso!', 'success')
        return redirect(url_for('listar_fornecedores'))
    return render_template('editar_fornecedor.html', fornecedor=fornecedor)

@app.route('/fornecedor/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_fornecedor(id):
    fornecedor = db.session.get(Fornecedor, id)
    if fornecedor.produtos or fornecedor.contas:
        flash('Não é possível excluir este fornecedor pois ele possui produtos ou contas a pagar associados.', 'danger')
        return redirect(url_for('listar_fornecedores'))
    db.session.delete(fornecedor)
    db.session.commit()
    flash('Fornecedor excluído com sucesso!', 'danger')
    return redirect(url_for('listar_fornecedores'))

# --- ROTAS DE PRODUTOS ---
@app.route('/produtos')
@login_required
def listar_produtos():
    search_term = request.args.get('q')
    query = Produto.query
    if search_term:
        query = query.filter(or_(Produto.nome.ilike(f'%{search_term}%'), Produto.codigo.ilike(f'%{search_term}%')))
    produtos = query.order_by(Produto.nome.asc()).all()
    return render_template('produtos.html', produtos=produtos, search_term=search_term)

@app.route('/produto/novo', methods=['GET', 'POST'])
@login_required
def adicionar_produto():
    if request.method == 'POST':
        codigo = request.form['codigo']
        produto_existente = Produto.query.filter_by(codigo=codigo).first()
        if produto_existente:
            flash('Já existe um produto com este código. Por favor, utilize outro.', 'danger')
            return redirect(url_for('adicionar_produto'))
        data_fabricacao = datetime.strptime(request.form.get('data_fabricacao'), '%Y-%m-%d').date() if request.form.get('data_fabricacao') else None
        data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date() if request.form.get('data_vencimento') else None
        novo_produto = Produto(codigo=codigo, nome=request.form['nome'], categoria=request.form.get('categoria'), preco_custo=float(request.form['preco_custo']), preco_venda=float(request.form['preco_venda']), quantidade_estoque=int(request.form['quantidade_estoque']), estoque_minimo=int(request.form['estoque_minimo']), fornecedor_id=request.form['fornecedor_id'], data_fabricacao=data_fabricacao, data_vencimento=data_vencimento)
        db.session.add(novo_produto)
        db.session.commit()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
    fornecedores = Fornecedor.query.all()
    return render_template('adicionar_produto.html', fornecedores=fornecedores)

@app.route('/produto/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_produto(id):
    produto_para_editar = db.session.get(Produto, id)
    if request.method == 'POST':
        novo_codigo = request.form['codigo']
        produto_existente = Produto.query.filter(Produto.codigo == novo_codigo, Produto.id != id).first()
        if produto_existente:
            flash('Já existe outro produto com este código. Por favor, utilize outro.', 'danger')
            return redirect(url_for('editar_produto', id=id))
        produto_para_editar.codigo = novo_codigo
        produto_para_editar.nome = request.form['nome']
        produto_para_editar.categoria = request.form.get('categoria')
        produto_para_editar.preco_custo = float(request.form['preco_custo'])
        produto_para_editar.preco_venda = float(request.form['preco_venda'])
        produto_para_editar.quantidade_estoque = int(request.form['quantidade_estoque'])
        produto_para_editar.estoque_minimo = int(request.form['estoque_minimo'])
        produto_para_editar.fornecedor_id = request.form['fornecedor_id']
        produto_para_editar.data_fabricacao = datetime.strptime(request.form.get('data_fabricacao'), '%Y-%m-%d').date() if request.form.get('data_fabricacao') else None
        produto_para_editar.data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date() if request.form.get('data_vencimento') else None
        db.session.commit()
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
    fornecedores = Fornecedor.query.all()
    return render_template('editar_produto.html', produto=produto_para_editar, fornecedores=fornecedores)

@app.route('/produto/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_produto(id):
    produto = db.session.get(Produto, id)
    db.session.delete(produto)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'danger')
    return redirect(url_for('listar_produtos'))

@app.route('/produto/entrada_xml', methods=['GET', 'POST'])
@login_required
def entrada_xml():
    if request.method == 'POST':
        if 'xml_file' not in request.files:
            flash('Nenhum ficheiro selecionado', 'warning')
            return redirect(request.url)
        file = request.files['xml_file']
        if file.filename == '':
            flash('Nenhum ficheiro selecionado', 'warning')
            return redirect(request.url)
        if file and file.filename.endswith('.xml'):
            try:
                xml_content = file.read()
                root = ET.fromstring(xml_content)
                ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
                infNFe_node = root.find('.//nfe:infNFe', ns)
                if infNFe_node is None or 'Id' not in infNFe_node.attrib:
                    flash('XML inválido: não foi possível encontrar a chave da NF-e (infNFe).', 'danger')
                    return redirect(request.url)
                chave_nfe = infNFe_node.attrib['Id'].replace('NFe', '')
                if XmlImportado.query.filter_by(chave_nfe=chave_nfe).first():
                    flash(f'ERRO: Este XML (Chave: {chave_nfe[:10]}...) já foi importado anteriormente.', 'danger')
                    return redirect(url_for('listar_produtos'))
                cnpj_emitente_node = root.find('.//nfe:emit/nfe:CNPJ', ns)
                if cnpj_emitente_node is None:
                    flash('XML inválido: CNPJ do emitente não encontrado.', 'danger')
                    return redirect(request.url)
                cnpj_emitente = cnpj_emitente_node.text
                fornecedor = Fornecedor.query.filter_by(cnpj=cnpj_emitente).first()
                if not fornecedor:
                    nome_fornecedor = root.find('.//nfe:emit/nfe:xNome', ns).text
                    flash(f'Fornecedor "{nome_fornecedor}" (CNPJ: {cnpj_emitente}) não encontrado. Por favor, cadastre-o primeiro com o CNPJ correto e tente novamente.', 'danger')
                    return redirect(url_for('adicionar_fornecedor'))
                produtos_atualizados, produtos_nao_encontrados = [], []
                for det in root.findall('.//nfe:det', ns):
                    cProd = det.find('.//nfe:cProd', ns).text
                    qCom = int(float(det.find('.//nfe:qCom', ns).text))
                    produto = Produto.query.filter_by(codigo=cProd).first()
                    if produto:
                        produto.quantidade_estoque += qCom
                        movimento = MovimentacaoEstoque(produto_id=produto.id, tipo='entrada', quantidade=qCom, observacao=f'Entrada por XML ({file.filename})')
                        db.session.add(movimento)
                        produtos_atualizados.append(f"{produto.nome} (+{qCom})")
                    else:
                        produtos_nao_encontrados.append(cProd)
                valor_total_nfe_node = root.find('.//nfe:ICMSTot/nfe:vNF', ns)
                if valor_total_nfe_node is None:
                    flash('XML inválido: Valor total da nota (vNF) não encontrado.', 'danger')
                    return redirect(request.url)
                valor_total_nfe = float(valor_total_nfe_node.text)
                venc_node = root.find('.//nfe:dup/nfe:dVenc', ns)
                data_vencimento = datetime.strptime(venc_node.text, '%Y-%m-%d').date() if venc_node is not None else date.today() + timedelta(days=30)
                nova_conta = ContaPagar(fornecedor_id=fornecedor.id, descricao=f"Ref. NF-e chave: {chave_nfe[:10]}...", valor=valor_total_nfe, data_vencimento=data_vencimento)
                db.session.add(nova_conta)
                novo_registro_xml = XmlImportado(chave_nfe=chave_nfe, nome_arquivo=file.filename)
                db.session.add(novo_registro_xml)
                db.session.commit()
                if produtos_atualizados:
                    flash(f'Entrada registada com sucesso para: {", ".join(produtos_atualizados)}', 'success')
                if produtos_nao_encontrados:
                    flash(f'Os seguintes códigos de produto não foram encontrados: {", ".join(produtos_nao_encontrados)}.', 'warning')
                flash(f'Conta a pagar no valor de R$ {valor_total_nfe:.2f} para {fornecedor.nome} lançada com sucesso.', 'info')
                return redirect(url_for('listar_produtos'))
            except Exception as e:
                flash(f'Ocorreu um erro inesperado ao processar o XML: {e}', 'danger')
                db.session.rollback()
                return redirect(request.url)
    return render_template('entrada_xml.html')

# --- ROTAS DE CLIENTES ---
@app.route('/clientes')
@login_required
def listar_clientes():
    search_term = request.args.get('q')
    query = Cliente.query
    if search_term:
        query = query.filter(or_(Cliente.nome.ilike(f'%{search_term}%'), Cliente.telefone.ilike(f'%{search_term}%')))
    clientes = query.order_by(Cliente.nome.asc()).all()
    return render_template('clientes.html', clientes=clientes, search_term=search_term)

@app.route('/cliente/novo', methods=['GET', 'POST'])
@login_required
def adicionar_cliente():
    if request.method == 'POST':
        novo_cliente = Cliente(nome=request.form['nome'], telefone=request.form.get('telefone'), email=request.form.get('email'), endereco=request.form.get('endereco'))
        db.session.add(novo_cliente)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_clientes'))
    return render_template('adicionar_cliente.html')

@app.route('/cliente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente = db.session.get(Cliente, id)
    if request.method == 'POST':
        cliente.nome = request.form['nome']
        cliente.telefone = request.form.get('telefone')
        cliente.email = request.form.get('email')
        cliente.endereco = request.form.get('endereco')
        db.session.commit()
        flash('Cliente atualizado com sucesso!', 'success')
        return redirect(url_for('listar_clientes'))
    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/cliente/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_cliente(id):
    cliente = db.session.get(Cliente, id)
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente excluído com sucesso!', 'danger')
    return redirect(url_for('listar_clientes'))

# --- ROTAS DE CONTAS A PAGAR ---
@app.route('/contas')
@login_required
def listar_contas():
    search_term = request.args.get('q')
    query = ContaPagar.query
    if search_term:
        query = query.filter(ContaPagar.descricao.ilike(f'%{search_term}%'))
    contas = query.order_by(ContaPagar.data_vencimento.asc()).all()
    return render_template('contas_a_pagar.html', contas=contas, search_term=search_term)

@app.route('/conta/nova', methods=['GET', 'POST'])
@login_required
def adicionar_conta():
    if request.method == 'POST':
        nova_conta = ContaPagar(fornecedor_id=request.form['fornecedor_id'], descricao=request.form['descricao'], valor=float(request.form['valor']), data_vencimento=datetime.strptime(request.form['data_vencimento'], '%Y-%m-%d').date())
        db.session.add(nova_conta)
        db.session.commit()
        flash('Conta cadastrada com sucesso!', 'success')
        return redirect(url_for('listar_contas'))
    fornecedores = Fornecedor.query.all()
    return render_template('adicionar_conta.html', fornecedores=fornecedores)

@app.route('/conta/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_conta(id):
    conta = db.session.get(ContaPagar, id)
    if request.method == 'POST':
        conta.fornecedor_id = request.form['fornecedor_id']
        conta.descricao = request.form['descricao']
        conta.valor = float(request.form['valor'])
        conta.data_vencimento = datetime.strptime(request.form['data_vencimento'], '%Y-%m-%d').date()
        conta.status = request.form['status']
        conta.data_pagamento = date.today() if conta.status == 'pago' else None
        db.session.commit()
        flash('Conta atualizada com sucesso!', 'success')
        return redirect(url_for('listar_contas'))
    fornecedores = Fornecedor.query.all()
    return render_template('editar_conta.html', conta=conta, fornecedores=fornecedores)

@app.route('/conta/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_conta(id):
    conta = db.session.get(ContaPagar, id)
    db.session.delete(conta)
    db.session.commit()
    flash('Conta excluída com sucesso!', 'danger')
    return redirect(url_for('listar_contas'))

@app.route('/conta/pagar/<int:id>', methods=['POST'])
@login_required
def pagar_conta(id):
    conta = db.session.get(ContaPagar, id)
    conta.status = 'pago'
    conta.data_pagamento = datetime.utcnow().date()
    db.session.commit()
    flash('Conta marcada como paga.', 'success')
    return redirect(url_for('listar_contas'))

# --- ROTAS DE CONTAS A RECEBER ---
@app.route('/contas_receber')
@login_required
def listar_contas_receber():
    contas = ContaReceber.query.order_by(ContaReceber.data_venda.desc()).all()
    return render_template('contas_a_receber.html', contas=contas)

@app.route('/conta_receber/baixar/<int:id>', methods=['POST'])
@login_required
def baixar_conta_receber(id):
    conta = db.session.get(ContaReceber, id)
    conta.status = 'Recebido'
    conta.data_recebimento = date.today()
    db.session.commit()
    flash('Conta recebida com sucesso!', 'success')
    return redirect(url_for('listar_contas_receber'))

# --- ROTA DE RELATÓRIOS ---
@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

@app.route('/relatorio/estoque')
@login_required
def relatorio_estoque():
    produtos = Produto.query.order_by(Produto.nome.asc()).all()
    valor_total_estoque = sum(p.quantidade_estoque * p.preco_custo for p in produtos)
    return render_template('relatorio_estoque.html', produtos=produtos, valor_total_estoque=valor_total_estoque, data_emissao=datetime.now())

@app.route('/relatorio/estoque_baixo')
@login_required
def relatorio_estoque_baixo():
    produtos = Produto.query.filter(Produto.quantidade_estoque <= Produto.estoque_minimo).order_by(Produto.nome.asc()).all()
    return render_template('relatorio_estoque_baixo.html', produtos=produtos, data_emissao=datetime.now())

@app.route('/relatorio/movimentacoes', methods=['GET', 'POST'])
@login_required
def relatorio_movimentacoes():
    query = MovimentacaoEstoque.query.options(joinedload(MovimentacaoEstoque.produto), joinedload(MovimentacaoEstoque.cliente))
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    start_date, end_date = None, None
    if request.method == 'POST' and start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(func.date(MovimentacaoEstoque.data).between(start_date, end_date))
        except ValueError:
            flash('Formato de data inválido. Por favor, use AAAA-MM-DD.', 'danger')
    movimentacoes = query.order_by(MovimentacaoEstoque.data.desc()).all()
    return render_template('relatorio_movimentacoes.html', movimentacoes=movimentacoes, data_emissao=datetime.now(), start_date=start_date, end_date=end_date)

@app.route('/relatorio/contas_receber', methods=['GET', 'POST'])
@login_required
def relatorio_contas_receber():
    query = ContaReceber.query.options(joinedload(ContaReceber.cliente))
    status_filter = request.form.get('status_filter', 'todos')
    if status_filter != 'todos':
        query = query.filter(ContaReceber.status == status_filter)
    contas = query.order_by(ContaReceber.data_venda.desc()).all()
    valor_total = sum(c.valor for c in contas)
    return render_template('relatorio_contas_receber.html', contas=contas, valor_total=valor_total, status_filter=status_filter, data_emissao=datetime.now())

@app.route('/relatorio/contas_pagar', methods=['GET', 'POST'])
@login_required
def relatorio_contas_pagar():
    query = ContaPagar.query.options(joinedload(ContaPagar.fornecedor))
    status_filter = request.form.get('status_filter', 'pendente')
    if status_filter != 'todos':
        query = query.filter(ContaPagar.status == status_filter)
    contas = query.order_by(ContaPagar.data_vencimento.asc()).all()
    valor_total = sum(c.valor for c in contas)
    return render_template('relatorio_contas_pagar.html', contas=contas, valor_total=valor_total, status_filter=status_filter, data_emissao=datetime.now())

@app.route('/relatorio/despesas_fornecedor')
@login_required
def relatorio_despesas_fornecedor():
    despesas = db.session.query(Fornecedor.nome, func.sum(ContaPagar.valor).label('total_gasto')).join(ContaPagar).filter(ContaPagar.status == 'pago').group_by(Fornecedor.nome).order_by(func.sum(ContaPagar.valor).desc()).all()
    valor_total_geral = sum(d.total_gasto for d in despesas)
    return render_template('relatorio_despesas_fornecedor.html', despesas=despesas, valor_total_geral=valor_total_geral, data_emissao=datetime.now())

# --- ROTAS DE BACKUP ---
@app.route('/backup', methods=['GET', 'POST'])
@login_required
def backup():
    if request.method == 'POST':
        try:
            db_path = app.instance_path
            db_filename = 'database.db'
            source_file = os.path.join(db_path, db_filename)

            if not os.path.exists(source_file):
                flash('Ficheiro da base de dados não encontrado.', 'danger')
                return redirect(url_for('backup'))

            timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            backup_filename = f'backup_{timestamp}.db'
            
            return send_file(source_file, as_attachment=True, download_name=backup_filename)

        except Exception as e:
            flash(f'Ocorreu um erro ao gerar o backup: {e}', 'danger')
            return redirect(url_for('backup'))

    return render_template('backup.html')

# --- 3. COMANDOS FINAIS ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
