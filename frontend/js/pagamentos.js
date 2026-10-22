const $ = id => document.getElementById(id);
const TIPOS = { HORISTA: "Horista", MENSALIDADE: "Mensalidade", OUTRO: "Outro" };

function mostrarCampos() {
  const t = $("tipo").value;
  document.querySelectorAll("[data-t]").forEach(l => {
    const ativo = l.dataset.t === t;
    l.classList.toggle("oculto", !ativo);
    l.querySelectorAll("input,select").forEach(c => (c.disabled = !ativo)); // campos ocultos não são enviados
  });
  $("dica").textContent = t === "MENSALIDADE"
    ? "A mensalidade é gerada ao vincular a vaga (e a cada novo mês). O valor vem da tarifa do tipo de veículo da vaga."
    : t === "HORISTA" ? "O valor vem da saída registrada (períodos iniciados de 30 min)." : "";
}
$("tipo").onchange = mostrarCampos;

async function carregar() {
  const [m, p, c, cb] = await Promise.all([acao(() => api("/movimentacoes")), acao(() => api("/pagamentos")), acao(() => api("/clientes")), acao(() => api("/pagamentos/cobrancas?status=ABERTA"))]);
  if (!m || !p || !c || !cb) return;
  const pagas = new Set(p.dados.filter(x => x.id_movimentacao).map(x => x.id_movimentacao));
  const pendentes = m.dados.filter(x => x.saida_em && Number(x.valor_total) > 0 && !pagas.has(x.id_movimentacao));
  $("mov").innerHTML = pendentes.length
    ? pendentes.map(x => `<option value="${x.id_movimentacao}">${esc(x.placa_registrada)} • ${moeda(x.valor_total)} • ${dataHora(x.saida_em)}</option>`).join("")
    : '<option value="">Nenhuma saída pendente</option>';
  const ativos = c.dados.filter(x => x.ativo);
  const rotuloCob = x => `${esc(x.nome_cliente)} • vaga ${esc(x.codigo_vaga)} • ${dataSimples(x.competencia_inicio)} a ${dataSimples(x.competencia_fim)} • ${moeda(x.valor)}`;
  $("cob").innerHTML = cb.dados.length ? cb.dados.map(x => `<option value="${x.id_cobranca}">${rotuloCob(x)}</option>`).join("") : '<option value="">Nenhuma mensalidade em aberto</option>';
  $("abertas").innerHTML = cb.dados.length ? cb.dados.map(x => `<tr><td>${esc(x.nome_cliente)}</td><td>${esc(x.codigo_vaga)}</td>
    <td>${dataSimples(x.competencia_inicio)} a ${dataSimples(x.competencia_fim)}</td><td><b>${moeda(x.valor)}</b></td>
    <td><button class="mini" data-cob="${x.id_cobranca}">Pagar</button></td></tr>`).join("") : linhasVazias(5, "Nenhuma mensalidade em aberto.");
  $("cliOutro").innerHTML = '<option value="">—</option>' + ativos.map(x => `<option value="${x.id_cliente}">${esc(x.nome)}</option>`).join("");
  const q = new URLSearchParams(location.search).get("mov");
  if (q && pendentes.some(x => String(x.id_movimentacao) === q)) { $("tipo").value = "HORISTA"; $("mov").value = q; mostrarCampos(); }
  $("lista").innerHTML = p.dados.length ? p.dados.map(x => `<tr><td>${dataHora(x.pago_em)}</td><td>${TIPOS[x.tipo_pagamento]}</td>
    <td>${esc(x.nome_cliente || x.placa_registrada || "—")}${x.nome_cliente && x.placa_registrada ? " • " + esc(x.placa_registrada) : ""}</td>
    <td>${x.competencia_inicio ? dataSimples(x.competencia_inicio) + " a " + dataSimples(x.competencia_fim) : "—"}</td>
    <td>${esc(x.forma_pagamento.replace("_", " ").toLowerCase())}</td><td><b>${moeda(x.valor_pago)}</b></td></tr>`).join("") : linhasVazias(6);
}

$("abertas").onclick = e => {
  const b = e.target.closest("button"); if (!b) return;
  $("tipo").value = "MENSALIDADE"; mostrarCampos(); $("cob").value = b.dataset.cob;
  $("form").scrollIntoView({ behavior: "smooth", block: "center" });
};

$("form").onsubmit = async e => {
  e.preventDefault();
  const d = formParaObjeto(e.target); // só inclui campos habilitados
  if (d.id_cliente === "") delete d.id_cliente;
  if (d.id_cliente) d.id_cliente = Number(d.id_cliente);
  if (d.id_movimentacao) d.id_movimentacao = Number(d.id_movimentacao);
  if (d.id_cobranca) d.id_cobranca = Number(d.id_cobranca);
  if (d.valor_pago) d.valor_pago = d.valor_pago.replace(",", ".");
  const r = await acao(() => api("/pagamentos", { metodo: "POST", corpo: d }), x => `Pagamento registrado: ${moeda(x.valor_pago)}.`);
  if (r) { e.target.reset(); mostrarCampos(); carregar(); }
};

(async () => {
  await iniciarPagina("pagamentos");
  mostrarCampos(); carregar();
})();
