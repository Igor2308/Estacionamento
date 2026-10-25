const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
let paginador;

const seq = formularioSequencial({
  form: $("form"), botao: $("salvar"),
  campos: [
    { el: $("codigo"), filtro: filtros.codigoVaga,
      validar: v => (/^[A-Z0-9][A-Z0-9\-]{0,19}$/.test(v) ? null : "Código inválido: use letras, números e hífen.") },
    { el: $("setor"), opcional: true, filtro: filtros.texto(50),
      validar: v => (/^[\p{L}\d][\p{L}\d \-./]*$/u.test(v) ? null : "Setor inválido: evite símbolos especiais.") },
    { el: $("tipo_vaga") },
    { el: $("tipo_veiculo"), erroVazio: "Selecione o tipo de veículo da vaga." },
  ],
});

paginador = criarPaginador({
  barra: $("paginacao"), busca: $("busca"),
  carregar: (pagina, texto) => acao(() => api(`/vagas?pagina=${pagina}&busca=${enc(texto)}`)),
  desenhar: (dados, { vazio }) => {
    $("lista").innerHTML = dados.length ? dados.map(x => {
      let vinculo = "—";
      if (x.tipo_vaga === "MENSALISTA") {
        vinculo = x.id_cliente
          ? `${esc(x.nome_cliente)} <button class="mini sec" data-a="desvincular" data-id="${x.id_vaga}">Desvincular</button>`
          : (x.ativa ? `Livre <button class="mini" data-a="vincular" data-id="${x.id_vaga}" data-codigo="${esc(x.codigo)}">Vincular cliente</button>` : "Livre");
      }
      return `<tr><td><b>${esc(x.codigo)}</b></td><td>${esc(x.setor || "—")}</td><td>${x.tipo_vaga === "MENSALISTA" ? "Mensalista" : "Rotativa"}</td>
        <td>${TIPOS_VEICULO[x.tipo_veiculo] || esc(x.tipo_veiculo)}</td><td>${vinculo}</td><td><span class="tag ${x.ativa ? "ok" : "off"}">${x.ativa ? "Ativa" : "Inativa"}</span></td>
        <td>${celulaCadastro(x)}</td>
        <td><button class="mini ${x.ativa ? "perigo" : "sec"}" data-a="status" data-id="${x.id_vaga}" data-ativa="${x.ativa ? 0 : 1}">${x.ativa ? "Desativar" : "Ativar"}</button></td></tr>`;
    }).join("") : linhasVazias(8, vazio);
  },
});

/* Escolher o cliente mensalista num modal com busca (sem carregar todos os clientes). */
function escolherClienteMensalista(codigo) {
  const corpo = document.createElement("div");
  const p = document.createElement("p"); p.style.margin = "0 0 .6rem"; p.textContent = `Escolha o cliente mensalista que vai ficar com a vaga ${codigo}:`;
  const caixa = document.createElement("div");
  const erro = document.createElement("small"); erro.className = "erro-campo";
  corpo.append(p, caixa, erro);
  let combo;
  return abrirModal({
    titulo: "Vincular vaga", corpo,
    botoes: [{ texto: "Cancelar", valor: null, tipo: "sec" }, { texto: "Vincular", valor: "ok", tipo: "primario" }],
    cancelar: null,
    aoAbrir: () => {
      combo = criarBusca(caixa, {
        placeholder: "Digite o nome ou CPF do cliente…",
        buscar: async t => (await api(`/clientes?ativo=1&modalidade=MENSALISTA&pagina=1&busca=${enc(t)}`)).dados.map(c => ({ id: c.id_cliente, rotulo: `${c.nome} — ${fmtDocumento(c)}` })),
        aoEscolher: () => (erro.textContent = ""),
      });
      combo.input.focus();
    },
    antesDeFechar: v => {
      if (v !== "ok") return true;
      if (!combo.valor) { erro.textContent = "Escolha um cliente mensalista da lista."; combo.input.focus(); return false; }
      return true;
    },
  }).then(v => (v === "ok" ? Number(combo.valor) : null));
}

$("lista").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = b.dataset.id; let r;
  if (b.dataset.a === "vincular") {
    const cli = await escolherClienteMensalista(b.dataset.codigo); if (!cli) return;
    r = await acao(() => api(`/vagas/${id}/vincular`, { metodo: "POST", corpo: { id_cliente: cli } }), x => x.mensagem);
  } else if (b.dataset.a === "desvincular") {
    if (!(await confirmar("Desvincular o cliente desta vaga? Ela ficará livre.", { titulo: "Desvincular vaga", confirmar: "Desvincular", perigo: true }))) return;
    r = await acao(() => api(`/vagas/${id}/desvincular`, { metodo: "POST" }), "Vaga desvinculada.");
  } else {
    r = await acao(() => api(`/vagas/${id}/status`, { metodo: "PATCH", corpo: { ativa: b.dataset.ativa === "1" } }), x => x.mensagem);
  }
  if (r) paginador.recarregar();
};

$("form").onsubmit = async e => {
  e.preventDefault();
  if (!seq.tocarTudo()) return;
  const corpo = { codigo: $("codigo").value.trim(), setor: $("setor").value.trim(), tipo_vaga: $("tipo_vaga").value, tipo_veiculo: $("tipo_veiculo").value };
  if (await acao(() => api("/vagas", { metodo: "POST", corpo }), "Vaga cadastrada.")) { e.target.reset(); paginador.recarregar(); }
};
(async () => {
  await iniciarPagina("vagas"); paginador.ir(1);
  if (new URLSearchParams(location.search).has("novo")) $("codigo").focus(); // vindo do painel
})();
