const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
const TIPOS = { HORISTA: "Horista", MENSALIDADE: "Mensalidade", OUTRO: "Outro" };
const FORMAS = { PIX: "Pix", DINHEIRO: "Dinheiro", CARTAO_DEBITO: "Cartão de débito", CARTAO_CREDITO: "Cartão de crédito", TRANSFERENCIA: "Transferência", OUTRO: "Outro" };
let pagAbertas, pagLista;

const valorBusca = combo => combo.valor || (combo.input.value.trim() ? "?" : "");
const periodo = x => `${dataSimples(x.competencia_inicio)} a ${dataSimples(x.competencia_fim)}`;
const vagasTxt = x => (x.quantidade_vagas > 1 ? `${x.quantidade_vagas} vagas (${x.codigo_vaga})` : `vaga ${x.codigo_vaga}`);

const comboMov = criarBusca($("comboMov"), {
  placeholder: "Digite a placa ou o nome do cliente…",
  buscar: async t => (await api(`/pagamentos/pendentes?pagina=1&busca=${enc(t)}`)).dados.map(x => ({
    id: x.id_movimentacao, valor: Number(x.valor_total),
    rotulo: `${x.placa_registrada} • ${moeda(x.valor_total)} • ${dataHora(x.saida_em)}${x.nome_cliente ? " • " + x.nome_cliente : ""}`,
  })),
});
const comboCob = criarBusca($("comboCob"), {
  placeholder: "Digite o nome do cliente ou o código da vaga…",
  buscar: async t => (await api(`/pagamentos/cobrancas?status=ABERTA&agrupar=1&pagina=1&busca=${enc(t)}`)).dados.map(x => ({
    id: x.id_cobranca, valor: Number(x.valor),
    rotulo: `${x.nome_cliente} • ${vagasTxt(x)} • ${periodo(x)} • ${moeda(x.valor)}`,
  })),
});
const comboCli = criarBusca($("comboCli"), {
  placeholder: "Digite o nome ou CPF/CNPJ do cliente…",
  buscar: async t => (await api(`/clientes?ativo=1&pagina=1&busca=${enc(t)}`)).dados.map(c => ({ id: c.id_cliente, rotulo: `${c.nome} — ${fmtDocumento(c)}` })),
});

const tipo = () => $("tipo").value;
const dinheiro = () => $("forma").value === "DINHEIRO";
/* valor que o cliente precisa pagar, conforme o tipo (null enquanto não souber) */
function valorAPagar() {
  if (tipo() === "HORISTA") return comboMov.item ? comboMov.item.valor : null;
  if (tipo() === "MENSALIDADE") return comboCob.item ? comboCob.item.valor : null;
  return dinheiroValido($("valor").value) ? numeroDinheiro($("valor").value) : null;
}
const erroCombo = msg => v => (v === "?" ? msg : null);

const seq = formularioSequencial({
  form: $("form"), botao: $("salvar"),
  aoAvaliar: () => atualizarTroco(),
  campos: [
    { el: $("tipo"), aoMudar: () => { comboMov.limpar(); comboCob.limpar(); comboCli.limpar(); $("valor").value = ""; $("recebido").value = ""; mostrarDica(); seq.limpar(); } },
    { el: comboMov.input, caixa: $("caixaMov"), valor: () => valorBusca(comboMov), visivel: () => tipo() === "HORISTA",
      erroVazio: "Escolha a saída que será paga.", validar: erroCombo("Escolha uma saída da lista.") },
    { el: comboCob.input, caixa: $("caixaCob"), valor: () => valorBusca(comboCob), visivel: () => tipo() === "MENSALIDADE",
      erroVazio: "Escolha a mensalidade que será paga.", validar: erroCombo("Escolha uma mensalidade da lista.") },
    { el: comboCli.input, caixa: $("caixaCli"), opcional: true, valor: () => valorBusca(comboCli), visivel: () => tipo() === "OUTRO",
      validar: erroCombo("Escolha um cliente da lista ou apague o texto.") },
    { el: $("valor"), caixa: $("caixaValor"), filtro: filtros.dinheiro, visivel: () => tipo() === "OUTRO",
      validar: v => (!dinheiroValido(v) ? "Valor inválido. Use números, com vírgula e até 2 casas (ex.: 10,50)."
        : numeroDinheiro(v) <= 0 ? "O valor deve ser maior que zero." : null) },
    { el: $("forma"), aoMudar: () => { $("recebido").value = ""; seq.limpar(); } },
    { el: $("recebido"), caixa: $("caixaRecebido"), filtro: filtros.dinheiro, visivel: dinheiro,
      validar: v => {
        if (!dinheiroValido(v)) return "Valor inválido. Use números, com vírgula e até 2 casas (ex.: 50,00).";
        const a = valorAPagar();
        return a !== null && numeroDinheiro(v) + 1e-9 < a ? `O cliente entregou menos que o valor a pagar (${moeda(a)}).` : null;
      } },
    { el: $("obs"), opcional: true, filtro: filtros.texto(255) },
  ],
});

