const TIPOS = { CARRO: "Carro", MOTO: "Moto", VAN: "Van", CAMINHAO: "Caminhão", OUTRO: "Outro" };
const CORES = { CARRO: "azul", MOTO: "laranja", VAN: "roxo", CAMINHAO: "rosa", OUTRO: "amarelo" };

(async () => {
  await iniciarPagina("dashboard");
  try {
    const [cli, vag, ab, pag, tar] = await Promise.all([api("/clientes"), api("/vagas"), api("/movimentacoes/abertas"), api("/pagamentos"), api("/tarifas")]);
    const clientes = cli.dados.filter(c => c.ativo), vagas = vag.dados.filter(v => v.ativa), abertas = ab.dados;

    // Ocupação por tipo de veículo:
    //  - vaga mensalista: ocupada quando está vinculada a um cliente (a vaga é dele);
    //  - vaga rotativa: ocupada por cada horista que está no pátio (limitado ao total de vagas do tipo).
    const horistasDentro = abertas.filter(m => m.modalidade !== "MENSALISTA");
    const porTipo = Object.keys(TIPOS).map(tipo => {
      const doTipo = vagas.filter(v => v.tipo_veiculo === tipo);
      const rot = doTipo.filter(v => v.tipo_vaga === "ROTATIVA").length;
      const men = doTipo.filter(v => v.tipo_vaga === "MENSALISTA").length;
      const menOcup = doTipo.filter(v => v.tipo_vaga === "MENSALISTA" && v.id_cliente).length;
      const rotOcup = Math.min(rot, horistasDentro.filter(m => (m.tipo_veiculo || "CARRO") === tipo).length);
      return { tipo, total: doTipo.length, rot, men, ocupadas: menOcup + rotOcup };
    });
    const total = vagas.length, ocupadas = porTipo.reduce((s, t) => s + t.ocupadas, 0);
    const totRot = vagas.filter(v => v.tipo_vaga === "ROTATIVA").length, totMen = total - totRot;

    const hoje = new Date().toLocaleDateString("sv-SE"); // AAAA-MM-DD no relógio local
    const recebidoHoje = pag.dados.filter(p => new Date(p.pago_em).toISOString().slice(0, 10) === hoje)
      .reduce((s, p) => s + Number(p.valor_pago), 0);

    const kpi = (titulo, valor, cor, extra = "") =>
      `<div class="kpi cor ${cor}"><span>${titulo}</span><b>${valor}</b>${extra ? `<small>${extra}</small>` : ""}</div>`;

    document.getElementById("kpis").innerHTML =
      kpi("Total de vagas", total, "azul", `${totRot} rotativas • ${totMen} mensalistas`) +
      kpi("Vagas ocupadas", ocupadas, "laranja", total ? `${Math.round(ocupadas * 100 / total)}% de ocupação` : "") +
      kpi("Vagas livres", total - ocupadas, "verde");

    document.getElementById("tipos").innerHTML = porTipo.map(t =>
      kpi(TIPOS[t.tipo], `${t.ocupadas}<span style="display:inline;font-size:1rem;font-weight:400"> / ${t.total}</span>`, CORES[t.tipo],
        `${t.total - t.ocupadas} livres • ${t.rot} rotativas • ${t.men} mensalistas`)).join("");

    document.getElementById("resumo").innerHTML =
      kpi("Clientes ativos", clientes.length, "ciano") +
      kpi("Veículos no pátio", abertas.length, "roxo") +
      kpi("Recebido hoje", moeda(recebidoHoje), "verde");

    // Tarifa atual de cada tipo: a vigente; senão a mais recente que já começou; senão a mais antiga.
    // (a lista chega da mais nova para a mais antiga)
    const agora = Date.now();
    const atual = tipo => {
      const ts = tar.dados.filter(t => t.tipo_veiculo === tipo);
      return ts.find(t => Number(t.vigente)) || ts.find(t => new Date(t.vigencia_inicio).getTime() <= agora) || ts[ts.length - 1];
    };
    document.getElementById("tarifas").innerHTML = Object.keys(TIPOS).map(tipo => {
      const t = atual(tipo);
      return `<div class="tarifa-item" style="--cor:var(--c-${CORES[tipo]})">
        <div><b><span class="ponto"></span>${TIPOS[tipo]}</b></div>
        ${t ? `<div class="valores"><b>${moeda(t.valor_periodo_30_min)} / 30 min</b><small>Mensal ${moeda(t.mensalidade_por_vaga)}</small></div>`
            : '<div class="valores"><small>Sem tarifa</small></div>'}</div>`;
    }).join("");

    document.getElementById("patio").innerHTML = abertas.length
      ? abertas.map(m => `<tr><td>${esc(m.placa_registrada)}</td><td>${TIPOS[m.tipo_veiculo] || "—"}</td><td>${esc(m.nome_cliente || "—")}</td><td>${dataHora(m.entrada_em)}</td></tr>`).join("")
      : linhasVazias(4, "Nenhum veículo no pátio.");
  } catch (e) { aviso(e.message, "erro"); }
})();
