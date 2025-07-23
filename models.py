# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Cria uma instância do SQLAlchemy que será conectada à aplicação Flask
db = SQLAlchemy()

class Fornecedor(db.Model):
    """
    Define a tabela 'fornecedor' para armazenar os dados dos fornecedores.
    """
    __tablename__ = 'fornecedor'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    
    # Relacionamentos: um fornecedor pode ter vários produtos e várias contas a pagar.
    # O 'backref' cria um atributo virtual (ex: produto.fornecedor) no modelo relacionado.
    # 'lazy=True' significa que os dados relacionados serão carregados apenas quando acessados.
    produtos = db.relationship('Produto', backref='fornecedor', lazy=True)
    contas = db.relationship('ContaPagar', backref='fornecedor', lazy=True)

    def __repr__(self):
        # Representação em texto do objeto, útil para depuração
        return f'<Fornecedor {self.nome}>'

class Produto(db.Model):
    """
    Define a tabela 'produto' para o controle de estoque.
    """
    __tablename__ = 'produto'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    preco_custo = db.Column(db.Float, nullable=False)
    preco_venda = db.Column(db.Float, nullable=False)
    quantidade_estoque = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo = db.Column(db.Integer, default=5)
    
    # Chave estrangeira que liga o produto a um fornecedor
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    
    # Relacionamento: um produto pode ter várias movimentações de estoque
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='produto', lazy=True)

    def __repr__(self):
        return f'<Produto {self.nome}>'

class MovimentacaoEstoque(db.Model):
    """
    Define a tabela 'movimentacao_estoque' para registrar entradas e saídas.
    """
    __tablename__ = 'movimentacao_estoque'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)  # 'entrada' ou 'saida'
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    observacao = db.Column(db.String(200))

    # Chave estrangeira que liga a movimentação a um produto
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)

    def __repr__(self):
        return f'<Movimentacao {self.produto.nome} - {self.tipo}: {self.quantidade}>'

class ContaPagar(db.Model):
    """
    Define a tabela 'conta_pagar' para o controle financeiro.
    """
    __tablename__ = 'conta_pagar'
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=True) # Fica nulo até ser pago
    status = db.Column(db.String(20), nullable=False, default='pendente') # 'pendente', 'pago', 'vencido'

    # Chave estrangeira que liga a conta a um fornecedor
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)

    def __repr__(self):
        return f'<Conta {self.descricao} - {self.status}>'
