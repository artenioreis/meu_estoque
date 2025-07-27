document.addEventListener('DOMContentLoaded', function () {
    const apiUrlContainer = document.getElementById('api-url-container');
    
    if (!apiUrlContainer) {
        console.error("Erro Crítico: O elemento 'api-url-container' não foi encontrado no HTML.");
        return;
    }

    const apiUrl = apiUrlContainer.dataset.url;

    if (!apiUrl || apiUrl.includes('{'.concat('{'))) {
        const errorBanner = document.getElementById('error-banner');
        if (errorBanner) {
            errorBanner.style.display = 'block';
        }
        console.error('Erro: A URL da API não foi renderizada. Verifique se o servidor Flask está rodando e se a página foi acessada através dele (ex: http://127.0.0.1:5000), e não abrindo o arquivo HTML diretamente.');
        return;
    }

    // Função para mostrar mensagem de "sem dados"
    const showNoDataMessage = (chartId, messageId) => {
        const chartCanvas = document.getElementById(chartId);
        const messageEl = document.getElementById(messageId);
        if (chartCanvas) chartCanvas.style.display = 'none';
        if (messageEl) messageEl.style.display = 'block';
    };

    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            // Gráfico 1: Vendas Diárias (Linha)
            if (data.vendas_diarias && data.vendas_diarias.data.some(v => v > 0)) {
                const ctxVendas = document.getElementById('graficoVendasDiarias')?.getContext('2d');
                if (ctxVendas) {
                    new Chart(ctxVendas, {
                        type: 'line',
                        data: {
                            labels: data.vendas_diarias.labels,
                            datasets: [{
                                label: 'Nº de Vendas',
                                data: data.vendas_diarias.data,
                                fill: true,
                                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                                borderColor: 'rgba(153, 102, 255, 1)',
                                tension: 0.1
                            }]
                        },
                        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
                    });
                }
            } else {
                showNoDataMessage('graficoVendasDiarias', 'no-data-vendas');
            }

            // Gráfico 2: Contas a Pagar (Rosca/Doughnut)
            if (data.contas_pagar && data.contas_pagar.labels.length > 0) {
                const ctxContas = document.getElementById('graficoContasPagar')?.getContext('2d');
                if (ctxContas) {
                    new Chart(ctxContas, {
                        type: 'doughnut',
                        data: {
                            labels: data.contas_pagar.labels,
                            datasets: [{
                                label: 'Status',
                                data: data.contas_pagar.data,
                                backgroundColor: ['rgba(255, 159, 64, 0.7)', 'rgba(75, 192, 192, 0.7)', 'rgba(255, 99, 132, 0.7)'],
                                borderColor: '#fff',
                                borderWidth: 2
                            }]
                        },
                        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } } }
                    });
                }
            } else {
                showNoDataMessage('graficoContasPagar', 'no-data-contas');
            }

            // Gráfico 3: Top Produtos em Estoque (Barras Horizontais)
            if (data.estoque && data.estoque.labels.length > 0) {
                const ctxEstoque = document.getElementById('graficoEstoque')?.getContext('2d');
                if (ctxEstoque) {
                    new Chart(ctxEstoque, {
                        type: 'bar',
                        data: {
                            labels: data.estoque.labels,
                            datasets: [{
                                label: 'Quantidade em Estoque',
                                data: data.estoque.data,
                                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 1
                            }]
                        },
                        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
                    });
                }
            } else {
                showNoDataMessage('graficoEstoque', 'no-data-estoque');
            }

            // Gráfico 4: Mais Vendidos (Barras Horizontais)
            if (data.mais_vendidos && data.mais_vendidos.labels.length > 0) {
                const ctxMaisVendidos = document.getElementById('graficoMaisVendidos')?.getContext('2d');
                if (ctxMaisVendidos) {
                    new Chart(ctxMaisVendidos, {
                        type: 'bar',
                        data: {
                            labels: data.mais_vendidos.labels,
                            datasets: [{
                                label: 'Unidades Vendidas',
                                data: data.mais_vendidos.data,
                                backgroundColor: 'rgba(75, 192, 192, 0.6)',
                                borderColor: 'rgba(75, 192, 192, 1)',
                                borderWidth: 1
                            }]
                        },
                        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
                    });
                }
            } else {
                showNoDataMessage('graficoMaisVendidos', 'no-data-vendidos');
            }
        })
        .catch(error => {
            console.error('Houve um problema com a operação fetch:', error);
        });
});
