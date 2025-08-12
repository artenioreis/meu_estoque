# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiration = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiration = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

class Fornecedor(db.Model):
    __tablename__ = 'fornecedor'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    cnpj = db.Column(db.String(18), unique=True, nullable=True)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    produtos = db.relationship('Produto', backref='fornecedor', lazy=True)
    contas = db.relationship('ContaPagar', backref='fornecedor', lazy=True)

class Produto(db.Model):
    __tablename__ = 'produto'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    preco_custo = db.Column(db.Float, nullable=False)
    preco_venda = db.Column(db.Float, nullable=False)
    quantidade_estoque = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo = db.Column(db.Integer, default=5)
    data_fabricacao = db.Column(db.Date, nullable=True)
    data_vencimento = db.Column(db.Date, nullable=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='produto', lazy=True)

class MovimentacaoEstoque(db.Model):
    __tablename__ = 'movimentacao_estoque'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    observacao = db.Column(db.String(200))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)

class ContaPagar(db.Model):
    __tablename__ = 'conta_pagar'
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pendente')
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)

class Cliente(db.Model):
    __tablename__ = 'cliente'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    endereco = db.Column(db.String(200))
    vendas = db.relationship('MovimentacaoEstoque', backref='cliente', lazy=True, cascade="all, delete-orphan")
    contas_a_receber = db.relationship('ContaReceber', backref='cliente', lazy=True, cascade="all, delete-orphan")

class ContaReceber(db.Model):
    __tablename__ = 'conta_receber'
    id = db.Column(db.Integer, primary_key=True)
    valor = db.Column(db.Float, nullable=False)
    data_venda = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    data_vencimento = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Em Aberto')
    forma_pagamento = db.Column(db.String(50), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)

class XmlImportado(db.Model):
    __tablename__ = 'xml_importado'
    id = db.Column(db.Integer, primary_key=True)
    chave_nfe = db.Column(db.String(44), nullable=False, unique=True)
    nome_arquivo = db.Column(db.String(200), nullable=False)
    data_importacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
