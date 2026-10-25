const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
let veiculos = [], editando = null, paginador;

const opcoes = (lista, id, rotulo, vazio) =>
  `<option value="">${vazio}</option>` + lista.map(x => `<option value="${x[id]}">${esc(rotulo(x))}</option>`).join("");

/* ---------- listas (marca / modelo / cor) ---------- */
async function carregarMarcas(selecionar) {
  const r = await acao(() => api("/marcas")); if (!r) return;
  $("marca").innerHTML = opcoes(r.dados, "id_marca", x => x.nome, "Selecione...");
  if (selecionar) $("marca").value = selecionar;
}
async function carregarModelos(selecionar) {
  const marca = $("marca").value;
  if (!marca) { $("modelo").innerHTML = '<option value="">Escolha a marca primeiro</option>'; seq.avaliar(); return; }
  const r = await acao(() => api("/modelos?id_marca=" + marca)); if (!r) return;
  $("modelo").innerHTML = opcoes(r.dados, "id_modelo", x => x.nome, "Selecione...");
  if (selecionar) $("modelo").value = selecionar;
  seq.avaliar();
}
async function carregarCores(selecionar) {
  const r = await acao(() => api("/cores")); if (!r) return;
  $("cor").innerHTML = opcoes(r.dados, "id_cor", x => x.nome, "Selecione...");
  if (selecionar) $("cor").value = selecionar;
}

/* cadastra um item novo na lista e já deixa selecionado (se já existir, só seleciona) */
const REGRAS = {
  marca: { max: 60, ok: /^[\p{L}\d][\p{L}\d .\-/]*$/u, msg: "Use letras, números, espaço, ponto, hífen ou barra." },
  modelo: { max: 80, ok: /^[\p{L}\d][\p{L}\d .\-/]*$/u, msg: "Use letras, números, espaço, ponto, hífen ou barra." },
  cor: { max: 40, ok: /^\p{L}[\p{L} \-]*$/u, msg: "Use somente letras (ex.: Azul metálico)." },
};
async function novoItem(rotulo, caminho, corpoExtra, campoId, recarregar) {
  const regra = REGRAS[rotulo];
  const nome = await perguntar(`Nome da nova ${rotulo}:`, {
    titulo: "Nova " + rotulo, maxlength: regra.max,
    validar: t => (regra.ok.test(t) ? null : regra.msg),
  });
  if (!nome) return;
  const r = await acao(() => api(caminho, { metodo: "POST", corpo: { ...corpoExtra, nome } }));
  if (!r) return;
  aviso(r.ja_existia ? `"${r.nome}" já estava cadastrada — selecionei para você.` : `"${r.nome}" cadastrada e selecionada.`);
  await recarregar(r[campoId]);
}

/* ---------- formulário em sequência ---------- */
const valorBusca = combo => combo.valor || (combo.input.value.trim() ? "?" : "");
const comboCliente = criarBusca($("comboCliente"), {
  placeholder: "Digite o nome ou CPF/CNPJ do cliente…",
  buscar: async texto => (await api(`/clientes?ativo=1&pagina=1&busca=${enc(texto)}`)).dados.map(c => ({
    id: c.id_cliente, rotulo: `${c.nome} — ${fmtDocumento(c)}`,
  })),
});

const seq = formularioSequencial({
  form: $("form"), botao: $("salvar"),
  campos: [
    { el: comboCliente.input, valor: () => valorBusca(comboCliente), bloqueado: () => !!editando,
      validar: v => (v === "?" ? "Escolha um cliente da lista." : null), erroVazio: "Escolha o cliente." },
    { el: $("placa"), filtro: filtros.placa, tamanho: 7,
      validar: v => (v.length < 7 ? "Placa incompleta: use o formato ABC1234 ou ABC1D23." : placaValida(v) ? null : "Placa inválida. Use o formato ABC1234 ou ABC1D23.") },
    { el: $("tipo") },
    { el: $("marca"), extras: [$("novaMarca")], erroVazio: "Selecione a marca.",
      aoMudar: () => { $("modelo").value = ""; carregarModelos(); } },
    { el: $("modelo"), extras: [$("novoModelo")], erroVazio: "Selecione o modelo." },
    { el: $("cor"), extras: [$("novaCor")], erroVazio: "Selecione a cor." },
  ],
});

$("novaMarca").onclick = async () => { await novoItem("marca", "/marcas", {}, "id_marca", carregarMarcas); await carregarModelos(); seq.avaliar(); };
$("novoModelo").onclick = async () => {
  if (!$("marca").value) return aviso("Escolha a marca antes de cadastrar o modelo.", "erro");
  await novoItem("modelo", "/modelos", { id_marca: Number($("marca").value) }, "id_modelo", carregarModelos); seq.avaliar();
};
$("novaCor").onclick = async () => { await novoItem("cor", "/cores", {}, "id_cor", carregarCores); seq.avaliar(); };