function atualizarTroco() {
  const caixa = $("trocoBox");
  const a = valorAPagar();
  if (!dinheiro() || a === null) { caixa.classList.add("oculto"); return; }
  caixa.classList.remove("oculto");
  const v = $("recebido").value;
  $("trocoLinha").textContent = `A receber: ${moeda(a)} · Troco a devolver`;
  $("trocoValor").textContent = dinheiroValido(v) && numeroDinheiro(v) >= a ? moeda(Math.round((numeroDinheiro(v) - a) * 100) / 100) : "—";
}
function mostrarDica() {
  $("dica").textContent = tipo() === "MENSALIDADE"
    ? "A mensalidade é gerada ao vincular a vaga (e a cada novo mês). O valor vem da tarifa do tipo de veículo da vaga."
    : tipo() === "HORISTA" ? "O valor vem da saída registrada (períodos iniciados de 30 min)." : "";
}
for (const c of [comboMov, comboCob]) c.input.addEventListener("input", () => atualizarTroco());
$("valor").addEventListener("input", () => atualizarTroco());

/* ---------- caixa do dia ---------- */
async function carregarCaixa() {
  const r = await acao(() => api("/pagamentos/resumo-dinheiro")); if (!r) return;
  $("caixaDia").innerHTML = `<div><span>Recebido em dinheiro</span><b>${moeda(r.recebido)}</b></div>
    <div><span>Troco devolvido</span><b>${moeda(r.troco)}</b></div>
    <div><span>Ficou no caixa</span><b>${moeda(r.liquido)}</b></div>
    <div><span>Pagamentos em dinheiro</span><b>${r.quantidade}</b></div>`;
}

/* ---------- listas ---------- */
pagAbertas = criarPaginador({
  barra: $("pagAbertas"), busca: $("buscaAbertas"),
  carregar: (p, t) => acao(() => api(`/pagamentos/cobrancas?status=ABERTA&agrupar=1&pagina=${p}&busca=${enc(t)}`)),
  desenhar: (dados, { vazio }) => {
    $("abertas").innerHTML = dados.length ? dados.map(x => `<tr><td>${esc(x.nome_cliente)}</td><td>${esc(x.quantidade_vagas > 1 ? `${x.quantidade_vagas} vagas: ${x.codigo_vaga}` : x.codigo_vaga)}</td>
      <td>${periodo(x)}</td><td><b>${moeda(x.valor)}</b></td>
      <td><button class="mini" data-cob="${x.id_cobranca}" data-valor="${x.valor}" data-r="${esc(`${x.nome_cliente} • ${vagasTxt(x)} • ${periodo(x)} • ${moeda(x.valor)}`)}">Pagar</button></td></tr>`).join("")
      : linhasVazias(5, vazio === "Nenhum registro encontrado." ? "Nenhuma mensalidade em aberto." : vazio);
  },
});
pagLista = criarPaginador({
  barra: $("pagLista"), busca: $("buscaLista"),
  carregar: (p, t) => acao(() => api(`/pagamentos?pagina=${p}&busca=${enc(t)}`)),
  desenhar: (dados, { vazio }) => {
    $("lista").innerHTML = dados.length ? dados.map(x => `<tr><td>${dataHora(x.pago_em)}</td><td>${TIPOS[x.tipo_pagamento]}</td>
      <td>${esc(x.nome_cliente || x.placa_registrada || "—")}${x.nome_cliente && x.placa_registrada ? " • " + esc(x.placa_registrada) : ""}</td>
      <td>${x.competencia_inicio ? periodo(x) : "—"}</td>
      <td>${FORMAS[x.forma_pagamento] || esc(x.forma_pagamento)}</td><td><b>${moeda(x.valor_pago)}</b></td>
      <td>${x.valor_recebido != null ? `${moeda(x.valor_recebido)}<br><small>troco ${moeda(x.troco)}</small>` : "—"}</td>
      <td>${celulaRegistro(x.cadastrado_por_nome, x.cadastrado_em)}</td></tr>`).join("") : linhasVazias(8, vazio);
  },
});
const atualizarListas = () => { pagAbertas.recarregar(); pagLista.recarregar(); carregarCaixa(); };

