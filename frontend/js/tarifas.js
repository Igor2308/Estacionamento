const $ = id => document.getElementById(id);
const TIPOS = { CARRO: "Carro", MOTO: "Moto", VAN: "Van", CAMINHAO: "Caminhão", OUTRO: "Outro" };

async function carregar() {
  const r = await acao(() => api("/tarifas")); if (!r) return;
  $("lista").innerHTML = r.dados.length ? r.dados.map(t => `<tr>
    <td><b>${TIPOS[t.tipo_veiculo] || esc(t.tipo_veiculo)}</b></td><td>${dataSimples(t.vigencia_inicio)}</td><td>${t.vigencia_fim ? dataSimples(t.vigencia_fim) : "em aberto"}</td>
    <td>${moeda(t.valor_periodo_30_min)}</td><td>${moeda(t.mensalidade_por_vaga)}</td>
    <td>${Number(t.vigente) ? '<span class="tag ok">Vigente</span>' : '<span class="tag off">Encerrada / futura</span>'}</td></tr>`).join("")
    : linhasVazias(6, "Nenhuma tarifa cadastrada — cadastre uma acima.");
}

$("form").onsubmit = async e => {
  e.preventDefault();
  const d = formParaObjeto(e.target);
  d.valor_periodo_30_min = d.valor_periodo_30_min.replace(",", ".");
  d.mensalidade_por_vaga = d.mensalidade_por_vaga.replace(",", ".");
  if (await acao(() => api("/tarifas", { metodo: "POST", corpo: d }), "Tarifa cadastrada.")) { e.target.reset(); $("inicio").value = hoje(); carregar(); }
};

function hoje() { return new Date().toLocaleDateString("sv-SE"); } // AAAA-MM-DD no relógio local
(async () => { await iniciarPagina("tarifas"); $("inicio").value = hoje(); carregar(); })();
