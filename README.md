Sistema de Gestão de Estoque e PDV
<!-- Sugestão: Tire um print screen do seu painel e substitua o link -->

Um sistema de gestão completo desenvolvido em Python com o framework Flask. Esta aplicação web foi projetada para ajudar pequenas empresas a gerir o seu estoque, processar vendas através de um Ponto de Venda (PDV), controlar as finanças (contas a pagar e a receber) e gerar relatórios essenciais para a tomada de decisões.

✨ Funcionalidades Principais
O sistema está dividido em módulos intuitivos para cobrir as principais áreas de gestão de um negócio:

Painel de Controlo (Dashboard):

Visão Geral: Gráficos informativos sobre os produtos mais vendidos, o estado do estoque e a situação financeira.

Alertas Inteligentes: Notificações automáticas para produtos com estoque baixo, produtos perto do vencimento e contas a pagar/receber em atraso.

Ponto de Venda (PDV):

Vendas Rápidas: Interface otimizada para um registo de vendas rápido e eficiente.

Gestão de Clientes: Pesquisa e associação de clientes a vendas.

Vendas a Prazo: Lançamento automático de contas a receber com opção de parcelamento.

Devoluções: Modo de devolução que reverte a venda, atualiza o estoque e gera crédito para o cliente.

Emissão de Cupom: Geração de um cupom não fiscal para cada transação.

Gestão de Estoque:

Cadastro de Produtos: Registo completo de produtos, incluindo código, preço de custo/venda, estoque mínimo e datas de validade.

Entrada por XML: Importação de Notas Fiscais Eletrónicas (NF-e) para dar entrada automática de produtos no estoque e lançar as contas a pagar.

Controlo de Movimentações: Histórico detalhado de todas as entradas e saídas.

Financeiro:

Contas a Pagar: Lançamento manual ou automático (via XML) de despesas.

Contas a Receber: Gestão de vendas a prazo, com controlo de parcelas e baixas de pagamentos.

Cadastros:

Clientes: Base de dados de clientes para associação a vendas.

Fornecedores: Registo de fornecedores com CNPJ para importação de XML.

Utilizadores: Sistema de login seguro, com criação de múltiplos utilizadores e recuperação de palavra-passe.

Relatórios:

Inventário de Estoque: Lista completa de produtos com valor de custo.

Estoque Baixo: Relação de produtos que precisam de ser repostos.

Movimentações: Histórico de entradas e saídas por período.

Financeiros: Relatórios de contas a pagar, a receber e despesas por fornecedor.

Sistema:

Backup: Funcionalidade para descarregar uma cópia de segurança da base de dados.

🚀 Tecnologias Utilizadas
Backend: Python, Flask, SQLAlchemy

Frontend: HTML, CSS, JavaScript, Bootstrap 5

Base de Dados: SQLite

Bibliotecas Python: Werkzeug (para segurança de palavras-passe), python-dateutil (para manipulação de datas).

⚙️ Instalação e Execução
Para executar este projeto localmente, siga os passos abaixo.

Pré-requisitos:

Python 3.x

pip (gestor de pacotes do Python)

1. Clone o Repositório:

git clone [https://github.com/seu-usuario/nome-do-repositorio.git](https://github.com/seu-usuario/nome-do-repositorio.git)
cd nome-do-repositorio

2. Crie e Ative um Ambiente Virtual:

# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

3. Instale as Dependências:

pip install -r requirements.txt

(Nota: Certifique-se de que tem um ficheiro requirements.txt com as bibliotecas Flask, Flask-SQLAlchemy, Werkzeug e python-dateutil).

4. Execute a Aplicação:

python app.py

A aplicação estará a ser executada em http://127.0.0.1:5000.

5. Primeiro Acesso:

Utilizador: admin

Palavra-passe: 171721

Ao fazer o primeiro login, o utilizador "admin" será criado automaticamente. Recomenda-se que troque a palavra-passe e o e-mail logo após o primeiro acesso.