$("abertas").onclick = e => {
  const b = e.target.closest("button"); if (!b) return;
  $("tipo").value = "MENSALIDADE"; $("tipo").dispatchEvent(new Event("change"));
  comboCob.definir({ id: Number(b.dataset.cob), valor: Number(b.dataset.valor), rotulo: b.dataset.r });
  seq.avaliar();
  $("form").scrollIntoView({ behavior: "smooth", block: "center" });
};

$("form").onsubmit = async e => {
  e.preventDefault();
  if (!seq.tocarTudo()) return;
  const d = { tipo_pagamento: tipo(), forma_pagamento: $("forma").value };
  const obs = $("obs").value.trim(); if (obs) d.observacao = obs;
  if (tipo() === "HORISTA") d.id_movimentacao = Number(comboMov.valor);
  if (tipo() === "MENSALIDADE") d.id_cobranca = Number(comboCob.valor);
  if (tipo() === "OUTRO") { d.valor_pago = $("valor").value.replace(",", "."); if (comboCli.valor) d.id_cliente = Number(comboCli.valor); }
  if (dinheiro()) d.valor_recebido = $("recebido").value.replace(",", ".");
  const r = await acao(() => api("/pagamentos", { metodo: "POST", corpo: d }));
  if (!r) return;
  if (r.troco && Number(r.troco) > 0) {
    // o troco precisa ficar na tela até o operador conferir: modal sem fechar sozinho
    await abrirModal({ titulo: "Pagamento registrado", tipo: "ok",
      corpo: `Valor pago: ${moeda(r.valor_pago)}\nRecebido do cliente: ${moeda(r.valor_recebido)}\nTROCO A DEVOLVER: ${moeda(r.troco)}`,
      botoes: [{ texto: "OK", valor: true, tipo: "primario" }], cancelar: true });
  } else aviso(`Pagamento registrado: ${moeda(r.valor_pago)}.`);
  e.target.reset(); comboMov.limpar(); comboCob.limpar(); comboCli.limpar(); seq.limpar(); mostrarDica(); atualizarListas();
};

(async () => {
  await iniciarPagina("pagamentos");
  mostrarDica(); seq.limpar();
  pagAbertas.ir(1); pagLista.ir(1); carregarCaixa();
  // vindo da saída do horista (?mov=ID): já deixa a saída escolhida
  const q = Number(new URLSearchParams(location.search).get("mov")) || null;
  if (q) {
    const r = await acao(() => api(`/pagamentos/pendentes?id_movimentacao=${q}&pagina=1`));
    const x = r && r.dados[0];
    if (x) { comboMov.definir({ id: x.id_movimentacao, valor: Number(x.valor_total), rotulo: `${x.placa_registrada} • ${moeda(x.valor_total)} • ${dataHora(x.saida_em)}${x.nome_cliente ? " • " + x.nome_cliente : ""}` }); seq.avaliar(); }
  }
})();
