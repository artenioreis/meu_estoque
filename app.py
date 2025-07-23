# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, Fornecedor, Produto, MovimentacaoEstoque, ContaPagar
from datetime import datetime, date, timedelta
from functools import wraps
from sqlalchemy import func
import streamlit as st

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
    if 'logged_in' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == '123456':
            session['logged_in'] = True
            session['username'] = username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

# --- ROTA PRINCIPAL ---
@app.route('/')
@login_required
def index():
    hoje = date.today()
    amanha = hoje + timedelta(days=1)

    # Busca contas vencidas
    contas_vencidas = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento < hoje).all()
    
    # Busca contas que vencem hoje
    contas_vencendo_hoje = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento == hoje).all()

    # Busca contas que vencem amanhã
    contas_vencendo_amanha = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento == amanha).all()

    # Busca outras contas pendentes (que não estão vencidas nem vencem hoje ou amanhã)
    outras_contas_pendentes = ContaPagar.query.filter(ContaPagar.status == 'pendente', ContaPagar.data_vencimento > amanha).order_by(ContaPagar.data_vencimento.asc()).all()

    produtos_estoque_baixo = Produto.query.filter(Produto.quantidade_estoque <= Produto.estoque_minimo).all()
    
    return render_template('index.html', 
                           produtos_alertas=produtos_estoque_baixo, 
                           contas_vencidas=contas_vencidas,
                           contas_vencendo_hoje=contas_vencendo_hoje,
                           contas_vencendo_amanha=contas_vencendo_amanha,
                           outras_contas_pendentes=outras_contas_pendentes)


# --- ROTA DA API PARA OS GRÁFICOS ---
@app.route('/api/dados_graficos')
@login_required
def dados_graficos():
    # ... (código da API permanece o mesmo)
    produtos_top_estoque = db.session.query(Produto.nome, Produto.quantidade_estoque).order_by(Produto.quantidade_estoque.desc()).limit(5).all()
    contas_por_status = db.session.query(ContaPagar.status, func.count(ContaPagar.id)).group_by(ContaPagar.status).all()
    dados = {
        'estoque': {
            'labels': [p.nome for p in produtos_top_estoque],
            'data': [p.quantidade_estoque for p in produtos_top_estoque]
        },
        'contas': {
            'labels': [s[0].capitalize() for s in contas_por_status],
            'data': [s[1] for s in contas_por_status]
        }
    }
    return jsonify(dados)


# --- OUTRAS ROTAS (sem alteração) ---
# ... (todas as outras rotas como /fornecedores, /produtos, etc. permanecem aqui)
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
    produtos = Produto.query.order_by(Produto.nome.asc()).all()
    return render_template('produtos.html', produtos=produtos)

@app.route('/produto/novo', methods=['GET', 'POST'])
@login_required
def adicionar_produto():
    if request.method == 'POST':
        novo_produto = Produto(
            codigo=request.form['codigo'], 
            nome=request.form['nome'],
            categoria=request.form['categoria'],
            preco_custo=float(request.form['preco_custo']),
            preco_venda=float(request.form['preco_venda']),
            quantidade_estoque=int(request.form['quantidade_estoque']),
            estoque_minimo=int(request.form['estoque_minimo']),
            fornecedor_id=request.form['fornecedor_id']
        )
        db.session.add(novo_produto)
        db.session.commit()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
    fornecedores = Fornecedor.query.all()
    return render_template('adicionar_produto.html', fornecedores=fornecedores)

@app.route('/produto/movimentar/<int:id>', methods=['GET', 'POST'])
@login_required
def movimentar_estoque(id):
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        tipo = request.form['tipo']
        quantidade = int(request.form['quantidade'])
        observacao = request.form.get('observacao', '')
        if tipo == 'entrada':
            produto.quantidade_estoque += quantidade
        elif tipo == 'saida':
            if produto.quantidade_estoque >= quantidade:
                produto.quantidade_estoque -= quantidade
            else:
                flash('Erro: Quantidade de saída maior que o estoque disponível.', 'danger')
                return redirect(url_for('listar_produtos'))
        movimento = MovimentacaoEstoque(produto_id=id, tipo=tipo, quantidade=quantidade, observacao=observacao)
        db.session.add(movimento)
        db.session.commit()
        flash(f'Estoque do produto {produto.nome} atualizado.', 'success')
        return redirect(url_for('listar_produtos'))
    return render_template('movimentar_estoque.html', produto=produto)

# --- ROTAS DE CONTAS A PAGAR ---
@app.route('/contas')
@login_required
def listar_contas():
    contas = ContaPagar.query.order_by(ContaPagar.data_vencimento.asc()).all()
    return render_template('contas_a_pagar.html', contas=contas)

@app.route('/conta/nova', methods=['GET', 'POST'])
@login_required
def adicionar_conta():
    if request.method == 'POST':
        nova_conta = ContaPagar(
            fornecedor_id=request.form['fornecedor_id'],
            descricao=request.form['descricao'],
            valor=float(request.form['valor']),
            data_vencimento=datetime.strptime(request.form['data_vencimento'], '%Y-%m-%d').date()
        )
        db.session.add(nova_conta)
        db.session.commit()
        flash('Conta cadastrada com sucesso!', 'success')
        return redirect(url_for('listar_contas'))
    fornecedores = Fornecedor.query.all()
    return render_template('adicionar_conta.html', fornecedores=fornecedores)

@app.route('/conta/pagar/<int:id>', methods=['POST'])
@login_required
def pagar_conta(id):
    conta = ContaPagar.query.get_or_404(id)
    conta.status = 'pago'
    conta.data_pagamento = datetime.utcnow().date()
    db.session.commit()
    flash('Conta marcada como paga.', 'success')
    return redirect(url_for('listar_contas'))

# --- ROTA DE RELATÓRIOS ---
@app.route('/relatorios')
@login_required
def relatorios():
    """
    Exibe a página central de relatórios.
    """
    return render_template('relatorios.html')


# --- COMANDO PARA CRIAR O BANCO DE DADOS ---
with app.app_context():
    db.create_all()

# --- EXECUÇÃO DA APLICAÇÃO ---
#if __name__ == '__main__':
   # app.run(debug=True)



# Seu código Streamlit aqui

if __name__ == "__main__":
    st.title("Minha Aplicação Streamlit")
    # Mais código Streamlit