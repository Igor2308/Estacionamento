const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
let pagAbertas, pagMensPatio, pagMensalistas, pagHistorico;

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
  const abas = { horista: ["painelHorista", "abaHorista"], patio: ["painelMensPatio", "abaMensPatio"], plano: ["painelMensalista", "abaMensalista"] };
  for (const [nome, [painel, botao]] of Object.entries(abas)) {
    $(painel).classList.toggle("oculto", nome !== aba);
    $(botao).classList.toggle("ativa", nome === aba);
  }
}
$("abaHorista").onclick = () => mostrarAba("horista");
$("abaMensPatio").onclick = () => mostrarAba("patio");
$("abaMensalista").onclick = () => mostrarAba("plano");

/* ---------- entrada: só aceita placa escolhida na lista de cadastradas ---------- */
const comboPlaca = criarBusca($("comboPlaca"), {
  placeholder: "Digite a placa ou o nome do cliente…",
  buscar: async t => (await api(`/veiculos?ativo=1&pagina=1&busca=${enc(t)}`)).dados.map(v => ({
    id: v.placa, rotulo: `${v.placa} — ${v.nome_cliente}${v.modalidade_cliente === "MENSALISTA" ? " (mensalista)" : ""}`,
  })),
});
const seq = formularioSequencial({
  form: $("form"), botao: $("salvar"),
  campos: [{ el: comboPlaca.input, valor: () => comboPlaca.valor || (comboPlaca.input.value.trim() ? "?" : ""),
    erroVazio: "Escolha a placa do veículo.", validar: v => (v === "?" ? "Escolha uma placa da lista (só placas cadastradas)." : null) }],
});
$("form").onsubmit = async e => {
  e.preventDefault();
  if (!seq.tocarTudo()) return;
  const r = await acao(() => api("/movimentacoes/entrada", { metodo: "POST", corpo: { placa: comboPlaca.valor } }),
    x => `Entrada de ${x.placa} registrada${x.modalidade === "MENSALISTA" ? " (mensalista)" : ""}.`);
  if (r) { comboPlaca.limpar(); seq.limpar(); recarregarTudo(); }
};

/* ---------- listas ---------- */
pagAbertas = criarPaginador({
  barra: $("pagAbertas"), busca: $("buscaAbertas"),
  carregar: (p, t) => acao(() => api(`/movimentacoes/abertas?apenas_horistas=1&pagina=${p}&busca=${enc(t)}`)),
  desenhar: (dados, { vazio }) => {
    carregadoEm = Date.now();
    $("abertas").innerHTML = dados.length ? dados.map(x => `<tr><td><b>${esc(x.placa_registrada)}</b></td>
      <td>${TIPOS_VEICULO[x.tipo_veiculo] || "—"}</td><td>${esc(x.nome_cliente || "—")}</td><td>${dataHora(x.entrada_em)}</td>
      <td>${esc(x.entrada_por_nome || "—")}</td>
      <td class="tempo" data-seg="${Number(x.segundos_no_patio) || 0}">${tempo(Number(x.segundos_no_patio) || 0)}</td>
      <td><button class="mini" data-id="${x.id_movimentacao}">Registrar saída</button></td></tr>`).join("")
      : linhasVazias(7, vazio === "Nenhum registro encontrado." ? "Nenhum horista no pátio." : vazio);
  },
});
pagMensPatio = criarPaginador({
  barra: $("pagMensPatio"), busca: $("buscaMensPatio"),
  carregar: (p, t) => acao(() => api(`/movimentacoes/abertas?apenas_mensalistas=1&pagina=${p}&busca=${enc(t)}`)),
  desenhar: (dados, { vazio }) => {
    carregadoEm = Date.now();
    $("mensPatio").innerHTML = dados.length ? dados.map(x => `<tr><td><b>${esc(x.placa_registrada)}</b></td>
      <td>${TIPOS_VEICULO[x.tipo_veiculo] || "—"}</td><td>${esc(x.nome_cliente || "—")}</td><td>${dataHora(x.entrada_em)}</td>
      <td>${esc(x.entrada_por_nome || "—")}</td>
      <td class="tempo" data-seg="${Number(x.segundos_no_patio) || 0}">${tempo(Number(x.segundos_no_patio) || 0)}</td>
      <td><button class="mini" data-id="${x.id_movimentacao}">Registrar saída</button></td></tr>`).join("")
      : linhasVazias(7, vazio === "Nenhum registro encontrado." ? "Nenhum mensalista no pátio." : vazio);
  },
});
pagMensalistas = criarPaginador({
  barra: $("pagMensalistas"), busca: $("buscaMensalistas"),
  carregar: (p, t) => acao(() => api(`/movimentacoes/mensalistas?pagina=${p}&busca=${enc(t)}`)),
  desenhar: (dados, { vazio }) => {
    $("mensalistas").innerHTML = dados.length ? dados.map(x => {
      const aberto = Number(x.valor_em_aberto) > 0;
      return `<tr><td><b>${esc(x.nome)}</b></td><td>${esc(x.codigo)}</td><td>${TIPOS_VEICULO[x.tipo_veiculo] || "—"}</td>
      <td>${aberto ? `<span class="tag off">${moeda(x.valor_em_aberto)}</span>` : '<span class="tag ok">Em dia</span>'}</td>
      <td><button class="mini perigo" data-vaga="${x.id_vaga}" data-nome="${esc(x.nome)}" data-cod="${esc(x.codigo)}" ${aberto ? 'disabled title="Pague o valor em aberto na tela Pagamentos"' : ""}>Cancelar vaga (saída)</button></td></tr>`;
    }).join("") : linhasVazias(5, vazio === "Nenhum registro encontrado." ? "Nenhuma vaga mensalista vinculada." : vazio);
  },
});
pagHistorico = criarPaginador({
  barra: $("pagHistorico"), busca: $("buscaHistorico"),
  carregar: (p, t) => acao(() => api(`/movimentacoes?fechadas=1&pagina=${p}&busca=${enc(t)}`)),
  desenhar: (dados, { vazio }) => {
    $("historico").innerHTML = dados.length ? dados.map(x => `<tr><td>${esc(x.placa_registrada)}</td>
      <td>${esc(x.nome_cliente || "—")}</td><td>${dataHora(x.entrada_em)}</td><td>${dataHora(x.saida_em)}</td>
      <td>${x.periodos_cobrados ?? 0}</td><td>${moeda(x.valor_total)}</td>
      <td>${esc(x.entrada_por_nome || "—")}</td><td>${esc(x.saida_por_nome || "—")}</td></tr>`).join("")
      : linhasVazias(8, vazio === "Nenhum registro encontrado." ? "Sem saídas registradas." : vazio);
  },
});
const recarregarTudo = () => { pagAbertas.recarregar(); pagMensPatio.recarregar(); pagMensalistas.recarregar(); pagHistorico.recarregar(); };

