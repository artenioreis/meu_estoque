# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, Fornecedor, Produto, MovimentacaoEstoque, ContaPagar, Cliente, ContaReceber
from datetime import datetime, date, timedelta
from functools import wraps
from sqlalchemy import func, or_
import json
from dateutil.relativedelta import relativedelta
import xml.etree.ElementTree as ET # Biblioteca para processar XML

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
        if 'logged_in' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == '123456':
            session['logged_in'] = True
            session['username'] = request.form['username']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

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
        cliente = Cliente.query.get(cliente_id)
    if not venda_data_str:
        flash('Nenhum item na venda.', 'warning')
        return redirect(url_for('pdv'))
    itens_venda = json.loads(venda_data_str)
    total_venda = 0
    for item in itens_venda:
        produto = Produto.query.get(item['id'])
        if produto and produto.quantidade_estoque >= item['quantidade']:
            produto.quantidade_estoque -= item['quantidade']
            movimento = MovimentacaoEstoque(produto_id=produto.id, tipo='saida', quantidade=item['quantidade'], observacao='Venda PDV', cliente_id=cliente_id)
            db.session.add(movimento)
            total_venda += item['quantidade'] * item['preco_venda']
        else:
            flash(f'Estoque insuficiente para o produto {produto.nome}.', 'danger')
            return redirect(url_for('pdv'))
    if cliente_id:
        nova_conta_receber = ContaReceber(cliente_id=cliente_id, valor=total_venda, forma_pagamento=forma_pagamento)
        if forma_pagamento in ['Dinheiro', 'Pix', 'Cartão']:
            nova_conta_receber.status = 'Recebido'
            nova_conta_receber.data_recebimento = date.today()
        db.session.add(nova_conta_receber)
    db.session.commit()
    return render_template('cupom.html', itens_venda=itens_venda, total_venda=total_venda, data_venda=datetime.now(), cliente=cliente, forma_pagamento=forma_pagamento)

# --- ROTAS DE FORNECEDORES ---
@app.route('/fornecedores')
@login_required
def listar_fornecedores():
    fornecedores = Fornecedor.query.order_by(Fornecedor.nome.asc()).all()
    return render_template('fornecedores.html', fornecedores=fornecedores)

@app.route('/fornecedor/novo', methods=['GET', 'POST'])
@login_required
def adicionar_fornecedor():
    if request.method == 'POST':
        novo_fornecedor = Fornecedor(nome=request.form['nome'], telefone=request.form.get('telefone'), email=request.form.get('email'))
        db.session.add(novo_fornecedor)
        db.session.commit()
        flash('Fornecedor cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_fornecedores'))
    return render_template('adicionar_fornecedor.html')

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
    produto_para_editar = Produto.query.get_or_404(id)
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
    produto = Produto.query.get_or_404(id)
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
                xml_content = file.read().decode('utf-8')
                root = ET.fromstring(xml_content)
                ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
                produtos_atualizados = []
                produtos_nao_encontrados = []
                for det in root.findall('.//nfe:det', ns):
                    cProd_node = det.find('.//nfe:cProd', ns)
                    qCom_node = det.find('.//nfe:qCom', ns)
                    if cProd_node is not None and qCom_node is not None:
                        cProd = cProd_node.text
                        qCom = int(float(qCom_node.text))
                        produto = Produto.query.filter_by(codigo=cProd).first()
                        if produto:
                            produto.quantidade_estoque += qCom
                            movimento = MovimentacaoEstoque(produto_id=produto.id, tipo='entrada', quantidade=qCom, observacao='Entrada por XML NF-e')
                            db.session.add(movimento)
                            produtos_atualizados.append(f"{produto.nome} (+{qCom})")
                        else:
                            produtos_nao_encontrados.append(cProd)
                db.session.commit()
                if produtos_atualizados:
                    flash(f'Entrada registada com sucesso para: {", ".join(produtos_atualizados)}', 'success')
                if produtos_nao_encontrados:
                    flash(f'Os seguintes códigos de produto não foram encontrados: {", ".join(produtos_nao_encontrados)}. Por favor, cadastre-os primeiro.', 'warning')
                return redirect(url_for('listar_produtos'))
            except ET.ParseError:
                flash('Erro ao processar o ficheiro XML. Verifique se o formato é válido.', 'danger')
            except Exception as e:
                flash(f'Ocorreu um erro inesperado: {e}', 'danger')
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
    cliente = Cliente.query.get_or_404(id)
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
    cliente = Cliente.query.get_or_404(id)
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
    conta = ContaPagar.query.get_or_404(id)
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
    conta = ContaPagar.query.get_or_404(id)
    db.session.delete(conta)
    db.session.commit()
    flash('Conta excluída com sucesso!', 'danger')
    return redirect(url_for('listar_contas'))

@app.route('/conta/pagar/<int:id>', methods=['POST'])
@login_required
def pagar_conta(id):
    conta = ContaPagar.query.get_or_404(id)
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
    conta = ContaReceber.query.get_or_404(id)
    conta.status = 'Recebido'
    conta.data_recebimento = date.today()
    db.session.commit()
    flash('Conta recebida com sucesso!', 'success')
    return redirect(url_for('listar_contas_receber'))

@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

# --- 3. COMANDOS FINAIS ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
