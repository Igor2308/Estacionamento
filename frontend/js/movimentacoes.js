const $ = id => document.getElementById(id);
const TIPOS = { CARRO: "Carro", MOTO: "Moto", VAN: "Van", CAMINHAO: "Caminhão", OUTRO: "Outro" };
// O tempo vem em segundos, calculado pelo servidor (mesmo relógio da cobrança); o navegador só vai somando.
let carregadoEm = Date.now();
function tempo(segundos) {
  const min = Math.max(0, Math.floor(segundos / 60));
  return Math.floor(min / 60) + "h " + String(min % 60).padStart(2, "0") + "min";
}
setInterval(() => {
  const extra = (Date.now() - carregadoEm) / 1000;
  document.querySelectorAll("td.tempo").forEach(td => (td.textContent = tempo(Number(td.dataset.seg) + extra)));
}, 30000);
function mostrarAba(aba) {
  const horista = aba === "horista";
  $("painelHorista").classList.toggle("oculto", !horista);
  $("painelMensalista").classList.toggle("oculto", horista);
  $("abaHorista").classList.toggle("ativa", horista);
  $("abaMensalista").classList.toggle("ativa", !horista);
}
$("abaHorista").onclick = () => mostrarAba("horista");
$("abaMensalista").onclick = () => mostrarAba("mensalista");

async function carregar() {
  const [a, h, m] = await Promise.all([acao(() => api("/movimentacoes/abertas")), acao(() => api("/movimentacoes")), acao(() => api("/movimentacoes/mensalistas"))]);
  if (!a || !h || !m) return;
  carregadoEm = Date.now();
  const horistas = a.dados.filter(x => x.modalidade !== "MENSALISTA");
  $("abertas").innerHTML = horistas.length ? horistas.map(x => `<tr><td><b>${esc(x.placa_registrada)}</b></td>
    <td>${TIPOS[x.tipo_veiculo] || "—"}</td><td>${esc(x.nome_cliente || "—")}</td><td>${dataHora(x.entrada_em)}</td>
    <td class="tempo" data-seg="${Number(x.segundos_no_patio) || 0}">${tempo(Number(x.segundos_no_patio) || 0)}</td>
    <td><button class="mini" data-id="${x.id_movimentacao}">Registrar saída</button></td></tr>`).join("")
    : linhasVazias(6, "Nenhum horista no pátio.");
  $("mensalistas").innerHTML = m.dados.length ? m.dados.map(x => {
    const aberto = Number(x.valor_em_aberto) > 0;
    return `<tr><td><b>${esc(x.nome)}</b></td><td>${esc(x.codigo)}</td><td>${TIPOS[x.tipo_veiculo] || "—"}</td>
    <td>${aberto ? `<span class="tag off">${moeda(x.valor_em_aberto)}</span>` : '<span class="tag ok">Em dia</span>'}</td>
    <td><button class="mini perigo" data-vaga="${x.id_vaga}" data-nome="${esc(x.nome)}" data-cod="${esc(x.codigo)}" ${aberto ? 'disabled title="Pague o valor em aberto na tela Pagamentos"' : ""}>Cancelar vaga (saída)</button></td></tr>`;
  }).join("") : linhasVazias(5, "Nenhuma vaga mensalista vinculada.");
  const fechadas = h.dados.filter(x => x.saida_em);
  $("historico").innerHTML = fechadas.length ? fechadas.slice(0, 50).map(x => `<tr><td>${esc(x.placa_registrada)}</td>
    <td>${esc(x.nome_cliente || "—")}</td><td>${dataHora(x.entrada_em)}</td><td>${dataHora(x.saida_em)}</td>
    <td>${x.periodos_cobrados ?? 0}</td><td>${moeda(x.valor_total)}</td></tr>`).join("") : linhasVazias(6, "Sem saídas registradas.");
}
async function carregarPlacas() {
  const r = await acao(() => api("/veiculos")); if (!r) return;
  $("placas").innerHTML = r.dados.filter(v => v.ativo && v.modalidade_cliente !== "MENSALISTA").map(v => `<option value="${esc(v.placa)}">${esc(v.nome_cliente)}</option>`).join("");
}
$("form").onsubmit = async e => {
  e.preventDefault();
  const r = await acao(() => api("/movimentacoes/entrada", { metodo: "POST", corpo: formParaObjeto(e.target) }),
    x => `Entrada de ${x.placa} registrada.`);
  if (r) { e.target.reset(); carregar(); }
};
$("abertas").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const r = await acao(() => api(`/movimentacoes/${b.dataset.id}/saida`, { metodo: "POST" }));
  if (!r) return;
  const valor = Number(r.valor_total);
  if (valor > 0) {
    aviso(`Saída registrada: ${r.periodos_cobrados} período(s) = ${moeda(valor)}.`);
    if (confirm(`Total a cobrar: ${moeda(valor)}.\nRegistrar o pagamento agora?`)) location.href = "pagamentos.html?mov=" + r.id_movimentacao;
  } else aviso("Saída registrada (sem cobrança).");
  carregar();
};
$("mensalistas").onclick = async e => {
  const b = e.target.closest("button"); if (!b || b.disabled) return;
  if (!confirm(`Cancelar o plano da vaga ${b.dataset.cod} de ${b.dataset.nome}?\n\nA vaga será liberada. Se for a última vaga do cliente, ele passará a ser horista.`)) return;
  const r = await acao(() => api(`/movimentacoes/mensalistas/vagas/${b.dataset.vaga}/saida`, { metodo: "POST" }), x => x.mensagem);
  if (r) { carregar(); carregarPlacas(); }
};
(async () => { await iniciarPagina("movimentacoes"); carregar(); carregarPlacas(); })();