/* Saída de horista (calcula e oferece o pagamento) ou de mensalista (só libera a vaga). */
async function registrarSaida(e) {
  const b = e.target.closest("button"); if (!b) return;
  const r = await acao(() => api(`/movimentacoes/${b.dataset.id}/saida`, { metodo: "POST" }));
  if (!r) return;
  const valor = Number(r.valor_total);
  recarregarTudo();
  if (valor > 0) {
    const agora = await abrirModal({
      titulo: "Saída registrada", tipo: "ok",
      corpo: `${r.periodos_cobrados} período(s) de 30 min.\nTotal a cobrar: ${moeda(valor)}.\n\nRegistrar o pagamento agora?`,
      botoes: [{ texto: "Depois", valor: false, tipo: "sec" }, { texto: "Registrar pagamento", valor: true, tipo: "primario" }],
      cancelar: false,
    });
    if (agora) location.href = "pagamentos.html?mov=" + r.id_movimentacao;
  } else aviso("Saída registrada. Sem cobrança: a mensalidade é paga à parte.");
}
$("abertas").onclick = registrarSaida;
$("mensPatio").onclick = registrarSaida;
$("mensalistas").onclick = async e => {
  const b = e.target.closest("button"); if (!b || b.disabled) return;
  const ok = await confirmar(`Cancelar o plano da vaga ${b.dataset.cod} de ${b.dataset.nome}?\n\nA vaga será liberada. Se for a última vaga do cliente, ele passará a ser horista.`,
    { titulo: "Cancelar vaga", confirmar: "Cancelar vaga", cancelar: "Voltar", perigo: true });
  if (!ok) return;
  const r = await acao(() => api(`/movimentacoes/mensalistas/vagas/${b.dataset.vaga}/saida`, { metodo: "POST" }), x => x.mensagem);
  if (r) recarregarTudo();
};
(async () => {
  await iniciarPagina("movimentacoes"); seq.limpar();
  pagAbertas.ir(1); pagMensPatio.ir(1); pagMensalistas.ir(1); pagHistorico.ir(1);
  // atalhos do painel: ?novo=1 foca a placa da entrada; #saida leva até o cartão de saída
  if (new URLSearchParams(location.search).has("novo")) comboPlaca.input.focus();
  if (location.hash === "#saida") $("saida").scrollIntoView();
})();
