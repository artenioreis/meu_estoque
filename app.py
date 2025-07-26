# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, Fornecedor, Produto, MovimentacaoEstoque, ContaPagar
from datetime import datetime, date, timedelta
from functools import wraps
from sqlalchemy import func, or_
import json
from dateutil.relativedelta import relativedelta

# --- CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'sua-chave-secreta-muito-segura'

db.init_app(app)

# Disponibiliza o módulo 'datetime' para os templates
@app.context_processor
def inject_datetime():
    return {'modules': {'datetime': datetime, 'date': date, 'timedelta': timedelta}}

# --- DECORADOR DE LOGIN ---
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
    
    produtos_perto_vencer = Produto.query.filter(
        Produto.data_vencimento != None,
        Produto.data_vencimento >= hoje,
        Produto.data_vencimento <= limite_vencimento
    ).order_by(Produto.data_vencimento.asc()).all()

    return render_template('index.html', 
                           produtos_alertas=produtos_estoque_baixo, 
                           produtos_perto_vencer=produtos_perto_vencer,
                           contas_vencidas=contas_vencidas,
                           contas_vencendo_hoje=contas_vencendo_hoje,
                           contas_vencendo_amanha=contas_vencendo_amanha,
                           outras_contas_pendentes=outras_contas_pendentes)

# --- ROTAS DA API ---
@app.route('/api/dados_graficos')
@login_required
def dados_graficos():
    # Gráfico 1: Top 5 produtos com mais estoque
    produtos_top_estoque = db.session.query(Produto.nome, Produto.quantidade_estoque).order_by(Produto.quantidade_estoque.desc()).limit(5).all()
    
    # Gráfico 2: Contagem de contas por status
    contas_por_status = db.session.query(ContaPagar.status, func.count(ContaPagar.id)).group_by(ContaPagar.status).all()

    # Gráfico 3: Top 5 produtos mais vendidos no PDV
    produtos_mais_vendidos = db.session.query(
        Produto.nome,
        func.sum(MovimentacaoEstoque.quantidade).label('total_vendido')
    ).join(Produto).filter(
        MovimentacaoEstoque.tipo == 'saida',
        MovimentacaoEstoque.observacao == 'Venda PDV'
    ).group_by(Produto.nome).order_by(func.sum(MovimentacaoEstoque.quantidade).desc()).limit(5).all()

    dados = {
        'estoque': {
            'labels': [p.nome for p in produtos_top_estoque],
            'data': [p.quantidade_estoque for p in produtos_top_estoque]
        },
        'contas': {
            'labels': [s[0].capitalize() for s in contas_por_status],
            'data': [s[1] for s in contas_por_status]
        },
        'mais_vendidos': {
            'labels': [p.nome for p in produtos_mais_vendidos],
            'data': [p.total_vendido for p in produtos_mais_vendidos]
        }
    }
    return jsonify(dados)

@app.route('/api/buscar_produto')
@login_required
def buscar_produto():
    query = request.args.get('q', '')
    produtos = Produto.query.filter(
        or_(
            Produto.nome.ilike(f'%{query}%'),
            Produto.codigo.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    resultado = [{'id': p.id, 'nome': p.nome, 'preco_venda': p.preco_venda} for p in produtos]
    return jsonify(resultado)

# --- ROTAS DE FORNECEDORES, PRODUTOS, CONTAS ---
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
        data_fabricacao_str = request.form.get('data_fabricacao')
        data_vencimento_str = request.form.get('data_vencimento')
        data_fabricacao = datetime.strptime(data_fabricacao_str, '%Y-%m-%d').date() if data_fabricacao_str else None
        data_vencimento = datetime.strptime(data_vencimento_str, '%Y-%m-%d').date() if data_vencimento_str else None
        novo_produto = Produto(
            codigo=request.form['codigo'], nome=request.form['nome'], categoria=request.form.get('categoria'),
            preco_custo=float(request.form['preco_custo']), preco_venda=float(request.form['preco_venda']),
            quantidade_estoque=int(request.form['quantidade_estoque']), estoque_minimo=int(request.form['estoque_minimo']),
            fornecedor_id=request.form['fornecedor_id'], data_fabricacao=data_fabricacao, data_vencimento=data_vencimento
        )
        db.session.add(novo_produto)
        db.session.commit()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
    fornecedores = Fornecedor.query.all()
    return render_template('adicionar_produto.html', fornecedores=fornecedores)

@app.route('/produto/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_produto(id):
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        produto.codigo = request.form['codigo']
        produto.nome = request.form['nome']
        produto.categoria = request.form.get('categoria')
        produto.preco_custo = float(request.form['preco_custo'])
        produto.preco_venda = float(request.form['preco_venda'])
        produto.quantidade_estoque = int(request.form['quantidade_estoque'])
        produto.estoque_minimo = int(request.form['estoque_minimo'])
        produto.fornecedor_id = request.form['fornecedor_id']
        data_fabricacao_str = request.form.get('data_fabricacao')
        data_vencimento_str = request.form.get('data_vencimento')
        produto.data_fabricacao = datetime.strptime(data_fabricacao_str, '%Y-%m-%d').date() if data_fabricacao_str else None
        produto.data_vencimento = datetime.strptime(data_vencimento_str, '%Y-%m-%d').date() if data_vencimento_str else None
        db.session.commit()
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
    fornecedores = Fornecedor.query.all()
    return render_template('editar_produto.html', produto=produto, fornecedores=fornecedores)

@app.route('/produto/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'danger')
    return redirect(url_for('listar_produtos'))

@app.route('/pdv')
@login_required
def pdv():
    return render_template('pdv.html')

@app.route('/finalizar_venda', methods=['POST'])
@login_required
def finalizar_venda():
    venda_data_str = request.form.get('venda_data')
    if not venda_data_str:
        flash('Nenhum item na venda.', 'warning')
        return redirect(url_for('pdv'))
    itens_venda = json.loads(venda_data_str)
    total_venda = 0
    for item in itens_venda:
        produto = Produto.query.get(item['id'])
        if produto:
            produto.quantidade_estoque -= item['quantidade']
            movimento = MovimentacaoEstoque(produto_id=produto.id, tipo='saida', quantidade=item['quantidade'], observacao='Venda PDV')
            db.session.add(movimento)
            total_venda += item['quantidade'] * item['preco_venda']
    db.session.commit()
    return render_template('cupom.html', itens_venda=itens_venda, total_venda=total_venda, data_venda=datetime.now())

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
        if conta.status == 'pago':
            conta.data_pagamento = date.today()
        else:
            conta.data_pagamento = None
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

@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

# --- COMANDO PARA CRIAR O BANCO DE DADOS ---
with app.app_context():
    db.create_all()

# --- BLOCO PARA DESENVOLVIMENTO LOCAL ---
if __name__ == '__main__':
    app.run(debug=True)