/* ---------- lista de veículos (50 por página + busca) ---------- */
paginador = criarPaginador({
  barra: $("paginacao"), busca: $("busca"),
  carregar: (pagina, texto) => acao(() => api(`/veiculos?pagina=${pagina}&busca=${enc(texto)}`)),
  desenhar: (dados, { vazio }) => {
    veiculos = dados;
    $("lista").innerHTML = dados.length ? dados.map(v => `<tr>
      <td><b>${esc(v.placa)}</b></td><td>${esc(v.nome_cliente)}</td><td>${TIPOS_VEICULO[v.tipo_veiculo] || esc(v.tipo_veiculo)}</td>
      <td>${esc([v.marca, v.modelo].filter(Boolean).join(" ") || "—")}</td><td>${esc(v.cor || "—")}</td>
      <td><span class="tag ${v.ativo ? "ok" : "off"}">${v.ativo ? "Ativo" : "Inativo"}</span></td>
      <td>${celulaCadastro(v)}</td>
      <td><button class="mini sec" data-a="editar" data-id="${v.id_veiculo}">Editar</button>
          <button class="mini ${v.ativo ? "perigo" : "sec"}" data-a="${v.ativo ? "desativar" : "reativar"}" data-id="${v.id_veiculo}">${v.ativo ? "Desativar" : "Reativar"}</button></td></tr>`).join("")
      : linhasVazias(8, vazio);
  },
});

$("lista").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = Number(b.dataset.id), v = veiculos.find(x => x.id_veiculo === id);
  if (!v) return;
  if (b.dataset.a === "editar") {
    limparFormulario();
    editando = id; $("tituloForm").textContent = "Editando: " + v.placa; $("salvar").textContent = "Salvar alterações";
    $("cancelar").classList.remove("oculto");
    // o dono do veículo não muda por aqui
    comboCliente.definir({ id: v.id_cliente, rotulo: v.nome_cliente });
    $("placa").value = v.placa; $("tipo").value = v.tipo_veiculo;
    $("marca").value = v.id_marca || ""; await carregarModelos(v.id_modelo); $("cor").value = v.id_cor || "";
    seq.limpar();
    scrollTo({ top: 0, behavior: "smooth" });
  } else if (b.dataset.a === "desativar") {
    if (!(await confirmar("Desativar o veículo " + v.placa + "?", { titulo: "Desativar veículo", confirmar: "Desativar", perigo: true }))) return;
    if (await acao(() => api("/veiculos/" + id, { metodo: "DELETE" }), "Veículo desativado.")) paginador.recarregar();
  } else {
    if (await acao(() => api("/veiculos/" + id, { metodo: "PUT", corpo: { ativo: true } }), "Veículo reativado.")) paginador.recarregar();
  }
};

function limparFormulario() {
  editando = null; $("form").reset(); comboCliente.limpar();
  $("modelo").innerHTML = '<option value="">Escolha a marca primeiro</option>';
  $("tituloForm").textContent = "Novo veículo"; $("salvar").textContent = "Salvar veículo"; $("cancelar").classList.add("oculto");
  seq.limpar();
}
$("cancelar").onclick = limparFormulario;

$("form").onsubmit = async e => {
  e.preventDefault();
  if (!seq.tocarTudo()) return;
  const corpo = {
    placa: $("placa").value.trim(), tipo_veiculo: $("tipo").value,
    id_marca: Number($("marca").value), id_modelo: Number($("modelo").value), id_cor: Number($("cor").value),
  };
  let r;
  if (editando) r = await acao(() => api("/veiculos/" + editando, { metodo: "PUT", corpo }), "Veículo atualizado.");
  else { corpo.id_cliente = Number(comboCliente.valor); r = await acao(() => api("/veiculos", { metodo: "POST", corpo }), "Veículo cadastrado."); }
  if (r) { limparFormulario(); paginador.recarregar(); }
};

(async () => {
  await iniciarPagina("veiculos");
  await Promise.all([carregarMarcas(), carregarCores()]);
  await carregarModelos(); paginador.ir(1);
  // vindo de outra tela com ?cliente=ID: já deixa o cliente escolhido
  if (new URLSearchParams(location.search).has("novo")) comboCliente.input.focus(); // vindo do painel
  const pre = Number(new URLSearchParams(location.search).get("cliente")) || null;
  if (pre) { const r = await acao(() => api("/clientes/" + pre)); if (r) comboCliente.definir({ id: r.dados.id_cliente, rotulo: `${r.dados.nome} — ${fmtDocumento(r.dados)}` }); }
})();
