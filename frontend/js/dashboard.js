const CORES = { CARRO: "azul", MOTO: "laranja", VAN: "roxo", CAMINHAO: "rosa", OUTRO: "amarelo" };

(async () => {
  await iniciarPagina("dashboard");
  try {
    // Os números vêm prontos do servidor; só os primeiros veículos do pátio são listados aqui.
    const [r, ab] = await Promise.all([api("/dashboard/resumo"), api("/movimentacoes/abertas?pagina=1")]);

    const porTipo = r.por_tipo;
    const total = porTipo.reduce((s, t) => s + t.total, 0), ocupadas = porTipo.reduce((s, t) => s + t.ocupadas, 0);
    const totRot = porTipo.reduce((s, t) => s + t.rotativas, 0), totMen = total - totRot;

    const kpi = (titulo, valor, cor, extra = "") =>
      `<div class="kpi cor ${cor}"><span>${titulo}</span><b>${valor}</b>${extra ? `<small>${extra}</small>` : ""}</div>`;

    document.getElementById("kpis").innerHTML =
      kpi("Total de vagas", total, "azul", `${totRot} rotativas • ${totMen} mensalistas`) +
      kpi("Vagas ocupadas", ocupadas, "laranja", total ? `${Math.round(ocupadas * 100 / total)}% de ocupação` : "") +
      kpi("Vagas livres", total - ocupadas, "verde") +
      kpi("Clientes ativos", r.clientes_ativos, "ciano") +
      kpi("Veículos no pátio", r.veiculos_no_patio, "roxo") +
      kpi("Recebido hoje", moeda(r.recebido_hoje), "rosa");

    // um cartão por tipo de veículo, os cinco na mesma linha (inclusive "Outro")
    document.getElementById("tipos").innerHTML = porTipo.map(t =>
      kpi(TIPOS_VEICULO[t.tipo], `${t.ocupadas}<span style="display:inline;font-size:1rem;font-weight:400"> / ${t.total}</span>`, CORES[t.tipo],
        `${t.total - t.ocupadas} livres • ${t.rotativas} rotativas • ${t.mensalistas} mensalistas`)).join("");

    document.getElementById("tarifas").innerHTML = Object.keys(TIPOS_VEICULO).map(tipo => {
      const t = r.tarifas[tipo];
      return `<div class="tarifa-item" style="--cor:var(--c-${CORES[tipo]})">
        <div><b><span class="ponto"></span>${TIPOS_VEICULO[tipo]}</b></div>
        ${t ? `<div class="valores"><b>${moeda(t.valor_periodo_30_min)} / 30 min</b><small>Mensal ${moeda(t.mensalidade_por_vaga)}</small></div>`
            : '<div class="valores"><small>Sem tarifa</small></div>'}</div>`;
    }).join("");

    const abertas = ab.dados;
    document.getElementById("patio").innerHTML = abertas.length
      ? abertas.map(m => `<tr><td>${esc(m.placa_registrada)}</td><td>${TIPOS_VEICULO[m.tipo_veiculo] || "—"}</td><td>${esc(m.nome_cliente || "—")}</td><td>${m.modalidade === "MENSALISTA" ? "Mensalista" : "Horista"}</td><td>${dataHora(m.entrada_em)}</td></tr>`).join("")
      : linhasVazias(5, "Nenhum veículo no pátio.");
    if (ab.total > abertas.length)
      document.getElementById("patioMais").textContent = `Mostrando os ${abertas.length} mais antigos de ${ab.total}. Veja todos em Entradas e saídas.`;
  } catch (e) { aviso(e.message, "erro"); }
})();
